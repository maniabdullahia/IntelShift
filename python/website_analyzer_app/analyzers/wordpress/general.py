from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urlunparse
import re
import json


# -----------------------------
# HELPERS
# -----------------------------

def clean_text(text):
    return re.sub(r"\s+", " ", text or "").strip()


def normalize_url(raw_url, base_url=None):
    if not raw_url:
        return None

    raw_url = str(raw_url).strip()

    if raw_url.lower().startswith(("javascript:", "#", "mailto:", "tel:")):
        return None

    full_url = urljoin(base_url or "", raw_url)
    parsed = urlparse(full_url)

    cleaned = parsed._replace(
        query="",
        fragment=""
    )

    return urlunparse(cleaned)


def unique_items(items, key):
    seen = set()
    output = []

    for item in items:
        value = item.get(key)

        if not value:
            continue

        value_key = str(value).strip().lower()

        if value_key in seen:
            continue

        seen.add(value_key)
        output.append(item)

    return output


def normalize_plan_name(name):
    name = clean_text(name)
    name = re.sub(
        r"^(%\s*off|save\s+\d+%|popular|recommended|best value)\s+",
        "",
        name,
        flags=re.I
    )
    name = re.sub(r"\s+", " ", name).strip(" -–—:")
    return name[:100]


def parse_price_amount(raw):
    if raw is None:
        return None

    s = str(raw).lower().replace(",", "").strip()
    s = s.replace("+", "")

    # For ranges, store the lower bound as amount.
    s = re.split(r"\s*[–-]\s*", s)[0]

    multiplier = 1

    if s.endswith("k"):
        multiplier = 1000
        s = s[:-1]

    try:
        return float(s) * multiplier
    except Exception:
        return None


PRICE_REGEX = re.compile(
    r"""
    (?P<prefix>~)?
    # Require a non-alpha char before Rs to avoid matching word endings like "growers."
    (?P<currency>(?<![a-zA-Z])(?:\$|£|€|₹|Rs\.?)|USD|EUR|GBP)
    \s*
    (?P<amount>
        \d[\d,]*(?:\.\d+)?(?:k)?
        (?:\s*[–-]\s*
        (?:(?:\$|£|€|₹|Rs\.?|USD|EUR|GBP)\s*)?
        \d[\d,]*(?:\.\d+)?(?:k)?)?
        \+?
    )
    \s*
    (?P<period>
        /\s*(?:mo|month|monthly|yr|year|annually|annual|seat|user)?
        |per\s+(?:month|year|user|seat)
        |monthly
        |annually
        |yearly
        |/year
        |/month
    )?
    """,
    re.IGNORECASE | re.VERBOSE
)


# ---------------------------------------------------------------------------
# Noise-heading detection (Issue 4)
# Headings that are prices, discounts, CTAs, or feature states must not
# become content sections or plan names.
# ---------------------------------------------------------------------------
_NOISE_HEADING_CURRENCY_RE = re.compile(
    r'^[$£€¥₹]\s*\d|^\d+\s*[$£€¥₹]',
    re.IGNORECASE
)
_NOISE_HEADING_DISCOUNT_RE = re.compile(
    r'^save\s+[\d$£€]|^\d+\s*%\s*off\b|^up\s+to\s+\d+\s*%',
    re.IGNORECASE
)
_NOISE_HEADING_CTA_RE = re.compile(
    r'^(?:buy\s+now|get\s+started|start\s+(?:free|now|today)|sign\s+up|try\s+(?:it\s+)?(?:free|now)|'
    r'upgrade\s+now|contact\s+sales|request\s+(?:a\s+)?demo|book\s+(?:a\s+)?demo|'
    r'get\s+(?:a\s+)?(?:free\s+)?(?:trial|quote|demo)|learn\s+more|read\s+more|shop\s+now)$',
    re.IGNORECASE
)
_NOISE_HEADING_FEATURE_STATE_RE = re.compile(
    r'^(?:included|not\s+included|available|unavailable|coming\s+soon|add[- ]on)$',
    re.IGNORECASE
)
_NOISE_HEADING_NUMERIC_RE = re.compile(r'^\d[\d,.\s]*$')
# Measurement/size strings: "113g", "283g", "113g & 226g", "500ml", "2 pack"
_NOISE_HEADING_MEASUREMENT_RE = re.compile(
    r'^\d[\d\s.,&x×]*(?:g|kg|ml|l|oz|lb|lbs?|pack|packs?)\b'
    r'(?:\s*[&×x]\s*\d[\d\s.,]*(?:g|kg|ml|l|oz|lb|lbs?|pack|packs?))?'
    r'\s*$',
    re.IGNORECASE
)


def is_noise_heading(text: str) -> bool:
    """Return True when a heading is noise that should not become a section/plan heading.

    Rejects:
    - Punct-only / < 3 alpha   ("-", "•", "—", ":", single letters)
    - Currency-only strings    ($5/mo, £29)
    - Discount strings          (Save $12 annually, 20% off)
    - Pure CTA strings          (Buy now, Get started)
    - Feature-state strings     (included, not included)
    - Numeric-only strings      (5, 100)
    - Measurement/size strings  (113g, 113g & 226g, 500ml, 2 pack)
    """
    if not text:
        return False
    t = text.strip()
    # Fewer than 3 alpha characters: punctuation-only or degenerate heading.
    # Catches: "-", "•", "|", "—", "–", ":", single letters, "- -", etc.
    if sum(1 for c in t if c.isalpha()) < 3:
        return True
    if _NOISE_HEADING_CURRENCY_RE.search(t):
        return True
    if _NOISE_HEADING_DISCOUNT_RE.search(t):
        return True
    if _NOISE_HEADING_CTA_RE.match(t):
        return True
    if _NOISE_HEADING_FEATURE_STATE_RE.match(t):
        return True
    if _NOISE_HEADING_NUMERIC_RE.match(t):
        return True
    if _NOISE_HEADING_MEASUREMENT_RE.match(t):
        return True
    return False


PLAN_BAD_NAMES = {
    "create",
    "manage",
    "optimize",
    "marketing & ecommerce features",
    "marketing & e-commerce features",
    "choose your plan",
    "compare features",
    "compare the costs",
    "compare the cost",
    "feature",
    "features",
    "widget list",
    "key features & benefits",
    "websites built",
    "of global sites",
    "five-star reviews",
    "your website, built brilliantly",
    "select your plan",
    "pricing",
    "plans",
    "monthly",
    "annually",
    "annual",
    "billing",
    "support",
    "learn more",
    "buy now",
    "contact sales",
    "faq",
    "faqs",
    "how woocommerce pricing works",
    "woocommerce pricing puts you in control",
    "payments: pick your processor",
    "hosting: choose your provider",
    "extensions: add à la carte",
    "extensions: add a la carte",
    "core platform: woocommerce",
    "estimate your costs with woocommerce",
    "grow your business, not your costs",
    "offer any payments without penalties",
    "see real woocommerce pricing breakdowns",
    "get a custom quote",
}

COMPARISON_OR_COMPONENT_NAMES = {
    "shopify basic",
    "shopify advanced",
    "shopify plus",
    "bigcommerce standard",
    "bigcommerce enterprise",
    "salesforce commerce cloud",
    "wix enterprise",
    "adobe commerce",
    "adobe commerce (magento)",
    "magento",
    "hosting",
    "hosting: choose your provider",
    "extensions",
    "extensions: add à la carte",
    "extensions: add a la carte",
    "payments",
    "payments: pick your processor",
    "core platform",
    "core platform: woocommerce",
}

KNOWN_PLAN_NAMES = {
    "free", "starter", "basic", "lite", "essential", "standard", "plus",
    "pro", "pro+", "premium", "advanced", "advanced solo", "business",
    "growth", "scale", "max", "ultra", "team", "teams", "enterprise",
    "enterprise plan", "agency", "expert", "one", "one agency", "solo",
    "personal", "professional", "developer", "ultimate", "unlimited",
    "guru", "individual", "hobby", "team plan", "business plan",
    "elite", "platinum", "diamond", "gold", "silver", "bronze",
    "launch", "grow", "accelerate", "foundation", "core", "advanced solo",
}

PLAN_CONTEXT_WORDS = [
    "site", "sites", "website", "websites", "user", "users", "seat", "seats",
    "credit", "credits", "support", "monthly", "annually", "billed", "plan",
    "free trial", "custom pricing", "enterprise", "buy now", "contact sales",
    "subscription", "included", "not included", "features", "templates",
    "per month", "per year", "/mo", "/yr"
]


def looks_like_plan_name(name):
    name = normalize_plan_name(name)
    low = name.lower()

    if not name or len(name) > 80:
        return False

    if low in PLAN_BAD_NAMES or low in COMPARISON_OR_COMPONENT_NAMES:
        return False

    if low.startswith(("for ", "a ", "the ", "how ", "what ", "why ", "here ",
                        "choose ", "select ", "compare ", "see ", "view ")):
        return False

    if re.search(r"[?.]$", name):
        return False

    if re.search(r"\d{4}|\$\s*\d|\d+\s*(?:k|mb|gb|%)", low):
        return False

    # Reject names ending in " plans" / " plan" — these are section headings,
    # not plan names ("Editor Pro plans", "Our plans", etc.)
    if re.search(r'\bplans?\s*$', low) and len(name.split()) > 1:
        return False

    # Reject noise headings (currency, discounts, CTAs, feature states)
    if is_noise_heading(name):
        return False

    if low in KNOWN_PLAN_NAMES:
        return True

    # Allow branded plan names only when they contain a known plan token.
    # Example: "Google AI Pro", "Elementor One", but not "Shopify Basic" on a comparison table.
    words = name.split()
    if 2 <= len(words) <= 4:
        if any(w.lower() in KNOWN_PLAN_NAMES for w in words):
            bad_brands = ["shopify", "bigcommerce", "salesforce", "wix", "adobe", "magento"]
            if not any(b in low for b in bad_brands):
                return True

    return False


def extract_price_mentions(text, limit=80):
    prices = []

    for match in PRICE_REGEX.finditer(text or ""):
        raw_amount = clean_text(match.group("amount"))
        currency = clean_text(match.group("currency"))
        period = clean_text(match.group("period")) or None

        prices.append({
            "raw": clean_text(match.group(0)),
            "currency": currency,
            "amountRaw": raw_amount,
            "amount": parse_price_amount(raw_amount),
            "period": period
        })

    seen = set()
    out = []

    for p in prices:
        key = p["raw"].lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(p)

    return out[:limit]


def get_level1_subtype(level1):
    if not isinstance(level1, dict):
        return None

    subtype = level1.get("generalSubtype")

    if subtype:
        return subtype

    debug = level1.get("pageTypeDebug") or {}
    signals = debug.get("signals") or {}

    return signals.get("generalSubtype")


def is_comparison_or_matrix_text(text):
    low = (text or "").lower()
    # Detect dense competitor-name clusters — characteristic of comparison tables
    competitor_hits = sum(1 for c in (
        "shopify", "bigcommerce", "salesforce", "wix", "magento",
        "adobe commerce", "squarespace", "woocommerce"
    ) if c in low)
    return (
        "feature free essential" in low
        or "shopify basic shopify advanced" in low
        or "bigcommerce standard" in low
        or "salesforce commerce cloud" in low
        or low.count("free trial") >= 5
        or (low.count("feature") >= 6 and low.count("included") >= 6)
        or competitor_hits >= 3   # 3+ competitors in one block = comparison table
    )


# -----------------------------
# CLEAN DOM
# -----------------------------

def clean_dom_for_general(html):
    soup = BeautifulSoup(html or "", "lxml")

    remove_selectors = [
        "script", "style", "noscript", "iframe", "svg", "template",
        "header", "footer", "nav",
        ".menu", ".navbar", ".site-header", ".site-footer",
        ".mobile-menu", ".offcanvas", ".popup", ".modal", ".drawer",
        ".newsletter", ".cookie", ".comments", "#comments", ".related-posts",
        ".woocommerce-mini-cart", ".cart-drawer",
        "[class*='popup']", "[class*='modal']", "[class*='drawer']",
        "[class*='cookie']", "[class*='newsletter']"
    ]

    for selector in remove_selectors:
        for node in soup.select(selector):
            node.decompose()

    return soup


# -----------------------------
# SEO / META / STRUCTURED DATA
# -----------------------------

def extract_basic_seo(soup, url):
    title = soup.title.get_text(" ") if soup.title else None

    meta_description = None
    desc = soup.select_one("meta[name='description']")

    if desc:
        meta_description = desc.get("content")

    canonical = None
    canonical_tag = soup.select_one("link[rel='canonical']")

    if canonical_tag:
        canonical = canonical_tag.get("href")

    h1 = soup.select_one("h1")

    return {
        "title": clean_text(title),
        "metaDescription": clean_text(meta_description),
        "canonical": normalize_url(canonical, url) if canonical else None,
        "h1": clean_text(h1.get_text(" ")) if h1 else None
    }


def extract_open_graph(soup):
    og = {}

    for meta in soup.select("meta[property^='og:']"):
        prop = meta.get("property", "").replace("og:", "")
        content = meta.get("content")

        if prop and content:
            og[prop] = clean_text(content)

    return og


def extract_json_ld_items(soup):
    items = []

    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            raw = script.string or script.get_text()

            if not raw:
                continue

            parsed = json.loads(raw)

            if isinstance(parsed, list):
                items.extend(parsed)
            else:
                items.append(parsed)

        except Exception:
            continue

    return items


# -----------------------------
# SAAS PAGE CLASSIFICATION
# -----------------------------

def classify_general_page(url, seo, text):
    path = urlparse(url).path.lower()

    title = " ".join([
        seo.get("title") or "",
        seo.get("h1") or "",
        path
    ]).lower()

    combined = (title + " " + (text or "")[:6000]).lower()

    if any(k in combined for k in [
        "pricing", "plans", "compare plans", "compare pricing", "free trial",
        "enterprise plan", "subscription", "billing", "per month", "monthly",
        "annually", "yearly", "custom pricing", "money-back guarantee"
    ]):
        return "pricing"

    if any(k in combined for k in [
        "documentation", "developer docs", "api reference", "getting started",
        "sdk", "webhooks", "guides", "reference docs"
    ]):
        return "documentation"

    if any(k in combined for k in [
        "integrations", "apps", "connect", "zapier", "hubspot", "slack integration"
    ]):
        return "integrations"

    if any(k in combined for k in [
        "enterprise", "soc 2", "sso", "custom pricing", "advanced security",
        "compliance", "audit logs"
    ]):
        return "enterprise"

    if any(k in combined for k in [
        "features", "capabilities", "solutions", "platform", "use cases", "product overview"
    ]):
        return "features"

    if any(k in combined for k in [
        "api", "graphql", "rest api", "access token", "developer api"
    ]):
        return "api"

    if any(k in combined for k in ["careers", "jobs", "we are hiring", "open positions"]):
        return "careers"

    if any(k in combined for k in ["blog", "media", "press", "news", "article", "insights"]):
        return "blog"

    if any(k in combined for k in ["about us", "our story", "mission", "vision", "who we are"]):
        return "about"

    if any(k in combined for k in ["contact us", "get in touch", "support center", "contact"]):
        return "contact"

    if any(k in combined for k in ["faq", "frequently asked questions"]):
        return "faq"

    if any(k in combined for k in ["privacy policy", "gdpr", "cookie policy", "data protection"]):
        return "privacyPolicy"

    if any(k in combined for k in ["terms of service", "terms and conditions", "acceptable use"]):
        return "terms"

    return "general"


# -----------------------------
# CONTENT EXTRACTION
# -----------------------------

def dedupe_sections(sections):
    seen = set()
    output = []

    for section in sections:
        text = clean_text(section.get("text", ""))
        heading = clean_text(section.get("heading", ""))

        if not text:
            continue

        key = (heading + "|" + text[:220]).lower()

        if key in seen:
            continue

        seen.add(key)

        output.append({
            "heading": heading or None,
            "text": text
        })

    return output


def extract_general_sections(soup):
    sections = []

    main = (
        soup.select_one("main")
        or soup.select_one(".site-main")
        or soup.select_one(".content")
        or soup.select_one(".entry-content")
        or soup.select_one(".page-content")
        or soup.body
        or soup
    )

    candidates = main.select(
        """
        section,
        article,
        .section,
        [class*='section'],
        .elementor-section,
        .elementor-widget-container,
        .wp-block-group,
        .entry-content,
        .page-content,
        .container,
        [class*='pricing'],
        [class*='plan']
        """
    )

    if not candidates:
        candidates = [main]

    for node in candidates:
        text = clean_text(node.get_text(" "))

        # Absolute minimum — catch even short headed service items
        if len(text) < 20:
            continue

        heading = None
        h = node.select_one("h1, h2, h3, .elementor-heading-title, strong")

        if h:
            raw_heading = clean_text(h.get_text(" "))
            if is_noise_heading(raw_heading):
                # Issue 1: measurement/noise heading — walk ALL heading elements in the
                # node and use the first clean semantic one instead.
                for fallback_h in node.select("h1, h2, h3, h4"):
                    fb = clean_text(fallback_h.get_text(" "))
                    if fb and not is_noise_heading(fb):
                        heading = fb
                        break
            else:
                heading = raw_heading

        # Null-heading nodes still need enough text to be meaningful
        if not heading and len(text) < 40:
            continue

        sections.append({
            "heading": heading,
            "text": text[:3000]
        })

    # Issue 2: extract H3 sub-sections from service/offering H2 containers.
    # When a page has <h2>Our Services</h2> followed by multiple <h3>…</h3>
    # children, each H3 must become an independent section rather than being
    # collapsed into the parent H2 block.
    _SERVICE_H2_RE = re.compile(
        r'\b(?:services?|offerings?|solutions?|capabilities?|'
        r'what\s+we\s+(?:do|offer|provide)|our\s+(?:services?|solutions?))\b',
        re.IGNORECASE
    )
    for h2 in main.select("h2"):
        h2_text = clean_text(h2.get_text(" "))
        if not _SERVICE_H2_RE.search(h2_text):
            continue
        # Walk siblings/children looking for H3-level service items
        parent = h2.parent
        for h3 in parent.select("h3"):
            h3_text = clean_text(h3.get_text(" "))
            if not h3_text or is_noise_heading(h3_text):
                continue
            parts = [h3_text]
            for sib in h3.find_next_siblings():
                if sib.name in ("h2", "h3", "h1"):
                    break
                t = clean_text(sib.get_text(" "))
                if t:
                    parts.append(t)
            sec_text = " ".join(parts)
            if len(sec_text) >= 40:
                sections.append({"heading": h3_text, "text": sec_text[:3000]})

    sections = dedupe_sections(sections)

    # --- Pass 1: structural noise removal ---
    # Build heading index for container-section detection.
    all_h_lower = [s["heading"].lower() for s in sections if s.get("heading")]

    pass1 = []
    for section in sections:
        heading = section.get("heading") or ""
        text = section.get("text", "")
        lower = text.lower()

        # heading == text: empty content stub (no body beyond the heading itself)
        if heading and text.strip() == heading.strip():
            continue

        # Single action-word headings (Create, Manage…) are feature-row labels
        if heading and heading.lower() in PLAN_BAD_NAMES:
            continue

        # Container section: a section whose text subsumes 3+ other section headings
        # (e.g. "Our Cloud Services" containing all individual service H3 headings)
        if heading:
            h_low = heading.lower()
            contained = sum(
                1 for h in all_h_lower
                if h != h_low and len(h) > 8 and h in lower
            )
            if contained >= 3:
                continue

        # Cookie / menu page noise
        if lower.count("cookie") > 6 and "pricing" not in lower:
            continue
        if lower.count("menu") > 10 and len(text) > 1800:
            continue

        pass1.append(section)

    # --- Pass 2: null-heading handling ---
    # Short null-heading sections are supplementary context for the preceding section
    # (e.g. size/description blocks after a product name). Merge them in.
    # Long null-heading sections or orphaned ones (no predecessor) are dropped.
    filtered = []
    for sec in pass1:
        if sec.get("heading") is None:
            if filtered and len(sec.get("text", "")) < 500:
                # Append to previous section's text
                prev = dict(filtered[-1])
                prev["text"] = (prev.get("text", "") + " " + sec["text"].strip())[:3000]
                filtered[-1] = prev
            # else: orphaned or too long → drop
        else:
            filtered.append(sec)

    return filtered[:45]


def extract_headings(soup):
    headings = []

    main = soup.select_one("main") or soup.body or soup

    for h in main.select("h1, h2, h3, h4"):
        text = clean_text(h.get_text(" "))

        if not text or len(text) > 180:
            continue

        # Issue 4: suppress noise headings (prices, discounts, CTAs, feature states)
        if is_noise_heading(text):
            continue

        headings.append({
            "level": h.name,
            "text": text
        })

    seen = set()
    out = []

    for h in headings:
        key = (h["level"], h["text"].lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(h)

    return out[:60]


def extract_links(soup, base_url):
    links = []

    main = soup.select_one("main") or soup.body or soup

    for a in main.select("a[href]"):
        text = clean_text(a.get_text(" "))
        href = a.get("href")

        if not text or not href or len(text) > 140:
            continue

        url = normalize_url(href, base_url)

        if not url:
            continue

        links.append({
            "text": text,
            "url": url
        })

    return unique_items(links, "url")[:80]


def extract_images(soup, base_url):
    images = []

    main = soup.select_one("main") or soup.body or soup

    for img in main.select("img"):
        src = (
            img.get("data-src")
            or img.get("data-lazy-src")
            or img.get("data-original")
            or img.get("src")
        )

        if not src or src.startswith("data:image"):
            continue

        src_lower = src.lower()

        if any(k in src_lower for k in ["logo", "icon", "spinner", "loader", "placeholder"]):
            continue

        images.append({
            "url": normalize_url(src, base_url),
            "alt": clean_text(img.get("alt"))
        })

    return unique_items(images, "url")[:40]


_CTA_KW_RE = re.compile(
    r'\b(?:contact|get\s+quote|request\s+quote|book|call|whatsapp|learn\s+more|'
    r'read\s+more|shop|buy|download|subscribe|sign\s+up|start|demo|get\s+started|'
    r'try|upgrade|contact\s+sales|talk\s+to|estimate|calculate)\b',
    re.IGNORECASE
)


def extract_ctas(soup, base_url):
    ctas = []

    for node in soup.select("a[href], button"):
        text = clean_text(node.get_text(" "))

        if not text or len(text) > 120:
            continue

        if _CTA_KW_RE.search(text):
            href = node.get("href")

            ctas.append({
                "text": text,
                "url": normalize_url(href, base_url) if href else None
            })

    seen = set()
    out = []
    for c in ctas:
        key = (c.get("text", "").lower(), c.get("url"))
        if key in seen:
            continue
        seen.add(key)
        out.append(c)

    return out[:40]


# -----------------------------
# PRICING EXTRACTION
# -----------------------------

def extract_plan_blocks_from_sections(sections):
    # Collect all valid plan headings upfront so we can use them as
    # cross-card boundary markers (Issue 2).
    all_plan_headings = [
        normalize_plan_name(s.get("heading") or "")
        for s in sections
        if looks_like_plan_name(normalize_plan_name(s.get("heading") or ""))
    ]

    blocks = []

    for section in sections:
        heading = normalize_plan_name(section.get("heading") or "")
        text = clean_text(section.get("text") or "")

        if not heading or not text:
            continue

        low_text = text.lower()

        if is_comparison_or_matrix_text(text):
            continue

        if not (looks_like_plan_name(heading) and any(w in low_text for w in PLAN_CONTEXT_WORDS)):
            continue

        # Issue 2: prevent cross-card price contamination.
        # When a section DOM node spans multiple plan cards the raw text
        # can contain the next card's price.  Cut the text at the first
        # occurrence of any OTHER plan heading so each block stays within
        # its own card's content.  Also cap at 900 chars as a safety net.
        search_start = len(heading)  # skip past the heading itself
        cutoff = min(len(text), 900)
        heading_low = heading.lower()
        for other in all_plan_headings:
            other_low = other.lower()
            if other_low == heading_low:
                continue
            # If the other heading is a pure prefix of ours (e.g. "Advanced" vs
            # "Advanced Solo"), its occurrences in our text are just our own
            # heading re-appearing — not a card boundary. Skip it.
            if heading_low.startswith(other_low + " "):
                continue
            # Also skip if we are a prefix of the other heading (e.g. when
            # processing "Advanced", skip "Advanced Solo" — it starts with us).
            # "Advanced Solo" in our section text is just a mention of the sibling
            # variant, not a true card boundary.
            if other_low.startswith(heading_low + " "):
                continue
            m = re.search(r'\b' + re.escape(other) + r'\b', text[search_start:], re.I)
            if m:
                boundary = search_start + m.start()
                if boundary < cutoff:
                    cutoff = boundary

        blocks.append({
            "name": heading,
            "text": text[:cutoff]
        })

    return unique_items(blocks, "name")


def extract_plan_blocks_from_headings(headings, main_text):
    valid_names = []

    for h in headings:
        txt = normalize_plan_name(h.get("text") or "")
        if looks_like_plan_name(txt):
            valid_names.append(txt)

    valid_names = list(dict.fromkeys(valid_names))
    blocks = []

    for i, name in enumerate(valid_names):
        # Build a negative lookahead so that "Advanced" does not match inside
        # "Advanced Solo" when both are in valid_names.  For every longer plan
        # name whose first word(s) equal this name, exclude the extra qualifier.
        qualifiers = [
            n[len(name):].strip()
            for n in valid_names
            if n.lower() != name.lower() and n.lower().startswith(name.lower() + " ")
        ]
        if qualifiers:
            neg_la = "(?!" + "|".join(r"\s+" + re.escape(q) for q in qualifiers) + ")"
            pattern = re.escape(name) + neg_la
        else:
            pattern = re.escape(name)

        m = re.search(r"\b" + pattern, main_text, flags=re.I)
        if not m:
            continue

        start = m.start()
        end = min(len(main_text), start + 900)  # 900-char cap reduces cross-card contamination

        for next_name in valid_names[i + 1:]:
            nm = re.search(r"\b" + re.escape(next_name) + r"\b", main_text[start + len(name):end], flags=re.I)
            if nm:
                end = start + len(name) + nm.start()
                break

        block_text = clean_text(main_text[start:end])

        if len(block_text) < 30 or is_comparison_or_matrix_text(block_text):
            continue

        blocks.append({
            "name": name,
            "text": block_text
        })

    return unique_items(blocks, "name")


def extract_plan_blocks_from_dom(soup):
    """Extract plan blocks using card-container boundaries (Elementor / column layouts).

    Strategy: for each plan-name H3, walk UP the DOM until we find the ancestor
    whose *parent* also contains sibling elements with other plan-name H3s.  That
    ancestor is the plan "card".  We then take all text inside the card — which is
    naturally bounded by the card container and cannot bleed into neighbouring cards.
    """
    main = soup.select_one("main") or soup.body or soup

    plan_h3s = []
    for h3 in main.find_all("h3"):
        if h3.find_parent(["header", "nav", "footer"]):
            continue
        name = normalize_plan_name(clean_text(h3.get_text(" ")))
        if looks_like_plan_name(name):
            plan_h3s.append((h3, name))

    if len(plan_h3s) < 2:
        return []

    # Build a set of all plan-name H3 nodes for fast lookup
    plan_h3_nodes = {id(h3): name for h3, name in plan_h3s}

    blocks = []
    for h3_node, name in plan_h3s:
        # Walk up from h3 to find its card container:
        # the node whose parent contains siblings that hold OTHER plan H3s.
        card = h3_node
        while card.parent and card.parent != main:
            parent = card.parent
            sibling_plan_count = 0
            for sib in parent.children:
                if sib is card or not hasattr(sib, "find_all"):
                    continue
                for h3 in sib.find_all("h3"):
                    if id(h3) in plan_h3_nodes and plan_h3_nodes[id(h3)] != name:
                        sibling_plan_count += 1
                        break
            if sibling_plan_count >= 1:
                break  # `card` is the column / card element
            card = parent

        block_text = clean_text(card.get_text(" "))[:900]
        if len(block_text) < 30 or is_comparison_or_matrix_text(block_text):
            continue
        blocks.append({"name": name, "text": block_text})

    return unique_items(blocks, "name")


def extract_features_from_block(block_text):
    features = []

    feature_patterns = [
        r"\b\d+[\d,]*\s+(?:site|sites|website|websites|user|users|seat|seats|credit|credits|template|templates)\b",
        r"\b(?:basic|priority|premium|dedicated)\s+support\b",
        r"\b(?:theme builder|form builder|popup builder|custom code|custom css|dynamic content|ecommerce features|image optimization|site accessibility|email deliverability|site management|cloud templates)\b",
        # "free trial" and "custom pricing" are useful signals; bare "included" / "not included" are noise
        r"\b(?:free trial|custom pricing)\b",
        r"\bunlimited\s+(?:site|sites|user|users|seat|seats|bandwidth|storage|email|emails|contacts|projects)\b",
    ]

    for pat in feature_patterns:
        for match in re.finditer(pat, block_text or "", flags=re.I):
            val = clean_text(match.group(0))
            if val and val.lower() not in [f.lower() for f in features]:
                features.append(val)

    return features[:18]


def infer_plan_description(block_text, plan_name):
    text = clean_text(block_text)
    if not text:
        return None

    # Strip promotional badge prefixes that appear before the plan name:
    # e.g. "Birthday 21 % off One …", "Best Value Elite License …", "Most Popular Pro …"
    text = re.sub(
        r'^(?:birthday|new|sale|hot|most popular|best value|popular|recommended)\s+\d*\s*%?\s*(?:off\s+)?',
        '', text, flags=re.I
    ).strip()
    # Also strip bare "NN % off" at the start (e.g. "20 % off Pro …")
    text = re.sub(r'^\d+\s*%\s*off\s+', '', text, flags=re.I).strip()

    text = re.sub(r"^" + re.escape(plan_name) + r"\b", "", text, flags=re.I).strip()
    text = re.split(r"(?:\$|£|€|₹|Rs\.?|Buy now|Contact sales|Billed|Monthly|Annually)", text, maxsplit=1, flags=re.I)[0]
    text = clean_text(text)

    if 8 <= len(text) <= 180:
        return text

    return None


def choose_better_plan_block(existing, candidate):
    if not existing:
        return candidate

    existing_text = existing.get("text", "")
    candidate_text = candidate.get("text", "")

    existing_prices = extract_price_mentions(existing_text, limit=3)
    candidate_prices = extract_price_mentions(candidate_text, limit=3)

    if candidate_prices and not existing_prices:
        return candidate

    if is_comparison_or_matrix_text(existing_text) and not is_comparison_or_matrix_text(candidate_text):
        return candidate

    # Prefer concise plan cards over huge sections.
    if candidate_prices and len(candidate_text) < len(existing_text):
        return candidate

    return existing


def extract_core_plans(sections, headings, main_text, soup=None):
    # DOM-based extraction first: uses H3 sibling boundaries (most precise for
    # Elementor card layouts where each plan is in its own column container).
    blocks = extract_plan_blocks_from_dom(soup) if soup is not None else []
    if not blocks:
        blocks = extract_plan_blocks_from_sections(sections)

    # DOM/section blocks are authoritative for the plan names they cover.
    # Only use heading-based blocks to fill in plan names NOT already found above.
    dom_names = {b["name"].lower() for b in blocks}
    heading_blocks = [
        b for b in extract_plan_blocks_from_headings(headings, main_text)
        if b["name"].lower() not in dom_names
    ]

    by_name = {}

    for b in blocks + heading_blocks:
        key = b["name"].lower()
        by_name[key] = choose_better_plan_block(by_name.get(key), b)

    plans = []

    for block in by_name.values():
        name = normalize_plan_name(block["name"])
        text = clean_text(block.get("text") or "")
        low = text.lower()

        if not looks_like_plan_name(name):
            continue

        if name.lower() in PLAN_BAD_NAMES or name.lower() in COMPARISON_OR_COMPONENT_NAMES:
            continue

        if is_comparison_or_matrix_text(text):
            continue

        price_mentions = extract_price_mentions(text, limit=8)
        primary_price = price_mentions[0] if price_mentions else None

        if name.lower() == "free" or re.search(r"\bfree\b", low[:120]):
            primary_price = {
                "raw": "Free",
                "currency": None,
                "amountRaw": "0",
                "amount": 0,
                "period": None
            }

        if re.search(r"\bcustom pricing\b|\bcontact sales\b", low[:260]) and not primary_price:
            primary_price = {
                "raw": "Custom pricing",
                "currency": None,
                "amountRaw": None,
                "amount": None,
                "period": None
            }

        # Issue 2: verify the price is co-located within the plan's own block
        # (not bled in from a neighbouring card that appears later in the text).
        # A price that only shows up after the first 600 chars is almost certainly
        # from the next card — discard it so the plan gets no price rather than
        # a wrong price.
        if primary_price and price_mentions:
            price_raw = price_mentions[0].get("raw", "")
            price_pos = text.find(price_raw)
            if price_pos > 600:
                primary_price = None
                price_mentions = []

        plans.append({
            "name": name,
            "type": "enterprise" if "enterprise" in name.lower() else "core_plan",
            "description": infer_plan_description(text, name),
            "price": primary_price,
            "priceMentions": price_mentions,
            "features": extract_features_from_block(text),
            "rawText": text[:1200]
        })

    filtered = []
    for p in plans:
        has_price = p.get("price") is not None
        is_known_enterprise = "enterprise" in p["name"].lower()
        has_contact_sales = re.search(
            r'\b(?:custom pricing|contact sales|talk to sales|request quote)\b',
            (p.get("rawText") or "").lower()
        )
        # Issue 3: a plan block without a price is only kept when it is a
        # genuine enterprise/custom tier — section headings and comparison
        # table column headers that have no price must be rejected.
        if has_price or is_known_enterprise or has_contact_sales:
            filtered.append(p)

    return unique_items(filtered, "name")[:20]


def detect_billing(text):
    low = (text or "").lower()

    return {
        "monthly": any(k in low for k in ["monthly", "/mo", "per month", "/month"]),
        "annual": any(k in low for k in ["annually", "annual", "yearly", "/yr", "per year", "billed annually"]),
        "billingModel": "annual" if "billed annually" in low or "annually" in low else ("monthly" if "monthly" in low else None),
        "mentionsAnnualDiscount": bool(re.search(r"save\s+\d+%|save\s+\$?\s*\d+", low)),
        "moneyBackGuarantee": "30-day" if re.search(r"30[- ]day money[- ]back", low) else ("mentioned" if "money-back" in low or "money back" in low else None)
    }


# Section headings that are known competitor/platform names — these are
# comparison table columns, not pricing components for the current site.
_COMPETITOR_PLATFORM_NAMES = frozenset({
    "shopify", "bigcommerce", "salesforce", "salesforce commerce cloud",
    "wix", "magento", "adobe commerce", "squarespace", "woocommerce",
    "prestashop", "volusion", "3dcart", "bigcartel", "ecwid", "square",
    "weebly", "godaddy", "shift4shop", "sellfy", "storenvy", "cratejoy",
    "netsuite", "sap commerce cloud", "oracle commerce", "hybris",
})


# Allowed component heading keywords (Issue 5 allowlist).
# A pricing component heading MUST contain one of these terms.
_COMPONENT_HEADING_ALLOWLIST = frozenset({
    "hosting", "payments", "payment processing", "extensions", "plugins",
    "transactions", "infrastructure", "platform", "core platform", "platform fee",
    "support", "addons", "add-ons", "revenue share", "server hosting",
    "premium plugins", "subscription processing", "localized selling",
    "processor",
})

# Issue 4: headings that look like case studies / brand examples must never
# become pricing components.
_CASE_STUDY_HEADING_RE = re.compile(
    r'\b(?:case\s+study|customer\s+(?:example|story|success)|example\s+store|'
    r'boutique|regulated\s+|subscription\s+(?:coffee|brand|box)|luxury\s+goods|'
    r'retailer$|brand$)\b',
    re.IGNORECASE
)


def extract_pricing_components(sections, text):
    components = []
    # Body-only fallback keywords (used when no heading is present)
    component_keywords = [
        "hosting", "extensions", "payments", "processor", "payment processing",
        "core platform", "platform fee", "revenue share", "subscription processing",
        "localized selling", "premium plugins", "server hosting"
    ]

    for section in sections or []:
        heading = clean_text(section.get("heading") or "")
        body = clean_text(section.get("text") or "")
        low_heading = heading.lower()
        low_body = body.lower()

        if not body:
            continue

        # Issue 3: Skip competitor/platform names — these are comparison table
        # columns and must never become pricing components.
        if low_heading in _COMPETITOR_PLATFORM_NAMES:
            continue

        # Issue 4: Skip case-study / brand-example headings.
        if heading and _CASE_STUDY_HEADING_RE.search(heading):
            continue

        # Issue 5: When a heading is present it MUST match the component allowlist.
        # Fall back to body-based detection only when there is no heading.
        if heading:
            is_component = any(k in low_heading for k in _COMPONENT_HEADING_ALLOWLIST)
        else:
            is_component = (
                any(k in low_body for k in component_keywords)
                and any(k in low_body for k in ["free", "$", "fee", "cost", "per month", "per year"])
            )

        if not is_component:
            continue

        if looks_like_plan_name(heading):
            continue

        prices = extract_price_mentions(body, limit=10)

        if not prices and "free" not in low_body:
            continue

        component = {
            "name": heading or infer_component_name(body),
            "type": "pricing_component",
            "priceMentions": prices,
            "free": bool(re.search(r"\bfree\b|\$0\b|0\s*%\s*revenue share", low_body)),
            "description": body[:450],
            "rawText": body[:1200]
        }

        # Try to expose a range when the component has a written range.
        range_match = re.search(
            r"(?P<currency>\$|£|€|₹|Rs\.?)\s*(?P<min>\d[\d,]*(?:\.\d+)?)\s*[–-]\s*(?P<currency2>\$|£|€|₹|Rs\.?)?\s*(?P<max>\d[\d,]*(?:\.\d+)?)(?P<period>/\s*(?:mo|month|year|yr)|\s*per\s+(?:month|year))?",
            body,
            flags=re.I
        )
        if range_match:
            component["range"] = {
                "currency": clean_text(range_match.group("currency")),
                "min": parse_price_amount(range_match.group("min")),
                "max": parse_price_amount(range_match.group("max")),
                "period": clean_text(range_match.group("period")) or None
            }

        components.append(component)

    return unique_items(components, "name")[:15]


def infer_component_name(text):
    low = (text or "").lower()
    if "hosting" in low:
        return "Hosting"
    if "extension" in low:
        return "Extensions"
    if "payment" in low or "processor" in low:
        return "Payments"
    if "revenue share" in low:
        return "Revenue share"
    if "core platform" in low:
        return "Core platform"
    return "Pricing component"


def extract_comparison_pricing(sections, text):
    comparisons = []

    competitors = [
        "Shopify Basic", "Shopify Advanced", "Shopify Plus",
        "BigCommerce Standard", "BigCommerce Enterprise",
        "Salesforce Commerce Cloud", "Wix Enterprise",
        "Adobe Commerce", "Magento"
    ]

    source_text = text or ""

    for c in competitors:
        if c.lower() in source_text.lower():
            comparisons.append({
                "name": c,
                "type": "comparison_pricing_column"
            })

    # Add a high-level table signal if a comparison section exists.
    for section in sections or []:
        heading = clean_text(section.get("heading") or "")
        body = clean_text(section.get("text") or "")
        low = (heading + " " + body).lower()

        if "compare the costs" in low or "shopify basic shopify advanced" in low:
            prices = extract_price_mentions(body, limit=25)
            if prices:
                return {
                    "detected": True,
                    "columns": unique_items(comparisons, "name")[:12],
                    "priceMentions": prices[:25],
                    "rawText": body[:1600]
                }

    return {
        "detected": bool(comparisons),
        "columns": unique_items(comparisons, "name")[:12],
        "priceMentions": [],
        "rawText": None
    }


def extract_comparison_matrix_signal(text, headings):
    low = (text or "").lower()
    heading_texts = [h.get("text", "") for h in headings]

    detected = any(k in low for k in ["compare features", "compare plans", "compare pricing", "compare the costs"])

    possible_columns = []
    for h in heading_texts:
        if looks_like_plan_name(h):
            possible_columns.append(h)

    feature_terms = []
    for term in [
        "number of websites", "support", "cloud templates", "api", "sso", "security",
        "users", "projects", "storage", "credits", "revenue share", "payment processing",
        "hosting", "extensions", "custom pricing"
    ]:
        if term in low:
            feature_terms.append(term)

    return {
        "detected": detected or len(feature_terms) >= 4,
        "columnsDetected": list(dict.fromkeys(possible_columns))[:12],
        "featureTerms": feature_terms[:20]
    }


def extract_enterprise_capabilities(text):
    low = (text or "").lower()
    caps = []

    mapping = {
        "sso": ["sso", "single sign-on", "single sign on"],
        "soc2": ["soc 2", "soc2"],
        "iso27001": ["iso 27001"],
        "auditLogs": ["audit logs", "audit log"],
        "sla": ["sla", "99.9% uptime", "uptime guarantee"],
        "dedicatedSupport": ["dedicated success", "dedicated account", "priority support", "premium-level support"],
        "advancedSecurity": ["advanced security", "enterprise-grade security", "security audits"],
        "customPricing": ["custom pricing"],
        "compliance": ["compliance", "gdpr", "ccpa", "hipaa"]
    }

    for key, patterns in mapping.items():
        if any(p in low for p in patterns):
            caps.append(key)

    return caps


def extract_ai_capabilities(text):
    low = (text or "").lower()
    caps = []

    mapping = {
        "aiContent": ["ai content", "generate copy", "content writing"],
        "aiImages": ["image generation", "image creation", "generate images"],
        "aiCode": ["code generation", "generate code"],
        "aiLayout": ["layout building", "generate wireframes", "ai site planner"],
        "aiAccessibility": ["ai-powered fixes", "ai accessibility"],
        "agenticAI": ["agentic ai", "ai agent", "agents"]
    }

    for key, patterns in mapping.items():
        if any(p in low for p in patterns):
            caps.append(key)

    return caps


def extract_pricing_data(soup, text, sections=None, headings=None):
    text = text or ""
    sections = sections or []
    headings = headings or []

    price_mentions = extract_price_mentions(text, limit=100)
    core_plans = extract_core_plans(sections, headings, text, soup=soup)
    if not core_plans and soup is not None:
        # Deterministic DOM fallback: parses plan-card grids the text-based
        # extractor misses (e.g. WPBakery's split currency/amount spans).
        try:
            from extractors.plan_parser import extract_plan_cards_from_dom
            core_plans = extract_plan_cards_from_dom(soup)
        except Exception:
            pass
    pricing_components = extract_pricing_components(sections, text)
    comparison_pricing = extract_comparison_pricing(sections, text)

    enterprise_plan = None
    for p in core_plans:
        if p.get("type") == "enterprise" or "enterprise" in p.get("name", "").lower():
            enterprise_plan = p
            break

    # Do not calculate main plan price range unless at least 2 real plan cards exist.
    # Component-only pages like WooCommerce pricing should keep this null.
    numeric_core_prices = []
    real_paid_plan_count = 0

    for p in core_plans:
        price = p.get("price") or {}
        amount = price.get("amount")
        if isinstance(amount, (int, float)) and amount > 0:
            numeric_core_prices.append(amount)
            real_paid_plan_count += 1

    if len(core_plans) < 2 or real_paid_plan_count < 2:
        numeric_core_prices = []

    plan_features = {}
    for p in core_plans:
        plan_features[p["name"]] = {
            "description": p.get("description"),
            "features": p.get("features") or []
        }

    billing = detect_billing(text)
    comparison_matrix = extract_comparison_matrix_signal(text, headings)

    has_pricing = (
        bool(core_plans)
        or bool(pricing_components)
        or bool(price_mentions)
        or "pricing" in text.lower()
    )

    if core_plans:
        pricing_model = "plan_based"
    elif pricing_components:
        pricing_model = "component_based"
    elif comparison_pricing.get("detected"):
        pricing_model = "comparison_based"
    else:
        pricing_model = "unknown"

    return {
        "hasPricing": has_pricing,
        "pricingModel": pricing_model,
        "currency": price_mentions[0]["currency"] if price_mentions else None,
        "billing": billing,
        "billingModel": billing.get("billingModel"),
        "planOrder": [p["name"] for p in core_plans],
        "plans": core_plans,
        "pricingComponents": pricing_components,
        "comparisonPricing": comparison_pricing,
        "planFeatures": plan_features,
        "comparisonMatrix": comparison_matrix,
        "enterprisePlan": enterprise_plan,
        "enterpriseOffering": bool(enterprise_plan) or "enterprise" in text.lower(),
        "freeTrial": "free trial" in text.lower(),
        "moneyBackGuarantee": billing.get("moneyBackGuarantee"),
        "priceMentions": price_mentions[:60],
        "lowestMainPlanPrice": min(numeric_core_prices) if numeric_core_prices else None,
        "highestMainPlanPrice": max(numeric_core_prices) if numeric_core_prices else None
    }


# -----------------------------
# SAAS SIGNALS
# -----------------------------

def extract_saas_signals(general_page_type, text, ctas, pricing_data=None):
    text_lower = (text or "").lower()
    pricing_data = pricing_data or {}

    return {
        "isSaaS": general_page_type in [
            "pricing", "features", "integrations", "documentation", "api", "enterprise"
        ] or bool(pricing_data.get("plans") or pricing_data.get("pricingComponents")),
        "hasPricing": bool(pricing_data.get("hasPricing")) or "pricing" in text_lower,
        "hasFreeTrial": "free trial" in text_lower,
        "hasApi": "api" in text_lower or "developer" in text_lower,
        "hasIntegrations": "integrations" in text_lower or "zapier" in text_lower,
        "hasEnterpriseOffering": bool(pricing_data.get("enterprisePlan")),
        "hasFeatureComparison": bool((pricing_data.get("comparisonMatrix") or {}).get("detected")),
        "enterpriseCapabilities": extract_enterprise_capabilities(text),
        "aiCapabilities": extract_ai_capabilities(text),
        "ctaCount": len(ctas)
    }


# -------------------------------------------------------
# SERVICE PAGE EXTRACTION
# -------------------------------------------------------

_SERVICE_SECTION_RE = re.compile(
    r'\b(?:our\s+)?(?:services?|solutions?|what\s+we\s+(?:offer|do|provide)|'
    r'capabilities|packages|how\s+we\s+help)\b',
    re.IGNORECASE
)

_PROCESS_SECTION_RE = re.compile(
    r'\b(?:'
    r'how\s+(?:it\s+works?|we\s+work|to\s+get\s+started|our\s+process\s+works?)'
    r'|our\s+(?:process|workflow|work\s+process)'
    r'|implementation\s+process'
    r'|getting\s+started'
    r'|step\s+[123456789]'
    r')\b',
    re.IGNORECASE
)

_SIZE_WEIGHT_RE = re.compile(
    r'\b\d+\s*(?:g|ml|oz|lb|lbs|kg|l|litre|liter|fl\.?\s*oz)\b',
    re.IGNORECASE
)

_NO_CART_RE = re.compile(
    r'\b(?:add\s+to\s+cart|buy\s+now|add\s+to\s+bag|purchase|checkout)\b',
    re.IGNORECASE
)

# Headings that START with a question word — never treat as service category labels
_INTERROGATIVE_START_RE = re.compile(
    r'^(?:what|how|why|when|where|which|who|is|are|do|can|does|will|should|did|was|were)\b',
    re.IGNORECASE
)

_SERVICE_SKIP_NAMES = frozenset({
    "menu", "navigation", "footer", "home", "about", "about us", "contact",
    "contact us", "faq", "faqs", "testimonials", "privacy policy", "terms",
    "blog", "news", "services", "our services", "what we offer", "solutions",
    "get started", "get in touch", "read more", "learn more", "subscribe",
    "newsletter", "follow us", "popular cloud based storage providers",
    "cloud based business app providers", "frequently asked questions",
    "available exclusively through retailers!",
    # Footer / contact headings that must never become service items
    "request a call", "call us", "hours", "address", "connect with us",
    "opening hours", "open hours", "business hours", "phone", "email",
    "directions", "find us", "location", "reach us", "social media",
    "our location", "visit us", "send us a message", "write to us",
    "copyright", "all rights reserved",
})


_SERVICE_NAME_REJECT_WORDS = frozenset({
    "process", "request", "contact", "call", "hours", "menu", "address",
    "enquire", "enquiry", "quote", "booking", "appointment",
})


def _clean_service_name(name):
    """Strip trailing colon/punctuation from a service heading."""
    name = clean_text(name)
    return name.rstrip(":").strip()


def _is_valid_service_name(name: str) -> bool:
    """Return False for names that are sentences / process descriptions / UI labels."""
    if not name:
        return False
    # Sentences or long descriptions (> 8 words)
    if len(name.split()) > 8:
        return False
    # Ends with a period → likely a sentence fragment
    if name.endswith("."):
        return False
    # Contains process / contact / navigation terms
    name_lower = name.lower()
    if any(w in name_lower for w in _SERVICE_NAME_REJECT_WORDS):
        return False
    return True


def extract_services(soup, headings, sections, base_url):
    """Extract individual service items from DOM or pre-extracted headings.

    Strategy 1: find DOM container whose h2 matches a service section pattern,
                then collect h3/h4 children as individual services.
    Strategy 2: walk the pre-extracted headings list, collect h3/h4 following
                a service-category h2.
    """
    services = []

    main = soup.select_one("main") or soup.body or soup

    # --- Strategy 1: DOM ---
    for container in main.find_all(["section", "div", "article"], limit=80):
        h2 = container.find("h2")
        if not h2 or not _SERVICE_SECTION_RE.search(h2.get_text(" ")):
            continue

        for item_h in container.find_all(["h3", "h4"]):
            name = _clean_service_name(item_h.get_text(" "))
            if not name or len(name) < 3 or len(name) > 120:
                continue
            if name.lower() in _SERVICE_SKIP_NAMES:
                continue
            if not _is_valid_service_name(name):
                continue

            # Description: adjacent siblings until next heading
            desc_parts = []
            for sib in item_h.next_siblings:
                if hasattr(sib, "name") and sib.name in ("h2", "h3", "h4"):
                    break
                if hasattr(sib, "get_text"):
                    t = clean_text(sib.get_text(" "))
                    if t and len(t) > 15 and not t.lower().startswith("image"):
                        desc_parts.append(t)
                if sum(len(d) for d in desc_parts) > 400:
                    break
            description = " ".join(desc_parts)[:400] or None

            # URL from anchor in or after heading
            link_url = None
            a = item_h.find("a", href=True)
            if not a:
                sib = item_h.find_next_sibling()
                if sib:
                    a = sib.find("a", href=True)
            if a:
                href = a.get("href", "")
                if href and not href.startswith(("#", "javascript:", "mailto:", "tel:")):
                    link_url = normalize_url(href, base_url)

            services.append({"name": name, "description": description, "url": link_url})

    if services:
        return unique_items(services, "name")[:25]

    # --- Strategy 2: headings list ---
    in_service_block = False
    for h in headings:
        h_text = h.get("text", "")
        level = h.get("level", "")

        if level == "h2" and _SERVICE_SECTION_RE.search(h_text):
            in_service_block = True
            continue

        if level == "h2":
            in_service_block = False  # New top-level heading exits block

        if not in_service_block or level not in ("h3", "h4"):
            continue

        name = _clean_service_name(h_text)
        if not name or len(name) < 3 or len(name) > 120:
            continue
        if name.lower() in _SERVICE_SKIP_NAMES:
            continue
        if not _is_valid_service_name(name):
            continue

        # Description from matching section
        description = None
        for sec in sections:
            sec_h = _clean_service_name(sec.get("heading") or "")
            if sec_h.lower() == name.lower():
                raw = sec.get("text", "")
                trimmed = re.sub(r'^' + re.escape(name) + r'[:\s]*', '', raw, flags=re.I).strip()
                if len(trimmed) > 20:
                    description = trimmed[:400]
                break

        services.append({"name": name, "description": description, "url": None})

    # Strategy 3: pages where each major service IS an h1 (e.g. Elementor layouts
    # where "Light Automation", "Fan Automation" etc. are individual h1 elements)
    if not services:
        main_h1s = [h for h in main.select("h1")
                    if not h.find_parent(["header", "nav"])]
        if len(main_h1s) > 1:
            for h1 in main_h1s:
                name = _clean_service_name(h1.get_text(" "))
                if not name or len(name) < 3 or len(name) > 120:
                    continue
                if name.lower() in _SERVICE_SKIP_NAMES:
                    continue
                if is_noise_heading(name):
                    continue
                if not _is_valid_service_name(name):
                    continue
                # Description: siblings until next h1/h2
                desc_parts = []
                for sib in h1.next_siblings:
                    if hasattr(sib, "name") and sib.name in ("h1", "h2"):
                        break
                    if hasattr(sib, "get_text"):
                        t = clean_text(sib.get_text(" "))
                        if t and len(t) > 15:
                            desc_parts.append(t)
                    if sum(len(d) for d in desc_parts) > 400:
                        break
                description = " ".join(desc_parts)[:400] or None
                services.append({"name": name, "description": description, "url": None})

    services = unique_items(services, "name")

    # Post-filter: remove single-word service names that are just a category suffix word.
    # e.g. "Automation" when "Light Automation", "Fan Automation", "Curtain Automation" exist —
    # those longer names make the bare word redundant and misleading as a service entry.
    if len(services) > 2:
        all_names_lower = [s["name"].lower() for s in services]
        _filtered = []
        for s in services:
            name_lower = s["name"].lower()
            if len(name_lower.split()) == 1:
                suffix_count = sum(
                    1 for n in all_names_lower
                    if n != name_lower and n.endswith(" " + name_lower)
                )
                if suffix_count >= 2:
                    continue  # generic category suffix, not a service
            _filtered.append(s)
        services = _filtered

    return services[:25]


def extract_service_categories(services, headings):
    """Extract service category name from the h2 heading that introduces the services block.

    E.g. "Our Cloud Management Services:" → "Cloud Management Services"
    """
    categories = []
    seen = set()

    for h in headings:
        if h.get("level") != "h2":
            continue
        name = _clean_service_name(h.get("text", ""))
        if not name or name.lower() in _SERVICE_SKIP_NAMES:
            continue
        if _INTERROGATIVE_START_RE.match(name):
            continue  # Skip questions like "What exactly are Cloud Services?"
        if not _SERVICE_SECTION_RE.search(name):
            continue  # Only extract names FROM service section headings
        # Strip leading "Our" and trailing colon to get a clean label
        clean = re.sub(r'^our\s+', '', name, flags=re.I).rstrip(":").strip()
        low = clean.lower()
        if low not in seen and len(clean) > 3:
            seen.add(low)
            categories.append(clean)

    return categories[:10]


def extract_benefits_list(soup, sections):
    """Extract benefit/USP items — short heading+description cards."""
    benefits = []

    _BENEFIT_H2_RE = re.compile(
        r'\b(?:benefits?|why\s+(?:choose|us|choose\s+us)|advantages?|'
        r'key\s+features?|what\s+you\s+get|what\s+we\s+bring|'
        r'locally\s+controlled|privacy\s+focused|encrypted)',
        re.IGNORECASE
    )

    main = soup.select_one("main") or soup.body or soup

    for container in main.find_all(["section", "div"], limit=80):
        h2 = container.find("h2")
        if not h2 or not _BENEFIT_H2_RE.search(h2.get_text(" ")):
            continue

        for card in container.find_all(["h3", "h4", "strong"], limit=20):
            name = _clean_service_name(card.get_text(" "))
            if not name or len(name) < 3 or len(name) > 80:
                continue
            if name.lower() in _SERVICE_SKIP_NAMES:
                continue
            # Only include short benefit-card items
            parent_text = clean_text(card.parent.get_text(" ")) if card.parent else ""
            if len(parent_text) > 400:
                continue
            desc = parent_text.replace(name, "", 1).strip()[:200] or None
            benefits.append({"name": name, "description": desc})

    # Fallback: extract from sections whose heading matches benefit patterns
    if not benefits:
        for sec in sections:
            heading = sec.get("heading") or ""
            if not _BENEFIT_H2_RE.search(heading):
                continue
            text = sec.get("text") or ""
            for line in re.split(r'[•·\-–]\s*|\n{2,}', text):
                v = clean_text(line)
                if 4 < len(v) < 80 and v[0].isupper() and v not in (heading,):
                    benefits.append({"name": v, "description": None})

    return unique_items(benefits, "name")[:20]


def extract_process_steps(soup, sections):
    """Extract numbered/ordered process steps (e.g. Quote → Survey → Deliver)."""
    # Guard: only proceed if the page has explicit process indicators.
    # This prevents false positives on generic service pages.
    _main_node = soup.select_one("main") or soup.body or soup
    _quick_text = clean_text(_main_node.get_text(" "))[:4000]
    _has_numbered = bool(re.search(
        r'(?:^|\s)(?:step\s+[123456789]|0[1-9]\s*[.\-–]\s+[A-Z])', _quick_text, re.I | re.M
    ))
    _has_process_heading = bool(_PROCESS_SECTION_RE.search(_quick_text))
    if not (_has_numbered or _has_process_heading):
        return []

    steps = []

    main = soup.select_one("main") or soup.body or soup

    # DOM: <ol> or process-labeled <ul> under a process heading
    _seen_titles: set = set()
    for list_node in main.find_all(["ol", "ul"], limit=8):
        prev_h = list_node.find_previous(["h2", "h3"])
        if not prev_h or not _PROCESS_SECTION_RE.search(prev_h.get_text(" ")):
            continue
        candidate_steps = []
        for i, li in enumerate(list_node.find_all("li"), 1):
            text = clean_text(li.get_text(" "))
            if not text or len(text) <= 2:
                continue
            # Split "Quote Fill out the form" → title="Quote", desc="Fill out the form"
            # Use only the FIRST word as title when it's a short CamelCase identifier
            # followed by more sentence text (capitalized or lowercase continuation).
            _first, _, _rest = text.partition(" ")
            if (len(_first) >= 3 and len(_first) <= 20 and
                    _first[0].isupper() and not _PROCESS_SECTION_RE.search(_first) and
                    len(_rest) >= 10):
                _title = _first[:80]
                _desc = _rest[:160] or None
            else:
                _title = None
                _desc = None
            if not _title:
                _m = re.match(r'^([A-Z][a-zA-Z]{1,}(?:\s+[A-Z][a-zA-Z]{1,}){0,2})\s+([a-z].{5,})', text)
                if _m and len(_m.group(1).split()) <= 3:
                    _title = _m.group(1)[:80]
                    _desc = _m.group(2)[:160] or None
                else:
                    _title = text[:80]
                    _desc = text[80:160] or None
            if _title.lower() in _seen_titles:
                continue
            _seen_titles.add(_title.lower())
            candidate_steps.append({
                "step": i,
                "title": _title,
                "description": _desc if _desc and len(_desc) > 5 else None
            })
        # Only accept if we found at least 2 items (avoid stray navigation lists)
        if len(candidate_steps) >= 2:
            steps.extend(candidate_steps)
            break

    if steps:
        return steps[:12]

    # Text pattern fallback from sections
    _seen_titles_fb: set = set()
    for sec in sections:
        heading = sec.get("heading") or ""
        text = sec.get("text") or ""
        if not _PROCESS_SECTION_RE.search(heading + " " + text[:200]):
            continue
        # Strip the section heading text from the start of the body to prevent
        # the heading words leaking into the first step title.
        scan_text = text
        if heading:
            scan_text = re.sub(r'^' + re.escape(heading) + r'\s*', '', text, flags=re.I).lstrip()
        # Numbered items: "01 Quote", "02 Survey", "03 Deliver"
        # Also short single/double-word steps without a number prefix.
        for m in re.finditer(r'(?:^|\s)(?:0?(\d+)[\s.–\-]+)?([A-Z][a-zA-Z]{1,}(?:\s+[A-Za-z]+){0,4})', scan_text):
            title = clean_text(m.group(2))
            if not title or len(title) < 3:
                continue
            if title.lower() in _SERVICE_SKIP_NAMES:
                continue
            # Don't treat the process-section heading itself as a step
            if _PROCESS_SECTION_RE.search(title):
                continue
            # Skip very long titles (likely sentences, not step names)
            if len(title.split()) > 7:
                continue
            if title.lower() in _seen_titles_fb:
                continue
            _seen_titles_fb.add(title.lower())
            n = int(m.group(1)) if m.group(1) else len(steps) + 1
            steps.append({"step": n, "title": title[:80], "description": None})
        if steps:
            break

    return steps[:12]


def extract_contact_options(soup, main_text, base_url):
    """Extract structured contact methods: phone, email, WhatsApp, form, hours."""
    options = []

    phones = re.findall(r'(?:\+?\d[\d\s().-]{7,}\d)', main_text)
    seen_digits = set()
    for phone in phones:
        digits = re.sub(r'\D', '', phone)
        if 8 <= len(digits) <= 15 and digits not in seen_digits:
            seen_digits.add(digits)
            options.append({
                "type": "phone",
                "value": clean_text(phone),
                "url": "tel:" + digits
            })

    emails_found = re.findall(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', main_text)
    seen_emails = set()
    for email in emails_found:
        if email not in seen_emails:
            seen_emails.add(email)
            options.append({"type": "email", "value": email, "url": "mailto:" + email})

    # WhatsApp links
    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        if "wa.me" in href or "whatsapp" in href.lower():
            label = clean_text(a.get_text(" ")) or "WhatsApp"
            options.append({"type": "whatsapp", "value": label, "url": href})

    # Contact form link
    seen_contact_urls = set()
    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        text = clean_text(a.get_text(" ")).lower()
        if any(k in text for k in ["contact", "get in touch", "enquire", "request"]):
            norm = normalize_url(href, base_url)
            if norm and "/contact" in norm.lower() and norm not in seen_contact_urls:
                seen_contact_urls.add(norm)
                options.append({
                    "type": "contact_form",
                    "value": clean_text(a.get_text(" ")),
                    "url": norm
                })

    # Business hours
    hours_m = re.search(
        r'\b(\d{1,2}(?:am|pm)\s*[-–]\s*\d{1,2}(?:am|pm)(?:[^.\n]{0,40})?)',
        main_text, re.IGNORECASE
    )
    if hours_m:
        options.append({"type": "hours", "value": clean_text(hours_m.group(1)), "url": None})

    # Dedupe
    seen_keys = set()
    out = []
    for opt in options:
        key = (opt["type"], (opt.get("value") or "").lower()[:40])
        if key not in seen_keys:
            seen_keys.add(key)
            out.append(opt)

    return out[:15]


# -------------------------------------------------------
# ABOUT / BRAND INTELLIGENCE
# -------------------------------------------------------

_VALUES_HEADING_RE = re.compile(
    r'\b(?:(?:our\s+)?(?:values?|principles?|philosophy|beliefs?|what\s+we\s+(?:stand\s+for|value|believe))|'
    r'core\s+values?)\b',
    re.IGNORECASE
)
_ORIGIN_HEADING_KEYWORDS = frozenset({
    "our story", "origin", "how we started", "our journey", "how it started",
    "our history", "the beginning", "our brand", "brand story", "our roots",
    "born from", "created from", "founded", "about claré", "about clare",
    "about the brand", "about us",
})
_BRAND_STORY_HEADING_KEYWORDS = frozenset({
    "who we are", "brand story", "discover us", "empowering", "our mission",
    "about the brand", "our philosophy", "meet the brand", "what we do",
})


def extract_about_intelligence(soup, sections, main_text):
    """Extract brand story, values, founder, mission, promise, positioning."""
    result = {
        "brandStory": None,
        "brandValues": [],
        "founder": None,
        "mission": None,
        "promise": None,
        "positioning": None,
        "originStory": None,
    }

    # ---- MISSION ----
    mission_m = re.search(
        r'(?:our\s+)?mission[:\s]+(.{20,400}?)(?:[.!]\s|\n|$)',
        main_text, re.IGNORECASE | re.DOTALL
    )
    if mission_m:
        result["mission"] = clean_text(mission_m.group(1))[:300]

    # ---- PROMISE / VISION ----
    # 1. Explicit label
    promise_m = re.search(
        r'(?:our\s+)?(?:vision|promise|commitment|tagline|slogan|motto)[:\s]+(.{15,300}?)(?:[.!]\s|\n|$)',
        main_text, re.IGNORECASE | re.DOTALL
    )
    if promise_m:
        result["promise"] = clean_text(promise_m.group(1))[:300]
    # 2. Quoted tagline ("Brand is …")
    if not result["promise"]:
        quote_m = re.search(r'[""„]([A-Z][^"""„]{15,180}?)["""]', main_text)
        if quote_m:
            result["promise"] = clean_text(quote_m.group(1))[:300]

    # ---- SECTIONS ----
    for sec in sections:
        heading = (sec.get("heading") or "").lower()
        text = clean_text(sec.get("text") or "")
        if not text:
            continue

        if "mission" in heading and not result["mission"]:
            result["mission"] = text[:300]

        if any(k in heading for k in ["vision", "promise", "commitment"]) and not result["promise"]:
            result["promise"] = text[:300]

        if any(k in heading for k in _ORIGIN_HEADING_KEYWORDS) and not result["originStory"]:
            result["originStory"] = text[:500]

        if any(k in heading for k in _BRAND_STORY_HEADING_KEYWORDS) and not result["brandStory"]:
            result["brandStory"] = text[:500]

    # ---- ORIGIN STORY — text regex fallback ----
    if not result["originStory"]:
        origin_m = re.search(
            r'(?:created\s+from|born\s+from|inspired\s+by|originated\s+from|built\s+from)'
            r'\s+(.{10,200}?)(?:[.!]\n|$)',
            main_text, re.IGNORECASE
        )
        if origin_m:
            result["originStory"] = clean_text(origin_m.group(0))[:300]

    # ---- FOUNDER ----
    # Pattern 1: "founded by Name" / "co-founder Name" / "CEO Name"
    founder_m = re.search(
        r'(?:founded\s+by|co-?founder[s]?[:\s]+|ceo[:\s]+|creator[:\s]+)'
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})',
        main_text
    )
    if founder_m:
        result["founder"] = clean_text(founder_m.group(1))

    # Pattern 2: "Name, Founder" / "Name - Founder" / "Name – brand founder"
    if not result["founder"]:
        founder_m2 = re.search(
            r'([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,}){1,3})'
            r'[,\s\-–]+(?:\w+\s+)?(?:founder|creator|ceo|owner|co-founder|established\s+by)',
            main_text, re.IGNORECASE
        )
        if founder_m2:
            result["founder"] = clean_text(founder_m2.group(1))

    # Pattern 3: "by Name in YEAR" or "by Name," near the start of the text
    if not result["founder"]:
        founder_m3 = re.search(
            r'\bby\s+([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,}){1,2})'
            r'(?:\s+in\s+\d{4}|[,.])',
            main_text
        )
        if founder_m3:
            result["founder"] = clean_text(founder_m3.group(1))

    # ---- BRAND VALUES ----
    # Strategy 1: DOM — find values section, collect h3/h4/li/strong items
    main = soup.select_one("main") or soup.body or soup
    for container in main.find_all(["section", "div"], limit=80):
        h = container.find(["h2", "h3"])
        if not h or not _VALUES_HEADING_RE.search(h.get_text(" ")):
            continue
        for item in container.find_all(["h3", "h4", "li", "strong"], limit=30):
            v = clean_text(item.get_text(" "))
            # Typical brand values are short (1-4 words, ≤40 chars)
            if 3 < len(v) < 60 and v.lower() not in _SERVICE_SKIP_NAMES and v not in result["brandValues"]:
                result["brandValues"].append(v)
        if result["brandValues"]:
            break  # found the values block

    # Strategy 2: Text regex — bullet/newline-split after values keyword
    if not result["brandValues"]:
        values_m = re.search(
            r'(?:our\s+values?|we\s+believe|core\s+values?|our\s+principles?)[:\s]+'
            r'(.{20,600}?)(?:\n{2,}|$)',
            main_text, re.IGNORECASE | re.DOTALL
        )
        if values_m:
            for item in re.split(r'[•·\-–]\s*|\n', values_m.group(1)):
                v = clean_text(item)
                if 3 < len(v) < 60 and v not in result["brandValues"]:
                    result["brandValues"].append(v)

    # Strategy 3: keyword scan — catch explicit value words that appear on the page
    # even when they aren't inside a dedicated "values" DOM block or regex block.
    _KNOWN_VALUE_TERMS = [
        "honesty", "authenticity", "authentique", "quality", "openness",
        "effectiveness", "efficacy", "transparency", "sustainability",
        "innovation", "integrity", "excellence", "responsibility",
        "compassion", "inclusion", "inclusivity", "diversity",
        "creativity", "simplicity", "reliability", "trust", "trustworthy",
        "passion", "respect", "courage", "accountability", "empathy",
    ]
    if len(result["brandValues"]) < 3:
        for term in _KNOWN_VALUE_TERMS:
            if re.search(r'\b' + re.escape(term) + r'\b', main_text, re.I):
                if term not in [v.lower() for v in result["brandValues"]]:
                    result["brandValues"].append(term)

    result["brandValues"] = result["brandValues"][:12]

    # ---- POSITIONING — H1, then meta description, then OG description ----
    h1_node = soup.select_one("h1")
    h1 = clean_text(h1_node.get_text(" ")) if h1_node else None
    meta_desc_tag = soup.select_one("meta[name='description']")
    meta_text = clean_text(meta_desc_tag.get("content") or "") if meta_desc_tag else None
    og_desc_tag = soup.select_one("meta[property='og:description']")
    og_desc = clean_text(og_desc_tag.get("content") or "") if og_desc_tag else None

    if h1 and len(h1) > 10:
        result["positioning"] = h1[:200]
    elif meta_text and len(meta_text) > 20:
        result["positioning"] = meta_text[:200]
    elif og_desc and len(og_desc) > 20:
        result["positioning"] = og_desc[:200]

    return result


# -------------------------------------------------------
# CONSUMER BRAND PRODUCT CATALOG
# -------------------------------------------------------

def _is_consumer_brand_catalog_html(soup, main_text, url):
    """Return True when Jina HTML shows a brand product listing with no ecommerce."""
    # No cart intent
    if _NO_CART_RE.search(main_text):
        return False
    # No prices
    if PRICE_REGEX.search(main_text):
        return False
    # Multiple size/weight mentions
    sizes = _SIZE_WEIGHT_RE.findall(main_text)
    if len(sizes) < 2:
        return False
    # Multiple h3 product sections
    h3s = soup.find_all("h3")
    if len(h3s) < 3:
        return False
    # URL must suggest a product context
    path = (urlparse(url or "").path or "").lower()
    if not any(k in path for k in ["/product", "/our-product", "/shop", "/range",
                                    "/lineup", "/catalog", "/range"]):
        return False
    return True


def extract_retail_partners(soup, main_text):
    """Extract retailer names mentioned near 'available at / find us at / exclusively through'."""
    partners = []
    patterns = [
        r'(?:available\s+(?:at|in|through)|find\s+us\s+(?:at|in)|exclusively\s+(?:at|through|available\s+at)|sold\s+(?:at|in|through)|carried\s+(?:at|by))\s*[:\-–]?\s*([A-Z][A-Za-z\x27&\s,]+?)(?:\.|,\s*and\s*more|$)',
        r'(?:our\s+retail(?:er)?\s+partner[s]?|select\s+retailer[s]?)\s*[:\-–]?\s*([A-Z][A-Za-z\x27&\s,]+?)(?:\.|$)',
    ]
    seen = set()
    for pat in patterns:
        for m in re.finditer(pat, main_text, re.I | re.M):
            raw = m.group(1).strip()
            # Split on commas / " and "
            for part in re.split(r',\s*|\s+and\s+', raw):
                name = clean_text(part).strip().rstrip(".")
                if name and 2 <= len(name) <= 60 and name.lower() not in seen:
                    seen.add(name.lower())
                    partners.append(name)
    # Also scan for known major retailers explicitly mentioned
    _KNOWN_RETAILERS = [
        "Costco", "Walmart", "Whole Foods", "Sobeys", "Loblaws", "Metro",
        "Safeway", "Kroger", "Trader Joe's", "Target", "IGA", "FreshCo",
        "Longos", "Thrifty Foods", "Save-On-Foods",
    ]
    text_lower = main_text.lower()
    for r in _KNOWN_RETAILERS:
        if r.lower() in text_lower and r not in partners:
            partners.append(r)
    return partners[:10]


def extract_brand_claims(soup, main_text):
    """Extract quality / certification claims common on consumer brand pages."""
    claims = []
    _CLAIM_PATTERNS = [
        r'\b(?:greenhouse[\-\s]grown|field[\-\s]grown|locally[\-\s]grown|organically[\-\s]grown)\b',
        r'\bnon[\-\s]?gmo\b',
        r'\bpesticide[\-\s]free\b',
        r'\bherbicide[\-\s]free\b',
        r'\bsustainably[\-\s]grown\b',
        r'\bsustainably[\-\s]sourced\b',
        r'\bwhole[\-\s]?30\s+approved\b',
        r'\bUSDA\s+organic\b',
        r'\bcertified\s+organic\b',
        r'\bkosher\b',
        r'\bgluten[\-\s]free\b',
        r'\bvegan\b',
        r'\bnon[\-\s]dairy\b',
        r'\bfarm[\-\s]fresh\b',
        r'\bwashed\s+ready[\-\s]to[\-\s]eat\b',
        r'\bready[\-\s]to[\-\s]eat\b',
    ]
    seen = set()
    for pat in _CLAIM_PATTERNS:
        m = re.search(pat, main_text, re.I)
        if m:
            norm = re.sub(r'\s+', '-', m.group(0).strip().lower())
            norm = re.sub(r'-+', '-', norm)
            if norm not in seen:
                seen.add(norm)
                claims.append(norm)
    return sorted(claims)


def extract_consumer_brand_catalog(soup, url):
    """Extract product cards from Jina-style HTML with alternating name/size sections.

    Pattern in Haven Greens Jina HTML:
        <section><h3>baby green leaf - pousses vertes</h3></section>
        <section><h3>113g & 226g</h3><p>Delicate, crisp...</p><img ...></section>
    """
    products = []

    _NOISE_HEADINGS = frozenset({
        "testimonials", "frequently asked questions", "faqs",
        "available exclusively through retailers!", "fresh. clean. locally grown.",
    })

    pending_name = None
    pending_image = None

    for sec in soup.find_all("section"):
        h3 = sec.find("h3")
        if not h3:
            continue
        text = clean_text(h3.get_text(" "))
        if not text:
            continue

        # Size/weight-only heading (pairs with previous product name)
        if pending_name and _SIZE_WEIGHT_RE.search(text) and re.match(r'^\d', text):
            desc_parts = []
            for p in sec.find_all("p"):
                p_text = clean_text(p.get_text(" "))
                if p_text and not p_text.lower().startswith("image"):
                    desc_parts.append(p_text)
            description = " ".join(desc_parts)[:400] or None

            img = sec.find("img")
            image_url = None
            if img:
                src = img.get("src") or img.get("data-src") or ""
                if src:
                    image_url = normalize_url(src, url)

            products.append({
                "name": pending_name,
                "sizes": text,
                "description": description,
                "imageUrl": image_url or pending_image,
            })
            pending_name = None
            pending_image = None
            continue

        # Noise / skip
        if text.lower() in _NOISE_HEADINGS:
            pending_name = None
            pending_image = None
            continue

        # New product name
        img = sec.find("img")
        pending_image = normalize_url(img.get("src", ""), url) if img else None
        pending_name = text

    # Fallback: sections where description lives in a different section from size
    # (catch Trillium Blend pattern: name section followed by size section with long desc)
    if not products:
        # Re-run with looser pairing — accept any h3 that's not a size heading as a name
        all_sections = soup.find_all("section")
        i = 0
        while i < len(all_sections):
            sec = all_sections[i]
            h3 = sec.find("h3")
            if not h3:
                i += 1
                continue
            name = clean_text(h3.get_text(" "))
            if name.lower() in _NOISE_HEADINGS or not name:
                i += 1
                continue
            # Look ahead for description
            desc = None
            sizes = None
            img_url = None
            if i + 1 < len(all_sections):
                next_sec = all_sections[i + 1]
                next_h3 = next_sec.find("h3")
                if next_h3:
                    next_text = clean_text(next_h3.get_text(" "))
                    if _SIZE_WEIGHT_RE.search(next_text):
                        sizes = next_text
                        ps = [clean_text(p.get_text(" ")) for p in next_sec.find_all("p")]
                        desc = " ".join(p for p in ps if p and not p.lower().startswith("image"))[:400]
                        img_node = next_sec.find("img")
                        if img_node:
                            img_url = normalize_url(img_node.get("src", ""), url)
                        i += 2
                        products.append({
                            "name": name,
                            "sizes": sizes,
                            "description": desc or None,
                            "imageUrl": img_url,
                        })
                        continue
            i += 1

    return products[:30]


# -----------------------------
# CONTACT / FAQ / POLICY
# -----------------------------

def extract_contact_details(soup):
    text = clean_text(soup.get_text(" "))

    emails = re.findall(
        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
        text
    )

    raw_phones = re.findall(
        r"(?:\+?\d[\d\s().-]{7,}\d)",
        text
    )

    phones = []
    for phone in raw_phones:
        cleaned = clean_text(phone)
        digits = re.sub(r"\D", "", cleaned)

        if 8 <= len(digits) <= 15 and not re.search(r"\b\d+\s+\d+\s+\d+\s+\d+", cleaned):
            phones.append(cleaned)

    return {
        "emails": list(dict.fromkeys(emails))[:10],
        "phones": list(dict.fromkeys(phones))[:10]
    }


_FAQ_Q_RE = re.compile(
    r'^(?:what|how|can|do|does|is|are|will|where|when|why|which|who)\b.{10,}[?]$',
    re.I
)


def _extract_faqs_from_nodes(faq_nodes):
    faqs = []
    for node in faq_nodes:
        text = clean_text(node.get_text(" "))
        if len(text) < 30:
            continue
        q = node.select_one(".schema-faq-question, summary, h3, h4, button")
        if q:
            question = clean_text(q.get_text(" "))
        else:
            continue
        if not question:
            continue
        q_low = question.lower()
        if q_low in PLAN_BAD_NAMES or q_low in ["create", "manage", "optimize", "free", "essential pro"]:
            continue
        if not ("?" in question or q_low.startswith(("what", "how", "can", "do", "is", "are", "will", "where", "when", "why"))):
            continue
        answer = text.replace(question, "", 1).strip()
        if question and answer and len(answer) >= 20:
            faqs.append({"question": question[:250], "answer": answer[:1000]})
    return faqs


def _extract_faqs_from_text(soup, main_text):
    """Text-based FAQ fallback: find the FAQ section heading, then parse Q&A pairs.

    Handles accordion-based FAQ sections (Elementor, Gravity Forms, etc.) where
    the CSS selectors don't match but the text is present in the page.
    """
    faqs = []
    # Find the FAQ section in the soup via heading text
    faq_heading = None
    for tag in soup.find_all(["h2", "h3", "h4"]):
        t = clean_text(tag.get_text(" ")).lower()
        if t in ("faq", "faqs", "frequently asked questions", "frequently asked questions."):
            faq_heading = tag
            break

    if faq_heading:
        # Collect sibling/descendant text from the FAQ container
        container = faq_heading.parent
        # Walk up if the container is very small (just the heading)
        for _ in range(3):
            if container and len(clean_text(container.get_text(" "))) < 200:
                container = container.parent
        faq_text = clean_text(container.get_text(" ")) if container else ""
    else:
        # Fallback: look for "faq" or "frequently asked questions" region in main_text
        m = re.search(r'\b(?:FAQ|Frequently Asked Questions)\.?\b', main_text, re.I)
        if not m:
            return faqs
        faq_text = main_text[m.start():][:4000]

    # Split on "?" boundaries to find question–answer pairs
    # Pattern: a question-like sentence ending in "?", followed by answer text
    # We split the FAQ text into sentences ending in "?" and collect pairs
    qa_re = re.compile(r'([A-Z][^?]{10,200}\?)\s*([^?]{20,800}?)(?=(?:[A-Z][^?]{10,}?[?])|$)', re.S)
    for m in qa_re.finditer(faq_text):
        question = clean_text(m.group(1))
        answer = clean_text(m.group(2))
        if not question or not answer:
            continue
        q_low = question.lower()
        if not q_low.startswith(("what", "how", "can", "do", "does", "is", "are", "will", "where", "when", "why", "which", "who")):
            continue
        if len(answer) < 15:
            continue
        faqs.append({"question": question[:250], "answer": answer[:1000]})
        if len(faqs) >= 20:
            break

    return faqs


def extract_faqs(soup, main_text=None):
    # Primary: CSS-selector-based extraction (schema markup, details/summary, .faq classes)
    faq_nodes = soup.select(
        ".faq, .schema-faq-section, [class*='faq'], details, "
        "[class*='accordion'], [class*='elementor-accordion'], [class*='toggle']"
    )
    faqs = _extract_faqs_from_nodes(faq_nodes)

    # Fallback: text-based extraction when no structured nodes found
    if not faqs and main_text:
        faqs = _extract_faqs_from_text(soup, main_text)

    return unique_items(faqs, "question")[:30]


def detect_policy_signals(text):
    text_lower = (text or "").lower()

    return {
        "hasPrivacyLanguage": any(k in text_lower for k in [
            "personal data", "privacy", "gdpr", "cookies", "data controller", "ccpa"
        ]),
        "hasReturnsLanguage": any(k in text_lower for k in [
            "return", "refund", "exchange", "shipping", "delivery", "money-back"
        ]),
        "hasLegalLanguage": any(k in text_lower for k in [
            "terms", "conditions", "liability", "agreement", "compliance"
        ])
    }


# -----------------------------
# MAIN ANALYZER
# -----------------------------

def analyze_general(self, url, html, headers, page_type, level1):
    result = self.base_result(
        url,
        html,
        headers,
        page_type,
        level1
    )

    raw_soup = BeautifulSoup(html or "", "lxml")
    content_soup = clean_dom_for_general(html)

    result["source"]["extractor"] = "WordPress General Page Extractor"

    seo = extract_basic_seo(raw_soup, url)
    open_graph = extract_open_graph(raw_soup)
    json_ld_items = extract_json_ld_items(raw_soup)

    main_text = clean_text(content_soup.get_text(" "))

    general_subtype = get_level1_subtype(level1)

    if general_subtype:
        general_page_type = general_subtype
    else:
        general_page_type = classify_general_page(url, seo, main_text)

    sections = extract_general_sections(content_soup)
    headings = extract_headings(content_soup)
    links = extract_links(content_soup, url)
    images = extract_images(content_soup, url)
    ctas = extract_ctas(content_soup, url)

    pricing_data = extract_pricing_data(
        content_soup,
        main_text,
        sections=sections,
        headings=headings
    )

    if general_subtype:
        general_page_type = general_subtype
    elif pricing_data.get("hasPricing") and (
        pricing_data.get("plans")
        or pricing_data.get("pricingComponents")
        or len(pricing_data.get("priceMentions") or []) >= 2
    ):
        general_page_type = "pricing"

    # On pricing pages, rebuild sections directly from H2 DOM nodes.
    # This is more reliable than filtering the extracted sections list because
    # the general section extractor often drops H2s whose body text is short,
    # discount-flagged, or otherwise noisy — losing real pricing page headings.
    if general_page_type == "pricing":
        _pricing_sections = []
        _seen_headings = set()
        for _h2 in content_soup.find_all("h2"):
            if _h2.find_parent(["header", "nav", "footer"]):
                continue
            _heading = clean_text(_h2.get_text(" "))
            if not _heading or is_noise_heading(_heading):
                continue
            _key = _heading.lower()
            if _key in _seen_headings:
                continue
            _seen_headings.add(_key)
            # Collect sibling content until next H1/H2
            _parts = []
            for _sib in _h2.next_siblings:
                if hasattr(_sib, "name") and _sib.name in ("h1", "h2"):
                    break
                if hasattr(_sib, "get_text"):
                    _t = clean_text(_sib.get_text(" "))
                    if _t and len(_t) > 10:
                        _parts.append(_t)
                if sum(len(_p) for _p in _parts) > 600:
                    break
            _body = " ".join(_parts)[:600] or _heading
            _pricing_sections.append({"heading": _heading, "text": _body})
        sections = _pricing_sections

    saas_data = extract_saas_signals(
        general_page_type,
        main_text,
        ctas,
        pricing_data=pricing_data
    )

    contact = extract_contact_details(content_soup)
    faqs = extract_faqs(content_soup, main_text=main_text)
    policy_signals = detect_policy_signals(main_text)

    # --- Service page extraction ---
    services_data = None
    if general_page_type in ("service_page", "general", "features", "landing_page", "homepage"):
        extracted_services = extract_services(content_soup, headings, sections, url)
        if extracted_services:
            services_data = {
                "services": extracted_services,
                "serviceCategories": extract_service_categories(extracted_services, headings),
                "benefits": extract_benefits_list(content_soup, sections),
                "processSteps": extract_process_steps(content_soup, sections),
                "contactOptions": extract_contact_options(content_soup, main_text, url),
            }

    # --- About / brand intelligence ---
    about_data = None
    if general_page_type in ("about", "general"):
        about_data = extract_about_intelligence(content_soup, sections, main_text)
        # Only keep if at least something was extracted
        if not any(about_data.get(k) for k in ("brandStory", "mission", "promise",
                                                 "founder", "originStory")):
            about_data = None

    # --- Consumer brand product catalog ---
    product_catalog = None
    if (
        general_page_type == "consumer_brand_products"
        or general_subtype == "consumer_brand_products"
        or _is_consumer_brand_catalog_html(content_soup, main_text, url)
    ):
        general_page_type = "consumer_brand_products"
        catalog_items = extract_consumer_brand_catalog(raw_soup, url)
        retail_partners = extract_retail_partners(content_soup, main_text)
        brand_claims = extract_brand_claims(content_soup, main_text)
        product_catalog = {
            "products": catalog_items,
            "productCount": len(catalog_items),
            "hasPrices": False,
            "hasCart": False,
            "distributionModel": "retail_only" if "retailer" in main_text.lower() else "unknown",
            "retailPartners": retail_partners or None,
            "brandClaims": brand_claims or None,
        }

    result["seo"] = seo
    result["openGraph"] = open_graph

    result["generalPage"] = {
        "type": general_page_type,
        "subtype": general_page_type,
        "title": (
            seo.get("h1")
            or open_graph.get("title")
            or seo.get("title")
        ),
        "pricing": pricing_data,
        "saas": saas_data,
        "sections": sections,
        "headings": headings,
        "ctas": ctas,
        "links": links,
        "images": images,
        "contact": contact,
        "faqs": faqs,
        "policySignals": policy_signals,
        "servicePage": services_data,
        "about": about_data,
        "productCatalog": product_catalog,
    }

    result["content"] = {
        "pageTitle": result["generalPage"]["title"],
        "mainText": main_text[:20000],
        "sections": sections,
        "headings": headings,
        "ctas": ctas
    }

    result["structuredData"] = {
        "jsonLdCount": len(json_ld_items),
        "items": json_ld_items[:20]
    }

    result["pricing"] = pricing_data
    result["saas"] = saas_data

    confidence = 0.45

    if result["generalPage"]["title"]:
        confidence += 0.15

    if len(main_text) >= 400:
        confidence += 0.15

    if sections:
        confidence += 0.10

    if headings:
        confidence += 0.05

    if pricing_data.get("hasPricing"):
        confidence += 0.05

    if contact.get("emails") or contact.get("phones"):
        confidence += 0.03

    if faqs:
        confidence += 0.03

    result["source"]["confidence"] = round(
        min(max(confidence, 0.35), 0.98),
        2
    )

    # G-F1: expose canonical products path consistent with other platforms
    result["products"] = []

    return result
