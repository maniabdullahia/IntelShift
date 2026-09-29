from bs4 import BeautifulSoup
import json  # noqa: F401
import re
from urllib.parse import urlparse


# =========================================================
# Image URL filter constants
# =========================================================

# Tracking / analytics / beacon URLs — never real product images
_IMAGE_TRACKING_RE = re.compile(
    r'(?:'
    r'/track[?/]'
    r'|track_page_view'
    r'|action=conversion'
    r'|[?&]ti='
    r'|/beacon[?/]'
    r'|/pixel[?/]'
    r'|[?&]pixel='
    r'|nova\.collect\.'
    r'|bat\.bing\.com'
    r'|t\.teads\.tv'
    r'|photorank'      # UGC / lookbook CDN
    r'|akamaihd\.net/media/'  # photorankmedia-a.akamaihd.net UGC CDN
    r'|doubleclick\.net'
    r'|google-analytics\.com'
    r'|googletagmanager\.com'
    r'|scorecardresearch\.com'
    r')',
    re.I
)

# Navigation / promo / site-UI banners
_IMAGE_NAV_PROMO_RE = re.compile(
    r'(?:'
    r'gnb[_%-]'               # LG Global Navigation Bar images (e.g. gnb_logo)
    r'|/gnb/'                 # Samsung GNB path (/gnb/images/...)
    r'|assets/us/gnb/'        # Samsung GNB asset path
    r'|/common/images/common/'
    r'|lg5-common'
    r'|popup[_-]close'
    r'|promo(?:tional)?[_-]banner'
    r'|header[_-]banner'
    r'|personal-setup'        # Apple personal-setup service image
    r'|applecare'             # Apple Care marketing banner
    r'|apple-care'
    r'|/trade-in'             # Apple trade-in graphic
    r'|iphone-compare'        # Apple comparison-table graphic
    r'|lazyload_home'         # Samsung homepage lazy-load nav images
    r'|lazyload-home'
    r'|LazyLoad_Home'
    r'|support-icon'          # Generic support / help icons
    r'|nav-icon'              # Navigation bar icons
    r'|menu-icon'
    r'|/footer/'              # Footer images
    r'|GetShopApp'            # App download banners
    r'|trustarc'              # TrustArc consent badge
    r'|teads'                 # Teads ad network
    r'|blank\.gif'            # Transparent placeholder
    r'|Order[_-]Help'         # Support / order help icons
    r'|Repair[_-]'            # Repair service icons
    r'|home-appliances/'      # Samsung/LG appliance nav images (on phone pages)
    r'|/washer'               # Laundry appliance images
    r'|/dryer'
    r'|/refrigerator'         # Refrigerator appliance images (wrong-category)
    r'|_Brushed_Black_SCOM'   # Samsung washer model suffix pattern
    r')',
    re.I
)

# Product gallery container selectors — tried in order before full DOM scan
_PRODUCT_GALLERY_SELECTORS = [
    "[data-testid*='product-image']",
    "[data-testid*='gallery']",
    "[data-test*='gallery']",
    "[class*='product-gallery']",
    "[class*='productGallery']",
    "[class*='ProductGallery']",
    "[class*='pdp-image']",
    "[class*='pdp__image']",
    "[class*='product-images']",
    "[class*='gallery__images']",
    "[aria-label*='gallery']",
]


# =========================================================
# Product region extraction — isolate PDP from nav/footer noise
# =========================================================

# Headings / text that signal the START of the main product area
_PRODUCT_REGION_START_RE = re.compile(
    r'(?:'
    r'buy\s+now'
    r'|reserve\s+now'
    r'|pre-?order\s+now'
    r'|add\s+to\s+(?:cart|bag|basket)'
    r'|choose\s+(?:a\s+)?(?:color|storage|size|model|option)'
    r'|select\s+(?:a\s+)?(?:color|storage|size|model|option)'
    r')',
    re.I
)

# Content that signals the END of the product section (stop extraction here)
_PRODUCT_REGION_STOP_RE = re.compile(
    r'(?:'
    r'\bsupport\b'
    r'|\bfor\s+business\b'
    r'|\bshop\s+by\s+category\b'
    r'|\brelated\s+products?\b'
    r'|\brecommended\s+for\s+you\b'
    r'|\byou\s+may\s+also\s+like\b'
    r'|\bsign\s+in\b'
    r'|\bcreate\s+account\b'
    r'|\bopen\s+my\s+menu\b'
    r'|\bmy\s+account\b'
    r'|\bterms\s+(?:of\s+)?(?:use|service)\b'
    r'|\bprivacy\s+policy\b'
    r'|\bcontact\s+us\b'
    r'|\bsite\s+map\b'
    r'|\bcustomer\s+(?:service|care|support)\b'
    r')',
    re.I
)

# CSS class / id patterns that mark non-product containers
_NOISE_CONTAINER_RE = re.compile(
    r'(?:'
    r'\bgnb\b'
    r'|\bnav(?:igation|bar|menu)?\b'
    r'|\bfooter\b'
    r'|\bheader\b'
    r'|\bsidebar\b'
    r'|\brelated[-_]products?\b'
    r'|\brecommend(?:ed|ation)s?\b'
    r'|\bcross[-_]sell\b'
    r'|\bupsell\b'
    r'|\bcookies?\b'
    r'|\bconsent\b'
    r'|\bchat[-_]?widget\b'
    r'|\bsupport[-_]?(?:bot|widget|chat)\b'
    r')',
    re.I
)


def _get_slug_from_url(url):
    """Extract the final non-numeric path segment as product slug."""
    if not url:
        return ''
    path = urlparse(url).path.rstrip('/')
    parts = [p for p in path.split('/') if p and not p.isdigit()]
    return parts[-1].lower() if parts else ''


def extract_product_region(soup, product_name, url=''):
    """Return a narrowed BeautifulSoup element containing only the product area.

    Strategy (in priority order):
    1. CSS selector for known PDP wrappers (most precise)
    2. Walk <main> children and drop known non-product containers
    3. Fall back to full <main> or <body>

    This is intentionally generic — it improves Samsung, Apple, LG, Sony,
    Dell, Lenovo, Adidas and any Jina-rendered page, not just Samsung.
    """
    # ── 1. Try well-known PDP wrapper selectors ───────────────────────────
    _PDP_SELECTORS = [
        # Semantic
        "[itemtype*='Product']",
        "[data-page-type*='product']",
        "[data-component*='ProductDetail']",
        "[data-testid*='product-detail']",
        "[data-testid*='pdp']",
        # Common class patterns
        ".pdp",
        ".pdp__content",
        ".pdp-content",
        ".product-detail",
        ".product-details",
        ".ProductDetail",
        ".product__main",
        ".product-main",
        "#product-detail",
        "#pdp",
        # Samsung / LG branded
        "[class*='pdp-']",
        "[class*='product-detail']",
        "[class*='ProductDetail']",
        "[class*='product-intro']",
        "[class*='product-overview']",
    ]
    for sel in _PDP_SELECTORS:
        el = soup.select_one(sel)
        if el:
            return el

    # ── 2. Walk <main> children and strip noise containers ────────────────
    main = soup.select_one("main") or soup.body
    if main:
        # Remove elements whose class/id strongly signals non-product content
        import copy
        main_copy = copy.copy(main)
        for el in main_copy.find_all(True):
            # Skip elements already decomposed with a removed parent —
            # decompose() nulls their attrs and el.get() would crash
            # (huygens.fr about page, AttributeError on NoneType).
            if getattr(el, "attrs", None) is None:
                continue
            el_class = ' '.join(el.get('class') or [])
            el_id = el.get('id') or ''
            combined = f"{el_class} {el_id}".lower()
            if _NOISE_CONTAINER_RE.search(combined):
                el.decompose()
        return main_copy

    return soup


def score_image_candidate(url_str, product_slug='', product_name=''):
    """Score an image URL by relevance to the product.

    Higher score = better candidate for imageUrl (pick the highest).
    Returns an integer score; negative = likely wrong-category/nav image.
    """
    if not url_str:
        return -999
    s = url_str.lower()
    slug = (product_slug or '').lower().replace(' ', '-')
    name_words = [w.lower() for w in (product_name or '').split() if len(w) > 2]

    score = 0

    # Strong positive: URL contains product slug
    if slug and slug in s:
        score += 50

    # Product name words in URL
    name_hits = sum(1 for w in name_words if w in s)
    score += name_hits * 10

    # Generic positive signals
    if 'features' in s:
        score += 30
    if 'hero' in s:
        score += 20
    if 'kv' in s or 'keyvisual' in s or 'key-visual' in s:
        score += 25
    if 'pdp' in s or 'product' in s:
        score += 15
    if 'main' in s or 'primary' in s:
        score += 10
    if re.search(r'_\d{2,}_', s):  # numbered gallery shot e.g. _01_
        score += 5

    # Strong negatives: wrong-category / nav
    _NEG_TERMS = [
        'gnb', '/gnb/', 'gnb_', 'gnb%', 'gnb-',
        'lazyload_home', 'lazyload-home', 'LazyLoad_Home'.lower(),
        'home-appliances', '/washer', '/dryer', '/refrigerator',
        'washing-machine', 'dishwasher',
        'footer', '/footer/',
        'trustarc', 'teads', 'blank.gif',
        'getshopapp', 'order-help', 'order_help',
        'repair', 'support-icon',
        'logo', 'icon', 'sprite', 'badge',
        'services-iphone', 'carrier-logo',
        '_Brushed_Black_SCOM'.lower(),
    ]
    for neg in _NEG_TERMS:
        if neg in s:
            score -= 100

    return score


# =========================================================
# Basic helpers
# =========================================================

def clean_text(text):
    return re.sub(r"\s+", " ", text or "").strip()


def strip_html_tags(text):
    """Strip HTML tags and decode entities; collapse whitespace."""
    if not text:
        return text
    import html as _html_mod
    cleaned = re.sub(r'<[^>]+>', ' ', text)
    cleaned = _html_mod.unescape(cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned or None


def get_meta(soup, name=None, property_name=None):
    if name:
        tag = soup.find("meta", attrs={"name": name})
        if tag:
            return clean_text(tag.get("content"))

    if property_name:
        tag = soup.find("meta", attrs={"property": property_name})
        if tag:
            return clean_text(tag.get("content"))

        tag = soup.find("meta", attrs={"name": property_name})
        if tag:
            return clean_text(tag.get("content"))

        for meta in soup.find_all("meta"):
            prop = meta.get("property") or meta.get("name") or ""
            if prop.lower() == property_name.lower():
                return clean_text(meta.get("content"))

    return None


def safe_float(value):
    if value is None:
        return None

    try:
        value = str(value)
        value = re.sub(r"[^\d.]", "", value)

        if not value:
            return None

        return float(value)

    except Exception:
        return None


def normalize_brand(brand):
    if not brand:
        return None

    if isinstance(brand, dict):
        return brand.get("name") or brand.get("@id") or None

    if isinstance(brand, str):
        return clean_text(brand)

    return None


def normalize_image_candidate(candidate):
    """Accept str or dict image candidate; return URL string or None.

    JSON-LD and hydration objects sometimes embed image dicts with keys like
    url / src / contentUrl / thumbnailUrl instead of plain strings.  Always
    call this before passing anything to is_good_product_image().
    """
    if isinstance(candidate, str):
        return candidate.strip() or None
    if isinstance(candidate, dict):
        for key in ("url", "src", "contentUrl", "thumbnailUrl", "image"):
            val = candidate.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
    return None


def canonicalize_image_url(src, base_url=None):
    """Resolve relative image URLs to absolute; return (canonical_key, resolved_src).

    canonical_key = URL with query string and fragment stripped (used only for
    deduplication — e.g. IKEA ?f=u and ?f=s variants map to the same key).
    resolved_src  = the absolute URL to store.
    Returns (None, None) for unusable inputs (data:, blob:, empty).
    """
    if not src:
        return None, None
    src = src.strip()
    if src.startswith(('data:', 'blob:')):
        return None, None
    # Resolve relative paths against the page URL
    if base_url and not src.startswith(('http://', 'https://', '//')):
        try:
            from urllib.parse import urljoin
            src = urljoin(base_url, src)
        except Exception:
            pass
    # Protocol-relative
    if src.startswith('//'):
        src = 'https:' + src
    # Build canonical key (path only, no query/fragment)
    try:
        from urllib.parse import urlparse, urlunparse
        p = urlparse(src)
        canonical_key = urlunparse((p.scheme, p.netloc, p.path, '', '', ''))
    except Exception:
        canonical_key = src.split('?')[0]
    return canonical_key or None, src


def is_context_rejection(src, product_url):
    """Return True when src is irrelevant for the given product_url context.

    Prevents Samsung smartphone pages from including refrigerator/TV nav
    images, and Apple shop pages from including AppleCare/compare images.
    """
    if not src or not product_url:
        return False
    src_l = src.lower()
    url_l = product_url.lower()
    host = urlparse(url_l).hostname or ''

    # Samsung smartphone page → reject home-appliance / TV / other-category images
    if 'samsung.com' in host:
        path = urlparse(url_l).path.lower()
        if any(x in path for x in ('/smartphones/', '/galaxy-', '/mobile/', '/galaxy_')):
            _wrong_cats = [
                '/home-appliances/', '/refrigerator', '/washing-machine',
                '/dryer', '/dishwasher', '/television', '/tvs/',
                '/monitors/', '/vacuum/', '/home-appliance',
            ]
            if any(x in src_l for x in _wrong_cats):
                return True

    # Apple shop page → reject service/payment/compare images (already in NAV_PROMO_RE
    # for most; this catches a few edge cases not covered by filename patterns)
    if 'apple.com' in host and '/shop/' in url_l:
        _apple_noise = [
            'services-iphone', 'carrier-logo', 'financing-',
            'payment-plan-', 'gift-card-',
        ]
        if any(x in src_l for x in _apple_noise):
            return True

    return False


# Option values that look like marketing/navigation copy — reject from option lists
_OPTION_VALUE_NOISE_RE = re.compile(
    r'^(?:'
    r'catch\s+the\b'
    r'|^play$'
    r'|compare\s+(?:size|model|plan|color)'
    r'|watch\s+(?:now|video)'
    r'|learn\s+more'
    r'|explore\b'
    r'|see\s+all'
    r'|view\s+all'
    r'|available\s+(?:in|at|from)'
    r'|^highlights?$'
    r'|^features?$'
    r'|galaxy\s+ai'
    r'|add\s+to\s+(?:cart|bag)'
    r'|buy\s+(?:now|it)'
    r'|shop\s+(?:now|all)'
    r'|free\s+shipping'
    r')',
    re.I
)


# =========================================================
# Vendor / category inference from URL and meta
# =========================================================

_URL_VENDOR_MAP = [
    ('apple.com',     'Apple'),
    ('samsung.com',   'Samsung'),
    ('nike.com',      'Nike'),
    ('adidas.com',    'Adidas'),
    ('puma.com',      'Puma'),
    ('lg.com',        'LG'),
    ('ikea.com',      'IKEA'),
    ('walmart.com',   'Walmart'),
    ('bestbuy.ca',    'Best Buy'),
    ('bestbuy.com',   'Best Buy'),
    ('target.com',    'Target'),
    ('amazon.com',    'Amazon'),
    ('sonos.com',     'Sonos'),
    ('dyson.com',     'Dyson'),
    ('bose.com',      'Bose'),
    ('asus.com',      'ASUS'),
    ('dell.com',      'Dell'),
    ('hp.com',        'HP'),
    ('lenovo.com',    'Lenovo'),
    ('microsoft.com', 'Microsoft'),
    ('sony.com',      'Sony'),
    ('logitech.com',  'Logitech'),
    ('under-armour.com', 'Under Armour'),
    ('underarmour.com',  'Under Armour'),
    ('newbalance.com',   'New Balance'),
    ('reebok.com',    'Reebok'),
    ('zara.com',      'Zara'),
    ('hm.com',        'H&M'),
    ('uniqlo.com',    'Uniqlo'),
]


def infer_vendor_from_context(url, soup, title):
    """Infer vendor/brand from URL domain, og:site_name, or known-brand title prefix.

    Priority: URL domain > og:site_name > title first word.
    Special case: nike.com with Jordan in title → vendor = 'Jordan'.
    """
    url_l = (url or '').lower()
    host = urlparse(url_l).hostname or ''

    # 1. Domain-based vendor (most reliable)
    for domain, vendor in _URL_VENDOR_MAP:
        if domain in host:
            if domain == 'nike.com' and title and 'jordan' in title.lower():
                return 'Jordan'
            return vendor

    # 2. og:site_name
    site_name = get_meta(soup, property_name='og:site_name')
    if site_name and 2 < len(site_name) < 40:
        return clean_text(site_name)

    # 3. First word of H1 / title if it matches a known brand
    if title:
        first_word = title.split()[0].lower() if title.split() else ''
        if first_word in _KNOWN_BRANDS:
            return title.split()[0]

    return None


# URL path fragments → product category labels
_URL_CATEGORY_MAP = [
    ('/shop/buy-iphone',       'iPhone'),
    ('/shop/buy-ipad',         'iPad'),
    ('/shop/buy-mac',          'Mac'),
    ('/shop/buy-watch',        'Apple Watch'),
    ('/shop/buy-airpods',      'AirPods'),
    ('/shop/buy-appletv',      'Apple TV'),
    ('/smartphones/',          'Smartphones'),
    ('/mobile/phones/',        'Smartphones'),
    ('/galaxy-',               'Smartphones'),
    ('/refrigerators/',        'Refrigerators'),
    ('/washing-machines/',     'Washing Machines'),
    ('/televisions/',          'TVs'),
    ('/laptops/',              'Laptops'),
    ('/tablets/',              'Tablets'),
    ('/cameras/',              'Cameras'),
    ('/headphones/',           'Headphones'),
    ('/speakers/',             'Speakers'),
    ('/shoes/',                'Shoes'),
    ('/footwear/',             'Footwear'),
    ('/sneakers/',             'Sneakers'),
    ('/clothing/',             'Clothing'),
    ('/apparel/',              'Clothing'),
    ('/furniture/',            'Furniture'),
    ('/sofas/',                'Sofas'),
    ('/beds/',                 'Beds'),
    ('/mattresses/',           'Mattresses'),
    ('/beauty/',               'Beauty'),
    ('/skincare/',             'Skincare'),
    ('/fragrance/',            'Fragrance'),
]


def infer_category_from_url(url, title=None):
    """Infer product category from URL path patterns, then from title keywords.

    Uses _URL_CATEGORY_MAP first (URL is authoritative), then falls back to
    the _TITLE_CATEGORY_MAP keyword scan on the product title.
    """
    url_l = (url or '').lower()
    for path_frag, cat in _URL_CATEGORY_MAP:
        if path_frag in url_l:
            return cat
    # Title keyword fallback
    if title:
        title_l = title.lower()
        for pattern, cat in _TITLE_CATEGORY_MAP:
            if re.search(pattern, title_l, re.I):
                return cat
    return None


# =========================================================
# Price helpers
# =========================================================

def extract_prices(text):
    if not text:
        return []

    patterns = [
        r"\$\s?\d+(?:[,.]\d{1,2})?",
        r"£\s?\d+(?:[,.]\d{1,2})?",
        r"€\s?\d+(?:[,.]\d{1,2})?",
        r"pkr\s?\d+(?:[,.]\d{1,2})?",
        r"rs\.?\s?\d+(?:[,.]\d{1,2})?"
    ]

    prices = []

    for pattern in patterns:
        prices.extend(re.findall(pattern, text, re.I))

    cleaned = []

    for price in prices:
        price = clean_text(price)

        if price.lower() in [
            "$0",
            "$0.00",
            "£0",
            "£0.00",
            "€0",
            "€0.00",
            "0",
            "0.00"
        ]:
            continue

        if price not in cleaned:
            cleaned.append(price)

    return cleaned


def detect_currency(price_text, html):
    combined = f"{price_text or ''} {html or ''}".lower()

    if "$" in combined:
        return "USD"

    if "£" in combined:
        return "GBP"

    if "€" in combined:
        return "EUR"

    if "pkr" in combined or "rs." in combined or "rs " in combined:
        return "PKR"

    return None


def infer_currency_from_url(url):
    """Delegate to shared currency utility (50+ TLDs, path-locale patterns)."""
    from utils.currency import currency_from_url
    return currency_from_url(url)


def extract_price(soup, html, jsonld_product=None, next_product=None):
    price = None
    compare_at = None
    currency = None
    raw = None

    # -------------------------
    # 1. JSON-LD offer
    # -------------------------

    if jsonld_product:
        offers = jsonld_product.get("offers")

        if isinstance(offers, list):
            offers = offers[0] if offers else None

        if isinstance(offers, dict):
            # Detect AggregateOffer vs regular Offer
            # AggregateOffer uses lowPrice/highPrice instead of price
            _offer_type = offers.get("@type")
            if isinstance(_offer_type, list):
                _is_aggregate = any(str(t).lower().endswith("aggregateoffer") for t in _offer_type)
            else:
                _is_aggregate = str(_offer_type or "").lower().endswith("aggregateoffer")

            if _is_aggregate:
                # AggregateOffer: price field absent; lowPrice is the current price
                price = offers.get("lowPrice")
                compare_at = offers.get("highPrice")
            else:
                price = (
                    offers.get("price")
                    or offers.get("lowPrice")
                    or offers.get("priceSpecification", {}).get("price")
                    if isinstance(offers.get("priceSpecification"), dict)
                    else offers.get("price") or offers.get("lowPrice")
                )
                compare_at = (
                    offers.get("highPrice")
                    or offers.get("compareAtPrice")
                    or offers.get("originalPrice")
                    or offers.get("wasPrice")
                )

            currency = (
                offers.get("priceCurrency")
                or offers.get("priceSpecification", {}).get("priceCurrency")
                if isinstance(offers.get("priceSpecification"), dict)
                else offers.get("priceCurrency")
            )

            raw = str(price) if price is not None else None

    # -------------------------
    # 2. Next/hydration object
    # -------------------------

    if price is None and next_product:
        for key in [
            "price",
            "currentPrice",
            "salePrice",
            "priceAmount",
            "formattedPrice"
        ]:
            if next_product.get(key):
                price = next_product.get(key)
                raw = str(price)
                break

        for key in [
            "compareAtPrice",
            "originalPrice",
            "wasPrice",
            "listPrice"
        ]:
            if next_product.get(key):
                compare_at = next_product.get(key)
                break

        for key in [
            "currency",
            "priceCurrency",
            "currencyCode"
        ]:
            if next_product.get(key):
                currency = next_product.get(key)
                break

    # -------------------------
    # 3. Meta / OpenGraph
    # Important for Sonos: price:amount / price:currency
    # -------------------------

    if price is None:
        meta_price = (
            get_meta(soup, property_name="product:price:amount")
            or get_meta(soup, property_name="og:price:amount")
            or get_meta(soup, property_name="price:amount")
            or get_meta(soup, name="price")
        )

        meta_currency = (
            get_meta(soup, property_name="product:price:currency")
            or get_meta(soup, property_name="og:price:currency")
            or get_meta(soup, property_name="price:currency")
            or get_meta(soup, name="currency")
        )

        if meta_price:
            price = meta_price
            raw = str(meta_price)
            currency = meta_currency

    # -------------------------
    # 4. DOM fallback
    # Do NOT infer compareAt from random page prices.
    # -------------------------

    if price is None:
        # 4a. Price-DESIGNATED nodes first: elements the site itself marks as
        # the price (data-testid="currentPrice-container" on nike.com,
        # itemprop="price", product-price classes). Whole-page first-dollar
        # matching is only a last resort - pages are full of unrelated
        # amounts (gift cards, shipping thresholds, promo banners).
        try:
            _price_nodes = soup.select(
                '[data-testid*="price" i], [itemprop="price"], '
                '[class*="product-price" i], [id*="product-price" i], '
                '[class*="price-current" i], [class*="current-price" i]'
            )
        except Exception:
            _price_nodes = []
        for _node in _price_nodes:
            _candidate_text = _node.get("content") or _node.get_text(" ", strip=True)
            _found = extract_prices(clean_text(_candidate_text))
            if _found:
                raw = _found[0]
                price = safe_float(raw)
                currency = detect_currency(raw, html)
                break

    if price is None:
        prices = extract_prices(clean_text(soup.get_text(" ", strip=True)))

        if prices:
            raw = prices[0]
            price = safe_float(raw)
            currency = detect_currency(raw, html)

    current_value = safe_float(price)
    compare_value = safe_float(compare_at)

    if compare_value and current_value and compare_value <= current_value:
        compare_value = None

    if not currency:
        currency = detect_currency(raw, html)

    return {
        "currency": currency,
        "current": current_value,
        "compareAt": compare_value,
        "isOnSale": bool(compare_value and current_value and compare_value > current_value),
        "priceTextRaw": raw
    }


# =========================================================
# JSON / hydration helpers
# =========================================================

def flatten_jsonld(item):
    output = []

    if isinstance(item, list):
        for child in item:
            output.extend(flatten_jsonld(child))

    elif isinstance(item, dict):
        output.append(item)

        if isinstance(item.get("@graph"), list):
            for child in item.get("@graph"):
                output.extend(flatten_jsonld(child))

        # schema.org ProductGroup (e.g. nike.com): the sellable Products with
        # offers/price live inside hasVariant. Without descending here, the
        # page fell through to the text fallback and grabbed a random dollar
        # amount ($50 banner instead of the $130 product price).
        if isinstance(item.get("hasVariant"), list):
            for child in item.get("hasVariant"):
                output.extend(flatten_jsonld(child))

    return output


def extract_jsonld_products(soup):
    products = []

    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            raw = script.string or script.get_text()

            if not raw:
                continue

            parsed = json.loads(raw)
            items = flatten_jsonld(parsed)

            for item in items:
                item_type = item.get("@type")

                if isinstance(item_type, list):
                    item_types = [str(x).lower() for x in item_type]
                else:
                    item_types = [str(item_type).lower()] if item_type else []

                # ProductGroup: the canonical product NAME lives on the group;
                # offers/price live on the variants ("... - Size XS" names).
                # Emit a merged product (group identity + first variant's
                # offers) FIRST, so callers get the right name AND price.
                if "productgroup" in item_types:
                    _variants = item.get("hasVariant") or []
                    _v0 = _variants[0] if (isinstance(_variants, list) and _variants
                                           and isinstance(_variants[0], dict)) else {}
                    merged = dict(_v0)
                    for _k in ("name", "description", "brand", "image"):
                        if item.get(_k):
                            merged[_k] = item[_k]
                    if merged.get("offers") or merged.get("name"):
                        products.append(merged)
                    continue

                if "product" in item_types:
                    products.append(item)

        except Exception:
            continue

    return products


def extract_next_data(soup):
    script = soup.find("script", id="__NEXT_DATA__")

    if not script:
        return None

    try:
        raw = script.string or script.get_text()
        return json.loads(raw)

    except Exception:
        return None


def _extract_next_product_from_known_paths(next_data):
    """Try well-known __NEXT_DATA__ paths for popular Next.js e-commerce sites
    before falling back to generic object scanning.

    Nike:  props.pageProps.initialState.pdp.product  (or .products[0])
    Generic Next.js: props.pageProps.product / productDetails / initialData.product
    """
    if not isinstance(next_data, dict):
        return None

    _PATHS = [
        # Nike — newer API shape
        ["props", "pageProps", "productResponse", "product"],
        ["props", "pageProps", "threads", "product"],
        ["props", "pageProps", "productGraph", "product"],
        # Nike — legacy shape
        ["props", "pageProps", "initialState", "pdp", "product"],
        ["props", "pageProps", "initialState", "pdp", "products"],
        ["props", "pageProps", "initialState", "product"],
        # Adidas / Reebok pattern
        ["props", "pageProps", "dehydratedState", "queries", 0, "state", "data", "product"],
        # ASOS pattern
        ["props", "pageProps", "productDetails"],
        # Common Next.js patterns
        ["props", "pageProps", "product"],
        ["props", "pageProps", "productData"],
        ["props", "pageProps", "initialData", "product"],
        ["props", "pageProps", "serverState", "product"],
        ["props", "pageProps", "data", "product"],
        ["props", "pageProps", "pageData", "product"],
        # Nuxt / Vue hydration
        ["data", "product"],
        ["fetch", "product"],
    ]

    _PRODUCT_KEYS = frozenset([
        "title", "name", "productname", "productTitle",
        "price", "currentprice", "saleprice",
        "description", "shortdescription",
    ])

    for path in _PATHS:
        obj = next_data
        for key in path:
            if not isinstance(obj, dict):
                obj = None
                break
            obj = obj.get(key)
        if obj is None:
            continue
        # If it's a list, take first element
        if isinstance(obj, list) and obj and isinstance(obj[0], dict):
            obj = obj[0]
        if not isinstance(obj, dict):
            continue
        lower_keys = {k.lower() for k in obj.keys()}
        # Accept if it has at least a name/title field
        if lower_keys & _PRODUCT_KEYS:
            return obj

    return None


def find_product_like_objects(obj, results=None, depth=0):
    if results is None:
        results = []

    if depth > 8:
        return results

    if isinstance(obj, dict):
        keys = set(obj.keys())
        lower_keys = {str(k).lower() for k in keys}

        product_score = 0

        if any(k in lower_keys for k in ["title", "name", "productname"]):
            product_score += 1

        if any(k in lower_keys for k in ["price", "priceamount", "currentprice", "saleprice", "formattedprice"]):
            product_score += 1

        if any(k in lower_keys for k in ["images", "image", "media"]):
            product_score += 1

        if any(k in lower_keys for k in ["variants", "options", "sku"]):
            product_score += 1

        if product_score >= 3:
            results.append(obj)

        for value in obj.values():
            find_product_like_objects(value, results, depth + 1)

    elif isinstance(obj, list):
        for item in obj:
            find_product_like_objects(item, results, depth + 1)

    return results


# =========================================================
# Image helpers
# =========================================================

def is_good_product_image(src):
    """Return True if src looks like a real product image.

    Accepts str OR dict — dicts are normalised via normalize_image_candidate()
    so callers never crash on JSON-LD image objects.
    """
    # ── Normalise dicts / guard against non-strings ──────────────────────
    if not isinstance(src, str):
        src = normalize_image_candidate(src)
        if not src:
            return False

    if not src:
        return False

    src_l = src.lower()

    # ── 1. Tracking pixels, analytics beacons, UGC CDNs, nav banners ─────
    if _IMAGE_TRACKING_RE.search(src_l):
        return False

    if _IMAGE_NAV_PROMO_RE.search(src_l):
        return False

    bad_image_terms = [
        "trustmark",
        "bazaarvoice",
        "logo",
        "icon",
        "sprite",
        "placeholder",
        "loading",
        "spinner",
        "avatar",
        "review",
        "photo/",
        "stars",
        "rating",
        "popup-close",
        "popup_close",
        # Apple service/non-product images
        "services-iphone",
        "carrier-logo",
        "financing-image",
        "payment-plan-",
        "gift-card-",
        # Samsung/LG wrong-category signals (GNB already caught above)
        "lazyload_home",
        "lazyload-home",
        # Video / carousel noise
        "blank.gif",
        "trustarc",
        "teads",
        "getshopapp",
        # Wrong-category appliance images caught at is_context_rejection level
        # but also block here as belt-and-suspenders
        "_brushed_black_scom",
    ]

    if any(x in src_l for x in bad_image_terms):
        return False

    # ── 2. Reject transform-only CDN paths BEFORE the CDN whitelist ───────
    # e.g. .../f_auto  or  .../t_web_pdp_535_v2/f_auto
    # These are Cloudinary/Nike transform parameters with no actual image ID.
    # They must be rejected even when the CDN host is whitelisted.
    _last_seg = src_l.rstrip('/').rsplit('/', 1)[-1].split('?')[0]
    if re.match(r'^[a-z]{1,2}_[a-z0-9_,]+$', _last_seg) and '.' not in _last_seg:
        return False

    # ── 3. Strong product CDN whitelist (allow even without extension) ────
    strong_product_cdn_terms = [
        "images.puma.com",
        "media.sonos.com",
        "static.nike.com",
        "underarmour.scene7.com",
        "cdn.shopify.com",
        "scene7.com",
        "is/image",
        "cdn-apple.com",
        "store.storeimages",
        "assets.adidas.com",
    ]

    if any(x in src_l for x in strong_product_cdn_terms):
        return True

    # ── 4. Good product path keywords ────────────────────────────────────
    good_product_terms = [
        "product",
        "pdp",
        "default",
        "main",
        "pair",
        "sole",
        "heel",
        "toe",
        "detail",
        "swatch",
        "media"
    ]

    if any(x in src_l for x in good_product_terms):
        return True

    # ── 5. Standard image extension ───────────────────────────────────────
    if re.search(r"\.(jpg|jpeg|png|webp)(\?|$)", src_l):
        return True

    return False


def _collect_imgs_from_container(container, seen=None):
    """Yield good product image URLs from a BeautifulSoup element."""
    if seen is None:
        seen = set()
    for img in container.find_all("img"):
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
        if not is_good_product_image(src):
            continue
        # Skip tiny images (icons, tracking pixels with explicit size)
        try:
            w = int(img.get("width") or 0)
            h = int(img.get("height") or 0)
            if (0 < w < 60) or (0 < h < 60):
                continue
        except (ValueError, TypeError):
            pass
        if src not in seen:
            seen.add(src)
            yield src


def extract_images_from_dom(soup, product_slug='', product_name='', product_region=None):
    """Extract product images from DOM, scoring and ranking by relevance.

    Uses product_region (narrowed soup element from extract_product_region)
    when provided, falling back to full-DOM scan.  Always scores images with
    score_image_candidate() and returns them ranked highest-score first.
    """
    candidates = []   # list of (score, url)
    seen_keys = set()

    def _try_add(src_raw):
        src = (normalize_image_candidate(src_raw)
               if not isinstance(src_raw, str) else src_raw)
        if not src:
            return
        if "," in src:
            src = src.split(",")[0].strip().split(" ")[0]
        if src.startswith("data:image") or src.startswith("blob:"):
            return
        if not is_good_product_image(src):
            return
        key = src.split("?")[0].lower()
        if key in seen_keys:
            return
        seen_keys.add(key)
        sc = score_image_candidate(src, product_slug, product_name)
        if sc < -50:   # definitely a nav/wrong-category image — skip entirely
            return
        candidates.append((sc, src))

    # og:image first (often the canonical hero shot)
    og_image = get_meta(soup, property_name="og:image")
    if og_image:
        _try_add(og_image)

    # 1. Try product gallery container first (most precise)
    gallery_found = False
    for selector in _PRODUCT_GALLERY_SELECTORS:
        container = soup.select_one(selector)
        if container:
            for src in _collect_imgs_from_container(container, set()):
                _try_add(src)
            if candidates:
                gallery_found = True
                break

    # 2. Scan product region (or full <main>) when no gallery found
    if not gallery_found:
        search_root = product_region or soup.select_one("main") or soup.body or soup
        for img in search_root.find_all("img"):
            if img.find_parent(["header", "nav", "footer"]):
                continue
            src = (
                img.get("src")
                or img.get("data-src")
                or img.get("data-lazy-src")
                or img.get("srcset")
            )
            if not src:
                continue
            # Skip tiny images (icons, tracking pixels)
            try:
                w = int(img.get("width") or 0)
                h = int(img.get("height") or 0)
                if (0 < w < 60) or (0 < h < 60):
                    continue
            except (ValueError, TypeError):
                pass
            _try_add(src)

    # Sort by score descending
    candidates.sort(key=lambda x: x[0], reverse=True)
    return [url for _, url in candidates[:30]]


# =========================================================
# Text / description helpers
# =========================================================

def is_bad_description(text):
    if not text:
        return True

    text_l = text.lower()

    bad_terms = [
        "new & featured",
        "new arrivals",
        "best sellers",
        "latest drops",
        "launch calendar",
        "shop all sale",
        "all shoes",
        "all clothing",
        "hoodies & sweatshirts",
        "bags & backpacks",
        "location :",
        "reviews :",
        "votes :",
        "more less",
        "write a review",
        "was this helpful",
        "free shipping",
        "order status",
        "returns",
        "sign in",
        "join us"
    ]

    bad_hits = sum(1 for term in bad_terms if term in text_l)

    if bad_hits >= 2:
        return True

    # Reject mega-menu style text: too many category words packed together.
    category_terms = [
        "basketball",
        "jordan",
        "lifestyle",
        "running",
        "soccer",
        "training",
        "clothing",
        "accessories",
        "hoodies",
        "pants",
        "shorts",
        "bags",
        "socks"
    ]

    category_hits = sum(1 for term in category_terms if term in text_l)

    if category_hits >= 7:
        return True

    return False


def clean_product_name(name):
    """Strip common SEO pipe suffixes: "Product | Brand" → "Product"."""
    if not name:
        return name
    # Pipe character is a universal title separator — strip everything after it
    name = re.sub(r'\s*\|.*$', '', name).strip()
    # Strip " - Brand.com" style suffixes
    name = re.sub(r'\s+-\s+\w+\.(?:com|co\.\w{2}|net|org)\s*$', '', name, flags=re.I).strip()
    return name or None


def extract_title(soup, jsonld_product=None, next_product=None):
    raw = None

    if jsonld_product:
        name = jsonld_product.get("name")
        if name:
            raw = clean_text(name)

    if raw is None and next_product:
        for key in ["title", "name", "productName"]:
            if next_product.get(key):
                raw = clean_text(next_product.get(key))
                break

    h1_candidate = None
    if raw is None:
        h1 = soup.find("h1")
        if h1:
            text = clean_text(h1.get_text(" ", strip=True))
            if text and text.lower() not in ["404", "not found"]:
                h1_candidate = text
                # Only accept H1 directly if it has 4+ words (enough to be a
                # real product name rather than a brand/category heading)
                if len(text.split()) >= 4:
                    raw = text

    og_title = get_meta(soup, property_name="og:title")

    if raw is None:
        # Weak H1 (≤3 words): prefer og:title when it is longer and more
        # descriptive (e.g. H1="Nike Sportswear" vs og="Nike Sportswear
        # Women's Oversized Windrunner Jacket")
        if og_title and h1_candidate:
            if len(og_title.split()) > len(h1_candidate.split()):
                raw = og_title
            else:
                raw = h1_candidate
        elif og_title:
            raw = og_title
        elif h1_candidate:
            raw = h1_candidate

    if raw is None and soup.title and soup.title.string:
        raw = clean_text(soup.title.string)

    return clean_product_name(raw)


def extract_description(soup, jsonld_product=None, next_product=None):
    # -------------------------
    # 1. JSON-LD description
    # -------------------------

    if jsonld_product:
        desc = jsonld_product.get("description")
        desc = clean_text(desc)
        if desc and '<' in desc:
            desc = strip_html_tags(desc)
        if desc and not is_bad_description(desc):
            return desc

    # -------------------------
    # 2. Hydration object description
    # -------------------------

    if next_product:
        for key in ["description", "shortDescription", "productDescription"]:
            if next_product.get(key):
                desc = clean_text(str(next_product.get(key)))
                if desc and '<' in desc:
                    desc = strip_html_tags(desc)
                if desc and not is_bad_description(desc):
                    return desc

    # -------------------------
    # 3. Product-specific DOM selectors
    # Avoid broad [class*='details'] because it catches reviews/nav.
    # -------------------------

    selectors = [
        "[data-testid*='product-description']",
        "[data-test-id*='product-description']",
        "[data-testid*='description']",
        "[data-test-id*='description']",
        ".product-description",
        ".product__description",
        ".pdp-description",
        ".description__content",
        "[class*='productDescription']",
        "[class*='ProductDescription']"
    ]

    for selector in selectors:
        block = soup.select_one(selector)

        if block:
            text = clean_text(block.get_text(" ", strip=True))

            if len(text) > 80 and not is_bad_description(text):
                return text[:1500]

    # -------------------------
    # 4. Meta fallback
    # Often cleaner than menu/review text.
    # -------------------------

    meta_desc = (
        get_meta(soup, name="description")
        or get_meta(soup, property_name="og:description")
    )

    if meta_desc:
        if '<' in meta_desc:
            meta_desc = strip_html_tags(meta_desc)
        if meta_desc and not is_bad_description(meta_desc):
            return meta_desc

    # -------------------------
    # 5. Paragraph fallback
    # Reject review/menu text.
    # -------------------------

    for p in soup.find_all("p"):
        text = clean_text(p.get_text(" ", strip=True))

        if text and len(text) > 60 and not is_bad_description(text):
            return text[:1500]

    return meta_desc or None


# =========================================================
# Description structure helpers
# =========================================================

_BENEFIT_SIGNALS = re.compile(
    r'\b(?:comfort|support|cushion|feel|fit|relief|'
    r'performance|experience|keep|stay|help|allow|enable|'
    r'provide|offer|ensure|improve|protect|reduce|prevent|'
    r'boost|enhance|promote|maximize|minimize|absorb|breathe)\b',
    re.I
)

_SPEC_SIGNALS = re.compile(
    r'\b(?:\d+(?:\.\d+)?\s*(?:mm|cm|g|kg|oz|lb|ml|l|gb|tb|hz|mah|v|w)|'
    r'weight|dimension|capacity|volume|resolution|processor|'
    r'battery|storage|memory|screen|display|width|height|depth|'
    r'warranty|sku|model\s*(?:no|number|#))\b',
    re.I
)

_FEATURE_SIGNALS = re.compile(
    r'\b(?:material|fabric|leather|rubber|foam|mesh|carbon|fiber|glass|'
    r'steel|aluminum|rubber|sole|upper|collar|lace|strap|lining|'
    r'outsole|midsole|technology|tech|system|design|construction|'
    r'built|made|crafted|featuring|includes|equipped|integrated)\b',
    re.I
)


def split_description_to_features(description):
    """Classify description sentences into features, benefits, specifications."""
    if not description or len(description) < 20:
        return [], [], []

    # Split on sentence boundaries and common bullet-point markers
    raw_sentences = re.split(
        r'(?<=[.!?])\s+|[\n\r]+|(?:^|\s)[•·▪▸‣]\s*',
        description
    )
    sentences = [s.strip() for s in raw_sentences if len(s.strip()) > 20]

    features, benefits, specifications = [], [], []

    for sentence in sentences[:25]:
        if _SPEC_SIGNALS.search(sentence):
            specifications.append(sentence[:200])
        elif _BENEFIT_SIGNALS.search(sentence):
            benefits.append(sentence[:200])
        else:
            features.append(sentence[:200])

    return features[:10], benefits[:10], specifications[:10]


# =========================================================
# Availability / variants / options
# =========================================================

def extract_availability(soup, jsonld_product=None, next_product=None):
    text = clean_text(soup.get_text(" ", strip=True)).lower()

    availability_raw = None

    if jsonld_product:
        offers = jsonld_product.get("offers")

        if isinstance(offers, list):
            offers = offers[0] if offers else None

        if isinstance(offers, dict):
            availability_raw = offers.get("availability")

    if next_product:
        for key in ["availability", "available", "inStock", "stockStatus"]:
            if key in next_product:
                availability_raw = next_product.get(key)
                break

    availability_l = str(availability_raw or "").lower()

    if "instock" in availability_l or availability_raw is True:
        return {
            "status": "in_stock",
            "label": "In stock",
            "inStock": True,
            "stockTextRaw": availability_raw
        }

    if "outofstock" in availability_l or availability_raw is False:
        return {
            "status": "out_of_stock",
            "label": "Out of stock",
            "inStock": False,
            "stockTextRaw": availability_raw
        }

    if "out of stock" in text or "sold out" in text:
        return {
            "status": "out_of_stock",
            "label": "Out of stock",
            "inStock": False,
            "stockTextRaw": "out of stock"
        }

    if "coming soon" in text or "notify me when available" in text:
        return {
            "status": "coming_soon",
            "label": "Coming soon",
            "inStock": False,
            "stockTextRaw": "coming soon"
        }

    if re.search(r'\bpre-?order\b', text, re.I):
        return {
            "status": "preorder",
            "label": "Pre-order",
            "inStock": True,
            "stockTextRaw": "pre-order"
        }

    if "in stock" in text:
        return {
            "status": "in_stock",
            "label": "In stock",
            "inStock": True,
            "stockTextRaw": "in stock"
        }

    # DOM button fallback — look for add-to-cart / add-to-bag buttons
    _ATC_SELECTORS = [
        "button[data-testid*='add-to-cart']",
        "button[data-testid*='add-to-bag']",
        "button[data-testid*='addToCart']",
        "button[data-testid*='addToBag']",
        "button[class*='add-to-cart']",
        "button[class*='add-to-bag']",
        "button[class*='addToCart']",
        "button[class*='addToBag']",
        "[data-action*='add-to-cart']",
        "[data-action*='add']",
    ]
    _ATC_TEXT_RE = re.compile(
        r'\b(?:add\s+to\s+(?:cart|bag|basket)|buy\s+now|add\s+to\s+trolley)\b',
        re.I
    )
    _OOS_TEXT_RE = re.compile(
        r'\b(?:out\s+of\s+stock|sold\s+out|unavailable|no\s+longer\s+available)\b',
        re.I
    )

    for selector in _ATC_SELECTORS:
        btn = soup.select_one(selector)
        if btn:
            is_disabled = (
                btn.get("disabled") is not None
                or btn.get("aria-disabled") == "true"
                or "disabled" in " ".join(btn.get("class") or []).lower()
            )
            if not is_disabled:
                return {
                    "status": "in_stock",
                    "label": "In stock",
                    "inStock": True,
                    "stockTextRaw": "add-to-cart button present"
                }

    # Scan button text for ATC or OOS signals
    _oos_buttons = 0
    _atc_buttons = 0
    for btn in soup.find_all("button"):
        btn_text = clean_text(btn.get_text(" ", strip=True))
        if not btn_text:
            continue
        if _OOS_TEXT_RE.search(btn_text):
            _oos_buttons += 1
        elif _ATC_TEXT_RE.search(btn_text):
            is_disabled = (
                btn.get("disabled") is not None
                or btn.get("aria-disabled") == "true"
            )
            if not is_disabled:
                _atc_buttons += 1

    if _atc_buttons > 0:
        return {
            "status": "in_stock",
            "label": "In stock",
            "inStock": True,
            "stockTextRaw": "add-to-cart button text found"
        }

    if _oos_buttons > 0:
        return {
            "status": "out_of_stock",
            "label": "Out of stock",
            "inStock": False,
            "stockTextRaw": "sold out button found"
        }

    # Size picker availability — if size buttons exist and some aren't sold-out → in_stock
    _size_containers = soup.select(
        "fieldset[data-testid*='size'], fieldset[aria-label*='size'], "
        "[role='radiogroup'][aria-label*='size'], [role='radiogroup'][aria-label*='Size']"
    )
    if _size_containers:
        _sold_out_count = 0
        _total_count = 0
        for _sc in _size_containers[:3]:
            for _btn in _sc.find_all(["button", "input"]):
                _lbl = (_btn.get("aria-label") or "").lower()
                _btn_text = clean_text(_btn.get_text(" ", strip=True)).lower()
                _total_count += 1
                if "sold out" in _lbl or "sold out" in _btn_text:
                    _sold_out_count += 1
                elif _btn.get("disabled") or _btn.get("aria-disabled") == "true":
                    _sold_out_count += 1
        if _total_count > 0:
            if _sold_out_count < _total_count:
                return {
                    "status": "in_stock",
                    "label": "In stock",
                    "inStock": True,
                    "stockTextRaw": "size picker has available sizes"
                }
            else:
                return {
                    "status": "out_of_stock",
                    "label": "Out of stock",
                    "inStock": False,
                    "stockTextRaw": "all sizes sold out"
                }

    return {
        "status": "unknown",
        "label": "Unknown",
        "inStock": None,
        "stockTextRaw": availability_raw
    }


def _normalise_variant(v):
    """Normalise a variant dict from any structured source to a common shape."""
    price_raw = (
        v.get("price") or v.get("currentPrice") or v.get("salePrice")
        or v.get("formattedPrice") or v.get("offerPrice")
    )
    # If price is a dict (e.g. {amount, currency}), flatten it
    if isinstance(price_raw, dict):
        price_raw = price_raw.get("amount") or price_raw.get("value") or price_raw.get("current")
    avail = v.get("available") or v.get("inStock") or v.get("availability")
    if isinstance(avail, str):
        avail = avail.lower() not in ("outofstock", "out_of_stock", "sold out", "false", "0")
    return {
        "id":        v.get("id") or v.get("variantId") or v.get("sku"),
        "title":     v.get("title") or v.get("name") or v.get("label"),
        "sku":       v.get("sku"),
        "price":     str(price_raw) if price_raw is not None else None,
        "available": avail,
        "option1":   v.get("option1") or v.get("size") or v.get("selectedOptions", [{}])[0].get("value") if v.get("selectedOptions") else None,
        "option2":   v.get("option2") or v.get("color") or (v.get("selectedOptions", [{}, {}])[1].get("value") if len(v.get("selectedOptions") or []) > 1 else None),
    }


def extract_variants(next_product=None, jsonld_product=None):
    variants = []

    # ── Source 1: __NEXT_DATA__ product.variants ──────────────────────────────
    if next_product:
        raw_variants = (
            next_product.get("variants")
            or next_product.get("skus")         # Nike skus array
            or next_product.get("sku")          # sometimes singular list
        )
        if isinstance(raw_variants, list):
            for v in raw_variants[:100]:
                if not isinstance(v, dict):
                    continue
                variants.append(_normalise_variant(v))

    # ── Source 2: JSON-LD offers list ────────────────────────────────────────
    # When a product has multiple Offer objects, each represents a variant SKU.
    if not variants and jsonld_product:
        offers = jsonld_product.get("offers") or {}
        # Offers may be a single dict OR a list
        if isinstance(offers, dict):
            offer_list = offers.get("offers") or []  # AggregateOffer wrapper
            if not offer_list and offers.get("@type") in ("Offer", "AggregateOffer"):
                offer_list = []  # single offer → no variant list useful
        elif isinstance(offers, list):
            offer_list = offers
        else:
            offer_list = []

        if len(offer_list) > 1:
            for o in offer_list[:100]:
                if not isinstance(o, dict):
                    continue
                variants.append(_normalise_variant({
                    "id":           o.get("sku") or o.get("productID"),
                    "title":        o.get("name") or o.get("description"),
                    "sku":          o.get("sku"),
                    "price":        o.get("price") or o.get("lowPrice"),
                    "availability": o.get("availability", ""),
                    "available":    "OutOfStock" not in str(o.get("availability", "")),
                }))

    return variants


# Selectors for button-group variant pickers (Nike sizes, Apple storage/color, etc.)
_BUTTON_GROUP_OPTION_SELECTORS = [
    # fieldset containers (most semantic)
    ("fieldset[data-testid*='size']",     "Size"),
    ("fieldset[aria-label*='size']",      "Size"),
    ("fieldset[data-testid*='color']",    "Color"),
    ("fieldset[aria-label*='color']",     "Color"),
    ("fieldset[data-testid*='storage']",  "Storage"),
    ("fieldset[aria-label*='storage']",   "Storage"),
    ("fieldset[data-testid*='capacity']", "Capacity"),
    ("fieldset[data-testid*='finish']",   "Finish"),
    # Generic fieldset — get name from legend
    ("fieldset",                          None),
    # Div/section pickers with explicit roles
    ("[role='radiogroup'][aria-label*='size']",     "Size"),
    ("[role='radiogroup'][aria-label*='Size']",     "Size"),
    ("[role='radiogroup'][aria-label*='color']",    "Color"),
    ("[role='radiogroup'][aria-label*='Color']",    "Color"),
    ("[role='radiogroup'][aria-label*='storage']",  "Storage"),
    ("[role='radiogroup'][aria-label*='Storage']",  "Storage"),
    ("[role='radiogroup'][aria-label*='capacity']", "Capacity"),
    ("[role='radiogroup'][aria-label*='finish']",   "Finish"),
]

_CLOUDINARY_TRANSFORM_RE = re.compile(r'^[a-z]{1,2}_[a-z0-9_,]+$')

# Option NAME noise: spec/feature headings that appear as fieldset legends
# but are not actual selectable variant axes
_OPTION_NAME_NOISE_RE = re.compile(
    r'^(?:'
    r'compare(?:\s+size)?'
    r'|catch\s+the\b'
    r'|highlights?'
    r'|features?'
    r'|specifications?'
    r'|thickness'
    r'|weight'
    r'|camera'
    r'|battery'
    r'|processor'
    r'|display'
    r'|performance'
    r'|connectivity'
    r'|network'
    r'|watch\s+(?:now|video)'
    r'|play'
    r'|video'
    r'|learn\s+more'
    r'|explore\b'
    r')',
    re.I
)


def extract_button_group_options(soup):
    """Extract variant options from button-group / radio UIs (Nike, Apple, etc.)."""
    options = []
    seen_names = set()

    for selector, hint_name in _BUTTON_GROUP_OPTION_SELECTORS:
        for container in soup.select(selector):
            # Skip inside header/nav/footer
            if container.find_parent(["header", "nav", "footer"]):
                continue

            # Derive option name from legend, aria-label, or hint
            opt_name = None
            legend = container.find("legend")
            if legend:
                opt_name = clean_text(legend.get_text(" ", strip=True))
            if not opt_name:
                opt_name = clean_text(container.get("aria-label") or "")
            if not opt_name and hint_name:
                opt_name = hint_name
            if not opt_name:
                continue

            # Trim "Select a …" or "Choose …" prefixes from label
            opt_name = re.sub(r'^(?:select|choose|pick)\s+(?:a\s+)?', '', opt_name, flags=re.I).strip()

            # Reject option names longer than 4 words (they're descriptions, not axes)
            if not opt_name or len(opt_name.split()) > 4:
                continue
            if len(opt_name) > 50:
                continue
            # Reject spec/feature headings masquerading as option names
            if _OPTION_NAME_NOISE_RE.match(opt_name):
                continue

            key = opt_name.lower()
            if key in seen_names:
                continue

            values = []
            seen_vals = set()
            for el in container.find_all(["button", "input", "label"]):
                # Skip if the button IS the legend element
                if el == legend:
                    continue
                label = (
                    el.get("aria-label")
                    or el.get("value")
                    or el.get("title")
                    or clean_text(el.get_text(" ", strip=True))
                )
                label = clean_text(label or "")
                if not label or len(label) > 40:
                    continue
                # Strip "- Sold Out" suffixes
                label = re.sub(
                    r'\s*[\u2013\u2014–-]\s*(?:sold\s*out|unavailable|out\s*of\s*stock).*',
                    '', label, flags=re.I
                ).strip()
                if not label:
                    continue
                # Skip generic CTA / marketing noise text
                if re.match(r'^(?:add\s+to|buy|select|choose|shop|view)', label, re.I):
                    continue
                if _OPTION_VALUE_NOISE_RE.match(label):
                    continue
                if _OPTION_VAL_GARBLE_RE.search(label):
                    continue
                lkey = label.lower()
                if lkey not in seen_vals:
                    seen_vals.add(lkey)
                    values.append(label)

            if len(values) >= 2:
                options.append({"name": opt_name, "values": values[:50]})
                seen_names.add(key)

    return options


# Non-product select names to reject (country, language, sort, etc.)
_SELECT_REJECT_NAMES = frozenset({
    "country", "selectcountry", "select-country", "select_country",
    "language", "selectlanguage", "lang", "locale", "region",
    "territory", "currency", "currencycode", "timezone",
    "sortby", "sort_by", "sortorder", "sort", "orderby",
    "filter", "filterby",
    "newsletter", "subscribe",
    "unit", "units",
})

# Values that look like country/region names → reject the select
_COUNTRY_SAMPLE = frozenset({
    "united states", "united kingdom", "canada", "australia", "germany",
    "france", "india", "japan", "china", "brazil", "mexico", "spain",
    "italy", "netherlands", "united arab emirates", "saudi arabia",
    "south korea", "singapore", "malaysia", "thailand", "turkey",
    "kuwait", "qatar", "oman", "bahrain",
})

_LANGUAGE_SAMPLE = frozenset({
    "english", "spanish", "french", "german", "italian", "portuguese",
    "arabic", "japanese", "chinese", "korean", "dutch", "russian",
})


def _is_product_select(select_el):
    """Return True only if a <select> element looks like a product option."""
    # Skip if inside navigation/header/footer
    if select_el.find_parent(["header", "nav", "footer"]):
        return False
    # Check name/id against known non-product selectors
    raw_name = (select_el.get("name") or select_el.get("id") or "").lower()
    normalised = raw_name.replace("-", "").replace("_", "").replace(" ", "")
    if normalised in _SELECT_REJECT_NAMES:
        return False
    # Sample the option values to detect country/language selects
    values_lower = [
        clean_text(o.get_text(" ", strip=True)).lower()
        for o in select_el.find_all("option")[:20]
    ]
    country_hits = sum(1 for v in values_lower if v in _COUNTRY_SAMPLE)
    lang_hits = sum(1 for v in values_lower if v in _LANGUAGE_SAMPLE)
    if country_hits >= 2 or lang_hits >= 2:
        return False
    # Skip "Select a ..." placeholder-only selects that have < 2 real values
    real_values = [v for v in values_lower if v and not v.startswith("select")]
    if len(real_values) < 2:
        return False
    return True


# Module-level regexes for stripping Nike-style description fragments from option values.
# "Shown: White/Photon Dust/Black/Metallic Gold" → strip prefix; "Style: HM9674-102" → drop.
_OPT_SHOWN_PREFIX_RE = re.compile(r'^Shown\s*:\s*', re.I)
_OPT_STYLE_CODE_RE   = re.compile(r'^Style\s*:\s*[A-Z0-9][A-Z0-9\-]{3,}', re.I)

_TEXT_OPTION_LABELS = [
    # (label_pattern, canonical_name)
    (re.compile(r'\bcolou?r\b', re.I),    'Color'),
    (re.compile(r'\bsize\b', re.I),       'Size'),
    (re.compile(r'\bstorage\b', re.I),    'Storage'),
    (re.compile(r'\bcapacity\b', re.I),   'Capacity'),
    (re.compile(r'\bfinish\b', re.I),     'Finish'),
    (re.compile(r'\bstyle\b', re.I),      'Style'),
    (re.compile(r'\bmodel\b', re.I),      'Model'),
    (re.compile(r'\bvariant\b', re.I),    'Variant'),
    (re.compile(r'\bwidth\b', re.I),      'Width'),
    (re.compile(r'\bmaterial\b', re.I),   'Material'),
    (re.compile(r'\bwattage\b', re.I),    'Wattage'),
    (re.compile(r'\bvoltage\b', re.I),    'Voltage'),
    (re.compile(r'\bscent\b', re.I),      'Scent'),
    (re.compile(r'\bflavou?r\b', re.I),   'Flavor'),
    (re.compile(r'\bpack(?:\s*size)?\b', re.I), 'Pack Size'),
    (re.compile(r'\bquantity\b', re.I),   'Quantity'),
]

# Regex to detect a "label: value" pattern from page text (used in Jina markdown)
_TEXT_OPTION_LINE_RE = re.compile(
    r'^[\*\-\s]*(?P<label>[A-Za-z][A-Za-z\s]{1,20}?)[\s]*[:：]\s*(?P<value>.+)$',
    re.MULTILINE
)

# UI phrases that appear when a color/size swatch button's full DOM text is
# accidentally concatenated into the option value (e.g. "White select size Save
# Model is 5'10\" and wears a size S"). Any value containing these is garbled.
_OPTION_VAL_GARBLE_RE = re.compile(
    r'\b(?:select\s+size|model\s+is\s+\d|wears\s+a\s+size|save\s+model'
    r'|add\s+to\s+bag|add\s+to\s+cart|sold\s+out\s+notify)'
    r'|(?:^|\s)Shown\s*:\s'     # Nike colorway description prefix
    r'|(?:^|\s)Style\s*:\s*[A-Z0-9]{4,}',  # Style code (e.g. "Style: HM9674-102")
    re.I,
)

_COLOR_NAMES = frozenset({
    "black", "white", "red", "blue", "green", "yellow", "orange", "purple",
    "pink", "grey", "gray", "silver", "gold", "beige", "brown", "navy",
    "teal", "cyan", "magenta", "maroon", "olive", "coral", "turquoise",
    "lavender", "cream", "ivory", "charcoal", "bronze", "rose", "tan",
    "midnight", "natural", "nude", "blush",
})

_SIZE_CODES = re.compile(
    r'^(?:X{0,3}S|X{0,3}L|[0-9]+(?:\.[05])?\s*(?:GB|TB|[Mm][Mm]|[Cc][Mm]|[Ii][Nn])?'
    r'|(?:US|EU|UK)\s*[0-9]+(?:\.[05])?'
    r'|One\s+Size'
    r'|[0-9]+x[0-9]+'
    r')$',
    re.I
)


def extract_text_based_options(page_text, existing_option_names=None):
    """Extract structured options from plain text (Jina markdown / visible text).

    Looks for labeled key:value pairs like "Color: Midnight Black" or
    "Storage: 256GB". Only extracts known option types to avoid noise.

    Returns list of {name, values} dicts (same shape as extract_options).
    """
    if not page_text:
        return []

    existing_names = {n.lower() for n in (existing_option_names or [])}
    options = []
    seen_label_keys = set()

    for m in _TEXT_OPTION_LINE_RE.finditer(page_text):
        raw_label = clean_text(m.group('label'))
        raw_value = clean_text(m.group('value'))
        if not raw_label or not raw_value:
            continue
        # Match against known labels
        canonical = None
        for pat, name in _TEXT_OPTION_LABELS:
            if pat.search(raw_label):
                canonical = name
                break
        if not canonical:
            continue
        if canonical.lower() in existing_names:
            continue
        if canonical.lower() in seen_label_keys:
            continue
        # Reject noise values
        if _OPTION_VALUE_NOISE_RE.match(raw_value):
            continue
        if len(raw_value) > 60:
            continue
        # Reject values where UI chrome was accidentally concatenated into the
        # option text (e.g. "White select size Save Model is 5'10\" and wears…")
        if _OPTION_VAL_GARBLE_RE.search(raw_value):
            continue
        # Split comma/slash-separated values
        raw_values = [v.strip() for v in re.split(r'[,/]', raw_value) if v.strip()]
        raw_values = [v for v in raw_values if v and len(v) <= 40
                      and not _OPTION_VALUE_NOISE_RE.match(v)
                      and not _OPTION_VAL_GARBLE_RE.search(v)]
        if not raw_values:
            continue
        seen_label_keys.add(canonical.lower())
        options.append({"name": canonical, "values": raw_values})

    return options


def extract_options(soup, next_product=None):
    options = []

    if next_product:
        raw_options = next_product.get("options")

        if isinstance(raw_options, list):
            for option in raw_options:
                if isinstance(option, dict):
                    opt_name = option.get("name") or ""
                    # Skip non-product option types from hydration data too
                    n = opt_name.lower().replace("-", "").replace("_", "")
                    if n in _SELECT_REJECT_NAMES:
                        continue
                    options.append({
                        "name": opt_name,
                        "values": option.get("values") if isinstance(option.get("values"), list) else []
                    })

    for select in soup.find_all("select"):
        if not _is_product_select(select):
            continue
        name = select.get("name") or select.get("id") or "Option"
        values = []
        for opt in select.find_all("option"):
            text = clean_text(opt.get_text(" ", strip=True))
            if text and not text.lower().startswith("select"):
                values.append(text)
        if values:
            options.append({
                "name": clean_text(name),
                "values": values
            })

    # Button-group options (Nike sizes, Apple storage/color, etc.)
    for bg_opt in extract_button_group_options(soup):
        existing_names = {o["name"].lower() for o in options}
        if bg_opt["name"].lower() not in existing_names:
            options.append(bg_opt)

    # Text-based options from visible page text (catches Jina markdown key:value pairs)
    page_text = soup.get_text("\n", strip=True)
    for txt_opt in extract_text_based_options(page_text, [o["name"] for o in options]):
        options.append(txt_opt)

    # ── Post-processing: strip / reject description-like values ─────────────
    # Some sites (Nike etc.) expose colorway descriptions as button labels:
    #   "Shown: White/Photon Dust/Black/Metallic Gold"  → strip "Shown: " prefix
    #   "Style: HM9674-102"                             → reject (style code)
    #   values with 3+ "/" and >20 chars                → reject (full colorway desc)
    _SHOWN_PREFIX_RE  = _OPT_SHOWN_PREFIX_RE
    _STYLE_CODE_RE    = _OPT_STYLE_CODE_RE
    clean_opts = []
    for opt in options:
        cleaned_vals = []
        for v in opt.get("values") or []:
            if _STYLE_CODE_RE.match(v):
                continue           # e.g. "Style: HM9674-102" → drop
            v = _SHOWN_PREFIX_RE.sub("", v).strip()  # strip "Shown: " prefix
            if v:
                cleaned_vals.append(v)
        if cleaned_vals:
            opt = dict(opt)
            opt["values"] = cleaned_vals
            clean_opts.append(opt)
    options = clean_opts

    return options[:20]


# =========================================================
# Breadcrumbs / ratings / URL helpers
# =========================================================

def extract_breadcrumbs(soup):
    breadcrumbs = []
    seen = set()

    selectors = [
        "nav[aria-label*='breadcrumb'] a",
        ".breadcrumb a",
        ".breadcrumbs a",
        "[class*='breadcrumb'] a"
    ]

    for selector in selectors:
        for a in soup.select(selector):
            text = clean_text(a.get_text(" ", strip=True))
            href = a.get("href")

            if text:
                key = (text.lower(), href)
                if key not in seen:
                    seen.add(key)
                    breadcrumbs.append({"text": text, "url": href})

    # JSON-LD BreadcrumbList extraction (supplements DOM breadcrumbs)
    _jsonld_crumbs = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            raw_js = script.string or script.get_text()
            if not raw_js:
                continue
            parsed = json.loads(raw_js)
            items = flatten_jsonld(parsed)
            for item in items:
                item_type = item.get("@type")
                if isinstance(item_type, list):
                    is_bcl = any(str(t).lower().endswith("breadcrumblist") for t in item_type)
                else:
                    is_bcl = str(item_type or "").lower().endswith("breadcrumblist")
                if not is_bcl:
                    continue
                elements = item.get("itemListElement") or []
                for el in elements:
                    if not isinstance(el, dict):
                        continue
                    name = el.get("name") or ""
                    item_ref = el.get("item")
                    if isinstance(item_ref, dict):
                        url_ = item_ref.get("@id") or item_ref.get("url") or None
                        if not name:
                            name = clean_text(item_ref.get("name") or "")
                    elif isinstance(item_ref, str):
                        url_ = item_ref
                    else:
                        url_ = None
                    name = clean_text(name)
                    position = el.get("position")
                    if name:
                        key = (name.lower(), url_)
                        if key not in seen:
                            seen.add(key)
                            _jsonld_crumbs.append({"text": name, "url": url_, "_pos": position})
        except Exception:
            continue

    # Sort JSON-LD crumbs by position, then append after DOM breadcrumbs
    _jsonld_crumbs.sort(key=lambda x: (x.get("_pos") is None, x.get("_pos") or 0))
    for crumb in _jsonld_crumbs:
        crumb.pop("_pos", None)
        breadcrumbs.append(crumb)

    return breadcrumbs[:20]


def _compute_discount(price, had_structured_source=False, is_js_rendered=False):
    """Return a discount dict, None (confirmed absent), or "unfetched" (exists but not retrieved).

    Decision logic for when compareAt is absent:
      - had_structured_source=True  → JSON-LD / __NEXT_DATA__ was parsed and had no compareAt
                                      → discount confirmed absent → None
      - is_js_rendered=True         → page renders via JS; sale price may exist in client state
                                      → "unfetched"
      - static HTML, no JS signals  → page rendered fully; no compareAt found = None
    """
    if not isinstance(price, dict):
        return "unfetched" if is_js_rendered else None
    current    = price.get("current")
    compare_at = price.get("compareAt")

    if compare_at and current and compare_at > current:
        saved   = round(compare_at - current, 2)
        percent = round((saved / compare_at) * 100)
        return {
            "percent":       percent,
            "savedAmount":   saved,
            "originalPrice": compare_at,
            "currentPrice":  current,
        }
    # compareAt explicitly present (even if 0 or equal) → confirmed no active discount
    if compare_at is not None:
        return None
    # compareAt absent — determine if this is an unfetched gap or confirmed absence
    if had_structured_source:
        return None          # JSON-LD / next_data had no compareAt → confirmed no discount
    if is_js_rendered:
        return "unfetched"   # JS page: sale price may exist in client-side state
    return None              # static HTML, page rendered fine, no compareAt = confirmed absent


def extract_rating(soup, jsonld_product=None):
    # ── 1. JSON-LD aggregateRating (most reliable) ────────────────────────
    if jsonld_product:
        rating = jsonld_product.get("aggregateRating")
        if isinstance(rating, dict):
            review_count = rating.get("reviewCount") or rating.get("ratingCount")
            try:
                review_count = int(review_count)
            except Exception:
                review_count = None
            return {
                "ratingValue": safe_float(rating.get("ratingValue")),
                "reviewCount": review_count
            }

    text = clean_text(soup.get_text(" ", strip=True))

    # ── 2. Aggregate-rating text patterns (prefer over per-review ratings) ─
    # BestBuy Jina: "**4.7** … Average rating based on 19 reviews"
    # Adidas Jina:  "Rating: 4.7" near "## Reviews (17944)"
    review_count = None
    agg_rating = None

    # "Average rating based on N reviews" — grab the number just before it
    m = re.search(
        r'(?:^|[^\d])(\d+\.\d{1,2})[^\n]{0,60}?average\s+rating',
        text, re.I | re.MULTILINE
    )
    if not m:
        m = re.search(
            r'average\s+rating[^\n]{0,60}?(\d+\.\d{1,2})',
            text, re.I
        )
    if m:
        agg_rating = safe_float(m.group(1))

    # "Rating: 4.7" (Adidas / generic)
    if agg_rating is None:
        m = re.search(r'\brating[:\s]+([1-5]\.\d{1,2})\b', text, re.I)
        if m:
            agg_rating = safe_float(m.group(1))

    # Review count: "based on N reviews" or "Reviews (N)"
    m2 = re.search(r'average\s+rating\s+based\s+on\s+(\d+)\s+reviews?', text, re.I)
    if not m2:
        m2 = re.search(r'reviews?\s*\((\d+)\)', text, re.I)
    if not m2:
        m2 = re.search(r'(\d{2,})\s+reviews?', text, re.I)
    if m2:
        try:
            review_count = int(m2.group(1))
        except Exception:
            pass

    if agg_rating is not None:
        return {"ratingValue": agg_rating, "reviewCount": review_count}

    # ── 3. "X out of 5" fallback — only if no aggregate found ────────────
    # Use the LAST such match to avoid picking a 5-star individual review
    # that appears before the aggregate section on pages like BestBuy.
    all_matches = list(re.finditer(r"([0-5](?:\.\d)?)\s*out of\s*5", text, re.I))
    if all_matches:
        # Prefer values < 5.0 (more likely to be aggregate than perfect review)
        for m in all_matches:
            val = safe_float(m.group(1))
            if val is not None and val < 5.0:
                # Guard: DOM-scraped rating without a count is unreliable
                if review_count is None:
                    return {"ratingValue": None, "reviewCount": None}
                return {"ratingValue": val, "reviewCount": review_count}
        # Fall back to last match (closest to review section)
        # Guard: a perfect 5.0 with no count is almost certainly an aria-label
        # artefact ("5 out of 5 stars") rather than a real aggregate — discard it.
        last_val = safe_float(all_matches[-1].group(1))
        if last_val is not None and review_count is None:
            return {"ratingValue": None, "reviewCount": None}
        return {
            "ratingValue": last_val,
            "reviewCount": review_count
        }

    return {"ratingValue": None, "reviewCount": review_count}


def get_handle_from_url(url):
    path = urlparse(url).path.strip("/")

    if not path:
        return None

    parts = path.split("/")

    # Nike product SKU should stay useful.
    if "/t/" in path:
        return parts[-1].replace(".html", "")

    for part in reversed(parts):
        part = part.replace(".html", "").strip()

        if len(part) > 5 and not part.isdigit():
            return part

    return parts[-1].replace(".html", "")


def is_real_404(soup, headers):
    status_code = headers.get("status_code") if headers else None

    h1 = soup.find("h1")
    h1_text = clean_text(h1.get_text(" ", strip=True)).lower() if h1 else ""

    title = clean_text(soup.title.string).lower() if soup.title and soup.title.string else ""

    if status_code == 404:
        return True

    if h1_text in ["404", "not found", "page not found"]:
        return True

    if title == "404" or "page not found" in title:
        return True

    return False


# =========================================================
# Jina-fallback field enrichment
# =========================================================

# Known retail/tech brand names that can appear as the first word of a product title
_KNOWN_BRANDS = frozenset({
    "asus", "dell", "hp", "lenovo", "apple", "samsung", "sony", "lg", "acer",
    "msi", "razer", "microsoft", "google", "huawei", "oneplus", "xiaomi",
    "nikon", "canon", "panasonic", "philips", "bosch", "bose", "jbl",
    "nike", "adidas", "puma", "reebok", "under armour", "new balance",
    "ikea", "dyson", "shark", "ninja", "keurig",
})

# Maps title keywords → category label
_TITLE_CATEGORY_MAP = [
    (r'\blaptop\b',         "Laptop"),
    (r'\bnotebook\b',       "Laptop"),
    (r'\bmonitor\b',        "Monitor"),
    (r'\bkeyboard\b',       "Keyboard"),
    (r'\bmouse\b',          "Mouse"),
    (r'\bheadphone',        "Headphones"),
    (r'\bearphone',         "Earphones"),
    (r'\bearbuds?\b',       "Earphones"),
    (r'\bspeaker\b',        "Speaker"),
    (r'\btablet\b',         "Tablet"),
    (r'\bsmartphone\b',     "Smartphone"),
    (r'\b(?:cell\s+)?phone\b', "Smartphone"),
    (r'\btv\b|\btelevision\b', "TV"),
    (r'\bcamera\b',         "Camera"),
    (r'\bprinter\b',        "Printer"),
    (r'\brouter\b',         "Router"),
    (r'\bssd\b|\bhard\s+drive\b|\bsolid[- ]state\b', "Storage"),
    (r'\bshoe[s]?\b|\bsneaker[s]?\b', "Shoes"),
    (r'\bboot[s]?\b',       "Shoes"),
    (r'\bshirt\b|\bjacket\b|\bpants\b|\bjeans\b', "Clothing"),
    (r'\bwatch\b',          "Watch"),
    (r'\brefrigerator\b|\bfridge\b', "Refrigerator"),
    (r'\bwasher\b|\bdryer\b', "Appliance"),
    (r'\bcoffee\s+(?:maker|machine)\b', "Coffee Maker"),
    (r'\bvacuum\b',         "Vacuum"),
]


def _extract_features_from_region_text(region_text, product_name=''):
    """Mine product region text for spec/feature bullets.

    Recognises patterns like:
      - "12MP Front Camera"
      - "Snapdragon 8 Elite for Galaxy"
      - "IP68 water resistance"
      - "4000mAh battery"
      - "Galaxy AI"

    Returns a deduplicated list of clean feature strings (max 30).
    """
    if not region_text:
        return []

    # Noise lines to skip — navigation, UI chrome, video labels
    _FEAT_LINE_NOISE_RE = re.compile(
        r'^(?:'
        r'play$'
        r'|video\s+\d+'
        r'|accessible\s+carousel'
        r'|blank\.gif'
        r'|catch\s+the\b'
        r'|compare\s+(?:size|model)'
        r'|watch\s+(?:now|video)'
        r'|learn\s+more'
        r'|explore\b'
        r'|see\s+all'
        r'|view\s+all'
        r'|buy\s+(?:now|it)'
        r'|shop\s+now'
        r'|add\s+to\s+(?:cart|bag)'
        r'|sign\s+in'
        r'|create\s+account'
        r'|open\s+my\s+menu'
        r'|terms\s+of\s+use'
        r'|privacy\s+policy'
        r'|cookie'
        r')',
        re.I
    )

    # Lines that look like real feature/spec bullets
    _FEAT_POSITIVE_RE = re.compile(
        r'(?:'
        r'\b\d+\s*(?:MP|mAh|GB|TB|nm|Hz|W|V|inch(?:es)?|mm|cm)\b'  # specs with units
        r'|IP\d+[a-z]?'         # ingress protection ratings (IP68, IPX4)
        r'|\bAI\b'              # AI branding
        r'|\bGalaxy\s+AI\b'
        r'|\bSnapdragon\b'
        r'|\bA\d+\s+(?:Bionic|chip)\b'  # Apple A-series
        r'|\bArmor\b'
        r'|\bGorilla\s+Glass\b'
        r'|\bSapphire\b'
        r'|5G|Wi-Fi|Bluetooth|NFC|USB-C|MagSafe'
        r'|OLED|AMOLED|LTPO|ProMotion'
        r'|\bwater\s+resist(?:ant|ance)\b'
        r'|\bdust\s+resist(?:ant|ance)\b'
        r'|\bfront\s+camera\b|\break\s+camera\b|\bwide\s+angle\b'
        r'|\bmemory\b|\bstorage\b|\bRAM\b'
        r'|\bbattery\b'
        r'|\bprocessor\b|\bchipset\b'
        r'|\bdisplay\b|\bscreen\b'
        r')',
        re.I
    )

    features = []
    seen = set()
    product_name_lower = (product_name or '').lower()

    for raw_line in region_text.splitlines():
        line = clean_text(raw_line)
        if not line:
            continue
        # Length guard: features are concise, not paragraphs
        word_count = len(line.split())
        if word_count < 2 or word_count > 12:
            continue
        # Skip obvious noise
        if _FEAT_LINE_NOISE_RE.match(line):
            continue
        # Skip the product name itself
        if line.lower() == product_name_lower:
            continue
        # Must contain a spec keyword/unit
        if not _FEAT_POSITIVE_RE.search(line):
            continue
        # Dedup
        key = line.lower()
        if key not in seen:
            seen.add(key)
            features.append(line)
        if len(features) >= 30:
            break

    return features


def extract_jina_product_extras(soup, url):
    """Extract fields that are only visible in Jina-converted HTML.

    Jina markdown becomes plain text — bold is `**...**`, sections are H2/H3.
    Parses:
      - Model / SKU  (``**Model:**X1607CA-BS51-CB``)
      - Web code     (``**Web Code:**19704951``)
      - Vendor       (first word of title if it's a known brand)
      - Category     (keyword scan of title)
      - compareAt    (``$699.99 SAVE $300`` → 999.99)
      - Currency     (domain/path inference, overrides $ = USD)
      - Availability (``Available to ship``)
      - Options from H3 section headings  (``### SSD Capacity: 512 GB``)
      - Warranty options  (``Not selected. 2 Years $169.99``)
      - Product code for Adidas (``Product code: M20324``)

    Returns a dict with any found values.  Absent keys mean "not found".
    """
    extras = {}
    page_text = clean_text(soup.get_text(" ", strip=True))
    pt = page_text  # short alias

    # ── Model / SKU ─────────────────────────────────────────────────────
    # Jina markdown bold: **Model:**X1607CA-BS51-CB → literal **Model:**…
    m = re.search(r'\*\*model\s*:\s*\*\*\s*([A-Z0-9][A-Z0-9\-]{3,})', pt, re.I)
    if not m:
        m = re.search(r'\bmodel\s*[:#]\s*([A-Z0-9][A-Z0-9\-]{3,})', pt, re.I)
    if m:
        extras['sku'] = m.group(1).strip()

    # ── Web code (BestBuy-style numeric product ID) ──────────────────────
    m = re.search(r'\*\*web\s+code\s*:\s*\*\*\s*(\d{5,})', pt, re.I)
    if not m:
        m = re.search(r'\bweb\s+code\s*[:#]?\s*(\d{5,})', pt, re.I)
    if m:
        extras['webCode'] = m.group(1).strip()

    # ── Product code (Adidas-style alphanumeric) ─────────────────────────
    m = re.search(r'\bproduct\s+code\s*[:#]\s*([A-Z][A-Z0-9]{4,})\b', pt, re.I)
    if m:
        extras['productCode'] = m.group(1).strip()

    # ── Vendor from title first word ─────────────────────────────────────
    title_el = soup.find("h1")
    title_text = clean_text(title_el.get_text(" ", strip=True)) if title_el else ""
    if title_text:
        first_word = title_text.split()[0] if title_text.split() else ""
        if first_word and first_word.lower() in _KNOWN_BRANDS:
            extras['vendor'] = first_word

    # ── Category from title keywords ─────────────────────────────────────
    if title_text:
        title_l = title_text.lower()
        for pattern, cat in _TITLE_CATEGORY_MAP:
            if re.search(pattern, title_l, re.I):
                extras['category'] = cat
                break

    # ── Currency from URL ─────────────────────────────────────────────────
    url_currency = infer_currency_from_url(url)
    if url_currency:
        extras['currency'] = url_currency

    # ── CompareAt from "SAVE $N" ──────────────────────────────────────────
    # e.g. "$699.99 SAVE $300" → compareAt = 699.99 + 300 = 999.99
    m = re.search(
        r'\$\s*([\d,]+(?:\.\d{1,2})?)\s+save\s+\$\s*([\d,]+(?:\.\d{1,2})?)',
        pt, re.I
    )
    if m:
        try:
            current = float(m.group(1).replace(',', ''))
            savings = float(m.group(2).replace(',', ''))
            extras['compareAt'] = round(current + savings, 2)
        except Exception:
            pass

    # ── Availability from shipping/pickup text ────────────────────────────
    if re.search(r'\bavailable\s+to\s+(?:ship|pickup|store|order)\b', pt, re.I):
        extras['availability'] = 'in_stock'
    elif re.search(r'\bsold\s+and\s+shipped\s+by\b', pt, re.I):
        extras['availability'] = 'in_stock'

    # ── Options from H3 section headings ─────────────────────────────────
    # BestBuy pattern: "### Solid-State Drive Capacity: 512 GB"
    # Then values follow as plain text lines e.g. "512 GB$699.99"
    jina_options = []
    for h3 in soup.find_all("h3"):
        h3_text = clean_text(h3.get_text(" ", strip=True))
        if not h3_text or len(h3_text) > 80:
            continue
        # Section heading must look like an option name (contains colon or
        # matches known option keywords)
        if ':' not in h3_text and not re.search(
            r'\b(?:storage|ssd|ram|memory|color|colour|finish|size|capacity|warranty|plan)\b',
            h3_text, re.I
        ):
            continue
        # Extract the option name (part before colon, or full heading)
        if ':' in h3_text:
            opt_name, _, opt_val_raw = h3_text.partition(':')
            opt_name = opt_name.strip()
            opt_val_raw = opt_val_raw.strip()
        else:
            opt_name = h3_text
            opt_val_raw = ""
        if not opt_name or len(opt_name) > 60:
            continue
        # Collect sibling text values
        values = []
        seen_vals = set()
        # Current value from heading text (e.g. "512 GB")
        if opt_val_raw:
            clean_val = re.sub(r'\$[\d,.]+.*$', '', opt_val_raw).strip()
            if clean_val and clean_val.lower() not in seen_vals:
                values.append(clean_val)
                seen_vals.add(clean_val.lower())
        # Sibling lines in the same section
        section = h3.find_parent("section")
        if section:
            for p in section.find_all("p"):
                p_text = clean_text(p.get_text(" ", strip=True))
                # Strip trailing prices
                p_text = re.sub(r'\$[\d,.]+.*$', '', p_text).strip()
                if not p_text or len(p_text) > 40:
                    continue
                if re.match(r'^(?:not\s+selected|selected|recommended|only|showing|available)',
                            p_text, re.I):
                    continue
                if p_text.lower() not in seen_vals:
                    values.append(p_text)
                    seen_vals.add(p_text.lower())
        if len(values) >= 1:
            jina_options.append({"name": opt_name, "values": values[:20]})

    # Warranty options: "2 Years $169.99" / "3 Years $254.99" pattern
    warranty_vals = []
    warranty_seen = set()
    for m in re.finditer(
        r'\b((?:no\s+plan|\d+\s+years?|\d+\s+months?)[^$\n]{0,20}?)\s*\$\s*[\d,.]+',
        pt, re.I
    ):
        val = clean_text(re.sub(r'\$.*$', '', m.group(1))).strip()
        if val and len(val) <= 30 and val.lower() not in warranty_seen:
            warranty_vals.append(val)
            warranty_seen.add(val.lower())
    if len(warranty_vals) >= 2:
        jina_options.append({"name": "Warranty", "values": warranty_vals[:10]})

    if jina_options:
        extras['jinaOptions'] = jina_options

    # ── Color / Finish from text key:value ────────────────────────────────
    # Adidas Jina: "Color: Core Black / Core Black / Gold Metallic"
    m = re.search(
        r'\bcolou?r\s*[:#]\s*(?:\*\*)?([^\n\*]{3,60})(?:\*\*)?',
        pt, re.I
    )
    if m:
        color_val = clean_text(m.group(1).strip().strip('*').strip())
        if color_val and not _OPTION_VALUE_NOISE_RE.match(color_val):
            extras['color'] = color_val

    m = re.search(
        r'\bfinish\s*[:#]\s*(?:\*\*)?([^\n\*]{3,40})(?:\*\*)?',
        pt, re.I
    )
    if m:
        finish_val = clean_text(m.group(1).strip().strip('*').strip())
        if finish_val and not _OPTION_VALUE_NOISE_RE.match(finish_val):
            extras['finish'] = finish_val

    # ── Breadcrumbs from "Home > Category > Product" navigation text ──────
    # Jina often renders breadcrumbs as plain text separated by ">" or "/"
    breadcrumb_candidates = []
    for sep_pat in (r'(?<!\S)>(?!\S)', r'\s/\s'):
        for text_node in soup.find_all(string=re.compile(r'\s[>/]\s')):
            parent = text_node.parent
            if parent and parent.name in ('nav', 'ol', 'ul', 'div', 'p', 'span'):
                parts = re.split(r'\s*[>/]\s*', str(text_node).strip())
                parts = [clean_text(p) for p in parts if clean_text(p)]
                if 2 <= len(parts) <= 8:
                    breadcrumb_candidates = parts
                    break
        if breadcrumb_candidates:
            break

    # Also scan for structured nav > breadcrumb text in Jina-converted HTML
    if not breadcrumb_candidates:
        for nav in soup.find_all(['nav', 'ol'], class_=re.compile(r'breadcrumb', re.I)):
            links = nav.find_all('a')
            texts = [clean_text(a.get_text(" ", strip=True)) for a in links]
            texts = [t for t in texts if t]
            if len(texts) >= 2:
                breadcrumb_candidates = texts
                break

    if len(breadcrumb_candidates) >= 2:
        extras['jinaBreadcrumbs'] = breadcrumb_candidates

    # ── Images from <img> tags (for Adidas/Jina pages that have them) ─────
    jina_images = []
    seen_jina_img_keys = set()
    for img in soup.find_all('img'):
        src = img.get('src') or img.get('data-src') or img.get('data-lazy-src') or ''
        if not src:
            continue
        canon_key, resolved = canonicalize_image_url(src, url)
        if not canon_key or not resolved:
            continue
        if canon_key in seen_jina_img_keys:
            continue
        if not is_good_product_image(resolved):
            continue
        seen_jina_img_keys.add(canon_key)
        jina_images.append(resolved)
        if len(jina_images) >= 20:
            break

    if jina_images:
        extras['jinaImages'] = jina_images

    return extras


# =========================================================
# Main analyzer
# =========================================================

def analyze_product(self, url, html, headers, page_type, level1):
    result = self.base_result(url, html, headers, page_type, level1)

    soup = BeautifulSoup(html or "", "lxml")

    detected_platform = level1.get("platform", "Unknown") if level1 else "Unknown"

    result["platform"] = detected_platform
    result["page"]["pageType"] = "product"

    if is_real_404(soup, headers or {}):
        result["success"] = False
        result["content"] = {
            "productName": None,
            "notFound": True
        }
        result["ecommerce"] = {
            "product": None,
            "notFound": True
        }
        result["products"] = []
        result["source"] = {
            "extractor": "Unknown Product Extractor",
            "extractorFamily": "Unknown",
            "platformDetected": detected_platform,
            "confidence": 0.1,
            "reason": "Product URL returned 404/not found."
        }
        return result

    jsonld_products = extract_jsonld_products(soup)
    jsonld_product = jsonld_products[0] if jsonld_products else None

    next_data = extract_next_data(soup)
    next_product = None
    if next_data:
        # Try known paths first (faster, more precise)
        next_product = _extract_next_product_from_known_paths(next_data)
        if not next_product:
            # Generic scan: walk the full JSON tree
            next_products = find_product_like_objects(next_data)
            next_product = next_products[0] if next_products else None

    title = extract_title(soup, jsonld_product, next_product)
    description = extract_description(soup, jsonld_product, next_product)
    price = extract_price(soup, html, jsonld_product, next_product)
    availability = extract_availability(soup, jsonld_product, next_product)

    # Derive product slug for image scoring
    product_slug = _get_slug_from_url(url)

    # ── Product region: narrow extraction scope away from nav/footer noise ──
    product_region = extract_product_region(soup, title or '', url)

    # ── Scored image pipeline ──────────────────────────────────────────────
    # Collect all image candidates; score_image_candidate() ranks them.
    # The scored list is already sorted by score DESC in extract_images_from_dom().
    scored_dom_images = extract_images_from_dom(
        soup,
        product_slug=product_slug,
        product_name=title or '',
        product_region=product_region,
    )

    # Normalise JSON-LD and hydration images through the same scoring pipeline
    structured_images = []
    if jsonld_product:
        image_data = jsonld_product.get("image")
        if isinstance(image_data, list):
            structured_images.extend(image_data)
        elif isinstance(image_data, str):
            structured_images.append(image_data)

    if next_product:
        image_data = (
            next_product.get("images")
            or next_product.get("image")
            or next_product.get("media")
        )
        if isinstance(image_data, list):
            for img in image_data:
                if isinstance(img, str):
                    structured_images.append(img)
                elif isinstance(img, dict):
                    src = img.get("src") or img.get("url")
                    if src:
                        structured_images.append(src)
        elif isinstance(image_data, str):
            structured_images.append(image_data)

    # Merge structured + DOM images; deduplicate; score-rank
    seen_img_keys = set()
    scored_all = []

    def _score_and_add(raw, base=url):
        src = normalize_image_candidate(raw) if not isinstance(raw, str) else raw
        if not src:
            return
        canon_key, resolved = canonicalize_image_url(src, base)
        if not canon_key or canon_key in seen_img_keys:
            return
        if not is_good_product_image(resolved):
            return
        if is_context_rejection(resolved, url):
            return
        sc = score_image_candidate(resolved, product_slug, title or '')
        if sc < -50:
            return
        seen_img_keys.add(canon_key)
        scored_all.append((sc, resolved))

    for img in structured_images:
        _score_and_add(img)
    for img in scored_dom_images:
        _score_and_add(img)

    scored_all.sort(key=lambda x: x[0], reverse=True)
    clean_images = [u for _, u in scored_all[:30]]

    # Last-resort fallback: og:image
    if not clean_images:
        og_img = get_meta(soup, property_name="og:image")
        if og_img:
            _score_and_add(og_img)
            clean_images = [u for _, u in scored_all[:30]]

    variants = extract_variants(next_product, jsonld_product)
    # Pass product_region so options extraction stays inside the product section
    options = extract_options(product_region, next_product)

    # ── DOM-level variant fallback (Playwright __DOM_VARIANTS__ injection) ────────
    # When Playwright extracted live DOM size/color buttons and injected them as
    # __DOM_VARIANTS__, use that data to fill gaps that __NEXT_DATA__ couldn't cover.
    if not variants or not options:
        _dom_v_tag = soup.find("script", {"id": "__DOM_VARIANTS__"})
        if _dom_v_tag:
            try:
                _dom_data = json.loads(_dom_v_tag.string or "{}")
                _dom_variants = _dom_data.get("variants") or []
                _dom_options  = _dom_data.get("options") or {}
                if not variants and _dom_variants:
                    variants = [_normalise_variant(v) for v in _dom_variants if isinstance(v, dict)]
                    print(f"DOM VARIANTS: extracted {len(variants)} variants from __DOM_VARIANTS__")
                if not options and _dom_options:
                    _dv_opts = []
                    for _k, _vals in _dom_options.items():
                        _clean = []
                        for _x in _vals:
                            if not isinstance(_x, dict): continue
                            _v = (_x.get("value") or "").strip()
                            if _OPT_STYLE_CODE_RE.match(_v): continue      # drop "Style: HM9674-102"
                            _v = _OPT_SHOWN_PREFIX_RE.sub("", _v).strip()  # strip "Shown: " prefix
                            if _v:
                                _clean.append(_v)
                        if _clean:
                            _dv_opts.append({"name": _k, "values": _clean})
                    if _dv_opts:
                        options = _dv_opts
                        print(f"DOM OPTIONS: extracted {len(options)} option group(s) from __DOM_VARIANTS__")
            except Exception as _dv_err:
                print(f"DOM VARIANTS parse error: {_dv_err}")

    # ── Structured-source flag ───────────────────────────────────────────────────
    # If JSON-LD or __NEXT_DATA__ was parsed, missing fields are genuinely absent.
    # If neither was available, check whether the page is JS-rendered — if so,
    # the data probably EXISTS but lives in JS state we couldn't reach.
    _has_structured_source = bool(next_product or jsonld_product)

    _html_l = (html or "").lower()
    _JS_SIGNALS = ("__next_data__", "/_next/static", "__nuxt__", "webpack", "react-dom")
    _JS_PLATFORMS = ("Next.js / React", "Next.js", "React", "Vue", "Nuxt")
    _is_js_rendered = (
        detected_platform in _JS_PLATFORMS
        or any(s in _html_l for s in _JS_SIGNALS)
    )

    # variants: confirmed absent when structured source had no variants;
    #           unfetched when JS-rendered with no structured source.
    if not variants:
        if _has_structured_source:
            variants = []           # confirmed: structured data had no variants
        elif _is_js_rendered:
            variants = "unfetched"  # JS page — variants are in client-side state
        else:
            variants = []           # static HTML, nothing found = confirmed absent

    # options: same logic
    if not options:
        if _has_structured_source:
            options = []
        elif _is_js_rendered:
            options = "unfetched"
        else:
            options = []
    breadcrumbs = extract_breadcrumbs(soup)
    rating = extract_rating(soup, jsonld_product)

    # --- Jina extras: fill gaps from Jina-converted markdown pages ---
    jina_extras = extract_jina_product_extras(soup, url)

    # Currency: URL domain overrides first (most reliable); Jina extras fills if still absent.
    url_currency = infer_currency_from_url(url)
    if url_currency:
        price["currency"] = url_currency
    elif jina_extras.get("currency") and not price.get("currency"):
        price["currency"] = jina_extras["currency"]

    # compareAt: fill if missing
    if jina_extras.get("compareAt") and not price.get("compareAt"):
        price["compareAt"] = jina_extras["compareAt"]

    # availability: override only when current value is unknown/None
    # NOTE: availability is a dict — check .get("status"), not the dict itself.
    if jina_extras.get("availability") and availability.get("status") == "unknown":
        availability = {
            "status": jina_extras["availability"],
            "label": "In stock" if jina_extras["availability"] == "in_stock" else jina_extras["availability"].replace("_", " ").title(),
            "inStock": jina_extras["availability"] in ("in_stock", "preorder"),
            "stockTextRaw": "jina_extras"
        }

    # options: merge jina options when standard extraction found nothing
    # (also replaces the "unfetched" sentinel when jina actually has data)
    if jina_extras.get("jinaOptions") and (not options or options == "unfetched"):
        options = jina_extras["jinaOptions"]

    # sku / productCode: carry forward to product dict
    _jina_sku = jina_extras.get("sku") or jina_extras.get("productCode")
    _jina_web_code = jina_extras.get("webCode")

    # vendor: fill when JSON-LD brand is absent — try jina, then URL/context inference
    _jina_vendor = jina_extras.get("vendor")
    _context_vendor = infer_vendor_from_context(url, soup, title)

    # category: fill when breadcrumbs are absent — try jina, then URL inference
    _jina_category = jina_extras.get("category")
    _url_category = infer_category_from_url(url, title)

    # Jina breadcrumbs: use when DOM breadcrumbs are empty
    _jina_breadcrumbs = jina_extras.get("jinaBreadcrumbs", [])
    if not breadcrumbs and _jina_breadcrumbs:
        breadcrumbs = [{"text": t, "url": None} for t in _jina_breadcrumbs]

    # Jina images: append to scored pipeline when no images found yet
    if not clean_images and jina_extras.get("jinaImages"):
        for ji in jina_extras["jinaImages"]:
            _score_and_add(ji)
        scored_all.sort(key=lambda x: x[0], reverse=True)
        clean_images = [u for _, u in scored_all[:30]]

    # color from jina extras → add to options if not already present
    if jina_extras.get("color"):
        existing_opt_names = {o["name"].lower() for o in options}
        if "color" not in existing_opt_names and "colour" not in existing_opt_names:
            options.append({"name": "Color", "values": [jina_extras["color"]]})
    if jina_extras.get("finish"):
        existing_opt_names = {o["name"].lower() for o in options}
        if "finish" not in existing_opt_names:
            options.append({"name": "Finish", "values": [jina_extras["finish"]]})

    _desc_features, _desc_benefits, _desc_specs = split_description_to_features(description)

    # ── Feature extraction from product region text ───────────────────────
    # When standard description extraction found few features, mine the product
    # region for bullet-style spec lines (e.g. "12MP Front Camera", "IP68", "12GB RAM")
    if len(_desc_features) < 3 and product_region is not None:
        region_text = product_region.get_text("\n", strip=True)
        _region_features = _extract_features_from_region_text(region_text, title or '')
        existing_lower = {f.lower() for f in _desc_features}
        for feat in _region_features:
            if feat.lower() not in existing_lower:
                _desc_features.append(feat)
                existing_lower.add(feat.lower())

    # -- Field confidence tracking --
    # Infers the source and reliability of each key output field using
    # evidence already available in analyze_product. Conservative by design:
    # prefer lower confidence over inflated scores.

    # title
    if jsonld_product and jsonld_product.get("name"):
        _fc_title = {"source": "jsonld", "confidence": 0.9}
    elif next_product and (next_product.get("title") or next_product.get("name") or next_product.get("productName")):
        _fc_title = {"source": "next_data", "confidence": 0.8}
    elif title:
        _fc_title = {"source": "dom", "confidence": 0.65}
    else:
        _fc_title = {"source": "missing", "confidence": 0.0}

    # brand
    _raw_brand_check = normalize_brand(jsonld_product.get("brand")) if jsonld_product else None
    if _raw_brand_check:
        _fc_brand = {"source": "jsonld", "confidence": 0.9}
    elif _jina_vendor:
        _fc_brand = {"source": "jina", "confidence": 0.6}
    elif _context_vendor:
        _fc_brand = {"source": "domain_inferred", "confidence": 0.7}
    else:
        _fc_brand = {"source": "missing", "confidence": 0.0}

    # price
    _offers_present = bool(jsonld_product and jsonld_product.get("offers"))
    if _offers_present and price.get("current") is not None:
        _fc_price = {"source": "jsonld", "confidence": 0.9}
    elif next_product and price.get("current") is not None:
        _fc_price = {"source": "next_data", "confidence": 0.85}
    elif price.get("current") is not None:
        _fc_price = {"source": "dom", "confidence": 0.6}
    else:
        _fc_price = {"source": "missing", "confidence": 0.0}

    # availability
    _av_raw = str(availability.get("stockTextRaw") or "")
    _av_status = availability.get("status", "unknown")
    if _av_status == "unknown":
        _fc_avail = {"source": "missing", "confidence": 0.0}
    elif "schema.org" in _av_raw.lower() or _av_raw.lower() in {"instock", "outofstock", "preorder", "discontinued"}:
        _fc_avail = {"source": "jsonld", "confidence": 0.9}
    elif _av_raw == "jina_extras":
        _fc_avail = {"source": "jina", "confidence": 0.65}
    elif "button" in _av_raw or "picker" in _av_raw:
        _fc_avail = {"source": "button_state", "confidence": 0.75}
    elif _av_raw:
        _fc_avail = {"source": "text", "confidence": 0.6}
    else:
        _fc_avail = {"source": "missing", "confidence": 0.0}

    # images
    _img_count = len(clean_images)
    _imgs_from_jsonld = bool(jsonld_product and jsonld_product.get("image"))
    _imgs_from_next = bool(structured_images and not _imgs_from_jsonld)
    _imgs_from_jina = bool(
        jina_extras.get("jinaImages") and _img_count > 0 and not structured_images
    )
    if _img_count == 0:
        _fc_images = {"source": "missing", "confidence": 0.0, "imageCount": 0}
    elif _imgs_from_jsonld:
        _fc_images = {"source": "jsonld", "confidence": 0.85, "imageCount": _img_count}
    elif _imgs_from_next:
        _fc_images = {"source": "next_data", "confidence": 0.85, "imageCount": _img_count}
    elif _imgs_from_jina:
        _fc_images = {"source": "jina", "confidence": 0.65, "imageCount": _img_count}
    else:
        _fc_images = {"source": "dom", "confidence": 0.7, "imageCount": _img_count}

    # description
    if jsonld_product and jsonld_product.get("description") and description:
        _fc_desc = {"source": "jsonld", "confidence": 0.85}
    elif next_product and (
        next_product.get("description")
        or next_product.get("shortDescription")
        or next_product.get("productDescription")
    ) and description:
        _fc_desc = {"source": "next_data", "confidence": 0.8}
    elif description:
        _fc_desc = {"source": "dom", "confidence": 0.65}
    else:
        _fc_desc = {"source": "missing", "confidence": 0.0}

    # breadcrumbs
    _bc_count = len(breadcrumbs)
    if _bc_count == 0:
        _fc_bc = {"source": "missing", "confidence": 0.0, "count": 0}
    else:
        _has_abs_url = any((b.get("url") or "").startswith("http") for b in breadcrumbs)
        _all_null_url = all(b.get("url") is None for b in breadcrumbs)
        if _has_abs_url:
            _fc_bc = {"source": "jsonld", "confidence": 0.85, "count": _bc_count}
        elif _all_null_url and _jina_breadcrumbs:
            _fc_bc = {"source": "jina", "confidence": 0.6, "count": _bc_count}
        else:
            _fc_bc = {"source": "dom", "confidence": 0.7, "count": _bc_count}

    _product_discount = _compute_discount(price, had_structured_source=_has_structured_source, is_js_rendered=_is_js_rendered)

    field_confidence = {
        "title": _fc_title,
        "brand": _fc_brand,
        "price": _fc_price,
        "availability": _fc_avail,
        "images": _fc_images,
        "description": _fc_desc,
        "breadcrumbs": _fc_bc,
        "variants": (
            {"source": "unfetched", "confidence": 0.0}
            if variants == "unfetched"
            else {"source": "next_data" if next_product else "jsonld" if jsonld_product else "dom", "confidence": 0.85 if (next_product or jsonld_product) else 0.6, "count": len(variants)}
        ),
        "options": (
            {"source": "unfetched", "confidence": 0.0}
            if options == "unfetched"
            else {"source": "next_data" if next_product else "jsonld" if jsonld_product else "dom", "confidence": 0.85 if (next_product or jsonld_product) else 0.6, "count": len(options)}
        ),
        "discount": (
            {"source": "unfetched", "confidence": 0.0}
            if _product_discount == "unfetched"
            else {"source": "computed", "confidence": 0.9}
            if isinstance(_product_discount, dict)
            else {"source": "computed", "confidence": 0.85}
        ),
    }

    confidence = 0.55

    if jsonld_product:
        confidence = 0.9
    elif next_product:
        confidence = 0.85
    elif title and price.get("current") and clean_images:
        confidence = 0.75
    elif title and clean_images:
        confidence = 0.65

    product = {
        "rank": 1,
        "name": title,
        "handle": get_handle_from_url(url),
        "productUrl": url,
        "imageUrl": clean_images[0] if clean_images else None,
        "additionalImageUrls": clean_images[1:30],
        "price": price,
        "availability": availability,
        "category": (breadcrumbs[-1]["text"] if breadcrumbs else None) or _jina_category or _url_category,
        "vendor": (normalize_brand(jsonld_product.get("brand")) if jsonld_product else None) or _jina_vendor or _context_vendor,
        "brand": (normalize_brand(jsonld_product.get("brand")) if jsonld_product else None) or _jina_vendor or _context_vendor,
        "discount": _product_discount,
        "shortDescription": description,
        "description": {
            "html": None,
            "text": description,
            "bullets": [],
            "headings": [],
            "features": _desc_features,
            "benefits": _desc_benefits,
            "usage": [],
            "specifications": _desc_specs
        },
        "sku": (jsonld_product.get("sku") if jsonld_product else None) or _jina_sku,
        "webCode": _jina_web_code,
        "options": options,
        "variants": variants,
        "breadcrumbs": breadcrumbs,
        "rating": rating,
        "metrics": {
            "variantCount": len(variants) if isinstance(variants, list) else None,
            "availableVariantCount": len([v for v in variants if isinstance(v, dict) and v.get("available")]) if isinstance(variants, list) else None,
            "imageCount": len(clean_images),
            "hasMultiplePrices": bool(price.get("compareAt")),
            "hasOptions": bool(options) if not isinstance(options, str) else None,
        },
        "fieldConfidence": field_confidence,
        "source": {
            "jsonLdFound": bool(jsonld_product),
            "nextDataFound": bool(next_product),
            "confidence": confidence
        }
    }

    result["content"] = {
        "productName": title,
        "productDescription": product["description"],
        "breadcrumbs": breadcrumbs
    }

    result["ecommerce"] = {
        "product": product,
        "price": price,
        "availability": availability,
        "variants": variants,
        "options": options,
        "metrics": product["metrics"]
    }

    result["products"] = [product]

    result["source"] = {
        "extractor": "Unknown Product Extractor",
        "extractorFamily": "Unknown",
        "platformDetected": detected_platform,
        "confidence": confidence,
    }
    return result
