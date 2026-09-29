from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urlunparse
import re
import json

from analyzers.pagination_helper import fetch_extra_pages


# ------------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------------

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
    cleaned = parsed._replace(query="", fragment="")
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


def _dollar_currency_from_url(url):
    """Delegate to shared currency utility."""
    from utils.currency import currency_from_url
    return currency_from_url(url) or "USD"


def normalize_price(raw, page_url=None):
    if not raw:
        return None
    raw = clean_text(raw)
    currency = None
    _rl = raw.lower()
    if "ca$" in _rl or (re.search(r'\bca\b', _rl) and "$" in raw):
        currency = "CAD"
    elif "a$" in _rl or "aud" in _rl:
        currency = "AUD"
    elif "£" in raw:
        currency = "GBP"
    elif "€" in raw:
        currency = "EUR"
    elif "aed" in _rl or "د.إ" in raw:
        currency = "AED"
    elif "sar" in _rl or "﷼" in raw:
        currency = "SAR"
    elif "inr" in _rl or "₹" in raw:
        currency = "INR"
    elif "pkr" in _rl or "₨" in raw or re.search(r'\brs\.?\b', _rl):
        currency = "PKR"
    elif "$" in raw:
        currency = _dollar_currency_from_url(page_url)
    match = re.search(r"(\d[\d,]*(?:\.\d{1,2})?)", raw)
    if not match:
        return {"raw": raw, "amount": None, "currency": currency}
    amount_str = match.group(1).replace(",", "")
    try:
        amount = float(amount_str)
    except Exception:
        amount = None
    # Zero-price guard
    if amount == 0.0:
        return {"raw": raw, "amount": None, "currency": currency}
    return {"raw": raw, "amount": amount, "currency": currency}


# ------------------------------------------------------------------
# JINA PLACEHOLDER DETECTION
# ------------------------------------------------------------------

def _is_jina_placeholder(text):
    """Return True if text is a Jina Reader auto-generated image alt."""
    if not text:
        return False
    t = text.strip()
    if re.match(r'^image\s*\d+', t, re.IGNORECASE):
        return True
    if re.search(r'\.(jpg|jpeg|png|webp|gif|svg)(\s*$|:)', t, re.IGNORECASE):
        return True
    if re.match(r'^thumbnail_', t, re.IGNORECASE):
        return True
    return False


def _slug_to_title(url_str):
    """Derive a human-readable label from the last non-empty path segment."""
    if not url_str:
        return None
    slug = urlparse(url_str).path.rstrip("/").split("/")[-1]
    if not slug:
        return None
    return slug.replace("-", " ").replace("_", " ").title()


def _strip_site_name(text):
    """Strip '| Site Name' suffix from title-like strings."""
    return re.sub(r"\s*\|\s*.+$", "", text or "").strip()


# ------------------------------------------------------------------
# BADGE / AVAILABILITY HELPERS
# ------------------------------------------------------------------

# Ordered from most specific to least — first match wins
_BADGE_PATTERNS = [
    (r"brand\s+new!", "BRAND NEW!"),
    (r"back\s+for\s+pride!", "Back for Pride!"),
    (r"fresh\s+for\s+spring!", "Fresh for Spring!"),
    (r"new\s+release", "New Release"),
    (r"new\s+arrival", "New Arrival"),
    (r"new!", "NEW!"),
    (r"\bnew\b", "NEW"),
    (r"ready\s+to\s+ship", "Ready to ship"),
    (r"in\s+stock", "In Stock"),
    (r"out\s+of\s+stock", "Out of Stock"),
    (r"sold\s+out", "Sold Out"),
    (r"\bsale\b", "Sale"),
]


def _extract_badge(text):
    """Extract first matching badge label from text."""
    if not text:
        return None
    for pattern, label in _BADGE_PATTERNS:
        if re.search(pattern, text, re.I):
            return label
    return None


def _availability_from_context(context_text):
    """Derive availability from parent <li> or nearby text."""
    if not context_text:
        return "unknown"
    t = context_text.lower()
    if "out of stock" in t or "sold out" in t:
        return "out_of_stock"
    if "add to cart" in t or "in stock" in t or "ready to ship" in t:
        return "in_stock"
    return "unknown"


# ------------------------------------------------------------------
# DOM CLEANING
# ------------------------------------------------------------------

def clean_wix_dom(html):
    soup = BeautifulSoup(html or "", "lxml")
    remove_selectors = [
        "script", "style", "noscript", "iframe", "svg", "template",
        "header", "footer", "nav",
        "[data-testid='mesh-container-content'] script",
        ".cookie", ".popup", ".modal",
        "[class*='cookie']", "[class*='popup']", "[class*='modal']"
    ]
    for selector in remove_selectors:
        for node in soup.select(selector):
            node.decompose()
    return soup


# ------------------------------------------------------------------
# SEO / META / OPEN GRAPH / JSON-LD
# ------------------------------------------------------------------

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


# ------------------------------------------------------------------
# WIX DETECTION
# ------------------------------------------------------------------

def detect_wix_collection_signals(url, soup):
    text = clean_text(soup.get_text(" ")).lower()
    html_lower = str(soup).lower()
    path = urlparse(url).path.lower()

    signals = []
    if "wix" in html_lower or "wixstatic.com" in html_lower:
        signals.append("wix_platform")
    if "wixstores" in html_lower or "wix-ecommerce" in html_lower:
        signals.append("wix_store_signal")
    if any(k in path for k in ["/shop", "/store", "/category", "/collection", "/collections"]):
        signals.append("collection_url")
    if any(k in text for k in ["quick view", "add to cart", "shop", "price", "sort by"]):
        signals.append("shop_text")
    if re.search(r"(price\s*)?[$£€]\s?\d+", text, re.I):
        signals.append("price_text")
    if "filter by" in text and "sort by" in text:
        signals.append("filter_sort_ui")

    return {
        "isLikelyCollection": len(signals) >= 2,
        "signals": signals
    }


# ------------------------------------------------------------------
# PRODUCT CARD EXTRACTION
# ------------------------------------------------------------------

# Nav/UI strings that should never be treated as product names
_PRODUCT_NAME_BLOCKLIST = {
    "quick view", "view", "add to cart", "buy now", "shop now",
    "new", "sale", "featured", "home", "back", "next", "previous",
    "more", "load more", "show more", "sort by", "filter",
    "in stock", "out of stock", "sold out"
}


def _clean_product_name(raw):
    """Strip common prefixes/suffixes from extracted product name text."""
    name = clean_text(raw or "")
    # Remove Jina placeholder patterns at start
    name = re.sub(r"^image\s*\d+[:\s]*", "", name, flags=re.IGNORECASE)
    name = re.sub(r"^(new!\s*)?(quick view\s*)?", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\bprice\b", "", name, flags=re.IGNORECASE)
    # Fine Frenchie "* * *" decorative separator — strip it and everything after
    name = re.sub(r"\s*\*\s*\*\s*\*\s*.*$", "", name)
    # Strip trailing availability status (e.g. "Classic French Market Basket Out of stock")
    name = re.sub(r"\s+(out\s+of\s+stock|sold\s+out|unavailable)\s*$", "", name, flags=re.IGNORECASE)
    name = _strip_site_name(name)
    return clean_text(name)


def _is_valid_product_name(name):
    if not name or len(name) < 3 or len(name) > 160:
        return False
    if _is_jina_placeholder(name):
        return False
    if name.lower() in _PRODUCT_NAME_BLOCKLIST:
        return False
    # All-digits or only punctuation
    if re.match(r'^[\d\s\W]+$', name):
        return False
    return True


def extract_products_from_links(soup, base_url):
    """
    Extract products from anchor tags that contain a price signal.
    Works well for Wix Jina-rendered pages:
      <li><a href="url"><img/> Quick View NEW!</a><a href="url">Name Price$40.00</a> Add to Cart</li>
    Also extracts badge and availability from the parent <li> context.
    A second pass captures out-of-stock /product-page/ links without prices.
    """
    products = []

    for a in soup.select("a[href]"):
        text = clean_text(a.get_text(" "))
        href = a.get("href")
        if not text or not href:
            continue

        # Must contain a price signal
        if "price" not in text.lower() and not re.search(r"[$£€]\s?\d+", text):
            continue

        if len(text) > 300:
            continue

        price_match = re.search(
            r"(?:(?:sale|regular)\s+)?price\s*((?:ca\$|[$£€])\s?\d+(?:[,.]\d{1,2})?)"
            r"|"
            r"((?:ca\$|[$£€])\s?\d+(?:[,.]\d{1,2})?)",
            text, re.I
        )
        if not price_match:
            continue

        price = clean_text(price_match.group(1) or price_match.group(2))
        name_raw = text[:price_match.start()]
        name = _clean_product_name(name_raw)

        if not _is_valid_product_name(name):
            # Try deriving from URL slug
            name = _slug_to_title(href) or ""
            if not _is_valid_product_name(name):
                continue

        # Badge and availability from parent <li> context
        badge = None
        availability = "unknown"
        parent_li = a.find_parent("li")
        if parent_li:
            li_text = clean_text(parent_li.get_text(" "))
            badge = _extract_badge(li_text)
            availability = _availability_from_context(li_text)

        products.append({
            "name": name,
            "url": normalize_url(href, base_url),
            "price": price,
            "priceNormalized": normalize_price(price, page_url=base_url),
            "image": None,
            "badge": badge,
            "availability": availability,
        })

    seen_urls = {p["url"] for p in products}

    # Second pass: /product-page/ links with no price but "out of stock" / "sold out" nearby.
    # Wix renders out-of-stock cards as: [Name](url) followed by "Out of Stock" text (no price shown).
    for a in soup.select("a[href*='/product-page/']"):
        href = a.get("href", "")
        norm_href = normalize_url(href, base_url)
        if norm_href in seen_urls:
            continue

        text = clean_text(a.get_text(" "))
        # Skip image-only / quick-view / very long anchors
        if not text or len(text) > 200:
            continue
        if re.search(r"[$£€]\s?\d+|price", text, re.I):
            continue  # already captured in main pass
        if re.search(r"quick\s*view|^\s*image\s", text, re.I):
            continue

        name = _clean_product_name(text)
        if not _is_valid_product_name(name):
            name = _slug_to_title(href) or ""
            if not _is_valid_product_name(name):
                continue

        # Check for out-of-stock signal in nearby context (next sibling text or parent <li>)
        availability = "unknown"
        parent_li = a.find_parent("li")
        if parent_li:
            li_text = clean_text(parent_li.get_text(" "))
            availability = _availability_from_context(li_text)
        if availability == "unknown":
            # Walk next siblings in parent paragraph/div for OOS text
            parent = a.parent
            if parent:
                siblings_text = " ".join(
                    clean_text(s.get_text(" ") if hasattr(s, "get_text") else str(s))
                    for s in list(a.next_siblings)[:6]
                ).lower()
                if re.search(r"out of stock|sold out|unavailable", siblings_text):
                    availability = "out_of_stock"

        if availability != "out_of_stock":
            continue  # only include no-price items if we can confirm OOS

        products.append({
            "name": name,
            "url": norm_href,
            "price": None,
            "priceNormalized": None,
            "image": None,
            "badge": "Out of Stock",
            "availability": "out_of_stock",
        })
        seen_urls.add(norm_href)

    return unique_items(products, "url")[:80]


def extract_products_from_wix_catalog_links(soup, base_url, current_url=None):
    """
    Extract products from /collection/{slug} links with no price signal.
    Used for Wix B2B catalog-style pages (e.g. OGI /seraphin brand listing).
    Each product appears as a /collection/{slug} link — no cart, no price.
    """
    products = []
    bad_terms = ["/cart", "/checkout", "mailto:", "tel:", "/blog"]

    for li in soup.find_all("li"):
        # Collect /collection/{slug} links in this <li>
        coll_anchors = []
        for a in li.find_all("a", href=True):
            href = a.get("href", "")
            if (
                re.search(r"/collection/[^/?#]+", href, re.I)
                and "/collections/" not in href.lower()
                and not any(b in href.lower() for b in bad_terms)
            ):
                coll_anchors.append(a)

        if not coll_anchors:
            continue

        # Find the text-only anchor (product name link, not image link)
        name_link = None
        for a in coll_anchors:
            txt = clean_text(a.get_text(" "))
            if txt and not _is_jina_placeholder(txt) and len(txt) >= 2 and a.find("img") is None:
                name_link = a
                break
        # Fallback: any anchor with non-placeholder text
        if not name_link:
            for a in coll_anchors:
                txt = clean_text(a.get_text(" "))
                if txt and not _is_jina_placeholder(txt) and len(txt) >= 2:
                    name_link = a
                    break

        if not name_link:
            continue

        raw_name = clean_text(name_link.get_text(" "))
        name = _clean_product_name(raw_name)
        if not _is_valid_product_name(name):
            name = _slug_to_title(name_link.get("href")) or ""
        if not _is_valid_product_name(name):
            continue

        href = name_link.get("href", "")
        url = normalize_url(href, base_url)

        # Grab first image from the <li>
        image = None
        for img in li.find_all("img"):
            src = img.get("src") or img.get("data-src")
            if src and not src.startswith("data:"):
                image = normalize_url(src, base_url)
                break

        li_text = clean_text(li.get_text(" "))
        badge = _extract_badge(li_text)

        products.append({
            "name": name,
            "url": url,
            "price": None,
            "priceNormalized": None,
            "image": image,
            "badge": badge,
            "availability": "unknown",
        })

    return unique_items(products, "url")[:80]


def extract_products_from_text_blocks(soup, base_url):
    """
    Fallback: scan full page text for "Product Name Price $X.XX" pattern.
    """
    products = []
    text = clean_text(soup.get_text(" "))

    pattern = re.compile(
        r"(?:New!\s*)?(?:Quick View\s*)?(.{3,120}?)\s+(?:Sale\s+|Regular\s+)?Price\s+((?:CA\$|[$£€])\s?\d+(?:[,.]\d{1,2})?)",
        re.I
    )

    for match in pattern.finditer(text):
        name = _clean_product_name(match.group(1))
        price = clean_text(match.group(2))

        if not _is_valid_product_name(name):
            continue

        products.append({
            "name": name,
            "url": None,
            "price": price,
            "priceNormalized": normalize_price(price, page_url=base_url),
            "image": None,
            "badge": None,
            "availability": "unknown",
        })

    return products[:80]


def attach_images_to_products(products, soup, base_url):
    """
    Match product images by alt text similarity.
    Skips Jina placeholder alts and uses slug fallback.
    """
    images = []

    for img in soup.select("img"):
        src = (
            img.get("data-src")
            or img.get("data-lazy-src")
            or img.get("src")
        )
        if not src or src.startswith("data:image"):
            continue

        alt = clean_text(img.get("alt"))
        # Ignore Jina placeholder alts for matching purposes
        if _is_jina_placeholder(alt):
            alt = None

        images.append({"url": normalize_url(src, base_url), "alt": alt or ""})

    for product in products:
        if product.get("image"):
            continue
        product_name = product.get("name", "").lower()
        for image in images:
            alt = image.get("alt", "").lower()
            if not alt:
                continue
            if (
                product_name in alt
                or alt in product_name
                or any(word in alt for word in product_name.split()[:3])
            ):
                product["image"] = image["url"]
                break

    return products


def extract_wix_products(soup, base_url, use_catalog_links=False):
    """
    Main product extraction entry point.

    Extraction order:
    1. If >5 /collection/{slug} links exist (Wix B2B catalog style, e.g. OGI /seraphin):
       try catalog extraction FIRST, then fall back to price-based.
    2. Otherwise: try price-based extraction first (standard Wix store with /product-page/ links),
       then catalog extraction (if use_catalog_links=True).
    3. Final fallback: text-block pattern extraction.

    This order ensures that B2B catalog pages populate products[] from the actual
    /collection/ item links rather than from a generic "featured product" heuristic.
    """
    # Count unique /collection/{slug} links (not /collections/)
    collection_link_count = sum(
        1 for a in soup.find_all("a", href=True)
        if re.search(r"/collection/[^/?#]+", a.get("href", ""), re.I)
        and "/collections/" not in (a.get("href", "") or "").lower()
    )

    if collection_link_count > 5:
        # B2B catalog pattern: >5 /collection/ links → extract catalog items first
        products = extract_products_from_wix_catalog_links(soup, base_url)
        if not products:
            products = extract_products_from_links(soup, base_url)
    else:
        # Standard store pattern: price-based extraction first
        products = extract_products_from_links(soup, base_url)
        if not products and use_catalog_links:
            products = extract_products_from_wix_catalog_links(soup, base_url)

    if not products:
        products = extract_products_from_text_blocks(soup, base_url)

    products = attach_images_to_products(products, soup, base_url)
    return unique_items(products, "name")[:80]


# ------------------------------------------------------------------
# CATEGORY / NAV LINKS
# ------------------------------------------------------------------

# URL path segments that strongly indicate a category/collection page
_CATEGORY_PATH_SEGMENTS = {
    "shop", "store", "category", "categories", "collection", "collections",
    "product-category", "catalog", "browse", "department"
}

# Text keywords that indicate a navigation category
_CATEGORY_TEXT_KEYWORDS = [
    "shop", "store", "collection", "collections", "category",
    "prints", "coloring pages", "external vendors", "specialty gifts",
    "fabric", "fabrics", "clothing", "dresses", "shirts", "socks",
    "jewellery", "ceramics", "textile", "cards", "stationery",
    "decor", "home", "furniture", "accessories", "bags", "shoes",
    "art", "gifts", "sale", "new arrivals", "featured",
    "kitchen", "bath", "outdoor", "tools", "electronics", "beauty",
    "food", "toys", "sports", "books", "music", "pets",
]

# Exclude pure nav words (no category meaning by themselves)
_CATEGORY_EXCLUDE_EXACT = {
    "home", "about", "contact", "faq", "search", "login",
    "sign up", "sign in", "register", "cart", "checkout",
    "account", "blog", "news", "press", "privacy", "terms",
    "cookie", "back", "next", "previous"
}


def extract_category_links(soup, base_url):
    """
    Extract category/collection links from a Wix shop/collection page.
    """
    categories = []
    base_host = urlparse(base_url).netloc if base_url else ""

    for a in soup.select("a[href]"):
        text = clean_text(a.get_text(" "))
        href = a.get("href")
        if not text or not href:
            continue

        # Skip Jina placeholder link texts
        if _is_jina_placeholder(text):
            continue

        if len(text) > 100:
            continue

        text_lower = text.lower().strip()

        # Skip pure nav / UI words
        if text_lower in _CATEGORY_EXCLUDE_EXACT:
            continue

        url = normalize_url(href, base_url)
        if not url:
            continue

        parsed = urlparse(url)
        path_lower = parsed.path.lower()
        path_segments = set(s for s in path_lower.strip("/").split("/") if s)

        # Skip external links
        if parsed.netloc and parsed.netloc != base_host:
            continue

        # Accept if path contains a category segment
        path_is_category = bool(path_segments & _CATEGORY_PATH_SEGMENTS)

        # Accept if text matches a category keyword
        text_is_category = any(k in text_lower for k in _CATEGORY_TEXT_KEYWORDS)

        if path_is_category or text_is_category:
            categories.append({"text": text, "url": url})

    return unique_items(categories, "url")[:60]


# ------------------------------------------------------------------
# FILTER EXTRACTION
# ------------------------------------------------------------------

def extract_collection_filters(page_text, soup=None, page_url=None):
    """
    Extract filter categories and price range from Wix collection pages.
    Works on Jina markdown text (filter UI labels appear verbatim in page text).
    Returns: {"category": [...], "priceRange": {"min": N, "max": N, "currency": "CAD"}}
    """
    filters = {}
    text = page_text or ""

    # ------ Category list ------
    # Wix Jina markdown: "Filter by Category Citrus Candles (9) Gourmand Candles (9) Price ..."
    cat_match = re.search(
        r"filter\s+by[\s\S]{0,80}?category\s+((?:[A-Za-z][\w\s&'`\-]+?(?:\s*\(\d+\))?\s*)+?)(?:price|sort\s+by|\Z)",
        text, re.I | re.DOTALL
    )
    if cat_match:
        cat_block = cat_match.group(1)
        categories = []

        if re.search(r"\(\d+\)", cat_block):
            # Items have count suffixes: "Citrus Candles (9) Gourmand (5) …"
            raw_cats = re.split(r"\s*\(\d+\)\s*", cat_block)
            for c in raw_cats:
                c = clean_text(c)
                if len(c) >= 3:
                    categories.append(c)
        else:
            # No count suffixes — items may be separated by "* " (indented Jina markdown)
            # or just by capitalised word boundaries.
            # Split on the literal asterisk bullets kept in page_text from indented markdown.
            parts = re.split(r"\*\s+", cat_block)
            for part in parts:
                c = clean_text(part)
                # Skip generic/nav words
                if c.lower() in {"all", "any", "none", "other", ""}:
                    continue
                if len(c) >= 3:
                    categories.append(c)

        if categories:
            filters["category"] = categories[:20]

    # ------ Price range ------
    # Patterns: "Price CA$25 CA$60", "$25 - $60", "Price Range: $25–$60", etc.
    pr_match = re.search(
        r"price(?:\s+range)?\s*[:\-]?\s*"
        r"(?:ca\s*\$|cad\s*\$?|[$£€])\s*(\d+(?:\.\d{1,2})?)"
        r"\s*[-–to]+\s*"
        r"(?:ca\s*\$|cad\s*\$?|[$£€])\s*(\d+(?:\.\d{1,2})?)",
        text, re.I
    )
    if not pr_match:
        # Two CA$/$ amounts near the word "price"
        pr_match = re.search(
            r"price[\s\S]{0,120}?"
            r"(?:ca\s*\$|cad\s*\$?|[$£€])\s*(\d+(?:\.\d{1,2})?)"
            r"[\s\S]{0,60}?"
            r"(?:ca\s*\$|cad\s*\$?|[$£€])\s*(\d+(?:\.\d{1,2})?)",
            text, re.I
        )

    if pr_match:
        try:
            min_val = float(pr_match.group(1))
            max_val = float(pr_match.group(2))
            if min_val > max_val:
                min_val, max_val = max_val, min_val
            # Detect currency
            if re.search(r"ca\s*\$|cad", text, re.I):
                currency = "CAD"
            elif "£" in text:
                currency = "GBP"
            elif "€" in text:
                currency = "EUR"
            elif re.search(r"\bpkr\b|₨", text, re.I):
                currency = "PKR"
            elif re.search(r"\binr\b|₹", text, re.I):
                currency = "INR"
            elif re.search(r"\baed\b|د\.إ", text, re.I):
                currency = "AED"
            elif re.search(r"\bsar\b|﷼", text, re.I):
                currency = "SAR"
            elif "$" in text:
                currency = _dollar_currency_from_url(page_url)
            else:
                currency = None
            filters["priceRange"] = {
                "min": min_val,
                "max": max_val,
                "currency": currency
            }
        except (ValueError, TypeError):
            pass

    return filters


# ------------------------------------------------------------------
# COLLECTION DESCRIPTION
# ------------------------------------------------------------------

_BAD_COLLECTION_DESCRIPTIONS = {
    "use tab to navigate through the menu items",
    "load more",
    "shop",
    "more",
    "skip to main content",
    "back to top",
    "top of page",
    "filter by",
    "sort by",
    "add to cart",
    "add to bag",
}


def _is_bad_description(text):
    """Return True if the text is navigation/UI junk, not a real description."""
    t = text.lower().strip()
    if t in _BAD_COLLECTION_DESCRIPTIONS:
        return True
    # Starts with a known nav phrase
    for bad in _BAD_COLLECTION_DESCRIPTIONS:
        if t.startswith(bad):
            return True
    # Pure URL / price / symbol
    if re.match(r'^[$£€\d#*/\\]', t):
        return True
    # Bare markdown link syntax: [text](url) or [](url)  — raw markdown not converted to HTML
    if re.match(r'^\[.*?\]\(https?://', text.strip()):
        return True
    # Standalone URL
    if re.match(r'^https?://', text.strip()):
        return True
    return False


def extract_collection_description(soup, page_text=None):
    """Extract first substantive text paragraph from a collection page."""
    # Try <p> tags first
    for p in soup.find_all("p"):
        text = clean_text(p.get_text(" "))
        if len(text) >= 40 and not _is_bad_description(text):
            return text[:500]

    # Fallback: first long line in page text that looks like a description
    for line in (page_text or "").split("\n"):
        line = line.strip()
        if len(line) >= 40 and not _is_bad_description(line):
            return line[:500]

    return None


# ------------------------------------------------------------------
# PAGE CONTENT
# ------------------------------------------------------------------

def extract_collection_content(soup, base_url):
    main = soup.select_one("main") or soup.body or soup
    headings = []
    for h in main.select("h1, h2, h3"):
        text = clean_text(h.get_text(" "))
        if text and len(text) <= 160:
            headings.append({"level": h.name, "text": text})

    sections = []
    for node in main.select("section, article"):
        text = clean_text(node.get_text(" "))
        if len(text) < 40:
            continue
        heading = None
        h = node.select_one("h1, h2, h3")
        if h:
            heading = clean_text(h.get_text(" "))
        sections.append({"heading": heading, "text": text[:1800]})

    links = []
    for a in main.select("a[href]"):
        text = clean_text(a.get_text(" "))
        href = a.get("href")
        if not text or not href or len(text) > 140:
            continue
        if _is_jina_placeholder(text):
            continue
        links.append({"text": text, "url": normalize_url(href, base_url)})

    images = []
    for img in main.select("img"):
        src = (
            img.get("data-src")
            or img.get("data-lazy-src")
            or img.get("src")
        )
        if not src or src.startswith("data:image"):
            continue
        alt = clean_text(img.get("alt"))
        if _is_jina_placeholder(alt):
            alt = _slug_to_title(src) or None
        images.append({"url": normalize_url(src, base_url), "alt": alt})

    return {
        "pageTitle": None,
        "headings": headings[:40],
        "sections": sections[:35],
        "links": unique_items(links, "url")[:80],
        "images": unique_items(images, "url")[:50],
        "mainText": clean_text(main.get_text(" "))[:15000]
    }


# ------------------------------------------------------------------
# PAGINATION
# ------------------------------------------------------------------

def detect_pagination_or_load_more(soup, base_url, page_text=None):
    """
    Detect pagination and Load More patterns.
    Checks both link text and ?page= query strings in hrefs.
    """
    page_links = []
    load_more_detected = False
    pagination_detected = False

    for a in soup.select("a[href]"):
        text = clean_text(a.get_text(" "))
        href = a.get("href", "")

        # ?page= in href (Fine Frenchie: /collectibles?page=2)
        if re.search(r"[?&]page=\d+", href):
            page_links.append({
                "text": text or "page",
                "url": normalize_url(href, base_url)
            })
            pagination_detected = True
        elif text.lower() in ["next", "previous", "load more", "show more", "more"]:
            page_links.append({
                "text": text,
                "url": normalize_url(href, base_url)
            })

    text_lower = (page_text or clean_text(soup.get_text(" "))).lower()
    if "load more" in text_lower or "show more" in text_lower:
        load_more_detected = True

    detected = pagination_detected or load_more_detected or bool(page_links)

    return {
        "detected": detected,
        "paginationDetected": pagination_detected,
        "loadMoreDetected": load_more_detected,
        "pageLinks": unique_items(page_links, "url")[:20]
    }


# ------------------------------------------------------------------
# BRAND / COLLECTION NAME HELPERS
# ------------------------------------------------------------------

def _extract_brand(seo, open_graph, url, collection_name=None, is_brand_collection=False):
    """
    Derive brand name for a collection page.
    Priority: og:site_name → title "| Brand" suffix → collectionName for brand_collection → domain slug.
    """
    # og:site_name
    site_name = open_graph.get("site_name") or open_graph.get("site-name")
    if site_name and len(site_name) >= 2:
        return clean_text(site_name)

    # "| Brand" from title
    title = seo.get("title") or ""
    parts = re.split(r"\s*\|\s*", title)
    if len(parts) >= 2:
        candidate = parts[-1].strip()
        if 2 <= len(candidate) <= 60:
            return candidate

    # For brand-listing pages (e.g. OGI /seraphin), the collection name IS the brand
    if is_brand_collection and collection_name and len(collection_name) >= 2:
        return collection_name

    # Domain slug fallback: "opticalgroup.com" → "Opticalgroup" (skip generic TLDs)
    try:
        host = urlparse(url).netloc.lower().lstrip("www.")
        domain_name = host.split(".")[0]
        if domain_name and len(domain_name) >= 3 and domain_name not in {
            "shop", "store", "buy", "get", "my", "the", "best"
        }:
            return domain_name.replace("-", " ").title()
    except Exception:
        pass

    return None


def _extract_collection_name(seo, open_graph):
    """Derive clean collection name from SEO metadata."""
    candidates = [
        seo.get("h1"),
        open_graph.get("title"),
        seo.get("title"),
    ]
    for c in candidates:
        if c:
            name = _strip_site_name(clean_text(c))
            if name and len(name) >= 2:
                return name
    return None


# ------------------------------------------------------------------
# COLLECTION TYPE DETECTION
# ------------------------------------------------------------------

def _detect_collection_type(products, page_text, level1_signals=None):
    """
    Classify the collection type:
      - "brand_collection": B2B catalog / brand listing with no prices (OGI /seraphin)
      - "product_collection": standard shop/category with prices + cart
      - "mixed": has both catalog links and priced products
    """
    l1 = level1_signals or []
    has_prices = any(p.get("price") for p in products)
    has_catalog_links = "wix_collection_product_links" in l1

    if has_catalog_links and not has_prices:
        return "brand_collection"
    if has_prices:
        return "product_collection"
    if has_catalog_links:
        return "mixed"
    return "product_collection"


# ------------------------------------------------------------------
# MAIN ANALYZER
# ------------------------------------------------------------------

def analyze_wix_collection(self, url, html, headers, page_type, level1):
    result = self.base_result(url, html, headers, page_type, level1)

    raw_soup = BeautifulSoup(html or "", "lxml")
    content_soup = clean_wix_dom(html)

    result["source"]["extractor"] = "Wix Collection Extractor"

    seo = extract_basic_seo(raw_soup, url)
    open_graph = extract_open_graph(raw_soup)
    json_ld_items = extract_json_ld_items(raw_soup)

    # Level1 signals from the page_type_detector (passed in level1 dict)
    l1_signals = []
    if isinstance(level1, dict):
        l1_signals = (
            level1.get("signals", [])
            or level1.get("pageTypeDebug", {}).get("signals", {}).keys()
        )
        # Also check nested structure
        if not l1_signals:
            for k in ["collectionSignals", "collection"]:
                sub = level1.get(k, {})
                if isinstance(sub, dict):
                    l1_signals = sub.get("signals", [])
                    if l1_signals:
                        break
    l1_signals = list(l1_signals)

    # Decide whether to try B2B catalog extraction (no-price /collection/ links)
    use_catalog = "wix_collection_product_links" in l1_signals

    page_text = clean_text(raw_soup.get_text(" "))

    products = extract_wix_products(content_soup, url, use_catalog_links=use_catalog)
    categories = extract_category_links(raw_soup, url)
    collection_signals = detect_wix_collection_signals(url, raw_soup)
    content = extract_collection_content(content_soup, url)
    pagination = detect_pagination_or_load_more(content_soup, url, page_text)

    # Follow numeric pagination and merge products from remaining pages. NOTE:
    # most Wix stores paginate via JavaScript/infinite-scroll with no fetchable
    # page URLs, so this is a no-op there (it only helps Wix sites that expose
    # real /page/N/-style links). JS pagination would need a rendered crawl.
    _extra_products, _fetched_all_pages = fetch_extra_pages(
        url,
        content_soup,
        lambda h, u: extract_wix_products(BeautifulSoup(h or "", "lxml"), u, use_catalog_links=use_catalog),
    )
    if _extra_products:
        products = unique_items(products + _extra_products, "url")
    if isinstance(pagination, dict):
        pagination["fullCatalogFetched"] = _fetched_all_pages

    # Collection name + brand
    collection_name = _extract_collection_name(seo, open_graph)
    collection_type = _detect_collection_type(products, page_text, l1_signals)
    is_brand_collection = collection_type == "brand_collection"
    brand = _extract_brand(seo, open_graph, url, collection_name, is_brand_collection)

    # Description
    description = extract_collection_description(content_soup, page_text)

    # Filters (category list + price range)
    filters = extract_collection_filters(page_text, content_soup, page_url=url)

    content["pageTitle"] = collection_name

    # Require strong transactional signals — not bare "cart"/"price" which
    # match Wix nav links ("Cart", "Gift Cards") and any price display.
    _pt_lower = page_text.lower()
    has_cart_or_checkout = any(
        k in _pt_lower
        for k in [
            "add to cart", "add to bag", "add to basket",
            "buy now", "quick buy",
            "proceed to checkout", "go to checkout",
            "view cart", "your cart",
        ]
    )

    has_product_grid = len(products) >= 2

    # ------------------------------------------------------------------
    # Single-product /collection/{slug} fallback (e.g. OGI /collection/fillia)
    # When no product grid or product links are found but the page itself
    # describes one product (has attribute selectors or product-info sections),
    # treat the current page as a single product in this collection.
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # When no product grid or product links are found but the page itself
    # describes one product (has attribute selectors or product-info sections),
    # treat the current page as a single product in this collection.
    # ------------------------------------------------------------------
    if not products and collection_name:
        _page_text_l = page_text.lower()
        _has_product_attrs = bool(re.search(
            r"\b(?:Color|Colour|Material|Shape|Size|Brand|Style|Collection)\s*\*",
            page_text, re.I
        ))
        _has_product_info = any(
            term in _page_text_l
            for term in [
                "product info", "find a store", "virtual try-on",
                "find a retailer", "product details", "materials", "features"
            ]
        )
        if _has_product_attrs or _has_product_info:
            single_product = {
                "name": collection_name,
                "url": url,
                "price": None,
                "priceNormalized": None,
                "image": None,
                "badge": None,
                "availability": "unknown",
            }
            products = attach_images_to_products([single_product], content_soup, url)

    has_product_grid = len(products) >= 2

    # Sample prices for competitive_schema
    sample_prices = [
        p["price"] for p in products
        if p.get("price")
    ][:10]

    # ------------------------------------------------------------------
    # Catalog-mode detection
    # When ALL products lack prices AND all URLs are /collection/ slugs
    # (no /product-page/), this is a B2B catalog / brand-listing page,
    # not a direct-purchase collection.  Stamp each item with
    # itemType="catalog_item" and set catalogMode=True on the collection.
    # ------------------------------------------------------------------
    has_any_price = any(p.get("price") for p in products)
    all_collection_urls = bool(products) and all(
        "/collection/" in (p.get("url") or "") for p in products
    )
    has_product_page_urls = any(
        "/product-page/" in (p.get("url") or "") for p in products
    )
    catalog_mode = (
        not has_any_price
        and len(products) > 5
        and all_collection_urls
        and not has_product_page_urls
    )
    if catalog_mode:
        for p in products:
            p.setdefault("itemType", "catalog_item")

    result["seo"] = seo
    result["openGraph"] = open_graph

    result["collection"] = {
        "title": collection_name,
        "collectionName": collection_name,
        "collectionType": collection_type,
        "brand": brand,
        "description": description,
        "productsCount": len(products),
        "products": products,
        "categoryLinks": categories,
        "filters": filters,
        "pagination": pagination,
        "paginationDetected": pagination.get("paginationDetected", False),
        "loadMoreDetected": pagination.get("loadMoreDetected", False),
        "signals": collection_signals,
        "samplePrices": sample_prices,
        "catalogMode": catalog_mode,
        "hasPricing": has_any_price,
    }

    result["ecommerce"] = {
        "hasEcommerceSignals": bool(products) or collection_signals["isLikelyCollection"],
        "featuredProductsCount": len(products),
        "featuredProducts": products[:50],
        "categoryLinks": categories,
        "hasProductGrid": has_product_grid,
        "hasCategories": bool(categories),
        "hasCartOrCheckout": has_cart_or_checkout,
        "samplePrices": sample_prices,
    }

    result["products"] = products

    result["content"] = content

    result["structuredData"] = {
        "jsonLdCount": len(json_ld_items),
        "items": json_ld_items[:20]
    }

    # Quality / confidence score
    confidence = 0.45
    if products:
        confidence += 0.25
    if len(products) >= 3:
        confidence += 0.10
    if any(p.get("price") for p in products):
        confidence += 0.05
    if collection_signals["isLikelyCollection"]:
        confidence += 0.05
    if collection_name:
        confidence += 0.05
    if categories:
        confidence += 0.03
    if description:
        confidence += 0.02

    result["source"]["confidence"] = round(min(max(confidence, 0.35), 0.95), 2)

    return result
