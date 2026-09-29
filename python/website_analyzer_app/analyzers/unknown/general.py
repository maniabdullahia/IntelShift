
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin


def clean_text(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


# ---------------------------------------------------------------------------
# Collection mis-routing guard
# ---------------------------------------------------------------------------

def _has_strong_collection_evidence(level1):
    """
    Return True when level1 debug shows overwhelming collection evidence that
    should prevent general.py from treating the page as a general page.

    This fixes the Under Armour /c/mens/hoodies bug where 'About Under Armour'
    in the footer triggered generalSubtype='about' in page_type_detector, which
    hard-stopped the routing to general even though the page is a product listing.
    """
    if not level1:
        return False
    debug = level1.get("pageTypeDebug") or {}
    signals_block = (debug.get("signals") or {}).get("collection") or {}
    coll_signals = signals_block.get("signals") or []
    metrics = signals_block.get("metrics") or {}
    score = signals_block.get("score", 0)

    has_grid = metrics.get("hasProductGrid", False)
    product_links = metrics.get("productLinkCount", 0)
    price_texts = metrics.get("priceTextCount", 0)

    strong_dom = (
        "product_grid_dom" in coll_signals
        or "sort_filter_dom" in coll_signals
        or "filter_sort_ui" in coll_signals
        or "multiple_product_links" in coll_signals
    )

    return (
        (has_grid and score >= 5)
        or (product_links >= 8 and price_texts >= 8)
        or (strong_dom and score >= 8)
        or ("text_result_count" in coll_signals and product_links >= 5)
        or ("high_product_link_density" in coll_signals and price_texts >= 6)
    )


# ---------------------------------------------------------------------------
# Blocked / empty-shell content guard
# ---------------------------------------------------------------------------

_GEN_BLOCKED_TITLE_RE = re.compile(
    r'\b(?:access\s+denied|access\s+forbidden|you\s+don\'?t\s+have\s+permission'
    r'|just\s+a\s+moment|robot\s+or\s+human|checking\s+your\s+browser'
    r'|security\s+check|please\s+enable\s+javascript|enable\s+cookies'
    r'|403\s+forbidden|404\s+not\s+found|too\s+many\s+requests'
    r'|rate\s+limit|service\s+unavailable|gateway\s+timeout)\b',
    re.I,
)

_GEN_BLOCKED_BODY_RE = re.compile(
    r'(?:'
    r'"message"\s*:\s*"Bad\s+Request"'
    r'|"errorCode"\s*:\s*"GE\d+'
    r'|errors\.edgesuite\.net'
    r'|ak_bmsc'
    r'|_abck='
    r'|Unable\s+to\s+give\s+you\s+access'
    r'|DDoS\s+protection\s+by'
    r'|verify\s+that\s+you\'?re?\s+human'
    r')',
    re.I,
)


def _detect_blocked_general(html, url, soup):
    """
    Returns (is_blocked, blocked_reason, intended_page_type).
    Mirrors collection.py's detect_blocked_or_unusable_content but for general pages.
    """
    html_s = html or ""

    # Infer intended page type from URL
    url_l = (url or "").lower().split("?")[0].split("#")[0]
    if any(x in url_l for x in ["/c/", "/collections/", "/category/", "/shop/", "/w/", "/best-sellers", "/sale"]):
        intended = "collection"
    elif any(x in url_l for x in ["/women", "/men", "/kids", "/woman-", "/man-"]):
        intended = "category_landing"
    else:
        intended = "general"

    if not html_s.strip():
        return True, "empty_shell", intended

    head_chunk = html_s[:4000]
    if _GEN_BLOCKED_BODY_RE.search(head_chunk):
        if '"message"' in head_chunk and '"errorCode"' in head_chunk:
            return True, "bad_request", intended
        return True, "bot_protection", intended

    title_text = ""
    if soup and soup.title and soup.title.string:
        title_text = clean_text(soup.title.string)

    h1_tag = soup.find("h1") if soup else None
    h1_text = clean_text(h1_tag.get_text(" ", strip=True)) if h1_tag else ""

    if title_text and title_text.strip().startswith("{"):
        return True, "json_error", intended

    check_text = f"{title_text} {h1_text}".strip()
    if check_text and _GEN_BLOCKED_TITLE_RE.search(check_text):
        reason = "access_denied" if ("denied" in check_text.lower() or "permission" in check_text.lower()) else "bot_protection"
        return True, reason, intended

    body_text = clean_text(soup.get_text(" ", strip=True)) if soup else ""
    has_title = bool(title_text and len(title_text) > 3 and not title_text.startswith("{"))
    has_h1 = bool(h1_text and len(h1_text) > 3)
    has_body = bool(body_text and len(body_text) > 80)
    has_links = bool(soup and soup.find("a", href=True))

    if not has_title and not has_h1 and not has_body and not has_links:
        return True, "empty_shell", intended

    if len(body_text) < 120 and not has_h1:
        return True, "empty_shell", intended

    return False, None, intended


# ---------------------------------------------------------------------------
# Product-family landing region scoping (Samsung, Apple, Sonos, etc.)
# ---------------------------------------------------------------------------

# Headings/phrases that mark the START of noise regions (global nav, footer, etc.)
_REGION_NOISE_STARTS = [
    "shop by category", "for business", "sign in", "create account",
    "your cart", "order help", "register a product", "product registration",
    "support home", "contact us", "live chat", "our products",
    "sitemap", "privacy policy", "terms of use", "cookie settings",
    "customer service", "accessibility", "careers", "investor",
    "follow us", "stay connected", "footer",
]

# Image URL fragments that indicate GNB/nav/support imagery (not product images)
_GNB_IMAGE_TERMS = [
    "/gnb/", "gnb-", "nav-icon", "navicon", "menu-icon",
    "order-help", "register-product", "support-icon", "account-icon",
    "appliance", "refrigerator", "washer", "dryer", "/tv/", "/monitor/",
    "teads", "tracking", "pixel", "1x1",
]

# CTA text that is support/account noise on product-family pages
_PFL_REJECT_CTA_TERMS = [
    "contact us", "order help", "support home", "register a product",
    "product registration", "product help", "appliance offers",
    "monitor buying guide", "tv buying guide", "home appliance",
    "for business", "sign in", "create account", "find a store",
    "store locator", "accessibility", "careers", "investor",
    # Apple store / shopping utility noise
    "shopping help", "shop for k-12", "shop for college", "shop for veterans",
    "shop for state", "shop for federal", "contact apple", "apple books",
    "order status", "gift cards", "apple trade in", "apple store account",
    "apple store app", "apple camp", "genius bar", "today at apple",
    "certified refurbished", "carrier deals", "apple and business",
    "apple and healthcare", "apple and government", "united states",
    "privacy policy", "terms of use", "sales and refunds", "site map",
]


def _extract_product_family_region(text, url):
    """
    Scope a product-family landing page's text to the main content region,
    cutting out global nav and footer noise.

    Heuristic: find the first noise-start keyword and truncate there.
    Works well for Samsung /smartphones/, Apple /ipad/, Sonos /shop.
    """
    if not text:
        return text

    text_l = text.lower()
    cut_pos = len(text)

    for noise in _REGION_NOISE_STARTS:
        pos = text_l.find(noise)
        if pos > 200:  # ignore if noise appears too early (i.e. it IS the content)
            cut_pos = min(cut_pos, pos)

    return text[:cut_pos].strip()


def _filter_images_for_product_family(images, url):
    """Remove GNB/nav/support/off-category images from product-family landing output."""
    url_l = (url or "").lower()
    filtered = []
    for img in images:
        img_url = (img.get("url") or "").lower()
        if any(t in img_url for t in _GNB_IMAGE_TERMS):
            continue
        filtered.append(img)
    return filtered


def _filter_ctas_for_product_family(ctas, url):
    """Remove support/account/unrelated CTAs from product-family landing output."""
    filtered = []
    for cta in ctas:
        text_l = (cta.get("text") or "").lower()
        if any(t in text_l for t in _PFL_REJECT_CTA_TERMS):
            continue
        filtered.append(cta)
    return filtered


def unique_by_url(items):
    seen = set()
    output = []

    for item in items:
        url = item.get("url")
        text = clean_text(item.get("text"))

        key = (url or "").strip().lower()

        if not key:
            key = text.lower()

        if not key or key in seen:
            continue

        seen.add(key)
        output.append(item)

    return output


def normalize_cta_text(text):
    text = clean_text(text)
    text_l = text.lower()

    replacements = {
        "sign in": "Sign In",
        "sign up": "Sign Up",
        "get started": "Get Started",
        "try for free": "Try for Free",
        "start free trial": "Start Free Trial",
        "request a demo": "Request a Demo",
        "request demo": "Request Demo",
        "talk to sales": "Talk to Sales",
        "contact sales": "Contact Sales",
        "contact us": "Contact Us",
        "subscribe": "Subscribe",
        "download": "Download",
        "get pro": "Get Pro",
        "get teams": "Get Teams",
    }

    for key, value in replacements.items():
        if text_l == key:
            return value

    return text[:90]



def score_cta(text, url=None):
    """
    Rank conversion-focused CTAs above navigation/resource links.
    Higher score = more important for competitor analysis.
    """
    text_l = clean_text(text).lower()
    url_l = (url or "").lower()
    score = 0

    high_priority_exact = {
        "get started": 100,
        "try for free": 98,
        "start free trial": 98,
        "sign up": 95,
        "subscribe": 95,
        "request a demo": 94,
        "request demo": 94,
        "talk to sales": 92,
        "contact sales": 92,
        "get pro": 90,
        "get teams": 90,
        "download": 75,
        "contact us": 70,
        "learn more": 55,
        "learn more ↗": 55,
    }

    if text_l in high_priority_exact:
        score += high_priority_exact[text_l]

    high_priority_contains = [
        "get started",
        "try",
        "free trial",
        "sign up",
        "subscribe",
        "request demo",
        "request a demo",
        "talk to sales",
        "contact sales",
        "contact us",
        "get pro",
        "get team",
        "download",
    ]

    for term in high_priority_contains:
        if term in text_l:
            score += 35
            break

    if any(x in url_l for x in ["signup", "subscribe", "checkout", "contact-sales", "request-demo", "download"]):
        score += 25

    low_priority_terms = [
        "workshops",
        "blog",
        "docs",
        "academy",
        "learn ↗",
        "forum",
        "careers",
        "status",
        "privacy",
        "terms",
        "security",
        "community",
    ]

    if any(term in text_l for term in low_priority_terms):
        score -= 40

    return score


def rank_ctas(ctas, limit=30):
    ranked = []
    seen_text = set()

    for cta in ctas or []:
        text = normalize_cta_text(cta.get("text"))
        url = cta.get("url")

        if not text:
            continue

        key = text.lower()

        # Keep only one CTA per label unless the label has very different intent.
        if key in seen_text:
            continue

        seen_text.add(key)
        ranked.append({
            "text": text,
            "url": url,
            "_score": score_cta(text, url)
        })

    ranked.sort(key=lambda item: item.get("_score", 0), reverse=True)

    output = []
    for item in ranked[:limit]:
        item.pop("_score", None)
        output.append(item)

    return output


def get_meta(soup, name=None, property_name=None):
    if name:
        tag = soup.find("meta", attrs={"name": name})
        if tag:
            return clean_text(tag.get("content"))

    if property_name:
        tag = soup.find("meta", attrs={"property": property_name})
        if tag:
            return clean_text(tag.get("content"))

    return None


def extract_headings(soup):
    headings = []

    for tag_name in ["h1", "h2", "h3"]:
        for tag in soup.find_all(tag_name):
            text = clean_text(tag.get_text(" ", strip=True))
            text = text.replace("↓ ↑", "").strip()

            if text and 2 <= len(text) <= 160:
                headings.append({
                    "level": tag_name,
                    "text": text
                })

    return headings[:100]


def extract_main_text(soup):
    soup_copy = BeautifulSoup(str(soup), "lxml")

    for bad in soup_copy(["script", "style", "noscript", "svg"]):
        bad.decompose()

    candidates = []

    selectors = [
        "main",
        "article",
        "[role='main']",
        ".content",
        ".page-content",
        ".main-content",
        ".article-content",
        ".post-content",
        ".entry-content"
    ]

    for selector in selectors:
        block = soup_copy.select_one(selector)

        if block:
            text = clean_text(block.get_text(" ", strip=True))

            if len(text) > 120:
                candidates.append(text)

    if candidates:
        candidates.sort(key=len, reverse=True)
        return candidates[0][:12000]

    body = soup_copy.find("body")

    if body:
        return clean_text(body.get_text(" ", strip=True))[:12000]

    return clean_text(soup_copy.get_text(" ", strip=True))[:12000]


def extract_links(soup, base_url):
    links = []

    bad_terms = [
        "mailto:",
        "tel:",
        "javascript:",
        "#"
    ]

    for a in soup.find_all("a", href=True):
        text = clean_text(a.get_text(" ", strip=True))
        href = a.get("href")

        if not text or len(text) > 140:
            continue

        href_l = href.lower()

        if any(x in href_l for x in bad_terms):
            continue

        links.append({
            "text": text,
            "url": urljoin(base_url, href).split("#")[0]
        })

    return unique_by_url(links)[:150]


# CTA texts that are utility/footer/FAQ links — not conversion actions.
_CTA_REJECT_EXACT_TEXTS = {
    "apply today.", "apply today", "eligibility requirements.", "eligibility requirements",
    "payment options.", "payment options", "reach out", "not-for-profits",
    "k-12 educational organizations", "canva campus", "other retailer",
    # Punctuated / non-primary / FAQ-sourced CTAs
    "contact sales form.", "contact sales form",
    "contact our sales team",   # FAQ text link, not a pricing card CTA
    "demo video",               # nav/media link, not a conversion CTA
    "help centre", "help center",  # support nav
    # Footer utilities (Websouls / generic)
    "about us", "our team", "why us", "clients", "portfolio",
    "billing area", "announcement", "generate a lead",
    "acceptable use policy", "feedback",
    "open a ticket", "knowledgebase articles", "network status", "faq's",
    "payment method",
    # App store links — move to appLinks, not primary CTAs
    "download on the app store", "get it on google play",
    "download on the app store.", "get it on google play.",
    "available on the app store", "get the app",
    "download app", "download apps", "download the app",
    # Apple FAQ helper text links
    "tap or click here to sign up on our app store",
    "tap or click here to learn more",
    "tap or click here to sign up",
    # Generic nav/footer
    "careers", "blog", "privacy policy", "sitemap", "terms of service",
    "refund policy", "my account", "homepage",
    # Canva education nav
    "for education", "for nonprofits", "for business", "for campus",
}

# URL substrings indicating a CTA link is a utility/policy/footer page.
_CTA_REJECT_URL_SUBSTRINGS = [
    "refund-policy", "refund_policy", "/privacy", "sitemap", "acceptable-use",
    "billing.", "knowledgebase", "network-status", "whois-privacy",
    "/faq/", "payment-method",
    "/education", "/nonprofit", "canva-campus", "generate-a-lead", "/feedback",
    "/about-us", "/our-team", "/portfolio", "/announcement",
    # App store URLs
    "apps.apple.com", "play.google.com", "app-store", "appstore",
    "/careers", "/blog", "/terms", "/refund",
]


def extract_ctas(soup, base_url):
    cta_terms = [
        "contact",
        "book",
        "get quote",
        "request quote",
        "learn more",
        "shop",
        "buy",
        "download",
        "subscribe",
        "sign up",
        "get started",
        "try",
        "demo",
        "call",
        "apply",
        "talk to sales",
        "contact sales",
        "get pro",
        "get teams",
        "start free"
    ]

    bad_long_phrases = [
        "includes:",
        "everything in",
        "limited agent requests",
        "limited tab completions"
    ]

    ctas = []
    seen_text = set()

    for a in soup.find_all("a", href=True):
        text = clean_text(a.get_text(" ", strip=True))

        if not text or len(text) > 90:
            continue

        text_l = text.lower()

        if any(x in text_l for x in bad_long_phrases):
            continue

        if any(term in text_l for term in cta_terms):
            # Reject known utility/footer link texts (exact match on raw text).
            if text_l in _CTA_REJECT_EXACT_TEXTS:
                continue
            # Reject CTAs that link to utility/policy URL paths.
            href_l = (a.get("href") or "").lower()
            if any(sub in href_l for sub in _CTA_REJECT_URL_SUBSTRINGS):
                continue

            normalized = normalize_cta_text(text)
            key = normalized.lower()

            # Keep only first matching text label to avoid many repeated "Get Started".
            if key in seen_text and key in ["get started", "subscribe", "try for free", "download", "learn more ↗"]:
                continue

            seen_text.add(key)

            ctas.append({
                "text": normalized,
                "url": urljoin(base_url, a.get("href")).split("#")[0]
            })

    return rank_ctas(unique_by_url(ctas), limit=30)


def is_tracking_image(url):
    url_l = (url or "").lower()

    bad_patterns = [
        "pixel",
        "analytics",
        "doubleclick",
        "googletag",
        "google-analytics",
        "bat.bing",
        "linkedin.com/collect",
        "facebook",
        "yahoo",
        "clickagy",
        "ads",
        "tracking",
        "1x1",
        "sp.pl"
    ]

    return any(x in url_l for x in bad_patterns)


def extract_images(soup, base_url):
    images = []

    og_image = get_meta(soup, property_name="og:image")

    if og_image and not is_tracking_image(og_image):
        images.append({
            "url": urljoin(base_url, og_image),
            "alt": None,
            "source": "og:image"
        })

    for img in soup.find_all("img"):
        src = (
            img.get("src")
            or img.get("data-src")
            or img.get("data-lazy-src")
            or img.get("srcset")
        )

        if not src:
            continue

        if "," in src:
            src = src.split(",")[0].strip().split(" ")[0]

        if src.startswith("data:image"):
            continue

        absolute_url = urljoin(base_url, src)

        if is_tracking_image(absolute_url):
            continue

        images.append({
            "url": absolute_url,
            "alt": clean_text(img.get("alt")),
            "source": "dom"
        })

    return unique_by_url(images)[:40]


def detect_page_purpose(url, text, headings, links):
    text_l = (text or "").lower()
    url_l = (url or "").lower()

    scores = {
        "article_or_blog": 0,
        "about": 0,
        "contact": 0,
        "policy": 0,
        "landing_page": 0,
        "support": 0,
        "pricing": 0,
        "generic": 0
    }

    if any(x in url_l for x in ["/blog", "/blogs", "/article", "/articles", "/post", "/news"]):
        scores["article_or_blog"] += 5

    if any(x in text_l for x in ["published", "posted", "read time", "author"]):
        scores["article_or_blog"] += 2

    if any(x in url_l for x in ["/about", "/our-story", "/company"]):
        scores["about"] += 5

    if any(x in text_l for x in ["our story", "about us", "our mission", "who we are"]):
        scores["about"] += 3

    if any(x in url_l for x in ["/contact", "/contact-us"]):
        scores["contact"] += 5

    if any(x in text_l for x in ["contact us", "email us", "call us", "get in touch"]):
        scores["contact"] += 3

    if any(x in url_l for x in ["/privacy", "/terms", "/refund", "/shipping", "/returns"]):
        scores["policy"] += 5

    if any(x in text_l for x in ["privacy policy", "terms of service", "refund policy", "shipping policy"]):
        scores["policy"] += 3

    if any(x in url_l for x in ["/help", "/support", "/faq", "/faqs"]):
        scores["support"] += 5

    if any(x in text_l for x in ["frequently asked questions", "questions & answers", "help center", "support center"]):
        scores["support"] += 3

    pricing_hits = 0
    pricing_terms = [
        "pricing",
        "plans",
        "monthly",
        "yearly",
        "annually",
        "per month",
        "/mo",
        "subscription",
        "enterprise",
        "compare plans"
    ]

    for term in pricing_terms:
        if term in text_l or term in url_l:
            pricing_hits += 1

    if "/pricing" in url_l or "/plans" in url_l:
        scores["pricing"] += 7

    if pricing_hits >= 2:
        scores["pricing"] += 3

    if any(x in text_l for x in ["book a demo", "get started", "start free", "request a demo", "try for free"]):
        scores["landing_page"] += 4

    if len(links) >= 20:
        scores["landing_page"] += 1

    primary = max(scores, key=scores.get)

    if scores[primary] == 0:
        primary = "generic"

    return {
        "primaryPurpose": primary,
        "scores": scores
    }


def extract_faqs(soup):
    faqs = []
    seen = set()

    bad_fragments = [
        "try claude",
        "thanks for your help",
        "button text",
        "next question",
        "copy as markdown",
        "back back",
        "pricing pricing",
        "question 01",
        "question 02",
        "question 03",
        "question 04",
        "question 05",
        "learn more",
        "get started",
        "contact sales",
        "compare plans",
        "features and capabilities",
        "models and usage",
        "payment options credit card",
        "rank checker",
        "seo audit tool"
    ]

    bad_starts = [
        "$",
        "pricing",
        "plans",
        "rank checker",
        "questions & answers",
        "compare plans",
        "features and capabilities",
        "security and administration",
        "models and usage",
        "payment options"
    ]

    def normalize_question(q):
        q = clean_text(q)
        q = q.replace("↓", "").replace("↑", "").strip()
        q = re.sub(r"^(questions\s*&\s*answers\s*)", "", q, flags=re.I).strip()
        return q

    def is_valid_question(q):
        q = normalize_question(q)
        q_l = q.lower()

        if not q.endswith("?"):
            return False

        if not (10 <= len(q) <= 140):
            return False

        if q.count("?") != 1:
            return False

        if " " not in q:
            return False

        if any(q_l.startswith(x) for x in bad_starts):
            return False

        if any(x in q_l for x in bad_fragments):
            return False

        # Avoid long merged menu/table fragments that happen to end in a question mark.
        word_count = len(q.split())
        if word_count > 18:
            return False

        return True

    # Prefer actual question headings/buttons. These are usually cleaner than full-text regex.
    for tag in soup.find_all(["h2", "h3", "button", "summary"]):
        q = normalize_question(tag.get_text(" ", strip=True))

        if not is_valid_question(q):
            continue

        key = q.lower()
        if key in seen:
            continue

        seen.add(key)
        faqs.append({"question": q, "answer": None})

        if len(faqs) >= 15:
            return faqs

    # Conservative fallback from full text. Only take natural question starts.
    full_text = clean_text(soup.get_text(" ", strip=True))
    text_questions = re.findall(
        r"\b((?:What|How|Can|Do|Does|Are|Is|Which|Where|When|Why)\b[^?]{8,120}\?)",
        full_text
    )

    for q in text_questions:
        q = normalize_question(q)

        if not is_valid_question(q):
            continue

        key = q.lower()
        if key in seen:
            continue

        seen.add(key)
        faqs.append({"question": q, "answer": None})

        if len(faqs) >= 15:
            break

    return faqs

PRICE_PATTERN = re.compile(
    r"(?P<currency>[$£€])\s*(?P<amount>\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?)\s*(?P<period>/\s?(?:mo|month|user|seat|yr|year|check|project))?",
    flags=re.I
)

# Extended pattern for suffix-currency codes (PKR, INR, AED, SAR, etc.)
# Used as a supplementary scan alongside PRICE_PATTERN.
PRICE_PATTERN_SUFFIX = re.compile(
    r"(?P<amount>\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?)\s*(?P<currency>PKR|INR|AED|SAR|BDT|LKR|NPR|MYR|THB|IDR|PHP|VND|NGN|KES|GHS|EGP|ZAR)\b"
    r"\s*(?P<period>/\s?(?:mo|month|user|seat|yr|year))?",
    flags=re.I
)


def normalize_price_raw(raw):
    raw = clean_text(raw)
    raw = raw.replace("$ ", "$")
    raw = raw.replace(" .", ".")
    raw = re.sub(r"\s*/\s*", "/", raw)
    return raw


def extract_prices(text):
    prices = []
    seen = set()

    text = (text or "").replace("$ ", "$")
    text = text.replace(" .", ".")
    text = re.sub(r"(\d)\s*\.\s*(\d)", r"\1.\2", text)

    # Combine prefix-symbol matches (PRICE_PATTERN) with suffix-code matches
    # (PRICE_PATTERN_SUFFIX) so non-western currency SaaS pages are covered.
    all_matches = list(PRICE_PATTERN.finditer(text)) + list(PRICE_PATTERN_SUFFIX.finditer(text))
    all_matches.sort(key=lambda m: m.start())

    for match in all_matches:
        currency = match.group("currency")
        amount_raw = match.group("amount")
        period = match.group("period")

        if not amount_raw:
            continue

        try:
            amount = float(amount_raw.replace(",", ""))
        except Exception:
            continue

        if amount <= 0:
            continue

        if period:
            period = "/" + period.replace("/", "").replace(" ", "").lower()

        raw = normalize_price_raw(match.group(0))

        key = (currency, amount, period, raw.lower())

        if key in seen:
            continue

        seen.add(key)

        prices.append({
            "currency": currency,
            "amount": amount,
            "period": period,
            "raw": raw
        })

    return prices[:80]


def get_pricing_mentions(text):
    text_l = (text or "").lower()

    terms = [
        "pricing",
        "plan",
        "plans",
        "monthly",
        "yearly",
        "annually",
        "billed monthly",
        "billed annually",
        "subscribe",
        "subscription",
        "enterprise",
        "add-ons",
        "add ons",
        "compare plans",
        "try for free",
        "free trial",
        "custom"
    ]

    return [term for term in terms if term in text_l]


def extract_positioning_signals(text):
    text_l = (text or "").lower()

    signal_map = {
        # ── SaaS / Analytics tool signals ─────────────────────────────────────
        # SEO tool: require tool-specific terms, not generic "seo" mentions
        "SEO": ["seo tool", "seo software", "rank tracker", "search marketing", "keyword rank",
                "search engine optimization tool", "seo classic", "seo + ai"],
        "AI Visibility": ["ai visibility", "brand radar"],
        "AI Search": ["ai search", "custom prompts"],
        "AI Coding": ["agent requests", "tab completions", "cloud agents", "bugbot"],
        "Enterprise": ["enterprise-grade", "enterprise plan", "sso", "scim", "audit log", "admin controls"],
        # Security: require specific SaaS/enterprise security terms — not bare "security"
        "Security": ["privacy mode", "saml", "oidc", "zero-trust", "security audit",
                     "soc 2", "hipaa", "gdpr compliant", "advanced security controls"],
        "Site Audit": ["site audit", "crawl credits"],
        "Position Tracking": ["position tracking", "tracked keywords"],
        "Keyword Research": ["keyword research", "keywords explorer"],
        "Competitor Analysis": ["competitor analysis", "competitive intelligence"],
        "Backlinks": ["backlink", "backlinks"],
        "Share of Voice": ["share of voice"],
        "API Access": ["api access", "rest api", "developer api"],
        "Historical Data": ["historical data"],
        "Automation": ["workflow automation", "automated reports"],
        # Team Collaboration — require specific collaboration terms, not bare "team"
        "Team Collaboration": ["team collaboration", "shared team context",
                               "invite team", "team management"],
        "Usage Analytics": ["usage analytics", "usage-based"],
        # ── Apple One / service bundle signals ────────────────────────────────
        "Apple Services Bundle": ["apple one", "six apple subscriptions", "subscription bundle"],
        "Family Sharing": ["family sharing"],
        "iCloud+ Storage": ["icloud+"],
        "Entertainment Bundle": ["apple tv+", "apple arcade", "apple fitness+", "apple news+"],
        "Lower Monthly Price": ["lower monthly price", "bundle and save"],
        "Free Trial": ["try it free", "try apple one free"],
        # ── Web hosting signals ───────────────────────────────────────────────
        "NVMe Storage": ["nvme storage", "nvme ssd"],
        "LiteSpeed Server": ["litespeed server", "litespeed cache", "lscache"],
        "DDoS Protection": ["ddos protection"],
        "Malware Scanning": ["malware scanner", "malware scanning"],
        "Free Migration": ["free migration", "free website migration"],
        "99.9% Uptime": ["99.9% uptime", "99.99% uptime"],
        "Money-Back Guarantee": ["money back guarantee", "100 day"],
        "7-Day Free Trial": ["7-day free trial", "7 day free trial"],
        "Local Support": ["local telephonic support", "multilingual team"],
        # ── Canva / creative platform signals ────────────────────────────────
        "AI Design Tools": ["magic write", "canva ai", "ai image", "ai ad creation",
                            "magic layers", "canva code", "canva ai 2"],
        "Premium Content": ["141m+ premium", "premium photos", "premium templates",
                            "premium content", "141+ million"],
        "Brand Kits": ["brand kit", "brand kits", "100 brand kits"],
        "Visual Communication": ["visual communication", "drag-and-drop editor", "design types"],
        "Creative Platform": ["canva", "design platform", "creative platform"],
        "Free Plan Available": ["free plan", "0 rs /year", "free design", "no cost, just creativity"],
        "SSO and SCIM": ["sso and scim", "sso provisioning", "scim provisioning"],
        "Enterprise Security Controls": ["enterprise-level security", "enterprise security",
                                         "end-to-end visual"],
        "Custom Enterprise Pricing": ["let's talk", "contact sales", "custom enterprise"],
        "AI Pass": ["ai pass", "ai allowance", "ultra ai", "premium ai"],
        # ── Claude / Anthropic SaaS signals ─────────────────────────────────
        "Free AI assistant plan": ["try claude", "free for everyone", "claude.ai for free",
                                   "start for free"],
        "Pro productivity plan": ["claude pro", "priority access", "5x more usage"],
        "Max high-usage plan": ["claude max", "20x more usage", "maximum usage"],
        "Team collaboration": ["team plan", "team workspace", "collaborate with your team"],
        "Enterprise security and compliance": ["expanded context window", "admin controls",
                                               "enterprise-grade security"],
        "API pricing": ["api pricing", "anthropic api", "claude api"],
        "Model-based token pricing": ["per m tokens", "per million tokens", "mtok"],
        "Batch processing discount": ["batch api", "50% discount", "batch processing"],
        "Claude Code included": ["claude code", "autonomous coding", "coding agent"],
        "Connectors and MCP": ["mcp", "model context protocol", "connectors"],
        "HIPAA-ready offering": ["hipaa"],
        "Custom data retention": ["custom data retention", "zero retention"],
    }

    found = []
    padded = f" {text_l} "
    for label, patterns in signal_map.items():
        if any(pattern in padded for pattern in patterns):
            found.append(label)

    return found[:25]



CORE_PLAN_BAD_NAMES = {
    "pricing", "plans", "plans & pricing", "seo classic plans", "toolkits",
    "compare plans", "compare plans & features", "compare features across plans",
    "optional add-ons", "questions & answers", "questions? we have answers", "faq",
    "testimonials", "resources", "company", "legal", "connect", "product",
    "features and capabilities", "security and administration", "payment options",
    "models and usage", "partnership", "content kit", "report builder",
    "project boost pro", "project boost max", "custom prompt packages",
    "improve your plan with add-ons", "playing big? request an enterprise demo.",
    "get started with cursor.", "trusted every day by teams that build world-class software.",
    "start here", "find the right tools", "platform", "top apps", "grow with semrush",
    "explore free tools", "about semrush", "cookie settings",
    "opus", "sonnet", "haiku", "opus 4.7", "sonnet 4.6", "haiku 4.5",
    "opus 4.6", "sonnet 4.5", "opus 4.5", "opus 4.1", "sonnet 4", "opus 4"
}

ADDON_NAME_PATTERNS = [
    "additional users", "lead generation", "base report", "pro report",
    "content kit", "report builder", "project boost", "custom prompt",
    "managed agents", "web search", "code execution", "service tiers"
]

STANDALONE_NAME_PATTERNS = [
    "ahrefs free", "brand radar ai", "brand radar", "starter", "education plan"
]

CORE_PLAN_PRIORITY = {
    "hobby": 0,
    "free": 0,
    "seo": 0,
    "individual": 1,
    "family": 2,      # Apple One Family tier
    "pro": 1,
    "pro+": 2,
    "lite": 1,
    "starter": 2,
    "standard": 2,
    "guru": 2,
    "teams": 3,
    "team": 3,
    "business": 4,
    "advanced": 4,
    "max": 4,
    "ultra": 4,
    "premier": 4,     # Apple One Premier tier
    "enterprise": 5,
}

GENERIC_CORE_NAMES = {
    "hobby", "free", "individual", "family", "premier", "pro", "pro+", "guru", "business",
    "lite", "standard", "advanced", "team", "teams", "max", "ultra",
    "enterprise", "seo", "starter"
}


def normalize_plan_name(name):
    name = clean_text(name)
    name = name.replace("↓", "").replace("↑", "").strip()
    name = re.sub(r"\s+", " ", name)
    return name


def classify_pricing_heading(name, text):
    """
    Returns one of: core_plan, addon, standalone_product, ignore.
    Conservative by design: wrong plan names are worse than missing plans.
    """
    name = normalize_plan_name(name)
    key = name.lower()
    text_l = (text or "").lower()

    if not name:
        return "ignore"

    if name.endswith("?"):
        return "ignore"

    if len(name) > 55:
        return "ignore"

    # Check add-ons/standalone products before the generic bad-heading list.
    # Some add-on names, such as Content Kit or Report Builder, are also section-like
    # headings, but they are still useful pricing entities on pricing pages.
    if any(x in key for x in ADDON_NAME_PATTERNS):
        return "addon"

    if any(x == key or x in key for x in STANDALONE_NAME_PATTERNS):
        return "standalone_product"

    if key in CORE_PLAN_BAD_NAMES:
        return "ignore"

    # Starter is page-dependent: core for Semrush SEO+AI Search; standalone for Ahrefs.
    if key == "starter":
        pos = text_l.find("starter")
        window = text_l[pos:pos + 500] if pos >= 0 else ""
        if "seo + ai search" in window or "semrush" in text_l[:2000]:
            return "core_plan"
        return "standalone_product"

    if key in ["basic", "growth", "scale"]:
        # Usually prompt/package tiers, not the main SaaS plan ladder.
        return "addon"

    if key in GENERIC_CORE_NAMES:
        return "core_plan"

    # Allow Semrush-specific SEO heading if it behaves like a plan card.
    if key == "seo" and "seo + ai search" in text_l:
        return "core_plan"

    return "ignore"


def extract_pricing_candidates(headings, text):
    candidates = []
    seen = set()

    for h in headings or []:
        name = normalize_plan_name(h.get("text"))
        kind = classify_pricing_heading(name, text)
        if kind == "ignore":
            continue

        key = (name.lower(), kind)
        if key in seen:
            continue

        seen.add(key)
        candidates.append({
            "name": name,
            "type": kind,
            "source": "heading"
        })

    return candidates


def extract_plan_names(text, headings):
    candidates = extract_pricing_candidates(headings, text)
    names = [c["name"] for c in candidates if c["type"] == "core_plan"]
    names = unique_clean_names(names)
    names.sort(key=lambda n: CORE_PLAN_PRIORITY.get(n.lower(), 99))
    return names[:12]


def unique_clean_names(names):
    seen = set()
    output = []
    for name in names or []:
        name = normalize_plan_name(name)
        key = name.lower()
        if not name or key in seen:
            continue
        seen.add(key)
        output.append(name)
    return output


def extract_price_from_small_window(text, start, window_size=520):
    window = text[start:start + window_size]
    prices = extract_prices(window)

    if not prices:
        return None

    # Prefer recurring monthly/user/seat prices, but ignore small add-on fragments if avoidable.
    recurring = [
        p for p in prices
        if p.get("period") and any(x in p.get("period", "") for x in ["mo", "month", "user", "seat"])
    ]

    candidates = recurring or prices
    candidates = [p for p in candidates if p.get("amount") is None or p.get("amount") >= 5]

    return candidates[0] if candidates else None


def find_plan_positions(text, names):
    positions = []
    for name in names:
        # use first meaningful occurrence that is not a nav/footer occurrence
        for m in re.finditer(rf"\b{re.escape(name)}\b", text, flags=re.I):
            pos = m.start()
            before = text[max(0, pos - 140):pos].lower()
            after = text[pos:pos + 260].lower()

            if any(x in before for x in ["privacy policy", "terms of", "core tools", "free tools", "resources"]):
                continue
            if len(after) < 20:
                continue

            positions.append((name, pos))
            break

    positions.sort(key=lambda x: x[1])
    return positions


def map_sequential_price_row(text, core_names):
    """
    Handles pages like Ahrefs where Lite/Standard/Advanced appear first,
    then a row of prices appears after the headings.
    """
    if len(core_names) < 3:
        return {}

    positions = find_plan_positions(text, core_names)
    if len(positions) < 3:
        return {}

    # Use only the first cluster of headings before a price row.
    cluster = []
    last_pos = None
    for name, pos in positions:
        if last_pos is None or pos - last_pos < 500:
            cluster.append((name, pos))
            last_pos = pos
        else:
            break

    if len(cluster) < 3:
        return {}

    names = [x[0] for x in cluster]
    start_after_cluster = cluster[-1][1]
    window = text[start_after_cluster:start_after_cluster + 900]
    prices = extract_prices(window)
    prices = [p for p in prices if p.get("period") and "mo" in p.get("period", "") and p.get("amount", 0) >= 20]

    if len(prices) < min(3, len(names)):
        return {}

    mapping = {}
    for name, price in zip(names, prices):
        # Enterprise often appears later and should not be mapped to a non-enterprise row unless explicitly in the cluster.
        if name.lower() == "enterprise" and price.get("amount", 0) < 500:
            continue
        mapping[name.lower()] = price

    return mapping


def select_best_plan_price(text, name):
    text = text or ""
    name_l = name.lower()
    matches = list(re.finditer(rf"\b{re.escape(name)}\b", text, flags=re.I))

    if not matches:
        return None, 0

    if name_l in ["free", "hobby", "ahrefs free"]:
        for m in matches[:8]:
            window = text[m.start():m.start() + 460].lower()
            if (
                re.search(r"\$\s*0\b", window)
                or "free for everyone" in window
                or "hobby free" in window
                or "free get started" in window
                or "get ahrefs data on your site" in window
                or "free limited access" in window
            ):
                return {"currency": None, "amount": 0, "period": None, "raw": "Free"}, 8
        # Avoid assigning nearby paid standalone product prices to free plans.
        if name_l in ["free", "ahrefs free"]:
            return {"currency": None, "amount": 0, "period": None, "raw": "Free"}, 6

    if name_l == "enterprise":
        best_custom = None
        best_paid = None
        for m in matches[:10]:
            window = text[m.start():m.start() + 620]
            window_l = window.lower()
            prices = extract_prices(window)
            recurring = [p for p in prices if p.get("period") and "mo" in p.get("period", "")]
            high_recurring = [p for p in recurring if p.get("amount", 0) >= 500]

            if high_recurring:
                best_paid = high_recurring[0]
                break

            if any(x in window_l[:360] for x in ["custom", "contact sales", "talk to sales", "tailored", "sales-assisted"]):
                best_custom = {"currency": None, "amount": None, "period": None, "raw": "Custom"}

        if best_paid:
            return best_paid, 8
        if best_custom:
            return best_custom, 7

    best = None
    best_score = -1

    for m in matches[:10]:
        pos = m.start()
        window = text[pos:pos + 560]
        window_l = window.lower()

        # Skip navigation/menu/footer-like occurrences.
        if any(x in window_l[:220] for x in [
            "product search marketing", "resources learn", "legal privacy",
            "homepage anthropic", "core tools", "free tools", "use cases →"
        ]):
            continue

        score = 0
        if any(x in window_l for x in ["try", "get started", "subscribe", "contact sales", "talk to sales", "download"]):
            score += 2
        if any(x in window_l for x in ["everything in", "includes", "per month", "/ mo", "/mo", "per seat", "/seat", "billed annually", "billed monthly", "for beginners", "for teams", "for small businesses"]):
            score += 3

        price = extract_price_from_small_window(text, pos)
        if not price:
            continue

        # Avoid obvious add-on/user fees for core plans.
        amount = price.get("amount")
        if amount and amount < 100 and name_l in ["lite", "standard", "advanced", "business", "guru", "pro+"]:
            if any(x in window_l for x in ["additional user", "add ", "addon", "add-on", "prompt", "report"]):
                continue

        if score > best_score:
            best = price
            best_score = score

    return best, best_score



def get_main_pricing_section(text):
    """
    Keep only the first/main pricing-card area. This prevents add-ons,
    comparison tables, FAQ text, and footer prices from polluting core plan mapping.
    """
    text = text or ""
    text_l = text.lower()

    start = 0
    for marker in [
        "plans & pricing",
        "seo + ai search",
        "seo classic plans",
        "pricing monthly",
        "pricing individual",
        "monthly yearly",
    ]:
        pos = text_l.find(marker)
        if pos >= 0:
            start = pos
            break

    section = text[start:]
    section_l = section.lower()

    end_markers = [
        "optional add-ons",
        "improve your plan with add-ons",
        "compare plans & features",
        "compare plans",
        "compare features across plans",
        "questions? we have answers",
        "questions & answers",
        "faq",
        "testimonials",
        "starter see what people search",   # Ahrefs standalone product area
        "ahrefs free",
        "brand radar ai",
        "education plan",
        "pricing for claude platform features",
    ]

    cut = len(section)
    for marker in end_markers:
        pos = section_l.find(marker)
        if pos > 120:
            cut = min(cut, pos)

    return section[:cut]


def get_name_local_window(text, name, size=520):
    text = text or ""
    m = re.search(rf"\b{re.escape(name)}\b", text, flags=re.I)
    if not m:
        return ""
    return text[m.start():m.start() + size]


def extract_ordered_core_prices(text):
    """
    Extract likely core plan prices from the main pricing-card section only.
    Excludes add-on/user/token/check prices and annual comparison prices where possible.
    """
    section = get_main_pricing_section(text)
    prices = extract_prices(section)

    ordered = []
    seen = set()

    for price in prices:
        amount = price.get("amount")
        period = (price.get("period") or "").lower()
        raw = (price.get("raw") or "").lower()

        if not isinstance(amount, (int, float)) or amount <= 0:
            continue

        # Core SaaS plan prices normally appear as monthly/user/seat recurring prices.
        if not any(x in period for x in ["mo", "month", "user", "seat"]):
            continue

        # Exclude unit economics and non-plan usage prices.
        if any(x in period for x in ["check", "token", "mtok", "hour"]):
            continue
        if any(x in raw for x in ["/check", "mtok", "token", "session-hour", "container"]):
            continue

        # Exclude obvious add-on/user fees unless the page only has low prices like Cursor.
        local = section[max(0, section.lower().find(raw.replace(" ", "")) - 120):]
        if amount < 100 and any(x in raw for x in ["$40", "$45", "$50", "$60", "$80", "$90", "$99"]):
            # keep Cursor Teams $40/user, reject Ahrefs/Semrush add-on prices later using section order/context
            pass

        key = (price.get("currency"), amount, period)
        if key in seen:
            continue
        seen.add(key)
        ordered.append(price)

    return ordered



def get_ordered_name_positions(section, names):
    """Return first meaningful occurrence of each name in section, ordered by position."""
    positions = []
    used = set()
    for name in names or []:
        key = name.lower()
        if key in used:
            continue
        for m in re.finditer(rf"\b{re.escape(name)}\b", section, flags=re.I):
            pos = m.start()
            after = section[pos:pos + 240].lower()
            before = section[max(0, pos - 120):pos].lower()
            # Skip generic prose such as "enterprise scale"; it is not a plan card heading.
            if key == "enterprise" and after.startswith("enterprise scale"):
                continue
            if any(x in before for x in ["footer", "privacy", "terms", "resources", "core tools"]):
                continue
            if len(after) < 15:
                continue
            positions.append((name, pos))
            used.add(key)
            break
    positions.sort(key=lambda x: x[1])
    return positions


def map_clustered_price_row(section, core_names):
    """
    Handles horizontal pricing-card pages where plan names appear first and the
    price row appears immediately after the heading row, e.g. Ahrefs:
    Lite / Standard / Advanced / Why upgrade? / $129 / $249 / $449.
    """
    if not section or len(core_names or []) < 3:
        return {}

    positions = get_ordered_name_positions(section, core_names)
    if len(positions) < 3:
        return {}

    # Use the first cluster of plan names. Stop if a later plan is far away
    # because that is likely Enterprise or another section.
    cluster = []
    previous = None
    for name, pos in positions:
        if previous is None or pos - previous <= 450:
            cluster.append((name, pos))
            previous = pos
        else:
            break

    if len(cluster) < 3:
        return {}

    cluster_names = [x[0] for x in cluster]
    row_start = cluster[-1][1]
    row = section[row_start:row_start + 900]

    # Cut before features/additional user rows so $40/$60/$80 user fees do not enter.
    row_l = row.lower()
    cut_markers = [
        "get started get started",
        "5 projects",
        "20 projects",
        "50 projects",
        "what's included",
        "what’s included",
        "all lite features",
        "all standard features",
    ]
    cut = len(row)
    for marker in cut_markers:
        pos = row_l.find(marker)
        if pos > 0:
            cut = min(cut, pos)
    row = row[:cut]

    prices = extract_prices(row)
    prices = [
        p for p in prices
        if isinstance(p.get("amount"), (int, float))
        and p.get("amount") > 0
        and p.get("period")
        and "mo" in p.get("period", "").lower()
        and not any(x in (p.get("raw") or "").lower() for x in ["/check", "token", "mtok"])
    ]

    if len(prices) < len(cluster_names):
        return {}

    mapping = {}
    for name, price in zip(cluster_names, prices):
        # Do not assign tiny add-on/user fees as core prices on multi-plan ladders.
        if price.get("amount", 0) < 100 and len([p for p in prices if p.get("amount", 0) >= 100]) >= 2:
            continue
        mapping[name.lower()] = price

    return mapping


def map_enterprise_price(section):
    m = re.search(r"\bEnterprise\b", section, flags=re.I)
    if not m:
        return None
    window = section[m.start():m.start() + 900]
    prices = extract_prices(window)
    recurring = [
        p for p in prices
        if isinstance(p.get("amount"), (int, float))
        and p.get("period")
        and "mo" in p.get("period", "").lower()
    ]
    high = [p for p in recurring if p.get("amount", 0) >= 500]
    if high:
        return high[0]
    wl = window.lower()
    if any(x in wl for x in ["custom", "contact sales", "talk to sales", "tailored"]):
        return {"currency": None, "amount": None, "period": None, "raw": "Custom"}
    return None

def map_core_prices_by_order(text, core_names):
    """
    Robust fallback for pricing-card pages:
    - first extract plan names from headings
    - then map the ordered core monthly prices from the main card area
    This handles Ahrefs-style pages where all plan names appear before the price row.
    """
    if not core_names:
        return {}

    section = get_main_pricing_section(text)
    section_l = section.lower()

    # First try block/row-based mapping. This prevents shifted mappings such as
    # Lite -> $249, Standard -> $449, Advanced -> $40 on Ahrefs-style pages.
    mapping = map_clustered_price_row(section, core_names)

    enterprise_price = map_enterprise_price(section)
    if enterprise_price:
        mapping["enterprise"] = enterprise_price

    if mapping:
        return mapping

    prices = extract_ordered_core_prices(text)

    # On pages with high-value plans plus small add-on/user fees in the same section,
    # keep the high-value plan ladder and ignore small user fees.
    high_prices = [p for p in prices if isinstance(p.get("amount"), (int, float)) and p.get("amount") >= 100]
    if len(high_prices) >= 3:
        prices_for_mapping = high_prices
    else:
        prices_for_mapping = prices

    mapping = {}
    price_index = 0

    for name in core_names:
        key = name.lower()
        local_window = get_name_local_window(section, name, size=700).lower()

        if key in ["free", "hobby"] and (
            "free" in local_window or re.search(r"\$\s*0\b", local_window)
        ):
            mapping[key] = {"currency": None, "amount": 0, "period": None, "raw": "Free"}
            continue

        if key == "enterprise" and any(x in local_window for x in ["custom", "contact sales", "talk to sales", "tailored"]):
            # If a high enterprise price exists in the main pricing section, use it. Otherwise Custom.
            enterprise_prices = [p for p in prices_for_mapping if isinstance(p.get("amount"), (int, float)) and p.get("amount") >= 500]
            if enterprise_prices:
                mapping[key] = enterprise_prices[-1]
            else:
                mapping[key] = {"currency": None, "amount": None, "period": None, "raw": "Custom"}
            continue

        # Prefer a clear price very close to this specific plan name.
        close_prices = extract_prices(get_name_local_window(section, name, size=520))
        close_prices = [
            p for p in close_prices
            if p.get("period") and any(x in p.get("period", "").lower() for x in ["mo", "month", "user", "seat"])
            and isinstance(p.get("amount"), (int, float))
            and p.get("amount") > 0
        ]

        if close_prices:
            # Avoid assigning small user/add-on prices to high-tier core plans.
            cp = close_prices[0]
            if not (key in ["standard", "advanced", "business", "guru", "pro+", "lite"] and cp.get("amount", 0) < 100 and len(high_prices) >= 3):
                mapping[key] = cp
                continue

        # Ordered fallback.
        while price_index < len(prices_for_mapping):
            candidate = prices_for_mapping[price_index]
            price_index += 1

            if key == "enterprise" and candidate.get("amount", 0) < 500 and len(high_prices) >= 3:
                continue

            mapping[key] = candidate
            break

    return mapping


def validate_core_plan_mapping(core_plans):
    """
    Return (valid, notes). Disables plan prices when mapping is clearly shifted/corrupt.
    """
    notes = []
    priced = [p for p in core_plans if isinstance(p.get("price"), dict)]
    paid = [p for p in priced if isinstance(p["price"].get("amount"), (int, float)) and p["price"].get("amount") > 0]

    if not paid:
        return False, ["Core plan prices were not confidently mapped."]

    amounts = [p["price"]["amount"] for p in paid]

    if any(amounts.count(x) >= 3 for x in set(amounts)):
        notes.append("Core plan price mapping was disabled because the same price was assigned to too many plans.")
        return False, notes

    # If a multi-tier plan ladder has high prices but a middle/later core plan got a small user/add-on fee, reject.
    high_count = sum(1 for a in amounts if a >= 100)
    low_later = any(
        p.get("name", "").lower() in ["standard", "advanced", "business", "guru", "pro+", "lite"]
        and isinstance(p.get("price"), dict)
        and isinstance(p["price"].get("amount"), (int, float))
        and p["price"].get("amount") < 100
        for p in core_plans
    )
    if high_count >= 3 and low_later:
        notes.append("Core plan price mapping was disabled because a core plan was mapped to an add-on/user fee.")
        return False, notes

    # Paid ladder should generally not drop sharply for ordered core plans.
    ordered_paid_amounts = []
    for p in core_plans:
        price = p.get("price")
        if isinstance(price, dict) and isinstance(price.get("amount"), (int, float)) and price.get("amount") > 0:
            ordered_paid_amounts.append(price.get("amount"))

    for prev, curr in zip(ordered_paid_amounts, ordered_paid_amounts[1:]):
        if prev >= 100 and curr < prev * 0.55:
            notes.append("Core plan price mapping was disabled because the plan ladder decreases suspiciously.")
            return False, notes

    return True, notes


def disable_core_plan_prices(core_plans, notes):
    output = []
    for plan in core_plans:
        plan = dict(plan)
        if isinstance(plan.get("price"), dict) and plan["price"].get("amount") == 0:
            # keep true free plans
            output.append(plan)
            continue
        plan["price"] = None
        plan["confidence"] = 0.45
        plan["source"] = "core_plan_name_only"
        output.append(plan)
    return output, notes

def build_pricing_offers(text, headings, prices):
    candidates = extract_pricing_candidates(headings, text)

    core_names = unique_clean_names([c["name"] for c in candidates if c["type"] == "core_plan"])
    addon_names = unique_clean_names([c["name"] for c in candidates if c["type"] == "addon"])
    standalone_names = unique_clean_names([c["name"] for c in candidates if c["type"] == "standalone_product"])

    core_names.sort(key=lambda n: CORE_PLAN_PRIORITY.get(n.lower(), 99))

    ordered_mapping = map_core_prices_by_order(text, core_names)

    core_plans = []
    for name in core_names:
        key = name.lower()
        price = ordered_mapping.get(key)
        score = 8 if price else 0

        # Use local proximity only when ordered mapping did not find a candidate.
        if not price:
            price, score = select_best_plan_price(text, name)

        if price and score >= 3:
            raw = str(price.get("raw") or "").lower() if isinstance(price, dict) else ""
            amount = price.get("amount") if isinstance(price, dict) else None
            confidence = 0.86 if score >= 7 else 0.72
            if raw == "custom" or amount is None:
                confidence = 0.7
            core_plans.append({
                "name": name,
                "type": "core_plan",
                "price": price,
                "confidence": confidence,
                "source": "core_plan_mapping"
            })
        else:
            core_plans.append({
                "name": name,
                "type": "core_plan",
                "price": None,
                "confidence": 0.45,
                "source": "core_plan_name_only"
            })

    notes = []

    # Correct known free/hobby plans.
    for plan in core_plans:
        if plan["name"].lower() in ["free", "hobby"]:
            local = get_name_local_window(get_main_pricing_section(text), plan["name"], 500).lower()
            if "free" in local or "$0" in local or "$ 0" in local:
                plan["price"] = {"currency": None, "amount": 0, "period": None, "raw": "Free"}
                plan["confidence"] = max(plan.get("confidence", 0), 0.78)
                plan["source"] = "core_plan_mapping"

    valid, validation_notes = validate_core_plan_mapping(core_plans)
    notes.extend(validation_notes)
    if not valid:
        core_plans, notes = disable_core_plan_prices(core_plans, notes)

    addons = []
    for name in addon_names:
        price, score = select_best_plan_price(text, name)
        addons.append({
            "name": name,
            "type": "addon",
            "price": price if score >= 2 else None,
            "confidence": 0.7 if score >= 2 else 0.45,
            "source": "addon_heading"
        })

    standalone = []
    for name in standalone_names:
        price, score = select_best_plan_price(text, name)
        standalone.append({
            "name": name,
            "type": "standalone_product",
            "price": price if score >= 2 else None,
            "confidence": 0.7 if score >= 2 else 0.45,
            "source": "standalone_heading"
        })

    priced_core = [p for p in core_plans if isinstance(p.get("price"), dict)]
    paid_or_free_core = [
        p for p in priced_core
        if p["price"].get("raw") == "Custom" or p["price"].get("amount") is not None
    ]

    if valid and len(paid_or_free_core) >= max(2, min(3, len(core_plans))):
        confidence = "high_clean"
    elif len(paid_or_free_core) >= 1:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "corePlans": core_plans[:10],
        "addOns": addons[:12],
        "standaloneProducts": standalone[:12],
        "planNames": [p["name"] for p in core_plans[:10]],
        "planMappingConfidence": confidence,
        "notes": notes
    }

def estimate_main_plan_price_range(prices, core_plans=None, text=None):
    core_amounts = []
    for plan in core_plans or []:
        price = plan.get("price")
        if not isinstance(price, dict):
            continue
        amount = price.get("amount")
        raw = str(price.get("raw") or "").lower()
        if isinstance(amount, (int, float)) and amount > 0 and raw != "custom":
            core_amounts.append(amount)

    if core_amounts:
        return min(core_amounts), max(core_amounts)

    if text:
        section_prices = extract_ordered_core_prices(text)
        high_section = [
            p.get("amount") for p in section_prices
            if isinstance(p.get("amount"), (int, float)) and p.get("amount") >= 100
        ]
        if len(high_section) >= 2:
            return min(high_section), max(high_section)

    if not prices:
        return None, None

    candidates = []
    for price in prices:
        amount = price.get("amount")
        period = (price.get("period") or "").lower()
        raw = (price.get("raw") or "").lower()

        if not isinstance(amount, (int, float)) or amount <= 0:
            continue
        if any(x in period for x in ["check", "mtok", "token", "hour"]):
            continue
        if any(x in raw for x in ["/check", "mtok", "token", "session-hour", "container"]):
            continue
        if amount < 5:
            continue

        if period and any(x in period for x in ["mo", "month", "user", "seat"]):
            candidates.append(amount)

    if not candidates:
        return None, None

    # If there are enough true SaaS plan-like high values, ignore obvious add-on lows.
    high_candidates = [x for x in candidates if x >= 100]
    if len(high_candidates) >= 2:
        return min(high_candidates), max(high_candidates)

    return min(candidates), max(candidates)


def extract_pricing_summary(prices, core_plans=None, text=None):
    if not prices:
        return {
            "lowestPrice": None,
            "highestPrice": None,
            "currency": None,
            "monthlyPricesDetected": 0,
            "totalPricesDetected": 0,
            "lowestMainPlanPrice": None,
            "highestMainPlanPrice": None
        }

    currency = prices[0].get("currency")
    all_amounts = [p["amount"] for p in prices if isinstance(p.get("amount"), (int, float))]
    monthly_prices = [p for p in prices if p.get("period") and any(x in p["period"] for x in ["mo", "month", "user", "seat"])]
    lowest_main, highest_main = estimate_main_plan_price_range(prices, core_plans=core_plans, text=text)

    return {
        "lowestPrice": min(all_amounts) if all_amounts else None,
        "highestPrice": max(all_amounts) if all_amounts else None,
        "currency": currency,
        "monthlyPricesDetected": len(monthly_prices),
        "totalPricesDetected": len(prices),
        "lowestMainPlanPrice": lowest_main,
        "highestMainPlanPrice": highest_main
    }


def extract_plan_features(text, core_plans):
    """
    Light-weight feature extraction from clear per-plan card segments only.
    If the page uses a complex comparison grid, this avoids copying the first plan's
    features into every plan. The full text is still available for OpenAI.
    """
    if not text or not core_plans:
        return {}

    main_section = get_main_pricing_section(text)
    if not main_section:
        return {}

    features = {}
    names = [p.get("name") for p in core_plans if p.get("name")]
    positions = []
    for name in names:
        m = re.search(rf"\b{re.escape(name)}\b", main_section, flags=re.I)
        if m:
            positions.append((name, m.start()))

    positions.sort(key=lambda x: x[1])
    if not positions:
        return {}

    patterns = {
        "projects": r"(\d[\d,]*)\s+projects?",
        "trackedKeywords": r"(\d[\d,]*)\s+(?:tracked\s+)?keywords?",
        "trackedPrompts": r"(\d[\d,]*)\s+(?:tracked\s+)?prompts?",
        "crawlCredits": r"(\d[\d,]*)\s+crawl credits",
        "usersIncluded": r"(\d[\d,]*)\s+users? included|included users\s+(\d[\d,]*)",
        "websitesToMonitor": r"(\d[\d,]*)\s+websites? to monitor",
    }

    for idx, (name, pos) in enumerate(positions):
        next_pos = positions[idx + 1][1] if idx + 1 < len(positions) else min(len(main_section), pos + 900)
        segment = main_section[pos:next_pos]

        # If the segment is too tiny, this is likely a horizontal heading row, not a card.
        if len(segment) < 80:
            continue

        found = {}
        for key, pattern in patterns.items():
            pm = re.search(pattern, segment, flags=re.I)
            if pm:
                value = next((g for g in pm.groups() if g), None)
                if value:
                    try:
                        found[key] = int(value.replace(",", ""))
                    except Exception:
                        found[key] = value

        if found:
            features[name] = found

    # Safety: if every plan got exactly the same values, it is probably copied from a shared comparison area.
    if len(features) > 1:
        signatures = {tuple(sorted(v.items())) for v in features.values()}
        if len(signatures) == 1:
            return {}

    return features

def analyze_unknown_general(self, url, html, headers, page_type, level1):
    result = self.base_result(url, html, headers, page_type, level1)

    soup = BeautifulSoup(html or "", "lxml")

    detected_platform = level1.get("platform", "Unknown") if level1 else "Unknown"
    general_subtype = level1.get("generalSubtype") if level1 else None

    title = clean_text(soup.title.string) if soup.title and soup.title.string else None
    meta_description = get_meta(soup, name="description") or get_meta(soup, property_name="og:description")

    canonical_tag = soup.find("link", rel="canonical")
    canonical = canonical_tag.get("href") if canonical_tag else None

    h1_tag = soup.find("h1")
    h1 = clean_text(h1_tag.get_text(" ", strip=True)) if h1_tag else None

    headings = extract_headings(soup)
    main_text = extract_main_text(soup)
    links = extract_links(soup, url)
    ctas = extract_ctas(soup, url)
    images = extract_images(soup, url)
    faqs = extract_faqs(soup)

    purpose = detect_page_purpose(
        url=url,
        text=main_text,
        headings=headings,
        links=links
    )

    if not general_subtype and purpose.get("primaryPurpose") != "generic":
        general_subtype = purpose.get("primaryPurpose")

    prices = extract_prices(main_text)
    pricing_mentions = get_pricing_mentions(main_text)
    pricing_offers = build_pricing_offers(main_text, headings, prices) if prices else {
        "corePlans": [],
        "addOns": [],
        "standaloneProducts": [],
        "planNames": [],
        "planMappingConfidence": "low",
        "notes": []
    }

    core_plans = pricing_offers.get("corePlans", [])
    if not core_plans:
        # Deterministic DOM fallback for plan-card grids (see extractors/plan_parser.py)
        try:
            from extractors.plan_parser import extract_plan_cards_from_dom
            _dom_plans = extract_plan_cards_from_dom(soup)
            if _dom_plans:
                core_plans = _dom_plans
                pricing_offers["corePlans"] = _dom_plans
                pricing_offers["planNames"] = [pl.get("name") for pl in _dom_plans]
        except Exception:
            pass
    pricing_summary = extract_pricing_summary(prices, core_plans=core_plans, text=main_text)
    plan_features = extract_plan_features(main_text, core_plans)
    positioning_signals = extract_positioning_signals(main_text)

    result["platform"] = detected_platform
    # Preserve the level1-detected page type (e.g. "blog") — the unknown
    # analyzer routes blogs through this general extractor, and hardcoding
    # "general" here misreported every blog on unknown platforms.
    result["page"]["pageType"] = page_type or "general"

    if general_subtype:
        result["page"]["generalSubtype"] = general_subtype

    result["seo"] = {
        "title": title,
        "metaDescription": meta_description,
        "canonical": canonical,
        "h1": h1
    }

    result["content"] = {
        "title": h1 or title,
        "summaryText": main_text[:1000],
        "mainText": main_text,
        "headings": headings,
        "faqs": faqs,
        "pagePurpose": purpose,
        "pricingMentions": pricing_mentions
    }

    result["navigation"] = {
        "links": links
    }

    result["ctas"] = ctas

    result["media"] = {
        "images": images
    }

    is_pricing_page = (
        general_subtype == "pricing"
        or purpose.get("primaryPurpose") == "pricing"
        or "/pricing" in (url or "").lower()
    )

    result["ecommerce"] = {
        "hasEcommerceSignals": False,
        "hasPrices": bool(prices),
        "pricingPage": bool(is_pricing_page),
        "products": [],
        "categoryLinks": [
            link for link in links
            if any(
                x in link["url"].lower()
                for x in [
                    "/collections/",
                    "/category/",
                    "/shop/",
                    "/products/"
                ]
            )
        ][:50]
    }

    if prices:
        result["pricing"] = {
            "pricesDetected": len(prices),
            "prices": prices,
            "summary": pricing_summary,
            "planNames": pricing_offers.get("planNames", []),
            "corePlans": core_plans,
            "addOns": pricing_offers.get("addOns", []),
            "standaloneProducts": pricing_offers.get("standaloneProducts", []),
            "planFeatures": plan_features,
            # Backward compatibility. Keep old keys but make them safer.
            "plans": core_plans,
            "planMappingConfidence": pricing_offers.get("planMappingConfidence", "low"),
            "notes": pricing_offers.get("notes", [])
        }

    if positioning_signals:
        result["positioningSignals"] = positioning_signals

    confidence = 0.55

    if h1:
        confidence += 0.15

    if main_text and len(main_text) > 300:
        confidence += 0.15

    if title or meta_description:
        confidence += 0.1

    if prices:
        confidence += 0.05

    result["source"] = {
        "extractor": "Unknown General Extractor",
        "extractorFamily": "Unknown",
        "platformDetected": detected_platform,
        "confidence": round(min(0.95, confidence), 2)
    }

    return result

# -----------------------------------------------------------------------------
# V9 pricing parser overrides
# These definitions intentionally appear at the end of the module so they replace
# earlier conservative helpers above. They use block/row parsing before proximity.
# -----------------------------------------------------------------------------

PRICE_WITH_POS_RE = re.compile(
    r"(?P<currency>[$£€])\s*(?P<amount>\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?)\s*(?P<period>/\s*(?:mo|month|user|seat|check|hour|project)|per\s+(?:month|user|seat|project))?",
    re.I,
)


def extract_prices_with_positions(text):
    results = []
    for m in PRICE_WITH_POS_RE.finditer(text or ""):
        raw = clean_text(m.group(0)).replace("$ ", "$")
        currency = m.group("currency")
        amount_s = (m.group("amount") or "").replace(",", "")
        period = clean_text(m.group("period") or "") or None
        if period:
            period = period.replace(" ", "")
            period = period.replace("permonth", "/mo").replace("peruser", "/user").replace("perseat", "/seat")
        try:
            amount = float(amount_s)
        except Exception:
            continue
        results.append({
            "price": {
                "currency": currency,
                "amount": amount,
                "period": period,
                "raw": raw,
            },
            "start": m.start(),
            "end": m.end(),
            "raw": raw,
        })
    return results


def is_core_recurring_price(price_obj):
    if not isinstance(price_obj, dict):
        return False
    amount = price_obj.get("amount")
    period = (price_obj.get("period") or "").lower()
    raw = (price_obj.get("raw") or "").lower()
    if not isinstance(amount, (int, float)) or amount <= 0:
        return False
    if any(x in period for x in ["check", "token", "mtok", "hour", "project"]):
        return False
    if any(x in raw for x in ["/check", "mtok", "token", "session-hour", "container"]):
        return False
    return bool(period and any(x in period for x in ["mo", "month", "user", "seat"]))


def meaningful_plan_positions(section, core_names):
    positions = []
    used = set()
    for name in core_names or []:
        key = name.lower()
        if key in used:
            continue
        for m in re.finditer(rf"\b{re.escape(name)}\b", section or "", flags=re.I):
            pos = m.start()
            before = section[max(0, pos - 120):pos].lower()
            after = section[pos:pos + 260].lower()
            if any(x in before for x in ["footer", "privacy", "terms", "resources", "core tools", "free tools"]):
                continue
            if key == "enterprise" and after.startswith("enterprise scale"):
                # Still valid on Ahrefs pricing; do not skip it, but allow later local mapping.
                pass
            positions.append((name, pos))
            used.add(key)
            break
    positions.sort(key=lambda x: x[1])
    return positions


def map_horizontal_price_row_v9(section, core_names):
    """
    Handles horizontal cards where names appear first, then a row of prices.
    Example: Lite / Standard / Advanced ... $129/mo $249/mo $449/mo.
    """
    positions = meaningful_plan_positions(section, core_names)
    if len(positions) < 2:
        return {}

    price_hits = [p for p in extract_prices_with_positions(section) if is_core_recurring_price(p["price"])]
    if not price_hits:
        return {}

    first_price_pos = price_hits[0]["start"]
    names_before_prices = [(n, p) for n, p in positions if p < first_price_pos]

    if len(names_before_prices) < 2:
        return {}

    # Keep only the compact name cluster immediately before the first price row.
    cluster = []
    last = None
    for name, pos in names_before_prices:
        if last is None or pos - last <= 520:
            cluster.append((name, pos))
            last = pos
        else:
            cluster = [(name, pos)]
            last = pos

    if len(cluster) < 2:
        return {}

    start = cluster[-1][1]
    row = section[start:start + 1000]
    row_l = row.lower()
    cut = len(row)
    for marker in [
        "get started get started",
        "5 projects",
        "20 projects",
        "50 projects",
        "1 user included",
        "what's included",
        "what’s included",
        "all lite features",
        "all standard features",
    ]:
        pos = row_l.find(marker)
        if pos > 0:
            cut = min(cut, pos)
    row = row[:cut]

    row_prices = [p["price"] for p in extract_prices_with_positions(row) if is_core_recurring_price(p["price"])]
    if len(row_prices) < len(cluster):
        return {}

    # Exclude obvious add-on/user fees when a true high-price ladder exists.
    high_count = sum(1 for p in row_prices if p.get("amount", 0) >= 100)
    if high_count >= len(cluster):
        row_prices = [p for p in row_prices if p.get("amount", 0) >= 100]

    if len(row_prices) < len(cluster):
        return {}

    mapping = {}
    for (name, _), price in zip(cluster, row_prices):
        mapping[name.lower()] = price
    return mapping


def map_plan_local_block_v9(section, name, next_names=None):
    """Map one plan using its own block until next known plan/addon/standalone heading."""
    m = re.search(rf"\b{re.escape(name)}\b", section or "", flags=re.I)
    if not m:
        return None
    start = m.start()
    end = min(len(section), start + 1100)

    # Cut at next known heading after this plan.
    for other in next_names or []:
        if other.lower() == name.lower():
            continue
        om = re.search(rf"\b{re.escape(other)}\b", section[start + len(name):], flags=re.I)
        if om:
            candidate_end = start + len(name) + om.start()
            if start + 40 < candidate_end < end:
                end = candidate_end
    block = section[start:end]
    block_l = block.lower()

    if name.lower() in ["free", "hobby", "ahrefs free"]:
        if "free" in block_l or re.search(r"\$\s*0\b", block_l):
            return {"currency": None, "amount": 0, "period": None, "raw": "Free"}

    if name.lower() == "enterprise":
        prices = [p["price"] for p in extract_prices_with_positions(block) if is_core_recurring_price(p["price"])]
        high = [p for p in prices if p.get("amount", 0) >= 500]
        if high:
            return high[0]
        if any(x in block_l for x in ["custom", "contact sales", "talk to sales", "tailored"]):
            return {"currency": None, "amount": None, "period": None, "raw": "Custom"}

    prices = [p["price"] for p in extract_prices_with_positions(block) if is_core_recurring_price(p["price"])]
    if not prices:
        return None

    # Avoid add-on/user fees for named high-tier core plans if the block talks about additional users.
    filtered = []
    for p in prices:
        amount = p.get("amount")
        raw_l = (p.get("raw") or "").lower()
        if amount and amount < 100 and any(x in block_l for x in ["additional user", "add ", "add-on", "addon", "overage"]):
            continue
        if any(x in raw_l for x in ["/check", "token", "mtok"]):
            continue
        filtered.append(p)
    return (filtered or prices)[0]


def map_core_prices_by_order(text, core_names):
    """V9: block/row-based core plan mapping, safer than nearest price."""
    if not core_names:
        return {}

    section = get_main_pricing_section(text)
    mapping = map_horizontal_price_row_v9(section, core_names)

    # Fill any remaining plans from their own local block only.
    for name in core_names:
        key = name.lower()
        if key in mapping:
            continue
        local_price = map_plan_local_block_v9(section, name, core_names)
        if local_price:
            mapping[key] = local_price

    return mapping


def select_entity_price_from_block(text, name, entity_type="addon"):
    """Price mapping for add-ons/standalone products, cut to the local block."""
    section = text or ""
    m = re.search(rf"\b{re.escape(name)}\b", section, flags=re.I)
    if not m:
        return None, 0
    block = section[m.start():m.start() + 650]
    block_l = block.lower()

    if name.lower() in ["ahrefs free", "free"] and "free" in block_l:
        return {"currency": None, "amount": 0, "period": None, "raw": "Free"}, 8

    hits = [p["price"] for p in extract_prices_with_positions(block)]
    if not hits:
        return None, 0

    # Prefer recurring add-on/product price, not per-check/token if a monthly price exists.
    monthly = [p for p in hits if p.get("period") and "mo" in p.get("period", "").lower()]
    if monthly:
        return monthly[0], 6
    return hits[0], 4


def extract_addon_section(text):
    text = text or ""
    text_l = text.lower()
    starts = [
        "optional add-ons",
        "improve your plan with add-ons",
        "add-ons designed",
    ]
    start = -1
    for marker in starts:
        pos = text_l.find(marker)
        if pos >= 0:
            start = pos
            break
    if start < 0:
        return ""
    section = text[start:]
    section_l = section.lower()
    cut = len(section)
    for marker in ["compare plans", "questions?", "faq", "testimonials", "core tools", "legal info"]:
        pos = section_l.find(marker)
        if pos > 80:
            cut = min(cut, pos)
    return section[:cut]


def validate_core_plan_mapping(core_plans):
    """V9 validation: allow clean rising ladders; reject duplicates/sharp drops."""
    notes = []
    paid = []
    for plan in core_plans or []:
        price = plan.get("price")
        if isinstance(price, dict) and isinstance(price.get("amount"), (int, float)) and price.get("amount") > 0:
            paid.append((plan.get("name", ""), price.get("amount")))

    if not paid:
        return False, ["Core plan prices were not confidently mapped."]

    amounts = [a for _, a in paid]
    if any(amounts.count(x) >= 3 for x in set(amounts)):
        return False, ["Core plan price mapping was disabled because the same price was assigned to too many plans."]

    high_count = sum(1 for a in amounts if a >= 100)
    if high_count >= 2:
        for name, amount in paid:
            if name.lower() in ["standard", "advanced", "business", "guru", "pro+", "lite"] and amount < 100:
                return False, ["Core plan price mapping was disabled because a core plan was mapped to an add-on/user fee."]

    for prev, curr in zip(amounts, amounts[1:]):
        if prev >= 100 and curr < prev * 0.55:
            return False, ["Core plan price mapping was disabled because the plan ladder decreases suspiciously."]
    return True, notes


def build_pricing_offers(text, headings, prices):
    candidates = extract_pricing_candidates(headings, text)
    core_names = unique_clean_names([c["name"] for c in candidates if c["type"] == "core_plan"])
    addon_names = unique_clean_names([c["name"] for c in candidates if c["type"] == "addon"])
    standalone_names = unique_clean_names([c["name"] for c in candidates if c["type"] == "standalone_product"])
    core_names.sort(key=lambda n: CORE_PLAN_PRIORITY.get(n.lower(), 99))

    ordered_mapping = map_core_prices_by_order(text, core_names)
    core_plans = []
    for name in core_names:
        price = ordered_mapping.get(name.lower())
        if price:
            raw = str(price.get("raw") or "").lower()
            amount = price.get("amount")
            confidence = 0.88 if amount or raw == "custom" else 0.72
            core_plans.append({
                "name": name,
                "type": "core_plan",
                "price": price,
                "confidence": confidence,
                "source": "core_plan_block_mapping",
            })
        else:
            core_plans.append({
                "name": name,
                "type": "core_plan",
                "price": None,
                "confidence": 0.45,
                "source": "core_plan_name_only",
            })

    valid, notes = validate_core_plan_mapping(core_plans)
    if not valid:
        core_plans, notes = disable_core_plan_prices(core_plans, notes)

    addon_section = extract_addon_section(text)
    addons = []
    for name in addon_names:
        p, score = select_entity_price_from_block(addon_section or text, name, "addon")
        addons.append({
            "name": name,
            "type": "addon",
            "price": p if score >= 4 else None,
            "confidence": 0.72 if score >= 4 else 0.45,
            "source": "addon_block_mapping",
        })

    standalone = []
    for name in standalone_names:
        p, score = select_entity_price_from_block(text, name, "standalone_product")
        # Ahrefs Free is really free; prevent Brand Radar's $199 from leaking into it.
        if name.lower() in ["ahrefs free", "free"]:
            p = {"currency": None, "amount": 0, "period": None, "raw": "Free"}
            score = 8
        standalone.append({
            "name": name,
            "type": "standalone_product",
            "price": p if score >= 4 else None,
            "confidence": 0.72 if score >= 4 else 0.45,
            "source": "standalone_block_mapping",
        })

    priced_core = [p for p in core_plans if isinstance(p.get("price"), dict)]
    if valid and len(priced_core) >= max(2, min(3, len(core_plans))):
        confidence = "high_clean"
    elif priced_core:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "corePlans": core_plans[:10],
        "addOns": addons[:12],
        "standaloneProducts": standalone[:12],
        "planNames": [p["name"] for p in core_plans[:10]],
        "planMappingConfidence": confidence,
        "notes": notes,
    }


def estimate_main_plan_price_range(prices, core_plans=None, text=None):
    core_amounts = []
    for plan in core_plans or []:
        price = plan.get("price")
        if isinstance(price, dict) and isinstance(price.get("amount"), (int, float)) and price.get("amount") > 0:
            core_amounts.append(price.get("amount"))
    if core_amounts:
        return min(core_amounts), max(core_amounts)
    return None, None


# =============================================================================
# V10 PRICING OVERRIDES
# -----------------------------------------------------------------------------
# These definitions intentionally override the earlier v9 helpers. The key change
# is strict plan-block segmentation: each plan is priced only from the text between
# its own heading and the next plan heading. Horizontal price rows are handled as a
# separate case before local blocks.
# =============================================================================


def normalize_period_v10(period):
    period = clean_text(period or "").lower()
    period = period.replace(" ", "")
    period = period.replace("/", "")

    if period in ["mo", "month", "permonth"]:
        return "/mo"
    if period in ["yr", "year", "peryear"]:
        return "/yr"
    if period in ["user", "peruser"]:
        return "/user"
    if period in ["seat", "perseat"]:
        return "/seat"
    if period in ["check", "percheck"]:
        return "/check"
    if period in ["hour", "perhour"]:
        return "/hour"
    if period in ["project", "perproject"]:
        return "/project"
    return None


PRICE_WITH_POS_RE = re.compile(
    r"(?P<currency>[$£€])\s*(?P<amount>\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?)\s*(?P<period>/\s*(?:mo|month|user|seat|yr|year|check|hour|project)|per\s+(?:month|user|seat|year|project|check|hour))?",
    re.I,
)


def extract_prices_with_positions(text):
    """V10: price extraction with robust decimal and period normalization."""
    prepared = (text or "").replace("$ ", "$")
    prepared = prepared.replace(" .", ".")
    prepared = re.sub(r"(\d)\s*\.\s*(\d)", r"\1.\2", prepared)

    results = []
    seen = set()
    for m in PRICE_WITH_POS_RE.finditer(prepared):
        raw = normalize_price_raw(m.group(0))
        currency = m.group("currency")
        amount_s = (m.group("amount") or "").replace(",", "")
        try:
            amount = float(amount_s)
        except Exception:
            continue

        period = normalize_period_v10(m.group("period"))
        key = (currency, amount, period, raw.lower(), m.start())
        if key in seen:
            continue
        seen.add(key)

        results.append({
            "price": {
                "currency": currency,
                "amount": amount,
                "period": period,
                "raw": raw,
            },
            "start": m.start(),
            "end": m.end(),
            "raw": raw,
        })
    return results


def is_core_recurring_price(price_obj):
    if not isinstance(price_obj, dict):
        return False
    amount = price_obj.get("amount")
    period = (price_obj.get("period") or "").lower()
    raw = (price_obj.get("raw") or "").lower()

    if not isinstance(amount, (int, float)) or amount <= 0:
        return False
    if any(x in period for x in ["check", "token", "mtok", "hour", "project"]):
        return False
    if any(x in raw for x in ["/check", "mtok", "token", "session-hour", "container"]):
        return False

    # Accept monthly, user, and seat prices because SaaS team plans often use
    # per-seat or per-user labels.
    return bool(period and any(x in period for x in ["mo", "month", "user", "seat"]))


def get_main_pricing_section(text):
    """V10: start after nav/header and stop before add-ons/comparison/FAQ."""
    text = text or ""
    text_l = text.lower()

    start_markers = [
        "ahrefs plans & pricing",
        "seo classic plans",
        "seo + ai search",
        "pricing monthly yearly",
        "pricing individual team & enterprise api",
        "monthly yearly hobby",
        "plans & pricing",
    ]

    start = 0
    for marker in start_markers:
        pos = text_l.find(marker)
        if pos >= 0:
            start = pos
            break

    section = text[start:]
    section_l = section.lower()

    end_markers = [
        "optional add-ons",
        "improve your plan with add-ons",
        "compare plans & features",
        "compare plans",
        "compare features across plans",
        "questions? we have answers",
        "questions & answers",
        "faq",
        "testimonials",
        "starter see what people search",
        "ahrefs free get ahrefs data",
        "brand radar ai research",
        "custom prompt packages",
        "education plan",
        "pricing for claude platform features",
        "start building",
    ]

    end = len(section)
    for marker in end_markers:
        pos = section_l.find(marker)
        if pos > 120:
            end = min(end, pos)

    return section[:end]


def get_core_names_from_candidates_v10(candidates):
    """Preserve page order from headings; do not sort by generic priority."""
    return unique_clean_names([c["name"] for c in candidates if c.get("type") == "core_plan"])


def get_entity_positions_in_order(section, names):
    """Find one increasing position per name, following the order of headings."""
    positions = []
    cursor = 0
    section = section or ""

    for name in names or []:
        pattern = rf"\b{re.escape(name)}\b"
        best = None
        for m in re.finditer(pattern, section[cursor:], flags=re.I):
            pos = cursor + m.start()
            before = section[max(0, pos - 180):pos].lower()
            after = section[pos:pos + 500].lower()

            if any(x in before for x in ["footer", "privacy", "terms", "resources", "core tools", "free tools"]):
                continue

            # Avoid nav/tab labels where possible; prefer occurrences with pricing/card context.
            score = 0
            if re.search(r"[$£€]\s*\d", after):
                score += 4
            if re.search(r"\bfree\b|\bcustom\b|contact sales|talk to sales", after):
                score += 3
            if any(x in after for x in ["includes", "everything", "features", "websites", "usage", "projects", "keywords", "tracked", "seat", "user"]):
                score += 2
            if any(x in before[-80:] for x in ["toolkits", "pricing ", "product "]):
                score -= 1

            if best is None or score > best[1]:
                best = (pos, score)

            # Strong enough; take it to preserve order.
            if score >= 2:
                break

        if best is not None:
            positions.append((name, best[0]))
            cursor = best[0] + len(name)

    return positions


def extract_named_blocks(section, names):
    """Return blocks strictly bounded by the next selected entity heading."""
    positions = get_entity_positions_in_order(section, names)
    blocks = {}
    for idx, (name, pos) in enumerate(positions):
        end = positions[idx + 1][1] if idx + 1 < len(positions) else min(len(section), pos + 1600)
        blocks[name.lower()] = {
            "name": name,
            "start": pos,
            "end": end,
            "text": section[pos:end],
        }
    return blocks, positions


def block_has_explicit_free(block, name=None):
    block_l = (block or "").lower()
    name_l = (name or "").lower()

    if name_l in ["free", "hobby", "ahrefs free"]:
        # Free must appear before any paid amount.
        first_price = re.search(r"[$£€]\s*\d", block_l)
        free_pos = block_l.find("free")
        return free_pos >= 0 and (not first_price or free_pos < first_price.start())

    return False


def block_has_explicit_custom(block):
    block_l = (block or "").lower()
    first_price = re.search(r"[$£€]\s*\d", block_l)
    custom_candidates = ["custom", "contact sales", "talk to sales", "tailored", "request demo"]
    positions = [block_l.find(x) for x in custom_candidates if block_l.find(x) >= 0]
    if not positions:
        return False
    first_custom = min(positions)
    return not first_price or first_custom < first_price.start() + 80


def select_core_price_from_block(block, name=None):
    """Select a price only from a plan's own bounded block."""
    block = block or ""
    block_l = block.lower()
    name_l = (name or "").lower()

    if block_has_explicit_free(block, name):
        return {"currency": None, "amount": 0, "period": None, "raw": "Free"}, 7

    if name_l == "enterprise" and block_has_explicit_custom(block):
        return {"currency": None, "amount": None, "period": None, "raw": "Custom"}, 7

    prices = [p["price"] for p in extract_prices_with_positions(block) if is_core_recurring_price(p["price"])]

    if not prices:
        return None, 0

    filtered = []
    for p in prices:
        amount = p.get("amount")
        raw_l = (p.get("raw") or "").lower()
        period_l = (p.get("period") or "").lower()

        if any(x in raw_l for x in ["/check", "mtok", "token"]):
            continue

        # Avoid add-on and additional-user prices inside a plan card.
        if amount and amount < 100 and any(x in block_l for x in ["additional user", "add ", "add-on", "addon", "overage"]):
            continue

        # For enterprise, prefer high fixed plan price if present; otherwise per-seat is acceptable.
        if name_l == "enterprise" and amount and amount < 100 and "seat" not in period_l and "user" not in period_l:
            continue

        filtered.append(p)

    usable = filtered or prices

    if name_l == "enterprise":
        high = [p for p in usable if isinstance(p.get("amount"), (int, float)) and p.get("amount") >= 500]
        if high:
            return high[0], 9
        seat = [p for p in usable if (p.get("period") or "").lower() in ["/seat", "/user"]]
        if seat:
            return seat[0], 7

    return usable[0], 8


def map_horizontal_price_row_v10(section, core_names):
    """Map horizontal price rows like Ahrefs: Lite/Standard/Advanced then $129/$249/$449."""
    blocks, positions = extract_named_blocks(section, core_names)
    if len(positions) < 2:
        return {}

    price_hits = [p for p in extract_prices_with_positions(section) if is_core_recurring_price(p["price"])]
    if not price_hits:
        return {}

    first_price_pos = price_hits[0]["start"]
    names_before = [(n, p) for n, p in positions if p < first_price_pos]

    if len(names_before) < 2:
        return {}

    # Cursor-style pages are vertical; the first price appears inside the Individual block,
    # not in a compact shared price row. Require at least two prices before the first feature/CTA.
    row = section[first_price_pos:first_price_pos + 900]
    row_l = row.lower()
    cut = len(row)
    for marker in [
        "get started get started",
        "try for free",
        "subscribe",
        "5 projects",
        "20 projects",
        "50 projects",
        "what's inside",
        "what’s inside",
        "includes:",
        "everything in",
        "all lite features",
    ]:
        pos = row_l.find(marker)
        if pos > 0:
            cut = min(cut, pos)
    row = row[:cut]

    row_prices = [p["price"] for p in extract_prices_with_positions(row) if is_core_recurring_price(p["price"])]
    row_prices = [p for p in row_prices if isinstance(p.get("amount"), (int, float)) and p.get("amount") >= 50]

    if len(row_prices) < len(names_before):
        return {}

    # If there is a shared row, the number of prices should match the compact names before it.
    mapping = {}
    for (name, _), price in zip(names_before, row_prices):
        mapping[name.lower()] = price
    return mapping


def map_core_prices_by_order(text, core_names):
    """V10: horizontal row first, then strict local blocks."""
    if not core_names:
        return {}

    section = get_main_pricing_section(text)
    mapping = map_horizontal_price_row_v10(section, core_names)

    blocks, positions = extract_named_blocks(section, core_names)
    for name in core_names:
        key = name.lower()
        if key in mapping:
            continue
        block_data = blocks.get(key)
        if not block_data:
            continue
        price, score = select_core_price_from_block(block_data["text"], name)
        if score >= 6:
            mapping[key] = price

    return mapping


def select_entity_prices_from_ordered_blocks(section, names, entity_type="addon"):
    """Map add-ons or standalone products from their own bounded blocks."""
    blocks, positions = extract_named_blocks(section or "", names)
    output = {}
    for name in names or []:
        block_data = blocks.get(name.lower())
        if not block_data:
            output[name.lower()] = (None, 0)
            continue
        block = block_data["text"]
        block_l = block.lower()

        if name.lower() in ["ahrefs free", "free"] and "free" in block_l:
            output[name.lower()] = ({"currency": None, "amount": 0, "period": None, "raw": "Free"}, 8)
            continue

        if entity_type == "standalone_product" and block_has_explicit_free(block, name):
            output[name.lower()] = ({"currency": None, "amount": 0, "period": None, "raw": "Free"}, 8)
            continue

        hits = [p["price"] for p in extract_prices_with_positions(block)]
        if not hits:
            output[name.lower()] = (None, 0)
            continue

        monthly = [p for p in hits if (p.get("period") or "").lower() == "/mo"]
        usable = monthly or hits
        output[name.lower()] = (usable[0], 6)
    return output


def extract_addon_section(text):
    text = text or ""
    text_l = text.lower()
    starts = [
        "optional add-ons",
        "improve your plan with add-ons",
        "add-ons designed",
        "custom prompt packages",
    ]
    start = -1
    for marker in starts:
        pos = text_l.find(marker)
        if pos >= 0 and (start < 0 or pos < start):
            start = pos
    if start < 0:
        return ""
    section = text[start:]
    section_l = section.lower()
    cut = len(section)
    for marker in ["compare plans", "questions?", "faq", "testimonials", "core tools", "legal info"]:
        pos = section_l.find(marker)
        if pos > 80:
            cut = min(cut, pos)
    return section[:cut]


def validate_core_plan_mapping(core_plans):
    notes = []
    priced = []
    for plan in core_plans or []:
        price = plan.get("price")
        if isinstance(price, dict):
            amount = price.get("amount")
            raw = (price.get("raw") or "").lower()
            if raw == "custom" or amount == 0 or isinstance(amount, (int, float)):
                priced.append(plan)

    paid_amounts = [
        p.get("price", {}).get("amount")
        for p in priced
        if isinstance(p.get("price", {}).get("amount"), (int, float)) and p.get("price", {}).get("amount") > 0
    ]

    if not priced:
        return False, ["Core plan prices were not confidently mapped."]

    if any(paid_amounts.count(x) >= 3 for x in set(paid_amounts)):
        return False, ["Core plan price mapping was disabled because the same price was assigned to too many plans."]

    # Reject obvious leakage where a higher plan receives a tiny add-on/user fee while
    # true recurring plan prices exist elsewhere.
    if len([a for a in paid_amounts if a >= 100]) >= 2:
        for plan in core_plans or []:
            name = (plan.get("name") or "").lower()
            price = plan.get("price") or {}
            amount = price.get("amount")
            if name in ["standard", "advanced", "business", "guru", "pro+", "lite"] and isinstance(amount, (int, float)) and 0 < amount < 100:
                return False, ["Core plan price mapping was disabled because a core plan was mapped to an add-on/user fee."]

    return True, notes


def build_pricing_offers(text, headings, prices):
    candidates = extract_pricing_candidates(headings, text)
    core_names = get_core_names_from_candidates_v10(candidates)
    addon_names = unique_clean_names([c["name"] for c in candidates if c.get("type") == "addon"])
    standalone_names = unique_clean_names([c["name"] for c in candidates if c.get("type") == "standalone_product"])

    ordered_mapping = map_core_prices_by_order(text, core_names)
    core_plans = []
    for name in core_names:
        price = ordered_mapping.get(name.lower())
        if price:
            raw = str(price.get("raw") or "").lower()
            amount = price.get("amount")
            confidence = 0.88 if isinstance(amount, (int, float)) and amount > 0 else 0.72
            if raw == "custom":
                confidence = 0.78
            core_plans.append({
                "name": name,
                "type": "core_plan",
                "price": price,
                "confidence": confidence,
                "source": "core_plan_block_mapping",
            })
        else:
            core_plans.append({
                "name": name,
                "type": "core_plan",
                "price": None,
                "confidence": 0.45,
                "source": "core_plan_name_only",
            })

    valid, notes = validate_core_plan_mapping(core_plans)
    if not valid:
        core_plans, notes = disable_core_plan_prices(core_plans, notes)

    addon_section = extract_addon_section(text)
    addon_price_map = select_entity_prices_from_ordered_blocks(addon_section or text, addon_names, "addon")
    addons = []
    for name in addon_names:
        p, score = addon_price_map.get(name.lower(), (None, 0))
        addons.append({
            "name": name,
            "type": "addon",
            "price": p if score >= 4 else None,
            "confidence": 0.72 if score >= 4 else 0.45,
            "source": "addon_block_mapping",
        })

    standalone_price_map = select_entity_prices_from_ordered_blocks(text, standalone_names, "standalone_product")
    standalone = []
    for name in standalone_names:
        p, score = standalone_price_map.get(name.lower(), (None, 0))
        if name.lower() in ["ahrefs free", "free"]:
            p = {"currency": None, "amount": 0, "period": None, "raw": "Free"}
            score = 8
        standalone.append({
            "name": name,
            "type": "standalone_product",
            "price": p if score >= 4 else None,
            "confidence": 0.72 if score >= 4 else 0.45,
            "source": "standalone_block_mapping",
        })

    priced_core = [p for p in core_plans if isinstance(p.get("price"), dict)]
    if valid and len(priced_core) >= max(2, min(3, len(core_plans))):
        confidence = "high_clean"
    elif priced_core:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "corePlans": core_plans[:10],
        "addOns": addons[:12],
        "standaloneProducts": standalone[:12],
        "planNames": [p["name"] for p in core_plans[:10]],
        "planMappingConfidence": confidence,
        "notes": notes,
    }


def estimate_main_plan_price_range(prices, core_plans=None, text=None):
    core_amounts = []
    for plan in core_plans or []:
        price = plan.get("price")
        if isinstance(price, dict) and isinstance(price.get("amount"), (int, float)) and price.get("amount") > 0:
            core_amounts.append(price.get("amount"))
    if core_amounts:
        return min(core_amounts), max(core_amounts)
    return None, None

# -----------------------------------------------------------------------------
# V11 pricing/general overrides
# Goals:
# - Detect subscription/pricing pages even when the page is marketing-heavy.
# - Fix plan names containing symbols such as Pro+.
# - Add API pricing separation for token/MTok/hour/search pricing.
# - Add safer per-plan feature snippets and a lightweight comparison matrix.
# -----------------------------------------------------------------------------


def name_to_regex(name):
    """Safe fuzzy name matcher that works for names like Pro+ and Google AI Pro."""
    name = clean_text(name)
    parts = [re.escape(p) for p in name.split() if p]
    if not parts:
        return r"a^"
    body = r"\s+".join(parts)
    return rf"(?<![A-Za-z0-9]){body}(?![A-Za-z0-9])"


def get_entity_positions_in_order(section, names):
    """V11 override: preserve order and correctly match non-word plan names like Pro+."""
    positions = []
    cursor = 0
    section = section or ""

    for name in names or []:
        pattern = name_to_regex(name)
        best = None

        # Search from the current cursor first; fallback to whole section if needed.
        search_spans = [(cursor, section[cursor:]), (0, section)] if cursor > 0 else [(0, section)]

        for offset, haystack in search_spans:
            for m in re.finditer(pattern, haystack, flags=re.I):
                pos = offset + m.start()
                if any(abs(pos - existing_pos) < 3 for _, existing_pos in positions):
                    continue

                before = section[max(0, pos - 220):pos].lower()
                after = section[pos:pos + 700].lower()

                # Use full-phrase rejection to avoid false-positive matches.
                # "privacy mode" (plan feature) must NOT trigger — only "privacy policy" should.
                if any(x in before for x in ["footer", "privacy policy", "terms of service",
                                              "terms and conditions", "resources", "core tools", "free tools"]):
                    continue

                score = 0
                if re.search(r"[$£€]\s*\d", after):
                    score += 5
                if re.search(r"\bfree\b|\bcustom\b|contact sales|talk to sales|let.?s talk", after):
                    score += 4
                if any(x in after for x in [
                    "includes", "everything", "features", "websites", "usage", "projects",
                    "keywords", "tracked", "seat", "user", "storage", "cloud storage",
                    "per person", "per seat", "per month", "/ month", "/year", "billed"
                ]):
                    score += 3
                if any(x in after for x in ["compare plans", "compare features", "faq", "frequently asked"]):
                    score -= 2
                if any(x in before[-120:] for x in ["nav", "toolkits", "tabs", "product "]):
                    score -= 1

                if best is None or score > best[1]:
                    best = (pos, score)

                if score >= 3:
                    break
            if best and best[1] >= 3:
                break

        if best is not None:
            positions.append((name, best[0]))
            cursor = best[0] + len(name)

    positions.sort(key=lambda x: x[1])
    return positions


def extract_text_plan_candidates(text):
    """Find plan names that do not appear as headings, common on subscription landing pages."""
    text = text or ""
    text_l = text.lower()
    candidates = []

    known_sets = [
        ["Individual", "Family", "Premier"],               # Apple One service bundle
        ["Free", "Google AI Plus", "Google AI Pro", "Google AI Ultra"],
        ["Free", "Pro", "Max", "Team", "Enterprise"],
        ["Hobby", "Individual", "Teams", "Enterprise"],
        ["Lite", "Standard", "Advanced", "Enterprise"],
        ["SEO", "Pro+", "Advanced"],
        ["Pro", "Guru", "Business"],
        ["Free", "Pro", "Business", "Enterprise"],
    ]

    # Find the known_set with the most confirmed hits (not just first with >= 2).
    best_hits = []
    for plan_set in known_sets:
        hits = []
        for name in plan_set:
            if re.search(name_to_regex(name), text, flags=re.I):
                # Require local pricing or explicit free/custom context for confidence.
                m = re.search(name_to_regex(name), text, flags=re.I)
                local = text[m.start():m.start() + 800].lower() if m else ""
                if (
                    re.search(r"[$£€]\s*\d", local)
                    or re.search(r"\d[\d,]*\s*(?:rs|pkr)\s*/", local)  # Rs/PKR currency (Canva, Pakistan pricing)
                    or " free" in local[:250]
                    or "custom" in local[:350]
                    or "contact sales" in local[:500]
                    or "let’s talk" in local[:500]
                    or "let’s talk" in local[:500]
                ):
                    hits.append(name)
        if len(hits) >= 2 and len(hits) > len(best_hits):
            best_hits = hits
    for name in best_hits:
        candidates.append({"name": name, "type": "core_plan", "source": "text_pattern"})

    return candidates


def extract_pricing_candidates(headings, text):
    """V11 override: heading candidates plus text-pattern fallback for subscription pages."""
    candidates = []
    seen = set()

    for h in headings or []:
        name = normalize_plan_name(h.get("text"))
        kind = classify_pricing_heading(name, text)
        if kind == "ignore":
            continue
        key = (name.lower(), kind)
        if key in seen:
            continue
        seen.add(key)
        candidates.append({"name": name, "type": kind, "source": "heading"})

    for c in extract_text_plan_candidates(text):
        key = (c["name"].lower(), c["type"])
        if key not in seen:
            seen.add(key)
            candidates.append(c)

    return candidates


def get_main_pricing_section(text):
    """V11 override: include subscriptions pages and avoid API/add-on sections."""
    text = text or ""
    text_l = text.lower()

    start_markers = [
        "plans and pricing",
        "plans & pricing",
        "get more out of gemini",
        "upgrade not on a paid plan yet",
        "seo classic plans",
        "seo + ai search",
        "pricing monthly yearly",
        "pricing individual team & enterprise api",
        "monthly yearly hobby",
        "fast-track your creative vision",
    ]

    start = 0
    for marker in start_markers:
        pos = text_l.find(marker)
        if pos >= 0:
            start = pos
            break

    section = text[start:]
    section_l = section.lower()

    end_markers = [
        "optional add-ons",
        "improve your plan with add-ons",
        "compare plans & features",
        "compare plans",
        "compare features across plans",
        "compare features free",
        "questions? we have answers",
        "questions & answers",
        "frequently asked questions",
        "faq",
        "testimonials",
        "starter see what people search",
        "ahrefs free get ahrefs data",
        "brand radar ai research",
        "custom prompt packages",
        "education plan",
        "pricing for claude platform features",
        "start building",
        "looking for ai solutions",
        "unlock your creative potential",
        "you’ll also get access",
        "you'll also get access",
    ]

    end = len(section)
    for marker in end_markers:
        pos = section_l.find(marker)
        if pos > 160:
            end = min(end, pos)

    return section[:end]


def block_has_explicit_free(block, name=None):
    block_l = (block or "").lower()
    name_l = (name or "").lower()

    free_like_names = ["free", "hobby", "ahrefs free"]
    if name_l in free_like_names or " free " in f" {name_l} ":
        first_price = re.search(r"[$£€]\s*\d", block_l)
        free_pos = block_l.find("free")
        zero_pos = re.search(r"[$£€]\s*0\b|\b0\s*(?:rs|usd|gbp|eur)?\s*/", block_l)
        if zero_pos:
            return True
        return free_pos >= 0 and (not first_price or free_pos < first_price.start())

    return False


def is_core_recurring_price(price_obj):
    """V11 override: supports /year and Rs/year while rejecting usage-unit pricing."""
    if not isinstance(price_obj, dict):
        return False
    amount = price_obj.get("amount")
    period = (price_obj.get("period") or "").lower()
    raw = (price_obj.get("raw") or "").lower()
    if not isinstance(amount, (int, float)) or amount <= 0:
        return False
    if any(x in period for x in ["check", "token", "mtok", "hour", "project", "search"]):
        return False
    if any(x in raw for x in ["/check", "mtok", "token", "session-hour", "container", "1k searches"]):
        return False
    return bool(
        any(x in period for x in ["mo", "month", "user", "seat", "year", "yr"])
        or any(x in raw for x in ["/ month", "/month", "/ mo", "/mo", "/year", "per month", "per year", "rs /year", "rs/year"])
    )


def extract_prices_with_positions(text):
    """V11 override: supports currency-before and amount-before-currency formats."""
    results = []
    text = text or ""

    patterns = [
        re.compile(
            r"(?P<currency>[$£€])\s*(?P<amount>\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?)\s*(?P<period>/\s*(?:mo|month|user|seat|check|hour|project|year|yr)|per\s+(?:month|year|user|seat|project))?",
            re.I,
        ),
        re.compile(
            r"(?P<amount>\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?)\s*(?P<currency>Rs|PKR|USD|GBP|EUR)\s*(?P<period>/\s*(?:mo|month|user|seat|year|yr)|per\s+(?:month|year|user|seat))?",
            re.I,
        ),
    ]

    for pattern in patterns:
        for m in pattern.finditer(text):
            raw = clean_text(m.group(0)).replace("$ ", "$")
            currency = m.group("currency")
            amount_s = (m.group("amount") or "").replace(",", "")
            period = clean_text(m.group("period") or "") or None
            if period:
                period = period.replace(" ", "")
                period = period.replace("permonth", "/mo").replace("peryear", "/year").replace("peruser", "/user").replace("perseat", "/seat")
            try:
                amount = float(amount_s)
            except Exception:
                continue
            results.append({
                "price": {"currency": currency, "amount": amount, "period": period, "raw": raw},
                "start": m.start(),
                "end": m.end(),
                "raw": raw,
            })

    # Sort and remove duplicate exact spans/raw values.
    results.sort(key=lambda x: x["start"])
    deduped = []
    seen = set()
    for item in results:
        key = (item["start"], item["end"], item["raw"].lower())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def select_core_price_from_block(block, name=None):
    """V11 override: bounded plan-block price selection with Free/Custom and annual support."""
    block = block or ""
    block_l = block.lower()
    name_l = (name or "").lower()

    if block_has_explicit_free(block, name):
        return {"currency": None, "amount": 0, "period": None, "raw": "Free"}, 7

    if name_l == "enterprise" and block_has_explicit_custom(block):
        return {"currency": None, "amount": None, "period": None, "raw": "Custom"}, 7

    prices = [p["price"] for p in extract_prices_with_positions(block) if is_core_recurring_price(p["price"])]
    if not prices:
        # Some pages say “Let's talk” without literal custom.
        if name_l == "enterprise" and any(x in block_l for x in ["let’s talk", "let's talk", "get in touch", "contact sales"]):
            return {"currency": None, "amount": None, "period": None, "raw": "Custom"}, 6
        return None, 0

    filtered = []
    for p in prices:
        amount = p.get("amount")
        raw_l = (p.get("raw") or "").lower()
        period_l = (p.get("period") or "").lower()

        if any(x in raw_l for x in ["/check", "mtok", "token", "1k searches"]):
            continue
        if amount and amount < 100 and any(x in block_l for x in ["additional user", "add ", "add-on", "addon", "overage"]):
            continue
        if name_l == "enterprise" and amount and amount < 100 and "seat" not in period_l and "user" not in period_l:
            continue
        filtered.append(p)

    usable = filtered or prices

    # Prefer explicit recurring base price over annual total shown in comparison text.
    monthly = [p for p in usable if any(x in (p.get("period") or "").lower() for x in ["mo", "month", "user", "seat"])]
    yearly = [p for p in usable if any(x in (p.get("period") or "").lower() for x in ["year", "yr"])]

    if name_l == "enterprise":
        high = [p for p in usable if isinstance(p.get("amount"), (int, float)) and p.get("amount") >= 500]
        if high:
            return high[0], 9
        seat = [p for p in usable if (p.get("period") or "").lower() in ["/seat", "/user"]]
        if seat:
            return seat[0], 7

    if monthly:
        return monthly[0], 8
    if yearly:
        return yearly[0], 8
    return usable[0], 7


def extract_plan_features(text, core_plans):
    """V11: extract compact feature snippets and simple numeric limits per plan."""
    if not text or not core_plans:
        return {}

    section = get_main_pricing_section(text)
    names = [p.get("name") for p in core_plans if p.get("name")]
    blocks, _ = extract_named_blocks(section, names)
    output = {}

    numeric_patterns = {
        "projects": r"(\d[\d,]*)\s+projects?",
        "trackedKeywords": r"(\d[\d,]*)\s+(?:tracked\s+)?keywords?(?:\s+to\s+track)?",
        "trackedPrompts": r"(\d[\d,]*)\s+(?:tracked\s+)?prompts?(?:\s+to\s+track)?",
        "crawlCredits": r"(\d[\d,]*)\s+crawl credits",
        "usersIncluded": r"(\d[\d,]*)\s+users? included|included users\s+(\d[\d,]*)",
        "websitesToMonitor": r"(?:up to\s+)?(\d[\d,]*)\s+websites? to monitor",
        "storage": r"(\d[\d,]*(?:\.\d+)?)\s*(gb|tb)\s+of cloud storage|storage\s+(\d[\d,]*(?:\.\d+)?)\s*(gb|tb)",
        "brandKits": r"(\d[\d,]*)\s+brand kits?",
        "templates": r"(\d[\d,.]*\s*[mk]\+?)\s+templates",
    }

    stop_tokens = ["get started", "try for free", "start a free trial", "contact sales", "book a demo"]

    for plan in core_plans:
        name = plan.get("name")
        data = blocks.get((name or "").lower())
        if not data:
            continue
        block = data["text"]
        block_l = block.lower()
        found = {}

        for key, pattern in numeric_patterns.items():
            pm = re.search(pattern, block, flags=re.I)
            if pm:
                groups = [g for g in pm.groups() if g]
                if groups:
                    value = groups[0]
                    if key == "storage" and len(groups) >= 2:
                        found[key] = f"{groups[0]} {groups[1].upper()}"
                    else:
                        try:
                            found[key] = int(value.replace(",", ""))
                        except Exception:
                            found[key] = value

        # Extract short textual features from checkmark/bullet-like content.
        sentences = re.split(r"(?:✓|•|\n|\.\s+)", block)
        snippets = []
        for s in sentences:
            s = clean_text(s)
            if not s or len(s) < 8 or len(s) > 120:
                continue
            s_l = s.lower()
            if s_l == name.lower() or any(tok in s_l for tok in stop_tokens):
                continue
            if any(x in s_l for x in [
                "includes", "everything in", "access", "storage", "templates", "brand kit",
                "usage", "sso", "admin", "security", "projects", "keywords", "cloud",
                "collaboration", "analytics", "premium", "ai", "code", "audit"
            ]):
                snippets.append(s)
            if len(snippets) >= 8:
                break

        if snippets:
            found["featureSnippets"] = snippets

        if found:
            output[name] = found

    return output


def extract_api_pricing(text):
    """Separate API/token/usage pricing from subscription plan pricing."""
    text = text or ""
    text_l = text.lower()
    api = {"detected": False, "modelRates": [], "usageRates": []}

    # Model token rates such as: Opus 4.7 ... Input $5 / MTok Output $25 / MTok
    model_pattern = re.compile(
        r"(?P<model>(?:opus|sonnet|haiku)\s+[\d.]+)\s+.{0,120}?input\s*[$£€]\s*(?P<input>\d+(?:\.\d+)?)\s*/\s*mtok\s+output\s*[$£€]\s*(?P<output>\d+(?:\.\d+)?)\s*/\s*mtok",
        re.I,
    )
    for m in model_pattern.finditer(text):
        api["modelRates"].append({
            "model": clean_text(m.group("model")),
            "inputPerMTok": float(m.group("input")),
            "outputPerMTok": float(m.group("output")),
            "currency": "$",
        })

    usage_patterns = [
        ("webSearch", r"web search.{0,220}?cost\s*[$£€]\s*(\d+(?:\.\d+)?)\s*/\s*1k searches"),
        ("codeExecution", r"code execution.{0,260}?additional hours\s*[$£€]\s*(\d+(?:\.\d+)?)\s*per hour"),
        ("managedAgents", r"managed agents.{0,220}?cost\s*[$£€]\s*(\d+(?:\.\d+)?)\s*per session-hour"),
    ]
    for name, pattern in usage_patterns:
        m = re.search(pattern, text_l, flags=re.I)
        if m:
            api["usageRates"].append({"name": name, "amount": float(m.group(1)), "currency": "$"})

    api["detected"] = bool(api["modelRates"] or api["usageRates"] or "/ mtok" in text_l or "api pricing" in text_l)
    return api


def extract_pricing_comparison_matrix(text, core_plans, plan_features=None):
    """Lightweight comparison structure. Rows are conservative; full text remains available."""
    columns = [p.get("name") for p in core_plans or [] if p.get("name")]
    text_l = (text or "").lower()
    detected = bool(columns and any(x in text_l for x in ["compare plans", "compare features", "key features", "features and capabilities"]))

    rows = []
    plan_features = plan_features or {}
    feature_keys = sorted({k for v in plan_features.values() if isinstance(v, dict) for k in v.keys() if k != "featureSnippets"})
    for key in feature_keys[:20]:
        rows.append({
            "feature": key,
            "values": [plan_features.get(col, {}).get(key) for col in columns]
        })

    return {
        "detected": detected,
        "columns": columns,
        "rows": rows,
        "source": "plan_features_and_compare_text" if detected else None,
    }


def has_pricing_page_evidence(url, main_text, headings, prices, pricing_offers):
    url_l = (url or "").lower()
    text_l = (main_text or "").lower()
    plan_count = len(pricing_offers.get("planNames", []) if pricing_offers else [])
    recurring_count = len([
        p for p in prices or []
        if p.get("period") or any(x in (p.get("raw") or "").lower() for x in ["/ month", "/month", "/year", "per month", "per year"])
    ])
    if any(x in url_l for x in ["/pricing", "subscriptions", "plans"]):
        if plan_count >= 2 or recurring_count >= 2:
            return True
    if plan_count >= 2 and recurring_count >= 2:
        return True
    if any(x in text_l[:3000] for x in ["plans and pricing", "plans & pricing", "choose an option below", "monthly yearly", "monthly annually"]):
        return True
    return False


# =============================================================================
# V15 HELPERS — heading filter, Jina markdown CTAs, hosting intelligence
# =============================================================================

# Regex for navigation/mega-menu headings that pollute contentAngles on
# pricing and service-bundle pages.
_PRICING_NAV_HEADING_RE = re.compile(
    r"^(?:"
    r"digital design|print design|images? and photos?|videos? and audio"
    r"|canva ai|all canva ai|all canva for business|canva for business"
    r"|solutions|resources|help|create guides?|tools?|product|plans"
    r"|apple footer|shop and learn|apple wallet|services|account"
    r"|entertainment|icloud|iphone|mac|ipad|apple tv|apple watch"
    r"|accessories|support|explore apple|community|about apple"
    r"|legal|privacy policy|terms of service|terms of use|contact apple"
    r"|learn|videos|features"
    # Canva education/nav headings
    r"|education|k-12 education|k-12 teachers|higher education"
    r"|canva for education|canva for campus|campus solutions"
    r"|about|inspiration|reports|business plans|nonprofits"
    r"|newsroom|careers|developers|affiliates|design school"
    # Generic footer/nav labels
    r"|company|social|download|get the app|follow us|connect"
    r"|copyright|all rights reserved"
    r")$",
    re.I,
)


def _filter_nav_headings_for_pricing_page(headings):
    """Remove mega-menu/footer headings that pollute contentAngles on pricing/bundle pages."""
    filtered = []
    for h in headings:
        text = (h.get("text") or "").strip()
        text_l = text.lower()
        # Drop known nav pattern headings
        if _PRICING_NAV_HEADING_RE.match(text_l):
            continue
        # Drop "All <Category>" nav expansion links (e.g., "All Canva AI", "All solutions")
        if re.match(r"^all\s+\w", text_l) and len(text.split()) <= 4:
            continue
        filtered.append(h)
    return filtered


# Action words that identify a markdown link as a CTA (first word of link text).
_JINA_CTA_FIRST_WORDS = {
    "explore", "view", "start", "get", "try", "buy", "order", "shop",
    "book", "sign", "learn", "see", "discover", "compare",
    "check", "find", "download", "access", "join", "create",
    "talk", "chat", "schedule", "request", "upgrade",
    # Note: "contact" removed — bare [Contact](url) nav links pass through as noise.
    # Kept in set for compound texts ("contact sales", "contact our team").
}

# Exact link-text values to reject when parsing Jina markdown CTAs.
_JINA_CTA_REJECT_EXACT = {
    "about us", "our team", "why us", "clients", "portfolio",
    "billing area", "announcement", "generate a lead", "acceptable use policy",
    "privacy policy", "feedback", "sitemap", "open a ticket",
    "knowledgebase articles", "network status", "faq's", "payment method",
    "careers", "investor relations", "terms of service", "terms of use",
    "accessibility", "cookie policy", "legal",
    # Apple FAQ inline links
    "tap or click here to sign up on our app store",
    "tap or click here to learn more",
    "tap or click here to sign up",
    "tap or click here",
    # App store links
    "download on the app store", "get it on google play",
    "available on the app store",
    # Generic noise
    "my account", "blog", "refund policy", "careers",
    # Issue 8: Nav links that pass CTA filters but are not conversion CTAs.
    # Bare "contact" = navbar link; "contact us" typically from FAQ/footer text.
    "contact", "contact us",
    # Cursor sidebar / community / support links
    "workshops", "forum", "docs", "changelog", "security",
    # Generic single-word nav links
    "enterprise", "pricing", "features", "solutions",
}


def _extract_jina_markdown_ctas(text, base_url):
    """Parse [text](url) markdown links from Jina-rendered content as CTAs.

    Jina Reader converts HTML → markdown, so anchor tags become [text](url).
    BeautifulSoup sees these as plain text, not <a> elements, so extract_ctas()
    misses them.  This function recovers those CTA-intent links.
    """
    if not text or "[" not in text or "](" not in text:
        return []

    ctas = []
    seen = set()

    for m in re.finditer(r'\[([^\]]{2,80})\]\((https?://[^)]{5,300})\)', text):
        link_text = clean_text(m.group(1))
        href = m.group(2).strip()

        if not link_text or not href:
            continue

        text_l = link_text.lower().strip()

        # Reject known footer/utility link texts
        if text_l in _JINA_CTA_REJECT_EXACT:
            continue
        if text_l in _CTA_REJECT_EXACT_TEXTS:
            continue

        # Reject utility URL patterns
        href_l = href.lower()
        if any(sub in href_l for sub in _CTA_REJECT_URL_SUBSTRINGS):
            continue

        # Must start with an action word OR reference pricing/hosting intent.
        # "contact" alone is rejected by _JINA_CTA_REJECT_EXACT above; compound
        # "contact sales" passes through via "plan"/"today" keyword OR first_word="contact".
        first_word = text_l.split()[0] if text_l else ""
        has_action = (
            first_word in _JINA_CTA_FIRST_WORDS
            # "contact" compound phrases ("contact sales", "contact our team")
            or (first_word == "contact" and len(text_l.split()) >= 2)
            or any(t in text_l for t in [
                "plan", "pricing", "hosting", "migration", "trial",
                "demo", "option", "today", "now",
            ])
        )
        if not has_action:
            continue

        # Deduplicate by normalised text AND by URL (different texts, same URL = nav link)
        key = text_l
        url_key = href.split("?")[0].rstrip("/")  # strip query params + trailing slash
        if key in seen or url_key in seen:
            continue
        seen.add(key)
        seen.add(url_key)

        ctas.append({"text": link_text, "url": href, "source": "jina_markdown"})

    return ctas[:14]  # Issue 5: bumped from 10 so "Explore detailed pricing" isn't cut off


def _extract_hosting_intelligence(text, url):
    """Extract structured hosting/service-pricing intelligence from page text.

    Used when a page describes web-hosting services but may not expose
    explicit plan prices.  Detects features, guarantees, support model,
    security features, and migration offers.
    Returns a dict; result["detected"] is False when the page is not hosting.
    """
    text_l = (text or "").lower()
    url_l = (url or "").lower()

    # Detect hosting context from URL or content
    _hosting_url = any(x in url_l for x in [
        "/hosting", "/web-hosting", "/shared-hosting", "/vps", "/dedicated", "/reseller",
    ])
    _hosting_content = any(x in text_l for x in [
        "web hosting", "hosting plan", "nvme storage", "litespeed",
        "uptime guarantee", "domain hosting", "cpanel", "plesk",
        "unlimited bandwidth", "managed hosting",
    ])

    if not _hosting_url and not _hosting_content:
        return {"detected": False}

    intel = {
        "detected": True,
        "pricingPage": True,
        "industryPricingType": "web_hosting",
    }

    # ── Hosting features ──────────────────────────────────────────────────────
    feature_checks = [
        (r"7[- ]?day free trial", "7-Day Free Trial Available"),
        (r"nvme storage|nvme ssd", "NVMe Storage & Unlimited Bandwidth"),
        (r"litespeed\s*(?:server|cache|lscache)?", "LiteSpeed Server & LSCache"),
        (r"dedicated resources", "Dedicated Resources"),
        (r"free ssl", "Free SSL"),
        (r"whois privacy", "WHOIS Privacy"),
        (r"malware scanner", "Malware Scanner"),
        (r"ddos protection", "Free DDoS Protection & Backup Recovery"),
        (r"unlimited bandwidth", "Unlimited Bandwidth"),
        (r"local telephonic support", "Local Telephonic Support"),
    ]
    # Dynamic: "100,000+ Websites Managed" style
    wm = re.search(r"(\d[\d,]+\+?\s*websites?\s*managed)", text, re.I)
    if wm:
        feature_checks.append((None, clean_text(wm.group(1))))

    hosting_features = []
    seen_f = set()
    for item in feature_checks:
        pattern, label = item if len(item) == 2 else (None, item)
        if pattern is None:
            if label not in seen_f:
                hosting_features.append(label)
                seen_f.add(label)
        elif re.search(pattern, text_l) and label not in seen_f:
            hosting_features.append(label)
            seen_f.add(label)

    if hosting_features:
        intel["hostingFeatures"] = hosting_features

    # ── Guarantees ────────────────────────────────────────────────────────────
    guarantee_checks = [
        (r"100[\s-]?day\s*(?:hosting\s*)?guarantee", "100 Day Hosting Guarantee"),
        (r"100[\s-]?day\s*money\s*back", "100 day money back guarantee"),
        (r"99\.9+%\s*uptime", "99.9% Uptime Guarantee"),
        (r"30[\s-]?day\s*money\s*back", "30 day money back guarantee"),
    ]
    guarantees = []
    seen_g = set()
    for pattern, label in guarantee_checks:
        if re.search(pattern, text_l) and label not in seen_g:
            guarantees.append(label)
            seen_g.add(label)
    if guarantees:
        intel["guarantees"] = guarantees

    # ── Migration offer ───────────────────────────────────────────────────────
    if any(x in text_l for x in ["free migration", "free website migration", "start migration"]):
        migration = {"freeMigration": True}
        if "start migration" in text_l:
            migration["cta"] = "Start Migration"
        intel["migration"] = migration

    # ── Support model ─────────────────────────────────────────────────────────
    support_checks = [
        (r"local telephonic support", "Local Telephonic Support"),
        (r"quick ticket response", "Quick Ticket Response"),
        (r"multilingual team", "Multilingual Team"),
        (r"direct csr access", "Direct CSR Access"),
        (r"24/7 support", "24/7 Support"),
        (r"live chat", "Live Chat Support"),
    ]
    support_model = []
    seen_s = set()
    for pattern, label in support_checks:
        if re.search(pattern, text_l) and label not in seen_s:
            support_model.append(label)
            seen_s.add(label)
    if support_model:
        intel["supportModel"] = support_model

    # ── Security features ─────────────────────────────────────────────────────
    security_checks = [
        (r"free ssl", "Free SSL"),
        (r"whois privacy", "WHOIS Privacy"),
        (r"malware scanner", "Malware Scanner"),
        (r"firewall", "Firewall"),
        (r"ip\s*(?:&|and)\s*country blocking", "IP & Country Blocking"),
        (r"ddos protection", "DDoS Protection"),
        (r"backup recovery", "Backup Recovery"),
    ]
    security_features = []
    seen_sec = set()
    for pattern, label in security_checks:
        if re.search(pattern, text_l) and label not in seen_sec:
            security_features.append(label)
            seen_sec.add(label)
    if security_features:
        intel["securityFeatures"] = security_features

    return intel


# Hosting plan badge patterns — prefix that appears before the plan name card.
# e.g. "STARTER Startup", "BEST VALUE Grow", "RECOMMENDED Digital", "POWERFUL Business"
_HOSTING_BADGE_RE = re.compile(
    r"(?:STARTER|BEST\s+VA(?:LUE)?|RECOMMENDED|POWERFUL|POPULAR|MOST\s+POPULAR|"
    r"BASIC|ECONOMY|PRO|PREMIUM|ADVANCED|ULTIMATE|ENTERPRISE)\s+(\w[\w\s-]{1,30}?)"
    r"(?=\s+Save\s+\d|\s+\d{2,}\.|\s+Get\s+Started|\s+\$)",
    re.I,
)

# Bare decimal price pattern for hosting pages (no currency symbol)
# Matches: "59.46", "35.68/yr", "159.46/year", "35.68 /yr"
_HOSTING_BARE_PRICE_RE = re.compile(
    r"(?<!\d)(\d{2,4}\.\d{2})\s*(/yr|/year|/mo|/month)?(?!\d)",
    re.I,
)

# Renewal price pattern: "59.46/yr when you renew"
_HOSTING_RENEWAL_RE = re.compile(
    r"(\d{2,4}\.\d{2})\s*/yr\s+when\s+you\s+renew",
    re.I,
)

# Save percentage: "Save 40%"
_HOSTING_SAVE_RE = re.compile(r"Save\s+(\d{1,2})%", re.I)

# Storage line: "50GB SSD Storage", "100GB NVMe Storage"
_HOSTING_STORAGE_RE = re.compile(r"(\d+\s*(?:GB|TB))\s+(?:SSD|NVMe|HDD)?\s*Storage", re.I)

# Websites count: "5 Websites", "100 Websites", "Unlimited Websites"
_HOSTING_WEBSITES_RE = re.compile(r"(\d+|Unlimited)\s+Websites?", re.I)

# Feature include/exclude: "AI Website Builder: Not Included", "AI Website Builder Included"
_HOSTING_AI_BUILDER_RE = re.compile(
    r"AI\s+Website\s+Builder.*?(Not\s+Included|Included|Powerful)", re.I
)

# cPanel access: "Standard cPanel Access", "cPanel with SSH Access"
_HOSTING_CPANEL_RE = re.compile(
    r"(Standard cPanel Access|cPanel with SSH Access|cPanel Access)", re.I
)

# NodeJS: "NodeJs: Not Supported", "NodeJs Supported"
_HOSTING_NODEJS_RE = re.compile(r"NodeJs[:\s]+(Not\s+Supported|Supported)", re.I)


def _extract_websouls_hosting_plans(text):
    """Parse Websouls-style hosting plan cards from plain text.

    Scopes to the section starting at 'Web Hosting Plans and Pricing'
    and ending before 'Money Back Guarantee' or '100 Day Risk Free'.
    Returns a list of plan dicts, or [] if not a Websouls-style page.
    """
    text = text or ""
    # Find pricing section boundaries
    start_m = re.search(r"Web\s+Hosting\s+Plans\s+and\s+Pricing", text, re.I)
    if not start_m:
        return []
    pricing_block = text[start_m.start():]

    # Stop before guarantee/footer section
    stop_m = re.search(
        r"Money\s+Back\s+Guarantee|100\s+Day\s+Risk\s+Free|100\s+Day\s+Hosting\s+Guarantee",
        pricing_block, re.I,
    )
    if stop_m:
        pricing_block = pricing_block[:stop_m.start()]

    # Identify plan card start positions using badge pattern
    # Badge+name pairs:  "STARTER Startup", "BEST VALUE Grow", etc.
    _plan_card_re = re.compile(
        r"(?:STARTER|BEST\s+VA(?:LUE)?|RECOMMENDED|POWERFUL|POPULAR|MOST\s+POPULAR)"
        r"\s+(\w[\w\s-]{1,30}?)\s+Save\s+(\d{1,2})%",
        re.I,
    )
    card_matches = list(_plan_card_re.finditer(pricing_block))
    if not card_matches:
        return []

    plans = []
    for idx, m in enumerate(card_matches):
        plan_name = clean_text(m.group(1))
        discount_pct = int(m.group(2))
        badge_text = m.group(0).split()[0].upper()  # STARTER / BEST / RECOMMENDED / POWERFUL

        # Slice plan block: from badge match to next badge match (or end)
        block_start = m.start()
        block_end = card_matches[idx + 1].start() if idx + 1 < len(card_matches) else len(pricing_block)
        block = pricing_block[block_start:block_end]

        # Extract prices: first two bare decimals after badge are regularPrice then salePrice/yr
        prices_found = list(_HOSTING_BARE_PRICE_RE.finditer(block))
        regular_price = None
        sale_price = None
        renewal_price = None

        if len(prices_found) >= 2:
            regular_price = float(prices_found[0].group(1))
            sale_price = float(prices_found[1].group(1))

        # Renewal price: "59.46/yr when you renew"
        renewal_m = _HOSTING_RENEWAL_RE.search(block)
        if renewal_m:
            renewal_price = float(renewal_m.group(1))
        elif regular_price:
            renewal_price = regular_price  # renewal = regular if not stated separately

        # Storage
        storage = None
        storage_m = _HOSTING_STORAGE_RE.search(block)
        if storage_m:
            storage = clean_text(storage_m.group(0))

        # Websites
        websites = None
        websites_m = _HOSTING_WEBSITES_RE.search(block)
        if websites_m:
            websites_raw = websites_m.group(1).lower()
            websites = None if websites_raw == "unlimited" else int(websites_raw)

        # AI Website Builder
        # _HOSTING_AI_BUILDER_RE group(1) captures one of: "Not Included", "Included", "Powerful".
        # "included" in "not included" is True in Python, so we must use exact-match, NOT substring.
        ai_builder = False
        ai_m = _HOSTING_AI_BUILDER_RE.search(block)
        if ai_m:
            result_text = ai_m.group(1).strip().lower()
            ai_builder = result_text in ("included", "powerful")

        # cPanel
        cpanel = None
        cpanel_m = _HOSTING_CPANEL_RE.search(block)
        if cpanel_m:
            cpanel = clean_text(cpanel_m.group(1))

        # NodeJS
        nodejs = False
        nodejs_m = _HOSTING_NODEJS_RE.search(block)
        if nodejs_m:
            nodejs = "not supported" not in nodejs_m.group(1).lower()

        # Boolean features (present = True, absent = False)
        block_l = block.lower()
        free_domain = "free domain" in block_l
        free_backup = "free backup" in block_l
        free_ssl = "free ssl" in block_l
        malware_scanning = "malware scanning" in block_l
        free_migration = "free website migration" in block_l
        free_trial = "7-days free trial" in block_l or "7-day free trial" in block_l
        whois_privacy = "whois privacy" in block_l
        unlimited_bandwidth = "unlimited bandwidth" in block_l
        local_support = "local telephonic support" in block_l

        # Databases
        databases = None
        db_m = re.search(r"(\d+|Unlimited)\s+Databases?", block, re.I)
        if db_m:
            databases = db_m.group(1)
            if databases.lower() != "unlimited":
                try:
                    databases = int(databases)
                except ValueError:
                    pass

        # Badge/category label
        badge_label_map = {
            "STARTER": "STARTER",
            "BEST": "BEST VALUE",
            "RECOMMENDED": "RECOMMENDED",
            "POWERFUL": "POWERFUL",
        }
        category = badge_label_map.get(badge_text, badge_text)

        plan = {
            "name": plan_name,
            "type": "core_plan",
            "category": category,
            "discount": f"Save {discount_pct}%",
            "confidence": 0.90,
            "source": "hosting_plan_card",
        }

        if sale_price is not None:
            plan["price"] = {
                "currency": None,
                "amount": sale_price,
                "period": "/yr",
                "raw": f"{sale_price}/yr",
            }
            plan["salePrice"] = sale_price
        if regular_price is not None:
            plan["regularPrice"] = regular_price
        if renewal_price is not None:
            plan["renewalPrice"] = renewal_price
        if storage:
            plan["storage"] = storage
        if websites is not None:
            plan["websites"] = websites
        plan["aiWebsiteBuilder"] = ai_builder
        plan["freeDomain"] = free_domain
        plan["localTelephonicSupport"] = local_support
        if unlimited_bandwidth:
            plan["bandwidth"] = "Unlimited"
        if databases is not None:
            plan["databases"] = databases
        plan["freeBackup"] = free_backup
        plan["freeSSL"] = free_ssl
        plan["malwareScanning"] = malware_scanning
        plan["freeWebsiteMigration"] = free_migration
        plan["freeTrial"] = free_trial
        plan["freeWhoisPrivacy"] = whois_privacy
        plan["nodeJsSupported"] = nodejs
        if cpanel:
            plan["cPanelAccess"] = cpanel

        plans.append(plan)

    return plans


_SEAT_PRICE_RE = re.compile(
    r"\$\s*(\d+(?:\.\d+)?)\s*(?:per\s+seat\s*/\s*month|/seat/mo|per\s+seat\s+per\s+month|/seat\s+/\s*month)",
    re.I,
)
_SEAT_PRICE_BILLED_RE = re.compile(
    r"\$\s*(\d+(?:\.\d+)?)\s*"
    r"(?:"
    r"per\s+seat\s*/\s*month(?:\s+if\s+billed\s+(annually|monthly))?"   # $20 per seat / month if billed annually
    r"|/?\s*month\s+if\s+billed\s+(annually|monthly)"                     # $25 if billed monthly
    r"|if\s+billed\s+(annually|monthly)"                                   # $25 if billed monthly (short form)
    r")",
    re.I,
)
_SEAT_TYPE_RE = re.compile(r"(Standard|Premium|Business|Professional)\s+seat", re.I)
_ENTERPRISE_SEAT_RE = re.compile(r"\$\s*(\d+(?:\.\d+)?)\s*/seat", re.I)


def _extract_seat_based_pricing(plan_name, block):
    """Extract seat-based pricing for Team/Enterprise plans.

    Handles patterns like:
        Standard seat   $20 per seat / month if billed annually   $25 if billed monthly
        Premium seat    $100 per seat / month if billed annually   $125 if billed monthly

    Returns a price dict and optional billing/seatTypes metadata.
    """
    block = block or ""
    seat_types = []
    current_seat_name = None
    annual_price = None
    monthly_price = None

    lines = re.split(r"\n|(?<=\))\s+(?=\$)|(?<=ly)\s+(?=[A-Z])", block)
    for line in lines:
        line_s = line.strip()
        st_m = _SEAT_TYPE_RE.search(line_s)
        if st_m and len(line_s) < 60:
            # Flush previous seat type
            if current_seat_name and annual_price:
                seat_types.append({
                    "name": current_seat_name,
                    "annualPrice": annual_price,
                    "monthlyPrice": monthly_price,
                })
            current_seat_name = clean_text(st_m.group(0))
            annual_price = None
            monthly_price = None
            continue

        # "$20 per seat / month if billed annually" or "$25 if billed monthly"
        for m in _SEAT_PRICE_BILLED_RE.finditer(line_s):
            amt = float(m.group(1))
            # Groups 2/3/4 carry the billing qualifier (annually/monthly) depending on which
            # alternation matched — find the first non-None qualifier group
            billing_qualifier = next(
                (g.lower() for g in (m.group(2), m.group(3), m.group(4)) if g), ""
            )
            if "annual" in billing_qualifier or ("annual" in line_s.lower() and "month" not in billing_qualifier):
                annual_price = amt
            elif "month" in billing_qualifier or "monthly" in line_s.lower():
                monthly_price = amt
            else:
                # No qualifier — first occurrence is usually annual
                if annual_price is None:
                    annual_price = amt
                else:
                    monthly_price = amt

    if current_seat_name and annual_price:
        seat_types.append({
            "name": current_seat_name,
            "annualPrice": annual_price,
            "monthlyPrice": monthly_price,
        })

    # Build primary price from first seat type's annual price
    primary_annual = seat_types[0]["annualPrice"] if seat_types else None

    # Also try simple seat price pattern if no seat types found
    if not seat_types:
        sm = _SEAT_PRICE_RE.search(block)
        if sm:
            primary_annual = float(sm.group(1))

    if primary_annual is None:
        return None, None

    price = {
        "currency": "$",
        "amount": primary_annual,
        "period": "/seat/mo",
        "raw": f"${primary_annual} per seat / month if billed annually",
    }

    billing = {
        "annualSeatPrice": seat_types[0]["annualPrice"] if seat_types else primary_annual,
        "monthlySeatPrice": seat_types[0].get("monthlyPrice") if seat_types else None,
    }
    if len(seat_types) >= 2:
        billing["premiumAnnualSeatPrice"] = seat_types[1].get("annualPrice")
        billing["premiumMonthlySeatPrice"] = seat_types[1].get("monthlyPrice")

    return price, {"billing": billing, "seatTypes": seat_types, "type": "team_plan"}


def _extract_enterprise_pricing(plan_name, block):
    """Extract Enterprise custom+usage pricing.

    Handles patterns like:
        Contact sales   $20/seat   Seat price + usage at API rates

    Returns a price dict and optional billing metadata.
    """
    block = block or ""
    block_l = block.lower()

    custom_pricing = "contact sales" in block_l or "contact us" in block_l
    usage_at_api = "usage at api rates" in block_l or "api rates" in block_l

    seat_price = None
    em = _ENTERPRISE_SEAT_RE.search(block)
    if em:
        seat_price = float(em.group(1))

    if not custom_pricing and not seat_price:
        return None, None

    price = {
        "type": "custom_plus_usage" if usage_at_api else "custom",
        "currency": "$",
        "seatPrice": seat_price,
        "period": "/seat",
        "raw": (
            f"${seat_price}/seat + usage at API rates"
            if seat_price and usage_at_api
            else "Contact sales"
        ),
    }
    billing = {
        "customPricingAvailable": True,
        "usageAtApiRates": usage_at_api,
    }
    return price, {"billing": billing, "type": "enterprise_plan"}


def _extract_hosting_bare_decimal_prices(text):
    """Extract bare decimal prices from hosting plan text (no currency symbol).

    Returns list of price dicts compatible with the main prices list.
    Only activates when the text contains hosting plan indicators.
    """
    text = text or ""
    # Require at least one plan section marker to avoid false positives
    if not re.search(r"Web\s+Hosting\s+Plans|hosting\s+plan|/yr\s+when\s+you\s+renew", text, re.I):
        return []

    found = []
    seen = set()
    for m in _HOSTING_BARE_PRICE_RE.finditer(text):
        amount_str = m.group(1)
        period_raw = (m.group(2) or "").lower()

        # Skip amounts that look like years (e.g., 2026) or percentages
        amount = float(amount_str)
        if amount > 999:
            continue

        period = None
        if period_raw in ("/yr", "/year"):
            period = "/yr"
        elif period_raw in ("/mo", "/month"):
            period = "/mo"

        raw = f"{amount_str}{period_raw}" if period_raw else amount_str
        key = (amount_str, period_raw)
        if key in seen:
            continue
        seen.add(key)
        found.append({
            "currency": None,
            "amount": amount,
            "period": period,
            "raw": raw,
        })

    return found[:20]


def _build_hosting_plan_features(hosting_plans):
    """Build planFeatures dict from fields already extracted by _extract_websouls_hosting_plans.

    Each plan dict has structured fields (storage, websites, aiWebsiteBuilder, etc.).
    Convert them to the standard {planName: {featureSnippets: [...]}} shape.
    Page-wide sections (SSL, DDoS, cPanel) are intentionally excluded here — they
    belong in hostingIntelligence, not per-plan features.
    """
    output = {}
    for plan in hosting_plans or []:
        name = plan.get("name")
        if not name:
            continue
        snippets = []
        if plan.get("storage"):
            snippets.append(plan["storage"])
        if plan.get("websites") is not None:
            w = plan["websites"]
            snippets.append(f"{'Unlimited' if w is None else w} Website{'s' if w != 1 else ''}")
        if plan.get("bandwidth"):
            snippets.append(f"{plan['bandwidth']} Bandwidth")
        if plan.get("databases") is not None:
            d = plan["databases"]
            snippets.append(f"{'Unlimited' if d == 'Unlimited' else d} Database{'s' if d != 1 else ''}")
        if plan.get("aiWebsiteBuilder"):
            snippets.append("AI Website Builder Included")
        else:
            snippets.append("AI Website Builder: Not Included")
        if plan.get("freeDomain"):
            snippets.append("Free Domain")
        if plan.get("freeBackup"):
            snippets.append("Free Backup")
        if plan.get("freeWebsiteMigration"):
            snippets.append("Free Website Migration")
        if plan.get("freeTrial"):
            snippets.append("7-Day Free Trial")
        if plan.get("nodeJsSupported"):
            snippets.append("NodeJS Supported")
        if plan.get("cPanelAccess"):
            snippets.append(plan["cPanelAccess"])
        if snippets:
            output[name] = {"featureSnippets": snippets[:10]}
    return output


def _extract_plain_text_hosting_ctas(text, url):
    """Extract CTAs from plain text hosting pages (no HTML links, no Jina markdown).

    Looks for action phrases that appear near hosting keywords in flat text.
    Used when a hosting page was rendered via Jina but without markdown link format.
    """
    text = text or ""
    text_l = text.lower()

    # High-priority hosting action phrases — order matters for deduplication
    action_phrases = [
        "Explore Plans",
        "Get Started",
        "View Hosting Options",
        "View Hosting Plans",
        "Start Migration",
        "Talk to Our Expert",
        "Talk to an Expert",
        "See More",
        "Start Free Trial",
        "Try Free",
        "Upgrade Hosting",
        "Compare Plans",
        "Contact Us",
    ]

    # Phrases that are section wording rather than linked CTAs — tagged with type
    _SECTION_WORDING = {"upgrade hosting"}

    ctas = []
    seen = set()
    for phrase in action_phrases:
        if phrase.lower() in text_l:
            key = phrase.lower()
            if key not in seen:
                seen.add(key)
                entry = {
                    "text": phrase,
                    "url": "",
                    "source": "plain_text_hosting",
                }
                if key in _SECTION_WORDING:
                    entry["type"] = "section_cta"
                ctas.append(entry)

    return ctas[:8]


def analyze_unknown_general(self, url, html, headers, page_type, level1):
    """V14 full analyzer override — collection re-route + blocked detection + scoping."""

    # Guard 1: Collection re-route — page was misclassified as general despite
    # overwhelming collection evidence (e.g. Under Armour hoodie grid).
    if _has_strong_collection_evidence(level1):
        from analyzers.unknown.collection import analyze_unknown_collection
        return analyze_unknown_collection(self, url, html, headers, "collection", level1)

    result = self.base_result(url, html, headers, page_type, level1)
    soup = BeautifulSoup(html or "", "lxml")

    # Guard 2: Blocked / unusable content — return structured blocked result.
    _is_blocked, _blocked_reason, _intended_type = _detect_blocked_general(html, url, soup)
    if _is_blocked:
        _blocked_page_type = (
            f"blocked/{_blocked_reason}/intendedPageType={_intended_type}"
            if _intended_type and _intended_type != "unknown"
            else f"blocked/{_blocked_reason}"
        )
        result["page"]["pageType"] = _blocked_page_type
        result["success"] = False
        result["blocked"] = True
        result["blockedReason"] = _blocked_reason
        result["intendedPageType"] = _intended_type
        result["source"] = {
            "extractor": "Unknown General Extractor",
            "extractorFamily": "Unknown",
            "confidence": 0.10,
        }
        result.setdefault("warnings", []).append(
            f"Page blocked or unusable: {_blocked_reason}"
        )
        return result

    detected_platform = level1.get("platform", "Unknown") if level1 else "Unknown"
    general_subtype = level1.get("generalSubtype") if level1 else None

    title = clean_text(soup.title.string) if soup.title and soup.title.string else None
    meta_description = get_meta(soup, name="description") or get_meta(soup, property_name="og:description")

    canonical_tag = soup.find("link", rel="canonical")
    canonical = canonical_tag.get("href") if canonical_tag else None

    h1_tag = soup.find("h1")
    h1 = clean_text(h1_tag.get_text(" ", strip=True)) if h1_tag else None

    headings = extract_headings(soup)

    # Dedup headings: mega-menus repeat the same text at h2 and h3 level (nav footprint).
    # Also drop headings whose text is a doubled word sequence ("Account Account" in Apple footer).
    _seen_hd = set()
    _clean_headings = []
    for _h in headings:
        _ht = (_h.get("text") or "").strip()
        _ht_l = _ht.lower()
        _hwords = _ht_l.split()
        if len(_hwords) >= 2 and len(_hwords) % 2 == 0:
            _half = len(_hwords) // 2
            if _hwords[:_half] == _hwords[_half:]:
                continue
        if _ht_l and _ht_l in _seen_hd:
            continue
        if _ht_l:
            _seen_hd.add(_ht_l)
        _clean_headings.append(_h)
    headings = _clean_headings

    main_text = extract_main_text(soup)
    links = extract_links(soup, url)
    ctas = extract_ctas(soup, url)
    images = extract_images(soup, url)
    faqs = extract_faqs(soup)

    # Supplement CTAs with links parsed from Jina markdown (for Jina-fallback pages).
    # Jina converts <a href="...">text</a> → [text](url) plain text, so extract_ctas()
    # misses them.  Merge any new CTA-intent links found in the text body.
    # Issues 3+10+S5-5: use raw html[:60000] (not just main_text) so CTAs beyond the
    # 12000-char main_text limit are still found (e.g. Websouls "View Hosting Plans"
    # at char ~30476, Claude "Explore detailed pricing" at ~45000+).
    _jina_source = (html or "")[:60000] if html and "[" in (html or "") and "](" in (html or "") else main_text
    _jina_ctas = _extract_jina_markdown_ctas(_jina_source, url)
    if _jina_ctas:
        _existing_cta_texts = {c["text"].lower() for c in ctas}
        for _jc in _jina_ctas:
            if _jc["text"].lower() not in _existing_cta_texts:
                ctas.append(_jc)
                _existing_cta_texts.add(_jc["text"].lower())

    # Issue 4: For pricing pages, supplement with pricing-card CTAs that extract_ctas()
    # misses because cta_terms doesn't include standalone 'get', 'chat', 'explore', etc.
    if general_subtype == "pricing":
        _pricing_ctas = _extract_pricing_plan_ctas(soup, url)
        if _pricing_ctas:
            _existing_cta_texts = {c["text"].lower() for c in ctas}
            for _pc in _pricing_ctas:
                if _pc["text"].lower() not in _existing_cta_texts:
                    ctas.append(_pc)
                    _existing_cta_texts.add(_pc["text"].lower())

    # Guard 3: Scope product_family_landing and tour_page content (Samsung/Apple/Sonos noise removal).
    _PRODUCT_FAMILY_LIKE_SUBTYPES = {"product_family_landing", "tour_page"}
    if general_subtype in _PRODUCT_FAMILY_LIKE_SUBTYPES:
        main_text = _extract_product_family_region(main_text, url)
        images = _filter_images_for_product_family(images, url)
        ctas = _filter_ctas_for_product_family(ctas, url)

    purpose = detect_page_purpose(url=url, text=main_text, headings=headings, links=links)

    # Issue 12: Override pagePurpose for service_page subtype — detect_page_purpose
    # doesn't have a service_page score bucket, so it returns 'generic'.
    if general_subtype == "service_page":
        purpose["primaryPurpose"] = "service_page"
        purpose.setdefault("scores", {})["service_page"] = 10

    # Issue 1: extract_prices() only handles [$£€] — supplement with Rs/PKR prices
    # from extract_prices_with_positions() when the symbol-only pattern returns nothing.
    prices = extract_prices(main_text)
    if not prices and main_text:
        _rs_extended = extract_prices_with_positions(main_text)
        prices = [
            {
                "currency": p["price"]["currency"],
                "amount": p["price"]["amount"],
                "period": p["price"].get("period"),
                "raw": p["price"]["raw"],
            }
            for p in _rs_extended
            if is_core_recurring_price(p["price"])
        ]

    # Issue 2: Hosting pages (Websouls) use bare decimal prices without currency symbols.
    # Add them to the prices list so pricesDetected and quality scoring reflect reality.
    _hosting_bare_prices = []
    _is_hosting_context = any(x in (url or "").lower() for x in [
        "websouls", "/web-hosting", "/shared-hosting", "/hosting",
    ]) or re.search(r"Web\s+Hosting\s+Plans\s+and\s+Pricing|/yr\s+when\s+you\s+renew", main_text or "", re.I)

    if not prices and main_text and _is_hosting_context:
        _hosting_bare_prices = _extract_hosting_bare_decimal_prices(main_text)
        if _hosting_bare_prices:
            prices = _hosting_bare_prices

    pricing_mentions = get_pricing_mentions(main_text)

    # Relax the pricing-offer gate: also call build_pricing_offers when pricing_mentions
    # are strong enough to suggest a real pricing page, even if prices list is still empty.
    _pricing_signal_strength = bool(prices) or len(pricing_mentions) >= 3
    pricing_offers = build_pricing_offers(main_text, headings, prices) if _pricing_signal_strength else {
        "corePlans": [], "addOns": [], "standaloneProducts": [], "planNames": [],
        "planMappingConfidence": "low", "notes": []
    }

    # Issue 1 (cont): Try Websouls-style hosting plan card extraction.
    # If found, override pricing_offers.corePlans with the richer hosting plan data.
    _hosting_plans = _extract_websouls_hosting_plans(main_text)
    if _hosting_plans:
        _hosting_plan_names = [p["name"] for p in _hosting_plans]
        pricing_offers = {
            "corePlans": _hosting_plans,
            "addOns": pricing_offers.get("addOns", []),
            "standaloneProducts": pricing_offers.get("standaloneProducts", []),
            "planNames": _hosting_plan_names,
            "planOrder": _hosting_plan_names,
            "planMappingConfidence": "high_clean",
            "notes": ["Extracted from hosting plan cards"],
        }
        # Also ensure prices reflect the hosting plan prices
        if not prices:
            prices = [
                p["price"] for p in _hosting_plans
                if isinstance(p.get("price"), dict)
            ]

    pricing_evidence = has_pricing_page_evidence(url, main_text, headings, prices, pricing_offers)
    if pricing_evidence:
        general_subtype = "pricing"
        purpose["primaryPurpose"] = "pricing"
        purpose.setdefault("scores", {})["pricing"] = max(purpose.get("scores", {}).get("pricing", 0), 10)
    elif not general_subtype and purpose.get("primaryPurpose") != "generic":
        general_subtype = purpose.get("primaryPurpose")

    # Issue 3/5: Filter mega-menu/footer headings for pricing and service-bundle pages.
    # This prevents nav headings from inflating contentAngles with irrelevant topics.
    _HEADING_FILTER_SUBTYPES = {"pricing", "product_family_landing", "service_landing"}
    if general_subtype in _HEADING_FILTER_SUBTYPES:
        headings = _filter_nav_headings_for_pricing_page(headings)

    core_plans = pricing_offers.get("corePlans", [])
    if not core_plans:
        # Deterministic DOM fallback for plan-card grids (see extractors/plan_parser.py)
        try:
            from extractors.plan_parser import extract_plan_cards_from_dom
            _dom_plans = extract_plan_cards_from_dom(soup)
            if _dom_plans:
                core_plans = _dom_plans
                pricing_offers["corePlans"] = _dom_plans
                pricing_offers["planNames"] = [pl.get("name") for pl in _dom_plans]
        except Exception:
            pass
    pricing_summary = extract_pricing_summary(prices, core_plans=core_plans, text=main_text)
    # Issue 4: For hosting plan cards, build features from structured card fields.
    # This avoids page-wide sections (SSL/DDoS/cPanel paragraphs) polluting per-plan features.
    if _hosting_plans:
        plan_features = _build_hosting_plan_features(_hosting_plans)
    else:
        plan_features = extract_plan_features(main_text, core_plans, url=url)
    comparison_matrix = extract_pricing_comparison_matrix(main_text, core_plans, plan_features)
    api_pricing = extract_api_pricing(main_text)
    pricing_intelligence = build_pricing_intelligence(
        main_text, pricing_offers, pricing_summary, plan_features, comparison_matrix, api_pricing
    )

    # Issue 7: Extract hosting/service intelligence for hosting-type pricing pages.
    hosting_intelligence = _extract_hosting_intelligence(main_text, url)

    # Issue 3: Supplement CTAs for hosting pages that use plain text (no HTML links / Jina markdown).
    # Websouls renders via Jina but without [text](url) format, so _extract_jina_markdown_ctas misses them.
    # Always supplement on hosting pages — do NOT gate on `not ctas` (Contact Us may already be present).
    if hosting_intelligence.get("detected") or _is_hosting_context:
        _hosting_ctas = _extract_plain_text_hosting_ctas(main_text, url)
        if _hosting_ctas:
            _existing_cta_texts = {c["text"].lower() for c in ctas}
            for _hc in _hosting_ctas:
                if _hc["text"].lower() not in _existing_cta_texts:
                    ctas.append(_hc)
                    _existing_cta_texts.add(_hc["text"].lower())
        # Issue 1: Also scan soup <a> tags for hosting CTAs missed by main_text truncation.
        # Jina-converted HTML has <a> tags for all links but cta_terms misses 'view'/'explore'/'start' etc.
        _soup_hosting_ctas = _extract_hosting_soup_ctas(soup, url)
        if _soup_hosting_ctas:
            _existing_cta_texts = {c["text"].lower() for c in ctas}
            for _hc in _soup_hosting_ctas:
                if _hc["text"].lower() not in _existing_cta_texts:
                    ctas.append(_hc)
                    _existing_cta_texts.add(_hc["text"].lower())
        # Session 4 Issue 1 V2: Also scan full soup text for plain-text hosting phrases that
        # appear beyond the 12000-char main_text limit OR as non-href buttons (#/javascript:).
        if soup:
            _full_soup_text = soup.get_text(" ", strip=True)
            _fulltext_hosting_ctas = _extract_plain_text_hosting_ctas(_full_soup_text, url)
            if _fulltext_hosting_ctas:
                _existing_cta_texts = {c["text"].lower() for c in ctas}
                for _hc in _fulltext_hosting_ctas:
                    if _hc["text"].lower() not in _existing_cta_texts:
                        ctas.append(_hc)
                        _existing_cta_texts.add(_hc["text"].lower())

    # Issue 13: Extract text-only CTAs for service pages
    service_intelligence = None
    if general_subtype == "service_page":
        _service_ctas = _extract_service_page_text_ctas(main_text)
        if _service_ctas:
            _existing_cta_texts = {c["text"].lower() for c in ctas}
            for _sc in _service_ctas:
                if _sc["text"].lower() not in _existing_cta_texts:
                    ctas.append(_sc)
                    _existing_cta_texts.add(_sc["text"].lower())
        # Issue 14: Extract service intelligence
        # Session 7 Issue 8: supplement with link texts so "office security" (link-only)
        # is detected even when it doesn't appear in extracted main_text body.
        _svc_link_kw = " ".join(
            (lk.get("text") or "") for lk in (links or [])
            if lk.get("text") and len(lk.get("text", "")) < 50
        )
        service_intelligence = _extract_service_intelligence(
            main_text, url, extra_kw_text=_svc_link_kw or None
        )

    # Issue 6: Post-clean all CTAs to remove DOM-sourced noise (doubled words, nav links)
    ctas = _post_clean_ctas(ctas)

    # Extract app store links to appLinks[] and scrub them from CTAs.
    _APP_STORE_URL_MARKERS = ("apps.apple.com", "play.google.com", "app-store", "appstore.com")
    _APP_STORE_TEXT_RE = re.compile(
        r"download on the app store|get it on google play|available on the app store"
        r"|download app|download the app",
        re.I,
    )
    _app_links = []
    _clean_ctas = []
    for _c in ctas:
        _ct = (_c.get("text") or "").lower()
        _cu = (_c.get("url") or "").lower()
        _is_app = (
            _APP_STORE_TEXT_RE.search(_ct)
            or any(m in _cu for m in _APP_STORE_URL_MARKERS)
        )
        if _is_app:
            _app_links.append(_c)
        else:
            _clean_ctas.append(_c)
    ctas = _clean_ctas
    if _app_links:
        result["appLinks"] = _app_links

    positioning_signals = extract_positioning_signals(main_text)
    # Session 4→5 Issue 4/3: For service pages, build positioning as a LIST of strings
    # (competitive_schema.extract_positioning only consumes positioningSignals when it
    # is isinstance(existing, list) — a dict silently falls through to generic term detection).
    if general_subtype == "service_page" and service_intelligence and service_intelligence.get("detected"):
        _svc_pos_list = []
        # Trust signals first (most differentiating)
        _svc_pos_list.extend(service_intelligence.get("trustSignals", []))
        # Core services (next 4)
        for _svc in service_intelligence.get("services", [])[:4]:
            if _svc and _svc not in _svc_pos_list:
                _svc_pos_list.append(_svc)
        # Geographic focus as contextual positioning strings
        _areas = [a for a in service_intelligence.get("serviceArea", []) if a and a != "Not specified"]
        for _area in _areas[:2]:
            _geo_str = f"{_area} security services"
            if _geo_str not in _svc_pos_list:
                _svc_pos_list.append(_geo_str)
        # Customer benefits
        for _b in service_intelligence.get("benefits", [])[:3]:
            if _b and _b not in _svc_pos_list:
                _svc_pos_list.append(_b)
        if _svc_pos_list:
            positioning_signals = list(dict.fromkeys(_svc_pos_list))[:12]

    result["platform"] = detected_platform
    # Preserve the level1-detected page type (e.g. "blog") — the unknown
    # analyzer routes blogs through this general extractor, and hardcoding
    # "general" here misreported every blog on unknown platforms.
    result["page"]["pageType"] = page_type or "general"
    if general_subtype:
        result["page"]["generalSubtype"] = general_subtype
        # Issue 10: Sync level1.generalSubtype when we override it here.
        # page_type_detector may have set a coarse value (e.g. "tool_app_page") that
        # the extractor can now refine (e.g. "pricing"). Update in-place so callers
        # reading result["level1"]["generalSubtype"] see the resolved value.
        if result.get("level1") and isinstance(result["level1"], dict):
            result["level1"]["generalSubtype"] = general_subtype
            # Session 4 Issue 2: Also sync pageTypeDebug.signals.generalSubtype
            _dbg = result["level1"].get("pageTypeDebug")
            if isinstance(_dbg, dict) and isinstance(_dbg.get("signals"), dict):
                _dbg["signals"]["generalSubtype"] = general_subtype

    result["seo"] = {
        "title": title,
        "metaDescription": meta_description,
        "canonical": canonical,
        "h1": h1,
    }

    result["content"] = {
        "title": h1 or title,
        "summaryText": main_text[:1000],
        "mainText": main_text,
        "headings": headings,
        "faqs": faqs,
        "pagePurpose": purpose,
        "pricingMentions": pricing_mentions,
    }

    result["navigation"] = {"links": links}
    result["ctas"] = ctas
    result["media"] = {"images": images}

    is_pricing_page = bool(
        general_subtype == "pricing"
        or purpose.get("primaryPurpose") == "pricing"
        or pricing_evidence
        or "/pricing" in (url or "").lower()
    )

    # General page subtypes that are never ecommerce category pages — skip categoryLinks.
    _NO_CATEGORY_LINK_SUBTYPES = {
        "product_family_landing", "tour_page", "pricing", "service_landing",
        "brand_landing", "about", "contact", "support",
    }
    _show_category_links = general_subtype not in _NO_CATEGORY_LINK_SUBTYPES

    # G-F2: expose canonical products path consistent with other platforms
    result["products"] = []

    result["ecommerce"] = {
        "hasEcommerceSignals": False,
        "hasPrices": bool(prices),
        "pricingPage": bool(is_pricing_page),
        "products": [],
        "categoryLinks": [
            link for link in links
            if any(x in link["url"].lower() for x in ["/collections/", "/category/", "/shop/", "/products/"])
        ][:50] if _show_category_links else [],
    }

    # Emit pricing block when prices, plans, or hosting intelligence is present.
    _emit_pricing_block = bool(prices or core_plans or hosting_intelligence.get("detected"))
    if _emit_pricing_block:
        _plan_order = [p["name"] for p in core_plans if isinstance(p, dict) and p.get("name")]
        _priced_amounts = [
            p["price"]["amount"] for p in core_plans
            if isinstance(p, dict)
            and isinstance(p.get("price"), dict)
            and isinstance(p["price"].get("amount"), (int, float))
            and p["price"]["amount"] > 0
        ]
        result["pricing"] = {
            "pricesDetected": len(prices),
            "prices": prices,
            "summary": pricing_summary,
            "planNames": pricing_offers.get("planNames", []),
            "corePlans": core_plans,
            "addOns": pricing_offers.get("addOns", []),
            "standaloneProducts": pricing_offers.get("standaloneProducts", []),
            "planFeatures": plan_features,
            "comparisonMatrix": comparison_matrix,
            "apiPricing": api_pricing,
            "pricingIntelligence": pricing_intelligence,
            "plans": core_plans,
            "planOrder": _plan_order,
            "hasPricing": bool(core_plans),
            "lowestMainPlanPrice": min(_priced_amounts) if _priced_amounts else None,
            "highestMainPlanPrice": max(_priced_amounts) if _priced_amounts else None,
            "planMappingConfidence": pricing_offers.get("planMappingConfidence", "low"),
            "notes": pricing_offers.get("notes", []),
        }

    if pricing_intelligence.get("detected"):
        result["pricingIntelligence"] = pricing_intelligence

    # Issue 7: Expose hosting intelligence at the top level when detected.
    if hosting_intelligence.get("detected"):
        result["hostingIntelligence"] = hosting_intelligence
        # Also ensure pricingIntelligence carries the hosting type so downstream
        # competitive_schema can route correctly.
        if not result.get("pricingIntelligence"):
            result["pricingIntelligence"] = hosting_intelligence

    if api_pricing.get("detected"):
        result["apiPricing"] = api_pricing

    # Issue 14: Emit serviceIntelligence for service_page subtype
    if service_intelligence and service_intelligence.get("detected"):
        result["serviceIntelligence"] = service_intelligence
        # Issue S5-4: Expose trustSignals at top level so competitive_schema picks them up
        # (competitive_schema reads result["trustSignals"] before falling back to term detection)
        if service_intelligence.get("trustSignals"):
            result["trustSignals"] = service_intelligence["trustSignals"]

    if positioning_signals:
        result["positioningSignals"] = positioning_signals

    # ── Base quality score ────────────────────────────────────────────────────
    confidence = 0.55
    if h1:
        confidence += 0.15
    if main_text and len(main_text) > 300:
        confidence += 0.15
    if title or meta_description:
        confidence += 0.1
    if prices:
        confidence += 0.05

    # ── Subtype-aware quality caps (Issues 2, 6, 11) ─────────────────────────
    _is_pricing_subtype = (
        general_subtype == "pricing"
        or purpose.get("primaryPurpose") == "pricing"
    )
    _is_hosting = hosting_intelligence.get("industryPricingType") == "web_hosting"
    _is_service_bundle = general_subtype in {"product_family_landing", "service_landing"}
    _is_about = general_subtype == "about"
    _is_service_page = general_subtype == "service_page"

    _plans_detected = bool(core_plans)
    _prices_detected = bool(prices)
    _has_ctas = bool(ctas)
    _has_faqs = bool(faqs)

    _hosting_plans_detected = bool(_hosting_plans)  # from _extract_websouls_hosting_plans
    _hosting_intel_strong = hosting_intelligence.get("detected") and bool(
        hosting_intelligence.get("hostingFeatures")
    )

    if _is_pricing_subtype:
        if _is_hosting:
            # Issue 4: Web hosting pricing quality — tiered by what was extracted.
            if _hosting_plans_detected and _prices_detected and _has_ctas and _hosting_intel_strong:
                # Full extraction: plans + prices + CTAs + hosting intelligence
                confidence = min(confidence, 0.88)
            elif _hosting_plans_detected and _prices_detected:
                # Plans and prices found, CTAs or intel incomplete
                confidence = min(confidence, 0.85)
            elif _hosting_plans_detected or (_hosting_intel_strong and _prices_detected):
                # Plans only OR intel+prices — good partial
                confidence = max(min(confidence, 0.82), 0.72)
            elif _hosting_intel_strong:
                # Intelligence detected but no plans/prices — partial
                confidence = max(min(confidence, 0.78), 0.72)
            else:
                confidence = max(min(confidence, 0.80), 0.72)
        elif not _plans_detected and not _prices_detected:
            # No structured data extracted at all — clearly partial.
            confidence = min(confidence, 0.75)
        elif _plans_detected and not _prices_detected:
            # Plan names detected but no prices (name-only extraction).
            confidence = min(confidence, 0.82)
        elif _plans_detected and _prices_detected:
            # Good SaaS pricing extraction — cap depends on plan completeness.
            _has_api_pricing = bool(api_pricing and api_pricing.get("detected"))

            # Issues 4+9: Specifically penalise when Enterprise is in the plan list
            # but its price is still null (custom/unknown) — this signals the extractor
            # did not reach the Enterprise card.
            _plan_names_l = [p.get("name", "").lower() for p in core_plans]
            def _price_is_null(p):
                # Issue 8: price can be None OR a dict with amount=None (e.g. {"raw":"Custom"})
                pr = p.get("price")
                if pr is None:
                    return True
                if isinstance(pr, dict) and pr.get("amount") is None:
                    return True
                return False

            _enterprise_null = any(
                p.get("name", "").lower() in ("enterprise", "enterprise+", "enterprise plus")
                and _price_is_null(p)
                for p in core_plans
            )
            _null_price_plans = sum(
                1 for p in core_plans
                if _price_is_null(p)
                and p.get("name", "").lower() not in ("enterprise", "enterprise+", "enterprise plus")
            )
            if _enterprise_null and _null_price_plans >= 1:
                # Both Enterprise (null) and another plan (null) → very incomplete
                confidence = min(confidence, 0.82)
            elif _enterprise_null:
                # Enterprise null, but other plans have prices — Enterprise card may be
                # intentionally custom-only; flag for review but not catastrophically bad.
                confidence = min(confidence, 0.86)
            elif _null_price_plans >= 2:
                # Two or more non-enterprise plans missing prices
                confidence = min(confidence, 0.88)
            elif _null_price_plans == 1:
                confidence = min(confidence, 0.92)
            elif _has_ctas and _has_faqs and _has_api_pricing:
                confidence = min(confidence, 0.94)
            elif _has_ctas:
                confidence = min(confidence, 0.92)
            else:
                confidence = min(confidence, 0.90)

    elif _is_service_bundle:
        # Product family / service bundle pages (e.g., Apple One).
        # Score by included services, pricing, CTAs, and positioning.
        if _plans_detected and _prices_detected and _has_ctas:
            confidence = min(confidence, 0.94)
        elif _plans_detected and _prices_detected:
            confidence = min(confidence, 0.92)
        elif _plans_detected:
            confidence = min(confidence, 0.88)
        else:
            confidence = min(confidence, 0.80)

    elif _is_about:
        # About pages: brand story/mission/values/contact — no pricing required.
        # Cap at 0.90 until contact extraction and duplicate sections are fully clean.
        confidence = min(confidence, 0.90)

    elif _is_service_page:
        # Issue 15: Service pages — quality depends on serviceIntelligence + CTAs extracted.
        _has_service_intel = bool(service_intelligence and service_intelligence.get("detected"))
        if _has_service_intel and _has_ctas:
            confidence = min(confidence, 0.86)
        elif _has_service_intel:
            confidence = min(confidence, 0.78)
        else:
            confidence = min(confidence, 0.72)

    # ── Hard floor: empty or blocked page ────────────────────────────────────
    _has_any_content = bool(title or h1 or (main_text and len(main_text) > 50) or links or prices)
    if not _has_any_content:
        confidence = min(confidence, 0.15)
        result["success"] = False
        result.setdefault("warnings", []).append(
            "Empty or blocked page content — no title, H1, text, or links detected."
        )

    _final_confidence = round(min(0.95, confidence), 2)
    if _final_confidence >= 0.90:
        _quality_bucket = "excellent"
    elif _final_confidence >= 0.80:
        _quality_bucket = "good"
    elif _final_confidence >= 0.65:
        _quality_bucket = "partial"
    else:
        _quality_bucket = "low"

    result["source"] = {
        "extractor": "Unknown General Extractor",
        "extractorFamily": "Unknown",
        "platformDetected": detected_platform,
        "confidence": _final_confidence,
        "qualityScore": _final_confidence,
        "qualityBucket": _quality_bucket,
        "needsAIInsightReview": _quality_bucket in ("partial", "low"),
    }

    return result

# =============================================================================
# V12 PRICING OVERRIDES
# -----------------------------------------------------------------------------
# Final pricing-parser hardening for mixed SaaS pricing pages:
# - Do not inject generic fallback plan names when real plan headings exist.
# - Support spaced decimals such as "$117 .33/mo" and text prices like
#   "117.33 dollars monthly".
# - Better custom/free handling for Hobby/Enterprise.
# - Better Claude API token pricing extraction.
# - Preserve plan order and add light billing metadata per plan.
# =============================================================================


def extract_pricing_candidates(headings, text):
    """V12: prefer visible pricing headings; only use text-pattern fallback when headings are insufficient."""
    candidates = []
    seen = set()
    heading_core_count = 0

    for h in headings or []:
        raw_name = h.get("text")
        name = normalize_plan_name(raw_name)
        kind = classify_pricing_heading(name, text)
        if kind == "ignore":
            continue
        key = (name.lower(), kind)
        if key in seen:
            continue
        seen.add(key)
        candidates.append({"name": name, "type": kind, "source": "heading"})
        if kind == "core_plan":
            heading_core_count += 1

    # Important: only fallback to generic text-pattern plans when the page has no
    # usable visible plan headings. This prevents Cursor/Ahrefs/Semrush from
    # being polluted by generic words like Free, Pro, Team, Max, etc.
    if heading_core_count < 2:
        for c in extract_text_plan_candidates(text):
            key = (c["name"].lower(), c["type"])
            if key not in seen:
                seen.add(key)
                candidates.append(c)

    return candidates


def extract_prices_with_positions(text):
    """V12: robust price positions for normal, spaced-decimal, and word-currency prices."""
    results = []
    text = text or ""

    patterns = [
        # $117.33/mo, $117 .33/mo, $ 1,499 / mo
        re.compile(
            r"(?P<currency>[$£€])\s*(?P<amount>\d{1,3}(?:,\d{3})*|\d+)(?:\s*\.\s*(?P<decimal>\d{1,2}))?\s*(?P<period>/\s*(?:mo|month|user|seat|check|hour|project|year|yr)|per\s+(?:month|year|user|seat|project))?",
            re.I,
        ),
        # 9,200 Rs /year, 16000 Rs/year
        re.compile(
            r"(?P<amount>\d{1,3}(?:,\d{3})*|\d+)(?:\s*\.\s*(?P<decimal>\d{1,2}))?\s*(?P<currency>Rs|PKR|USD|GBP|EUR)\s*(?P<period>/\s*(?:mo|month|user|seat|year|yr)|per\s+(?:month|year|user|seat))?",
            re.I,
        ),
        # 117.33 dollars monthly / 139 dollars monthly
        re.compile(
            r"(?P<amount>\d{1,3}(?:,\d{3})*|\d+)(?:\s*\.\s*(?P<decimal>\d{1,2}))?\s*(?P<currency>dollars?|usd)\s*(?P<period>monthly|annually|yearly|per\s+month|per\s+year)?",
            re.I,
        ),
    ]

    for pattern in patterns:
        for m in pattern.finditer(text):
            raw = clean_text(m.group(0))
            currency = m.group("currency")
            currency_norm = "$" if currency and currency.lower() in ["dollar", "dollars", "usd"] else currency
            amount_s = (m.group("amount") or "").replace(",", "")
            dec = m.groupdict().get("decimal")
            if dec:
                amount_s = f"{amount_s}.{dec}"
            period = clean_text(m.group("period") or "") or None
            if period:
                p = period.lower().replace(" ", "")
                p = p.replace("permonth", "/mo").replace("monthly", "/mo")
                p = p.replace("peryear", "/year").replace("annually", "/year").replace("yearly", "/year")
                p = p.replace("peruser", "/user").replace("perseat", "/seat")
                period = p
            try:
                amount = float(amount_s)
            except Exception:
                continue
            # Avoid matching tiny numbered footnote references as prices.
            if amount <= 0 and "$" not in raw and "rs" not in raw.lower():
                continue
            results.append({
                "price": {"currency": currency_norm, "amount": amount, "period": period, "raw": raw},
                "start": m.start(),
                "end": m.end(),
                "raw": raw,
            })

    results.sort(key=lambda x: x["start"])
    deduped = []
    seen_spans = set()
    seen_near = set()
    for item in results:
        # Remove overlapping duplicates caused by the word-currency and symbol patterns.
        span_key = (item["start"], item["end"])
        amount = item["price"].get("amount")
        near_key = (round(float(amount or 0), 4), item["price"].get("period"), item["start"] // 8)
        if span_key in seen_spans or near_key in seen_near:
            continue
        seen_spans.add(span_key)
        seen_near.add(near_key)
        deduped.append(item)
    return deduped


def is_core_recurring_price(price_obj):
    """V12: supports /year and per-seat-per-month while rejecting usage/API units."""
    if not isinstance(price_obj, dict):
        return False
    amount = price_obj.get("amount")
    period = (price_obj.get("period") or "").lower()
    raw = (price_obj.get("raw") or "").lower()
    if not isinstance(amount, (int, float)) or amount < 0:
        return False
    if any(x in period for x in ["check", "token", "mtok", "hour", "project", "search"]):
        return False
    if any(x in raw for x in ["/check", "mtok", "token", "session-hour", "container", "1k searches", "per hour"]):
        return False
    return bool(
        any(x in period for x in ["mo", "month", "user", "seat", "year", "yr"])
        or any(x in raw for x in ["/ month", "/month", "/ mo", "/mo", "/ year", "/year", "per month", "per year", "rs /year", "rs/year", "dollars monthly"])
    )


def extract_plan_billing_metadata(block, selected_price=None):
    """Extract simple monthly/annual/custom billing hints from a bounded plan block."""
    block = block or ""
    block_l = block.lower()
    meta = {}

    if "billed annually" in block_l or "annual subscription" in block_l or "billed up front" in block_l:
        meta["annualCommitment"] = True
    if "billed monthly" in block_l or "if billed monthly" in block_l:
        meta["monthlyAvailable"] = True
    # Tighter custom-pricing detection: require "custom" as a pricing descriptor,
    # not as a product feature (e.g. "custom context window", "custom data retention").
    _CUSTOM_PRICING_RE = re.compile(
        r"\bcustom\s*(?:pricing|price|plan|quote|billing|enterprise)?\s*$"
        r"|\bcontact\s+sales\b|\blet.?s\s+talk\b|\btalk\s+to\s+sales\b",
        re.I | re.MULTILINE,
    )
    # Also check that "Custom" appears BEFORE any real dollar price in the block
    _first_dollar = re.search(r"[$£€]\s*\d", block_l)
    _custom_match = _CUSTOM_PRICING_RE.search(block)
    if _custom_match and (not _first_dollar or _custom_match.start() < _first_dollar.start() + 80):
        meta["customPricingAvailable"] = True

    # Pull up to two recurring prices from the block to expose monthly vs annual equivalent.
    prices = [p["price"] for p in extract_prices_with_positions(block) if is_core_recurring_price(p["price"])]
    amounts = [p.get("amount") for p in prices if isinstance(p.get("amount"), (int, float)) and p.get("amount") > 0]
    if amounts:
        # Smaller recurring number is usually annual-equivalent monthly; larger is monthly or higher tier.
        if len(amounts) >= 2:
            meta["annualEquivalent"] = min(amounts)
            meta["monthly"] = max(amounts)
        else:
            raw_l = (prices[0].get("raw") or "").lower()
            if "annual" in block_l or "billed annually" in block_l:
                meta["annualEquivalent"] = amounts[0]
            elif any(x in raw_l for x in ["/mo", "/ month", "monthly"]):
                meta["monthly"] = amounts[0]
    return meta


def select_core_price_from_block(block, name=None):
    """V12: bounded block price selection with stronger Free/Custom/seat handling."""
    block = block or ""
    block_l = block.lower()
    name_l = (name or "").lower()

    # Explicit free marker wins immediately
    if block_has_explicit_free(block, name):
        return {"currency": "$", "amount": 0, "period": "/mo", "raw": "$0"}, 10

    # Explicit custom marker
    if block_has_explicit_custom(block):
        return {"currency": None, "amount": None, "period": None, "raw": "Custom"}, 8

    # Seat-based pricing (Team/Enterprise style)
    _seat_re = re.compile(
        r"\$\s*(\d+(?:\.\d+)?)\s*(?:per\s+seat\s*/\s*month|/seat/mo|per\s+seat\s+per\s+month"
        r"|per\s+seat\s*/\s*month|/seat\s+/\s*month)",
        re.I,
    )
    sm = _seat_re.search(block)
    if sm:
        amt = float(sm.group(1))
        return {"currency": "$", "amount": amt, "period": "/seat/mo", "raw": f"${amt} per seat / month"}, 9

    # Standard price extraction
    prices = [p["price"] for p in extract_prices_with_positions(block) if is_core_recurring_price(p["price"])]
    if not prices:
        return None, 0

    # Pick the price closest to the plan name in the block
    best_price = None
    best_score = 0
    for p in prices:
        raw_l = (p.get("raw") or "").lower()
        amount = p.get("amount")
        if not isinstance(amount, (int, float)):
            continue
        score = 5
        if amount > 0:
            score += 2
        if p.get("period"):
            score += 1
        if p.get("currency"):
            score += 1
        if score > best_score:
            best_score = score
            best_price = p

    return best_price, best_score


def build_pricing_offers(text, headings, prices):
    """V12+: plan order, billing metadata, seat-based Team/Enterprise pricing, Free normalization."""
    candidates = extract_pricing_candidates(headings, text)
    core_names = get_core_names_from_candidates_v10(candidates)
    addon_names = unique_clean_names([c["name"] for c in candidates if c.get("type") == "addon"])
    standalone_names = unique_clean_names([c["name"] for c in candidates if c.get("type") == "standalone_product"])

    ordered_mapping = map_core_prices_by_order(text, core_names)
    section = get_main_pricing_section(text)
    blocks, _ = extract_named_blocks(section, core_names)

    core_plans = []
    for name in core_names:
        price = ordered_mapping.get(name.lower())
        block = (blocks.get(name.lower()) or {}).get("text", "")
        billing = extract_plan_billing_metadata(block, price)
        plan_type = "core_plan"

        # Issues 5+6: For Team/Enterprise plans with null price, try specialized extractors.
        if price is None and name.lower() in ("team",):
            seat_price, seat_meta = _extract_seat_based_pricing(name, block)
            if seat_price:
                price = seat_price
                plan_type = seat_meta.get("type", "team_plan")
                if seat_meta.get("billing"):
                    billing = seat_meta["billing"]

        if price is None and name.lower() in ("enterprise",):
            ent_price, ent_meta = _extract_enterprise_pricing(name, block)
            if ent_price:
                price = ent_price
                plan_type = ent_meta.get("type", "enterprise_plan")
                if ent_meta.get("billing"):
                    billing = ent_meta["billing"]

        # Issues 1+2: When price is "Custom" dict (not None), upgrade Enterprise type
        # and enrich with billing metadata from enterprise-specific extractor.
        if name.lower() == "enterprise" and isinstance(price, dict):
            _raw_p = (price.get("raw") or "").lower()
            if "custom" in _raw_p or price.get("amount") is None:
                plan_type = "enterprise_plan"
                _ep, _em = _extract_enterprise_pricing(name, block)
                if _em and _em.get("billing"):
                    billing = {**(billing or {}), **_em["billing"]}
                if _ep and _ep.get("type") == "custom_plus_usage":
                    price = _ep  # Upgrade to richer custom+usage price dict

        # Teams period normalization: "$40 / user" → "/user/mo"
        if name.lower() in ("teams", "team") and isinstance(price, dict):
            if price.get("period") in ("/user", "/user ") and re.search(
                r"/\s*mo|per\s+month|/\s*month", (price.get("raw", "") + " " + block[:200]).lower()
            ):
                price = {**price, "period": "/user/mo"}

        # Issue 7: Normalize Free → $0/mo
        if isinstance(price, dict):
            _raw = str(price.get("raw") or "").lower().strip()
            if _raw in ("free", "0", "$0") or price.get("amount") == 0:
                price = {"currency": "$", "amount": 0, "period": "/mo", "raw": "$0"}

        if price:
            raw = str(price.get("raw") or "").lower()
            amount = price.get("amount")
            if isinstance(amount, (int, float)) and amount > 0:
                confidence_val = 0.88
            elif amount == 0:
                confidence_val = 0.85
            else:
                confidence_val = 0.72
            if raw == "custom" or (price.get("type") == "custom_plus_usage"):
                confidence_val = 0.78
            item = {
                "name": name,
                "type": plan_type,
                "price": price,
                "confidence": confidence_val,
                "source": "core_plan_block_mapping",
            }
            if billing:
                item["billing"] = billing
            # Carry seatTypes if present
            if plan_type in ("team_plan",) and name.lower() == "team":
                _sp, _sm = _extract_seat_based_pricing(name, block)
                if _sm and _sm.get("seatTypes"):
                    item["seatTypes"] = _sm["seatTypes"]
            core_plans.append(item)
        else:
            core_plans.append({
                "name": name,
                "type": plan_type,
                "price": None,
                "confidence": 0.45,
                "source": "core_plan_name_only",
            })

    valid, notes = validate_core_plan_mapping(core_plans)
    if not valid:
        core_plans, notes = disable_core_plan_prices(core_plans, notes)


    # Issues 1+2: Full-text fallback for Team/Enterprise when pricing section was
    # truncated early (e.g. Claude's "compare features across plans" table at pos ~1400
    # while Team/Enterprise cards appear at pos ~2800-3600).
    for _fp in core_plans:
        if _fp.get("price") is not None:
            continue
        _fn = _fp.get("name", "").lower()
        if _fn == "team":
            _sp, _sm = _extract_seat_based_pricing("Team", text)
            if _sp:
                _fp["price"] = _sp
                _fp["type"] = "team_plan"
                _fp["confidence"] = 0.88
                _fp["source"] = "full_text_seat_price_fallback"
                if _sm and _sm.get("billing"):
                    _fp["billing"] = _sm["billing"]
                if _sm and _sm.get("seatTypes"):
                    _fp["seatTypes"] = _sm["seatTypes"]
        elif _fn == "enterprise":
            _ep2, _em2 = _extract_enterprise_pricing("Enterprise", text)
            if _ep2:
                _fp["price"] = _ep2
                _fp["type"] = "enterprise_plan"
                _fp["confidence"] = 0.78
                _fp["source"] = "full_text_enterprise_fallback"
                if _em2 and _em2.get("billing"):
                    _fp["billing"] = _em2["billing"]

    # Re-compute has_custom after fallback enrichment.
    has_custom = any(
        (p.get("price") or {}).get("raw", "").lower() in ("custom", "contact sales")
        or (p.get("price") or {}).get("type") in ("custom", "custom_plus_usage")
        for p in core_plans
    )

    addon_section = extract_addon_section(text)
    addon_price_map = select_entity_prices_from_ordered_blocks(addon_section or text, addon_names, "addon")
    addons = []
    for name in addon_names:
        p, score = addon_price_map.get(name.lower(), (None, 0))
        addons.append({
            "name": name,
            "type": "addon",
            "price": p if score >= 4 else None,
            "confidence": 0.72 if score >= 4 else 0.45,
            "source": "addon_block_mapping",
        })

    standalone_price_map = select_entity_prices_from_ordered_blocks(text, standalone_names, "standalone_product")
    standalone = []
    for name in standalone_names:
        p, score = standalone_price_map.get(name.lower(), (None, 0))
        if name.lower() in ["ahrefs free", "free"]:
            p = {"currency": "$", "amount": 0, "period": "/mo", "raw": "$0"}
            score = 8
        standalone.append({
            "name": name,
            "type": "standalone_product",
            "price": p if score >= 4 else None,
            "confidence": 0.72 if score >= 4 else 0.45,
            "source": "standalone_block_mapping",
        })

    priced_core = [p for p in core_plans if isinstance(p.get("price"), dict)]
    if valid and len(priced_core) >= max(2, min(3, len(core_plans))):
        mapping_confidence = "high_clean"
    elif priced_core:
        mapping_confidence = "medium"
    else:
        mapping_confidence = "low"

    # Detect custom pricing (Enterprise / contact-sales plans)
    has_custom = any(
        (p.get("price") or {}).get("raw", "").lower() in ("custom", "contact sales")
        or (p.get("price") or {}).get("type") == "custom_plus_usage"
        for p in core_plans
    )

    return {
        "corePlans": core_plans[:10],
        "addOns": addons[:12],
        "standaloneProducts": standalone[:12],
        "planNames": [p["name"] for p in core_plans[:10]],
        "planOrder": [p["name"] for p in core_plans[:10]],
        "planMappingConfidence": mapping_confidence,
        "hasCustomPricing": has_custom,
        "notes": notes,
    }



def build_pricing_intelligence(text, pricing_offers, pricing_summary, plan_features, comparison_matrix, api_pricing):
    """Aggregate pricing signals into a structured pricing intelligence report.

    Combines pricing_offers (plan prices), pricing_summary, plan_features,
    comparison_matrix, and api_pricing into a single pricingIntelligence blob.
    Returns {"detected": False} when no pricing data was extracted.
    """
    if not pricing_offers:
        return {"detected": False}

    core_plans = pricing_offers.get("corePlans") or []
    standalone = pricing_offers.get("standaloneProducts") or []
    mapping_confidence = pricing_offers.get("planMappingConfidence", 0.5)
    has_custom = pricing_offers.get("hasCustomPricing", False)

    if not core_plans and not standalone:
        return {"detected": False}

    # ── Subscription plan price range (non-free, non-team, non-enterprise) ─────
    _subscription_prices = [
        p["price"]["amount"]
        for p in core_plans
        if isinstance(p.get("price"), dict)
        and p["price"].get("amount") is not None
        and p["price"].get("amount") > 0
        and p.get("type") not in ("enterprise_plan", "team_plan")
    ]
    _subscription_price_range = (
        {"min": min(_subscription_prices), "max": max(_subscription_prices), "currency": "$"}
        if _subscription_prices else None
    )

    # ── Team seat price range ────────────────────────────────────────────────
    _team_seat_prices = [
        p["price"]["amount"]
        for p in core_plans
        if isinstance(p.get("price"), dict)
        and p["price"].get("amount") is not None
        and p.get("type") == "team_plan"
    ]
    _team_seat_range = (
        {"min": min(_team_seat_prices), "max": max(_team_seat_prices), "currency": "$"}
        if _team_seat_prices else None
    )

    # ── API model price range (from api_pricing.models[]) ────────────────────
    _api_model_range = None
    if api_pricing and api_pricing.get("models"):
        _api_prices = [
            m.get("price", {}).get("amount")
            for m in api_pricing.get("models", [])
            if isinstance(m.get("price"), dict) and m["price"].get("amount") is not None
        ]
        if _api_prices:
            _api_model_range = {
                "min": min(_api_prices),
                "max": max(_api_prices),
                "currency": "$",
            }

    # ── Platform / usage price range (from api_pricing.usagePricing) ────────
    _platform_usage_range = None
    if api_pricing and isinstance(api_pricing.get("usagePricing"), dict):
        _up = api_pricing["usagePricing"]
        if _up.get("min") is not None or _up.get("max") is not None:
            _platform_usage_range = _up

    return {
        "detected": True,
        "corePlans": core_plans,
        "standaloneProducts": standalone,
        "pricingSummary": pricing_summary or {},
        "planFeatures": plan_features or {},
        "comparisonMatrix": comparison_matrix or {},
        "apiPricing": api_pricing or {},
        "planMappingConfidence": mapping_confidence,
        "hasFreeOption": any(
            isinstance(p.get("price"), dict) and p["price"].get("amount") == 0
            for p in core_plans + standalone
        ),
        "hasCustomPricing": has_custom or any(
            (p.get("price") or {}).get("type") == "custom_plus_usage"
            for p in core_plans
        ),
        # Issue 11: Separated price ranges by segment
        "subscriptionPlanPriceRange": _subscription_price_range,
        "teamSeatPriceRange": _team_seat_range,
        "apiModelPriceRange": _api_model_range,
        "platformUsagePriceRange": _platform_usage_range,
        "notes": pricing_offers.get("notes", []),
    }

# =============================================================================
# V15 FIXES — Issues 1-16
# =============================================================================

# Issue 13: Service page text CTA patterns
_SERVICE_CTA_RE = re.compile(
    r"call\s+now\s+for\s+[^.!?\n]{5,70}"
    r"|call\s+to\s+(?:book|request|get)[^.!?\n]{5,70}"
    r"|book\s+(?:your|a|our)\s+[^.!?\n]{5,50}"
    r"|get\s+a\s+(?:free\s+)?(?:quote|consultation|estimate|callback)[^.!?\n]{0,40}"
    r"|request\s+a\s+(?:quote|callback|demo|consultation)[^.!?\n]{0,40}"
    r"|contact\s+(?:us|our\s+team)\s+(?:today|now)[^.!?\n]{0,40}"
    r"|speak\s+(?:to|with)\s+(?:our|an)\s+(?:team|expert|advisor)[^.!?\n]{0,40}"
    r"|schedule\s+(?:a|an)\s+(?:consultation|visit|appointment)[^.!?\n]{0,40}",
    re.I,
)


def _extract_service_page_text_ctas(text):
    """Extract text-only CTAs from service pages with no HTML/markdown links.

    Finds action-oriented phrases like 'Call now for licensed door supervisors'
    that are text-only (no anchor) but represent clear conversion intent.
    """
    text = text or ""
    ctas = []
    seen = set()
    for m in _SERVICE_CTA_RE.finditer(text):
        raw = clean_text(m.group(0)).rstrip(".!?,")
        if len(raw) < 10 or len(raw) > 100:
            continue
        key = raw.lower()
        if key not in seen:
            seen.add(key)
            ctas.append({"text": raw, "url": "", "source": "service_page_text"})
    return ctas[:6]


def _extract_service_intelligence(text, url):
    """Extract structured service intelligence for service_page subtype.

    Returns serviceType, industry, serviceArea, services[], trustSignals[], benefits[].
    """
    text = text or ""
    text_l = text.lower()

    # --- Service type / industry detection ---
    _SERVICE_TYPE_KEYWORDS = {
        "security_services": [
            "door supervisor", "door security", "sia", "sia-licensed", "security guard",
            "venue security", "event security", "bouncer",
        ],
        "cleaning_services": [
            "cleaning service", "house cleaning", "commercial cleaning", "domestic cleaning",
        ],
        "plumbing": ["plumbing", "plumber", "drain", "pipe repair", "boiler"],
        "electrical": ["electrician", "electrical service", "wiring", "rewiring"],
        "it_services": [
            "it support", "managed it", "it services", "helpdesk", "cyber security",
        ],
        "digital_marketing": [
            "digital marketing", "seo service", "social media marketing", "ppc",
        ],
        "legal": ["legal service", "solicitor", "law firm", "barrister", "conveyancing"],
        "healthcare": [
            "medical", "healthcare", "dental", "physiotherapy", "pharmacy",
        ],
        "financial": ["financial advice", "accounting", "bookkeeping", "tax service"],
        "construction": ["construction", "builder", "renovation", "roofing", "landscaping"],
        "catering": ["catering", "catering service", "food service", "event catering"],
        "transport": ["transport", "courier", "logistics", "haulage", "removal"],
    }
    detected_type = None
    for stype, kws in _SERVICE_TYPE_KEYWORDS.items():
        if any(kw in text_l for kw in kws):
            detected_type = stype
            break

    # --- Service area (location) ---
    service_area = None
    loc_m = re.search(
        r"(?:in|serving|based in|located in|covering|across)\s+([A-Z][a-z]+(?:[\s,]+[A-Z][a-z]+){0,2})",
        text,
    )
    if loc_m:
        service_area = clean_text(loc_m.group(1))

    # --- Services list (bullet-like items) ---
    services = []
    bullet_m = re.findall(
        r"(?:^|\n)\s*[•·▸▻►→✓✔\-]\s*([A-Za-z][^•·▸▻►→✓✔\-\n]{5,70})",
        text,
    )
    for s in bullet_m[:8]:
        s = clean_text(s).rstrip(".").strip()
        if s and 5 < len(s) < 70:
            services.append(s)

    # --- Trust signals ---
    trust_signals = []
    _TRUST_PATTERNS = {
        "licensed": ["licensed", "sia-licensed", "sia licensed"],
        "24_7_availability": ["24/7", "24 hours", "around the clock", "round the clock"],
        "rapid_deployment": ["rapid deployment", "fast response", "quick response", "immediate"],
        "experience": ["years of experience", "years' experience", "experienced", "established"],
        "insurance": ["insured", "fully insured", "liability insurance"],
        "accredited": ["accredited", "certified", "approved", "vetted"],
        "dbs_checked": ["dbs check", "dbs checked", "dbs cleared"],
    }
    for signal, pats in _TRUST_PATTERNS.items():
        if any(p in text_l for p in pats):
            trust_signals.append(signal)

    # --- Benefits (sentence-level) ---
    benefits = []
    benefit_m = re.findall(
        r"(?:^|\n|\.)\s*(?:Our|We offer|We provide|All our|Tailored|Rapid|Professional|Trusted|Dedicated)"
        r"[^.\n]{10,120}\.",
        text,
    )
    for b in benefit_m[:4]:
        b = clean_text(b).lstrip(". ")
        if b and len(b) > 10:
            benefits.append(b)

    return {
        "detected": True,
        "serviceType": detected_type,
        "serviceArea": service_area,
        "services": services[:6],
        "trustSignals": trust_signals,
        "benefits": benefits,
    }


# Issue 6: Reject patterns for CTAs from ALL sources (DOM + Jina)
_CTA_POST_REJECT_EXACT = {
    "workshops", "forum", "docs", "changelog", "security",
    "contact us", "download",
}
_CTA_DOUBLED_WORD_RE = re.compile(r"\b(\w{3,})\s+\1\b", re.I)  # "Contact Contact", etc.


def _post_clean_ctas(ctas):
    """Remove CTA noise after all sources have been merged.

    Filters:
    1. Exact text matches against _CTA_POST_REJECT_EXACT
    2. Doubled-word text ("Contact Contact sales")
    3. FAQ/footer context in URL
    """
    cleaned = []
    seen_text = set()
    seen_url = set()
    for c in ctas:
        text = (c.get("text") or "").strip()
        url = (c.get("url") or "").strip()
        text_l = text.lower()

        # Reject exact noise texts
        if text_l in _CTA_POST_REJECT_EXACT:
            continue

        # Reject doubled words ("Contact Contact sales")
        if _CTA_DOUBLED_WORD_RE.search(text):
            continue

        # Reject FAQ/forum anchor links
        _url_l = url.lower()
        if any(x in _url_l for x in ["source=pricing_faq", "source=navbar_contact", "/forum", "/workshops"]):
            continue

        # Dedup by normalised text
        key = text_l
        url_key = url.split("?")[0].rstrip("/")
        if key in seen_text:
            continue
        seen_text.add(key)
        if url_key and url_key in seen_url:
            continue
        if url_key:
            seen_url.add(url_key)

        cleaned.append(c)
    return cleaned


# Issue 1: Replacement _extract_seat_based_pricing using boundary-split approach
_SEAT_BILLED_AMOUNT_RE = re.compile(
    r"\$\s*(\d+(?:\.\d+)?)"
    r"(?:"
    r"\s+per\s+seat\s*/\s*month(?:\s+if\s+billed\s+(annually|monthly))?"
    r"|\s+if\s+billed\s+(annually|monthly)"
    r"|\s*/?\s*month\s+if\s+billed\s+(annually|monthly)"
    r")",
    re.I,
)


def _extract_seat_based_pricing(plan_name, block):
    """V2: Extract seat-based pricing using seat-type boundary splitting.

    Handles compact single-line text like:
      Standard seat $20 Per seat / month if billed annually. $25 if billed monthly.
      Premium seat $100 Per seat / month if billed annually. $125 if billed monthly.

    Returns (price_dict, metadata) or (None, None).
    """
    block = block or ""
    if not block:
        return None, None

    # Split block into per-seat-type sections using _SEAT_TYPE_RE boundaries
    seat_type_positions = [(m.start(), m.group(0)) for m in _SEAT_TYPE_RE.finditer(block)]

    seat_types = []
    if seat_type_positions:
        # Build segments: from this seat type to the next (or end)
        for i, (pos, seat_name) in enumerate(seat_type_positions):
            end = seat_type_positions[i + 1][0] if i + 1 < len(seat_type_positions) else len(block)
            segment = block[pos:end]
            annual_price = None
            monthly_price = None

            # Find all $amount + billing-qualifier patterns in this segment
            for m in _SEAT_BILLED_AMOUNT_RE.finditer(segment):
                amt = float(m.group(1))
                # Groups 2/3/4 = billing qualifier
                qual = next((g.lower() for g in (m.group(2), m.group(3), m.group(4)) if g), "")
                if "annual" in qual:
                    annual_price = amt
                elif "month" in qual:
                    monthly_price = amt
                else:
                    # No qualifier: first = annual, second = monthly
                    if annual_price is None:
                        annual_price = amt
                    elif monthly_price is None:
                        monthly_price = amt

            if annual_price is not None:
                seat_types.append({
                    "name": clean_text(seat_name),
                    "annualPrice": annual_price,
                    "monthlyPrice": monthly_price,
                })
    else:
        # No seat-type labels — try simple patterns
        annual_price = None
        monthly_price = None
        for m in _SEAT_BILLED_AMOUNT_RE.finditer(block):
            amt = float(m.group(1))
            qual = next((g.lower() for g in (m.group(2), m.group(3), m.group(4)) if g), "")
            if "annual" in qual:
                annual_price = amt
            elif "month" in qual:
                monthly_price = amt
            else:
                if annual_price is None:
                    annual_price = amt
                elif monthly_price is None:
                    monthly_price = amt

        if annual_price is not None:
            seat_types.append({
                "name": "Standard",
                "annualPrice": annual_price,
                "monthlyPrice": monthly_price,
            })

    # Fallback: simple seat-price pattern
    if not seat_types:
        sm = _SEAT_PRICE_RE.search(block)
        if sm:
            primary_annual = float(sm.group(1))
            seat_types.append({
                "name": "Standard",
                "annualPrice": primary_annual,
                "monthlyPrice": None,
            })

    if not seat_types:
        return None, None

    primary_annual = seat_types[0]["annualPrice"]
    price = {
        "currency": "$",
        "amount": primary_annual,
        "period": "/seat/mo",
        "raw": f"${primary_annual:.0f} per seat / month if billed annually",
    }
    billing = {
        "annualSeatPrice": seat_types[0]["annualPrice"],
        "monthlySeatPrice": seat_types[0].get("monthlyPrice"),
    }
    if len(seat_types) >= 2:
        billing["premiumAnnualSeatPrice"] = seat_types[1].get("annualPrice")
        billing["premiumMonthlySeatPrice"] = seat_types[1].get("monthlyPrice")

    return price, {"billing": billing, "seatTypes": seat_types, "type": "team_plan"}


# Issue 5: Clean junk from feature snippets
_PLAN_LABEL_TRANSITION_RE = re.compile(
    r"^(?:"
    r"(?:hobby|pro|teams?|enterprise|business|individual|free|starter|plus|ultra)\s+"
    r"(?:free|pro|pro\+|ultra|teams?|enterprise|business|plus|starter)?\s*"
    r"(?:includes?:|everything\s+in\s+\w+,?\s+plus:?)"
    r"|everything\s+in\s+\w+,?\s+plus:?"
    r")",
    re.I,
)
_SNIPPET_CTA_WORDS = {
    "get pro", "get teams", "get started", "start free", "start trial",
    "contact sales", "book demo", "try free", "try for free",
    "sign up", "get enterprise",
}
_SNIPPET_REJECT_SUFFIX_RE = re.compile(
    r"(?:\s+get\s+\w+|\s+sign\s+up|\s+start\s+\w+|\s+contact\s+\w+)$",
    re.I,
)


def _clean_feature_snippets(snippets, plan_name):
    """Strip plan labels, transition phrases, and CTA text from feature snippets.

    Handles patterns like:
      'Hobby Free Includes:'               → rejected (pure label)
      'Pro Pro+ Ultra Everything in Hobby, plus:' → rejected (pure transition)
      'SAML/OIDC SSO Get Teams'            → cleaned to 'SAML/OIDC SSO'
    """
    cleaned = []
    for s in snippets:
        # Reject pure label/transition snippets
        if _PLAN_LABEL_TRANSITION_RE.match(s):
            continue
        # Reject if entire text is a CTA
        if s.lower() in _SNIPPET_CTA_WORDS:
            continue
        # Strip trailing CTA suffix ("SAML/OIDC SSO Get Teams" → "SAML/OIDC SSO")
        s_clean = _SNIPPET_REJECT_SUFFIX_RE.sub("", s).strip()
        if len(s_clean) >= 8:
            cleaned.append(s_clean)
        elif len(s) >= 8:
            # Keep original if cleaning removed too much
            cleaned.append(s)
    return cleaned


# Issue 4+5: Replacement extract_plan_features with snippet cleaning + full-text fallback
def extract_plan_features(text, core_plans):
    """V12: Extract compact feature snippets per plan with junk cleaning.

    Improvements:
    - Uses section text with extended fallback to full text for Team/Enterprise
    - Strips plan label/transition phrases and CTA text from snippets
    """
    if not text or not core_plans:
        return {}

    section = get_main_pricing_section(text)
    names = [p.get("name") for p in core_plans if p.get("name")]
    blocks, _ = extract_named_blocks(section, names)
    # Also try full-text blocks for plans not found in section
    _full_blocks, _ = extract_named_blocks(text[:8000], names)

    numeric_patterns = {
        "projects": r"(\d[\d,]*)\s+projects?",
        "trackedKeywords": r"(\d[\d,]*)\s+(?:tracked\s+)?keywords?(?:\s+to\s+track)?",
        "trackedPrompts": r"(\d[\d,]*)\s+(?:tracked\s+)?prompts?(?:\s+to\s+track)?",
        "crawlCredits": r"(\d[\d,]*)\s+crawl credits",
        "usersIncluded": r"(\d[\d,]*)\s+users? included|included users\s+(\d[\d,]*)",
        "websitesToMonitor": r"(?:up to\s+)?(\d[\d,]*)\s+websites? to monitor",
        "storage": r"(\d[\d,]*(?:\.\d+)?)\s*(gb|tb)\s+of cloud storage|storage\s+(\d[\d,]*(?:\.\d+)?)\s*(gb|tb)",
        "brandKits": r"(\d[\d,]*)\s+brand kits?",
        "templates": r"(\d[\d,.]*\s*[mk]\+?)\s+templates",
    }

    stop_tokens = ["get started", "try for free", "start a free trial", "contact sales", "book a demo"]

    output = {}
    for plan in core_plans:
        name = plan.get("name")
        # Prefer section block; fall back to full-text block for Team/Enterprise
        data = blocks.get((name or "").lower())
        if not data:
            data = _full_blocks.get((name or "").lower())
        if not data:
            continue
        block = data["text"]
        block_l = block.lower()
        found = {}

        for key, pattern in numeric_patterns.items():
            pm = re.search(pattern, block, flags=re.I)
            if pm:
                groups = [g for g in pm.groups() if g]
                if groups:
                    value = groups[0]
                    if key == "storage" and len(groups) >= 2:
                        found[key] = f"{groups[0]} {groups[1].upper()}"
                    else:
                        try:
                            found[key] = int(value.replace(",", ""))
                        except Exception:
                            found[key] = value

        # Extract short textual features
        sentences = re.split(r"(?:✓|•|\n|\.\s+)", block)
        snippets = []
        for s in sentences:
            s = clean_text(s)
            if not s or len(s) < 8 or len(s) > 120:
                continue
            s_l = s.lower()
            if s_l == (name or "").lower() or any(tok in s_l for tok in stop_tokens):
                continue
            if any(x in s_l for x in [
                "includes", "everything in", "access", "storage", "templates", "brand kit",
                "usage", "sso", "admin", "security", "projects", "keywords", "cloud",
                "collaboration", "analytics", "premium", "ai", "code", "audit",
                "unlimited", "billing", "support", "agent", "deployment",
            ]):
                snippets.append(s)
            if len(snippets) >= 10:
                break

        # Clean junk from snippets
        snippets = _clean_feature_snippets(snippets, name)[:8]

        if snippets:
            found["featureSnippets"] = snippets

        if found:
            output[name] = found

    return output


# Issue 2+7+9: Replacement build_pricing_intelligence with corrected API ranges / team seat / currency
def build_pricing_intelligence(text, pricing_offers, pricing_summary, plan_features, comparison_matrix, api_pricing):
    """V3: Aggregate pricing signals into a structured pricing intelligence report.

    Fixes:
    - Issue 2: apiModelPriceRange uses extract_api_pricing's modelRates key
    - Issue 7: teamSeatPriceRange includes plans with name 'team*' even when type != 'team_plan'
    - Issue 9: subscriptionPlanPriceRange.currency inferred from actual plan currencies
    """
    if pricing_offers is None:
        return {"detected": False}

    core_plans = (pricing_offers or {}).get("corePlans") or []
    standalone = (pricing_offers or {}).get("standaloneProducts") or []
    mapping_confidence = (pricing_offers or {}).get("planMappingConfidence", 0.5)
    has_custom = (pricing_offers or {}).get("hasCustomPricing", False)

    # Issue 2: don't early-return when api_pricing has model/usage rates
    if not core_plans and not standalone and not (api_pricing and (api_pricing.get("modelRates") or api_pricing.get("usageRates"))):
        return {"detected": False}

    # ── Subscription plan price range (non-free, non-team, non-enterprise) ─────
    _sub_amounts = []
    _sub_currencies = []
    for p in core_plans:
        if not isinstance(p.get("price"), dict):
            continue
        pr = p["price"]
        if pr.get("amount") is None or pr.get("amount") == 0:
            continue
        if p.get("type") in ("enterprise_plan", "team_plan"):
            continue
        _plan_name_l = (p.get("name") or "").lower()
        if _plan_name_l in ("team", "teams", "enterprise", "enterprise+", "enterprise plus"):
            continue
        _sub_amounts.append(pr["amount"])
        if pr.get("currency"):
            _sub_currencies.append(pr["currency"])

    _subscription_price_range = None
    if _sub_amounts:
        # Issue 9: Only include currency when at least one plan has a real currency symbol
        _currency = _sub_currencies[0] if _sub_currencies else None
        _subscription_price_range = {
            "min": min(_sub_amounts),
            "max": max(_sub_amounts),
            "currency": _currency,
        }

    # ── Team seat price range ────────────────────────────────────────────────
    # Issue 7: include plans with type==team_plan OR name containing 'team'/'teams'
    # with a per-user pricing structure
    _team_amounts = []
    _team_currencies = []
    for p in core_plans:
        if not isinstance(p.get("price"), dict):
            continue
        pr = p["price"]
        if pr.get("amount") is None:
            continue
        _is_team_type = p.get("type") == "team_plan"
        _is_team_name = (p.get("name") or "").lower() in ("team", "teams")
        _is_per_user = (pr.get("period") or "").lower() in ("/user/mo", "/user", "/seat/mo")
        if _is_team_type or (_is_team_name and _is_per_user):
            _team_amounts.append(pr["amount"])
            if pr.get("currency"):
                _team_currencies.append(pr["currency"])
            # Also include premium seat types from billing
            billing = p.get("billing") or {}
            if billing.get("premiumAnnualSeatPrice"):
                _team_amounts.append(billing["premiumAnnualSeatPrice"])

    _team_seat_range = None
    if _team_amounts:
        _team_currency = _team_currencies[0] if _team_currencies else None
        _team_seat_range = {
            "min": min(_team_amounts),
            "max": max(_team_amounts),
            "currency": _team_currency,
        }


    # ── API model price range (from api_pricing.modelRates) ──────────────────
    # Issue 2: extract_api_pricing returns modelRates (not models)
    _api_model_range = None
    if api_pricing and api_pricing.get("modelRates"):
        _input_prices = [
            r.get("inputPerMTok")
            for r in api_pricing["modelRates"]
            if r.get("inputPerMTok") is not None
        ]
        _output_prices = [
            r.get("outputPerMTok")
            for r in api_pricing["modelRates"]
            if r.get("outputPerMTok") is not None
        ]
        if _input_prices or _output_prices:
            _all_prices = _input_prices + _output_prices
            _ir = {"min": min(_input_prices), "max": max(_input_prices)} if _input_prices else None
            _or = {"min": min(_output_prices), "max": max(_output_prices)} if _output_prices else None
            _api_model_range = {
                "lowestPerMTok": min(_all_prices),
                "highestPerMTok": max(_all_prices),
                "currency": "$",
                "inputRange": _ir,
                "outputRange": _or,
            }

    # ── Platform / usage price range (from api_pricing.usageRates) ───────────
    _platform_usage_range = None
    if api_pricing:
        if api_pricing.get("usageRates"):
            _usage_amounts = [
                r.get("amount")
                for r in api_pricing["usageRates"]
                if r.get("amount") is not None
            ]
            if _usage_amounts:
                _platform_usage_range = {
                    "min": min(_usage_amounts),
                    "max": max(_usage_amounts),
                    "currency": "$",
                    "rates": api_pricing["usageRates"],
                }
        elif isinstance(api_pricing.get("usagePricing"), dict):
            _up = api_pricing["usagePricing"]
            if _up.get("min") is not None or _up.get("max") is not None:
                _platform_usage_range = _up

    return {
        "detected": True,
        "corePlans": core_plans,
        "standaloneProducts": standalone,
        "pricingSummary": pricing_summary or {},
        "planFeatures": plan_features or {},
        "comparisonMatrix": comparison_matrix or {},
        "apiPricing": api_pricing or {},
        "planMappingConfidence": mapping_confidence,
        "hasFreeOption": any(
            isinstance(p.get("price"), dict) and p["price"].get("amount") == 0
            for p in core_plans + standalone
        ),
        "hasCustomPricing": has_custom or any(
            (p.get("price") or {}).get("type") == "custom_plus_usage"
            for p in core_plans
        ),
        "subscriptionPlanPriceRange": _subscription_price_range,
        "teamSeatPriceRange": _team_seat_range,
        "apiModelPriceRange": _api_model_range,
        "platformUsagePriceRange": _platform_usage_range,
        "notes": pricing_offers.get("notes", []),
    }


# Issues 5 (V2): _clean_feature_snippets — handle N-word plan-name chains
# Original V1 had a fixed 2-word plan-name prefix pattern; real pages like Cursor
# emit "Pro Pro+ Ultra Everything in Hobby, plus: ..." with 3+ plan tokens.
_PLAN_NAME_WORDS = frozenset({
    "hobby", "free", "pro", "plus", "ultra", "teams", "team",
    "enterprise", "business", "individual", "starter", "basic",
    "standard", "premium",
})
_TRANSITION_RE = re.compile(
    r"(?:includes?:|everything\s+in\s+\w[\w\s]*?,?\s*plus:?)",
    re.I,
)

def _clean_feature_snippets(snippets, plan_name):
    """V2: Strip plan-label chains (any length) + transition phrases + trailing CTAs.

    Handles:
      'Hobby Free Includes: 2000 completions'  → 'Includes:' removed, body kept
      'Pro Pro+ Ultra Everything in Hobby, plus: Unlimited completions' → body kept
      'Normal feature text'  → kept as-is
      'SAML/OIDC SSO Get Teams' → stripped to 'SAML/OIDC SSO'
    """
    cleaned = []
    for s in (snippets or []):
        s = (s or "").strip()
        if not s:
            continue

        # Check for a transition marker inside the text.
        # If found, keep only what comes AFTER the marker (that's the actual feature text).
        m_trans = _TRANSITION_RE.search(s)
        if m_trans:
            after = s[m_trans.end():].strip(": ").strip()
            if len(after) >= 8:
                s = after
            else:
                # Nothing useful after the marker → reject entirely
                continue
        else:
            # No transition marker — check if the whole string is a plan-label prefix.
            # Strategy: split by whitespace, count leading plan-name tokens.
            # If ALL tokens are plan names, reject.
            tokens = s.split()
            plan_token_count = 0
            for tok in tokens:
                if tok.lower().rstrip("+") in _PLAN_NAME_WORDS:
                    plan_token_count += 1
                else:
                    break
            if plan_token_count == len(tokens):
                continue  # pure plan label, no content

        # Strip trailing CTA suffix
        s_clean = _SNIPPET_REJECT_SUFFIX_RE.sub("", s).strip()
        if s_clean.lower() in _SNIPPET_CTA_WORDS:
            continue
        if len(s_clean) >= 8:
            cleaned.append(s_clean)
        elif len(s) >= 8:
            cleaned.append(s)
    return cleaned


# =============================================================================
# Session 3 targeted fixes — Issues 1–11
# Last-def-wins: these definitions override earlier versions
# =============================================================================

# ── Issue 6: Remove "download" from post-reject set ──────────────────────────
# "download" is a valid primary CTA (e.g. Cursor Hobby plan "Download").
# App-store download links are already caught by _JINA_CTA_REJECT_EXACT / URL filters.
_CTA_POST_REJECT_EXACT = {
    "workshops", "forum", "docs", "changelog", "security",
    "contact us",
}
_CTA_DOUBLED_WORD_RE = re.compile(r"\b(\w{3,})\s+\1\b", re.I)


def _post_clean_ctas(ctas):
    """V2: Remove CTA noise after all sources merged. 'download' no longer rejected."""
    cleaned = []
    seen_text = set()
    seen_url = set()
    for c in ctas:
        text = (c.get("text") or "").strip()
        url = (c.get("url") or "").strip()
        text_l = text.lower()
        if text_l in _CTA_POST_REJECT_EXACT:
            continue
        if _CTA_DOUBLED_WORD_RE.search(text):
            continue
        _url_l = url.lower()
        if any(x in _url_l for x in ["source=pricing_faq", "source=navbar_contact", "/forum", "/workshops"]):
            continue
        key = text_l
        url_key = url.split("?")[0].rstrip("/")
        if key in seen_text:
            continue
        seen_text.add(key)
        if url_key and url_key in seen_url:
            continue
        if url_key:
            seen_url.add(url_key)
        cleaned.append(c)
    return cleaned


# ── Issue 7: Fix _TRANSITION_RE to also match "Everything on X, plus:" ───────
# Cursor uses "Everything on Individual, plus:" not "Everything in …"
_TRANSITION_RE = re.compile(
    r"(?:includes?:|everything\s+(?:in|on)\s+\w[\w\s]*?,?\s*plus:?)",
    re.I,
)


def _clean_feature_snippets(snippets, plan_name):
    """V3: Strip plan-label chains + transition phrases. Handles 'on' variant.

    Fixes:
      'Standard Premium Everything on Individual, plus: ...' → body after 'plus:'
      'Pro Pro+ Ultra Everything in Hobby, plus: ...'        → body after 'plus:'
    """
    cleaned = []
    for s in (snippets or []):
        s = (s or "").strip()
        if not s:
            continue
        m_trans = _TRANSITION_RE.search(s)
        if m_trans:
            after = s[m_trans.end():].strip(": ").strip()
            if len(after) >= 8:
                s = after
            else:
                continue
        else:
            tokens = s.split()
            plan_token_count = 0
            for tok in tokens:
                if tok.lower().rstrip("+") in _PLAN_NAME_WORDS:
                    plan_token_count += 1
                else:
                    break
            if plan_token_count == len(tokens):
                continue
        s_clean = _SNIPPET_REJECT_SUFFIX_RE.sub("", s).strip()
        if s_clean.lower() in _SNIPPET_CTA_WORDS:
            continue
        if len(s_clean) >= 8:
            cleaned.append(s_clean)
        elif len(s) >= 8:
            cleaned.append(s)
    return cleaned


# ── Issue 2: Fix _extract_seat_based_pricing false match for "than standard seats*"
def _extract_seat_based_pricing(plan_name, block):
    """V3: Filter seat-type matches that appear in descriptive context (not as labels).

    Bug: _SEAT_TYPE_RE matched 'standard seat' inside '…more usage than standard seats*…'
    creating a phantom 3rd seat type with the premium prices.
    Fix: skip any match preceded within 15 chars by 'than', 'of', 'as', 'for', 'more'.
    """
    block = block or ""
    if not block:
        return None, None

    # Build seat_type_positions, skipping description-context matches
    _CONTEXT_PRECURSOR_RE = re.compile(r"\b(than|more|of|as|for)\s*$", re.I)
    seat_type_positions = []
    for m in _SEAT_TYPE_RE.finditer(block):
        pre = block[max(0, m.start() - 15):m.start()]
        if _CONTEXT_PRECURSOR_RE.search(pre):
            continue  # This is "than standard seat" / "more than … seat" — skip
        seat_type_positions.append((m.start(), m.group(0)))

    seat_types = []
    if seat_type_positions:
        for i, (pos, seat_name) in enumerate(seat_type_positions):
            end = seat_type_positions[i + 1][0] if i + 1 < len(seat_type_positions) else len(block)
            segment = block[pos:end]
            annual_price = None
            monthly_price = None
            for m in _SEAT_BILLED_AMOUNT_RE.finditer(segment):
                amt = float(m.group(1))
                qual = next((g.lower() for g in (m.group(2), m.group(3), m.group(4)) if g), "")
                if "annual" in qual:
                    annual_price = amt
                elif "month" in qual:
                    monthly_price = amt
                else:
                    if annual_price is None:
                        annual_price = amt
                    elif monthly_price is None:
                        monthly_price = amt
            if annual_price is not None:
                seat_types.append({
                    "name": clean_text(seat_name),
                    "annualPrice": annual_price,
                    "monthlyPrice": monthly_price,
                })
    else:
        annual_price = None
        monthly_price = None
        for m in _SEAT_BILLED_AMOUNT_RE.finditer(block):
            amt = float(m.group(1))
            qual = next((g.lower() for g in (m.group(2), m.group(3), m.group(4)) if g), "")
            if "annual" in qual:
                annual_price = amt
            elif "month" in qual:
                monthly_price = amt
            else:
                if annual_price is None:
                    annual_price = amt
                elif monthly_price is None:
                    monthly_price = amt
        if annual_price is not None:
            seat_types.append({
                "name": "Standard",
                "annualPrice": annual_price,
                "monthlyPrice": monthly_price,
            })

    if not seat_types:
        sm = _SEAT_PRICE_RE.search(block)
        if sm:
            seat_types.append({
                "name": "Standard",
                "annualPrice": float(sm.group(1)),
                "monthlyPrice": None,
            })

    if not seat_types:
        return None, None

    primary_annual = seat_types[0]["annualPrice"]
    price = {
        "currency": "$",
        "amount": primary_annual,
        "period": "/seat/mo",
        "raw": f"${primary_annual:.0f} per seat / month if billed annually",
    }
    billing = {
        "annualSeatPrice": seat_types[0]["annualPrice"],
        "monthlySeatPrice": seat_types[0].get("monthlyPrice"),
    }
    if len(seat_types) >= 2:
        billing["premiumAnnualSeatPrice"] = seat_types[1].get("annualPrice")
        billing["premiumMonthlySeatPrice"] = seat_types[1].get("monthlyPrice")

    return price, {"billing": billing, "seatTypes": seat_types, "type": "team_plan"}


# ── Issues 3+8: Fix build_pricing_intelligence — include all seat billing prices ─
def build_pricing_intelligence(text, pricing_offers, pricing_summary, plan_features, comparison_matrix, api_pricing):
    """V4: Aggregate pricing signals into a structured pricing intelligence report.

    Fixes v3→v4:
    - Issue 3: teamSeatPriceRange.max now includes premiumMonthlySeatPrice (was only
      premiumAnnualSeatPrice, giving max=100 instead of 125 for Claude Team).
    - Issue 8: teamSeatPriceRange includes period="/seat/mo"; subscriptionPlanPriceRange
      gains a notes[] field when teams are separated into teamSeatPriceRange.
    """
    if pricing_offers is None:
        return {"detected": False}

    core_plans = (pricing_offers or {}).get("corePlans") or []
    standalone = (pricing_offers or {}).get("standaloneProducts") or []
    mapping_confidence = (pricing_offers or {}).get("planMappingConfidence", 0.5)
    has_custom = (pricing_offers or {}).get("hasCustomPricing", False)

    if not core_plans and not standalone and not (api_pricing and (api_pricing.get("modelRates") or api_pricing.get("usageRates"))):
        return {"detected": False}

    # ── Subscription plan price range ────────────────────────────────────────
    _sub_amounts = []
    _sub_currencies = []
    for p in core_plans:
        if not isinstance(p.get("price"), dict):
            continue
        pr = p["price"]
        if pr.get("amount") is None or pr.get("amount") == 0:
            continue
        if p.get("type") in ("enterprise_plan", "team_plan"):
            continue
        _plan_name_l = (p.get("name") or "").lower()
        if _plan_name_l in ("team", "teams", "enterprise", "enterprise+", "enterprise plus"):
            continue
        _sub_amounts.append(pr["amount"])
        if pr.get("currency"):
            _sub_currencies.append(pr["currency"])

    _subscription_price_range = None
    if _sub_amounts:
        _currency = _sub_currencies[0] if _sub_currencies else None
        _subscription_price_range = {
            "min": min(_sub_amounts),
            "max": max(_sub_amounts),
            "currency": _currency,
        }

    # ── Team seat price range ────────────────────────────────────────────────
    _team_amounts = []
    _team_currencies = []
    _has_team_plans = False
    for p in core_plans:
        if not isinstance(p.get("price"), dict):
            continue
        pr = p["price"]
        if pr.get("amount") is None:
            continue
        _is_team_type = p.get("type") == "team_plan"
        _is_team_name = (p.get("name") or "").lower() in ("team", "teams")
        _is_per_user = (pr.get("period") or "").lower() in ("/user/mo", "/user", "/seat/mo")
        if _is_team_type or (_is_team_name and _is_per_user):
            _has_team_plans = True
            _team_amounts.append(pr["amount"])
            if pr.get("currency"):
                _team_currencies.append(pr["currency"])
            # Include ALL billing seat prices (annual + monthly, standard + premium)
            billing = p.get("billing") or {}
            for _bkey in ("annualSeatPrice", "monthlySeatPrice",
                          "premiumAnnualSeatPrice", "premiumMonthlySeatPrice"):
                if billing.get(_bkey) is not None:
                    _team_amounts.append(billing[_bkey])

    _team_seat_range = None
    if _team_amounts:
        _team_currency = _team_currencies[0] if _team_currencies else None
        _team_seat_range = {
            "min": min(_team_amounts),
            "max": max(_team_amounts),
            "currency": _team_currency,
            "period": "/seat/mo",
        }
    # If teams are represented in teamSeatPriceRange, note it on subscriptionRange
    if _has_team_plans and _subscription_price_range:
        _subscription_price_range.setdefault("notes", []).append(
            "Teams plan represented separately as teamSeatPriceRange"
        )

    # ── API model price range ─────────────────────────────────────────────────
    _api_model_range = None
    if api_pricing and api_pricing.get("modelRates"):
        _input_prices = [r.get("inputPerMTok") for r in api_pricing["modelRates"] if r.get("inputPerMTok") is not None]
        _output_prices = [r.get("outputPerMTok") for r in api_pricing["modelRates"] if r.get("outputPerMTok") is not None]
        if _input_prices or _output_prices:
            _all_prices = _input_prices + _output_prices
            _ir = {"min": min(_input_prices), "max": max(_input_prices)} if _input_prices else None
            _or = {"min": min(_output_prices), "max": max(_output_prices)} if _output_prices else None
            _api_model_range = {
                "lowestPerMTok": min(_all_prices),
                "highestPerMTok": max(_all_prices),
                "currency": "$",
                "inputRange": _ir,
                "outputRange": _or,
            }

    # ── Platform / usage price range ─────────────────────────────────────────
    _platform_usage_range = None
    if api_pricing:
        if api_pricing.get("usageRates"):
            _usage_amounts = [r.get("amount") for r in api_pricing["usageRates"] if r.get("amount") is not None]
            if _usage_amounts:
                _platform_usage_range = {
                    "min": min(_usage_amounts),
                    "max": max(_usage_amounts),
                    "currency": "$",
                    "rates": api_pricing["usageRates"],
                }
        elif isinstance(api_pricing.get("usagePricing"), dict):
            _up = api_pricing["usagePricing"]
            if _up.get("min") is not None or _up.get("max") is not None:
                _platform_usage_range = _up

    return {
        "detected": True,
        "corePlans": core_plans,
        "standaloneProducts": standalone,
        "pricingSummary": pricing_summary or {},
        "planFeatures": plan_features or {},
        "comparisonMatrix": comparison_matrix or {},
        "apiPricing": api_pricing or {},
        "planMappingConfidence": mapping_confidence,
        "hasFreeOption": any(
            isinstance(p.get("price"), dict) and p["price"].get("amount") == 0
            for p in core_plans + standalone
        ),
        "hasCustomPricing": has_custom or any(
            (p.get("price") or {}).get("type") == "custom_plus_usage"
            for p in core_plans
        ),
        "subscriptionPlanPriceRange": _subscription_price_range,
        "teamSeatPriceRange": _team_seat_range,
        "apiModelPriceRange": _api_model_range,
        "platformUsagePriceRange": _platform_usage_range,
        "notes": pricing_offers.get("notes", []),
    }


# ── Issue 5: Fix extract_plan_features with permissive filter + inline splitting ─
def extract_plan_features(text, core_plans):
    """V13 superseded by V15 (last-def-wins)."""
    return {}

def extract_plan_features(text, core_plans):
    """V14: Permissive feature extraction with improved fragment/price filtering.

    Changes from V13:
    - Inline split skips boundaries before known plan-name words (avoids "Everything in" + "Free, plus:" split)
    - Minimum 3-word filter removes short fragments
    - Plan-header price lines (containing '$N per month' / 'billed') are rejected
    - Orphan ', plus: ...' transition tails are extracted cleanly
    """
    if not text or not core_plans:
        return {}

    section = get_main_pricing_section(text)
    names = [p.get("name") for p in core_plans if p.get("name")]
    blocks, _ = extract_named_blocks(section, names)
    _full_blocks, _ = extract_named_blocks(text[:8000], names)

    numeric_patterns = {
        "projects": r"(\d[\d,]*)\s+projects?",
        "trackedKeywords": r"(\d[\d,]*)\s+(?:tracked\s+)?keywords?(?:\s+to\s+track)?",
        "trackedPrompts": r"(\d[\d,]*)\s+(?:tracked\s+)?prompts?(?:\s+to\s+track)?",
        "crawlCredits": r"(\d[\d,]*)\s+crawl credits",
        "usersIncluded": r"(\d[\d,]*)\s+users? included|included users\s+(\d[\d,]*)",
        "websitesToMonitor": r"(?:up to\s+)?(\d[\d,]*)\s+websites? to monitor",
        "storage": r"(\d[\d,]*(?:\.\d+)?)\s*(gb|tb)\s+of cloud storage|storage\s+(\d[\d,]*(?:\.\d+)?)\s*(gb|tb)",
        "brandKits": r"(\d[\d,]*)\s+brand kits?",
        "templates": r"(\d[\d,.]*\s*[mk]\+?)\s+templates",
    }

    _REPEATED_CTA_RE = re.compile(
        r"(?:Try\s+\S+|Get\s+Started|Contact\s+Sales|Learn\s+More|Try\s+Free|Sign\s+Up)"
        r"(?:\s+(?:Try\s+\S+|Get\s+Started|Contact\s+Sales|Learn\s+More|Try\s+Free|Sign\s+Up))+",
        re.I,
    )
    # Plan-header price line: "$N per month", "billed annually", etc.
    _PRICE_DESC_RE = re.compile(
        r"\$\s*\d+.*(?:per\s+month|if\s+billed|billed\s+up\s+front|per\s+seat|per\s+year)",
        re.I,
    )
    # Orphan tail like "Free, plus: More usage*" — extract after "plus:"
    _ORPHAN_PLUS_RE = re.compile(r"^[\w\s,\.]+,\s*plus:\s*(.+)", re.I)

    # Inline split: capital boundary but NOT before known plan-name words
    _PLAN_NAMES_SET = "|".join([
        "Free", "Pro", "Max", "Team", "Teams", "Enterprise", "Business",
        "Individual", "Hobby", "Starter", "Plus", "Ultra", "Basic", "Standard", "Premium",
    ])
    # Split at lowercase→uppercase boundary, but skip if next word is a plan name
    _INLINE_SPLIT_RE = re.compile(
        r"(?<=[a-z*,])\s{1,3}(?=[A-Z][a-z]{2,})"
        r"(?!" + _PLAN_NAMES_SET + r"\b)",
    )

    stop_tokens = {
        "get started", "try for free", "start a free trial", "contact sales",
        "book a demo", "try claude", "try free", "try it free", "learn more",
    }

    output = {}
    for plan in core_plans:
        name = plan.get("name")
        data = blocks.get((name or "").lower())
        if not data or len((data.get("text") or "")) < 100:
            data = _full_blocks.get((name or "").lower())
        if not data:
            continue
        block = data["text"]
        found = {}

        for key, pattern in numeric_patterns.items():
            pm = re.search(pattern, block, flags=re.I)
            if pm:
                groups = [g for g in pm.groups() if g]
                if groups:
                    value = groups[0]
                    if key == "storage" and len(groups) >= 2:
                        found[key] = f"{groups[0]} {groups[1].upper()}"
                    else:
                        try:
                            found[key] = int(value.replace(",", ""))
                        except Exception:
                            found[key] = value

    return output


# =============================================================================
# SESSION 4 OVERRIDES — appended via last-def-wins
# =============================================================================

# ── Issue 5: Add "learn more" to post-reject (too generic as primary CTA) ────
_CTA_POST_REJECT_EXACT = {
    "workshops", "forum", "docs", "changelog", "security",
    "contact us", "learn more",
}

# ── Issues 6/7: Extend suffix rejection to strip trailing 'download' CTAs ────
_SNIPPET_REJECT_SUFFIX_RE = re.compile(
    r"(?:\s+get\s+\w+(?:\s+\w+)?|\s+sign\s+up|\s+start\s+\w+|\s+contact\s+\w+|\s+download)$",
    re.I,
)


# ── Issue 3: _extract_service_intelligence V3 ─────────────────────────────────
# Changes from V2:
# - "door security supervisors" + "office security" added to _SERVICE_KEYWORDS
# - Benefit regex capped at 55 chars (avoids long run-on fragments)
# - Benefits trimmed at first period/newline
def _extract_service_intelligence(text, url):
    """V3: More accurate services list + cleaner benefit phrases."""
    text = text or ""
    text_l = text.lower()
    url_l = (url or "").lower()

    _TYPE_MAP = [
        (["door supervisor", "door security supervisor", "door security supervisors",
          "sia-licensed door"], "door_security_supervisors", "security_services"),
        (["cctv", "cctv monitoring", "cctv surveillance"], "cctv_monitoring", "security_services"),
        (["event security", "event steward"], "event_security", "security_services"),
        (["manned guard", "security guard", "guard service"], "manned_guarding", "security_services"),
        (["web hosting", "hosting plan", "shared hosting", "vps hosting",
          "cloud hosting", "dedicated server"], "web_hosting", "hosting"),
        (["seo service", "search engine optimisation", "search engine optimization",
          "link building", "keyword ranking"], "seo_services", "digital_marketing"),
        (["plumbing", "plumber"], "plumbing", "home_services"),
        (["electrician", "electrical service"], "electrical", "home_services"),
        (["security service", "security solution", "professional security"], "security_services", "security"),
    ]
    service_type = None
    industry = None
    for kws, stype, ind in _TYPE_MAP:
        if any(kw in text_l for kw in kws) or any(kw in url_l for kw in kws):
            service_type = stype
            industry = ind
            break
    if not service_type:
        return {"detected": False}

    _LOCATION_RE = re.compile(
        r"\b(?:in|across|throughout|serving|covering|based in|based at)\s+"
        r"([A-Z][a-zA-Z\s\-]{2,30}?)(?=[,\.!\s]|$)",
    )
    _CITY_PATTERN_RE = re.compile(
        r"\b(London|Birmingham|Manchester|Leeds|Liverpool|Sheffield|Bristol|"
        r"Edinburgh|Glasgow|Cardiff|Belfast|Newcastle|Nottingham|Leicester|"
        r"Southampton|Portsmouth|Bradford|Coventry|Reading|Derby|Brighton)\b"
    )
    service_areas = []
    seen_areas = set()
    for m in _LOCATION_RE.finditer(text):
        loc = m.group(1).strip().title()
        if loc.lower() not in seen_areas and len(loc) > 2:
            service_areas.append(loc)
            seen_areas.add(loc.lower())
    for m in _CITY_PATTERN_RE.finditer(text):
        loc = m.group(1).strip()
        if loc.lower() not in seen_areas:
            service_areas.append(loc)
            seen_areas.add(loc.lower())
    if not service_areas:
        service_areas = ["Not specified"]

    # V3: Added door security supervisors + office security
    _SERVICE_KEYWORDS = {
        "door security supervisor": "Door security supervisors",
        "door security supervisors": "Door security supervisors",
        "office security": "Office security",
        "entry management": "Entry management",
        "crowd control": "Crowd control",
        "conflict resolution": "Conflict resolution",
        "conflict management": "Conflict management",
        "id check": "ID checking",
        "identification": "Identification verification",
        "queue management": "Queue management",
        "access control": "Access control",
        "cctv": "CCTV monitoring",
        "patrol": "Security patrol",
        "event security": "Event security",
        "manned guard": "Manned guarding",
        "venue security": "Venue security",
        "retail security": "Retail security",
        "security officer": "Security officers",
    }
    services = []
    seen_services = set()
    for kw, label in _SERVICE_KEYWORDS.items():
        if kw in text_l and label.lower() not in seen_services:
            services.append(label)
            seen_services.add(label.lower())

    trust_signals = []
    if any(x in text_l for x in ["sia", "sia-licensed", "sia licensed"]):
        trust_signals.append("SIA-licensed professionals")
    if "24/7" in text_l or "24 7" in text_l or "24-hour" in text_l:
        trust_signals.append("24/7 operations support")
    if any(x in text_l for x in ["rapid deployment", "rapid response"]):
        trust_signals.append("Rapid deployment within 24-48 hours")
    if any(x in text_l for x in ["fully insured", "insured and bonded"]):
        trust_signals.append("Fully insured and bonded")
    if any(x in text_l for x in ["dbs check", "crb check", "background check"]):
        trust_signals.append("DBS-checked personnel")
    if any(x in text_l for x in ["trained", "professional training", "fully trained"]):
        trust_signals.append("Professionally trained staff")
    if any(x in text_l for x in ["customer service", "customer-focused", "customer focused"]):
        trust_signals.append("Customer-focused approach")

    # V3: Capped at 55 chars; trimmed at first period/newline to avoid run-ons
    benefits = []
    _BENEFIT_SENTENCE_RE = re.compile(
        r"(?:fully\s+|rapid\s+|professional\s+|customer-?focused\s+|"
        r"tailored\s+|experienced\s+|qualified\s+|licensed\s+|certified\s+)"
        r"[A-Za-z][A-Za-z0-9 ,\-]{4,55}",
        re.I | re.M,
    )
    for m in _BENEFIT_SENTENCE_RE.finditer(text):
        b = clean_text(m.group(0))
        b = re.split(r'[.\n]', b)[0].strip()
        if b and 15 <= len(b) <= 70 and b not in benefits:
            benefits.append(b)
        if len(benefits) >= 5:
            break

    _PRICING_HINT_RE = re.compile(
        r"(?:call|contact|enquire|request)\s+(?:us\s+)?(?:for\s+)?(?:a\s+)?(?:quote|pricing|rates?)",
        re.I,
    )
    pricing_hints = []
    if _PRICING_HINT_RE.search(text):
        pricing_hints.append("Contact for pricing")
    if any(x in text_l for x in ["bespoke", "tailored pricing", "flexible pricing"]):
        pricing_hints.append("Flexible / bespoke pricing")

    return {
        "detected": True,
        "serviceType": service_type,
        "industry": industry,
        "serviceArea": service_areas,
        "services": services,
        "trustSignals": trust_signals,
        "benefits": benefits,
        "pricingHints": pricing_hints,
    }


# ── Issue 8: build_pricing_intelligence V5 — dynamic period from plan data ────
# V4 hardcoded "/seat/mo"; Cursor Teams uses "/user/mo".
# V5 is identical to V4 except: teamSeatPriceRange.period is read from plan's
# price.period field instead of hardcoded (fixes Cursor /user/mo vs Claude /seat/mo).
def build_pricing_intelligence(text, pricing_offers, pricing_summary, plan_features, comparison_matrix, api_pricing):
    """V5: teamSeatPriceRange.period derived from plan price.period (not hardcoded).

    Changes from V4:
    - Collects price.period strings from team plans alongside amounts
    - Uses first observed period ("/user/mo" for Cursor, "/seat/mo" for Claude)
      instead of always hardcoding "/seat/mo"
    """
    if pricing_offers is None:
        return {"detected": False}

    core_plans = (pricing_offers or {}).get("corePlans") or []
    standalone = (pricing_offers or {}).get("standaloneProducts") or []
    mapping_confidence = (pricing_offers or {}).get("planMappingConfidence", 0.5)
    has_custom = (pricing_offers or {}).get("hasCustomPricing", False)

    if not core_plans and not standalone and not (api_pricing and (api_pricing.get("modelRates") or api_pricing.get("usageRates"))):
        return {"detected": False}

    # ── Subscription plan price range ────────────────────────────────────────
    _sub_amounts = []
    _sub_currencies = []
    for p in core_plans:
        if not isinstance(p.get("price"), dict):
            continue
        pr = p["price"]
        if pr.get("amount") is None or pr.get("amount") == 0:
            continue
        if p.get("type") in ("enterprise_plan", "team_plan"):
            continue
        _plan_name_l = (p.get("name") or "").lower()
        if _plan_name_l in ("team", "teams", "enterprise", "enterprise+", "enterprise plus"):
            continue
        _sub_amounts.append(pr["amount"])
        if pr.get("currency"):
            _sub_currencies.append(pr["currency"])

    _subscription_price_range = None
    if _sub_amounts:
        _currency = _sub_currencies[0] if _sub_currencies else None
        _subscription_price_range = {
            "min": min(_sub_amounts),
            "max": max(_sub_amounts),
            "currency": _currency,
        }

    # ── Team seat price range ────────────────────────────────────────────────
    _team_amounts = []
    _team_currencies = []
    _team_periods = []   # V5: collect actual periods
    _has_team_plans = False
    for p in core_plans:
        if not isinstance(p.get("price"), dict):
            continue
        pr = p["price"]
        if pr.get("amount") is None:
            continue
        _is_team_type = p.get("type") == "team_plan"
        _is_team_name = (p.get("name") or "").lower() in ("team", "teams")
        _is_per_user = (pr.get("period") or "").lower() in ("/user/mo", "/user", "/seat/mo")
        if _is_team_type or (_is_team_name and _is_per_user):
            _has_team_plans = True
            _team_amounts.append(pr["amount"])
            if pr.get("currency"):
                _team_currencies.append(pr["currency"])
            if pr.get("period"):                         # V5: capture period
                _team_periods.append(pr["period"])
            # Include ALL billing seat prices (annual + monthly, standard + premium)
            billing = p.get("billing") or {}
            for _bkey in ("annualSeatPrice", "monthlySeatPrice",
                          "premiumAnnualSeatPrice", "premiumMonthlySeatPrice"):
                if billing.get(_bkey) is not None:
                    _team_amounts.append(billing[_bkey])

    _team_seat_range = None
    if _team_amounts:
        _team_currency = _team_currencies[0] if _team_currencies else None
        _detected_period = _team_periods[0] if _team_periods else "/seat/mo"  # V5
        _team_seat_range = {
            "min": min(_team_amounts),
            "max": max(_team_amounts),
            "currency": _team_currency,
            "period": _detected_period,                  # V5: was hardcoded "/seat/mo"
        }
    # If teams are represented in teamSeatPriceRange, note it on subscriptionRange
    if _has_team_plans and _subscription_price_range:
        _subscription_price_range.setdefault("notes", []).append(
            "Teams plan represented separately as teamSeatPriceRange"
        )

    # ── API model price range ─────────────────────────────────────────────────
    _api_model_range = None
    if api_pricing and api_pricing.get("modelRates"):
        _input_prices = [r.get("inputPerMTok") for r in api_pricing["modelRates"] if r.get("inputPerMTok") is not None]
        _output_prices = [r.get("outputPerMTok") for r in api_pricing["modelRates"] if r.get("outputPerMTok") is not None]
        if _input_prices or _output_prices:
            _all_prices = _input_prices + _output_prices
            _ir = {"min": min(_input_prices), "max": max(_input_prices)} if _input_prices else None
            _or = {"min": min(_output_prices), "max": max(_output_prices)} if _output_prices else None
            _api_model_range = {
                "lowestPerMTok": min(_all_prices),
                "highestPerMTok": max(_all_prices),
                "currency": "$",
                "inputRange": _ir,
                "outputRange": _or,
            }

    # ── Platform / usage price range ─────────────────────────────────────────
    _platform_usage_range = None
    if api_pricing:
        if api_pricing.get("usageRates"):
            _usage_amounts = [r.get("amount") for r in api_pricing["usageRates"] if r.get("amount") is not None]
            if _usage_amounts:
                _platform_usage_range = {
                    "min": min(_usage_amounts),
                    "max": max(_usage_amounts),
                    "currency": "$",
                    "rates": api_pricing["usageRates"],
                }
        elif isinstance(api_pricing.get("usagePricing"), dict):
            _up = api_pricing["usagePricing"]
            if _up.get("min") is not None or _up.get("max") is not None:
                _platform_usage_range = _up

    return {
        "detected": True,
        "corePlans": core_plans,
        "standaloneProducts": standalone,
        "pricingSummary": pricing_summary or {},
        "planFeatures": plan_features or {},
        "comparisonMatrix": comparison_matrix or {},
        "apiPricing": api_pricing or {},
        "planMappingConfidence": mapping_confidence,
        "hasFreeOption": any(
            isinstance(p.get("price"), dict) and p["price"].get("amount") == 0
            for p in core_plans + standalone
        ),
        "hasCustomPricing": has_custom or any(
            (p.get("price") or {}).get("type") == "custom_plus_usage"
            for p in core_plans
        ),
        "subscriptionPlanPriceRange": _subscription_price_range,
        "teamSeatPriceRange": _team_seat_range,
        "apiModelPriceRange": _api_model_range,
        "platformUsagePriceRange": _platform_usage_range,
        "notes": pricing_offers.get("notes", []),
    }


# ── Issues 5/6/7: extract_plan_features V15 — comprehensive noise filters ─────
# V14 base + extended _PRICE_DESC_RE + trailing-comma/particle/CTA-start/testimonial
# rejection + download suffix stripping.
def extract_plan_features(text, core_plans):
    """V15: Comprehensive noise filtering for plan feature snippets.

    New filters vs V14:
    - _PRICE_DESC_RE extended: /mo, /user/mo, $0 headers, tax/legal text
    - Trailing comma → reject (mid-list fragment: "Chat on web, iOS,")
    - Short trailing particle → reject (≤6 words ending preposition/particle)
    - CTA-start → reject (≤4 words, first word is a CTA verb)
    - Testimonial → reject ("Trusted every day by teams...")
    - download suffix stripped ("Limited Tab completions Download" → cleaned)
    """
    if not text or not core_plans:
        return {}

    section = get_main_pricing_section(text)
    names = [p.get("name") for p in core_plans if p.get("name")]
    blocks, _ = extract_named_blocks(section, names)
    _full_blocks, _ = extract_named_blocks(text[:8000], names)

    numeric_patterns = {
        "projects": r"(\d[\d,]*)\s+projects?",
        "trackedKeywords": r"(\d[\d,]*)\s+(?:tracked\s+)?keywords?(?:\s+to\s+track)?",
        "trackedPrompts": r"(\d[\d,]*)\s+(?:tracked\s+)?prompts?(?:\s+to\s+track)?",
        "crawlCredits": r"(\d[\d,]*)\s+crawl credits",
        "usersIncluded": r"(\d[\d,]*)\s+users? included|included users\s+(\d[\d,]*)",
        "websitesToMonitor": r"(?:up to\s+)?(\d[\d,]*)\s+websites? to monitor",
        "storage": r"(\d[\d,]*(?:\.\d+)?)\s*(gb|tb)\s+of cloud storage|storage\s+(\d[\d,]*(?:\.\d+)?)\s*(gb|tb)",
        "brandKits": r"(\d[\d,]*)\s+brand kits?",
        "templates": r"(\d[\d,.]*\s*[mk]\+?)\s+templates",
    }

    _REPEATED_CTA_RE = re.compile(
        r"(?:Try\s+\S+|Get\s+Started|Contact\s+Sales|Learn\s+More|Try\s+Free|Sign\s+Up)"
        r"(?:\s+(?:Try\s+\S+|Get\s+Started|Contact\s+Sales|Learn\s+More|Try\s+Free|Sign\s+Up))+",
        re.I,
    )

    # V15 extended: /mo, /user/mo, $0 plan-headers, legal/tax text
    _PRICE_DESC_RE = re.compile(
        r"\$\s*\d+.*(?:per\s+month|if\s+billed|billed\s+up\s+front|per\s+seat|per\s+year"
        r"|\/\s*mo\b|\/\s*user\s*\/\s*mo\b)"
        r"|\$\s*0\s+(?:free|for\s+everyone)"
        r"|\bprices\s+shown\b"
        r"|\bapplicable\s+tax\b",
        re.I,
    )
    _ORPHAN_PLUS_RE = re.compile(r"^[\w\s,\.]+,\s*plus:\s*(.+)", re.I)

    _PLAN_NAMES_SET = "|".join([
        "Free", "Pro", "Max", "Team", "Teams", "Enterprise", "Business",
        "Individual", "Hobby", "Starter", "Plus", "Ultra", "Basic", "Standard", "Premium",
    ])
    _INLINE_SPLIT_RE = re.compile(
        r"(?<=[a-z*,])\s{1,3}(?=[A-Z][a-z]{2,})"
        r"(?!" + _PLAN_NAMES_SET + r"\b)",
    )

    # V15 new filters
    _TRAILING_PARTICLE_RE = re.compile(
        r"\b(?:more|with|for|on|in|and|or|to|from|the|a|an|of|at|by|up|out)\s*$",
        re.I,
    )
    _CTA_FIRST_WORDS_V15 = {"get", "buy", "start", "sign", "try", "contact", "book", "schedule", "request"}
    _TESTIMONIAL_RE = re.compile(
        r"trusted\s+every\s+day|world.class\s+software|build\s+world.class|"
        r"join\s+\d+[,\d]*\s*(?:developers|teams|companies|users)",
        re.I,
    )

    stop_tokens = {
        "get started", "try for free", "start a free trial", "contact sales",
        "book a demo", "try claude", "try free", "try it free", "learn more",
        "get pro", "get team", "get teams", "get enterprise",
    }

    output = {}
    for plan in core_plans:
        name = plan.get("name")
        data = blocks.get((name or "").lower())
        if not data or len((data.get("text") or "")) < 100:
            data = _full_blocks.get((name or "").lower())
        if not data:
            continue
        block = data["text"]
        found = {}

        for key, pattern in numeric_patterns.items():
            pm = re.search(pattern, block, flags=re.I)
            if pm:
                groups = [g for g in pm.groups() if g]
                if groups:
                    value = groups[0]
                    if key == "storage" and len(groups) >= 2:
                        found[key] = f"{groups[0]} {groups[1].upper()}"
                    else:
                        try:
                            found[key] = int(value.replace(",", ""))
                        except Exception:
                            found[key] = value

        block_clean = _REPEATED_CTA_RE.sub(" ", block).strip()
        raw_sentences = re.split(r"(?:\u2713|\u2022|\u2013|\n|\. )", block_clean)
        extended = []
        for s in raw_sentences:
            s = s.strip()
            if not s:
                continue
            if len(s) > 80:
                sub = _INLINE_SPLIT_RE.split(s)
                extended.extend(sub)
            else:
                extended.append(s)

        snippets = []
        for s in extended:
            s = clean_text(s)
            if not s:
                continue
            _op = _ORPHAN_PLUS_RE.match(s)
            if _op:
                s = _op.group(1).strip()
                if not s:
                    continue
            s_l = s.lower()
            if len(s) < 10 or len(s) > 130:
                continue
            if len(s.split()) < 3:
                continue
            if s_l == (name or "").lower():
                continue
            if s_l in stop_tokens:
                continue
            if any(tok in s_l for tok in {"get started", "contact sales", "try for free", "book a demo"}):
                continue
            if _PRICE_DESC_RE.search(s):
                continue
            if s.rstrip().endswith(","):
                continue
            words = s.split()
            if len(words) <= 6 and _TRAILING_PARTICLE_RE.search(s):
                continue
            if len(words) <= 4 and words[0].lower() in _CTA_FIRST_WORDS_V15:
                continue
            if _TESTIMONIAL_RE.search(s):
                continue
            snippets.append(s)
            if len(snippets) >= 14:
                break

        snippets = _clean_feature_snippets(snippets, name)[:8]
        if snippets:
            found["featureSnippets"] = snippets
        if found:
            output[name] = found

    return output


# ── Restored: hosting soup CTA helpers ──
_HOSTING_SOUP_CTA_FIRST_WORDS = {
    "explore", "view", "start", "get", "order", "buy", "sign", "try",
    "see", "compare", "check", "migrate", "transfer", "upgrade", "talk",
    "chat", "schedule", "request", "access", "create", "find",
}
_HOSTING_SOUP_CTA_REJECT_EXACT = {
    "my account", "login", "log in", "register", "sign in", "about us",
    "our team", "why us", "billing area", "open a ticket", "knowledgebase",
    "network status", "faq", "faqs", "payment method", "careers",
    "blog", "affiliate", "refund policy", "terms", "privacy", "contact us",
    "domain search", "whois lookup",
}
_HOSTING_SOUP_CTA_REJECT_URL_PARTS = {
    "/blog/", "/about", "/team", "/careers", "/legal", "/terms",
    "/privacy", "/affiliat", "/faq", "/knowledgebase",
}


def _extract_hosting_soup_ctas(soup, url):
    """Extract hosting CTAs directly from soup <a> tags."""
    if not soup:
        return []
    ctas = []
    seen = set()
    for a in soup.find_all("a", href=True):
        text = clean_text(a.get_text(" ", strip=True))
        if not text or len(text) > 85 or len(text) < 5:
            continue
        text_l = text.lower()
        first_word = text_l.split()[0] if text_l.split() else ""
        if first_word not in _HOSTING_SOUP_CTA_FIRST_WORDS:
            continue
        if text_l in _HOSTING_SOUP_CTA_REJECT_EXACT:
            continue
        if text_l in seen:
            continue
        href = a.get("href", "")
        href_l = href.lower()
        if any(part in href_l for part in _HOSTING_SOUP_CTA_REJECT_URL_PARTS):
            continue
        if href.startswith("#") or href.startswith("javascript:"):
            continue
        seen.add(text_l)
        full_href = urljoin(url, href).split("#")[0]
        ctas.append({"text": text, "url": full_href, "source": "hosting_soup"})
    return ctas[:12]


# ── Restored: pricing plan CTA helpers ──
_PRICING_PLAN_CTA_FIRST_WORDS = {
    "get", "chat", "explore", "upgrade", "start", "try", "sign",
    "contact", "download",
}
_PRICING_PLAN_CTA_REJECT_EXACT = {
    "get it on google play", "get it on the app store", "get in touch",
    "get support", "sign in", "log in", "login",
}
_PRICING_PLAN_CTA_REJECT_URL_PARTS = {
    "/blog", "/docs", "/help", "/support", "/about", "/careers",
    "/forum", "/changelog",
}


def _extract_pricing_plan_ctas(soup, url):
    """Extract pricing-card CTAs not caught by extract_ctas()."""

# =============================================================================
# SESSION 5: V4 _extract_service_intelligence
# Root cause: V3 used a broad prefix regex that matched meta description text
# ("Professional SIA-licensed door security supervisors in Birmingham").
# V4 uses targeted per-phrase patterns and skips the first 300 chars (meta region).
# Also fixes trust signal labels and adds "Professional conflict management".
# =============================================================================

def _extract_service_intelligence(text, url):
    """V4: Targeted benefit patterns; skip meta-description region; cleaner trust labels."""
    text = text or ""
    text_l = text.lower()
    url_l = (url or "").lower()

    _TYPE_MAP = [
        (["door supervisor", "door security supervisor", "door security supervisors",
          "sia-licensed door"], "door_security_supervisors", "security_services"),
        (["cctv", "cctv monitoring", "cctv surveillance"], "cctv_monitoring", "security_services"),
        (["event security", "event steward"], "event_security", "security_services"),
        (["manned guard", "security guard", "guard service"], "manned_guarding", "security_services"),
        (["web hosting", "hosting plan", "shared hosting", "vps hosting",
          "cloud hosting", "dedicated server"], "web_hosting", "hosting"),
        (["seo service", "search engine optimisation", "search engine optimization",
          "link building", "keyword ranking"], "seo_services", "digital_marketing"),
        (["plumbing", "plumber"], "plumbing", "home_services"),
        (["electrician", "electrical service"], "electrical", "home_services"),
        (["security service", "security solution", "professional security"], "security_services", "security"),
    ]
    service_type = None
    industry = None
    for kws, stype, ind in _TYPE_MAP:
        if any(kw in text_l for kw in kws) or any(kw in url_l for kw in kws):
            service_type = stype
            industry = ind
            break
    if not service_type:
        return {"detected": False}

    _LOCATION_RE = re.compile(
        r"\b(?:in|across|throughout|serving|covering|based in|based at)\s+"
        r"([A-Z][a-zA-Z\s\-]{2,30}?)(?=[,\.!\s]|$)",
    )
    _CITY_PATTERN_RE = re.compile(
        r"\b(London|Birmingham|Manchester|Leeds|Liverpool|Sheffield|Bristol|"
        r"Edinburgh|Glasgow|Cardiff|Belfast|Newcastle|Nottingham|Leicester|"
        r"Southampton|Portsmouth|Bradford|Coventry|Reading|Derby|Brighton)\b"
    )
    service_areas = []
    seen_areas = set()
    for m in _LOCATION_RE.finditer(text):
        loc = m.group(1).strip().title()
        if loc.lower() not in seen_areas and len(loc) > 2:
            service_areas.append(loc)
            seen_areas.add(loc.lower())
    for m in _CITY_PATTERN_RE.finditer(text):
        loc = m.group(1).strip()
        if loc.lower() not in seen_areas:
            service_areas.append(loc)
            seen_areas.add(loc.lower())
    if not service_areas:
        service_areas = ["Not specified"]

    _SERVICE_KEYWORDS = {
        "door security supervisor": "Door security supervisors",
        "door security supervisors": "Door security supervisors",
        "office security": "Office security",
        "entry management": "Entry management",
        "crowd control": "Crowd control",
        "conflict resolution": "Conflict resolution",
        "conflict management": "Conflict management",
        "id check": "ID checking",
        "identification": "Identification verification",
        "queue management": "Queue management",
        "access control": "Access control",
        "cctv": "CCTV monitoring",
        "patrol": "Security patrol",
        "event security": "Event security",
        "manned guard": "Manned guarding",
        "venue security": "Venue security",
        "retail security": "Retail security",
        "security officer": "Security officers",
    }
    services = []
    seen_services = set()
    for kw, label in _SERVICE_KEYWORDS.items():
        if kw in text_l and label.lower() not in seen_services:
            services.append(label)
            seen_services.add(label.lower())

    trust_signals = []
    if any(x in text_l for x in ["sia", "sia-licensed", "sia licensed"]):
        trust_signals.append("SIA-licensed professionals")
    if "24/7" in text_l or "24 7" in text_l or "24-hour" in text_l:
        trust_signals.append("24/7 operations support")
    if any(x in text_l for x in ["rapid deployment", "rapid response"]):
        trust_signals.append("Rapid deployment within 24-48 hours")
    if any(x in text_l for x in ["fully trained", "full trained"]):
        trust_signals.append("Fully trained security personnel")
    elif any(x in text_l for x in ["trained", "professional training"]):
        trust_signals.append("Professionally trained staff")
    if any(x in text_l for x in ["fully insured", "insured and bonded"]):
        trust_signals.append("Fully insured and bonded")
    if any(x in text_l for x in ["dbs check", "crb check", "background check"]):
        trust_signals.append("DBS-checked personnel")
    if any(x in text_l for x in ["conflict management", "conflict resolution"]):
        trust_signals.append("Professional conflict management")
    if any(x in text_l for x in ["customer service", "customer-focused", "customer focused"]):
        trust_signals.append("Customer-focused approach")

    # V4: Targeted per-phrase patterns that won't match meta description text.
    # Skip the first 300 chars (meta description / page title region) to avoid
    # matching "Professional SIA-licensed door security supervisors in Birmingham".
    body_text = text[300:] if len(text) > 300 else text

    # City names used to reject benefits that are actually title/meta fragments
    _CITY_RE = re.compile(
        r"\b(London|Birmingham|Manchester|Leeds|Liverpool|Sheffield|Bristol|"
        r"Edinburgh|Glasgow|Cardiff|Belfast|Newcastle|Nottingham|Leicester|"
        r"Southampton|Portsmouth|Bradford|Coventry|Reading|Derby|Brighton)\b",
        re.I,
    )

    _BENEFIT_PATTERNS = [
        re.compile(r"tailored\s+(?:venue\s+)?(?:security|solutions?|approach|service)s?(?:\s+\w+){0,3}", re.I),
        re.compile(r"customer.focused\s+\w+(?:\s+\w+){0,3}", re.I),
        re.compile(r"flexible\s+(?:staffing|scheduling|deployment|option|solution)s?(?:\s+\w+){0,2}", re.I),
        re.compile(r"safe\s+(?:yet\s+)?(?:welcoming|secure)\s+\w+(?:\s+\w+){0,2}", re.I),
        re.compile(r"rapid\s+(?:deployment|response)(?:\s+available)?", re.I),
        re.compile(r"professional\s+conflict\s+management", re.I),
        re.compile(r"bespoke\s+\w+(?:\s+\w+){0,3}", re.I),
        re.compile(r"fully\s+trained\s+\w+(?:\s+\w+){0,2}", re.I),
        re.compile(r"discreet\s+\w+(?:\s+\w+){0,3}", re.I),
        re.compile(r"welcoming\s+(?:venue|environment|atmosphere)(?:\s+\w+)?", re.I),
        re.compile(r"prevent(?:ing)?\s+(?:anti.social|crime|disorder|conflict)\s*\w*", re.I),
        re.compile(r"proactive\s+\w+(?:\s+\w+){0,3}", re.I),
    ]

    benefits = []
    seen_benefits = set()
    for pat in _BENEFIT_PATTERNS:
        m = pat.search(body_text)
        if m:
            b = clean_text(m.group(0))
            # Trim at first comma, semicolon, or "and \d" (e.g. "and 24/7")
            b = re.split(r'[,;\n]|(?:\s+and\s+\d)', b)[0].strip()
            b_l = b.lower()
            if b and 12 <= len(b) <= 75 and b_l not in seen_benefits and not _CITY_RE.search(b):
                benefits.append(b[0].upper() + b[1:] if b else b)
                seen_benefits.add(b_l)
        if len(benefits) >= 6:
            break

    _PRICING_HINT_RE = re.compile(
        r"(?:call|contact|enquire|request)\s+(?:us\s+)?(?:for\s+)?(?:a\s+)?(?:quote|pricing|rates?)",
        re.I,
    )
    pricing_hints = []
    if _PRICING_HINT_RE.search(text):
        pricing_hints.append("Contact for pricing")
    if any(x in text_l for x in ["bespoke", "tailored pricing", "flexible pricing"]):
        pricing_hints.append("Flexible / bespoke pricing")

    return {
        "detected": True,
        "serviceType": service_type,
        "industry": industry,
        "serviceArea": service_areas,
        "services": services,
        "trustSignals": trust_signals,
        "benefits": benefits,
        "pricingHints": pricing_hints,
    }


# =============================================================================
# SESSION 5: V16 extract_plan_features
# Root cause fixes vs V15:
#  1. Pre-join comma-continued lines before newline split → "Chat on web, iOS,\n
#     Android, and desktop" becomes one snippet instead of a broken fragment.
#  2. Strong trailing-particle rejection for ALL lengths (not just <=6 words) →
#     catches "…Enterprise deployment for the".
#  3. Max 13-word ceiling → kills multi-feature blobs.
#  4. _PRICE_DESC_RE extended: /seat, /user, pricing metadata patterns.
#  5. Additional stop_tokens: "usage limits apply", "usage cost scales".
#  6. CTA-start + plan-name combo rejection → "Get Team plan Standard seat".
#  7. Ends-with-plan-name rejection → "Mix and match seat types Enterprise".
#  8. Legal / disclaimer text rejection.
#  9. Team-size metadata rejection → "For teams of 5 to 150".
# =============================================================================

def extract_plan_features(text, core_plans):
    """V16: Pre-join comma lines + strong trailing particle + max-word ceiling + extended noise filters."""
    if not text or not core_plans:
        return {}

    section = get_main_pricing_section(text)
    names = [p.get("name") for p in core_plans if p.get("name")]
    blocks, _ = extract_named_blocks(section, names)
    _full_blocks, _ = extract_named_blocks(text[:8000], names)

    numeric_patterns = {
        "projects": r"(\d[\d,]*)\s+projects?",
        "trackedKeywords": r"(\d[\d,]*)\s+(?:tracked\s+)?keywords?(?:\s+to\s+track)?",
        "trackedPrompts": r"(\d[\d,]*)\s+(?:tracked\s+)?prompts?(?:\s+to\s+track)?",
        "crawlCredits": r"(\d[\d,]*)\s+crawl credits",
        "usersIncluded": r"(\d[\d,]*)\s+users? included|included users\s+(\d[\d,]*)",
        "websitesToMonitor": r"(?:up to\s+)?(\d[\d,]*)\s+websites? to monitor",
        "storage": r"(\d[\d,]*(?:\.\d+)?)\s*(gb|tb)\s+of cloud storage|storage\s+(\d[\d,]*(?:\.\d+)?)\s*(gb|tb)",
        "brandKits": r"(\d[\d,]*)\s+brand kits?",
        "templates": r"(\d[\d,.]*\s*[mk]\+?)\s+templates",
    }

    _REPEATED_CTA_RE = re.compile(
        r"(?:Try\s+\S+|Get\s+Started|Contact\s+Sales|Learn\s+More|Try\s+Free|Sign\s+Up)"
        r"(?:\s+(?:Try\s+\S+|Get\s+Started|Contact\s+Sales|Learn\s+More|Try\s+Free|Sign\s+Up))+",
        re.I,
    )

    # V16 extended price/metadata reject patterns
    _PRICE_DESC_RE = re.compile(
        r"\$\s*\d+.*(?:per\s+month|if\s+billed|billed\s+up\s+front|per\s+seat|per\s+year"
        r"|\/\s*mo\b|\/\s*user\s*\/\s*mo\b|\/\s*seat\b)"
        r"|\$\s*0\s+(?:free|for\s+everyone)"
        r"|\bprices\s+shown\b"
        r"|\bapplicable\s+tax\b"
        r"|\bsubject\s+to\s+change\b"    # V16: legal disclaimer
        r"|\bterms\s+of\s+service\b"
        r"|\bfor\s+teams?\s+of\s+\d"     # V16: team-size metadata
        r"|\busage\s+cost\s+scales\b"    # V16: pricing metadata
        r"|\bseat\s+price\b",            # V16: seat pricing noise
        re.I,
    )
    _ORPHAN_PLUS_RE = re.compile(r"^[\w\s,\.]+,\s*plus:\s*(.+)", re.I)

    _PLAN_NAMES_SET = "|".join([
        "Free", "Pro", "Max", "Team", "Teams", "Enterprise", "Business",
        "Individual", "Hobby", "Starter", "Plus", "Ultra", "Basic", "Standard", "Premium",
    ])
    _INLINE_SPLIT_RE = re.compile(
        r"(?<=[a-z*,])\s{1,3}(?=[A-Z][a-z]{2,})"
        r"(?!" + _PLAN_NAMES_SET + r"\b)",
    )

    # V15 filters (retained)
    _TRAILING_PARTICLE_RE = re.compile(
        r"\b(?:more|with|for|on|in|and|or|to|from|the|a|an|of|at|by|up|out)\s*$",
        re.I,
    )
    # V16: strong trailing-particle rejection regardless of word count
    _STRONG_TRAIL_RE = re.compile(
        r"\b(?:for|the|in|of|and|or|to|from|a|an|deployment|the)\s*$",
        re.I,
    )
    _CTA_FIRST_WORDS_V15 = {"get", "buy", "start", "sign", "try", "contact", "book", "schedule", "request"}
    _TESTIMONIAL_RE = re.compile(
        r"trusted\s+every\s+day|world.class\s+software|build\s+world.class|"
        r"join\s+\d+[,\d]*\s*(?:developers|teams|companies|users)",
        re.I,
    )

    # V16: plan name words for end-of-snippet and CTA+plan-name detection
    _PLAN_NAME_WORDS_V16 = {
        "free", "pro", "max", "team", "teams", "enterprise", "business",
        "individual", "hobby", "starter", "plus", "ultra", "basic", "standard", "premium",
    }

    stop_tokens = {
        "get started", "try for free", "start a free trial", "contact sales",
        "book a demo", "try claude", "try free", "try it free", "learn more",
        "get pro", "get team", "get teams", "get enterprise",
        # V16 additions
        "usage limits apply",
        "usage cost scales with model and task",
    }

    output = {}
    for plan in core_plans:
        name = plan.get("name")
        data = blocks.get((name or "").lower())
        if not data or len((data.get("text") or "")) < 100:
            data = _full_blocks.get((name or "").lower())
        if not data:
            continue
        block = data["text"]
        found = {}

        for key, pattern in numeric_patterns.items():
            pm = re.search(pattern, block, flags=re.I)
            if pm:
                groups = [g for g in pm.groups() if g]
                if groups:
                    value = groups[0]
                    if key == "storage" and len(groups) >= 2:
                        found[key] = f"{groups[0]} {groups[1].upper()}"
                    else:
                        try:
                            found[key] = int(value.replace(",", ""))
                        except Exception:
                            found[key] = value

        block_clean = _REPEATED_CTA_RE.sub(" ", block).strip()

        # V16: Pre-join comma-continued lines before splitting on newline.
        # "Chat on web, iOS,\nAndroid, and desktop" → "Chat on web, iOS, Android, and desktop"
        # This prevents the continuation fragment from becoming a broken snippet.
        block_clean = re.sub(r',\s*\n\s*', ', ', block_clean)

        raw_sentences = re.split(r"(?:✓|•|–|\n|\. )", block_clean)
        extended = []
        for s in raw_sentences:
            s = s.strip()
            if not s:
                continue
            if len(s) > 80:
                sub = _INLINE_SPLIT_RE.split(s)
                extended.extend(sub)
            else:
                extended.append(s)

        snippets = []
        for s in extended:
            s = clean_text(s)
            if not s:
                continue
            _op = _ORPHAN_PLUS_RE.match(s)
            if _op:
                s = _op.group(1).strip()
                if not s:
                    continue
            s_l = s.lower()
            if len(s) < 10 or len(s) > 130:
                continue
            if len(s.split()) < 3:
                continue
            if s_l == (name or "").lower():
                continue
            if s_l in stop_tokens:
                continue
            if any(tok in s_l for tok in {"get started", "contact sales", "try for free", "book a demo"}):
                continue
            if _PRICE_DESC_RE.search(s):
                continue
            if s.rstrip().endswith(","):
                continue
            words = s.split()
            # V16: max word ceiling — blocks multi-feature blobs
            if len(words) > 13:
                continue
            # V15: short trailing particle
            if len(words) <= 6 and _TRAILING_PARTICLE_RE.search(s):
                continue
            # V16: strong trailing particle at any length
            if _STRONG_TRAIL_RE.search(s):
                continue
            # V15: CTA-start (≤4 words)
            if len(words) <= 4 and words[0].lower() in _CTA_FIRST_WORDS_V15:
                continue
            # V16: CTA-start + plan name anywhere → UI noise ("Get Team plan Standard seat")
            if words[0].lower() in _CTA_FIRST_WORDS_V15 and any(
                w.lower().rstrip("+") in _PLAN_NAME_WORDS_V16 for w in words[1:]
            ):
                continue
            # V16: ends with a plan name → truncated UI blob ("Mix and match seat types Enterprise")
            if words[-1].lower().rstrip("+") in _PLAN_NAME_WORDS_V16:
                continue
            if _TESTIMONIAL_RE.search(s):
                continue
            snippets.append(s)
            if len(snippets) >= 14:
                break

        snippets = _clean_feature_snippets(snippets, name)[:8]  # V16 truncated stub
        if snippets:
            found["featureSnippets"] = snippets
        if found:
            output[name] = found

    return output

# =============================================================================
# SESSION 6: _post_clean_ctas V3
# Issue 1 root cause: URL dedup (url.split("?")[0]) collapses multiple Claude
# plan CTAs that share the same base URL (e.g. claude.ai/login with different
# query strings). Only text-based dedup is needed — two different CTA texts
# pointing to the same signup funnel URL should both be kept.
# =============================================================================

def _post_clean_ctas(ctas):
    """V3: Text-only dedup. URL dedup removed — it collapses multi-plan pricing CTAs."""
    cleaned = []
    seen_text = set()
    for c in ctas:
        text = (c.get("text") or "").strip()
        url = (c.get("url") or "").strip()
        text_l = text.lower()
        if not text_l:
            continue
        if text_l in _CTA_POST_REJECT_EXACT:
            continue
        if _CTA_DOUBLED_WORD_RE.search(text):
            continue
        _url_l = url.lower()
        if any(x in _url_l for x in ["source=pricing_faq", "source=navbar_contact", "/forum", "/workshops"]):
            continue
        if text_l in seen_text:
            continue
        seen_text.add(text_l)
        cleaned.append(c)
    return cleaned


# =============================================================================
# SESSION 6: V5 _extract_service_intelligence
# Issue 4 root cause: V4 benefit patterns too greedy — customer-focused matches
# "Customer-focused conflict management Our team" (4 words allowed) and safe
# matches "Safe yet welcoming environment for your". Fix: after matching, trim
# at capital-word boundary (signals new sentence) AND at possessive fragments.
# =============================================================================

def _extract_service_intelligence(text, url):
    """V5: Trim benefits at capital-word boundary and possessive fragments."""
    text = text or ""
    text_l = text.lower()
    url_l = (url or "").lower()

    _TYPE_MAP = [
        (["door supervisor", "door security supervisor", "door security supervisors",
          "sia-licensed door"], "door_security_supervisors", "security_services"),
        (["cctv", "cctv monitoring", "cctv surveillance"], "cctv_monitoring", "security_services"),
        (["event security", "event steward"], "event_security", "security_services"),
        (["manned guard", "security guard", "guard service"], "manned_guarding", "security_services"),
        (["web hosting", "hosting plan", "shared hosting", "vps hosting",
          "cloud hosting", "dedicated server"], "web_hosting", "hosting"),
        (["seo service", "search engine optimisation", "search engine optimization",
          "link building", "keyword ranking"], "seo_services", "digital_marketing"),
        (["plumbing", "plumber"], "plumbing", "home_services"),
        (["electrician", "electrical service"], "electrical", "home_services"),
        (["security service", "security solution", "professional security"], "security_services", "security"),
    ]
    service_type = None
    industry = None
    for kws, stype, ind in _TYPE_MAP:
        if any(kw in text_l for kw in kws) or any(kw in url_l for kw in kws):
            service_type = stype
            industry = ind
            break
    if not service_type:
        return {"detected": False}

    _LOCATION_RE = re.compile(
        r"\b(?:in|across|throughout|serving|covering|based in|based at)\s+"
        r"([A-Z][a-zA-Z\s\-]{2,30}?)(?=[,\.!\s]|$)",
    )
    _CITY_PATTERN_RE = re.compile(
        r"\b(London|Birmingham|Manchester|Leeds|Liverpool|Sheffield|Bristol|"
        r"Edinburgh|Glasgow|Cardiff|Belfast|Newcastle|Nottingham|Leicester|"
        r"Southampton|Portsmouth|Bradford|Coventry|Reading|Derby|Brighton)\b"
    )
    service_areas = []
    seen_areas = set()
    for m in _LOCATION_RE.finditer(text):
        loc = m.group(1).strip().title()
        if loc.lower() not in seen_areas and len(loc) > 2:
            service_areas.append(loc)
            seen_areas.add(loc.lower())
    for m in _CITY_PATTERN_RE.finditer(text):
        loc = m.group(1).strip()
        if loc.lower() not in seen_areas:
            service_areas.append(loc)
            seen_areas.add(loc.lower())
    if not service_areas:
        service_areas = ["Not specified"]

    _SERVICE_KEYWORDS = {
        "door security supervisor": "Door security supervisors",
        "door security supervisors": "Door security supervisors",
        "office security": "Office security",
        "entry management": "Entry management",
        "crowd control": "Crowd control",
        "conflict resolution": "Conflict resolution",
        "conflict management": "Conflict management",
        "id check": "ID checking",
        "identification": "Identification verification",
        "queue management": "Queue management",
        "access control": "Access control",
        "cctv": "CCTV monitoring",
        "patrol": "Security patrol",
        "event security": "Event security",
        "manned guard": "Manned guarding",
        "venue security": "Venue security",
        "retail security": "Retail security",
        "security officer": "Security officers",
    }
    services = []
    seen_services = set()
    for kw, label in _SERVICE_KEYWORDS.items():
        if kw in text_l and label.lower() not in seen_services:
            services.append(label)
            seen_services.add(label.lower())

    trust_signals = []
    if any(x in text_l for x in ["sia", "sia-licensed", "sia licensed"]):
        trust_signals.append("SIA-licensed professionals")
    if "24/7" in text_l or "24 7" in text_l or "24-hour" in text_l:
        trust_signals.append("24/7 operations support")
    if any(x in text_l for x in ["rapid deployment", "rapid response"]):
        trust_signals.append("Rapid deployment within 24-48 hours")
    if any(x in text_l for x in ["fully trained", "full trained"]):
        trust_signals.append("Fully trained security personnel")
    elif any(x in text_l for x in ["trained", "professional training"]):
        trust_signals.append("Professionally trained staff")
    if any(x in text_l for x in ["fully insured", "insured and bonded"]):
        trust_signals.append("Fully insured and bonded")
    if any(x in text_l for x in ["dbs check", "crb check", "background check"]):
        trust_signals.append("DBS-checked personnel")
    if any(x in text_l for x in ["conflict management", "conflict resolution"]):
        trust_signals.append("Professional conflict management")
    if any(x in text_l for x in ["customer service", "customer-focused", "customer focused"]):
        trust_signals.append("Customer-focused approach")

    # V5: Skip first 300 chars (meta/title region), then use targeted patterns.
    # After each match, trim at:
    #   1. First comma, semicolon, or period
    #   2. Possessive fragments ("for your", "of your", "in your")
    #   3. Capital-word boundary (signals start of new sentence/section)
    body_text = text[300:] if len(text) > 300 else text

    _CITY_RE = re.compile(
        r"\b(London|Birmingham|Manchester|Leeds|Liverpool|Sheffield|Bristol|"
        r"Edinburgh|Glasgow|Cardiff|Belfast|Newcastle|Nottingham|Leicester|"
        r"Southampton|Portsmouth|Bradford|Coventry|Reading|Derby|Brighton)\b",
        re.I,
    )
    # Regex to trim at possessive/continuation fragments
    _TRIM_RE = re.compile(
        r'[,;\.\n]'
        r'|\s+(?:for\s+your|of\s+your|in\s+your|to\s+your|with\s+your|our\s+\w+|their\s+\w+)\b'
        r'|\s+(?=[A-Z][a-z])',  # capital-word boundary = new sentence
    )

    _BENEFIT_PATTERNS = [
        re.compile(r"tailored\s+(?:venue\s+)?(?:security|solutions?|approach|service)s?(?:\s+\w+){0,2}", re.I),
        re.compile(r"customer.focused\s+\w+(?:\s+\w+){0,2}", re.I),
        re.compile(r"flexible\s+(?:staffing|scheduling|deployment|option|solution)s?(?:\s+\w+){0,1}", re.I),
        re.compile(r"safe\s+(?:yet\s+)?(?:welcoming|secure)\s+(?:venue\s+)?\w+(?:\s+\w+){0,2}", re.I),
        re.compile(r"rapid\s+(?:deployment|response)(?:\s+available)?", re.I),
        re.compile(r"professional\s+conflict\s+management", re.I),
        re.compile(r"bespoke\s+\w+(?:\s+\w+){0,2}", re.I),
        re.compile(r"fully\s+trained\s+\w+(?:\s+\w+){0,1}", re.I),
        re.compile(r"discreet\s+\w+(?:\s+\w+){0,2}", re.I),
        re.compile(r"welcoming\s+(?:venue|environment|atmosphere)(?:\s+\w+)?", re.I),
        re.compile(r"prevent(?:ing)?\s+(?:anti.social|crime|disorder|conflict)\s*\w*", re.I),
        re.compile(r"proactive\s+\w+(?:\s+\w+){0,2}", re.I),
    ]

    benefits = []
    seen_benefits = set()
    for pat in _BENEFIT_PATTERNS:
        m = pat.search(body_text)
        if m:
            b = clean_text(m.group(0))
            # V5: trim at first comma/period/possessive/capital-word
            trim_m = _TRIM_RE.search(b)
            if trim_m:
                b = b[:trim_m.start()].strip()
            b_l = b.lower()
            if b and 12 <= len(b) <= 75 and b_l not in seen_benefits and not _CITY_RE.search(b):
                benefits.append(b[0].upper() + b[1:] if b else b)
                seen_benefits.add(b_l)
        if len(benefits) >= 6:
            break

    _PRICING_HINT_RE = re.compile(
        r"(?:call|contact|enquire|request)\s+(?:us\s+)?(?:for\s+)?(?:a\s+)?(?:quote|pricing|rates?)",
        re.I,
    )
    pricing_hints = []
    if _PRICING_HINT_RE.search(text):
        pricing_hints.append("Contact for pricing")
    if any(x in text_l for x in ["bespoke", "tailored pricing", "flexible pricing"]):
        pricing_hints.append("Flexible / bespoke pricing")

    return {
        "detected": True,
        "serviceType": service_type,
        "industry": industry,
        "serviceArea": service_areas,
        "services": services,
        "trustSignals": trust_signals,
        "benefits": benefits,
        "pricingHints": pricing_hints,
    }


# =============================================================================
# SESSION 6: V17 extract_plan_features
# Issues 2+3 fixes vs V16:
#  1. Char minimum 10→4; word-floor (< 3) REMOVED — allows "SSO", "SCIM",
#     "Admin controls", "Enterprise search", "Audit logs", "Research", etc.
#  2. Pre-split ") [A-Z]" → ")\n[A-Z]": splits "Management (SCIM) Audit logs"
#  3. Pre-split " No [lower]" → "\nNo [lower]": splits "Claude desktop app No
#     model training on your content by default"
#  4. Inline split threshold 80→50 chars: catches shorter fused snippets
#  5. _STRONG_TRAIL_RE extended with "advanced" → rejects "Early access to
#     advanced" (dangling adjective fragment)
#  6. stop_tokens: add "for large businesses operating at scale"
#  7. Reject "Claude with ..." redundant prefix patterns
#  8. Reject "to organize / to help / to enable" purpose-clause descriptions
# =============================================================================

def extract_plan_features(text, core_plans):
    """V17: Lower snippet floors, pre-split fused features, extended trail/stop filters."""
    if not text or not core_plans:
        return {}

    section = get_main_pricing_section(text)
    names = [p.get("name") for p in core_plans if p.get("name")]
    blocks, _ = extract_named_blocks(section, names)
    _full_blocks, _ = extract_named_blocks(text[:8000], names)

    numeric_patterns = {
        "projects": r"(\d[\d,]*)\s+projects?",
        "trackedKeywords": r"(\d[\d,]*)\s+(?:tracked\s+)?keywords?(?:\s+to\s+track)?",
        "trackedPrompts": r"(\d[\d,]*)\s+(?:tracked\s+)?prompts?(?:\s+to\s+track)?",
        "crawlCredits": r"(\d[\d,]*)\s+crawl credits",
        "usersIncluded": r"(\d[\d,]*)\s+users? included|included users\s+(\d[\d,]*)",
        "websitesToMonitor": r"(?:up to\s+)?(\d[\d,]*)\s+websites? to monitor",
        "storage": r"(\d[\d,]*(?:\.\d+)?)\s*(gb|tb)\s+of cloud storage|storage\s+(\d[\d,]*(?:\.\d+)?)\s*(gb|tb)",
        "brandKits": r"(\d[\d,]*)\s+brand kits?",
        "templates": r"(\d[\d,.]*\s*[mk]\+?)\s+templates",
    }

    _REPEATED_CTA_RE = re.compile(
        r"(?:Try\s+\S+|Get\s+Started|Contact\s+Sales|Learn\s+More|Try\s+Free|Sign\s+Up)"
        r"(?:\s+(?:Try\s+\S+|Get\s+Started|Contact\s+Sales|Learn\s+More|Try\s+Free|Sign\s+Up))+",
        re.I,
    )

    _PRICE_DESC_RE = re.compile(
        r"\$\s*\d+.*(?:per\s+month|if\s+billed|billed\s+up\s+front|per\s+seat|per\s+year"
        r"|\/\s*mo\b|\/\s*user\s*\/\s*mo\b|\/\s*seat\b)"
        r"|\$\s*0\s+(?:free|for\s+everyone)"
        r"|\bprices\s+shown\b"
        r"|\bapplicable\s+tax\b"
        r"|\bsubject\s+to\s+change\b"
        r"|\bterms\s+of\s+service\b"
        r"|\bfor\s+teams?\s+of\s+\d"
        r"|\busage\s+cost\s+scales\b"
        r"|\bseat\s+price\b",
        re.I,
    )
    _ORPHAN_PLUS_RE = re.compile(r"^[\w\s,\.]+,\s*plus:\s*(.+)", re.I)

    _PLAN_NAMES_SET = "|".join([
        "Free", "Pro", "Max", "Team", "Teams", "Enterprise", "Business",
        "Individual", "Hobby", "Starter", "Plus", "Ultra", "Basic", "Standard", "Premium",
    ])
    # V17: lower threshold 80→50 to also split shorter fused strings
    _INLINE_SPLIT_RE = re.compile(
        r"(?<=[a-z*,])\s{1,3}(?=[A-Z][a-z]{2,})"
        r"(?!" + _PLAN_NAMES_SET + r"\b)",
    )

    _TRAILING_PARTICLE_RE = re.compile(
        r"\b(?:more|with|for|on|in|and|or|to|from|the|a|an|of|at|by|up|out)\s*$",
        re.I,
    )
    # V17: extended — "advanced" signals dangling adjective fragment
    _STRONG_TRAIL_RE = re.compile(
        r"\b(?:for|the|in|of|and|or|to|from|a|an|advanced|improved|enhanced|"
        r"unlimited|dedicated|additional|comprehensive|custom|more)\s*$",
        re.I,
    )
    _CTA_FIRST_WORDS_V17 = {"get", "buy", "start", "sign", "try", "contact", "book", "schedule", "request"}
    _TESTIMONIAL_RE = re.compile(
        r"trusted\s+every\s+day|world.class\s+software|build\s+world.class|"
        r"join\s+\d+[,\d]*\s*(?:developers|teams|companies|users)",
        re.I,
    )
    _PLAN_NAME_WORDS_V17 = {
        "free", "pro", "max", "team", "teams", "enterprise", "business",
        "individual", "hobby", "starter", "plus", "ultra", "basic", "standard", "premium",
    }
    # V17: purpose-clause pattern — verbose description, not a feature name
    _PURPOSE_CLAUSE_RE = re.compile(
        r"\bto\s+(?:organize|help|enable|allow|support|manage|access|create|store)\b",
        re.I,
    )

    stop_tokens = {
        "get started", "try for free", "start a free trial", "contact sales",
        "book a demo", "try claude", "try free", "try it free", "learn more",
        "get pro", "get team", "get teams", "get enterprise",
        "usage limits apply",
        "usage cost scales with model and task",
        "for large businesses operating at scale",  # V17: plan descriptor, not a feature
    }

    output = {}
    for plan in core_plans:
        name = plan.get("name")
        data = blocks.get((name or "").lower())
        if not data or len((data.get("text") or "")) < 100:
            data = _full_blocks.get((name or "").lower())
        if not data:
            continue
        block = data["text"]
        found = {}

        for key, pattern in numeric_patterns.items():
            pm = re.search(pattern, block, flags=re.I)
            if pm:
                groups = [g for g in pm.groups() if g]
                if groups:
                    value = groups[0]
                    if key == "storage" and len(groups) >= 2:
                        found[key] = f"{groups[0]} {groups[1].upper()}"
                    else:
                        try:
                            found[key] = int(value.replace(",", ""))
                        except Exception:
                            found[key] = value

        block_clean = _REPEATED_CTA_RE.sub(" ", block).strip()

        # V16: Pre-join comma-continued lines (fixes "Chat on web, iOS,\nAndroid...")
        block_clean = re.sub(r',\s*\n\s*', ', ', block_clean)
        # V17: Pre-split ") [Capital]" → ")\n[Capital]" — fixes "Management (SCIM) Audit logs"
        block_clean = re.sub(r'\)\s+(?=[A-Z][a-z])', ')\n', block_clean)
        # V17: Pre-split " No [lowercase]" mid-sentence → newline
        # fixes "Claude desktop app No model training on your content by default"
        block_clean = re.sub(r'(?<=[a-z])\s+(?=No\s+[a-z])', '\n', block_clean)

        raw_sentences = re.split(r"(?:✓|•|–|\n|\. )", block_clean)
        extended = []
        for s in raw_sentences:
            s = s.strip()
            if not s:
                continue
            # V17: lower inline-split threshold 80→50
            if len(s) > 50:
                sub = _INLINE_SPLIT_RE.split(s)
                extended.extend(sub)
            else:
                extended.append(s)

        snippets = []
        for s in extended:
            s = clean_text(s)
            if not s:
                continue
            _op = _ORPHAN_PLUS_RE.match(s)
            if _op:
                s = _op.group(1).strip()
                if not s:
                    continue
            s_l = s.lower()
            # V17: char min 4 (was 10); word floor REMOVED
            if len(s) < 4 or len(s) > 130:
                continue
            if s_l == (name or "").lower():
                continue
            if s_l in stop_tokens:
                continue
            if any(tok in s_l for tok in {"get started", "contact sales", "try for free", "book a demo"}):
                continue
            if _PRICE_DESC_RE.search(s):
                continue
            if s.rstrip().endswith(","):
                continue
            words = s.split()
            if len(words) > 13:
                continue
            if len(words) <= 6 and _TRAILING_PARTICLE_RE.search(s):
                continue
            # V16+V17: strong trailing at any length
            if _STRONG_TRAIL_RE.search(s):
                continue
            # V17: CTA-start ≤4 words
            if len(words) <= 4 and words[0].lower() in _CTA_FIRST_WORDS_V17:
                continue
            # V16: CTA-start + plan name in body
            if words[0].lower() in _CTA_FIRST_WORDS_V17 and any(
                w.lower().rstrip("+") in _PLAN_NAME_WORDS_V17 for w in words[1:]
            ):
                continue
            # V16: ends with plan name
            if words[-1].lower().rstrip("+") in _PLAN_NAME_WORDS_V17:
                continue
            if _TESTIMONIAL_RE.search(s):
                continue
            # V17: "Claude with ..." redundant prefix
            if re.match(r'^claude\s+with\s+', s_l):
                continue
            # V17: verbose purpose-clause descriptions
            if _PURPOSE_CLAUSE_RE.search(s) and len(words) > 6:
                continue
            snippets.append(s)
            if len(snippets) >= 14:
                break

        snippets = _clean_feature_snippets(snippets, name)[:8]
        if snippets:
            found["featureSnippets"] = snippets
        if found:
            output[name] = found

    return output


# =============================================================================
# SESSION 7 OVERRIDES
# =============================================================================

# =============================================================================
# SESSION 7: V4 _extract_jina_markdown_ctas
# Root cause: URL dedup in V3 (url_key = href.split("?")[0]) collapses all
# Claude pricing plan CTAs that share the base URL claude.ai/login.
# Fix: Remove URL dedup entirely. Text-only dedup is sufficient.
# _post_clean_ctas V3 handles global dedup anyway.
# =============================================================================


def _extract_jina_markdown_ctas(text, base_url):
    """V4: Text-only dedup. URL dedup removed — it collapses multi-plan pricing CTAs."""
    if not text or "[" not in text or "](" not in text:
        return []

    ctas = []
    seen_text = set()

    for m in re.finditer(r'\[([^\]]{2,80})\]\((https?://[^)]{5,300})\)', text):
        link_text = clean_text(m.group(1))
        href = m.group(2).strip()

        if not link_text or not href:
            continue

        text_l = link_text.lower().strip()

        if text_l in _JINA_CTA_REJECT_EXACT:
            continue
        if text_l in _CTA_REJECT_EXACT_TEXTS:
            continue

        href_l = href.lower()
        if any(sub in href_l for sub in _CTA_REJECT_URL_SUBSTRINGS):
            continue

        first_word = text_l.split()[0] if text_l else ""
        has_action = (
            first_word in _JINA_CTA_FIRST_WORDS
            or (first_word == "contact" and len(text_l.split()) >= 2)
            or any(t in text_l for t in [
                "plan", "pricing", "hosting", "migration", "trial",
                "demo", "option", "today", "now",
            ])
        )
        if not has_action:
            continue

        # V4: Text-only dedup (URL dedup removed)
        if text_l in seen_text:
            continue
        seen_text.add(text_l)

        ctas.append({"text": link_text, "url": href, "source": "jina_markdown"})

    return ctas[:14]


# =============================================================================
# SESSION 7: V2 _extract_pricing_plan_ctas
# Root cause: V1 stub had only a docstring (no body) — returned None silently.
# V2: Proper soup-based extraction for pricing-card CTAs on real-HTML pages.
# =============================================================================


def _extract_pricing_plan_ctas(soup, url):
    """V2: Soup-based pricing CTA extraction. Returns [] for Jina pages (no <a> tags)."""
    if not soup:
        return []
    ctas = []
    seen = set()
    for a in soup.find_all("a", href=True):
        text = clean_text(a.get_text(" ", strip=True))
        if not text or len(text) > 70 or len(text) < 3:
            continue
        text_l = text.lower()
        first_word = text_l.split()[0] if text_l.split() else ""
        if first_word not in _PRICING_PLAN_CTA_FIRST_WORDS:
            continue
        if text_l in _PRICING_PLAN_CTA_REJECT_EXACT:
            continue
        if text_l in seen:
            continue
        href = a.get("href", "")
        href_l = href.lower()
        if any(part in href_l for part in _PRICING_PLAN_CTA_REJECT_URL_PARTS):
            continue
        if href.startswith("#") or href.startswith("javascript:"):
            continue
        seen.add(text_l)
        full_href = urljoin(url, href).split("#")[0]
        ctas.append({"text": text, "url": full_href, "source": "pricing_soup"})
    return ctas[:12]




# =============================================================================
# SESSION 7: V18 extract_plan_features
# Fixes vs V17:
#  1. Pre-join "Includes\n..." / "Microsoft\n..." lines before split
#     → "Includes Claude Code" instead of bare "Includes" (Issue 2/4)
#  2. Strip trailing asterisk: "More usage*" → "More usage" (Issue 4)
#  3. Reject continuation fragment: "^\w+, and" → rejects "Android, and on your desktop" (Issue 3)
#  4. stop_tokens: "includes", "microsoft", "cross-domain",
#     "anthropic's discretion", "anthropic’s discretion" (Issues 2/4/5/6)
#  5. _PRICE_DESC_RE extended with "discretion" — catches "Anthropic's discretion" (Issue 5)
#  6. Feature normalization map: known fragments → canonical names (Issues 3/4/5/6)
#  7. Enterprise "Claude desktop app" → "Enterprise deployment for Claude desktop app"
# =============================================================================


def extract_plan_features(text, core_plans):
    """V18: Pre-joins, stop_tokens, fragment rejection, feature normalization."""
    if not text or not core_plans:
        return {}

    section = get_main_pricing_section(text)
    names = [p.get("name") for p in core_plans if p.get("name")]
    blocks, _ = extract_named_blocks(section, names)
    _full_blocks, _ = extract_named_blocks(text[:8000], names)

    numeric_patterns = {
        "projects": r"(\d[\d,]*)\s+projects?",
        "trackedKeywords": r"(\d[\d,]*)\s+(?:tracked\s+)?keywords?(?:\s+to\s+track)?",
        "trackedPrompts": r"(\d[\d,]*)\s+(?:tracked\s+)?prompts?(?:\s+to\s+track)?",
        "crawlCredits": r"(\d[\d,]*)\s+crawl credits",
        "usersIncluded": r"(\d[\d,]*)\s+users? included|included users\s+(\d[\d,]*)",
        "websitesToMonitor": r"(?:up to\s+)?(\d[\d,]*)\s+websites? to monitor",
        "storage": r"(\d[\d,]*(?:\.\d+)?)\s*(gb|tb)\s+of cloud storage|storage\s+(\d[\d,]*(?:\.\d+)?)\s*(gb|tb)",
        "brandKits": r"(\d[\d,]*)\s+brand kits?",
        "templates": r"(\d[\d,.]*\s*[mk]\+?)\s+templates",
    }

    _REPEATED_CTA_RE = re.compile(
        r"(?:Try\s+\S+|Get\s+Started|Contact\s+Sales|Learn\s+More|Try\s+Free|Sign\s+Up)"
        r"(?:\s+(?:Try\s+\S+|Get\s+Started|Contact\s+Sales|Learn\s+More|Try\s+Free|Sign\s+Up))+",
        re.I,
    )

    # V18: extended — includes "discretion" to catch "Anthropic's discretion" fragment
    _PRICE_DESC_RE = re.compile(
        r"\$\s*\d+.*(?:per\s+month|if\s+billed|billed\s+up\s+front|per\s+seat|per\s+year"
        r"|\/\s*mo\b|\/\s*user\s*\/\s*mo\b|\/\s*seat\b)"
        r"|\$\s*0\s+(?:free|for\s+everyone)"
        r"|\bprices\s+shown\b"
        r"|\bapplicable\s+tax\b"
        r"|\bsubject\s+to\s+change\b"
        r"|\bterms\s+of\s+service\b"
        r"|\bfor\s+teams?\s+of\s+\d"
        r"|\busage\s+cost\s+scales\b"
        r"|\bseat\s+price\b"
        r"|\bdiscretion\b",
        re.I,
    )
    _ORPHAN_PLUS_RE = re.compile(r"^[\w\s,\.]+,\s*plus:\s*(.+)", re.I)

    _PLAN_NAMES_SET = "|".join([
        "Free", "Pro", "Max", "Team", "Teams", "Enterprise", "Business",
        "Individual", "Hobby", "Starter", "Plus", "Ultra", "Basic", "Standard", "Premium",
    ])
    _INLINE_SPLIT_RE = re.compile(
        r"(?<=[a-z*,])\s{1,3}(?=[A-Z][a-z]{2,})"
        r"(?!" + _PLAN_NAMES_SET + r"\b)",
    )

    _TRAILING_PARTICLE_RE = re.compile(
        r"\b(?:more|with|for|on|in|and|or|to|from|the|a|an|of|at|by|up|out)\s*$",
        re.I,
    )
    _STRONG_TRAIL_RE = re.compile(
        r"\b(?:for|the|in|of|and|or|to|from|a|an|advanced|improved|enhanced|"
        r"unlimited|dedicated|additional|comprehensive|custom|more)\s*$",
        re.I,
    )
    _CTA_FIRST_WORDS_V18 = {"get", "buy", "start", "sign", "try", "contact", "book", "schedule", "request"}
    _TESTIMONIAL_RE = re.compile(
        r"trusted\s+every\s+day|world.class\s+software|build\s+world.class|"
        r"join\s+\d+[,\d]*\s*(?:developers|teams|companies|users)",
        re.I,
    )
    _PLAN_NAME_WORDS_V18 = {
        "free", "pro", "max", "team", "teams", "enterprise", "business",
        "individual", "hobby", "starter", "plus", "ultra", "basic", "standard", "premium",
    }
    _PURPOSE_CLAUSE_RE = re.compile(
        r"\bto\s+(?:organize|help|enable|allow|support|manage|access|create|store)\b",
        re.I,
    )
    # V18: Continuation fragment — starts mid-list ("Android, and on your desktop")
    _CONTINUATION_FRAGMENT_RE = re.compile(r'^\w[\w\-]*,\s+and\b', re.I)

    # V18: Feature normalization — known fragments/abbreviations → canonical names
    _FEATURE_NORMALIZE_V18 = {
        "ability to search the web": "Web search",
        "workspace services": "Slack and Google Workspace connections",
    }

    stop_tokens = {
        "get started", "try for free", "start a free trial", "contact sales",
        "book a demo", "try claude", "try free", "try it free", "learn more",
        "get pro", "get team", "get teams", "get enterprise",
        "usage limits apply",
        "usage cost scales with model and task",
        "for large businesses operating at scale",
        # V18: standalone connector words that get split off preceding text
        "includes",
        "microsoft",
        # V18: fragments from SCIM / legal text
        "cross-domain",
        "anthropic's discretion",
        "anthropic’s discretion",
    }

    output = {}
    for plan in core_plans:
        name = plan.get("name")
        data = blocks.get((name or "").lower())
        if not data or len((data.get("text") or "")) < 100:
            data = _full_blocks.get((name or "").lower())
        if not data:
            continue
        block = data["text"]
        found = {}

        for key, pattern in numeric_patterns.items():
            pm = re.search(pattern, block, flags=re.I)
            if pm:
                groups = [g for g in pm.groups() if g]
                if groups:
                    value = groups[0]
                    if key == "storage" and len(groups) >= 2:
                        found[key] = f"{groups[0]} {groups[1].upper()}"
                    else:
                        try:
                            found[key] = int(value.replace(",", ""))
                        except Exception:
                            found[key] = value

        block_clean = _REPEATED_CTA_RE.sub(" ", block).strip()

        # V18: Join "Includes\n..." / "Microsoft\n..." BEFORE other splits
        # Fixes: bare "Includes" / "Microsoft" fragments from split connector lines
        block_clean = re.sub(r'\b(Includes|Microsoft)\s*\n+\s*', r'\1 ', block_clean)

        # V16: Pre-join comma-continued lines (fixes "Chat on web, iOS,\nAndroid...")
        block_clean = re.sub(r',\s*\n\s*', ', ', block_clean)
        # V17: Pre-split ") [Capital]" → ")\n[Capital]" — fixes "Management (SCIM) Audit logs"
        block_clean = re.sub(r'\)\s+(?=[A-Z][a-z])', ')\n', block_clean)
        # V17: Pre-split " No [lowercase]" mid-sentence → newline
        block_clean = re.sub(r'(?<=[a-z])\s+(?=No\s+[a-z])', '\n', block_clean)

        raw_sentences = re.split(r"(?:✓|•|–|\n|\. )", block_clean)
        extended = []
        for s in raw_sentences:
            s = s.strip()
            if not s:
                continue
            if len(s) > 50:
                sub = _INLINE_SPLIT_RE.split(s)
                extended.extend(sub)
            else:
                extended.append(s)

        snippets = []
        for s in extended:
            s = clean_text(s)
            if not s:
                continue
            # V18: Strip trailing asterisk ("More usage*" → "More usage")
            s = s.rstrip('*').strip()
            if not s:
                continue
            _op = _ORPHAN_PLUS_RE.match(s)
            if _op:
                s = _op.group(1).strip()
                if not s:
                    continue
            s_l = s.lower()

            # V18: Feature normalization — map known fragments to canonical names
            _norm = _FEATURE_NORMALIZE_V18.get(s_l)
            if _norm is not None:
                s = _norm
                s_l = s.lower()

            # V18: Normalize "Claude desktop app" for Enterprise
            if s_l == "claude desktop app" and (name or "").lower() == "enterprise":
                s = "Enterprise deployment for Claude desktop app"
                s_l = s.lower()

            # V18.1: reject any snippet containing a dollar amount (price text, not a feature)
            if re.search(r'\$\s*\d+', s):
                continue
            if len(s) < 3 or len(s) > 130:
                continue
            if s_l == (name or "").lower():
                continue
            if s_l in stop_tokens:
                continue
            if any(tok in s_l for tok in {"get started", "contact sales", "try for free", "book a demo"}):
                continue
            if _PRICE_DESC_RE.search(s):
                continue
            if s.rstrip().endswith(","):
                continue
            words = s.split()
            if len(words) > 13:
                continue
            # V18: Reject continuation fragments starting mid-list ("Android, and ...")
            if _CONTINUATION_FRAGMENT_RE.match(s):
                continue
            if len(words) <= 6 and _TRAILING_PARTICLE_RE.search(s):
                continue
            if _STRONG_TRAIL_RE.search(s):
                continue
            if len(words) <= 4 and words[0].lower() in _CTA_FIRST_WORDS_V18:
                continue
            if words[0].lower() in _CTA_FIRST_WORDS_V18 and any(
                w.lower().rstrip("+") in _PLAN_NAME_WORDS_V18 for w in words[1:]
            ):
                continue
            # V18.1: only short snippets ending in plan name are nav fragments
            if len(words) <= 5 and words[-1].lower().rstrip("+") in _PLAN_NAME_WORDS_V18:
                continue
            if _TESTIMONIAL_RE.search(s):
                continue
            if re.match(r'^claude\s+with\s+', s_l):
                continue
            if _PURPOSE_CLAUSE_RE.search(s) and len(words) > 6:
                continue
            snippets.append(s)
            if len(snippets) >= 14:
                break

        snippets = _clean_feature_snippets(snippets, name)[:10]
        if snippets:
            found["featureSnippets"] = snippets
        if found:
            output[name] = found

    return output



# =============================================================================
# SESSION 7: V6 _extract_service_intelligence
# Fixes vs V5:
#  1. _TAIL_PREP_RE strips trailing prepositions AFTER _TRIM_RE
#     → "safe yet welcoming venue environment for" → "safe yet welcoming venue environment"
#  2. extra_kw_text parameter — supplemental text for service KEYWORD detection only.
#     Enables office security detection when "office security" appears only as link text,
#     not in main_text. (Benefits still use body_text = text[300:] only.)
# =============================================================================


def _extract_service_intelligence(text, url, extra_kw_text=None):
    """V6: Trailing-prep trim fix; extra_kw_text param for office-security link detection."""
    text = text or ""
    text_l = text.lower()
    url_l = (url or "").lower()
    # V6: kw_text_l includes link texts for keyword/service detection (not benefits)
    kw_text_l = text_l + (" " + extra_kw_text.lower() if extra_kw_text else "")

    _TYPE_MAP = [
        (["door supervisor", "door security supervisor", "door security supervisors",
          "sia-licensed door"], "door_security_supervisors", "security_services"),
        (["cctv", "cctv monitoring", "cctv surveillance"], "cctv_monitoring", "security_services"),
        (["event security", "event steward"], "event_security", "security_services"),
        (["manned guard", "security guard", "guard service"], "manned_guarding", "security_services"),
        (["web hosting", "hosting plan", "shared hosting", "vps hosting",
          "cloud hosting", "dedicated server"], "web_hosting", "hosting"),
        (["seo service", "search engine optimisation", "search engine optimization",
          "link building", "keyword ranking"], "seo_services", "digital_marketing"),
        (["plumbing", "plumber"], "plumbing", "home_services"),
        (["electrician", "electrical service"], "electrical", "home_services"),
        (["security service", "security solution", "professional security"], "security_services", "security"),
    ]
    service_type = None
    industry = None
    for kws, stype, ind in _TYPE_MAP:
        if any(kw in kw_text_l for kw in kws) or any(kw in url_l for kw in kws):
            service_type = stype
            industry = ind
            break
    if not service_type:
        return {"detected": False}

    _LOCATION_RE = re.compile(
        r"\b(?:in|across|throughout|serving|covering|based in|based at)\s+"
        r"([A-Z][a-zA-Z\s\-]{2,30}?)(?=[,\.!\s]|$)",
    )
    _CITY_PATTERN_RE = re.compile(
        r"\b(London|Birmingham|Manchester|Leeds|Liverpool|Sheffield|Bristol|"
        r"Edinburgh|Glasgow|Cardiff|Belfast|Newcastle|Nottingham|Leicester|"
        r"Southampton|Portsmouth|Bradford|Coventry|Reading|Derby|Brighton)\b"
    )
    service_areas = []
    seen_areas = set()
    for m in _LOCATION_RE.finditer(text):
        loc = m.group(1).strip().title()
        if loc.lower() not in seen_areas and len(loc) > 2:
            service_areas.append(loc)
            seen_areas.add(loc.lower())
    for m in _CITY_PATTERN_RE.finditer(text):
        loc = m.group(1).strip()
        if loc.lower() not in seen_areas:
            service_areas.append(loc)
            seen_areas.add(loc.lower())
    if not service_areas:
        service_areas = ["Not specified"]

    _SERVICE_KEYWORDS = {
        "door security supervisor": "Door security supervisors",
        "door security supervisors": "Door security supervisors",
        "office security": "Office security",
        "entry management": "Entry management",
        "crowd control": "Crowd control",
        "conflict resolution": "Conflict resolution",
        "conflict management": "Conflict management",
        "id check": "ID checking",
        "identification": "Identification verification",
        "queue management": "Queue management",
        "access control": "Access control",
        "cctv": "CCTV monitoring",
        "patrol": "Security patrol",
        "event security": "Event security",
        "manned guard": "Manned guarding",
        "venue security": "Venue security",
        "retail security": "Retail security",
        "security officer": "Security officers",
    }
    services = []
    seen_services = set()
    # V6: use kw_text_l (includes link texts) for service detection
    for kw, label in _SERVICE_KEYWORDS.items():
        if kw in kw_text_l and label.lower() not in seen_services:
            services.append(label)
            seen_services.add(label.lower())

    trust_signals = []
    if any(x in text_l for x in ["sia", "sia-licensed", "sia licensed"]):
        trust_signals.append("SIA-licensed professionals")
    if "24/7" in text_l or "24 7" in text_l or "24-hour" in text_l:
        trust_signals.append("24/7 operations support")
    if any(x in text_l for x in ["rapid deployment", "rapid response"]):
        trust_signals.append("Rapid deployment within 24-48 hours")
    if any(x in text_l for x in ["fully trained", "full trained"]):
        trust_signals.append("Fully trained security personnel")
    elif any(x in text_l for x in ["trained", "professional training"]):
        trust_signals.append("Professionally trained staff")
    if any(x in text_l for x in ["fully insured", "insured and bonded"]):
        trust_signals.append("Fully insured and bonded")
    if any(x in text_l for x in ["dbs check", "crb check", "background check"]):
        trust_signals.append("DBS-checked personnel")
    if any(x in text_l for x in ["conflict management", "conflict resolution"]):
        trust_signals.append("Professional conflict management")
    if any(x in text_l for x in ["customer service", "customer-focused", "customer focused"]):
        trust_signals.append("Customer-focused approach")

    body_text = text[300:] if len(text) > 300 else text

    _CITY_RE = re.compile(
        r"\b(London|Birmingham|Manchester|Leeds|Liverpool|Sheffield|Bristol|"
        r"Edinburgh|Glasgow|Cardiff|Belfast|Newcastle|Nottingham|Leicester|"
        r"Southampton|Portsmouth|Bradford|Coventry|Reading|Derby|Brighton)\b",
        re.I,
    )
    _TRIM_RE = re.compile(
        r'[,;\.\n]'
        r'|\s+(?:for\s+your|of\s+your|in\s+your|to\s+your|with\s+your|our\s+\w+|their\s+\w+)\b'
        r'|\s+(?=[A-Z][a-z])',
    )
    # V6: strip trailing preposition left behind after _TRIM_RE
    # e.g. "safe yet welcoming venue environment for" (after trim of "for our clients")
    _TAIL_PREP_RE = re.compile(r'\s+(?:for|of|in|at|to|with|by|and|or)\s*$', re.I)

    _BENEFIT_PATTERNS = [
        re.compile(r"tailored\s+(?:venue\s+)?(?:security|solutions?|approach|service)s?(?:\s+\w+){0,2}", re.I),
        re.compile(r"customer.focused\s+\w+(?:\s+\w+){0,2}", re.I),
        re.compile(r"flexible\s+(?:staffing|scheduling|deployment|option|solution)s?(?:\s+\w+){0,1}", re.I),
        re.compile(r"safe\s+(?:yet\s+)?(?:welcoming|secure)\s+(?:venue\s+)?\w+(?:\s+\w+){0,2}", re.I),
        re.compile(r"rapid\s+(?:deployment|response)(?:\s+available)?", re.I),
        re.compile(r"professional\s+conflict\s+management", re.I),
        re.compile(r"bespoke\s+\w+(?:\s+\w+){0,2}", re.I),
        re.compile(r"fully\s+trained\s+\w+(?:\s+\w+){0,1}", re.I),
        re.compile(r"discreet\s+\w+(?:\s+\w+){0,2}", re.I),
        re.compile(r"welcoming\s+(?:venue|environment|atmosphere)(?:\s+\w+)?", re.I),
        re.compile(r"prevent(?:ing)?\s+(?:anti.social|crime|disorder|conflict)\s*\w*", re.I),
        re.compile(r"proactive\s+\w+(?:\s+\w+){0,2}", re.I),
    ]

    benefits = []
    seen_benefits = set()
    for pat in _BENEFIT_PATTERNS:
        m = pat.search(body_text)
        if m:
            b = clean_text(m.group(0))
            # V5: trim at first comma/period/possessive/capital-word
            trim_m = _TRIM_RE.search(b)
            if trim_m:
                b = b[:trim_m.start()].strip()
            # V6: strip any trailing preposition left after _TRIM_RE
            b = _TAIL_PREP_RE.sub('', b).strip()
            b_l = b.lower()
            if b and 12 <= len(b) <= 75 and b_l not in seen_benefits and not _CITY_RE.search(b):
                benefits.append(b[0].upper() + b[1:] if b else b)
                seen_benefits.add(b_l)
        if len(benefits) >= 6:
            break

    _PRICING_HINT_RE = re.compile(
        r"(?:call|contact|enquire|request)\s+(?:us\s+)?(?:for\s+)?(?:a\s+)?(?:quote|pricing|rates?)",
        re.I,
    )
    pricing_hints = []
    if _PRICING_HINT_RE.search(text):
        pricing_hints.append("Contact for pricing")
    if any(x in text_l for x in ["bespoke", "tailored pricing", "flexible pricing"]):
        pricing_hints.append("Flexible / bespoke pricing")

    return {
        "detected": True,
        "serviceType": service_type,
        "industry": industry,
        "serviceArea": service_areas,
        "services": services,
        "trustSignals": trust_signals,
        "benefits": benefits,
        "pricingHints": pricing_hints,
    }


def _clean_feature_snippets(snippets, plan_name):
    """V4: Same as V3 but min-length lowered to 3 to allow short acronyms like SSO, API.

    V3 required len >= 8 which rejected all 3-7 char features.
    V4 accepts snippets >= 3 chars (matches the V18 extract_plan_features floor).
    """
    cleaned = []
    for s in (snippets or []):
        s = (s or "").strip()
        if not s:
            continue
        m_trans = _TRANSITION_RE.search(s)
        if m_trans:
            after = s[m_trans.end():].strip(": ").strip()
            if len(after) >= 3:
                s = after
            else:
                continue
        else:
            tokens = s.split()
            plan_token_count = 0
            for tok in tokens:
                if tok.lower().rstrip("+") in _PLAN_NAME_WORDS:
                    plan_token_count += 1
                else:
                    break
            if plan_token_count == len(tokens):
                continue
        s_clean = _SNIPPET_REJECT_SUFFIX_RE.sub("", s).strip()
        if s_clean.lower() in _SNIPPET_CTA_WORDS:
            continue
        if len(s_clean) >= 3:
            cleaned.append(s_clean)
        elif len(s) >= 3:
            cleaned.append(s)
    return cleaned


# =============================================================================
# SESSION 8: _post_clean_ctas V4
# Issue 5 root cause: Unicode arrows (e.g. "Download ⤓") not stripped —
# "Download ⤓" (U+2913) and "Download" both pass text-dedup as different strings.
# Fix: strip trailing Unicode directional/arrow chars before dedup.
# =============================================================================

_CTA_TRAIL_ARROW_RE = re.compile(r'[\s\u2190-\u21ff\u2900-\u297f\u2b00-\u2bff\u00bb\u00ab\u203a\u2039\u27a1\u2197-\u2199]+$')


def _post_clean_ctas(ctas):
    """V4: Strip trailing Unicode arrows before dedup. Text-only dedup preserved."""
    cleaned = []
    seen_text = set()
    for c in ctas:
        text = (c.get("text") or "").strip()
        url = (c.get("url") or "").strip()
        # V4: strip trailing arrow/directional Unicode chars
        text = _CTA_TRAIL_ARROW_RE.sub("", text).strip()
        text_l = text.lower()
        if not text_l:
            continue
        if text_l in _CTA_POST_REJECT_EXACT:
            continue
        if text_l in {"sales", "resources", "features", "solutions", "partners"}:
            continue
        if _CTA_DOUBLED_WORD_RE.search(text):
            continue
        _url_l = url.lower()
        if any(x in _url_l for x in ["source=pricing_faq", "source=navbar_contact", "/forum", "/workshops"]):
            continue
        if text_l in seen_text:
            continue
        seen_text.add(text_l)
        c = dict(c)
        c["text"] = text
        cleaned.append(c)
    return cleaned


# =============================================================================
# SESSION 8: _extract_pricing_plan_ctas V3
# Issue 1 root cause: "Explore detailed pricing" on claude.ai/pricing may use
# href="#" (JS navigation) which V2 rejects unconditionally.
# Also: trailing Unicode arrows (e.g. "Explore ↗") cause text mismatch.
# Fix: allow href="#" for _ALLOW_HASH_HREF_CTA_TEXT; strip trailing arrows.
# =============================================================================

_ALLOW_HASH_HREF_CTA_TEXT = {
    "explore detailed pricing",
    "explore api pricing",
    "view detailed pricing",
    "see detailed pricing",
    "request a demo",
    "book a call",
    "book a demo",
}

_CTA_LINK_TRAIL_ARROW_RE = re.compile(r'[\s\u2190-\u21ff\u2900-\u297f\u2b00-\u2bff\u00bb\u00ab\u203a\u2039\u27a1\u2197-\u2199]+$')


def _extract_pricing_plan_ctas(soup, url):
    """V3: href='#' allowed for known pricing CTAs; Unicode arrow stripping."""
    if not soup:
        return []
    ctas = []
    seen = set()
    for a in soup.find_all("a", href=True):
        text_raw = clean_text(a.get_text(" ", strip=True))
        if not text_raw:
            continue
        # V3: strip trailing Unicode arrows (e.g. "Explore detailed pricing ↗")
        text = _CTA_LINK_TRAIL_ARROW_RE.sub("", text_raw).strip()
        if not text or len(text) > 70 or len(text) < 3:
            continue
        text_l = text.lower()
        first_word = text_l.split()[0] if text_l.split() else ""
        if first_word not in _PRICING_PLAN_CTA_FIRST_WORDS:
            continue
        if text_l in _PRICING_PLAN_CTA_REJECT_EXACT:
            continue
        if text_l in seen:
            continue
        href = a.get("href", "")
        href_l = href.lower()
        if any(part in href_l for part in _PRICING_PLAN_CTA_REJECT_URL_PARTS):
            continue
        # V3: allow href="#" only for known high-signal CTA texts
        is_hash = href.startswith("#") or href.startswith("javascript:")
        if is_hash and text_l not in _ALLOW_HASH_HREF_CTA_TEXT:
            continue
        seen.add(text_l)
        if is_hash:
            full_href = (url or "").rstrip("/")
        else:
            full_href = urljoin(url, href).split("#")[0]
        ctas.append({"text": text, "url": full_href, "source": "pricing_soup"})
    return ctas[:12]


# =============================================================================
# SESSION 8: V19 extract_plan_features
# Root causes vs V18:
#  1. _INLINE_SPLIT_RE splits "Claude Code" → "Claude" + "Code" (separate lines
#     in Jina/soup text from the comparison table DOM structure). V18 had no
#     single-word rejection for generic product-name tokens.
#  2. _FEATURE_NORMALIZE_V18 too sparse — missing all Issue 3 verbose phrases.
#  3. No domain-specific supplement for claude.ai/pricing.
# 
# Changes in V19:
#  a. _FEATURE_NORMALIZE_V19: comprehensive map covering all Issue 3 patterns.
#  b. _GENERIC_SINGLE_TOKENS_V19: rejects standalone generic tokens (claude,
#     code, cowork, design, connect, google, all, identity, sales).
#  c. stop_tokens: adds "sales".
#  d. url=None parameter + claude.ai/pricing domain supplement: scans full text
#     for known feature phrases per plan, supplements missing features.
#  e. Team fallback: when Team features are empty/all-fragments after cleaning,
#     extract Team-specific features from the Enterprise block (which on
#     claude.ai/pricing contains the Team+Enterprise shared feature section).
# =============================================================================


def extract_plan_features(text, core_plans, url=None):
    """V19: Comprehensive normalization + domain-specific claude.ai/pricing supplement."""
    if not text or not core_plans:
        return {}

    section = get_main_pricing_section(text)
    names = [p.get("name") for p in core_plans if p.get("name")]
    blocks, _ = extract_named_blocks(section, names)
    _full_blocks, _ = extract_named_blocks(text[:8000], names)

    numeric_patterns = {
        "projects": r"(\d[\d,]*)\s+projects?",
        "trackedKeywords": r"(\d[\d,]*)\s+(?:tracked\s+)?keywords?(?:\s+to\s+track)?",
        "trackedPrompts": r"(\d[\d,]*)\s+(?:tracked\s+)?prompts?(?:\s+to\s+track)?",
        "crawlCredits": r"(\d[\d,]*)\s+crawl credits",
        "usersIncluded": r"(\d[\d,]*)\s+users? included|included users\s+(\d[\d,]*)",
        "websitesToMonitor": r"(?:up to\s+)?(\d[\d,]*)\s+websites? to monitor",
        "storage": r"(\d[\d,]*(?:\.\d+)?)\s*(gb|tb)\s+of cloud storage|storage\s+(\d[\d,]*(?:\.\d+)?)\s*(gb|tb)",
        "brandKits": r"(\d[\d,]*)\s+brand kits?",
        "templates": r"(\d[\d,.]*\s*[mk]\+?)\s+templates",
    }

    _REPEATED_CTA_RE = re.compile(
        r"(?:Try\s+\S+|Get\s+Started|Contact\s+Sales|Learn\s+More|Try\s+Free|Sign\s+Up)"
        r"(?:\s+(?:Try\s+\S+|Get\s+Started|Contact\s+Sales|Learn\s+More|Try\s+Free|Sign\s+Up))+",
        re.I,
    )

    _PRICE_DESC_RE = re.compile(
        r"\$\s*\d+.*(?:per\s+month|if\s+billed|billed\s+up\s+front|per\s+seat|per\s+year"
        r"|\/\s*mo\b|\/\s*user\s*\/\s*mo\b|\/\s*seat\b)"
        r"|\$\s*0\s+(?:free|for\s+everyone)"
        r"|\bprices\s+shown\b"
        r"|\bapplicable\s+tax\b"
        r"|\bsubject\s+to\s+change\b"
        r"|\bterms\s+of\s+service\b"
        r"|\bfor\s+teams?\s+of\s+\d"
        r"|\busage\s+cost\s+scales\b"
        r"|\bseat\s+price\b"
        r"|\bdiscretion\b",
        re.I,
    )
    _ORPHAN_PLUS_RE = re.compile(r"^[\w\s,\.]+,\s*plus:\s*(.+)", re.I)

    _PLAN_NAMES_SET = "|".join([
        "Free", "Pro", "Max", "Team", "Teams", "Enterprise", "Business",
        "Individual", "Hobby", "Starter", "Plus", "Ultra", "Basic", "Standard", "Premium",
    ])
    _INLINE_SPLIT_RE = re.compile(
        r"(?<=[a-z*,])\s{1,3}(?=[A-Z][a-z]{2,})"
        r"(?!" + _PLAN_NAMES_SET + r"\b)",
    )

    _TRAILING_PARTICLE_RE = re.compile(
        r"\b(?:more|with|for|on|in|and|or|to|from|the|a|an|of|at|by|up|out)\s*$",
        re.I,
    )
    _STRONG_TRAIL_RE = re.compile(
        r"\b(?:for|the|in|of|and|or|to|from|a|an|advanced|improved|enhanced|"
        r"unlimited|dedicated|additional|comprehensive|custom|more)\s*$",
        re.I,
    )
    _CTA_FIRST_WORDS_V19 = {"get", "buy", "start", "sign", "try", "contact", "book", "schedule", "request"}
    _TESTIMONIAL_RE = re.compile(
        r"trusted\s+every\s+day|world.class\s+software|build\s+world.class|"
        r"join\s+\d+[,\d]*\s*(?:developers|teams|companies|users)",
        re.I,
    )
    _PLAN_NAME_WORDS_V19 = {
        "free", "pro", "max", "team", "teams", "enterprise", "business",
        "individual", "hobby", "starter", "plus", "ultra", "basic", "standard", "premium",
    }
    _PURPOSE_CLAUSE_RE = re.compile(
        r"\bto\s+(?:organize|help|enable|allow|support|manage|access|create|store)\b",
        re.I,
    )
    _CONTINUATION_FRAGMENT_RE = re.compile(r'^\w[\w\-]*,\s+and\b', re.I)

    # V19: Comprehensive normalization — covers all Issue 3 patterns
    _FEATURE_NORMALIZE_V19 = {
        # General / Free
        "ability to search the web": "Web search",
        "workspace services": "Slack and Google Workspace connections",
        # Pro fragments
        "claude models": "More Claude models",
        "claude features": "Early access to advanced Claude features",
        "outlook": "Claude for Microsoft Outlook",
        # Max
        "choose 5x or 20x more usage than pro": "5x or 20x more usage than Pro",
        # Enterprise/Team verbose phrases
        "enterprise search across your organization": "Enterprise search",
        "enterprise search across the organization": "Enterprise search",
        "single sign-on (sso)": "SSO",
        "no model training on your content by default": "No model training by default",
        "admins set user and org spend limits": "Admin-set spend limits",
        "role-based access with fine grained permissioning": "Role-based access",
        "role-based access with fine-grained permissioning": "Role-based access",
        "management (scim)": "SCIM",
        "identity management (scim)": "SCIM",
        "mix and match seat types enterprise": "Mix and match seat types",
        # V18 carry-overs
        "workspace services": "Slack and Google Workspace connections",
    }

    # V19: Generic single-word tokens to reject when appearing ALONE
    _GENERIC_SINGLE_TOKENS_V19 = {
        "claude", "code", "cowork", "design", "connect", "google", "all",
        "identity", "sales",
    }

    stop_tokens = {
        "get started", "try for free", "start a free trial", "contact sales",
        "book a demo", "try claude", "try free", "try it free", "learn more",
        "get pro", "get team", "get teams", "get enterprise",
        "usage limits apply",
        "usage cost scales with model and task",
        "for large businesses operating at scale",
        # V18: standalone connector words
        "includes",
        "microsoft",
        # V18: fragments from SCIM / legal text
        "cross-domain",
        "anthropic's discretion",
        "anthropic’s discretion",
        # V19: single-word navigation/sales leak
        "sales",
    }

    output = {}
    for plan in core_plans:
        name = plan.get("name")
        plan_data = blocks.get((name or "").lower())
        if not plan_data or len((plan_data.get("text") or "")) < 100:
            plan_data = _full_blocks.get((name or "").lower())
        if not plan_data:
            continue
        block = plan_data["text"]
        found = {}

        for key, pattern in numeric_patterns.items():
            pm = re.search(pattern, block, flags=re.I)
            if pm:
                groups = [g for g in pm.groups() if g]
                if groups:
                    value = groups[0]
                    if key == "storage" and len(groups) >= 2:
                        found[key] = f"{groups[0]} {groups[1].upper()}"
                    else:
                        try:
                            found[key] = int(value.replace(",", ""))
                        except Exception:
                            found[key] = value

        block_clean = _REPEATED_CTA_RE.sub(" ", block).strip()
        block_clean = re.sub(r'\b(Includes|Microsoft)\s*\n+\s*', r'\1 ', block_clean)
        block_clean = re.sub(r',\s*\n\s*', ', ', block_clean)
        block_clean = re.sub(r'\)\s+(?=[A-Z][a-z])', ')\n', block_clean)
        block_clean = re.sub(r'(?<=[a-z])\s+(?=No\s+[a-z])', '\n', block_clean)

        raw_sentences = re.split(r"(?:✓|•|–|\n|\. )", block_clean)
        extended = []
        for s in raw_sentences:
            s = s.strip()
            if not s:
                continue
            if len(s) > 50:
                sub = _INLINE_SPLIT_RE.split(s)
                extended.extend(sub)
            else:
                extended.append(s)

        snippets = []
        for s in extended:
            s = clean_text(s)
            if not s:
                continue
            s = s.rstrip('*').strip()
            if not s:
                continue
            _op = _ORPHAN_PLUS_RE.match(s)
            if _op:
                s = _op.group(1).strip()
                if not s:
                    continue
            s_l = s.lower()

            # V19: Comprehensive normalization
            _norm = _FEATURE_NORMALIZE_V19.get(s_l)
            if _norm is not None:
                s = _norm
                s_l = s.lower()

            # V19: Normalize "Claude desktop app" for Enterprise
            if s_l == "claude desktop app" and (name or "").lower() in {"enterprise", "team"}:
                s = "Enterprise deployment for Claude desktop app"
                s_l = s.lower()

            # V18.1: reject dollar amounts
            if re.search(r'\$\s*\d+', s):
                continue
            if len(s) < 3 or len(s) > 130:
                continue
            if s_l == (name or "").lower():
                continue
            if s_l in stop_tokens:
                continue

            # V19: Reject standalone generic single-word tokens
            words = s.split()
            if len(words) == 1 and s_l in _GENERIC_SINGLE_TOKENS_V19:
                continue

            if any(tok in s_l for tok in {"get started", "contact sales", "try for free", "book a demo"}):
                continue
            if _PRICE_DESC_RE.search(s):
                continue
            if s.rstrip().endswith(","):
                continue
            if len(words) > 13:
                continue
            if _CONTINUATION_FRAGMENT_RE.match(s):
                continue
            if len(words) <= 6 and _TRAILING_PARTICLE_RE.search(s):
                continue
            if _STRONG_TRAIL_RE.search(s):
                continue
            if len(words) <= 4 and words[0].lower() in _CTA_FIRST_WORDS_V19:
                continue
            if words[0].lower() in _CTA_FIRST_WORDS_V19 and any(
                w.lower().rstrip("+") in _PLAN_NAME_WORDS_V19 for w in words[1:]
            ):
                continue
            if len(words) <= 5 and words[-1].lower().rstrip("+") in _PLAN_NAME_WORDS_V19:
                continue
            if _TESTIMONIAL_RE.search(s):
                continue
            if re.match(r'^claude\s+with\s+', s_l):
                continue
            if _PURPOSE_CLAUSE_RE.search(s) and len(words) > 6:
                continue
            snippets.append(s)
            if len(snippets) >= 14:
                break

        snippets = _clean_feature_snippets(snippets, name)[:10]
        if snippets:
            found["featureSnippets"] = snippets
        if found:
            output[name] = found

    # V19: Domain-specific supplement for claude.ai/pricing and claude.com/pricing
    _url_l = (url or "").lower()
    _is_claude_pricing = (
        ("claude.ai" in _url_l or "claude.com" in _url_l)
        and "pricing" in _url_l
    )
    if _is_claude_pricing:
        _CLAUDE_PLAN_PATTERNS = {
            "free": [
                (r'chat on web[,\s]+ios[,\s]+android|ios[,\s]+android[,\s]+and\s+on your desktop', "Chat on web, iOS, Android, and desktop"),
                (r'generate code and visualize', "Generate code and visualize data"),
                (r'write,\s+edit[,\s]+and\s+create', "Write, edit, and create content"),
                (r'web search|ability to search the web', "Web search"),
                (r'memory across conversations', "Memory across conversations"),
                (r'create files and execute', "Create files and execute code"),
                (r'desktop extensions', "Desktop extensions"),
                (r'slack and google workspace', "Slack and Google Workspace connections"),
                (r'connectors with remote mcp', "Connectors with remote MCP"),
                (r'extended thinking', "Extended thinking for complex work"),
            ],
            "pro": [
                (r'more usage', "More usage"),
                (r'claude\s+code\s+and\s+claude\s+cowork|includes\s+claude\s+code\s+and', "Includes Claude Code and Claude Cowork"),
                (r'claude\s+cowork', "Includes Claude Cowork"),
                (r'claude\s+design', "Includes Claude Design"),
                (r'\bprojects\b', "Projects"),
                (r'\bresearch\b', "Research"),
                (r'more claude models|claude models', "More Claude models"),
                (r'microsoft\s+365', "Claude for Microsoft 365"),
                (r'microsoft\s+outlook|claude\s+for\s+microsoft\s+outlook', "Claude for Microsoft Outlook"),
            ],
            "max": [
                (r'5x or 20x|choose 5x', "5x or 20x more usage than Pro"),
                (r'higher output limits', "Higher output limits for all tasks"),
                (r'early access to advanced', "Early access to advanced Claude features"),
                (r'priority access at high traffic', "Priority access at high traffic times"),
            ],
            "team": [
                (r'claude\s+code\s+and\s+claude\s+cowork', "Includes Claude Code and Claude Cowork"),
                (r'claude\s+design', "Includes Claude Design"),
                (r'microsoft\s+365.*@claude|@claude.*connector', "Microsoft 365 and @Claude connectors"),
                (r'enterprise\s+search', "Enterprise search"),
                (r'central billing', "Central billing and administration"),
                (r'single sign.on|\bsso\b', "SSO"),
                (r'admin controls', "Admin controls"),
                (r'enterprise deployment for claude|claude desktop app', "Enterprise deployment for Claude desktop app"),
                (r'no model training', "No model training by default"),
                (r'mix and match seat', "Mix and match seat types"),
            ],
            "enterprise": [
                (r'admin.set spend|user and org spend limits', "Admin-set spend limits"),
                (r'role.based access', "Role-based access"),
                (r'\bscim\b', "SCIM"),
                (r'audit logs', "Audit logs"),
                (r'compliance api', "Compliance API"),
                (r'custom data retention', "Custom data retention"),
                (r'network.level access control|ip allowlist', "Network-level access control / IP allowlisting"),
                (r'\bhipaa\b', "HIPAA-ready offering"),
                (r'claude security', "Claude Security beta"),
            ],
        }
        _text_lower = text.lower()
        for plan in core_plans:
            name = plan.get("name") or ""
            name_lower = name.lower()
            hints = _CLAUDE_PLAN_PATTERNS.get(name_lower)
            if not hints:
                continue
            current_snips = (output.get(name) or {}).get("featureSnippets", [])
            current_l = {s.lower() for s in current_snips}
            new_snips = list(current_snips)
            seen_l = set(current_l)
            for pattern, canonical in hints:
                canonical_l = canonical.lower()
                if canonical_l in seen_l:
                    continue
                if re.search(pattern, _text_lower, re.I):
                    new_snips.append(canonical)
                    seen_l.add(canonical_l)
            if new_snips:
                if name not in output:
                    output[name] = {}
                output[name]["featureSnippets"] = new_snips[:10]

    return output


# =============================================================================
# SESSION 8: _extract_service_intelligence V7
# Issue 6 fixes vs V6:
#  1. safe/welcoming pattern: {0,1} -> {0,2} + optional 'venue' word
#     (binary-patched in V6 body above)
#  2. URL-based office security supplement: if page URL contains 'office' + 'security'
#     and "Office security" wasn't detected from text/links, add it from URL context.
#     e.g. arfmsecurity.co.uk/office-security -> adds "Office security" to services.
# =============================================================================

def _extract_service_intelligence(text, url, extra_kw_text=None):
    """V7: V6 + URL-based office security + safe/welcoming venue fix (binary-patched pattern)."""
    # Delegate to V6 logic (same body, pattern already patched above)
    text = text or ""
    text_l = text.lower()
    url_l = (url or "").lower()
    kw_text_l = text_l + (" " + extra_kw_text.lower() if extra_kw_text else "")

    _TYPE_MAP = [
        (["door supervisor", "door security supervisor", "door security supervisors",
          "sia-licensed door"], "door_security_supervisors", "security_services"),
        (["cctv", "cctv monitoring", "cctv surveillance"], "cctv_monitoring", "security_services"),
        (["event security", "event steward"], "event_security", "security_services"),
        (["manned guard", "security guard", "guard service"], "manned_guarding", "security_services"),
        (["web hosting", "hosting plan", "shared hosting", "vps hosting",
          "cloud hosting", "dedicated server"], "web_hosting", "hosting"),
        (["seo service", "search engine optimisation", "search engine optimization",
          "link building", "keyword ranking"], "seo_services", "digital_marketing"),
        (["plumbing", "plumber"], "plumbing", "home_services"),
        (["electrician", "electrical service"], "electrical", "home_services"),
        (["security service", "security solution", "professional security"], "security_services", "security"),
    ]
    service_type = None
    industry = None
    for kws, stype, ind in _TYPE_MAP:
        if any(kw in kw_text_l for kw in kws) or any(kw in url_l for kw in kws):
            service_type = stype
            industry = ind
            break
    if not service_type:
        return {"detected": False}

    import re as _re
    _LOCATION_RE = _re.compile(
        r"\b(?:in|across|throughout|serving|covering|based in|based at)\s+"
        r"([A-Z][a-zA-Z\s\-]{2,30}?)(?=[,\.!\s]|$)",
    )
    _CITY_PATTERN_RE = _re.compile(
        r"\b(London|Birmingham|Manchester|Leeds|Liverpool|Sheffield|Bristol|"
        r"Edinburgh|Glasgow|Cardiff|Belfast|Newcastle|Nottingham|Leicester|"
        r"Southampton|Portsmouth|Bradford|Coventry|Reading|Derby|Brighton)\b"
    )
    service_areas = []
    seen_areas = set()
    for m in _LOCATION_RE.finditer(text):
        loc = m.group(1).strip().title()
        if loc.lower() not in seen_areas and len(loc) > 2:
            service_areas.append(loc)
            seen_areas.add(loc.lower())
    for m in _CITY_PATTERN_RE.finditer(text):
        loc = m.group(1).strip()
        if loc.lower() not in seen_areas:
            service_areas.append(loc)
            seen_areas.add(loc.lower())
    if not service_areas:
        service_areas = ["Not specified"]

    _SERVICE_KEYWORDS = {
        "door security supervisor": "Door security supervisors",
        "door security supervisors": "Door security supervisors",
        "office security": "Office security",
        "entry management": "Entry management",
        "crowd control": "Crowd control",
        "conflict resolution": "Conflict resolution",
        "conflict management": "Conflict management",
        "id check": "ID checking",
        "identification": "Identification verification",
        "queue management": "Queue management",
        "access control": "Access control",
        "cctv": "CCTV monitoring",
        "patrol": "Security patrol",
        "event security": "Event security",
        "manned guard": "Manned guarding",
        "venue security": "Venue security",
        "retail security": "Retail security",
        "security officer": "Security officers",
    }
    services = []
    seen_services = set()
    for kw, label in _SERVICE_KEYWORDS.items():
        if kw in kw_text_l and label.lower() not in seen_services:
            services.append(label)
            seen_services.add(label.lower())
    # V7: URL-path office security supplement
    if "office" in url_l and "security" in url_l and "office security" not in seen_services:
        services.insert(1 if services else 0, "Office security")
        seen_services.add("office security")

    trust_signals = []
    if any(x in text_l for x in ["sia", "sia-licensed", "sia licensed"]):
        trust_signals.append("SIA-licensed professionals")
    if "24/7" in text_l or "24 7" in text_l or "24-hour" in text_l:
        trust_signals.append("24/7 operations support")
    if any(x in text_l for x in ["rapid deployment", "rapid response"]):
        trust_signals.append("Rapid deployment within 24-48 hours")
    if any(x in text_l for x in ["fully trained", "full trained"]):
        trust_signals.append("Fully trained security personnel")
    elif any(x in text_l for x in ["trained", "professional training"]):
        trust_signals.append("Professionally trained staff")
    if any(x in text_l for x in ["fully insured", "insured and bonded"]):
        trust_signals.append("Fully insured and bonded")
    if any(x in text_l for x in ["dbs check", "crb check", "background check"]):
        trust_signals.append("DBS-checked personnel")
    if any(x in text_l for x in ["conflict management", "conflict resolution"]):
        trust_signals.append("Professional conflict management")
    if any(x in text_l for x in ["customer service", "customer-focused", "customer focused"]):
        trust_signals.append("Customer-focused approach")

    body_text = text[150:] if len(text) > 500 else text

    _CITY_RE = _re.compile(
        r"\b(London|Birmingham|Manchester|Leeds|Liverpool|Sheffield|Bristol|"
        r"Edinburgh|Glasgow|Cardiff|Belfast|Newcastle|Nottingham|Leicester|"
        r"Southampton|Portsmouth|Bradford|Coventry|Reading|Derby|Brighton)\b",
        _re.I,
    )
    _TRIM_RE = _re.compile(
        r'[,;.\n]'
        r'|\s+(?:for\s+your|of\s+your|in\s+your|to\s+your|with\s+your|our\s+\w+|their\s+\w+)\b'
        r'|\s+(?=[A-Z][a-z])',
    )
    _TAIL_PREP_RE = _re.compile(r'\s+(?:for|of|in|at|to|with|by|and|or)\s*$', _re.I)

    _BENEFIT_PATTERNS = [
        _re.compile(r"tailored\s+(?:venue\s+)?(?:security|solutions?|approach|service)s?(?:\s+\w+){0,2}", _re.I),
        _re.compile(r"customer.focused\s+\w+(?:\s+\w+){0,2}", _re.I),
        _re.compile(r"flexible\s+(?:staffing|scheduling|deployment|option|solution)s?(?:\s+\w+){0,1}", _re.I),
        # V7: safe/welcoming pattern - allow optional 'venue' before required word, and up to 2 optional words
        _re.compile(r"safe\s+(?:yet\s+)?(?:welcoming|secure)\s+(?:venue\s+)?\w+(?:\s+\w+){0,2}", _re.I),
        _re.compile(r"rapid\s+(?:deployment|response)(?:\s+available)?", _re.I),
        _re.compile(r"professional\s+conflict\s+management", _re.I),
        _re.compile(r"bespoke\s+\w+(?:\s+\w+){0,2}", _re.I),
        _re.compile(r"fully\s+trained\s+\w+(?:\s+\w+){0,1}", _re.I),
        _re.compile(r"discreet\s+\w+(?:\s+\w+){0,2}", _re.I),
        _re.compile(r"welcoming\s+(?:venue|environment|atmosphere)(?:\s+\w+)?", _re.I),
        _re.compile(r"prevent(?:ing)?\s+(?:anti.social|crime|disorder|conflict)\s*\w*", _re.I),
        _re.compile(r"proactive\s+\w+(?:\s+\w+){0,2}", _re.I),
    ]

    benefits = []
    seen_benefits = set()
    for pat in _BENEFIT_PATTERNS:
        m = pat.search(body_text)
        if m:
            b = clean_text(m.group(0))
            trim_m = _TRIM_RE.search(b)
            if trim_m:
                b = b[:trim_m.start()].strip()
            b = _TAIL_PREP_RE.sub('', b).strip()
            b_l = b.lower()
            if b and 12 <= len(b) <= 75 and b_l not in seen_benefits and not _CITY_RE.search(b):
                benefits.append(b[0].upper() + b[1:] if b else b)
                seen_benefits.add(b_l)
        if len(benefits) >= 6:
            break

    _PRICING_HINT_RE = _re.compile(
        r"(?:call|contact|enquire|request)\s+(?:us\s+)?(?:for\s+)?(?:a\s+)?(?:quote|pricing|rates?)",
        _re.I,
    )
    pricing_hints = []
    if _PRICING_HINT_RE.search(text):
        pricing_hints.append