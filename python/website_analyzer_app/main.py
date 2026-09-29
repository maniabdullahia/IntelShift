import json
import os
import re
import sys
import time
from pathlib import Path
import traceback


def _fix_pycache():
    """
    Remove stale or corrupt .pyc files.

    Uses a two-pass strategy:
    1. Structural check: remove any .pyc that is corrupt (can't unmarshal) or
       whose source .py is newer than what the .pyc recorded (timestamp mismatch).
    2. Mtime-delta guard: also remove .pyc files where the source .py mtime is
       within ±2 seconds of the stored timestamp — OneDrive and network file-
       systems often don't preserve sub-second precision, so files copied/synced
       can appear same-timestamp even though the content changed.  Deleting these
       is cheap (Python just recompiles once) and prevents hard-to-debug import
       issues caused by stale bytecode.
    """
    import marshal, struct
    here = Path(__file__).parent
    removed_files = 0
    for pycache in list(here.rglob("__pycache__")):
        if not pycache.is_dir():
            continue
        for pyc in pycache.glob("*.pyc"):
            try:
                data = pyc.read_bytes()
                if len(data) < 20:
                    pyc.unlink(); removed_files += 1; continue
                # Validate bytecode is parseable
                marshal.loads(data[16:])
                src_py = pyc.parent.parent / (pyc.stem.split(".")[0] + ".py")
                if src_py.exists():
                    stored_ts = struct.unpack("<I", data[8:12])[0]
                    src_mtime = int(src_py.stat().st_mtime)
                    # Remove if source is newer OR within 2s (sync-lag safety margin)
                    if src_mtime >= stored_ts - 2:
                        pyc.unlink(); removed_files += 1
            except Exception:
                try:
                    pyc.unlink(); removed_files += 1
                except Exception:
                    pass
        try:
            if not any(pycache.iterdir()):
                pycache.rmdir()
        except Exception:
            pass
    if removed_files:
        print(f"[startup] Removed {removed_files} stale/corrupt .pyc file(s).")

_fix_pycache()

# Load .env early so all modules (fetcher, llm_extractor, etc.) see API keys via os.getenv().
try:
    from dotenv import load_dotenv as _load_dotenv
    from pathlib import Path as _DotenvPath
    _load_dotenv(dotenv_path=str(_DotenvPath(__file__).parent / ".env"), override=False)
    del _load_dotenv, _DotenvPath
except ImportError:
    pass

from level1_detector.fetcher import fetch_html, fetch_with_playwright, fetch_with_microlink, fetch_with_firecrawl, fetch_with_openai_browse
from level1_detector.jina_reader import fetch_with_jina, guess_page_type_from_url
from level1_detector.platform_detector import detect_platform
from level1_detector.page_type_detector import detect_page_type
from analyzers.shopify.shopify_analyzer import ShopifyAnalyzer
from analyzers.wordpress.wordpress_analyzer import WordPressAnalyzer
from analyzers.wix.wix_analyzer import WixAnalyzer
from analyzers.unknown.unknown_analyzer import UnknownAnalyzer
from post_processors.competitive_schema import normalize_for_competitive_analysis
from utils.page_guards import detect_page_block
from utils.currency import currency_from_text as _currency_from_text

BLOCKED_STATUS_CODES = {401, 403, 418, 429, 451, 503}

# Quality score below this threshold triggers automatic escalation to the next
# fetcher in the chain (Jina → Microlink → Firecrawl → OpenAI browse).
# The best-scoring result across all tried fetchers is returned.
QUALITY_ESCALATION_THRESHOLD = 0.50

# Hard time budget for the whole fallback chain (Jina → Microlink → Firecrawl
# → OpenAI). When exceeded, remaining tiers are skipped: we return the best
# partial result so far, or a website_blocked result if there is none.
# Override with env ANALYZER_FALLBACK_BUDGET_SECONDS.
FALLBACK_TIME_BUDGET_SECONDS = float(os.getenv("ANALYZER_FALLBACK_BUDGET_SECONDS", "90"))

# Shown verbatim by the client app when a site can't be analyzed.
WEBSITE_BLOCKED_USER_MESSAGE = (
    "This website blocks automated analysis, so we can't crawl it. "
    "Please choose a different competitor website."
)


def mark_website_blocked(normalized, reason=None):
    """Stamp the canonical website_blocked contract onto a result.

    Client apps (React) key off top-level `status == "website_blocked"` and
    display `userMessage`. `blockedReason` is one of:
    bot_protection | crawl_blocked | all_fetchers_failed | time_budget_exceeded
    """
    if not isinstance(normalized, dict):
        return normalized
    normalized["status"] = "website_blocked"
    normalized["success"] = False
    normalized["blocked"] = True
    normalized["userMessage"] = WEBSITE_BLOCKED_USER_MESSAGE
    if reason:
        normalized["blockedReason"] = reason
    return normalized


def _budget_exceeded(chain_start, stage):
    elapsed = time.monotonic() - chain_start
    if elapsed > FALLBACK_TIME_BUDGET_SECONDS:
        print(
            f"[BUDGET] {elapsed:.0f}s elapsed (budget {FALLBACK_TIME_BUDGET_SECONDS:.0f}s) "
            f"— skipping {stage}"
        )
        return True
    return False


def _get_result_quality(normalized):
    """
    Return an effective quality score for escalation decisions.

    Starts from extractionQuality.score (completeness) and applies penalties
    from dataConsistency flags (correctness signals).  This means a result that
    is structurally complete but has wrong data — e.g. price in USD on a .pk
    site — will get a lower effective score and trigger escalation rather than
    being returned as final.

    Penalties (non-cumulative cap at -0.20 total from consistency):
      currency_likely_wrong  → -0.12
      price_mismatch         → -0.10
      product_name_equals_*  → -0.08
    """
    eq = (normalized.get("analysisReady") or {}).get("extractionQuality", {})
    base_score = float(eq.get("score", 0) or 0)

    dc = eq.get("dataConsistency") or {}
    flags = dc.get("flags") or []
    penalty = 0.0
    if any("currency_likely_wrong" in f for f in flags):
        penalty += 0.12
    if any("price_mismatch" in f for f in flags):
        penalty += 0.10
    if any("product_name_equals" in f for f in flags):
        penalty += 0.08
    if any("collection_prices_missing" in f for f in flags):
        penalty += 0.15
    if any("collection_prices_partial" in f for f in flags):
        penalty += 0.08
    # Cap consistency penalty so a completeness-good result can't drop below 0.30
    penalty = min(penalty, 0.20)

    effective = round(base_score - penalty, 4)
    if penalty > 0:
        print(f"[QUALITY] consistency penalty -{penalty:.2f} "
              f"(base={base_score:.2f} → effective={effective:.2f}) flags={flags}")
    return effective


def choose_analyzer(platform: str, confidence: float = 1.0):
    # Below 0.65 confidence the platform signal is too weak to trust.
    # Route to UnknownAnalyzer so we return honest nulls rather than wrong
    # data from a mismatched platform-specific analyzer.
    _CONFIDENCE_FLOOR = 0.65
    if confidence < _CONFIDENCE_FLOOR and platform not in ("Unknown",):
        print(f"[PLATFORM] Low confidence ({confidence:.2f}) for '{platform}' — routing to UnknownAnalyzer")
        return UnknownAnalyzer()
    if platform == "Shopify":
        return ShopifyAnalyzer()
    if platform in ["WordPress", "WooCommerce / WordPress"]:
        return WordPressAnalyzer()
    if platform == "Wix":
        return WixAnalyzer()
    return UnknownAnalyzer()


def normalize_url(url: str):
    url = (url or "").strip()
    if not url.startswith("http"):
        url = "https://" + url
    return url


def is_blocked_response(html, headers):
    headers = headers or {}
    status_code = (
        headers.get("status_code")
        or headers.get("statusCode")
        or headers.get("Status-Code")
    )
    try:
        status_code = int(status_code) if status_code is not None else None
    except Exception:
        status_code = None
    if html is None:
        return True, status_code
    if status_code in BLOCKED_STATUS_CODES:
        return True, status_code
    return False, status_code


# URL path fragments that indicate a bot-protection redirect (HTTP 200)
_BOT_BLOCK_URL_TERMS = [
    "/blocked", "robot-or-human", "/captcha", "/challenge/",
    "access-denied", "security-check", "/verify",
]

# Title / H1 patterns that unmistakably signal a bot-protection page
_BOT_BLOCK_TITLE_RE = re.compile(
    r'\b(?:robot\s+or\s+human|access\s+denied|blocked'
    r'|just\s+a\s+moment|verify\s+you(?:\'?re|\s+are)\s+human'
    r'|security\s+check|please\s+complete\s+the\s+security'
    r'|checking\s+if\s+the\s+site\s+connection\s+is\s+secure'
    r'|enable\s+javascript\s+and\s+cookies\s+to\s+continue)\b',
    re.I
)

# Body-text patterns (scanned in first 2 000 chars of HTML)
_BOT_BLOCK_BODY_RE = re.compile(
    r'\b(?:activate\s+and\s+hold\s+the\s+button'
    r'|verify\s+that\s+you\'?re?\s+human'
    r'|please\s+complete\s+the\s+security\s+check'
    r'|enable\s+cookies\s+and\s+reload'
    r'|ddos\s+protection\s+by)\b',
    re.I
)


def is_bot_protection_page(url, html):
    """Return True for bot-protection / CAPTCHA pages that return HTTP 200.

    Checks three signals in order:
      1. Final URL contains a known challenge path fragment.
      2. Page title / first H1 matches bot-protection wording.
      3. First 2 000 chars of HTML body contain challenge-specific text.
    """
    url_l = (url or "").lower()
    if any(t in url_l for t in _BOT_BLOCK_URL_TERMS):
        return True

    if not html:
        return False

    head_chunk = html[:2000].lower()
    if _BOT_BLOCK_TITLE_RE.search(head_chunk):
        return True
    if _BOT_BLOCK_BODY_RE.search(head_chunk):
        return True
    return False


def bot_protection_result(input_url, final_url, headers, status_code):
    """Structured result for a page blocked by bot-protection (HTTP 200 challenge)."""
    return {
        "success": False,
        "status": "website_blocked",
        "blocked": True,
        "blockedReason": "bot_protection",
        "userMessage": WEBSITE_BLOCKED_USER_MESSAGE,
        "crawl": {
            "success": False,
            "blocked": True,
            "crawlBlocked": True,
            "statusCode": status_code or 200,
            "blockedReason": "bot_protection",
            "reason": (
                "Bot-protection / CAPTCHA page detected "
                "(HTTP 200 with challenge content)."
            ),
        },
        "inputUrl": input_url,
        "finalUrl": final_url or input_url,
        "platform": "Unknown",
        "page": {"url": final_url or input_url, "pageType": "blocked"},
        "technical": {"responseHeaders": headers or {}},
        "source": {"stage": "fetcher", "success": False},
    }


def blocked_result(input_url, final_url, headers, status_code, reason=None, blocked_reason="crawl_blocked"):
    headers = headers or {}
    return {
        "success": False,
        "status": "website_blocked",
        "blocked": True,
        "blockedReason": blocked_reason,
        "userMessage": WEBSITE_BLOCKED_USER_MESSAGE,
        "crawl": {
            "success": False, "blocked": True, "crawlBlocked": True,
            "statusCode": status_code,
            "reason": reason or "Request was blocked or no HTML was returned."
        },
        "inputUrl": input_url,
        "finalUrl": final_url or input_url,
        "platform": "Unknown",
        "page": {"url": final_url or input_url, "pageType": "unknown"},
        "technical": {"responseHeaders": headers},
        "source": {"stage": "fetcher", "success": False}
    }


def jina_fallback_content_result(input_url, jina_result, original_headers=None):
    final_url   = jina_result.get("finalUrl") or input_url
    page_type   = guess_page_type_from_url(final_url)
    title       = jina_result.get("title") or ""
    description = jina_result.get("description") or ""
    markdown    = jina_result.get("markdown") or ""
    status_code = jina_result.get("statusCode")

    result = {
        "success": False,
        "crawl": {
            "success": False, "blocked": True, "crawlBlocked": True,
            "statusCode": status_code,
            "reason": "Normal crawler failed. Jina Reader fallback content was saved for AI analysis.",
            "retryable": True
        },
        "inputUrl": input_url,
        "finalUrl": final_url,
        "platform": "Unknown",
        "page": {"url": final_url, "pageType": page_type},
        "seo": {
            "title": title, "metaDescription": description,
            "canonical": final_url, "h1": title
        },
        "content": {"title": title, "summaryText": description, "mainText": "", "headings": []},
        "ecommerce": {
            "hasEcommerceSignals": page_type in ["product", "collection"],
            "products": [], "categoryLinks": [],
            "hasProductGrid": False, "hasCategories": False, "hasCartOrCheckout": False
        },
        "products": [],
        "technical": {
            "finalUrl": final_url,
            "responseHeaders": {
                **(jina_result.get("headers") or {}),
                "status_code": status_code, "blocked": True,
                "fetch_method": "jina_reader",
                "jina_usable": jina_result.get("usable"),
                "original_fetch_headers": original_headers or {}
            }
        },
        "source": {
            "stage": "jina_reader", "success": False,
            "fetchFallback": "jina_reader", "fallbackSavedForAI": True
        },
        "fallbackContent": {
            "source": "jina_reader", "url": final_url,
            "title": title, "description": description,
            "markdown": markdown, "text": markdown,
            "usable": jina_result.get("usable"),
            "reason": jina_result.get("reason"),
            "recommendedUse": (
                "Send this fallbackContent to OpenAI only if normal structured "
                "extraction is missing or low quality."
            )
        }
    }

    normalized = normalize_for_competitive_analysis(result)
    normalized["analysisReady"]["extractionQuality"]["score"] = 0.35 if markdown else 0
    normalized["analysisReady"]["extractionQuality"]["warnings"] = [
        "Normal crawler failed.",
        "Jina Reader fallback content was saved for AI analysis.",
        "Structured analyzer output is incomplete for this page."
    ]
    normalized["analysisReady"]["extractionQuality"]["missingFields"] = [
        "structuredPageContent", "products", "prices"
    ]
    # Structured extraction failed — from the client's point of view this site
    # can't be analyzed, even though raw markdown was saved for AI use.
    return mark_website_blocked(normalized, reason="crawl_blocked")


def _is_wix_collection_markdown(markdown):
    """
    Return True when Jina markdown appears to be a Wix collection/catalog page.
    Used to force platform=Wix when platform detection returns Unknown.
    Requires wixstatic.com + at least one strong collection indicator.
    """
    import re as _re
    if not markdown:
        return False
    m_lower = markdown.lower()
    if "wixstatic.com" not in m_lower and "wix.com" not in m_lower:
        return False
    has_filter_sort  = "filter by" in m_lower and "sort by" in m_lower
    has_quick_view   = "quick view" in m_lower
    price_count      = len(_re.findall(r"[$£€]\s?\d+", markdown))
    product_page_cnt = len(_re.findall(r"/product-page/[^\s)\"']+", m_lower))
    collection_links = len(_re.findall(r"/collection/[a-z0-9\-]+", m_lower))
    load_more        = "load more" in m_lower
    return (
        has_filter_sort
        or has_quick_view
        or price_count >= 3
        or product_page_cnt >= 3
        or collection_links >= 5
        or load_more
    )


def _parse_jina_markdown_categories(markdown):
    """Extract category names from '## Product Categories' section in Jina markdown.
    Returns list of {"name": str, "url": None} dicts, or [] if section absent."""
    # Strip image markdown (![alt](url)) before parsing — prevents image URLs
    # from being treated as category or product names (Mubah Group issue).
    markdown = re.sub(r"!\[.*?\]\(.*?\)", "", markdown)
    match = re.search(
        r'##\s+Product\s+Categor\w*\s*\n([\s\S]+?)(?=\n##|\Z)', markdown, re.I
    )
    if not match:
        return []
    text = match.group(1).strip()
    # Items may be newline, bullet, or space-separated (e.g. "Paint Car Care Adhesives")
    # Split on newlines/bullets first, then fall back to space-separated words
    raw = [c.strip("*- \t") for c in re.split(r'[\n\*\-]+', text)]
    items = []
    for chunk in raw:
        chunk = chunk.strip()
        if not chunk:
            continue
        # Chunk looks like "Paint Car Care Adhesives" — split by 2+ spaces or title case
        sub = re.split(r'\s{2,}|(?<=[a-z])(?=[A-Z])', chunk)
        for s in sub:
            s = s.strip()
            if 2 < len(s) < 60:
                items.append(s)
    # Dedupe preserving order
    seen = set()
    cats = []
    for name in items:
        if name.lower() not in seen:
            seen.add(name.lower())
            cats.append({"name": name, "url": None})
    return cats[:30]


def _parse_jina_markdown_products(markdown):
    """Extract product names from Jina markdown.

    Two extraction passes:

    Pass 1 — section-based: looks for a '## Featured Items' (or similar)
      heading and parses the list below it.

    Pass 2 — heading+size: detects the consumer-brand pattern where each
      product is its own ## heading immediately followed by a size line:

        ## Crispy Mini Gem
        113g & 226g

        ## Peppery Arugula
        80g
    """
    # Pre-clean: strip image markdown and video-placeholder links before any
    # regex matching.  Jina renders YouTube embeds as [Video N](url) which
    # can appear between a ## heading and its size line, breaking Pass 2.
    markdown = re.sub(r"!\[.*?\]\(.*?\)", "", markdown or "")
    markdown = re.sub(r"\[Video\s+\d+\]\([^)]*\)", "", markdown, flags=re.IGNORECASE)

    products = []
    seen = set()

    # ----------------------------------------------------------------
    # Pass 1: named section (Featured Items / New Arrivals / etc.)
    # ----------------------------------------------------------------
    match = re.search(
        r'##\s+(?:Featured\s+Items?|New\s+Arrivals?|Best\s+Sellers?|Products?)\s*\n([\s\S]+?)(?=\n##|\Z)',
        markdown, re.I
    )
    if match:
        text = match.group(1).strip()
        raw = [c.strip("*- \t") for c in re.split(r'[\n\*\-]+', text)]
        for item in raw:
            item = item.strip()
            if not item or len(item) < 3 or len(item) > 100:
                continue
            price_match = re.search(
                r'(?:AED|€|£|\$|₨|Rs\.?|PKR)\s*[\d,.]+(?:\.\d{1,2})?'
                r'|[\d,.]+\s*(?:AED)',
                item, re.I
            )
            price_raw = price_match.group(0) if price_match else None
            name = item.replace(price_raw, "").strip(" –—-") if price_raw else item
            name = name.strip()
            if not name or len(name) < 3 or name.lower() in seen:
                continue
            seen.add(name.lower())
            products.append({
                "name": name,
                "url": None,
                "price": price_raw,
                "priceTextRaw": price_raw,
                "image": None,
                "imageUrl": None,
                "badge": None,
                "sectionName": "Featured Items",
                "source": "jina_markdown"
            })

    # ----------------------------------------------------------------
    # Pass 2: ## ProductName\n<size line>
    # Consumer brands (e.g. havengreens.ca) list each SKU as its own
    # H2 heading with a size or weight line immediately below.
    # Always runs — `seen` set prevents duplicates with Pass 1.
    # ----------------------------------------------------------------
    if True:
        # Pattern: ## Some Product Name\n(optional blank)\n<size spec>
        # Size spec: digits + unit, optionally multiple separated by & or ,
        # Also handles pack formats like "12-pack", "6-pack"
        _SIZE_UNIT = r'(?:g|kg|ml|l|cl|oz|lb|lbs|litre|liter)s?'
        _SIZE_VAL  = r'\d+\s*' + _SIZE_UNIT
        _SIZE_ITEM = r'(?:\d+[-\s]pack|' + _SIZE_VAL + r')'
        _SIZE_LINE = (
            r'(?:' + _SIZE_ITEM +
            r'(?:\s*[&,/]\s*' + _SIZE_ITEM + r')*)'
        )
        heading_size_re = re.compile(
            r'^##\s+(.+?)\s*\n+(' + _SIZE_LINE + r')',
            re.MULTILINE | re.IGNORECASE
        )
        for m in heading_size_re.finditer(markdown):
            name = m.group(1).strip()
            size = m.group(2).strip()
            if not name or len(name) < 3 or len(name) > 120:
                continue
            if name.lower() in seen:
                continue
            seen.add(name.lower())
            products.append({
                "name": name,
                "size": size,
                "url": None,
                "price": None,
                "priceTextRaw": None,
                "image": None,
                "imageUrl": None,
                "badge": None,
                "sectionName": "Products",
                "source": "jina_product_heading"
            })

    return products[:20]


def _jina_markdown_to_html(markdown, title="", description=""):
    """Convert Jina Reader markdown to structured HTML.

    Produces a <section> block for each ## / ### heading so that
    extract_sections() sees one section per heading (4+ for most brand
    homepages) instead of a single monolithic blob.

    Pre-filters YouTube/video embed placeholders ("Video 1", "Video 2", …)
    that Jina renders as link text — these are not real navigation or CTAs.

    Pre-heading content (preamble lines before the first heading) is wrapped
    in <p class="jina-preamble"> so extract_hero() can skip it when looking
    for the hero subheadline / story.
    """
    import re as _re

    md = markdown or ""

    # ------------------------------------------------------------------
    # 1. Remove video-placeholder links before any other processing.
    #    Jina renders YouTube/video embeds as [Video N](url) — strip them.
    # ------------------------------------------------------------------
    md = _re.sub(r'\[Video\s+\d+\]\([^)]*\)', '', md, flags=_re.IGNORECASE)

    # ------------------------------------------------------------------
    # 2. Inline markup: images and links (order matters)
    # ------------------------------------------------------------------
    # [![alt](img)](href)
    md = _re.sub(
        r'\[!\[([^\]]*)\]\(([^)]+)\)\]\(([^)]+)\)',
        r'<a href="\3"><img src="\2" alt="\1"></a>', md
    )
    # ![alt](src)
    md = _re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', r'<img src="\2" alt="\1">', md)
    # [text](href)
    md = _re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', md)
    # list items (* and *   variants)
    md = _re.sub(r'^\*   (.+)$', r'<li>\1</li>', md, flags=_re.MULTILINE)
    md = _re.sub(r'^\* (.+)$',   r'<li>\1</li>', md, flags=_re.MULTILINE)

    # ------------------------------------------------------------------
    # 3. Split markdown into (level, heading_text, [body_lines]) chunks
    #    at each heading boundary (####/###/##/#).
    # ------------------------------------------------------------------
    chunks: list = []          # list of (int level, str|None heading, list[str] body)
    cur_lvl   = 0              # 0 = pre-heading preamble
    cur_head  = None
    cur_body: list = []

    for line in md.splitlines():
        m4 = _re.match(r'^#### (.+)$', line)
        m3 = _re.match(r'^### (.+)$',  line)
        m2 = _re.match(r'^## (.+)$',   line)
        m1 = _re.match(r'^# (.+)$',    line)

        if m4 or m3 or m2 or m1:
            chunks.append((cur_lvl, cur_head, cur_body))
            m         = m4 or m3 or m2 or m1
            cur_lvl   = 4 if m4 else (3 if m3 else (2 if m2 else 1))
            cur_head  = m.group(1).strip()
            cur_body  = []
        else:
            cur_body.append(line)

    chunks.append((cur_lvl, cur_head, cur_body))

    # ------------------------------------------------------------------
    # 4. Render chunks to HTML
    # ------------------------------------------------------------------
    html_parts: list = []

    for (lvl, htext, body_lines) in chunks:
        # Turn body lines into paragraphs (split at blank lines, then at
        # single newlines so single-\n-separated items each get a <p>).
        raw = '\n'.join(body_lines)
        paras: list = []
        for seg in _re.split(r'\n{2,}', raw):
            for subline in seg.splitlines():
                s = subline.strip()
                if s:
                    paras.append(s)

        if lvl == 0:
            # Pre-heading preamble — mark with class so hero extraction
            # can skip it (avoids meta-description becoming subheadline).
            for p in paras:
                html_parts.append(f'<p class="jina-preamble">{p}</p>')

        elif lvl == 1:
            # H1 = SEO page title — standalone element, NOT in a <section>
            html_parts.append(f'<h1>{htext}</h1>')
            for p in paras:
                html_parts.append(f'<p class="jina-preamble">{p}</p>')

        else:
            # H2 / H3 / H4 = content section — wrap with <section>
            htag = f'h{lvl}'
            inner = f'<{htag}>{htext}</{htag}>'
            for p in paras:
                inner += f'<p>{p}</p>'
            html_parts.append(f'<section>{inner}</section>')

    meta = (f'<meta name="description" content="{description}">'
            if description else '')
    body = ''.join(html_parts)
    return (
        f'<html><head><title>{title}</title>{meta}</head>'
        f'<body>{body}</body></html>'
    )


def analyze_with_jina_fallback(input_url, original_headers=None):
    _chain_start = time.monotonic()

    def _time_budget_blocked():
        """website_blocked result for when the fallback chain runs out of time."""
        return mark_website_blocked(
            normalize_for_competitive_analysis(blocked_result(
                input_url=input_url, final_url=input_url,
                headers={
                    "blocked": True, "fetch_method": "budget_exceeded",
                    "original_fetch_headers": original_headers or {},
                },
                status_code=None,
                reason=f"Fallback chain exceeded the {FALLBACK_TIME_BUDGET_SECONDS:.0f}s time budget.",
                blocked_reason="time_budget_exceeded",
            )),
            reason="time_budget_exceeded",
        )

    jina_result = fetch_with_jina(input_url)

    # Treat "success but unusable" the same as failure — Jina sometimes returns
    # HTTP 200 but proxies the target site's error body (e.g. Lululemon returns
    # {"message":"Bad Request.","errorCode":"GE401001"} with Content-Type:
    # application/json). usable=False + tiny markdown = no real content fetched.
    _jina_ok = (
        jina_result.get("success")
        and jina_result.get("usable")
        and len((jina_result.get("markdown") or "").strip()) >= 200
    )

    # Best result tracking across ALL fetcher tiers.
    # Whichever fetcher produces the highest quality score wins.
    # _esc_best is set when Jina succeeds but quality < QUALITY_ESCALATION_THRESHOLD.
    # _fallback_best is set when Jina fails and we try ML/FC/OA.
    _esc_best         = None   # best result when Jina OK but low quality
    _esc_best_score   = -1.0
    _fallback_best       = None  # best result when Jina not OK
    _fallback_best_score = -1.0
    _jina_fail_reason = (
        jina_result.get("reason")
        or ("Jina returned unusable content" if jina_result.get("success") else "Jina request failed")
    )

    if not _jina_ok:
        # ── Tier 2.5: Microlink ───────────────────────────────────────────────
        # Headless Puppeteer + stealth — different fingerprint from Jina.
        # Free tier, no API key required.
        if _budget_exceeded(_chain_start, "Microlink"):
            return _time_budget_blocked()
        print(f"[MICROLINK] Jina not usable ({_jina_fail_reason}) — trying Microlink for {input_url}")
        ml = fetch_with_microlink(input_url)
        if ml.get("success"):
            ml_markdown    = ml["markdown"]
            ml_url         = ml.get("finalUrl") or input_url
            ml_title       = ml.get("title") or ""
            ml_description = ml.get("description") or ""

            try:
                ml_html          = _jina_markdown_to_html(ml_markdown, title=ml_title, description=ml_description)

                _ml_guard = detect_page_block(ml_markdown, ml_url)
                if _ml_guard["blocked"]:
                    print(f"[MICROLINK] Page guard blocked: {_ml_guard['reason']}")
                    raise ValueError(f"Page guard: {_ml_guard['reason']}")

                platform_result  = detect_platform(html=ml_markdown, url=ml_url, headers={})
                platform         = platform_result.get("platform", "Unknown")
                page_type_result = detect_page_type(html=ml_html, url=ml_url, platform=platform)
                detected_pt      = page_type_result.get("pageType", "general")

                analyzer = choose_analyzer(platform, platform_result.get("platformConfidence", 1.0))
                result   = analyzer.analyze(
                    url=ml_url, html=ml_html, headers={},
                    page_type=detected_pt,
                    level1={**platform_result, **page_type_result},
                )

                try:
                    from level1_detector.llm_extractor import run_llm_fallback_if_needed
                    result = run_llm_fallback_if_needed(result, ml_html, ml_url, detected_pt)
                except Exception as _llm_err:
                    print(f"LLM FALLBACK (microlink): error — {_llm_err}")

                result["success"]          = True
                result["extractionMethod"] = "microlink_fallback"
                result["crawl"] = {
                    "success": True, "blocked": True, "crawlBlocked": True,
                    "statusCode": 200,
                    "reason": "Normal crawler and Jina both blocked; content extracted via Microlink.",
                    "retryable": False, "microlinkAnalyzed": True,
                }
                result["inputUrl"] = input_url
                result.setdefault("technical", {})["responseHeaders"] = {
                    "blocked": True, "fetch_method": "microlink",
                    "original_fetch_headers": original_headers or {},
                }
                print(f"[MICROLINK] Success — platform={platform} pageType={detected_pt}")
                _ml_norm  = normalize_for_competitive_analysis(result)
                _ml_score = _get_result_quality(_ml_norm)
                print(f"[MICROLINK] Quality score={_ml_score:.2f}")
                if _ml_score > _fallback_best_score:
                    _fallback_best, _fallback_best_score = _ml_norm, _ml_score
                if _ml_score >= QUALITY_ESCALATION_THRESHOLD:
                    print(f"[MICROLINK] Score above threshold — using result")
                    return _fallback_best
                print(f"[MICROLINK] Score below threshold — continuing to Firecrawl")
            except Exception as _ml_err:
                print(f"[MICROLINK] Analysis error after fetch: {_ml_err}")

        print(f"[MICROLINK] Also failed: {ml.get('reason') if not ml.get('success') else 'analysis error'}")
        # ── end Microlink ─────────────────────────────────────────────────────

        if _budget_exceeded(_chain_start, "Firecrawl"):
            return _fallback_best if _fallback_best is not None else _time_budget_blocked()
        print(f"[FIRECRAWL] Trying Firecrawl for {input_url}")
        fc = fetch_with_firecrawl(input_url)
        if fc.get("success"):
            fc_html   = fc["html"]
            fc_url    = fc.get("finalUrl") or input_url
            fc_status = fc.get("statusCode")

            _fc_guard = detect_page_block(fc_html, fc_url)
            if _fc_guard["blocked"]:
                print(f"[FIRECRAWL] Page guard blocked ({_fc_guard['blockType']}): {_fc_guard['reason']} — skipping to next tier")
            else:
                platform_result  = detect_platform(html=fc_html, url=fc_url, headers={})
                platform         = platform_result.get("platform", "Unknown")
                page_type_result = detect_page_type(html=fc_html, url=fc_url, platform=platform)
                detected_pt      = page_type_result.get("pageType", "general")

                analyzer = choose_analyzer(platform, platform_result.get("platformConfidence", 1.0))
                result   = analyzer.analyze(
                    url=fc_url, html=fc_html, headers={},
                    page_type=detected_pt,
                    level1={**platform_result, **page_type_result},
                )

                # LLM fallback (pricing, product enrichment, etc.)
                try:
                    from level1_detector.llm_extractor import run_llm_fallback_if_needed
                    result = run_llm_fallback_if_needed(result, fc_html, fc_url, detected_pt)
                except Exception as _llm_err:
                    print(f"LLM FALLBACK (firecrawl): error — {_llm_err}")

                result["success"]          = True
                result["extractionMethod"] = "firecrawl_fallback"
                result["crawl"] = {
                    "success": True, "blocked": True, "crawlBlocked": True,
                    "statusCode": fc_status,
                    "reason": (
                        "Normal crawler and Jina both blocked; "
                        "content extracted via Firecrawl."
                    ),
                    "retryable": False, "firecrawlAnalyzed": True,
                }
                result["inputUrl"] = input_url
                result.setdefault("technical", {})["responseHeaders"] = {
                    "blocked": True, "fetch_method": "firecrawl",
                    "original_fetch_headers": original_headers or {},
                }
                print(f"[FIRECRAWL] Success — platform={platform} pageType={detected_pt}")
                _fc_norm  = normalize_for_competitive_analysis(result)
                _fc_score = _get_result_quality(_fc_norm)
                print(f"[FIRECRAWL] Quality score={_fc_score:.2f}")
                if _fc_score > _fallback_best_score:
                    _fallback_best, _fallback_best_score = _fc_norm, _fc_score
                if _fc_score >= QUALITY_ESCALATION_THRESHOLD:
                    print(f"[FIRECRAWL] Score above threshold — using result")
                    return _fallback_best
                print(f"[FIRECRAWL] Score below threshold — continuing to OpenAI")
        # ── end Firecrawl ──────────────────────────────────────────────────────

        print(f"[FIRECRAWL] Also failed: {fc.get('reason')}")

        # ── Tier 4: OpenAI web browse ──────────────────────────────────────────
        # Playwright, Jina, and Firecrawl all failed.  OpenAI's infrastructure
        # uses different IPs and can often retrieve content from sites blocked
        # by Cloudflare / Akamai.  Output is text/markdown; we process it the
        # same way as the Jina fallback path.
        # Detect page type from URL so OpenAI gets a task-specific prompt
        _url_page_type = guess_page_type_from_url(input_url)
        if _budget_exceeded(_chain_start, "OpenAI browse"):
            return _fallback_best if _fallback_best is not None else _time_budget_blocked()
        print(f"[OPENAI] Firecrawl failed — trying OpenAI web browse for {input_url} (pageType={_url_page_type})")
        oa = fetch_with_openai_browse(input_url, page_type=_url_page_type)
        if oa.get("success"):
            oa_markdown    = oa["markdown"]
            oa_url         = oa.get("finalUrl") or input_url
            oa_title       = oa.get("title") or ""
            oa_description = oa.get("description") or ""

            try:
                oa_html          = _jina_markdown_to_html(oa_markdown, title=oa_title, description=oa_description)
                platform_result  = detect_platform(html=oa_markdown, url=oa_url, headers={})
                platform         = platform_result.get("platform", "Unknown")
                # For OpenAI browse, trust URL-based page type over HTML-based:
                # the markdown output won't have DOM structure (no product grids,
                # no <a> links) so HTML-based detection degrades to "general".
                if _url_page_type and _url_page_type != "general":
                    detected_pt      = _url_page_type
                    page_type_result = {"pageType": detected_pt, "pageTypeConfidence": 0.9}
                else:
                    page_type_result = detect_page_type(html=oa_html, url=oa_url, platform=platform)
                    detected_pt      = page_type_result.get("pageType", "general")

                analyzer = choose_analyzer(platform, platform_result.get("platformConfidence", 1.0))
                result = analyzer.analyze(
                    url=oa_url, html=oa_html, headers={},
                    page_type=detected_pt,
                    level1={**platform_result, **page_type_result},
                )

                # Skip LLM fallback for collection/homepage — it targets
                # product/pricing extraction and misclassifies product lists
                # as SaaS plans on collection pages.
                if detected_pt not in ("collection", "homepage"):
                    try:
                        from level1_detector.llm_extractor import run_llm_fallback_if_needed
                        result = run_llm_fallback_if_needed(result, oa_html, oa_url, detected_pt)
                    except Exception as _llm_err:
                        print(f"LLM FALLBACK (openai browse): error — {_llm_err}")

                # ── Parse OpenAI structured sections from HTML ──────────────────
                # _jina_markdown_to_html converts ## headings into
                # <section><h2>Name</h2>...</section> blocks.
                # The generic analyzer doesn't look inside these, so we extract
                # every known section here and write directly into the result.
                _OA_ANY_SECTION_RE = re.compile(
                    r'<section>\s*<h2>(.*?)</h2>(.*?)</section>',
                    re.I | re.S,
                )
                _OA_LI_RE       = re.compile(r'<li>(.*?)</li>', re.I)
                # Matches "## Product Options" lines in the as-rendered HTML.
                # _jina_markdown_to_html does NOT convert **bold** → <strong>, so
                # "**Color**: Black, White" stays as literal ** inside a <p> tag.
                # Use [^<]+ to stop at the closing </p> tag.
                _OA_OPT_LINE_RE = re.compile(r'\*\*(.*?)\*\*:\s*([^<]+)')
                # Values that mean "no real data"
                _OA_JUNK_RE     = re.compile(
                    r'^(n/?a\.?|none|various|multiple|'
                    r'available in .+|not (available|found|shown)|tbd|-)$',
                    re.I,
                )

                _parsed_options    = []
                _related_products  = []
                _materials_text    = None
                _care_instructions = []

                for _sec in _OA_ANY_SECTION_RE.finditer(oa_html):
                    _sec_name = _sec.group(1).strip()
                    _sec_body = _sec.group(2)

                    if re.search(r'^product\s+options?$', _sec_name, re.I):
                        # Primary format: **Key**: val1, val2, val3 (bold markers)
                        _sec_opts = []
                        for _om in _OA_OPT_LINE_RE.finditer(_sec_body):
                            _ok  = _om.group(1).strip()
                            _ovs = [v.strip() for v in _om.group(2).split(',')]
                            _ovs = [v for v in _ovs
                                    if v and not _OA_JUNK_RE.match(v)]
                            if _ok and _ovs:
                                _sec_opts.append({"name": _ok, "values": _ovs})

                        # Fallback: plain "Key: val1, val2" inside <p> tags
                        # (OpenAI sometimes omits ** markers despite the prompt)
                        if not _sec_opts:
                            _OA_PLAIN_OPT_RE = re.compile(
                                r'<p>([A-Za-z][A-Za-z /&]{0,25}?):\s*([^<]{2,60})</p>',
                                re.I,
                            )
                            for _pm in _OA_PLAIN_OPT_RE.finditer(_sec_body):
                                _ok  = _pm.group(1).strip()
                                _ov_raw = _pm.group(2).strip()
                                _ovs = [v.strip() for v in _ov_raw.split(',')]
                                _ovs = [v for v in _ovs
                                        if v and len(v) <= 50
                                        and not _OA_JUNK_RE.match(v)]
                                if _ok and _ovs:
                                    _sec_opts.append({"name": _ok, "values": _ovs})

                        _parsed_options.extend(_sec_opts)

                    elif re.search(r'colou?rs?|sizes?|variants?', _sec_name, re.I):
                        # Legacy ## Colors / ## Sizes (backwards-compat if model uses old headings)
                        _vals = [
                            m.group(1).strip()
                            for m in _OA_LI_RE.finditer(_sec_body)
                            if m.group(1).strip()
                               and not _OA_JUNK_RE.match(m.group(1).strip())
                        ]
                        if _vals:
                            _on = "Color" if re.search(r'colou?r', _sec_name, re.I) else "Size"
                            _parsed_options.append({"name": _on, "values": _vals})

                    elif re.search(r'^materials?$', _sec_name, re.I):
                        _mt = re.sub(r'<[^>]+>', '', _sec_body).strip()
                        if _mt and not _OA_JUNK_RE.match(_mt):
                            _materials_text = _mt

                    elif re.search(r'^care\s+instructions?$', _sec_name, re.I):
                        _care_instructions = [
                            m.group(1).strip()
                            for m in _OA_LI_RE.finditer(_sec_body)
                            if m.group(1).strip()
                               and not _OA_JUNK_RE.match(m.group(1).strip())
                        ]

                    elif re.search(r'^related\s+products?$', _sec_name, re.I):
                        _related_products = [
                            m.group(1).strip()
                            for m in _OA_LI_RE.finditer(_sec_body)
                            if m.group(1).strip()
                               and not _OA_JUNK_RE.match(m.group(1).strip())
                        ]

                # Write options → ecommerce.product / ecommerce / products list
                if _parsed_options:
                    _ec = result.setdefault("ecommerce", {})
                    _ec["options"] = _parsed_options
                    _ec_prod = _ec.get("product")
                    if isinstance(_ec_prod, dict):
                        _ec_prod["options"] = _parsed_options
                        _ec_prod["metrics"] = {
                            **(_ec_prod.get("metrics") or {}),
                            "hasOptions": True,
                        }
                    for _rp in (result.get("products") or []):
                        if isinstance(_rp, dict):
                            _rp["options"] = _parsed_options
                            (_rp.get("metrics") or {})["hasOptions"] = True

                # Write materials + care instructions into each product object
                for _pobj in [
                    (result.get("ecommerce") or {}).get("product"),
                    *(result.get("products") or []),
                ]:
                    if not isinstance(_pobj, dict):
                        continue
                    if _materials_text:
                        _pobj["materials"] = _materials_text
                    if _care_instructions:
                        _pobj["careInstructions"] = _care_instructions

                # Write related products at top level + into ecommerce
                if _related_products:
                    result["relatedProducts"] = _related_products
                    result.setdefault("ecommerce", {})["relatedProducts"] = _related_products
                # ── end OpenAI section parser ─────────────────────────────────

                # ── Collection page: parse product list from OpenAI markdown ──
                # The collection prompt produces "* **Name** — $price" lines.
                # _jina_markdown_to_html converts "* " → <li> but leaves **
                # as literal markers, so parse from the raw markdown instead.
                if detected_pt == "collection" and not result.get("products"):
                    # Detect currency from markdown (symbols/codes) then TLD fallback.
                    _oa_col_currency = _currency_from_text(oa_markdown, oa_url) or "USD"

                    # Matches: * **Name** — $price (was $X) | Colors: c1, c2 | Sizes: s1, s2
                    _COL_PROD_RE = re.compile(
                        r'^[-*]\s*(?:\*\*)?(.+?)(?:\*\*)?\s*[—–-]+\s*\$?([\d,]+(?:\.\d+)?)'
                        r'(?:\s*\(was\s*\$[\d,]+(?:\.\d+)?\))?'   # optional "(was $X)"
                        r'((?:\s*\|\s*\w[\w ]{0,15}:\s*[^\|\n<]+)*)',  # optional | Key: vals
                        re.MULTILINE,
                    )
                    _COL_VARIANT_RE = re.compile(
                        r'\|\s*(\w[\w ]{0,15}):\s*([^\|\n<]+)',
                        re.I,
                    )
                    _oa_col_products = []
                    _seen_col_names  = set()
                    for _cm in _COL_PROD_RE.finditer(oa_markdown):
                        _pname      = _cm.group(1).strip().strip('*').strip()
                        _pprice_raw = _cm.group(2).replace(',', '')
                        if not _pname or _pname.lower() in _seen_col_names:
                            continue
                        # Skip section headings or instruction lines
                        if re.match(
                            r'^(products?|category|subcategor|filter|nav|description)',
                            _pname, re.I,
                        ):
                            continue
                        _seen_col_names.add(_pname.lower())
                        try:
                            _pprice = float(_pprice_raw)
                        except (ValueError, AttributeError):
                            _pprice = None

                        # Parse | Colors: ... | Sizes: ... segments
                        _variants_text = _cm.group(3) or ""
                        _prod_options  = []
                        for _vp in _COL_VARIANT_RE.finditer(_variants_text):
                            _vkey_raw = _vp.group(1).strip()
                            if re.match(r'colou?rs?', _vkey_raw, re.I):
                                _vkey = "Color"
                            elif re.match(r'sizes?', _vkey_raw, re.I):
                                _vkey = "Size"
                            else:
                                _vkey = _vkey_raw.title()
                            _vvals = [
                                v.strip() for v in _vp.group(2).split(',')
                                if v.strip() and len(v.strip()) <= 30
                            ]
                            if _vvals:
                                _prod_options.append({"name": _vkey, "values": _vvals})

                        _prod_entry = {
                            "rank":  len(_oa_col_products) + 1,
                            "name":  _pname,
                            "price": {
                                "currency":    _oa_col_currency,
                                "current":     _pprice,
                                "compareAt":   None,
                                "isOnSale":    False,
                                "priceTextRaw": f"{_oa_col_currency} {_pprice_raw}",
                            },
                            "availability": {"status": "unknown", "inStock": None},
                            "source":       {"extractor": "openai_browse_collection"},
                        }
                        if _prod_options:
                            _prod_entry["options"] = _prod_options
                        _oa_col_products.append(_prod_entry)
                    if _oa_col_products:
                        result["products"] = _oa_col_products
                        _ec = result.setdefault("ecommerce", {})
                        _ec["products"]     = _oa_col_products
                        _ec["productCount"] = len(_oa_col_products)

                        # priceRange from extracted product prices
                        _valid_prices = [
                            p["price"]["current"]
                            for p in _oa_col_products
                            if isinstance((p.get("price") or {}).get("current"), (int, float))
                        ]
                        _price_range = (
                            {"min": min(_valid_prices), "max": max(_valid_prices), "currency": _oa_col_currency}
                            if _valid_prices else {}
                        )

                        # ecommerce.productStats — quality scorer reads this path
                        # for collection.productStats and collection.priceRange checks
                        _ec["productStats"] = {
                            "productCount": len(_oa_col_products),
                            "priceRange":   _price_range,
                        }

                        # result["collection"] sub-object — consistency
                        _col = result.setdefault("collection", {})
                        _col["products"]         = _oa_col_products
                        _col["productsDetected"] = len(_oa_col_products)
                        if _price_range:
                            _col["priceRange"] = _price_range

                        # content.collectionName — quality scorer reads
                        # result["content"]["collectionName"] (not result["collection"])
                        # Reject seo.h1 if it looks like a product SKU (e.g. "HN -18")
                        # so the OA-browse path does not overwrite a good collectionName
                        # with a product code from the page H1.
                        _SKU_RE = re.compile(r'^[A-Z0-9]{1,6}\s*[-–]\s*[A-Z0-9]+\s*$', re.I)
                        _raw_h1 = (result.get("seo") or {}).get("h1") or ""
                        _safe_h1 = _raw_h1 if not _SKU_RE.match(_raw_h1.strip()) else ""
                        _col_name = (
                            _col.get("title")
                            or (result.get("content") or {}).get("heading")
                            or _safe_h1
                            or ""
                        )
                        if _col_name:
                            result.setdefault("content", {})["collectionName"] = _col_name
                            _col["collectionName"] = _col_name

                        # collectionSummary — quality scorer reads result["collectionSummary"]
                        result["collectionSummary"] = {
                            "name":         _col_name,
                            "productCount": len(_oa_col_products),
                            "priceRange":   _price_range or None,
                            "source":       "openai_browse",
                        }

                        print(f"[OPENAI] Parsed {len(_oa_col_products)} collection products from markdown")

                # Clean up OpenAI browse artifacts:
                # 1. Citation references like "( shop.lululemon.com )" that OpenAI
                #    appends inline to description text as source attributions.
                # 2. Markdown bold/heading markers that slipped through conversion.
                _CITATION_RE = re.compile(r'\s*\(\s*[\w.-]+\.\w{2,}\s*\)', re.I)
                def _strip_citations(obj):
                    """Recursively strip OpenAI inline citations from string fields.
                    Filters empty strings from lists after stripping."""
                    if isinstance(obj, str):
                        return _CITATION_RE.sub('', obj).strip()
                    if isinstance(obj, list):
                        cleaned = [_strip_citations(i) for i in obj]
                        # Drop entries that became empty after citation removal
                        return [i for i in cleaned if i != ""]
                    if isinstance(obj, dict):
                        return {k: _strip_citations(v) for k, v in obj.items()}
                    return obj

                for _top_key in ("products", "ecommerce", "content", "seo", "relatedProducts"):
                    if _top_key in result:
                        result[_top_key] = _strip_citations(result[_top_key])

                _MD_JUNK = re.compile(r'^[*#_\s]+$')
                for _obj in (result.get("ecommerce") or {}, result):
                    _opts = _obj.get("options") if isinstance(_obj, dict) else None
                    if isinstance(_opts, list):
                        _obj["options"] = [
                            {**_o, "values": [v for v in (_o.get("values") or []) if not _MD_JUNK.match(v)]}
                            for _o in _opts
                            if any(v and not _MD_JUNK.match(v) for v in (_o.get("values") or []))
                        ]
                    _prod = _obj.get("product") if isinstance(_obj, dict) else None
                    if isinstance(_prod, dict):
                        _popts = _prod.get("options") or []
                        _prod["options"] = [
                            {**_o, "values": [v for v in (_o.get("values") or []) if not _MD_JUNK.match(v)]}
                            for _o in _popts
                            if any(v and not _MD_JUNK.match(v) for v in (_o.get("values") or []))
                        ]

                result["success"]          = True
                result["extractionMethod"] = "openai_browse_fallback"
                result["crawl"] = {
                    "success": True, "blocked": True, "crawlBlocked": True,
                    "statusCode": 200,
                    "reason": (
                        "Normal crawler, Jina, and Firecrawl all blocked; "
                        "content extracted via OpenAI web browse."
                    ),
                    "retryable": False, "openaiBrowseAnalyzed": True,
                }
                result["inputUrl"] = input_url
                result.setdefault("technical", {})["responseHeaders"] = {
                    "blocked": True, "fetch_method": "openai_browse",
                    "original_fetch_headers": original_headers or {},
                }
                print(f"[OPENAI] Success — platform={platform} pageType={detected_pt}")
                _oa_norm  = normalize_for_competitive_analysis(result)
                _oa_score = _get_result_quality(_oa_norm)
                print(f"[OPENAI] Quality score={_oa_score:.2f}")
                if _oa_score > _fallback_best_score:
                    _fallback_best, _fallback_best_score = _oa_norm, _oa_score
                # OpenAI is last resort — return best regardless of score
                return _fallback_best
            except Exception as _oa_err:
                print(f"[OPENAI] Analysis error after browse: {_oa_err}")
        # ── end OpenAI browse ──────────────────────────────────────────────────

        print(f"[OPENAI] Also failed: {oa.get('reason') if not oa.get('success') else 'analysis error'}")
        if _fallback_best:
            print(f"[QUALITY] All new fetchers tried — returning best partial result (score={_fallback_best_score:.2f})")
            return _fallback_best
        return mark_website_blocked(
            normalize_for_competitive_analysis(
                blocked_result(
                    input_url=input_url, final_url=input_url,
                    headers={
                        "blocked": True, "fetch_method": "all_failed",
                        "jina_error": _jina_fail_reason,
                        "original_fetch_headers": original_headers or {}
                    },
                    status_code=jina_result.get("statusCode"),
                    reason="Normal crawler, Jina, Firecrawl, and OpenAI browse all failed.",
                    blocked_reason="all_fetchers_failed",
                )
            ),
            reason="all_fetchers_failed",
        )

    final_url   = jina_result.get("finalUrl") or input_url
    markdown    = jina_result.get("markdown") or ""
    title       = jina_result.get("title") or ""
    description = jina_result.get("description") or ""
    status_code = jina_result.get("statusCode")

    fallback_content = {
        "source": "jina_reader", "url": final_url,
        "title": title, "description": description,
        "markdown": markdown, "text": markdown,
        "usable": jina_result.get("usable"),
        "reason": jina_result.get("reason"),
        "recommendedUse": (
            "Send this fallbackContent to OpenAI only if normal structured "
            "extraction is missing or low quality."
        )
    }

    # Guard: catch CAPTCHA / login wall / error pages before spending analysis time
    _jina_guard = detect_page_block(markdown, final_url)
    if _jina_guard["blocked"]:
        print(f"[JINA] Page guard blocked ({_jina_guard['blockType']}): {_jina_guard['reason']}")
        return normalize_for_competitive_analysis(
            blocked_result(
                input_url=input_url, final_url=final_url,
                headers={
                    "blocked": True, "fetch_method": "jina",
                    "blockType": _jina_guard["blockType"],
                    "original_fetch_headers": original_headers or {},
                },
                status_code=status_code,
                reason=_jina_guard["reason"],
            )
        )

    # Detect platform from Jina markdown -- CDN URLs are strong signals
    platform_result = detect_platform(html=markdown, url=final_url, headers={})
    platform = platform_result.get("platform", "Unknown")

    # Force Wix when platform is Unknown but markdown has clear Wix collection signals
    # (wixstatic.com CDN + quick view / filter-sort / prices / product links)
    if platform == "Unknown" and _is_wix_collection_markdown(markdown):
        platform = "Wix"
        platform_result = {**platform_result, "platform": "Wix", "confidence": 0.80}

    # Run analysis when:
    #  - platform is known (Wix/Shopify/etc.), OR
    #  - platform is Unknown but Jina returned usable content (general page fallback)
    if (platform != "Unknown" or jina_result.get("usable")) and markdown:
        try:
            jina_html = _jina_markdown_to_html(markdown, title=title, description=description)
            page_type_result = detect_page_type(html=jina_html, url=final_url, platform=platform)
            detected_pt = page_type_result.get("pageType", "homepage")

            # Override to "collection" for Wix when markdown clearly is a collection page.
            # Covers "general"/"unknown" (low-signal pages) and "product" (Wix attribute
            # selectors like Color*/Size* can score product > collection even on catalog pages).
            if (
                platform == "Wix"
                and detected_pt in ("general", "unknown", "product")
                and _is_wix_collection_markdown(markdown)
            ):
                detected_pt = "collection"
                page_type_result = {
                    **page_type_result,
                    "pageType": "collection",
                    "pageTypeConfidence": 0.80,
                    "pageTypeSignals": {
                        **page_type_result.get("pageTypeSignals", {}),
                        "collection": 80
                    }
                }

            analyzer = choose_analyzer(platform, platform_result.get("platformConfidence", 1.0))
            result = analyzer.analyze(
                url=final_url,
                html=jina_html,
                headers={},
                page_type=detected_pt,
                level1={**platform_result, **page_type_result}
            )

            # Tier-2 LLM fallback — also applies to Jina path.
            # Covers pricing pages blocked by Playwright (e.g. Vercel, Retool).
            try:
                from level1_detector.llm_extractor import run_llm_fallback_if_needed
                result = run_llm_fallback_if_needed(result, jina_html, final_url, detected_pt)
            except Exception as _llm_err:
                print(f"LLM FALLBACK (jina): error — {_llm_err}")

            # Enrich homepage result with categories/products parsed from
            # Jina markdown sections (## Product Categories / ## Featured Items).
            # These sections are not recoverable from the minimal converted HTML
            # so we parse them directly from the raw markdown.
            if detected_pt == "homepage" and platform in ("WordPress", "WooCommerce", "WordPress / WooCommerce"):
                ec = result.setdefault("ecommerce", {})
                if not ec.get("categoryLinks"):
                    md_cats = _parse_jina_markdown_categories(markdown)
                    if md_cats:
                        ec["categoryLinks"] = md_cats
                        ec["hasEcommerceSignals"] = True
                if not ec.get("featuredProducts"):
                    md_prods = _parse_jina_markdown_products(markdown)
                    if md_prods:
                        ec["featuredProducts"] = md_prods
                        ec["featuredProductsCount"] = len(md_prods)
                        ec["hasEcommerceSignals"] = True
                        # Sync Jina-discovered products into homepageStrategy
                        # (build_homepage_strategy() ran before Jina enrichment
                        # so homepageStrategy.featuredProducts is still empty).
                        _hs = result.get("homepageStrategy") or {}
                        if _hs and not _hs.get("featuredProducts"):
                            _hs["featuredProducts"] = [
                                {
                                    "name": p.get("name"),
                                    "price": p.get("price"),
                                    "section": p.get("sectionName"),
                                }
                                for p in md_prods[:10]
                            ]

            # Success if we extracted meaningful content from any field set
            has_products   = bool(result.get("ecommerce", {}).get("featuredProducts"))
            has_categories = bool(result.get("ecommerce", {}).get("categoryLinks"))
            has_content    = bool((result.get("content") or {}).get("mainText", ""))
            # result["products"] is populated by collection/product analyzers —
            # check it directly so collection pages aren't marked success=False
            has_raw_products = bool(result.get("products"))
            # Also check unknown-homepage-analyzer fields (Nike, ARFM, etc.)
            _hp = result.get("homepage") or {}
            _hp_hero = _hp.get("hero") or {}
            has_hero    = bool(
                _hp_hero.get("headline") or _hp_hero.get("campaignHero")
                or _hp_hero.get("supportingText")
            )
            has_sections  = bool(_hp.get("sections") or [])
            has_services  = bool(_hp.get("services") or [])
            has_menu_items = bool(_hp.get("menuItems") or [])
            is_usable = (
                has_products or has_categories or has_content
                or has_raw_products
                or has_hero or has_sections or has_services or has_menu_items
            )

            result["success"] = is_usable
            result["extractionMethod"] = "jina_fallback"
            result["crawl"] = {
                "success": is_usable, "blocked": True, "crawlBlocked": True,
                "statusCode": status_code,
                "reason": (
                    "Normal crawler blocked; platform detected and extracted "
                    "from Jina Reader fallback."
                ),
                "retryable": True, "jinaAnalyzed": True
            }
            result["inputUrl"] = input_url
            result.setdefault("technical", {})["responseHeaders"] = {
                "blocked": True, "fetch_method": "jina_reader",
                "jina_usable": jina_result.get("usable"),
                "original_fetch_headers": original_headers or {}
            }
            result["fallbackContent"] = fallback_content

            normalized = normalize_for_competitive_analysis(result)
            aq = normalized["analysisReady"]["extractionQuality"]

            # Better quality score for Wix collection Jina fallback with real products
            extracted_products = result.get("products") or []
            n_products = len(extracted_products)
            if is_usable and detected_pt == "collection" and platform == "Wix" and n_products > 0:
                if n_products >= 6:
                    aq["score"] = 0.90
                elif n_products >= 3:
                    aq["score"] = 0.82
                else:
                    aq["score"] = 0.75
            else:
                # Smarter Jina quality adjustment: apply a smaller penalty
                # when meaningful data was actually extracted.  Each signal
                # that proves the extraction worked reduces the penalty.
                #
                # Check BOTH WordPress-style keys (homepageStrategy, business,
                # competitiveSignals) AND unknown-analyzer-style keys (homepage.*)
                # so that ARFM, Websouls, Nike etc. get correct signal counts.
                _hp_raw = result.get("homepage") or {}
                _hp_hero_raw = _hp_raw.get("hero") or {}
                _has_hero = bool(
                    (result.get("homepageStrategy") or {})
                    .get("hero", {})
                    .get("headline")
                    or _hp_hero_raw.get("headline")
                    or _hp_hero_raw.get("campaignHero")
                    or _hp_hero_raw.get("supportingText")
                )
                _has_products = bool(
                    (result.get("ecommerce") or {}).get("featuredProducts")
                )
                # Business model: check WordPress-style first, then unknown-analyzer style
                _hp_biz_raw = (_hp_raw.get("businessModel") or {}).get("primaryModel", "")
                _biz_primary = (
                    (result.get("business") or {})
                    .get("businessModel", {})
                    .get("primary", "")
                    or _hp_biz_raw
                    or "general"
                )
                _has_biz_model = _biz_primary not in ("general", "unknown", None, "")
                # CTAs: check both competitiveSignals and unknown-analyzer homepage.ctas
                _has_ctas = bool(
                    (result.get("competitiveSignals") or {})
                    .get("ctaStrategy", {})
                    .get("ctaCount", 0)
                    or (_hp_raw.get("ctas") or [])
                    or (_hp_hero_raw.get("primaryCtas") or [])
                )
                _jina_quality_signals = sum([
                    _has_hero, _has_products, _has_biz_model, _has_ctas
                ])
                if _jina_quality_signals >= 3:
                    _jina_multiplier = 0.95   # very good extraction
                elif _jina_quality_signals >= 2:
                    _jina_multiplier = 0.88   # good extraction
                elif _jina_quality_signals >= 1:
                    _jina_multiplier = 0.80   # partial extraction
                else:
                    _jina_multiplier = 0.72   # poor extraction
                # Issues 11+16: When the extractor (general.py) has set source.qualityScore
                # as the authoritative quality, use it instead of the signal-based multiplier.
                # This prevents the Jina penalty from overriding an already-calibrated score.
                _extractor_src_quality = (
                    (result.get("source") or {}).get("qualityScore") or 0
                )
                if _extractor_src_quality > 0:
                    aq["score"] = round(_extractor_src_quality, 2)
                else:
                    aq["score"] = max(0.35, round(
                        (aq.get("score") or 0) * _jina_multiplier, 2
                    ))

            # General escalation trigger: collection/product pages with no extracted
            # data should always score below the escalation threshold so the system
            # automatically retries with Microlink → Firecrawl → OpenAI browse.
            # This fires for ANY platform (Samsung, Zara, etc.) — not site-specific.
            if detected_pt == "collection" and not extracted_products:
                _pre_cap = aq.get("score") or 0
                aq["score"] = min(_pre_cap, 0.40)
                print(
                    f"[QUALITY] Collection page with 0 products — "
                    f"capping score {_pre_cap:.2f}→0.40 to trigger escalation"
                )
            elif detected_pt == "product":
                _product_ec = (result.get("ecommerce") or {}).get("product") or {}
                if not _product_ec.get("name") and not _product_ec.get("price"):
                    _pre_cap = aq.get("score") or 0
                    aq["score"] = min(_pre_cap, 0.40)
                    print(
                        f"[QUALITY] Product page with no name/price — "
                        f"capping score {_pre_cap:.2f}→0.40 to trigger escalation"
                    )

            # Issues 11+16: Sync source.qualityScore to the final extractionQuality.score
            # so source, extractionQuality, and merger are all consistent.
            if "source" in normalized and aq.get("score"):
                normalized["source"]["qualityScore"] = aq["score"]
                _sq = aq["score"]
                normalized["source"]["qualityBucket"] = (
                    "excellent" if _sq >= 0.90 else
                    "good" if _sq >= 0.80 else
                    "partial" if _sq >= 0.65 else
                    "low"
                )

            warnings = aq.get("warnings") or []
            warnings.append(
                "Extracted from Jina Reader fallback (markdown converted to HTML). "
                "Some fields may be incomplete."
            )
            aq["warnings"] = warnings

            # Cap pageTypeConfidence -- blocked crawl means uncertain page structure

            page_info = normalized.get("page") or {}
            if page_info.get("pageTypeConfidence"):
                page_info["pageTypeConfidence"] = min(page_info["pageTypeConfidence"], 0.75)

            # Issue S6-5 (Jina path): filter generic keyword-derived trust terms for
            # service pages that have specific serviceIntelligence.trustSignals.
            _jina_page_subtype = (result.get("page") or {}).get("generalSubtype") or ""
            if _jina_page_subtype == "service_page":
                _jina_svc_trust = (result.get("serviceIntelligence") or {}).get("trustSignals") or []
                if _jina_svc_trust:
                    _JINA_GENERIC_TRUST = {
                        "secure", "trusted", "trust", "security", "compliance",
                        "certified", "verified", "privacy",
                    }
                    _j_ar = normalized.get("analysisReady") or {}
                    _j_cs = _j_ar.get("competitiveSignals") or {}
                    _j_at = _j_cs.get("trustSignals")
                    if isinstance(_j_at, list):
                        _j_filtered = [t for t in _j_at if (t or "").lower() not in _JINA_GENERIC_TRUST]
                        normalized["analysisReady"]["competitiveSignals"]["trustSignals"] = (
                            _j_filtered if _j_filtered else _j_at
                        )

            # Attach merger meta
            normalized["analysisReady"]["merger"] = _build_merger_meta(
                normalized,
                fallbacks_tried=["requests", "jina"],
                extraction_method="jina",
            )

            # ── Quality gate: escalate to better fetchers if score too low ────
            _jina_final_score = _get_result_quality(normalized)
            if _jina_final_score >= QUALITY_ESCALATION_THRESHOLD:
                return normalized  # good enough — done
            # Score below threshold — store as best so far and escalate
            _esc_best       = normalized
            _esc_best_score = _jina_final_score
            print(
                f"[QUALITY ESCALATION] Jina score={_jina_final_score:.2f} "
                f"< {QUALITY_ESCALATION_THRESHOLD} — trying Microlink, Firecrawl, OpenAI"
            )
            # Fall through to the escalation block below the try/except

        except Exception as _jina_exc:
            import traceback as _tb
            print(f"[jina_fallback] analyzer error: {_jina_exc}", file=sys.stderr)
            _tb.print_exc(file=sys.stderr)


    # ── Quality Escalation: Jina succeeded but quality was below threshold ────
    # Try Microlink → Firecrawl → OpenAI in sequence.
    # The best-scoring result across all tiers is returned.
    if _esc_best is not None:
        # ── Escalation Tier 1: Microlink ──────────────────────────────────────
        if _budget_exceeded(_chain_start, "Microlink escalation"):
            return _esc_best
        print(f"[MICROLINK-ESC] Trying Microlink for {input_url}")
        _esc_ml = fetch_with_microlink(input_url)
        if _esc_ml.get("success"):
            try:
                _esc_ml_md   = _esc_ml["markdown"]
                _esc_ml_url  = _esc_ml.get("finalUrl") or input_url
                _esc_ml_html = _jina_markdown_to_html(
                    _esc_ml_md, title=_esc_ml.get("title", ""),
                    description=_esc_ml.get("description", ""),
                )
                _esc_ml_pr   = detect_platform(html=_esc_ml_md, url=_esc_ml_url, headers={})
                _esc_ml_plat = _esc_ml_pr.get("platform", "Unknown")
                _esc_ml_ptr  = detect_page_type(html=_esc_ml_html, url=_esc_ml_url, platform=_esc_ml_plat)
                _esc_ml_pt   = _esc_ml_ptr.get("pageType", "general")
                _esc_ml_res  = choose_analyzer(_esc_ml_plat, _esc_ml_pr.get("platformConfidence", 1.0)).analyze(
                    url=_esc_ml_url, html=_esc_ml_html, headers={},
                    page_type=_esc_ml_pt,
                    level1={**_esc_ml_pr, **_esc_ml_ptr},
                )
                try:
                    from level1_detector.llm_extractor import run_llm_fallback_if_needed
                    _esc_ml_res = run_llm_fallback_if_needed(_esc_ml_res, _esc_ml_html, _esc_ml_url, _esc_ml_pt)
                except Exception:
                    pass
                _esc_ml_res.update({
                    "success": True, "extractionMethod": "microlink_fallback",
                    "inputUrl": input_url,
                    "crawl": {
                        "success": True, "blocked": True, "crawlBlocked": True,
                        "statusCode": 200,
                        "reason": "Quality escalation: Jina quality low; re-extracted via Microlink.",
                        "retryable": False, "microlinkAnalyzed": True,
                    },
                })
                _esc_ml_res.setdefault("technical", {})["responseHeaders"] = {
                    "blocked": True, "fetch_method": "microlink",
                    "original_fetch_headers": original_headers or {},
                }
                _esc_ml_norm  = normalize_for_competitive_analysis(_esc_ml_res)
                _esc_ml_score = _get_result_quality(_esc_ml_norm)
                print(f"[MICROLINK-ESC] score={_esc_ml_score:.2f} vs Jina={_esc_best_score:.2f}")
                if _esc_ml_score > _esc_best_score:
                    _esc_best, _esc_best_score = _esc_ml_norm, _esc_ml_score
                if _esc_ml_score >= QUALITY_ESCALATION_THRESHOLD:
                    print(f"[QUALITY ESCALATION] Microlink exceeded threshold — using result")
                    return _esc_best
                print(f"[MICROLINK-ESC] Still below threshold — continuing to Firecrawl")
            except Exception as _esc_ml_err:
                print(f"[MICROLINK-ESC] Error: {_esc_ml_err}")
        else:
            print(f"[MICROLINK-ESC] Failed: {_esc_ml.get('reason')}")

        # ── Escalation Tier 2: Firecrawl ──────────────────────────────────────
        if _budget_exceeded(_chain_start, "Firecrawl escalation"):
            return _esc_best
        print(f"[FIRECRAWL-ESC] Trying Firecrawl for {input_url}")
        _esc_fc = fetch_with_firecrawl(input_url)
        if _esc_fc.get("success"):
            try:
                _esc_fc_html = _esc_fc["html"]
                _esc_fc_url  = _esc_fc.get("finalUrl") or input_url
                _esc_fc_pr   = detect_platform(html=_esc_fc_html, url=_esc_fc_url, headers={})
                _esc_fc_plat = _esc_fc_pr.get("platform", "Unknown")
                _esc_fc_ptr  = detect_page_type(html=_esc_fc_html, url=_esc_fc_url, platform=_esc_fc_plat)
                _esc_fc_pt   = _esc_fc_ptr.get("pageType", "general")
                _esc_fc_res  = choose_analyzer(_esc_fc_plat, _esc_fc_pr.get("platformConfidence", 1.0)).analyze(
                    url=_esc_fc_url, html=_esc_fc_html, headers={},
                    page_type=_esc_fc_pt,
                    level1={**_esc_fc_pr, **_esc_fc_ptr},
                )
                try:
                    from level1_detector.llm_extractor import run_llm_fallback_if_needed
                    _esc_fc_res = run_llm_fallback_if_needed(_esc_fc_res, _esc_fc_html, _esc_fc_url, _esc_fc_pt)
                except Exception:
                    pass
                _esc_fc_res.update({
                    "success": True, "extractionMethod": "firecrawl_fallback",
                    "inputUrl": input_url,
                    "crawl": {
                        "success": True, "blocked": True, "crawlBlocked": True,
                        "statusCode": _esc_fc.get("statusCode"),
                        "reason": "Quality escalation: Jina quality low; re-extracted via Firecrawl.",
                        "retryable": False, "firecrawlAnalyzed": True,
                    },
                })
                _esc_fc_res.setdefault("technical", {})["responseHeaders"] = {
                    "blocked": True, "fetch_method": "firecrawl",
                    "original_fetch_headers": original_headers or {},
                }
                _esc_fc_norm  = normalize_for_competitive_analysis(_esc_fc_res)
                _esc_fc_score = _get_result_quality(_esc_fc_norm)
                print(f"[FIRECRAWL-ESC] score={_esc_fc_score:.2f} vs best so far={_esc_best_score:.2f}")
                if _esc_fc_score > _esc_best_score:
                    _esc_best, _esc_best_score = _esc_fc_norm, _esc_fc_score
                if _esc_fc_score >= QUALITY_ESCALATION_THRESHOLD:
                    print(f"[QUALITY ESCALATION] Firecrawl exceeded threshold — using result")
                    return _esc_best
                print(f"[FIRECRAWL-ESC] Still below threshold — continuing to OpenAI")
            except Exception as _esc_fc_err:
                print(f"[FIRECRAWL-ESC] Error: {_esc_fc_err}")
        else:
            print(f"[FIRECRAWL-ESC] Failed: {_esc_fc.get('reason')}")

        # ── Escalation Tier 3: OpenAI browse (last resort) ────────────────────
        if _budget_exceeded(_chain_start, "OpenAI escalation"):
            return _esc_best
        _esc_oa_pt = guess_page_type_from_url(input_url)
        print(f"[OPENAI-ESC] Trying OpenAI browse for {input_url} (pageType={_esc_oa_pt})")
        _esc_oa = fetch_with_openai_browse(input_url, page_type=_esc_oa_pt)
        if _esc_oa.get("success"):
            try:
                _esc_oa_md   = _esc_oa["markdown"]
                _esc_oa_url  = _esc_oa.get("finalUrl") or input_url
                _esc_oa_html = _jina_markdown_to_html(
                    _esc_oa_md, title=_esc_oa.get("title", ""),
                    description=_esc_oa.get("description", ""),
                )
                _esc_oa_pr   = detect_platform(html=_esc_oa_md, url=_esc_oa_url, headers={})
                _esc_oa_plat = _esc_oa_pr.get("platform", "Unknown")
                # Trust URL-based page type for OpenAI (same logic as main OA path)
                if _esc_oa_pt and _esc_oa_pt != "general":
                    _esc_oa_ptr    = {"pageType": _esc_oa_pt, "pageTypeConfidence": 0.9}
                    _esc_oa_det_pt = _esc_oa_pt
                else:
                    _esc_oa_ptr    = detect_page_type(html=_esc_oa_html, url=_esc_oa_url, platform=_esc_oa_plat)
                    _esc_oa_det_pt = _esc_oa_ptr.get("pageType", "general")
                _esc_oa_res = choose_analyzer(_esc_oa_plat, _esc_oa_pr.get("platformConfidence", 1.0)).analyze(
                    url=_esc_oa_url, html=_esc_oa_html, headers={},
                    page_type=_esc_oa_det_pt,
                    level1={**_esc_oa_pr, **_esc_oa_ptr},
                )
                if _esc_oa_det_pt not in ("collection", "homepage"):
                    try:
                        from level1_detector.llm_extractor import run_llm_fallback_if_needed
                        _esc_oa_res = run_llm_fallback_if_needed(_esc_oa_res, _esc_oa_html, _esc_oa_url, _esc_oa_det_pt)
                    except Exception:
                        pass
                _esc_oa_res.update({
                    "success": True, "extractionMethod": "openai_browse_fallback",
                    "inputUrl": input_url,
                    "crawl": {
                        "success": True, "blocked": True, "crawlBlocked": True,
                        "statusCode": 200,
                        "reason": "Quality escalation: Jina quality low; re-extracted via OpenAI browse.",
                        "retryable": False, "openaiBrowseAnalyzed": True,
                    },
                })
                _esc_oa_res.setdefault("technical", {})["responseHeaders"] = {
                    "blocked": True, "fetch_method": "openai_browse",
                    "original_fetch_headers": original_headers or {},
                }
                _esc_oa_norm  = normalize_for_competitive_analysis(_esc_oa_res)
                _esc_oa_score = _get_result_quality(_esc_oa_norm)
                print(f"[OPENAI-ESC] score={_esc_oa_score:.2f} vs best so far={_esc_best_score:.2f}")
                if _esc_oa_score > _esc_best_score:
                    _esc_best, _esc_best_score = _esc_oa_norm, _esc_oa_score
            except Exception as _esc_oa_err:
                print(f"[OPENAI-ESC] Error: {_esc_oa_err}")
        else:
            print(f"[OPENAI-ESC] Failed: {_esc_oa.get('reason')}")

        # Return the best result found across all tiers
        _esc_method = (_esc_best.get("extractionMethod") if _esc_best else "none")
        print(f"[QUALITY ESCALATION] Done — best score={_esc_best_score:.2f} method={_esc_method}")
        return _esc_best

    # Step 5: Sitemap / robots / RSS fallback
    # Step 5: Sitemap / robots / RSS fallback
    try:
        sitemap_data = _fetch_sitemap_fallback(input_url)
        if sitemap_data:
            bare = jina_fallback_content_result(
                input_url=input_url,
                jina_result=jina_result,
                original_headers=original_headers
            )
            bare.setdefault("sitemap", {}).update(sitemap_data)
            bare["analysisReady"]["extractionQuality"]["score"] = max(
                bare["analysisReady"]["extractionQuality"].get("score", 0), 0.20
            )
            bare["analysisReady"]["extractionQuality"]["qualityBucket"] = "partial"
            bare["analysisReady"]["merger"] = _build_merger_meta(
                bare,
                fallbacks_tried=["requests", "jina", "sitemap"],
                extraction_method="sitemap",
            )
            return bare
    except Exception as _se:
        print(f"[sitemap_fallback] error: {_se}", file=sys.stderr)

    # Bare fallback — mark for AI insights
    bare = jina_fallback_content_result(
        input_url=input_url,
        jina_result=jina_result,
        original_headers=original_headers
    )
    bare["analysisReady"]["extractionQuality"]["qualityBucket"] = "failed"
    bare["analysisReady"]["merger"] = _build_merger_meta(
        bare,
        fallbacks_tried=["requests", "jina"],
        extraction_method="jina",
    )
    return bare


# ---------------------------------------------------------------------------
# Merger meta builder
# ---------------------------------------------------------------------------

def _build_merger_meta(normalized_result, fallbacks_tried, extraction_method):
    """Build the merger metadata block for analysisReady.merger.

    qualityBucket mapping:
      good    — score >= 0.75
      partial — score >= 0.35
      blocked — page is blocked/empty-shell
      failed  — score < 0.35 and not blocked
    """
    aq = (normalized_result.get("analysisReady") or {}).get("extractionQuality") or {}
    score = aq.get("score") or 0.0
    is_blocked = (
        normalized_result.get("success") is False
        and (normalized_result.get("crawl") or {}).get("blocked") is True
    )

    if is_blocked:
        bucket = "blocked"
    elif score >= 0.75:
        bucket = "good"
    elif score >= 0.35:
        bucket = "partial"
    else:
        bucket = "failed"

    # needs AI review: true when blocked, failed, or quality < 0.75 (partial).
    # At >= 0.75 with a clean extraction, downstream can merge without AI.
    if is_blocked:
        needs_ai = True
    elif score >= 0.75:
        needs_ai = False
    else:
        needs_ai = True  # partial (< 0.75) or failed (< 0.35)
    usable_for_merge = bucket in ("good", "partial")
    usable_for_insights = bucket != "blocked"

    return {
        "extractionMethod": extraction_method,
        "qualityScore": round(score, 2),
        "qualityBucket": bucket,
        "needsAIInsightReview": needs_ai,
        "fallbacksTried": fallbacks_tried,
        "usableForMerge": usable_for_merge,
        "usableForInsights": usable_for_insights,
    }


# ---------------------------------------------------------------------------
# Sitemap / robots / feed fallback
# ---------------------------------------------------------------------------

def _fetch_sitemap_fallback(url):
    """Attempt to retrieve deterministic signals from sitemap.xml, robots.txt,
    and RSS/Atom feeds.  Only pure network I/O — no AI.

    Returns a dict with any of: sitemapUrls, feedItems, robotsSitemapHints
    or None if nothing usable was found.
    """
    import urllib.request
    from urllib.parse import urljoin, urlparse

    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    result = {}

    # 1. sitemap.xml
    for path in ["/sitemap.xml", "/sitemap_index.xml", "/sitemap.php", "/sitemap"]:
        try:
            req = urllib.request.Request(
                urljoin(base, path),
                headers={"User-Agent": "Mozilla/5.0 (compatible; SiteAnalyzer/1.0)"},
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    raw = resp.read(80000).decode("utf-8", errors="ignore")
                    locs = re.findall(r'<loc>\s*([^<\s]+)\s*</loc>', raw)
                    if locs:
                        result["sitemapUrls"] = locs[:60]
                        result["sitemapPath"] = path
                        break
        except Exception:
            pass

    # 2. robots.txt — extract Sitemap: directives
    if not result.get("sitemapUrls"):
        try:
            req = urllib.request.Request(
                urljoin(base, "/robots.txt"),
                headers={"User-Agent": "Mozilla/5.0 (compatible; SiteAnalyzer/1.0)"},
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    robots_text = resp.read(5000).decode("utf-8", errors="ignore")
                    sitemap_hints = re.findall(
                        r'(?i)^Sitemap:\s*(.+)$', robots_text, re.MULTILINE
                    )
                    if sitemap_hints:
                        result["robotsSitemapHints"] = sitemap_hints[:5]
        except Exception:
            pass

    # 3. RSS / Atom feed
    for path in ["/feed", "/feed.xml", "/rss.xml", "/atom.xml", "/rss", "/feed/rss2"]:
        try:
            req = urllib.request.Request(
                urljoin(base, path),
                headers={"User-Agent": "Mozilla/5.0 (compatible; SiteAnalyzer/1.0)"},
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    raw = resp.read(30000).decode("utf-8", errors="ignore")
                    # Extract item/entry titles + links
                    titles = re.findall(
                        r'<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>', raw
                    )
                    links = re.findall(r'<link[^>]*>([^<]+)</link>', raw)
                    if titles and len(titles) > 1:
                        feed_items = []
                        for i, t in enumerate(titles[1:11]):  # skip channel title
                            feed_items.append({
                                "title": t.strip(),
                                "url": links[i + 1].strip() if i + 1 < len(links) else None
                            })
                        result["feedItems"] = feed_items
                        result["feedTitle"] = titles[0].strip() if titles else None
                        break
        except Exception:
            pass

    return result if result else None


def _log_url_history(url: str, result: dict) -> None:
    """Append a one-line record of every analysis to output/url_history.jsonl.

    This builds a real-world corpus of everything the app has analyzed:
    - feed it to the accuracy scorecard:  python tools/accuracy_check.py output/url_history.jsonl
    - see which platforms/page types users actually analyze
    - reproduce any past analysis (url + timestamp + quality at the time)

    Never breaks analysis: failures are swallowed. Disable with URL_HISTORY=off.
    """
    import os
    if os.getenv("URL_HISTORY", "on").lower() in ("off", "0", "false"):
        return
    try:
        from datetime import datetime, timezone
        page = result.get("page") or {}
        eq = ((result.get("analysisReady") or {}).get("extractionQuality") or {})
        products = result.get("products") or []
        priced = sum(
            1 for pr in products
            if isinstance(pr, dict) and isinstance(pr.get("price"), dict)
            and pr["price"].get("current") is not None
        )
        record = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "url": page.get("url") or url,
            "inputUrl": url,
            "pageType": page.get("pageType"),
            "platform": result.get("platform"),
            "success": result.get("success"),
            "blocked": bool((result.get("crawl") or {}).get("crawlBlocked")),
            "extractionMethod": result.get("extractionMethod"),
            "qualityScore": eq.get("score"),
            "qualityBucket": eq.get("qualityBucket"),
            "productCount": len(products),
            "pricedProductCount": priced,
            "flags": ((eq.get("dataConsistency") or {}).get("flags")) or [],
        }
        Path("output").mkdir(exist_ok=True)
        with open(Path("output") / "url_history.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _degraded_result(url: str, exc: Exception):
    """Best-effort, valid-shaped result for a page whose analysis crashed. Keeps the
    URL in the run (so one bad page never empties a whole side) while flagging LOW
    extraction quality + the error, so the merge/compare + UI treat it as unreliable
    rather than presenting hollow data as fact."""
    try:
        base = {
            "success": False,
            "inputUrl": url,
            "page": {"url": url, "pageType": "error"},
            "crawl": {"success": False, "blocked": False, "crawlBlocked": False,
                      "reason": f"analysis_error: {type(exc).__name__}"},
        }
        normalized = normalize_for_competitive_analysis(base)
        _aq = normalized.setdefault("analysisReady", {}).setdefault("extractionQuality", {})
        _aq["score"] = 0.0
        _aq["qualityBucket"] = "error"
        _dq = normalized.setdefault("dataQuality", {})
        _dq["extractionError"] = True
        _dq["reason"] = str(exc)[:300]
        return normalized
    except Exception as _inner:
        # Absolute last resort — a minimal dict the pipeline can skip safely.
        print(f"❌ [analyze_url] degraded-result builder also failed: {_inner}", flush=True)
        return {
            "success": False,
            "inputUrl": url,
            "page": {"url": url, "pageType": "error"},
            "crawl": {"success": False, "reason": "analysis_error"},
            "dataQuality": {"extractionError": True, "reason": str(exc)[:300]},
            "analysisReady": {"extractionQuality": {"score": 0.0, "qualityBucket": "error"}},
        }


def analyze_url(url: str):
    """Analyze one URL and log it to the URL history.

    Never raises: a crash in the per-page pipeline is logged with a full traceback
    and downgraded to a flagged low-quality result, so a single failing page can't
    500 and wipe out an entire competitor/owner side of the comparison.
    """
    try:
        result = _analyze_url_impl(url)
    except Exception as exc:
        tb = traceback.format_exc()
        print(f"❌ [analyze_url] {url} crashed — returning degraded result:\n{tb}", flush=True)
        result = _degraded_result(url, exc)
    try:
        _log_url_history(url, result)
    except Exception:
        pass
    return result


def _analyze_url_impl(url: str):
    input_url = normalize_url(url)
    html, final_url, headers = fetch_html(input_url)
    blocked, status_code = is_blocked_response(html, headers)

    if blocked:
        return analyze_with_jina_fallback(input_url=input_url, original_headers=headers)

    # Detect bot-protection pages that return HTTP 200 (e.g. Walmart /blocked?url=...)
    if is_bot_protection_page(final_url, html):
        return normalize_for_competitive_analysis(
            bot_protection_result(
                input_url=input_url,
                final_url=final_url,
                headers=headers,
                status_code=status_code or 200,
            )
        )

    platform_result = detect_platform(html=html, url=final_url, headers=headers)
    page_type_result = detect_page_type(
        html=html, url=final_url,
        platform=platform_result.get("platform", "")
    )
    analyzer = choose_analyzer(platform_result.get("platform"), platform_result.get("platformConfidence", 1.0))
    detected_page_type = page_type_result.get("pageType", "general")

    result = analyzer.analyze(
        url=final_url, html=html, headers=headers,
        page_type=detected_page_type,
        level1={**platform_result, **page_type_result}
    )

    # ── Playwright retry for JS-heavy platforms ──────────────────────────────
    # If the initial fetch (requests/cloudscraper) didn't run Playwright and
    # the extraction came back with nextDataFound=False or low confidence on a
    # JS platform (Next.js, React, Vue, Webflow), retry with Playwright so we
    # can pull __NEXT_DATA__ and other runtime-injected data.
    _JS_PLATFORMS = {"Next.js / React", "React", "Vue", "Webflow", "Next.js"}
    _already_playwright = headers.get("fetch_method") == "playwright" or headers.get("forced_playwright")
    _platform_name = platform_result.get("platform", "")
    _src = result.get("source") or {}
    _confidence = _src.get("confidence") or _src.get("qualityScore") or 1.0
    _next_data_missing = _src.get("nextDataFound") is False
    _needs_pw_retry = (
        _platform_name in _JS_PLATFORMS
        and not _already_playwright
        and (_next_data_missing or _confidence < 0.75)
    )
    if _needs_pw_retry:
        print(f"PLAYWRIGHT RETRY: platform={_platform_name} nextDataFound={_next_data_missing} confidence={_confidence}")
        pw_html, pw_final_url, pw_headers = fetch_with_playwright(final_url)
        if pw_html:
            pw_result = analyzer.analyze(
                url=pw_final_url, html=pw_html, headers=pw_headers,
                page_type=detected_page_type,
                level1={**platform_result, **page_type_result}
            )
            pw_result["_playwright_retry"] = True
            pw_headers["forced_playwright"] = True
            pw_headers["forced_playwright_reason"] = "js_platform_low_confidence_retry"
            pw_headers["original_fetch_method"] = headers.get("fetch_method", "requests")
            result = pw_result
            headers = pw_headers
            final_url = pw_final_url
            print(f"PLAYWRIGHT RETRY: succeeded, nextDataFound={result.get('source', {}).get('nextDataFound')}")
        else:
            print("PLAYWRIGHT RETRY: failed")
            headers["playwright_retry_attempted"] = True
            headers["playwright_retry_failed"] = True
    # ─────────────────────────────────────────────────────────────────────────

    # ── Playwright retry for missing prices (headless / JS-rendered stores) ──
    # A collection/product page that yields products but ZERO prices almost
    # always renders prices client-side. One local Playwright pass is free and
    # usually recovers them (e.g. Gymshark: 96 products, 0 priced without JS).
    def _price_coverage(res):
        # Some extractions emit non-dict entries in products (a known WP
        # collection-extractor quirk) — guard them or pr.get() crashes.
        prods = [p for p in (res.get("products") or []) if isinstance(p, dict)]
        if not prods:
            return None
        priced = sum(
            1 for pr in prods
            if isinstance(pr.get("price"), dict) and pr["price"].get("current") is not None
        )
        return priced / len(prods)

    # Retry triggers (was: only exact zero coverage, which missed most real
    # cases — Gymshark/Mejuri render the whole grid client-side so products=0
    # and coverage=None; Pela had 2% coverage; none of these ever retried):
    #   1. collection page with NO products at all      → grid is JS-rendered
    #   2. collection/product with coverage below 80%   → prices JS-rendered
    _PRICE_RETRY_COVERAGE_THRESHOLD = 0.8
    _already_pw2 = headers.get("fetch_method") == "playwright" or headers.get("forced_playwright")
    _cov = _price_coverage(result)

    # Invariant guardrail: a collection where EVERY priced product shows the
    # identical price (>=3 priced) or EVERY product is out of stock (>=3 known)
    # is almost always a DOM-misalignment/placeholder glitch, not reality. Treat
    # it like low coverage and force a products.json re-fetch.
    def _collection_broken(res):
        prods = [p for p in (res.get("products") or []) if isinstance(p, dict)]
        if len(prods) < 3:
            return None
        priced = [(p.get("price") or {}).get("current") for p in prods]
        priced = [x for x in priced if x is not None]
        if len(priced) >= 3 and len(set(priced)) == 1:
            return "all_same_price"
        stock = [(p.get("availability") or {}).get("inStock") for p in prods]
        known = [s for s in stock if s is not None]
        if len(known) >= 3 and all(s is False for s in known):
            return "all_out_of_stock"
        return None

    def _distinct_prices(res):
        vals = [(p.get("price") or {}).get("current") for p in (res.get("products") or []) if isinstance(p, dict)]
        return len({v for v in vals if v is not None})

    def _in_stock_count(res):
        return sum(1 for p in (res.get("products") or []) if isinstance(p, dict) and (p.get("availability") or {}).get("inStock") is True)

    # Only treat "broken" as retry-worthy when the data ISN'T already from the
    # authoritative products.json (confidence >= 0.9) — a uniform-price collection
    # straight from products.json is genuinely uniform, not a glitch.
    _src_conf_now = (result.get("source") or {}).get("confidence") or 0
    _broken_reason = (
        _collection_broken(result)
        if (detected_page_type == "collection" and _src_conf_now < 0.9)
        else None
    )

    _needs_price_retry = detected_page_type in ("collection", "product") and (
        (_cov is None and detected_page_type == "collection")
        or (_cov is not None and _cov < _PRICE_RETRY_COVERAGE_THRESHOLD)
        or bool(_broken_reason)
    )
    if _needs_price_retry and _already_pw2:
        headers["price_retry"] = "skipped_already_playwright"
    if _needs_price_retry and not _already_pw2:
        _n_prods = len(result.get("products") or [])
        _n_priced = sum(
            1 for pr in (result.get("products") or [])
            if isinstance(pr, dict)
            and isinstance(pr.get("price"), dict) and pr["price"].get("current") is not None
        )
        print(f"PLAYWRIGHT RETRY (prices): {_n_prods} products, {_n_priced} priced (coverage={_cov if _cov is not None else 'n/a'}, invariant={_broken_reason or 'ok'}) — retrying with JS rendering")
        pw_html2, pw_final_url2, pw_headers2 = fetch_with_playwright(final_url)
        if pw_html2:
            pw_result2 = analyzer.analyze(
                url=pw_final_url2, html=pw_html2, headers=pw_headers2,
                page_type=detected_page_type,
                level1={**platform_result, **page_type_result},
            )
            pw_cov2 = _price_coverage(pw_result2)
            pw_n_prods2 = len(pw_result2.get("products") or [])
            pw_n_priced2 = round((pw_cov2 or 0.0) * pw_n_prods2)
            # Keep the retry only if it's a real improvement: more priced
            # products, products where there were none before, or — for the
            # invariant cases — more distinct prices / some in-stock now.
            _improved = pw_n_priced2 > _n_priced or (pw_n_prods2 > 0 and _n_prods == 0)
            if _broken_reason == "all_same_price":
                _improved = _improved or _distinct_prices(pw_result2) > _distinct_prices(result)
            elif _broken_reason == "all_out_of_stock":
                _improved = _improved or _in_stock_count(pw_result2) > _in_stock_count(result)
            if _improved:
                pw_headers2["forced_playwright"] = True
                pw_headers2["forced_playwright_reason"] = "low_price_coverage_retry"
                pw_headers2["original_fetch_method"] = headers.get("fetch_method", "requests")
                pw_headers2["price_retry"] = "succeeded"
                result, headers, final_url = pw_result2, pw_headers2, pw_final_url2
                print(f"PLAYWRIGHT RETRY (prices): improved — {pw_n_prods2} products, coverage {pw_cov2 if pw_cov2 is not None else 0:.0%}")
            else:
                headers["price_retry"] = "no_improvement"
                print("PLAYWRIGHT RETRY (prices): no improvement, keeping original result")
        else:
            print("PLAYWRIGHT RETRY (prices): fetch failed")
            headers["price_retry"] = "fetch_failed"
            headers["playwright_price_retry_failed"] = True

    # Invariant flag: if the collection STILL looks broken after any retry AND it
    # wasn't sourced from the authoritative products.json (confidence >= 0.9),
    # stamp a dataQuality note so the AI verification layer can flag it to the
    # user ("prices look identical — verify on the full store") instead of us
    # presenting a likely-glitched number as fact. Genuinely uniform collections
    # from products.json are trusted and NOT flagged.
    if detected_page_type == "collection":
        _still_broken = _collection_broken(result)
        _src_conf = (result.get("source") or {}).get("confidence") or 0
        if _still_broken and _src_conf < 0.9:
            _dq = result.setdefault("dataQuality", {})
            _dq["suspicious"] = True
            _dq["reason"] = _still_broken
            _dq["note"] = (
                "Every product shows the same price — likely a fetch glitch, verify on the full store."
                if _still_broken == "all_same_price"
                else "Every product reads out of stock — likely a stock-parse failure, verify on the full store."
            )
            print(f"⚠️  [invariant] collection still looks broken ({_still_broken}, confidence={_src_conf}) — flagged as dataQuality")

    # ── Playwright retry for empty homepage shells (JS-rendered themes) ──────
    # Some Shopify themes render the hero, featured collections and product
    # rails entirely client-side, so the requests/cloudscraper HTML is a shell
    # with no hero, no collections and no featured products. Analyzing that
    # shell reports "no video / no hero / 0 featured collections" even though
    # the live homepage is rich (e.g. ayeshashoaibmalik). If the homepage came
    # back empty and we haven't already rendered it, do one Playwright pass.
    _already_pw3 = headers.get("fetch_method") == "playwright" or headers.get("forced_playwright")
    _is_shopify = "shopify" in str(_platform_name).lower()
    if detected_page_type == "homepage" and _is_shopify and not _already_pw3:
        _content = result.get("content") or {}
        _ecom = result.get("ecommerce") or {}
        _empty_homepage = (
            not (_content.get("heroMedia") or [])
            and not (_ecom.get("featuredCollections") or [])
            and not (_ecom.get("featuredProducts") or [])
            and len(_content.get("sections") or []) <= 1
        )
        if _empty_homepage:
            print("PLAYWRIGHT RETRY (homepage): empty shell (no hero/collections/products) — retrying with JS rendering")
            pw_html3, pw_final_url3, pw_headers3 = fetch_with_playwright(final_url)
            if pw_html3:
                pw_result3 = analyzer.analyze(
                    url=pw_final_url3, html=pw_html3, headers=pw_headers3,
                    page_type=detected_page_type,
                    level1={**platform_result, **page_type_result},
                )
                _pc = pw_result3.get("content") or {}
                _pe = pw_result3.get("ecommerce") or {}
                _improved3 = bool(
                    (_pc.get("heroMedia") or [])
                    or (_pe.get("featuredCollections") or [])
                    or (_pe.get("featuredProducts") or [])
                    or len(_pc.get("sections") or []) > len(_content.get("sections") or [])
                )
                if _improved3:
                    pw_headers3["forced_playwright"] = True
                    pw_headers3["forced_playwright_reason"] = "empty_homepage_retry"
                    pw_headers3["original_fetch_method"] = headers.get("fetch_method", "requests")
                    result, headers, final_url = pw_result3, pw_headers3, pw_final_url3
                    print("PLAYWRIGHT RETRY (homepage): improved — hero/collections/products recovered")
                else:
                    print("PLAYWRIGHT RETRY (homepage): no improvement, keeping original result")
            else:
                print("PLAYWRIGHT RETRY (homepage): fetch failed")
                headers["homepage_retry"] = "fetch_failed"

    # base_analyzer copies headers into result.technical.responseHeaders with
    # dict(headers) at analyze() time — anything written to `headers` AFTER
    # analyze() (price_retry, forced_playwright, retry flags) never reached the
    # result, which is why priceRetryOutcomes was always empty in accuracy
    # reports. Stamp retry metadata onto the result explicitly.
    _rh = result.setdefault("technical", {}).setdefault("responseHeaders", {})
    for _retry_key in ("price_retry", "forced_playwright", "forced_playwright_reason",
                       "original_fetch_method", "playwright_retry_attempted",
                       "playwright_retry_failed", "playwright_price_retry_failed"):
        if headers.get(_retry_key) is not None:
            _rh[_retry_key] = headers[_retry_key]
    # ─────────────────────────────────────────────────────────────────────────

    # Always carry Level-1 detection metadata on the result. Some analyzers
    # (notably the homepage extractors) rebuild their result dict from scratch
    # and drop base_result's level1 - which erased platform/pageType
    # confidence from every homepage and broke downstream confidence checks.
    _l1_detected = {**platform_result, **page_type_result}
    _l1_existing = result.get("level1") or {}
    result["level1"] = {**_l1_detected, **_l1_existing}

    # Respect blocked=True set by the analyzer (e.g. Zara Akamai empty-shell).
    _analyzer_blocked = result.get("blocked") is True or result.get("success") is False
    if _analyzer_blocked:
        result["success"] = False
        result.setdefault("page", {})["pageType"] = "blocked"
        result["crawl"] = {
            "success": False, "blocked": True, "crawlBlocked": True,
            "statusCode": status_code or 200,
            "reason": "Page detected as bot-protection or empty shell by analyzer.",
        }
        normalized = normalize_for_competitive_analysis(result)
        _aq = normalized.setdefault("analysisReady", {}).setdefault("extractionQuality", {})
        _aq["score"] = 0.1
        _aq["qualityBucket"] = "blocked"
        normalized["analysisReady"]["merger"] = _build_merger_meta(
            normalized,
            fallbacks_tried=["requests"],
            extraction_method="requests",
        )
        return mark_website_blocked(normalized, reason="bot_protection")

    result["success"] = True
    result["crawl"] = {
        "success": True, "blocked": False, "crawlBlocked": False,
        "statusCode": status_code or 200
    }

    # ── Tier-2 LLM fallback (GPT-4o-mini) ────────────────────────────────────
    # Universal dispatcher: covers product (name/price null), collection
    # (products empty), pricing (plans empty), and unknown pages.
    try:
        from level1_detector.llm_extractor import run_llm_fallback_if_needed
        result = run_llm_fallback_if_needed(
            result, html, final_url, detected_page_type
        )
    except Exception as _llm_err:
        print(f"LLM FALLBACK: error — {_llm_err}")
    # ─────────────────────────────────────────────────────────────────────────

    normalized = normalize_for_competitive_analysis(result)

    # ── Text-evidence safety net ─────────────────────────────────────────────
    # Structure-first extraction drops anything its selectors don't match, and the
    # AI payload is built from that structured output — so a missed element (e.g. a
    # theme's announcement bar) is invisible to the AI too. Capture the cleaned full
    # visible text + key zones verbatim so a curated slice can be fed to the AI as
    # recovery evidence. Numbers stay deterministic; this is for interpretation only.
    try:
        from extractors.text_evidence import build_text_evidence
        # Named rawTextEvidence to avoid colliding with the comparison engine's own
        # structured `textEvidence` (summary/headings/mainTextPreview).
        normalized["rawTextEvidence"] = build_text_evidence(
            html, url=final_url, page_type=detected_page_type
        )
    except Exception as _te_err:
        print(f"TEXT EVIDENCE: skipped — {_te_err}")

    # Issue 9 (Session 4): Sync source.qualityScore → analysisReady.extractionQuality
    # The Jina path (lines ~765-788) already does this; the direct path did not.
    # build_extraction_quality() scores from field presence (starts at 1.0), which
    # diverges from general.py's calibrated confidence score. Use the extractor's
    # score as the authoritative value when it is set.
    # These enrichment steps are wrapped so a failure in one never loses the whole
    # page (which already has its extracted products/sections). analysisReady is
    # guaranteed present by normalize_for_competitive_analysis.
    try:
        _src_quality = (result.get("source") or {}).get("qualityScore") or 0
        if _src_quality > 0:
            _eq = normalized.setdefault("analysisReady", {}).setdefault("extractionQuality", {})
            _sq = round(_src_quality, 2)
            _eq["score"] = _sq
            _bkt = (
                "excellent" if _sq >= 0.90 else
                "good"      if _sq >= 0.80 else
                "partial"   if _sq >= 0.65 else
                "low"
            )
            _eq["qualityBucket"] = _bkt
            if normalized.get("source"):
                normalized["source"]["qualityScore"] = _sq
                normalized["source"]["qualityBucket"] = _bkt
    except Exception as _eq_err:
        print(f"EXTRACTION QUALITY sync: skipped — {_eq_err}")

    # Issue S6-5: For service pages with serviceIntelligence.trustSignals, filter
    # the generic keyword-derived terms that competitive_schema always appends via
    # detect_terms(full_text, TRUST_TERMS) (e.g. "secure","trusted","security","compliance"
    # always fire on an ARFM security-company page).
    try:
        _page_subtype = (result.get("page") or {}).get("generalSubtype") or ""
        if _page_subtype == "service_page":
            _svc_trust = (result.get("serviceIntelligence") or {}).get("trustSignals") or []
            if _svc_trust:
                _GENERIC_TRUST = {
                    "secure", "trusted", "trust", "security", "compliance",
                    "certified", "verified", "privacy",
                }
                _ar = normalized.get("analysisReady") or {}
                _cs = _ar.get("competitiveSignals") or {}
                _at = _cs.get("trustSignals")
                if isinstance(_at, list):
                    _filtered = [t for t in _at if (t or "").lower() not in _GENERIC_TRUST]
                    # Fall back to original list if filtering removed everything
                    normalized["analysisReady"]["competitiveSignals"]["trustSignals"] = (
                        _filtered if _filtered else _at
                    )
    except Exception as _svc_err:
        print(f"SERVICE TRUST filter: skipped — {_svc_err}")

    try:
        normalized.setdefault("analysisReady", {})["merger"] = _build_merger_meta(
            normalized,
            fallbacks_tried=["requests"],
            extraction_method="requests",
        )
    except Exception as _mg_err:
        print(f"MERGER META: skipped — {_mg_err}")
    return normalized


def build_output_filename(data, prefix=""):
    """Derive a descriptive output filename from the analyzed result.

    Examples:
        sivanna-com-pk_homepage.json
        sivanna-com-pk_collection_matte-lipstick.json
        gymshark-com_product_silicone-lifting-straps.json
        elementor-com_general_pricing.json
    """
    page = data.get("page") or {}
    url = page.get("url") or data.get("inputUrl") or ""
    page_type = (page.get("pageType") or "unknown").lower()

    domain = ""
    slug = ""
    try:
        from urllib.parse import urlparse as _urlparse
        parsed = _urlparse(url)
        domain = (parsed.netloc or "").replace("www2.", "").replace("www.", "")
        segments = [x for x in (parsed.path or "").split("/") if x]
        # Drop structural segments so the slug is the meaningful part.
        drop = {"collections", "products", "collection", "product", "pages",
                "category", "categories", "shop", "en", "us", "en-us", "en_us", "w"}
        meaningful = [seg for seg in segments if seg.lower() not in drop]
        if meaningful:
            slug = meaningful[-1]
    except Exception:
        pass

    def _clean(part):
        part = re.sub(r"\.(html?|php|aspx?)$", "", str(part or ""), flags=re.I)
        part = re.sub(r"[^A-Za-z0-9]+", "-", part).strip("-").lower()
        return part[:60]

    pieces = [x for x in [_clean(domain), _clean(page_type), _clean(slug)] if x]
    # homepage slug repeats nothing useful; and don't repeat pageType==slug
    if len(pieces) == 3 and pieces[1] == pieces[2]:
        pieces = pieces[:2]
    name = (prefix + "_".join(pieces)) if pieces else prefix + "website_analysis"
    return name + ".json"


def save_output(data, output_path=None):
    """Save the analysis JSON.

    When output_path is None a descriptive filename is generated from the
    result (domain + page type + slug), and existing files are never
    overwritten (a -2, -3, ... counter is appended instead).
    """
    Path("output").mkdir(exist_ok=True)

    if output_path is None:
        output_file = Path("output") / build_output_filename(data)
        base = build_output_filename(data)[:-5]  # without .json
        counter = 2
        while output_file.exists():
            output_file = Path("output") / f"{base}-{counter}.json"
            counter += 1
    else:
        output_file = Path(output_path)

    output_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return output_file


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: py main.py https://example.com/page-url")
        sys.exit(1)

    input_url = normalize_url(sys.argv[1])

    try:
        data = analyze_url(input_url)
        if data.get("success") is False:
            output_file = save_output(data, output_path="output/" + build_output_filename(data, prefix="error_"))
        else:
            output_file = save_output(data)
        print(json.dumps(data, indent=2, ensure_ascii=False))
        print(f"\\nSaved to {output_file}")

    except Exception as e:
        tb = __import__("traceback").format_exc()
        print(tb, file=sys.stderr)
        error_data = {
            "success": False, "inputUrl": input_url,
            "error": str(e),
            "traceback": tb,
            "crawl": {
                "success": False, "blocked": False,
                "crawlBlocked": False, "statusCode": None
            },
            "source": {"stage": "main.py", "success": False}
        }
        save_output(error_data, output_path="output/error_analysis.json")
        sys.exit(1)
