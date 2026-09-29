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

    if raw_url.lower().startswith(("javascript:", "#")):
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

        if not value or value in seen:
            continue

        seen.add(value)
        output.append(item)

    return output


def clean_wix_dom(html):
    soup = BeautifulSoup(html or "", "lxml")

    remove_selectors = [
        "script",
        "style",
        "noscript",
        "iframe",
        "svg",
        "template",
        "header",
        "footer",
        "nav",
        ".cookie",
        ".popup",
        ".modal",
        ".newsletter",
        "[class*='cookie']",
        "[class*='popup']",
        "[class*='modal']"
    ]

    for selector in remove_selectors:
        for node in soup.select(selector):
            node.decompose()

    return soup


# -----------------------------
# SEO
# -----------------------------

def extract_basic_seo(soup, url):
    title = soup.title.get_text(" ") if soup.title else None

    desc = soup.select_one("meta[name='description']")
    canonical = soup.select_one("link[rel='canonical']")
    h1 = soup.select_one("h1")

    return {
        "title": clean_text(title),
        "metaDescription": clean_text(desc.get("content")) if desc else None,
        "canonical": normalize_url(canonical.get("href"), url) if canonical else None,
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
# PAGE CLASSIFICATION
# -----------------------------

def classify_general_page(url, seo, text):
    path = urlparse(url).path.lower()

    combined = (
        (seo.get("title") or "")
        + " "
        + (seo.get("h1") or "")
        + " "
        + path
        + " "
        + text[:4000]
    ).lower()

    if any(k in combined for k in [
        "about",
        "our story",
        "who we are",
        "mission",
        "artist"
    ]):
        return "about"

    if any(k in combined for k in [
        "contact",
        "get in touch",
        "email",
        "phone"
    ]):
        return "contact"

    if any(k in combined for k in [
        "service",
        "services",
        "offerings",
        "solutions"
    ]):
        return "services"

    if any(k in combined for k in [
        "faq",
        "frequently asked",
        "questions"
    ]):
        return "faq"

    if any(k in combined for k in [
        "privacy",
        "policy",
        "cookies"
    ]):
        return "privacyPolicy"

    if any(k in combined for k in [
        "terms",
        "conditions"
    ]):
        return "terms"

    if any(k in combined for k in [
        "portfolio",
        "projects",
        "gallery"
    ]):
        return "portfolio"

    return "general"


# -----------------------------
# GENERAL SUBTYPE DETECTION
# -----------------------------

_TOUR_SERVICE_KEYWORDS = [
    "what to expect", "duration", "pickup", "pick-up", "drop-off",
    "guided", "guide", "experience", "tour", "excursion", "activity",
    "itinerary", "stops", "included", "includes", "departure", "arrival",
    "bedouin", "safari", "sunset", "sunrise", "atv", "quad", "adventure",
    # additional tour indicators
    "book your tour", "book now", "reserve your spot",
]

_SERVICE_KEYWORDS = [
    "service", "consultation", "corporate", "workshop", "team building",
    "event", "application form", "request information",
    "book a", "request a call", "get quote", "free consultation",
    "how it works", "candle party", "candle parties",
    "hire us", "book us", "group booking",
]

_ABOUT_KEYWORDS = [
    "founder", "our story", "about us", "brand story", "mission",
    "who we are", "our team", "our history", "meet the team",
]

_TOOL_APP_KEYWORDS = [
    "app", "virtual try-on", "try on", "3d rendering", "real-time tracking",
    "augmented reality", "ar ", "safari mobile", "mobile device",
    "download the app", "available on", "platform requirements",
    "web app", "desktop app", "browser extension",
    "software", "platform", "dashboard",
]


def detect_general_subtype(url, seo, text):
    """
    Return a finer-grained subtype for general pages:
      - "tour_page": travel/activity booking with itinerary/pickup/guide signals
      - "service_page": workshop, corporate event, consultation, candle parties, etc.
      - "tool_app_page": product configurator, virtual try-on, AR, software
      - "about": founder/our story/brand story pages
      - None: no strong match
    """
    from urllib.parse import urlparse as _up
    path = _up(url).path.lower() if url else ""

    combined = (
        (seo.get("title") or "")
        + " " + (seo.get("h1") or "")
        + " " + (seo.get("metaDescription") or "")
        + " " + text[:6000]
        + " " + path
    ).lower()

    tour_hits = sum(1 for k in _TOUR_SERVICE_KEYWORDS if k in combined)
    tool_hits = sum(1 for k in _TOOL_APP_KEYWORDS if k in combined)
    service_hits = sum(1 for k in _SERVICE_KEYWORDS if k in combined)

    # tool_app_page checked before about — nav links like "our story" are common
    # on brand/product pages and must not suppress a clear tool_app signal
    if tool_hits >= 2:
        return "tool_app_page"

    if tour_hits >= 3:
        if any(k in combined for k in ["tour", "excursion", "atv", "quad", "safari",
                                        "bedouin", "itinerary", "stops"]):
            return "tour_page"
        return "service_page"

    # About page — requires keyword in title/H1 OR 2+ about keywords in body
    # (prevents nav-link "our story" from misclassifying product/tool pages)
    seo_combined = ((seo.get("title") or "") + " " + (seo.get("h1") or "")).lower()
    about_in_title = any(k in seo_combined for k in ["our story", "about us", "brand story", "founder"])
    about_hits = sum(1 for k in _ABOUT_KEYWORDS if k in combined)
    if about_in_title or about_hits >= 2:
        return "about"

    # Service page from dedicated service keywords (workshops, events, corporate, etc.)
    if service_hits >= 2:
        return "service_page"

    return None


# -----------------------------
# SERVICE / TOUR EXTRACTION
# -----------------------------

def extract_service_tour_data(soup, text, seo):
    """Extract structured fields from a tour or service page."""

    # serviceName from H1 or title
    h1 = soup.select_one("h1")
    service_name = clean_text(h1.get_text(" ")) if h1 else (seo.get("h1") or seo.get("title") or "")

    # Summary: meta description or first substantive paragraph
    summary = seo.get("metaDescription") or ""
    if not summary:
        for p in soup.find_all("p"):
            pt = clean_text(p.get_text(" "))
            if len(pt) >= 60:
                summary = pt[:500]
                break

    # Duration: look for patterns like "1.5hrs", "3 hours", "2-3 hours", "90 minutes"
    duration = None
    dur_match = re.search(
        r"(\d+(?:[.,]\d+)?\s*(?:hrs?|hours?|min(?:utes?)?)"
        r"|\d+\s*[-–]\s*\d+\s*(?:hrs?|hours?|min(?:utes?)?))",
        text, re.I
    )
    if dur_match:
        duration = clean_text(dur_match.group(0))

    # Includes: bullet list items under "includes", "what's included", "included"
    includes = []
    in_includes = False
    for li in soup.find_all("li"):
        li_text = clean_text(li.get_text(" "))
        prev = li.find_previous(["h1","h2","h3","h4","p","strong"])
        if prev:
            prev_text = clean_text(prev.get_text(" ")).lower()
            if any(k in prev_text for k in ["include", "what to expect", "you'll get", "what's"]):
                in_includes = True
        if in_includes and 3 <= len(li_text) <= 200:
            includes.append(li_text)
    # Fallback: any <li> items that look like inclusions
    if not includes:
        for li in soup.find_all("li"):
            li_text = clean_text(li.get_text(" "))
            if 10 <= len(li_text) <= 200:
                includes.append(li_text)
    includes = includes[:20]

    # Markdown fallback: when soup has no <li> (markdown-only mode), parse bullet lines
    if not includes and text:
        for line in text.splitlines():
            ls = line.strip()
            # Only real bullet items: '* text', '- text', '+ text'
            if ls and ls[0] in ('*', '-', '+') and len(ls) > 2 and ls[1] in (' ', '\t'):
                stripped = ls[1:].strip()
                if 10 <= len(stripped) <= 200:
                    includes.append(stripped)
        includes = includes[:20]

    # Pickup info
    pickup_info = None
    pick_match = re.search(
        r"(pick[- ]?up[^.]{0,120}(?:hotel|location|point|address|area)[^.]*\.?)",
        text, re.I
    )
    if pick_match:
        pickup_info = clean_text(pick_match.group(1))[:200]

    # Stops: look for stop/waypoint list items referencing locations
    stops = []
    for li in soup.find_all("li"):
        li_text = clean_text(li.get_text(" "))
        if any(k in li_text.lower() for k in ["stop", "cave", "tea", "view", "photo", "oasis"]):
            stops.append(li_text)
    stops = stops[:10]

    # Trust signals: ratings, reviews, guarantees
    trust_signals = []
    for pattern in [r"\d+(?:\.\d)?\s*(?:star|\/5|\/10)", r"\d[\d,]+\s*reviews?",
                    r"certified", r"safety", r"insured", r"licensed"]:
        m = re.search(pattern, text, re.I)
        if m:
            trust_signals.append(clean_text(m.group(0)))

    # Positioning
    positioning = None
    for h in soup.select("h2, h3"):
        ht = clean_text(h.get_text(" "))
        if any(k in ht.lower() for k in ["why choose", "why us", "what makes", "difference"]):
            sib = h.find_next_sibling()
            if sib:
                positioning = clean_text(sib.get_text(" "))[:300]
            break

    # CTA strategy
    cta_texts = []
    for node in soup.select("a[href], button"):
        ct = clean_text(node.get_text(" ")).lower()
        if any(k in ct for k in ["book", "reserve", "enquire", "contact", "whatsapp", "call"]):
            cta_texts.append(clean_text(node.get_text(" ")))
    cta_strategy = cta_texts[:5] if cta_texts else None

    return {
        "serviceName": service_name,
        "summary": summary[:500] if summary else None,
        "duration": duration,
        "includes": includes,
        "pickupInfo": pickup_info,
        "stops": stops if stops else None,
        "positioning": positioning,
        "trustSignals": trust_signals if trust_signals else None,
        "ctaStrategy": cta_strategy,
    }


# -----------------------------
# TOOL / APP EXTRACTION
# -----------------------------

def extract_tool_app_data(soup, text, seo):
    """Extract structured fields from a tool or app page."""

    # toolName
    h1 = soup.select_one("h1")
    tool_name = clean_text(h1.get_text(" ")) if h1 else (seo.get("h1") or seo.get("title") or "")

    # Summary
    summary = seo.get("metaDescription") or ""
    if not summary:
        for p in soup.find_all("p"):
            pt = clean_text(p.get_text(" "))
            if len(pt) >= 60:
                summary = pt[:500]
                break

    # targetAudience
    target_audience = None
    for h in soup.select("h2, h3"):
        ht = clean_text(h.get_text(" ")).lower()
        if any(k in ht for k in ["who is it for", "who can use", "designed for", "perfect for", "ideal for"]):
            sib = h.find_next_sibling()
            if sib:
                target_audience = clean_text(sib.get_text(" "))[:200]
            break

    # Features: bullet list items
    features = []
    for li in soup.find_all("li"):
        li_text = clean_text(li.get_text(" "))
        if 10 <= len(li_text) <= 200:
            features.append(li_text)
    features = features[:15]

    # Platform requirements
    platform_req = None
    plat_match = re.search(
        r"((?:requires?|works? (?:on|with)|compatible with|available (?:on|for))[^.]{0,150}\.)",
        text, re.I
    )
    if plat_match:
        platform_req = clean_text(plat_match.group(1))[:200]

    # Positioning
    positioning = None
    for h in soup.select("h2, h3"):
        ht = clean_text(h.get_text(" "))
        if any(k in ht.lower() for k in ["why choose", "why us", "what makes", "difference", "how it works"]):
            sib = h.find_next_sibling()
            if sib:
                positioning = clean_text(sib.get_text(" "))[:300]
            break

    # Trust signals
    trust_signals = []
    for pattern in [r"\d+(?:\.\d)?\s*(?:star|\/5|\/10)", r"\d[\d,]+\s*(?:users?|brands?|customers?|clients?)",
                    r"certified", r"secure", r"privacy"]:
        m = re.search(pattern, text, re.I)
        if m:
            trust_signals.append(clean_text(m.group(0)))

    return {
        "toolName": tool_name,
        "summary": summary[:500] if summary else None,
        "targetAudience": target_audience,
        "features": features if features else None,
        "platformRequirements": platform_req,
        "positioning": positioning,
        "trustSignals": trust_signals if trust_signals else None,
    }


# -----------------------------
# COLLECTION EVIDENCE GUARD
# -----------------------------

def _has_real_collection_evidence(soup, text):
    """
    Return True only if the page shows real collection/shop signals:
    - Prices present, OR
    - Filter/sort UI, OR
    - Pagination or load-more, OR
    - 3+ product-page links (product grid)
    """
    t = text.lower()
    has_prices = bool(re.search(r"[$\xa3€]\s?\d+", text))
    has_filter = ("filter by" in t or "sort by" in t)
    has_pagination = ("load more" in t or "?page=" in text or "/page/" in text)
    has_grid = len(soup.select("a[href*='/product-page/']")) >= 3
    return has_prices or has_filter or has_pagination or has_grid


# -----------------------------
# MAIN ANALYZE FUNCTION
# -----------------------------

def analyze_general(url, html, markdown=None):
    """
    Analyze a general (non-product, non-collection) Wix page.
    Supports both raw HTML and Jina markdown fallback.
    """
    raw_html = html or ""
    raw_text = markdown or ""

    # Build soup from HTML if available; otherwise stub from markdown
    if raw_html.strip():
        soup = clean_wix_dom(raw_html)
        main_text = clean_text(soup.get_text(" "))
    else:
        soup = BeautifulSoup("", "lxml")
        main_text = raw_text

    seo = extract_basic_seo(soup, url) if raw_html.strip() else {
        "title": None, "metaDescription": None, "canonical": None, "h1": None
    }

    # If markdown was provided but no H1 in soup, try to pull H1 from markdown
    if not seo.get("h1") and raw_text:
        m = re.search(r"^#\s+(.+)$", raw_text, re.MULTILINE)
        if m:
            seo["h1"] = clean_text(m.group(1))

    open_graph = extract_open_graph(soup) if raw_html.strip() else {}
    json_ld_items = extract_json_ld_items(soup) if raw_html.strip() else []

    # Use markdown text as body if HTML body is empty
    if not main_text.strip() and raw_text:
        main_text = raw_text

    page_label = classify_general_page(url, seo, main_text)
    general_subtype = detect_general_subtype(url, seo, main_text)

    # Content soup (no nav/header/footer) for structured extraction
    if raw_html.strip():
        content_soup = clean_wix_dom(raw_html)
    else:
        content_soup = soup

    service_data = None
    tool_data = None
    if general_subtype in ("tour_page", "service_page"):
        service_data = extract_service_tour_data(content_soup, main_text, seo)
    if general_subtype == "tool_app_page":
        tool_data = extract_tool_app_data(content_soup, main_text, seo)

    # Ecommerce signals - only flag products if real evidence exists
    # Tool/app pages are never ecommerce product pages even if their Jina
    # markdown contains filter/sort/load-more UI from an embedded catalog.
    if general_subtype == "tool_app_page":
        has_real_ecommerce = False
    else:
        has_real_ecommerce = _has_real_collection_evidence(content_soup, main_text)
    ecommerce_signals = {
        "hasEcommerceSignals": has_real_ecommerce,
        "hasProducts": has_real_ecommerce,
        "hasCartOrCheckout": False,
        "hasPricingInfo": bool(re.search(r"[$\xa3€]\s?\d+", main_text)),
    }

    general_page = {
        "pageLabel": page_label,
        "generalSubtype": general_subtype,
        "seo": seo,
        "openGraph": open_graph if open_graph else None,
        "jsonLd": json_ld_items if json_ld_items else None,
    }
    if service_data:
        general_page["serviceData"] = service_data
    if tool_data:
        general_page["toolData"] = tool_data

    result = {
        "success": True,
        "url": url,
        "platform": "Wix",
        "pageType": "general",
        "generalPage": general_page,
        "ecommerce": ecommerce_signals,
        # General pages have no collection/product data unless real ecommerce evidence exists
        "collection": None,
        "products": [],
        "featuredProducts": [],
    }

    return result
