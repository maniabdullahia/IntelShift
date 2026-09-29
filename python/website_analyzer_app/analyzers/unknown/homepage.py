"""Unknown homepage extractor -- production-ready for:
  SaaS/software, WordPress plugin, local restaurant, security/service,
  brand ecommerce, product-family brand, editorial campaign, Jina markdown.
"""
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Footer / nav heading patterns -- stop section extraction here
_FOOTER_HEADING_RE = re.compile(
    r'^\s*(?:footer|navigation|apple\s*footer|shop\s+and\s+learn|'
    r'apple\s+wallet|entertainment|apple\s+store|for\s+business|'
    r'for\s+education|for\s+healthcare|for\s+government|apple\s+values|'
    r'about\s+apple|account|privacy\s*policy|terms(?:\s+and\s+conditions)?|'
    r'sitemap|contact\s+us|cookie|legal|support|newsroom|investor|'
    r'careers?|copyright|all\s+rights\s+reserved|site\s+info|'
    r'quick\s+links|useful\s+links|company\s+info|'
    r'select\s+your\s+country(?:/region)?|samsung\s+offer\s+programs?|'
    r'shop\s+explore\s+shop|'
    # Samsung global nav headings
    r'shop\s+by\s+category|accessible\s+menu|sign\s+in\s*/\s*create|'
    r'my\s+(?:page|orders|cart)|product\s+registration|your\s+cart\s+is\s+empty|'
    r'layer\s+popup|check\s+preferences|popular\s+searches|'
    r'buy\s+direct\s+get\s+more|samsung\s+experience\s+stores?'
    r')\s*$',
    re.I,
)

# Samsung: known headings that mark the START of real homepage content
# (everything before the first matching section is nav/preamble)
_SAMSUNG_REAL_START_RE = re.compile(
    r'experience\s+a\s+whole\s+new|father.?s\s+day|'
    r'answering\s+your\s+passion|laundry\s+day|'
    r'recommended\s+for\s+you|explore\s+the\s+stor|'
    r'made\s+for\s+the\s+moment|one\s+on\s+anyone|'
    r'discover\s+galaxy|new\s+galaxy|galaxy\s+ai|'
    r'get\s+more\s+with\s+galaxy|everyday\s+essentials',
    re.I,
)

# Nike: known headings that mark the START of real campaign content
# (everything before the first matching section is GNB / nav preamble)
_NIKE_REAL_START_RE = re.compile(
    r'no\s+final\s+whistle|no\s+under|only\s+dogs?|'
    r'one\s+on\s+anyone|no\s+sugarcoating|'
    r'made\s+for\s+the\s+moment|joga\s+sinistro|'
    r'engineered\s+for\s+every\s+move|'
    r'meet\s+the\s+future|shop\s+(?:kd\b|golf\b|soccer\s+cleats)|'
    r'what(?:\'s|\s+is)\s+new|latest\s+drops?|drop\s+of\s+the\s+week|'
    r'season(?:al)?\s+must[\s-]haves?|trending(?:\s+now)?|'
    r'new\s+(?:releases?|arrivals?|drops?)|rep\s+your\s+team',
    re.I,
)

# Brand-specific product URL path patterns (Samsung, LG, Sony style)
# Requires: /category[suffix]/product-slug with slug ≥5 chars
_BRAND_PRODUCT_PATH_RE = re.compile(
    r'/(?:smartphones?|tablets?|televisions?|home-?theater|computing|laptops?|'
    r'monitors?|audio(?:-sound)?|cameras?|wearables?|appliances?|mobile|'
    r'galaxy|tvs?|phones?|watches?|earbuds?|headphones?|washers?|refrigerators?)'
    r'[^/]*/[a-z0-9][a-z0-9\-_]{4,}(?:/[a-z0-9][a-z0-9\-_]{4,})?/?(?:\?|$)',
    re.I,
)

# CSS class fragments indicating footer/cookie/legal wrappers
_FOOTER_CLASS_RE = re.compile(
    r'footer|site-footer|nav-footer|bottom-bar|cookie-banner|'
    r'consent|gdpr|legal-footer|copyright|site-info|colophon|'
    r'back-to-top|sticky-bar',
    re.I,
)

# CTAs -- exact text values to reject (footer/nav/support links)
_CTA_REJECT_EXACT = {
    "find a store", "help", "join us", "sign in", "log in", "login",
    "account", "sitemap", "careers", "newsroom", "privacy",
    "privacy policy", "terms", "terms and conditions", "cookie policy",
    "cookie settings", "legal", "accessibility", "investors",
    "shopping help", "contact apple", "shop for business",
    "shop for k-12", "shop for college", "shop for veterans",
    "shop for military", "shop for k12", "order status", "returns",
    "shipping", "manage your apple id", "apple id", "icloud",
    "newsletter", "unsubscribe", "sign up for emails",
    "about", "about us", "contact us", "our story",
    "sustainability", "responsibility",
    # Shopping utility / nav
    "bag", "cart", "checkout", "wishlist", "0 items", "watch now",
    # Samsung global-nav / program links (not homepage CTAs)
    "special offers", "shop explore shop", "buy direct get more",
    "samsung offer programs", "samsung experience stores",
    "tv & audio offers", "explore refrigerators", "explore laundry",
    "appliance offers", "monitor offers",
    "support home", "order help", "product registration",
    "my page", "my orders", "your cart is empty",
    "check preferences", "popular searches",
    # Generic UI noise
    "close", "previous", "next", "skip",
    # Samsung nav / support links that look like CTAs but aren't
    "samsung vision ai", "shop home", "explore", "warranty information",
    "service center", "samsung account faq", "samsung community",
    "request a repair", "track repair", "how to recycle",
    "why samsung account", "slide-in electric range recall",
    # Nav labels that may bleed into hero / CTA extraction
    "my account",
}

# URL path fragments that disqualify a CTA link
_CTA_REJECT_URL_PARTS = (
    "/privacy", "/terms", "/cookie", "/legal", "/sitemap",
    "/careers", "/newsroom", "/investor", "/accessibility",
    "/help", "/support", "/account", "/login", "/signin",
    "/signup", "/membership", "/about-us", "/about_us",
    "/newsletter", "/unsubscribe",
    # Shopping utility paths — not homepage CTAs
    "/bag", "/cart", "/checkout", "/wishlist",
)

# CTA action pattern -- link text must contain at least one of these
_CTA_ACTION_RE = re.compile(
    r'\b(?:shop|buy|get\s+started|start|explore|discover|learn\s+more|'
    r'book|try|demo|view\s+(?:all|demo|products|collection|menu|pricing)|'
    r'order|reserve|call|get\s+(?:a\s+)?(?:quote|estimate)|'
    r'sign\s+up(?:\s+for)?|contact\s+sales|request\s+(?:a\s+)?demo|'
    r'see\s+(?:all|more|menu|products)|apply(?:\s+now)?|'
    r'rep\s+your\s+team|read\s+more)\b',
    re.I,
)

# Phone number -- valid 7-15 digit string (not year ranges)
_PHONE_DIGITS_RE = re.compile(
    r'(?<!\d)(?:\+\d{1,3}[\s\-\.]?)?\(?\d{2,4}\)?[\s\-\.]?\d{3,4}[\s\-\.]?\d{3,5}(?!\d)'
)
_YEAR_RANGE_RE = re.compile(r'\b(?:19|20)\d{2}\s*[--]\s*(?:19|20)?\d{2,4}\b')
_COPYRIGHT_RE = re.compile(r'©\s*\d{4}')

# Repeated-text heading detector ("Shop and Learn Shop and Learn")
_DOUBLED_TEXT_RE = re.compile(r'^(.{5,}?)\s+\1$')

# SaaS pricing plan patterns
_PLAN_PRICE_RE = re.compile(
    r'(?P<name>[A-Za-z][A-Za-z\s]{2,30}(?:Plan|License|Tier)?)\s*'
    r'(?:Save[^$£€\n]*?)?\s*[$£€]\s*(?P<amount>[\d,]+)'
    r'(?:\s*(?:per|/)\s*(?P<period>year|month|mo|yr|annual))?',
    re.I,
)

# Restaurant menu price patterns (numeric, no currency symbol)
# Supports em-dash / en-dash / double-dash / equals separators and PKR/INR prefix:
#   "Finger fish (6pcs) — 1975"       (em dash U+2014)
#   "Cheese Naan — 715"
#   "Chicken Karahi — H 2050"         (H = half, prefix)
#   "Murgh Tikka Boti (12pcs) 1695"   (space only)
#   "Mint Raita = PKR 369"            (= separator + currency prefix)
#   "Chicken Cheese Kebab (4pcs) PKR 2195"  (space + currency prefix)
_MENU_PRICE_RE = re.compile(
    r'\b([A-Za-z][A-Za-z\d\s&\(\)\.\/\-\']{3,60}?)'
    r'(?:\s*(?:—|–|-{2,}|=)\s*(?:[HF]\s+)?(?:(?:PKR|INR|Rs\.?|AED|SAR|USD|GBP|EUR)\s*)?'
    r'|\s+(?:PKR|INR|Rs\.?|AED|SAR|USD|GBP|EUR)\s*'
    r'|\s{1,8})'
    r'(\d{3,6})\b(?!\s*%)',
    re.M,
)

# Restaurant: Half/Full (H/F) price variant pattern
# Matches: "Chicken Qoila Karahi — H PKR 2150 / F PKR 3150"
#           "Murgh Tikka — H 1950 / F 2950"
_MENU_HF_PRICE_RE = re.compile(
    r'\b([A-Za-z][A-Za-z\d\s&\(\)\.\/\-\']{3,60}?)'
    r'(?:\s*(?:—|–|-{2,}|=)\s*|\s+)'
    r'H\s*(?:PKR|INR|Rs\.?|AED|SAR|USD|GBP|EUR)?\s*(\d{3,6})'
    r'\s*[/|]\s*'
    r'F\s*(?:PKR|INR|Rs\.?|AED|SAR|USD|GBP|EUR)?\s*(\d{3,6})\b',
    re.M | re.I,
)

# Trade-in / promotional credit patterns (Apple)
_TRADE_IN_RE = re.compile(
    r'(?:trade.in|credit|get\s+up\s+to|up\s+to)\s+\$[\d,]+',
    re.I,
)

# Known brand domain overrides (bypass scoring for high-confidence brands)
_DOMAIN_OVERRIDES = {
    "apple.com": {
        "primaryModel": "ecommerce_brand",
        "secondaryModel": "product_family_homepage",
        "industry": "consumer electronics / technology",
        "homepageStyle": ["brand_campaign", "product_family"],
    },
    "samsung.com": {
        "primaryModel": "ecommerce_brand",
        "secondaryModel": "multi_category_ecommerce_brand",
        "industry": "consumer electronics / technology",
        "homepageStyle": ["featured_collections", "product_family"],
    },
    "nike.com": {
        "primaryModel": "ecommerce_brand",
        "secondaryModel": "brand_editorial_homepage",
        "industry": "apparel & footwear",
        "homepageStyle": ["brand_campaign"],
    },
}

# Video player UI noise lines injected by Jina for video-heavy pages (Nike, etc.)
# Also covers Samsung modal/carousel UI noise injected into section text.
_VIDEO_NOISE_LINES = frozenset([
    "current time", "0:00", "duration", "stream type", "live", "1x",
    "chapters", "descriptions off, selected",
    "captions settings, opens captions settings dialog",
    "captions off, selected", "en (main), selected",
    # Samsung UI elements that leak into section text
    "login using samsung account",
    "login using your samsung account",          # variant WITH "your"
    "login using your samsung account continue as a guest",
    "continue as a guest", "continue as guest",
    "close close", "previous next",
    "layer popup", "check preferences",
])
_VIDEO_LANG_RE = re.compile(
    r'^(?:català|čeština|dansk|deutsch|english(?:\s+\(united\s+kingdom\))?|'
    r'español\s+\((?:latinoamérica|españa)\)|français|magyar|italiano|'
    r'norsk\s+bokmål|nederlands|polski|português\s+\((?:brasil|portugal)\)|'
    r'svenska|türkçe|ελληνικά|русский|日本語|한국어|简体中文|繁體中文|ภาษาไทย)\s*$',
    re.I,
)

# Strips full HTML5 video-player modal dialog blocks from section text.
# Pattern: "This is a modal window. Beginning of dialog window. … End of dialog window."
# Nike (and other video-heavy pages) embed these accessibility dialogs inline.
_MODAL_DIALOG_RE = re.compile(
    r'This\s+is\s+a\s+modal\s+window\..*?End\s+of\s+dialog\s+window\.',
    re.I | re.S,
)

# Video player status fragments that appear before/after the modal block:
# "Seek to live, currently behind live LIVE Remaining Time-0:15 Playback Rate
#  Descriptions Captions … Audio Track Alternate Audio, selected"
_VIDEO_PLAYER_FRAGMENT_RE = re.compile(
    r'(?:'
    r'Seek\s+to\s+live,?\s+currently\s+behind\s+live\s+LIVE\s+Remaining\s+Time[-\s]*[\d:]+\s*'
    r'Playback\s+Rate\s+Descriptions?\s+Captions?\s*(?:Captions?\s+)?'
    r'Audio\s+Track\s+Alternate\s+Audio,?\s+selected'
    r'|Beginning\s+of\s+dialog\s+window'
    r'|Escape\s+will\s+cancel\s+and\s+close\s+the\s+window'
    r'|Text\s+(?:Color|Edge\s+Style)\s+Transparency'
    r'|Background\s+Color\s+Transparency'
    r'|Window\s+Color\s+Transparency'
    r'|Font\s+(?:Size|Family|Edge\s+Style)'
    r'|Reset\s+restore\s+all\s+settings\s+to\s+the\s+default\s+values'
    r'|Done\s+Close\s+Modal\s+Dialog'
    r')',
    re.I,
)


def _strip_video_player_noise(text):
    """Remove HTML5 video-player modal dialog blocks and status fragments
    that Jina injects into section text on video-heavy pages (Nike, etc.)."""
    if not text:
        return text
    # Strip full modal dialog block first (greedy, multi-line)
    text = _MODAL_DIALOG_RE.sub('', text)
    # Strip any remaining status-line fragments sentence-by-sentence
    if _VIDEO_PLAYER_FRAGMENT_RE.search(text):
        # Split on sentence boundaries, drop contaminated sentences
        parts = re.split(r'(?<=[.!?])\s+', text)
        clean = [p for p in parts if not _VIDEO_PLAYER_FRAGMENT_RE.search(p)]
        text = ' '.join(clean)
    return re.sub(r'\s{2,}', ' ', text).strip()

# Service list headings for service businesses
_SERVICE_HEADING_RE = re.compile(
    r'(?:what\s+we\s+offer|our\s+services|services?\s+we\s+provide|'
    r'what\s+we\s+do|our\s+solutions|capabilities)',
    re.I,
)

# Feature list headings for SaaS/plugin
_FEATURE_HEADING_RE = re.compile(
    r'(?:features?|capabilities|what\s+(?:you\s+)?(?:can\s+)?(?:get|do)|'
    r'key\s+features?|product\s+features?|what(?:\'s|\s+is)\s+included)',
    re.I,
)

# Product teaser path pattern (Nike /t/slug, Adidas /us/en/ etc.)
_PRODUCT_TEASER_PATH_RE = re.compile(r'/t/[a-z0-9][a-z0-9\-_%]{2,}', re.I)


def _slug_to_title(url):
    """Convert a Nike /t/ product URL slug to a readable title.

    Strips product-ID codes (camelCase or all-caps segments like 2BSg6dMb,
    kIP8magY, IQUADZMV) from the end of the slug and title-cases the words.

    Examples:
      /t/jordan-triangle-basketball-shoes-2BSg6dMb/IB1154-001
        → "Jordan Triangle Basketball Shoes"
      /t/vapor-edge-360-untouchable-mens-football-cleats-kIP8magY/FQ0235-001
        → "Vapor Edge 360 Untouchable Mens Football Cleats"
    """
    m = re.search(r'/t/([^/?#]+)', url, re.I)
    if not m:
        return None
    slug = m.group(1)
    # Strip trailing product-ID segment: camelCase codes (2BSg6dMb, kIP8magY)
    # or all-uppercase codes (IQUADZMV, BNDJTB2D) — ≥5 chars
    slug = re.sub(
        r'-(?:[A-Za-z0-9]*(?:[a-z][A-Z]|[A-Z][a-z])[A-Za-z0-9]*|[A-Z0-9]{5,})$',
        '', slug,
    )
    words = [w for w in slug.replace('-', ' ').split() if w]
    if len(words) < 2 or (len(words) == 1 and words[0].isdigit()):
        return None
    return ' '.join(w.title() for w in words)

# Apple ecosystem subdomains — treated as featuredPrograms/ecosystemLinks, not brandExtensions
_APPLE_ECOSYSTEM_SUBDOMAINS = frozenset([
    "tv.apple.com", "music.apple.com", "apps.apple.com", "arcade.apple.com",
    "fitness.apple.com", "news.apple.com", "developer.apple.com",
    "accounts.apple.com", "support.apple.com", "appleid.apple.com",
    "card.apple.com", "icloud.com", "www.icloud.com",
])

# Extra Apple/utility nav text to reject as primary CTAs (supplements _CTA_REJECT_EXACT)
_CTA_NAV_TEXT_REJECT_RE = re.compile(
    r'^\s*(?:store|accessories|bag|cart|\d+\+?|gift\s+cards?|'
    r'certified\s+refurbished|financing|carrier\s+deals?(?:\s+at\s+apple)?|'
    r'shop\s+for\s+(?:veterans?(?:\s+and\s+military)?|military|'
    r'state(?:\s+and\s+local)?(?:\s+employees?)?|federal(?:\s+employees?)?|k-?12|college)|'
    r'item\s+\d+|language|region|select\s+country)\s*$',
    re.I,
)

# Samsung product titles that are CTA text / generic category names — NOT real products
_SAMSUNG_PRODUCT_REJECT_RE = re.compile(
    r'^(?:learn\s+more|view\s+all|explore|shop(?:\s+\w+)*|buy|find\s+your|'
    r'switch\s+to|certified\s+re[- ]newed|samsung\s+vision\s+ai|'
    r'galaxy\s+smartphone|galaxy\s+tab$|galaxy\s+watch$|galaxy\s+buds$|'
    r'galaxy\s+ring$|galaxy\s+phones?$|galaxy\s+ai$|'
    r'tvs?$|monitors?$|laptops?$|home\s+appliances?$|'
    r'shop\s+home|shop\s+now|design\.samsung\.com|'
    r'all\s+samsung\s+|see\s+all|see\s+more|'
    r'get\s+started|sign\s+up|join|'
    # Nav / utility / category strings
    r'mobile$|tv\s*&\s*av$|accessories$|apps\s*&\s*services$|'
    r'samsung\s+rewards|samsung\s+offer\s+programs?|samsung\s+care\+?|'
    r'samsung\s+experience\s+stores?|for\s+business|'
    r'samsung\s+authorized\s+reseller|samsung\s+members?|'
    r'buy\s+direct\s+get\s+more|samsung\s+developer|samsung\s+newsroom|'
    r'samsung\s+promotions?|'
    # Samsung support / account / warranty strings (Issue 3 & 4)
    r'support\s+home|warranty\s+information|service\s+center|'
    r'request\s+a\s+repair|track\s+repair|order\s+help|samsung\s+community|'
    r'slide.?in\s+electric\s+range\s+recall|how\s+to\s+recycle|'
    r'why\s+samsung\s+account|product\s+registration|samsung\s+account\s+faq|'
    r'shop\s+home|samsung\s+vision\s+ai)\s*$',
    re.I,
)

# Samsung: bare product-family names without a specific model qualifier.
# section_text products matching this (with no URL) are too generic to keep.
# Keep: "Galaxy Buds4 Pro", "Galaxy Z Fold7", "Galaxy Ring" (no digits after Ring)
# Reject: "Galaxy Buds4", "Galaxy S26", "Galaxy Tab S10", "Galaxy Watch8", "Bespoke AI", "The Frame"
_SAMSUNG_BARE_FAMILY_RE = re.compile(
    r'^(?:'
    r'Galaxy\s+[A-Z]\d+[a-z]?\s*$|'           # Galaxy S26, Galaxy S11
    r'Galaxy\s+Buds?\s*\d+[a-z]?\s*$|'        # Galaxy Buds4 (no Pro/Plus suffix)
    r'Galaxy\s+Tab\s+[A-Z]\d+[a-z]?\s*$|'     # Galaxy Tab S10 (no FE/5G suffix)
    r'Galaxy\s+Watch\s*\d+[a-z]?\s*$|'        # Galaxy Watch8 (no Classic suffix)
    r'Bespoke\s+AI\s*$|'                       # Bespoke AI alone (not Bespoke AI Vented Combo)
    r'The\s+Frame\s*$'                         # The Frame alone (not The Frame Pro / 65 Inch...)
    r')',
    re.I,
)

# Apple-specific utility/CTA paths that should NOT be classified as collections
_APPLE_NON_COLLECTION_PATH_RE = re.compile(
    r'/shop/(?:goto|buy-|product/|go/|refurbished|iphone|mac|ipad|watch|airpods|accessories)|'
    r'/us/shop/|trade.?in|apple\s+card|financing|get\s+your\s+estimate',
    re.I,
)

# Bot protection / empty-shell detection (Akamai)
_EMPTY_SHELL_COOKIE_RE = re.compile(r'\bak_bmsc\b', re.I)

# Menu section meta-headings that are NOT real menu categories
_MENU_META_HEADING_RE = re.compile(
    r'^\s*(?:our\s+menu|food\s+menu|the\s+menu|menu|'
    r'visit\s+\S.*|explore\s+our|welcome\s+to|home|contact|gallery|'
    r'location[s]?|reservations?|opening\s+hours?|'
    r'about\s+us?|faqs?|'
    # Non-category / nav terms that appear in restaurant Jina HTML
    r'bar(?:\s*[&+]\s*drinks?)?|[àa]\s*la\s+carte|events?|buffet)\s*$',
    re.I,
)


# ---------------------------------------------------------------------------
# Core utilities (kept from original)
# ---------------------------------------------------------------------------

def clean_text(text):
    return re.sub(r"\s+", " ", text or "").strip()


def unique_list(items):
    seen = set()
    output = []
    for item in items:
        if not item:
            continue
        key = str(item).strip().lower()
        if key in seen:
            continue
        seen.add(key)
        output.append(item)
    return output


def unique_by_url(items):
    seen = set()
    output = []
    for item in items:
        url = item.get("url")
        if not url or url in seen:
            continue
        seen.add(url)
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
            if text and 3 <= len(text) <= 140:
                headings.append({"level": tag_name, "text": text})
    return headings[:80]


def looks_like_product_url(href):
    href_l = (href or "").lower()
    # Standard product URL patterns
    if any(x in href_l for x in [
        "/product/", "/products/", "/product-page/", "/item/", "/pd/",
        "/p/", "/t/",
    ]):
        return True
    # Brand-specific deep product paths (Samsung, LG, Sony: /us/smartphones/model-slug/)
    if _BRAND_PRODUCT_PATH_RE.search(href_l):
        return True
    return False


def looks_like_category_url(href):
    href_l = (href or "").lower()
    return any(x in href_l for x in [
        "/collections/", "/collection/", "/category/", "/categories/",
        "/product-category/", "/shop/", "/store/", "/catalog/",
        "/men", "/women", "/kids", "/sale", "/new-arrivals",
        "/best-sellers", "/clothing", "/shoes", "/accessories",
        "/w/",  # Nike collection paths
    ])


# ---------------------------------------------------------------------------
# Jina mode detection
# ---------------------------------------------------------------------------

def _is_jina_mode(soup):
    """Return True when HTML was produced by _jina_markdown_to_html()."""
    return bool(
        soup.find(class_="jina-preamble")
        or (
            soup.find("h1")
            and soup.find("section")
            and not soup.find("nav")
            and not soup.find(class_=True, attrs={"class": re.compile(r"hero|banner|header", re.I)})
        )
    )


# ---------------------------------------------------------------------------
# Issue 2: Homepage main region extraction (footer / nav removal)
# ---------------------------------------------------------------------------

def extract_homepage_main_region(soup):
    """Return a BeautifulSoup of the main content area with footer/nav removed.

    Creates a lightweight copy limited to content-bearing tags; does NOT
    modify the caller's soup object.
    """
    html_str = str(soup)
    main_soup = BeautifulSoup(html_str, "lxml")

    # Remove <footer> elements entirely
    for el in main_soup.find_all("footer"):
        el.decompose()

    # Remove elements whose CSS classes strongly indicate nav/footer
    for el in main_soup.find_all(True):
        classes = " ".join(el.get("class") or [])
        if _FOOTER_CLASS_RE.search(classes):
            el.decompose()

    # Remove <nav> elements (global nav / mega-menu)
    for el in main_soup.find_all("nav"):
        el.decompose()

    return main_soup


# ---------------------------------------------------------------------------
# Issue 3: Business model classification (expanded 12-model taxonomy)
# ---------------------------------------------------------------------------

def classify_business_model(url, text, soup, level1=None):
    """Return {primaryModel, secondaryModel, scores, industry, homepageStyle}.

    Supported models:
      security_services, restaurant, local_business, plugin_software, saas,
      ecommerce_brand, retail_ecommerce, service_business, lead_generation,
      agency, contentPublisher, brand_editorial_homepage, manufacturer,
      marketplace, hybrid_local_ecommerce
    """
    t = text.lower()
    url_l = (url or "").lower()
    platform = (level1 or {}).get("platform", "")

    # Domain-level override for high-confidence known brands (bypass scoring)
    _raw_domain = url_l.split("//")[-1].split("/")[0]
    _domain = re.sub(r'^www\.', '', _raw_domain)
    for known_domain, override in _DOMAIN_OVERRIDES.items():
        if _domain == known_domain or _domain.endswith("." + known_domain):
            return {
                "primaryModel": override["primaryModel"],
                "secondaryModel": override["secondaryModel"],
                "scores": {},
                "industry": override["industry"],
                "homepageStyle": override["homepageStyle"],
            }

    scores = {k: 0 for k in (
        "security_services", "restaurant", "local_business",
        "plugin_software", "saas", "ecommerce_brand", "retail_ecommerce",
        "service_business", "lead_generation", "agency",
        "contentPublisher", "brand_editorial_homepage", "manufacturer",
        "marketplace", "hybrid_local_ecommerce", "web_hosting_provider",
    )}

    # -- Security services --------------------------------------------------
    security_signals = [
        "security guard", "sia-licensed", "sia licensed", "door supervisor",
        "event security", "retail security", "office security",
        "security services", "vacant property security", "concert security",
        "rapid deployment", "licensed guard", "security personnel",
        "security provider", "site protection", "vetted security",
        "arfm security", "manned guarding",
    ]
    sec_score = sum(2 for s in security_signals if s in t)
    if sec_score:
        scores["security_services"] = sec_score
        scores["service_business"] = max(scores["service_business"], sec_score // 2)

    # -- Web hosting / domain registration provider -------------------------
    hosting_signals = [
        "web hosting", "domain registration", "vps hosting", "dedicated server",
        "ssl certificate", "cpanel", "unlimited bandwidth", "unlimited databases",
        "free domain", "free backup", "website builder", "domain name",
        "hosting plan", "hosting package", "web host", "nameserver", "dns management",
        "shared hosting", "cloud hosting", "reseller hosting", "managed wordpress",
        "hosting control panel", "softaculous", "fantastico",
        "email hosting", "dedicated ip", "server uptime",
    ]
    hosting_score = sum(2 for s in hosting_signals if s in t)
    # Strong signals: URL with "hosting" keyword or multiple plan headings
    if "hosting" in url_l:
        hosting_score += 4
    if hosting_score >= 4:
        scores["web_hosting_provider"] = hosting_score

    # -- Restaurant / food service ------------------------------------------
    restaurant_signals = [
        "restaurant", "karahi", "biryani", "handi", "lahori", "tandoor",
        "naan", "dine", "dining", "cuisine", "chef", "kitchen",
        "book a table", "reservation", "bbq", "buffet", "à la carte",
        "our menu", "food to go", "takeaway", "takeout", "delivery",
        "zouq", "eatery",
    ]
    rest_score = sum(1 for s in restaurant_signals if s in t)
    # Bonus: .pk domain or Lahore / Pakistan mention
    # Suppressed when hosting signals dominate (websouls.pk is a hosting provider, not a restaurant)
    if ".pk" in url_l or "lahore" in t or "pakistan" in t:
        if rest_score >= 2 and scores.get("web_hosting_provider", 0) < 4:
            rest_score += 2
    if "menu" in t and any(s in t for s in ["bbq", "karahi", "biryani", "restaurant", "dining"]):
        rest_score += 3
    scores["restaurant"] = rest_score

    # -- Plugin / WordPress software ----------------------------------------
    plugin_signals = [
        "wordpress plugin", "wp plugin", "form builder", "license",
        "per year", "add-on", "addon", "plugin", "extension",
        "gravity forms", "woocommerce",
    ]
    plugin_score = sum(2 for s in plugin_signals if s in t)
    # Distinguish from generic SaaS: requires "plugin" or "license" or "wordpress"
    if "plugin" in t or "license" in t or "wordpress" in t:
        scores["plugin_software"] = plugin_score

    # -- SaaS / software platform ------------------------------------------
    saas_signals = [
        "free trial", "start trial", "pricing plans", "api",
        "dashboard", "platform", "saas", "software as a service",
        "monthly subscription", "annual plan", "enterprise plan",
        "sign up for free", "14-day", "30-day trial",
    ]
    saas_score = sum(2 for s in saas_signals if s in t)
    # IMPORTANT: "digital reporting" alone must NOT trigger saas
    if "digital reporting" in t and not any(
        s in t for s in ["api", "dashboard", "free trial", "saas", "software", "platform"]
    ):
        saas_score = max(0, saas_score - 2)
    scores["saas"] = saas_score

    # -- Ecommerce brand ---------------------------------------------------
    ecom_signals = [
        "shop now", "buy now", "add to cart", "shop all", "new arrivals",
        "best sellers", "featured products", "free shipping", "checkout",
        "collection", "just do it", "engineered for",
    ]
    ecom_score = sum(2 for s in ecom_signals if s in t)
    if any(x in url_l for x in ["/shop", "/store", "/collections", "/products"]):
        ecom_score += 2
    brand_editorial_signals = [
        "just do it", "campaign", "collection drop", "editorial",
        "lookbook", "inspire", "athlete", "culture", "shop soccer",
        "shop cleats", "shop basketball",
    ]
    if sum(1 for s in brand_editorial_signals if s in t) >= 2:
        scores["brand_editorial_homepage"] = 4
    scores["ecommerce_brand"] = ecom_score

    # -- Service / lead-gen ------------------------------------------------
    service_signals = [
        "our services", "what we offer", "free consultation",
        "book a call", "request a demo", "get in touch",
        "we provide", "tailored solutions", "bespoke",
        "professional services",
    ]
    svc_score = sum(1 for s in service_signals if s in t)
    scores["service_business"] = max(scores["service_business"], svc_score)

    leadgen_signals = [
        "contact sales", "get a quote", "request a quote",
        "book a demo", "get in touch", "call us now",
        "free consultation", "schedule a call",
    ]
    scores["lead_generation"] = sum(2 for s in leadgen_signals if s in t)

    # -- Agency ------------------------------------------------------------
    if any(s in t for s in ["creative agency", "digital agency", "marketing agency",
                             "design agency", "web agency"]):
        scores["agency"] = 4

    # -- Content publisher -------------------------------------------------
    content_signals = ["blog", "articles", "resources", "news", "guides", "podcast"]
    scores["contentPublisher"] = sum(1 for s in content_signals if s in t)

    # -- Hybrid local ecommerce (restaurant + online store) ----------------
    if scores["restaurant"] >= 3 and ecom_score >= 2:
        scores["hybrid_local_ecommerce"] = (scores["restaurant"] + ecom_score) // 2
    # Also detect hybrid when restaurant has an external shop/ordering domain
    if scores["restaurant"] >= 3 and ecom_score < 2 and soup is not None:
        base_domain_check = re.sub(r'^www\.', '', url_l.split("//")[-1].split("/")[0])
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            if not href.startswith("http"):
                continue
            a_text = clean_text(a.get_text(" ", strip=True)).lower()
            link_domain = re.sub(r'^www\.', '', href.split("//")[-1].split("/")[0].lower())
            if link_domain != base_domain_check and any(
                x in a_text for x in ["shop", "food to go", "order", "store", "buy"]
            ):
                ecom_score += 2
                scores["ecommerce_brand"] += 2
                scores["hybrid_local_ecommerce"] = (scores["restaurant"] + ecom_score) // 2
                break

    # Pick primary (highest score)
    primary = max(scores, key=scores.get)
    if scores[primary] == 0:
        primary = "unknown"

    # Pick secondary (second highest, different from primary, score > 0)
    sorted_models = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    secondary = None
    for model, sc in sorted_models[1:]:
        if sc > 0 and model != primary:
            secondary = model
            break

    # Derive homepage style tags
    homepage_styles = []
    if primary in ("ecommerce_brand", "retail_ecommerce"):
        if scores.get("brand_editorial_homepage", 0) >= 3:
            homepage_styles.append("brand_campaign")
        else:
            homepage_styles.append("featured_collections")
    if primary in ("saas", "plugin_software"):
        homepage_styles.append("saas_product")
    if primary == "restaurant":
        homepage_styles.append("local_restaurant")
    if primary in ("security_services", "service_business"):
        homepage_styles.append("service_lead_gen")
    if primary == "web_hosting_provider":
        homepage_styles.append("hosting_pricing_homepage")

    # Derive industry hint
    industry = None
    if primary == "web_hosting_provider":
        industry = "web hosting / domain registration / cloud infrastructure"
    elif primary == "security_services":
        industry = "security services"
    elif primary == "restaurant":
        if "lahori" in t or "karahi" in t or "pakistan" in t:
            industry = "Pakistani restaurant / food service"
        else:
            industry = "restaurant / food service"
    elif primary in ("plugin_software", "saas"):
        if "form" in t:
            industry = "form builder software"
        else:
            industry = "software / SaaS"
    elif primary == "ecommerce_brand":
        # Try to be specific about which ecommerce vertical
        if any(x in t for x in ["electronics", "smartphone", "laptop", "monitor", "tv ", "tablet",
                                  "galaxy", "macbook", "iphone", "gaming", "appliance"]):
            industry = "consumer electronics / technology"
        elif any(x in t for x in ["shoe", "sneaker", "athletic wear", "sportswear", "jersey",
                                    "cleats", "running", "training gear"]):
            industry = "apparel & footwear"
        elif any(x in t for x in ["beauty", "skincare", "makeup", "cosmetic", "fragrance"]):
            industry = "beauty & personal care"
        elif any(x in t for x in ["furniture", "home decor", "kitchen", "bedding", "mattress"]):
            industry = "home & furniture"
        else:
            industry = "ecommerce / retail"

    return {
        "primaryModel": primary,
        "secondaryModel": secondary,
        "scores": scores,
        "industry": industry,
        "homepageStyle": homepage_styles,
    }


# ---------------------------------------------------------------------------
# Issue 4: Hero extraction (Jina + campaign aware)
# ---------------------------------------------------------------------------

def extract_hero_v2(soup, jina_mode=False, url=None):
    """Extract hero with headline, subheadline, campaignHero, supportingText."""
    h1 = soup.find("h1")
    headline = clean_text(h1.get_text(" ", strip=True)) if h1 else None

    subheadline = None
    campaign_hero = None
    supporting_text = None
    primary_ctas = []

    if jina_mode:
        # Jina HTML: H1 is the page title; preamble paras have class jina-preamble;
        # first real section (H2) is often the campaign/hero headline.
        if h1:
            for sibling in h1.find_next_siblings():
                # Jina-preamble paragraphs (H1-body text, marked by _jina_markdown_to_html)
                # are normally skipped for campaign_hero, but may contain a tagline like
                # "Est. in Lahore · A Taste of Pure Happiness" — extract it before skipping.
                if "jina-preamble" in (sibling.get("class") or []):
                    if not supporting_text and sibling.name == "p":
                        _pt = clean_text(sibling.get_text(" ", strip=True))
                        # Strip bare Jina link patterns [](url) — these are noise, not taglines
                        _pt = re.sub(r'\[\]\([^)]*\)', '', _pt).strip()
                        _pt = clean_text(_pt)
                        # Reject nav labels (My Account, Sign In, etc.) as supportingText
                        if _pt.lower() in _CTA_REJECT_EXACT:
                            continue
                        if _pt and 5 <= len(_pt) <= 250 and not _CTA_ACTION_RE.search(_pt):
                            if '◆' in _pt or '·' in _pt or '|' in _pt:
                                # Separator-joined: extract the best non-location part
                                for _part in re.split(r'[◆·|]', _pt):
                                    _part = clean_text(_part)
                                    if not _part or len(_part) < 5:
                                        continue
                                    _pl = _part.lower()
                                    # Reject nav labels embedded in separator strings
                                    if _pl in _CTA_REJECT_EXACT:
                                        continue
                                    if re.match(r'^(?:est\.?\s|established|located in|est\s+in\s+the)', _pl):
                                        continue
                                    if sum(1 for c in _part if c.isupper()) / max(len(_part), 1) > 0.55:
                                        continue
                                    if not _is_video_noise_line(_pl) and re.search(r'[a-z]{3,}', _part):
                                        supporting_text = _part[:400]
                                        break
                            else:
                                # Plain tagline (no separator) — accept if it looks like brand copy
                                _ptl = _pt.lower()
                                _cap_r = sum(1 for c in _pt if c.isupper()) / max(len(_pt), 1)
                                if (
                                    _cap_r <= 0.55
                                    and not _is_video_noise_line(_ptl)
                                    and re.search(r'[a-z]{3,}', _pt)
                                    and not re.match(r'^(?:est\.?\s|established|located|copyright|©)', _ptl)
                                ):
                                    supporting_text = _pt[:400]
                    continue
                tag = sibling.name
                text = clean_text(sibling.get_text(" ", strip=True))
                if not text:
                    continue
                if tag == "section":
                    inner_h = sibling.find(["h2", "h3"])
                    if inner_h:
                        campaign_hero = clean_text(inner_h.get_text(" ", strip=True))
                    # Find best supporting text: iterate all <p> tags, pick tagline-like one.
                    # Skip CTAs so we don't use "Explore Our Menu" as a tagline.
                    for p_tag in sibling.find_all("p"):
                        # Skip paragraphs whose ENTIRE text is link text (pure nav/CTA wrappers)
                        # but allow paragraphs with surrounding non-link prose (e.g. Samsung demo text)
                        if p_tag.find("a"):
                            p_full = clean_text(p_tag.get_text(" ", strip=True))
                            p_link_text = " ".join(
                                clean_text(a.get_text(" ", strip=True))
                                for a in p_tag.find_all("a")
                            ).strip()
                            # If all text is inside links → skip (pure CTA wrapper)
                            if p_full.lower() == p_link_text.lower():
                                continue
                        p_text = clean_text(p_tag.get_text(" ", strip=True))
                        # Strip bare Jina link patterns [](url) before checking
                        p_text = re.sub(r'\[\]\([^)]*\)', '', p_text).strip()
                        p_text = clean_text(p_text)
                        if not p_text or len(p_text) < 5 or len(p_text) > 250:
                            continue
                        ptl = p_text.lower()
                        # Skip video/UI noise
                        if _is_video_noise_line(ptl):
                            continue
                        # Skip SHORT action CTAs (button labels ≤40 chars) — not full sentences.
                        # Allow longer text like "Book your personal demo at a Samsung Experience Store."
                        if _CTA_ACTION_RE.search(p_text) and len(p_text) <= 40:
                            continue
                        # Skip compound nav strips: "Find a Store Help Join Us Sign In"
                        if len(_NAV_COMPOUND_RE.findall(p_text)) >= 2:
                            continue
                        # Handle separator-joined phrases (e.g. "Est. in Lahore · A Taste of Pure Happiness")
                        # Try to extract a valid tagline from one of the parts.
                        # Don't pre-reject the whole paragraph — check each part individually.
                        if '◆' in p_text or '·' in p_text or '|' in p_text:
                            parts = re.split(r'[◆·|]', p_text)
                            for part in parts:
                                part = clean_text(part)
                                if not part or len(part) < 5:
                                    continue
                                pl = part.lower()
                                if re.match(r'^(?:est\.?\s|established|located in|est\s+in\s+the)', pl):
                                    continue
                                cap_r = sum(1 for c in part if c.isupper()) / max(len(part), 1)
                                if cap_r > 0.55:
                                    continue
                                if _is_video_noise_line(pl) or _CTA_ACTION_RE.search(part):
                                    continue
                                # Must have some lowercase letters (not all-caps label)
                                if re.search(r'[a-z]{3,}', part):
                                    supporting_text = part[:400]
                                    break
                            if supporting_text:
                                break
                            continue  # couldn't extract a tagline from this para
                        # Plain paragraph: check caps ratio
                        cap_ratio = sum(1 for c in p_text if c.isupper()) / max(len(p_text), 1)
                        if cap_ratio > 0.55:
                            continue
                        supporting_text = p_text[:400]
                        break
                    # Extract CTA links from hero section
                    for a in sibling.find_all("a", href=True):
                        a_text = _extract_link_text_for_cta(a)
                        if a_text and _CTA_ACTION_RE.search(a_text):
                            href = a.get("href", "")
                            if not href or href.startswith("javascript:"):
                                pass
                            elif href.startswith("#"):
                                # Hash anchor — no real URL; treat as text_cta
                                if a_text.lower() not in _CTA_REJECT_EXACT:
                                    primary_ctas.append({
                                        "text": a_text,
                                        "url": None,
                                        "type": "text_cta",
                                    })
                            else:
                                primary_ctas.append({
                                    "text": a_text,
                                    "url": urljoin(url or "", href).split("#")[0],
                                })
                    # Also collect text-only CTAs from paragraphs in hero section
                    for p_tag in sibling.find_all("p"):
                        if p_tag.find("a"):
                            continue
                        p_text = clean_text(p_tag.get_text(" ", strip=True))
                        if (p_text and 4 <= len(p_text) <= 60
                                and _CTA_ACTION_RE.search(p_text)
                                and p_text.lower() not in _CTA_REJECT_EXACT):
                            primary_ctas.append({"text": p_text, "url": None, "type": "text_cta"})
                    break
                elif tag in ("h2", "h3") and len(text) > 5:
                    campaign_hero = text
                    break
                elif tag == "p" and 10 < len(text) <= 400:
                    supporting_text = text
                    break

        # Also look for first H3 as campaign hero if campaign_hero still unset
        if not campaign_hero:
            for h3 in soup.find_all("h3")[:5]:
                text = clean_text(h3.get_text(" ", strip=True))
                if text and not _FOOTER_HEADING_RE.match(text) and len(text) > 5:
                    campaign_hero = text
                    break

    else:
        # Normal HTML: look for .hero / header / banner CSS selectors
        hero_selectors = [
            ".hero", "[class*='hero']", "[data-testid*='hero']",
            "[class*='banner']", "header",
        ]
        hero_block = None
        for selector in hero_selectors:
            try:
                block = soup.select_one(selector)
                if block:
                    hero_block = block
                    break
            except Exception:
                pass

        if hero_block:
            inner_h = hero_block.find(["h2", "h3"])
            if inner_h:
                subheadline = clean_text(inner_h.get_text(" ", strip=True))
            # Try all <p> tags; pick first that looks like brand copy (not "Est." location)
            for inner_p in hero_block.find_all("p"):
                p_text = clean_text(inner_p.get_text(" ", strip=True))
                if not p_text or len(p_text) < 5 or len(p_text) > 250:
                    continue
                ptl = p_text.lower()
                if _is_video_noise_line(ptl) or _CTA_ACTION_RE.search(p_text):
                    continue
                if re.match(r'^(?:est\.?\s|established|located in|est\s+in\s+the)', ptl):
                    continue
                supporting_text = p_text[:400]
                break
        elif h1:
            for sibling in h1.find_next_siblings():
                text = clean_text(sibling.get_text(" ", strip=True))
                if text and 5 < len(text) <= 300 and sibling.name in ("h2", "p"):
                    subheadline = text
                    break

        # For non-Jina pages: if supportingText is still unset, scan h1 siblings
        # for a short tagline-like text (catches restaurant taglines "A Taste of…")
        if not supporting_text and h1:
            for sib in h1.find_next_siblings()[:15]:
                t = clean_text(sib.get_text(" ", strip=True))
                if not t or len(t) < 5 or len(t) > 200:
                    continue
                tl = t.lower()
                if _is_video_noise_line(tl) or _CTA_ACTION_RE.search(t):
                    continue
                if re.match(r'^(?:est\.?\s|established|located in|est\s+in\s+the|©)', tl):
                    continue
                # Skip headings (already captured as headline/subheadline)
                if sib.name in ("h1", "h2", "h3", "h4", "h5"):
                    continue
                # Skip nav, footer, header containers
                if sib.name in ("nav", "header", "footer"):
                    continue
                supporting_text = t[:400]
                break

        # Extract primary CTAs from hero region
        hero_region = hero_block or (h1.parent if h1 else None)
        if hero_region:
            for a in hero_region.find_all("a", href=True)[:10]:
                a_text = clean_text(a.get_text(" ", strip=True))
                href = a.get("href", "")
                if (a_text and len(a_text) < 60
                        and _CTA_ACTION_RE.search(a_text)
                        and href
                        and not href.startswith("javascript:")):
                    primary_ctas.append({
                        "text": a_text,
                        "url": urljoin(url or "", href).split("#")[0],
                    })

    return {
        "headline": headline,
        "subheadline": subheadline,
        "campaignHero": campaign_hero,
        "supportingText": supporting_text,
        "primaryCtas": primary_ctas[:5],
        "text": supporting_text or subheadline or campaign_hero,
    }


def _extract_link_text_for_cta(a_tag):
    """Extract visible text from an <a> tag, ignoring <img> alt spam.

    Handles the Jina markdown pattern where text is in the parent <li>
    adjacent to an empty-text anchor.
    """
    texts = []
    for node in a_tag.children:
        if hasattr(node, "name"):
            if node.name == "img":
                continue
            texts.append(clean_text(node.get_text(" ", strip=True)))
        else:
            t = str(node).strip()
            if t:
                texts.append(t)
    result = " ".join(t for t in texts if t)
    if not result:
        parent = a_tag.parent
        if parent and parent.name == "li":
            for node in parent.children:
                if hasattr(node, "name") and node.name == "img":
                    continue
                if hasattr(node, "name") and node is a_tag:
                    continue
                t = (clean_text(str(node)) if not hasattr(node, "name")
                     else clean_text(node.get_text(" ", strip=True)))
                if t:
                    result = t
                    break
    return clean_text(result)


# ---------------------------------------------------------------------------
# Issue 5: Section extraction (heading-based, Jina-aware, footer-filtered)
# ---------------------------------------------------------------------------

def _is_video_noise_line(text_lower):
    """Return True if the line is video-player UI noise (Jina Nike/video pages)
    or Samsung modal/carousel UI noise."""
    tl = text_lower.strip()
    if tl in _VIDEO_NOISE_LINES:
        return True
    if _VIDEO_LANG_RE.match(tl):
        return True
    # "Loaded: 21.01%", "Remaining Time 1:26", "en (Main), selected"
    if re.match(r'^(?:loaded:\s*[\d.]+%|remaining\s+time\s+\d+:\d+|slide\s+\d+\s+of\s+\d+)$', tl):
        return True
    # "Duration 1:26", "Current Time 0:00", "Stream Type LIVE"
    if re.match(r'^(?:duration|current\s+time|stream\s+type|remaining\s+time|loaded)[\s:]', tl):
        return True
    # Playback speed tokens: "1x", "2x", "0.5x"
    if re.match(r'^\d+(?:\.\d+)?x$', tl):
        return True
    # Samsung / generic carousel UI single-word tokens
    if re.match(r'^(?:close|previous|next|skip|pause|play|mute|unmute|fullscreen)$', tl):
        return True
    # Compound noise: paragraph contains 2+ known noise tokens (Samsung login modal bleed)
    # e.g. "Login using Samsung Account Continue as guest Close Close Father's Day Previous"
    noise_hit = sum(1 for n in _VIDEO_NOISE_LINES if n in tl)
    if noise_hit >= 2:
        return True
    return False


def _strip_samsung_nav_from_jina_soup(soup):
    """For samsung.com Jina HTML, remove the full GNB preamble and leave only
    real homepage content starting at the first section matching
    _SAMSUNG_REAL_START_RE (e.g. "Experience a whole new Galaxy").

    Samsung's Jina markdown encodes GNB as BOTH:
    - <section> elements with nav headings (SHOP BY CATEGORY, etc.)
    - Flat <ul>/<li> elements for category links (Mobile, Galaxy Tab, TV & AV…)

    Both must be removed.  After stripping, also clean login/account noise
    that Samsung injects inside the real content region.
    """
    # ── Step 1: find the first real-content section ───────────────────────
    all_sections = soup.find_all("section")

    start_section = None
    for sec in all_sections:
        h = sec.find(["h2", "h3"])
        if h and _SAMSUNG_REAL_START_RE.search(h.get_text(strip=True)):
            start_section = sec
            break

    if start_section is None:
        # Fallback: strip leading sections with known nav headings only
        for sec in list(all_sections):
            h = sec.find(["h2", "h3"])
            if h and _FOOTER_HEADING_RE.match(h.get_text(strip=True)):
                sec.decompose()
            else:
                break
        return soup

    # ── Step 2: remove EVERY sibling before start_section (flat GNB lists, ──
    # headings, paragraphs, ul/li blocks that the section-strip missed).
    # PRESERVE <h1> so extract_hero_v2() can anchor hero extraction.
    for sib in list(start_section.find_previous_siblings()):
        if sib.name == "h1":
            continue  # keep h1 for hero extraction
        sib.decompose()

    # ── Step 3: clean login / modal noise inside real sections ────────────
    _SAMSUNG_LOGIN_RE = re.compile(
        r'login\s+using(?:\s+your)?\s+samsung\s+account|'
        r'continue\s+as\s+(?:a\s+)?guest|'
        r'layer\s+popup|check\s+preferences|'
        r'close\s+close|previous\s+next',
        re.I,
    )
    for tag in list(soup.find_all(["p", "li"])):
        t = tag.get_text(" ", strip=True)
        if t and len(t) < 250 and _SAMSUNG_LOGIN_RE.search(t.lower()):
            tag.decompose()

    return soup


def _strip_nike_nav_from_jina_soup(soup):
    """For nike.com Jina HTML, remove the GNB preamble and leave only
    real campaign content starting at the first section matching
    _NIKE_REAL_START_RE (e.g. "NO FINAL WHISTLE", "TRENDING NOW").

    Nike's Jina markdown encodes the GNB as flat sections with headings like
    "Men", "Women", "Jordan", "New & Featured", "Best Sellers", "SNKRS Launch
    Calendar", etc. before the real editorial content.
    """
    all_sections = soup.find_all("section")

    start_section = None
    for sec in all_sections:
        h = sec.find(["h2", "h3"])
        if h and _NIKE_REAL_START_RE.search(h.get_text(strip=True)):
            start_section = sec
            break

    if start_section is None:
        # Fallback: look for matching headings outside sections
        for h_tag in soup.find_all(["h1", "h2", "h3"]):
            if _NIKE_REAL_START_RE.search(h_tag.get_text(strip=True)):
                # Remove all document-level siblings before this heading
                for sib in list(h_tag.find_previous_siblings()):
                    sib.decompose()
                return soup
        return soup

    # Remove every sibling before the first real campaign section
    for sib in list(start_section.find_previous_siblings()):
        sib.decompose()

    return soup


def _extract_brand_products_from_sections(sections, domain):
    """Extract featured products from section headings for known brand domains.

    Covers:
    - Apple: section headings are product-family names (iPhone, MacBook Air…)
    - Samsung: section text links to deep product paths already handled by
      looks_like_product_url; this adds any remaining Galaxy-named headings.
    """
    products = []
    seen = set()
    domain_l = (domain or "").lower()

    # Prefix patterns for Apple product headings like "Introducing iPhone 16 Air"
    # or "Meet MacBook Air" — strip these before matching the product name
    _APPLE_PRODUCT_PREFIX_RE = re.compile(
        r'^(?:introducing|meet|all\s+new|new|the\s+new|say\s+hello\s+to|'
        r'designed\s+for|made\s+for|built\s+for)\s+',
        re.I,
    )
    _APPLE_PRODUCT_RE = re.compile(
        r'\b(?:iphone(?:\s+\d+)?(?:\s+(?:pro(?:\s+max)?|plus|air|mini|max))?|'
        r'macbook(?:\s+(?:air|pro))?(?:\s+\d+[- ]?(?:inch)?)?|'
        r'ipad(?:\s+(?:air|pro|mini))?(?:\s+\d+[- ]?(?:inch)?)?|'
        r'apple\s+watch(?:\s+(?:ultra\s*\d*|series\s+\d+))?|'
        r'airpods?(?:\s+pro(?:\s+\d+)?)?(?:\s+max)?|'
        r'apple\s+tv(?:\s+\d+k)?|homepod(?:\s+mini)?|'
        r'imac|mac\s+(?:pro|mini|studio)?(?:\s+\w+)?|vision\s+pro)\b',
        re.I,
    )
    # Apple-specific program/service section headings
    _APPLE_PROGRAM_RE = re.compile(
        r'\bapple\s+(?:trade[- ]in|card|pay|one|for\s+college|for\s+veterans?|'
        r'fitness\+?|tv\+?|arcade|music|news\+?|icloud\+?|business|education)|'
        r'endless\s+entertainment|back\s+to\s+(?:school|campus)|'
        r'student\s+(?:discount|savings?|program)|'
        r'apple\s+in\s+education|apple\s+at\s+work\b',
        re.I,
    )
    _SAMSUNG_MODEL_RE = re.compile(
        r'\b(?:galaxy\s+(?:s\d+|z\s+fold\d*|z\s+flip\d*|book\d*|'
        r'tab\s+s\d+|watch\s*\d*|buds\d*|ring|xr)|'
        r'the\s+frame(?:\s+pro)?|neo\s+qled|qled\s+qn?\d+|oled\s+s\d+|'
        r'bespoke\s+ai)\b',
        re.I,
    )

    is_apple = "apple.com" in domain_l
    is_samsung = "samsung.com" in domain_l

    for sec in sections:
        heading = (sec.get("heading") or "").strip()
        if not heading:
            continue
        hl = heading.lower()

        if is_apple:
            # Strip "Introducing", "Meet", "All new" prefixes before matching
            clean_heading = _APPLE_PRODUCT_PREFIX_RE.sub("", heading).strip()
            clean_hl = clean_heading.lower()
            if _APPLE_PRODUCT_RE.search(clean_heading) and clean_hl not in seen:
                seen.add(clean_hl)
                # Use cleaned heading as product title
                products.append({"title": clean_heading, "url": None, "source": "section"})
            elif _APPLE_PROGRAM_RE.search(heading) and hl not in seen:
                # Programs go into featuredPrograms, not products
                seen.add(hl)
                products.append({"title": heading, "url": None, "source": "apple_program"})
        elif is_samsung:
            # Strip trailing " Buy" CTA suffix from Samsung headings
            if re.search(r'\s+buy\s*$', heading, re.I):
                heading = re.sub(r'\s+buy\s*$', '', heading, flags=re.I).strip()
                hl = heading.lower()
            # Reject CTA / generic category names
            if _SAMSUNG_PRODUCT_REJECT_RE.match(heading):
                continue
            if _SAMSUNG_MODEL_RE.search(heading) and hl not in seen:
                seen.add(hl)
                products.append({"title": heading, "url": None, "source": "section"})

    # For Apple: also scan section text lines for standalone product name mentions.
    # This catches cases where "iPhone", "iPad Air" etc. appear as the first
    # line of a section body (not a heading tag) on the Apple Jina page.
    if is_apple:
        for sec in sections:
            sec_text = sec.get("text") or ""
            for line in sec_text.splitlines():
                line = clean_text(line.strip())
                # Product name lines are short (≤ 50 chars)
                if not line or len(line) < 3 or len(line) > 50:
                    continue
                # Strip common prefixes before matching
                line_clean = _APPLE_PRODUCT_PREFIX_RE.sub("", line).strip()
                m = _APPLE_PRODUCT_RE.search(line_clean)
                if not m:
                    continue
                product_name = m.group()
                # Product name must dominate the line (≥ 45% of chars) to avoid
                # picking up sentences that merely mention a product in passing.
                if len(product_name) < len(line_clean) * 0.45:
                    continue
                pl = product_name.lower()
                if pl not in seen:
                    seen.add(pl)
                    products.append({"title": product_name, "url": None, "source": "section_text"})

    # For Samsung: also scan section text for Galaxy model mentions
    if is_samsung:
        for sec in sections:
            for m in _SAMSUNG_MODEL_RE.finditer(sec.get("text") or ""):
                title = clean_text(m.group())
                tl = title.lower()
                if tl not in seen and len(title) > 5 and not _SAMSUNG_PRODUCT_REJECT_RE.match(title):
                    seen.add(tl)
                    products.append({"title": title, "url": None, "source": "section_text"})

    return products[:15]


def _extract_programs_from_sections(sections, products):
    """For ecommerce-brand homepages, extract campaign/program names from sections.

    A section heading is a 'program' if it is NOT a product name already
    extracted, and looks like a campaign title, seasonal event, or brand
    program (Father's Day, Apple Trade In, Apple Card, etc.).
    """
    product_titles_l = {(p.get("title") or "").lower() for p in products}
    _PROG_SKIP_RE = re.compile(
        r'^(?:shop|buy|explore all|view all|see all|learn more|get started|'
        r'sign up|contact|about|support|help|faq|privacy|terms|careers|'
        r'sustainability|newsroom|investors?)\b',
        re.I,
    )
    programs = []
    seen = set()
    for sec in sections:
        heading = (sec.get("heading") or "").strip()
        if not heading or len(heading) < 3 or len(heading) > 80:
            continue
        hl = heading.lower()
        if hl in seen or hl in product_titles_l:
            continue
        if _FOOTER_HEADING_RE.match(heading):
            continue
        if _PROG_SKIP_RE.match(heading):
            continue
        # Must look like a meaningful title (not single word nav items)
        if " " not in heading and len(heading) < 8:
            continue
        seen.add(hl)
        programs.append({"title": heading, "url": None})
    return programs[:8]


def _compute_homepage_quality(
    primary_model, hero, sections, ctas, products, categories,
    title, meta_description, contact_info, trust_signals,
    services, value_props, menu_items, menu_categories, brand_extensions,
    jina_mode=False,
):
    """Business-model-aware homepage quality/confidence score.

    Returns a float in [0.50, 0.92].  Each model rewards its own
    positive signals and does NOT penalise for missing signals that
    are irrelevant to that model type.

    jina_mode=True caps ecommerce_brand scores at 0.74 (Jina fallback
    has inherent nav/VP pollution → cannot be marked "good" automatically).
    """
    base = 0.50

    has_hero = bool(hero.get("headline"))
    has_sections = len(sections) >= 2
    has_ctas = len(ctas) >= 1
    has_title = bool(title or meta_description)
    has_contact = bool(contact_info.get("phone") or contact_info.get("email"))

    if primary_model in ("ecommerce_brand", "retail_ecommerce"):
        score = base
        if has_hero:                               score += 0.10
        if has_sections:                           score += 0.08
        if has_ctas:                               score += 0.08
        if products or categories:                 score += 0.10
        if has_title:                              score += 0.06
        if has_contact:                            score += 0.04
        if trust_signals:                          score += 0.03
        if primary_model != "unknown":             score += 0.03
        # Jina fallback has nav/VP pollution → cap below "good" threshold
        # so needsAIInsightReview=true until human-verified extraction
        if jina_mode:
            score = min(score, 0.74)

    elif primary_model == "restaurant":
        # Issue 8: quality-aware restaurant scoring.
        # Target: 0.76-0.82 with clean extraction (items + categories present),
        #         0.68-0.74 with partial extraction (no category fields / few cats).
        # items_with_cat: menu items that have a category field set (quality signal).
        items_with_cat = sum(1 for i in menu_items if i.get("category"))
        score = base
        if has_hero:                               score += 0.06
        # Full credit only when items have category fields (well-structured extraction)
        if items_with_cat >= 3:                    score += 0.05
        elif len(menu_items) >= 3:                 score += 0.02
        # Full credit only when ≥3 distinct menu categories extracted
        if len(menu_categories) >= 3:              score += 0.04
        elif len(menu_categories) >= 2:            score += 0.02
        if has_sections:                           score += 0.04
        if has_ctas:                               score += 0.03
        if has_contact:                            score += 0.03
        if brand_extensions:                       score += 0.02
        if has_title:                              score += 0.01

    elif primary_model in ("security_services", "service_business",
                           "local_business", "lead_generation"):
        score = base
        if has_hero:                               score += 0.10
        if len(services) >= 2:                     score += 0.12
        if len(trust_signals) >= 2:                score += 0.08
        if len(value_props) >= 2:                  score += 0.06
        if has_ctas:                               score += 0.06
        # For service businesses: contact phone/email is optional (some only have CTAs)
        # Give partial credit for serviceArea when no direct phone/email
        if has_contact:                            score += 0.06
        elif contact_info.get("serviceArea"):      score += 0.03
        if contact_info.get("serviceArea"):        score += 0.04
        if has_sections:                           score += 0.04
        if has_title:                              score += 0.02

    elif primary_model == "web_hosting_provider":
        score = base
        if has_hero:                               score += 0.08
        if has_sections:                           score += 0.10
        if len(services) >= 2:                     score += 0.12
        if has_ctas:                               score += 0.08
        if has_title:                              score += 0.06
        if trust_signals:                          score += 0.06
        if has_contact:                            score += 0.04
        if primary_model != "unknown":             score += 0.04
        # Pricing plans proxy: products or categories contain plan-like entries
        if products or categories:                 score += 0.06

    elif primary_model in ("saas", "plugin_software"):
        score = base
        if has_hero:                               score += 0.10
        if has_sections:                           score += 0.10
        if has_ctas:                               score += 0.08
        if products or categories:                 score += 0.08
        if has_title:                              score += 0.06
        if has_contact:                            score += 0.04
        if trust_signals:                          score += 0.04

    else:  # unknown / generic
        score = base
        if has_hero:                               score += 0.12
        if has_sections:                           score += 0.10
        if has_ctas:                               score += 0.08
        if products or categories:                 score += 0.10
        if has_title:                              score += 0.08
        if primary_model not in ("unknown", "contentPublisher"):
            score += 0.05
        if has_contact:                            score += 0.05

    return round(min(0.92, score), 2)


def extract_sections_v2(soup, jina_mode=False):
    """Extract homepage sections -- footer-filtered, heading-based for Jina."""
    sections = []

    if jina_mode:
        sections = _extract_sections_from_headings(soup)
    else:
        css_sections = _extract_sections_css(soup)
        if css_sections:
            sections = [s for s in css_sections if not _is_footer_section(s)]
        if not sections or len(sections) < 2:
            heading_sections = _extract_sections_from_headings(soup)
            if len(heading_sections) > len(sections):
                sections = heading_sections

    return sections[:20]


def _is_footer_section(section):
    heading = (section.get("heading") or "").strip()
    if not heading:
        return False
    if _FOOTER_HEADING_RE.match(heading):
        return True
    if _DOUBLED_TEXT_RE.match(heading):
        return True
    return False


def _extract_sections_from_headings(soup):
    """Build sections from H2/H3 heading hierarchy (works for Jina HTML)."""
    sections = []
    seen = set()

    def _collect_parts(container, skip_tag=None):
        """Collect text parts from children, filtering video noise."""
        parts = []
        for child in container.children:
            if not hasattr(child, "name"):
                t = str(child).strip()
                if t and not _is_video_noise_line(t.lower()):
                    parts.append(t)
                continue
            if child is skip_tag or child.name in ("h2", "h3", "h4"):
                continue
            t = clean_text(child.get_text(" ", strip=True))
            if not t or len(t) <= 3:
                continue
            # Strip HTML5 video-player modal noise before line-level check
            t = _strip_video_player_noise(t)
            if t and not _is_video_noise_line(t.lower()):
                parts.append(t)
        return parts

    section_tags = soup.find_all("section")
    if section_tags:
        for sec in section_tags:
            h_tag = sec.find(["h2", "h3", "h4"])
            if not h_tag:
                continue
            heading = clean_text(h_tag.get_text(" ", strip=True))
            if not heading or _FOOTER_HEADING_RE.match(heading) or _DOUBLED_TEXT_RE.match(heading):
                continue
            heading_l = heading.lower()[:80]
            if heading_l in seen:
                continue
            seen.add(heading_l)
            parts = _collect_parts(sec, skip_tag=h_tag)
            section_text = _strip_video_player_noise(" ".join(parts))[:600]
            sections.append({"heading": heading, "text": section_text})
        if sections:
            return sections

    # H2 pass
    for h2 in soup.find_all("h2"):
        heading = clean_text(h2.get_text(" ", strip=True))
        if not heading or len(heading) < 3 or len(heading) > 120:
            continue
        if _FOOTER_HEADING_RE.match(heading) or _DOUBLED_TEXT_RE.match(heading):
            continue
        heading_l = heading.lower()[:80]
        if heading_l in seen:
            continue
        seen.add(heading_l)
        parts = []
        for sibling in h2.find_next_siblings():
            if sibling.name == "h2":
                break
            if sibling.name in ("h3", "h4"):
                t = clean_text(sibling.get_text(" ", strip=True))
                t = _strip_video_player_noise(t)
                if t and not _is_video_noise_line(t.lower()):
                    parts.append(t)
            elif sibling.name == "p":
                t = clean_text(sibling.get_text(" ", strip=True))
                t = _strip_video_player_noise(t)
                if t and len(t) > 5 and not _is_video_noise_line(t.lower()):
                    parts.append(t)
            elif sibling.name in ("ul", "ol"):
                for li in sibling.find_all("li"):
                    t = clean_text(li.get_text(" ", strip=True))
                    t = _strip_video_player_noise(t)
                    if t and not _is_video_noise_line(t.lower()):
                        parts.append(t)
            if sum(len(p) for p in parts) > 600:
                break
        section_text = " ".join(parts)[:600]
        sections.append({"heading": heading, "text": section_text})

    # H3 fallback when no H2/section structure (e.g., Samsung Jina with only H3 headings)
    if not sections:
        for h3 in soup.find_all("h3"):
            heading = clean_text(h3.get_text(" ", strip=True))
            if not heading or len(heading) < 3 or len(heading) > 120:
                continue
            if _FOOTER_HEADING_RE.match(heading) or _DOUBLED_TEXT_RE.match(heading):
                continue
            heading_l = heading.lower()[:80]
            if heading_l in seen:
                continue
            seen.add(heading_l)
            parts = []
            for sibling in h3.find_next_siblings():
                if sibling.name in ("h2", "h3"):
                    break
                if sibling.name == "p":
                    t = clean_text(sibling.get_text(" ", strip=True))
                    if t and len(t) > 5 and not _is_video_noise_line(t.lower()):
                        parts.append(t)
                if sum(len(p) for p in parts) > 400:
                    break
            section_text = " ".join(parts)[:400]
            sections.append({"heading": heading, "text": section_text})

    return sections


def _extract_sections_css(soup):
    """Original CSS-class-based section extraction."""
    sections = []
    for section in soup.find_all(["section", "article", "div"]):
        classes = " ".join(section.get("class") or []).lower()
        if not any(x in classes for x in [
            "section", "hero", "banner", "feature", "collection",
            "category", "product", "testimonial", "review", "trust", "benefit",
        ]):
            continue
        heading_tag = section.find(["h1", "h2", "h3"])
        heading = clean_text(heading_tag.get_text(" ", strip=True)) if heading_tag else None
        text = clean_text(section.get_text(" ", strip=True))
        if not text or len(text) < 30:
            continue
        if heading or len(text) <= 500:
            sections.append({"heading": heading, "text": text[:600]})
    seen = set()
    cleaned = []
    for s in sections:
        key = (s.get("heading") or s.get("text") or "")[:100].lower()
        if key not in seen:
            seen.add(key)
            cleaned.append(s)
    return cleaned[:25]


# ---------------------------------------------------------------------------
# Issue 6: CTA extraction (reject nav/footer, handle Jina li-based links)
# ---------------------------------------------------------------------------

def extract_ctas_v2(soup, url, business_model=None):
    """Extract homepage CTAs; reject nav/footer/support links."""
    ctas = []
    seen_urls = set()
    seen_texts = set()

    # App store URL pattern — links to Google Play / Apple App Store / Huawei AppGallery
    # should be collected as appLinks, not CTAs.
    _APP_STORE_URL_RE = re.compile(
        r'play\.google\.com|apps\.apple\.com|appgallery\.huawei\.com|'
        r'itunes\.apple\.com|market\.android\.com',
        re.I,
    )

    def _add(text, href):
        if not text or len(text) > 80:
            return
        text_l = text.lower().strip()
        if text_l in _CTA_REJECT_EXACT:
            return
        # Reject Apple/utility nav fragments that aren't real homepage CTAs
        if _CTA_NAV_TEXT_REJECT_RE.match(text):
            return
        href_l = (href or "").lower()
        if any(x in href_l for x in _CTA_REJECT_URL_PARTS):
            return
        if href_l.startswith(("javascript:", "mailto:", "#")) or not href:
            return
        # Reject app store links (Google Play, Apple App Store, Huawei AppGallery)
        if _APP_STORE_URL_RE.search(href_l):
            return
        # Reject questions (FAQ text used as CTA) and testimonial/history fragments
        if "?" in text:
            return
        if re.match(r'^In\s+(?:\d{4}|[A-Z][a-z])', text):
            return
        # Reject long descriptive text (> 70 chars with lowercase start = body copy, not CTA)
        if len(text) > 70 and text[0].islower():
            return
        full_url = urljoin(url or "", href).split("#")[0]
        if full_url in seen_urls or text_l[:50] in seen_texts:
            return
        seen_urls.add(full_url)
        seen_texts.add(text_l[:50])
        ctas.append({"text": text, "url": full_url})

    # Pass 1: standard <a> tags with text
    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        text = clean_text(a.get_text(" ", strip=True))
        if not text:
            continue
        if (
            _CTA_ACTION_RE.search(text)
            or looks_like_category_url(href)
            or looks_like_product_url(href)
        ):
            _add(text, href)

    # Pass 2: Jina-style <li> items where text is adjacent to an empty <a>
    # e.g. <li><img> Shop Soccer Lifestyle <a href="..."></a></li>
    for li in soup.find_all("li"):
        a_tags = li.find_all("a", href=True)
        if not a_tags:
            continue
        href = a_tags[0].get("href", "")
        if not href:
            continue
        li_copy = BeautifulSoup(str(li), "lxml")
        for img in li_copy.find_all("img"):
            img.decompose()
        for a in li_copy.find_all("a"):
            a.decompose()
        text = clean_text(li_copy.get_text(" ", strip=True))
        if text and _CTA_ACTION_RE.search(text):
            _add(text, href)

    # Pass 3: Jina bare-link pattern — _jina_markdown_to_html() cannot convert
    # empty-bracket links [](url) since its regex requires [text](url).
    # These survive as literal "[](url)" strings in <li> or <p> elements.
    # e.g. <li><img> Shop Soccer Lifestyle [](https://www.nike.com/w/...)</li>
    _BARE_LINK_RE = re.compile(r'\[\]\(([^)]+)\)')
    for el in soup.find_all(["li", "p"]):
        el_html = str(el)
        bare_matches = _BARE_LINK_RE.findall(el_html)
        if not bare_matches:
            continue
        href = bare_matches[0]
        # Strip img tags and [](url) patterns, then extract plain text
        el_copy = BeautifulSoup(el_html, "lxml")
        for img in el_copy.find_all("img"):
            img.decompose()
        raw_text = el_copy.get_text(" ", strip=True)
        # Remove any remaining [](url) literal text
        raw_text = _BARE_LINK_RE.sub("", raw_text)
        text = clean_text(raw_text)
        if text and _CTA_ACTION_RE.search(text):
            _add(text, href)

    # Pass 4: Text-only CTAs (Jina mode — plain text paragraphs with no proper links).
    # Captures: "Explore Our Menu", "Book an Event", "Call now for tailored security solutions".
    #
    # IMPORTANT: skip elements that contain bare-link [](url) patterns — those were
    # already captured by Pass 3 with a URL; re-adding without URL causes duplicates
    # (e.g. "Shop Soccer Lifestyle [](https://...)" → "Shop Soccer Lifestyle" already in CTAs).
    _BARE_LINK_CHECK_RE = re.compile(r'\[\]\(')
    for el in soup.find_all(["p", "li"]):
        # Skip elements with real (non-anchor) links — already handled by Passes 1-3
        el_links = el.find_all("a", href=True)
        has_real_link = any(
            a.get("href", "").startswith(("http", "/")) and
            not a.get("href", "").startswith("/#") and
            len(a.get("href", "")) > 1
            for a in el_links
        )
        if has_real_link:
            continue
        # Allow elements with only anchor links (e.g. <a href="#menu">Explore Our Menu</a>)
        # so restaurant text CTAs ("Explore Our Menu", "Book an Event") are captured.
        # Skip if raw HTML contains a bare-link pattern (Pass 3 covers it)
        if _BARE_LINK_CHECK_RE.search(str(el)):
            continue
        t = clean_text(el.get_text(" ", strip=True))
        # Tighter limit for text_ctas (no URL to validate against): 70 chars max
        if not t or len(t) > 70 or len(t) < 4:
            continue
        if not _CTA_ACTION_RE.search(t):
            continue
        tl = t.lower().strip()
        if tl in _CTA_REJECT_EXACT:
            continue
        if tl[:50] in seen_texts:
            continue
        if _is_video_noise_line(tl):
            continue
        # Reject question text (FAQ fragments) and testimonial/history openers
        if "?" in t:
            continue
        if re.match(r'^In\s+(?:\d{4}|[A-Z][a-z])', t):
            continue
        seen_texts.add(tl[:50])
        ctas.append({"text": t, "url": None, "type": "text_cta"})

    # Pass 4b: For restaurant pages, also scan h2/h3 headings for CTA-action text.
    # "Explore Our Menu" and "Book an Event" may appear as section headings (h2/h3)
    # in Jina HTML, which Pass 4's p/li scan misses.
    if (business_model or "").lower() == "restaurant":
        for h_tag in soup.find_all(["h2", "h3"]):
            t = clean_text(h_tag.get_text(" ", strip=True))
            if not t or len(t) < 4 or len(t) > 60:
                continue
            if not _CTA_ACTION_RE.search(t):
                continue
            tl = t.lower().strip()
            if tl in _CTA_REJECT_EXACT:
                continue
            if _MENU_META_HEADING_RE.match(t):
                continue
            if tl[:50] in seen_texts:
                continue
            seen_texts.add(tl[:50])
            ctas.append({"text": t, "url": None, "type": "text_cta"})

    return ctas[:25]


# ---------------------------------------------------------------------------
# Pricing extraction (by business type)
# ---------------------------------------------------------------------------

def extract_pricing_v2(text, url, business_model=None, soup=None):
    """Return pricing dict appropriate for the business model."""
    primary = (business_model or "").lower()

    if primary in ("plugin_software", "saas"):
        return _extract_saas_pricing(text)
    if primary == "restaurant":
        return _extract_restaurant_pricing(text, url, soup=soup)
    if primary in ("ecommerce_brand", "retail_ecommerce"):
        return _extract_ecommerce_pricing(text)

    prices = _find_currency_prices(text)
    return {"pricesDetected": len(prices), "samplePrices": prices[:10]}


def _find_currency_prices(text):
    # Proper price pattern: $1,499.99 or $1499.99 or $49/month
    # Uses \d{1,3}(?:,\d{3})* to correctly handle comma-separated thousands
    patterns = [
        r"\$\s?\d{1,3}(?:,\d{3})*(?:\.\d{2})?(?:\s*/\s*(?:year|month|mo|yr))?",
        r"£\s?\d{1,3}(?:,\d{3})*(?:\.\d{2})?",
        r"€\s?\d{1,3}(?:,\d{3})*(?:\.\d{2})?",
    ]
    prices = []
    for p in patterns:
        for m in re.finditer(p, text, re.I):
            prices.append(clean_text(m.group()))
    return unique_list(prices)


def _extract_saas_pricing(text):
    plans = []
    seen = set()
    for m in _PLAN_PRICE_RE.finditer(text):
        name = clean_text(m.group("name"))
        amount = m.group("amount").replace(",", "")
        period = (m.group("period") or "year").lower()
        period = "year" if period in ("yr", "annual", "annually") else period
        period = "month" if period in ("mo", "monthly") else period
        key = name.lower()
        if key in seen or len(name) < 3 or len(name) > 60:
            continue
        if any(w in name.lower() for w in [" is ", " are ", " the ", " our ", " your ", " we ", " you "]):
            continue
        seen.add(key)
        plans.append({
            "name": name,
            "price": f"${amount}/{period}",
            "amount": int(amount),
            "period": period,
        })
    return {
        "plans": plans,
        "planCount": len(plans),
        "hasFreeplan": any("free" in p["name"].lower() for p in plans),
        "hasTrialMention": bool(re.search(r'\b(?:free\s+trial|try\s+free|trial)\b', text, re.I)),
    }


def _extract_ecommerce_pricing(text):
    """Extract ecommerce-style price signals (ranges, sale mentions)."""
    prices = _find_currency_prices(text)
    amounts = []
    for p in prices:
        m = re.search(r'[\d,]+(?:\.\d{2})?', p.replace(",", ""))
        if m:
            try:
                amounts.append(float(m.group().replace(",", "")))
            except ValueError:
                pass
    result = {
        "samplePrices": prices[:10],
        "pricesDetected": len(prices),
        "hasSalePrices": bool(re.search(r'\b(?:sale|was|now|save|off|discount)\b', text, re.I)),
    }
    if amounts:
        result["minPrice"] = min(amounts)
        result["maxPrice"] = max(amounts)
    return result


# ---------------------------------------------------------------------------
# Restaurant pricing / menu extraction
# ---------------------------------------------------------------------------

# Currency detection: domain extension → currency code
_DOMAIN_CURRENCY_MAP = {
    ".pk": ("PKR", "medium"),
    ".in": ("INR", "medium"),
    ".uk": ("GBP", "medium"),
    ".ae": ("AED", "medium"),
    ".sa": ("SAR", "medium"),
    ".ca": ("CAD", "medium"),
    ".au": ("AUD", "medium"),
    ".eu": ("EUR", "medium"),
    ".de": ("EUR", "medium"),
    ".fr": ("EUR", "medium"),
}


def _detect_restaurant_currency(url, text):
    """Return (currency_code, confidence) based on domain TLD and text signals."""
    url_l = (url or "").lower()
    for ext, (code, conf) in _DOMAIN_CURRENCY_MAP.items():
        if url_l.endswith(ext) or (f"{ext}/" in url_l):
            return code, conf
    # Text signals
    if re.search(r'\brs\.?\s*\d{3,}|\bpkr\b', text, re.I):
        return "PKR", "high"
    if re.search(r'£\s*\d', text):
        return "GBP", "high"
    if re.search(r'€\s*\d', text):
        return "EUR", "high"
    if re.search(r'\binr\b|₹', text, re.I):
        return "INR", "high"
    return "USD", "low"


def _extract_restaurant_pricing(text, url, soup=None):
    """Extract menu items (with category) and price range from restaurant page text.

    Category-aware: when `soup` is provided, walks heading-delimited sections to
    tag each menu item with its parent heading (e.g. "Starters", "Mains").
    Falls back to plain line-by-line scan when soup is not available.
    """
    currency, currency_confidence = _detect_restaurant_currency(url, text)
    menu_items = []
    seen_names = set()

    def _clean_menu_item_name(raw_name):
        """Strip category prefix bleed and description suffix from a raw item name.

        Two problems handled:
        1. Category prepended: "SALADS RAITAS' & SIDES Chicken apple salad"
           → the ALL-CAPS category label bled into the name via Strategy B text scan.
        2. Description appended: "Boti (8pcs) Boneless chicken with velvety sauce"
           → text after quantity descriptor (8pcs) is a description, not the name.
        """
        name = raw_name.strip()
        # Strip ALL-CAPS category prefix (≥2 words) followed by a Title-Case item name.
        # Pattern: "SALADS RAITAS' & SIDES " before "Chicken..."
        m_prefix = re.match(r'^([A-Z][A-Z\s\'\&\.]{8,}?)\s+(?=[A-Z][a-z])', name)
        if m_prefix:
            prefix_words = m_prefix.group(1).strip().split()
            if 2 <= len(prefix_words) <= 6:
                name = name[m_prefix.end():].strip()
        # Trim description suffix: truncate after quantity descriptor "(Npcs)" or "(Ng)"
        # e.g. "Boti (8pcs) Boneless chicken..." → "Boti (8pcs)"
        m_qty = re.search(r'(\(\d+\s*(?:pcs?|pieces?|g|kg|ml|oz|ltr?)\))', name, re.I)
        if m_qty:
            name = name[:m_qty.end()].strip()
        return name

    # Bare cut/portion suffixes that are NOT complete dish names
    _BARE_CUT_RE = re.compile(
        r'^(?:boti|tikka\s+boti|seekh|reshmi|chapli|half|full|regular|small|large)'
        r'(?:\s*\(\d+\s*pcs?\))?$',
        re.I,
    )

    def _validate_name(name):
        """Return True if name is acceptable as a menu item name."""
        if not name or len(name) < 4 or len(name) > 80:
            return False
        if not re.search(r'[A-Za-z]{3,}', name):
            return False
        if name[0].islower():
            return False  # mid-sentence fragment
        if len(name.split()) > 8:
            return False  # description/sentence, not a dish name
        # Reject pure currency code captured as name
        if re.match(r'^(?:PKR|INR|Rs\.?|AED|SAR|USD|GBP|EUR)$', name, re.I):
            return False
        # Reject known nav/location terms
        if name.lower() in {"location", "address", "map", "directions",
                             "contact", "phone", "email", "website"}:
            return False
        # Reject bare portion/cut labels without a main dish name
        if _BARE_CUT_RE.match(name):
            return False
        # Reject names with embedded 2-3 digit standalone numbers (malformed split)
        # e.g. "Tandoori Roti 95 Khameeri" — the 95 is from an adjacent price line
        if re.search(r'(?<!\()\s\d{2,3}\s(?!\d)', name):
            return False
        return True

    def _add_item(name, amount, category=None):
        name = _clean_menu_item_name(clean_text(name))
        if not _validate_name(name):
            return
        # Guard against years
        if re.match(r'^(?:19|20)\d{2}$', amount):
            return
        name_key = name.lower()
        if name_key in seen_names:
            return
        seen_names.add(name_key)
        price_val = int(amount)
        item = {
            "name": name,
            "price": f"{currency} {price_val}",
            "priceValue": price_val,
            "currency": currency,
        }
        if category:
            item["category"] = category
        menu_items.append(item)

    def _add_hf_item(name, h_amount, f_amount, category=None):
        """Add a menu item with Half/Full price variants."""
        name = _clean_menu_item_name(clean_text(name))
        if not _validate_name(name):
            return
        if (re.match(r'^(?:19|20)\d{2}$', h_amount)
                or re.match(r'^(?:19|20)\d{2}$', f_amount)):
            return
        name_key = name.lower()
        if name_key in seen_names:
            return
        seen_names.add(name_key)
        h_val = int(h_amount)
        f_val = int(f_amount)
        item = {
            "name": name,
            "price": f"H {currency} {h_val} / F {currency} {f_val}",
            "currency": currency,
            "variants": [
                {"label": "H", "priceValue": h_val},
                {"label": "F", "priceValue": f_val},
            ],
        }
        if category:
            item["category"] = category
        menu_items.append(item)

    # ---- Strategy A: category-aware DOM walk (Jina sections) ----
    if soup is not None:
        # Walk all headings; collect siblings until next heading
        current_category = None
        for tag in soup.find_all(["h2", "h3", "h4", "p", "li"]):
            if tag.name in ("h2", "h3", "h4"):
                heading = clean_text(tag.get_text(" ", strip=True))
                if heading and not _MENU_META_HEADING_RE.match(heading):
                    current_category = heading
                elif heading and _MENU_META_HEADING_RE.match(heading):
                    current_category = None  # reset on meta-headings
            else:
                line_text = tag.get_text(" ", strip=True)
                # Try H/F variant pattern first (e.g. "Chicken Karahi — H 2150 / F 3150")
                for m in _MENU_HF_PRICE_RE.finditer(line_text):
                    _add_hf_item(m.group(1), m.group(2), m.group(3), current_category)
                # Then single-price items (skip names already captured by H/F scan)
                for m in _MENU_PRICE_RE.finditer(line_text):
                    _add_item(m.group(1), m.group(2), current_category)

    # ---- Strategy B: plain line-by-line scan (fallback / additional items) ----
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        # H/F variants first
        for m in _MENU_HF_PRICE_RE.finditer(line):
            _add_hf_item(m.group(1), m.group(2), m.group(3), None)
        # Then single-price items
        for m in _MENU_PRICE_RE.finditer(line):
            _add_item(m.group(1), m.group(2), None)

    # Price range — gather amounts from single-price and variant items
    amounts = []
    for i in menu_items:
        if i.get("priceValue"):
            amounts.append(i["priceValue"])
        elif i.get("variants"):
            amounts.extend(v["priceValue"] for v in i["variants"] if v.get("priceValue"))
    price_range = None
    if amounts:
        price_range = {
            "min": min(amounts),
            "max": max(amounts),
            "currency": currency,
        }

    return {
        "menuItems": menu_items[:40],
        "menuPrices": menu_items[:40],
        "currency": currency,
        "currencyConfidence": currency_confidence,
        "priceRange": price_range,
    }


def _extract_menu_categories(soup, text):
    """Extract restaurant menu category names using two strategies.

    Strategy 1: Section headings that contain price-pattern matches in their
                body text (most reliable — these ARE menu sections).
    Strategy 2: Headings that match known menu category keywords.
    """
    cats = []
    seen = set()

    _MENU_CAT_KW_RE = re.compile(
        r'\b(?:starter|starters|appetizer|appetizers|mains?|main\s+course|'
        r'entree|entrees|dessert|desserts|sides|salad|salads|raita|raitas|'
        r'drinks?|beverages?|soup|soups|shorba|kebab|kebabs?|tikka|karahi|'
        r'biryani|bbq|grill|grills?|naan|bread|breads?|rice|pulao|'
        r'kids?|children|pizza|pasta|burger|burgers?|sandwich|sandwiches|'
        r'seafood|fish|chicken|beef|lamb|mutton|vegetarian|vegan|'
        r'combo|deal|deals|special|specials|snack|snacks|wrap|wraps|'
        r'handi|daal|lentil|masala|curry|curries|roti|paratha|'
        r'platter|platters|tandoor|barbeque|charcoal|'
        # South-Asian / Urdu menu terms
        r'mehfil|riwayaat|lazeez|nafeese|nahari|nihari|haleem|salan|'
        r'murgh|gosht|seekh|reshmi|chapli|shami|bun\s+kabab|'
        r'to\s+start|finger\s+food|street\s+food|'
        r'ala\s+carte|a\s+la\s+carte)\b',
        re.I,
    )

    def _add_cat(heading):
        heading = clean_text(heading)
        if not heading or len(heading) < 3 or len(heading) > 80:
            return
        # Skip meta-headings like "Our Menu", "Visit ...", "Welcome to"
        if _MENU_META_HEADING_RE.match(heading):
            return
        # Reject separator-joined navigation strings
        # e.g. "LAHORI KARAHI · BBQ · HANDI · BIRYANI" (nav strip, not a category)
        if '·' in heading or '◆' in heading:
            return
        # Also reject obvious non-category terms not caught by _MENU_META_HEADING_RE
        _hl = heading.lower().strip()
        if _hl in {
            "location", "visit us", "directions", "map",
            "our story", "our team", "careers", "jobs",
        }:
            return
        k = _hl
        if k in seen:
            return
        seen.add(k)
        cats.append(heading)

    def _has_real_price(text_blob):
        """Return True only if text_blob contains a price match that isn't a year."""
        for m in _MENU_PRICE_RE.finditer(text_blob):
            amount = m.group(2)
            if re.match(r'^(?:19|20)\d{2}$', amount):
                continue  # skip year-like numbers
            return True
        # Fallback: explicit currency code followed by a non-year number
        # Catches "PKR 1475", "Rs. 795", "INR 550" that _MENU_PRICE_RE may miss
        for m in re.finditer(
            r'(?:PKR|INR|Rs\.?|AED|SAR)\s*(\d{3,6})\b', text_blob, re.I
        ):
            if not re.match(r'^(?:19|20)\d{2}$', m.group(1)):
                return True
        return False

    # Strategy 1: h3/h4 sections with price-pattern matches (highest precision)
    # These are actual category sub-sections (e.g. "### TO START WITH")
    for sec in soup.find_all("section"):
        h = sec.find(["h3", "h4"])
        if not h:
            continue
        heading = clean_text(h.get_text(" ", strip=True))
        sec_text = sec.get_text(" ", strip=True)
        if _has_real_price(sec_text):
            _add_cat(heading)

    # Strategy 1b: h2 sections with price matches (only if no h3 cats found yet)
    if len(cats) < 3:
        for sec in soup.find_all("section"):
            h = sec.find("h2")
            if not h:
                continue
            heading = clean_text(h.get_text(" ", strip=True))
            sec_text = sec.get_text(" ", strip=True)
            if _has_real_price(sec_text):
                _add_cat(heading)

    # Strategy 1c: H2/H3/H4 headings followed by price-matched sibling text
    for h_tag in soup.find_all(["h2", "h3", "h4"]):
        heading = clean_text(h_tag.get_text(" ", strip=True))
        if not heading:
            continue
        k = heading.lower()
        if k in seen:
            continue
        sibling_text = ""
        for sib in h_tag.find_next_siblings():
            if sib.name in ("h2", "h3", "h4"):
                break
            sibling_text += " " + sib.get_text(" ", strip=True)
            if len(sibling_text) > 500:
                break
        if _has_real_price(sibling_text):
            _add_cat(heading)
        else:
            # Also check the h_tag's PARENT container for prices
            # (handles layouts where heading is in a wrapper div)
            parent = h_tag.parent
            if parent and parent.name not in ("body", "html"):
                parent_text = parent.get_text(" ", strip=True)
                if k not in parent_text.lower()[:20]:  # avoid re-checking heading itself
                    pass
                elif _has_real_price(parent_text):
                    _add_cat(heading)

    # Strategy 2: keyword headings not already captured (lowest precision)
    for h_tag in soup.find_all(["h2", "h3", "h4"]):
        heading = clean_text(h_tag.get_text(" ", strip=True))
        if not heading:
            continue
        if _MENU_META_HEADING_RE.match(heading):
            continue
        k = heading.lower()
        if k in seen:
            continue
        if _MENU_CAT_KW_RE.search(heading):
            _add_cat(heading)

    # Strategy 1d: sections with price matches but NO heading tag.
    # The first <p> inside the section IS the category label (Zouq-style).
    for sec in soup.find_all("section"):
        if sec.find(["h2", "h3", "h4"]):
            continue  # Already covered by Strategies 1–1c
        sec_text = sec.get_text(" ", strip=True)
        if not _has_real_price(sec_text):
            continue
        first_p = sec.find("p")
        if not first_p:
            continue
        first_p_text = clean_text(first_p.get_text(" ", strip=True))
        # Must be a short, non-numeric string (category label, not a price line)
        if first_p_text and 3 <= len(first_p_text) <= 80 and not re.search(r'\d{3,}', first_p_text):
            _add_cat(first_p_text)

    # Strategy 3: scan <p>/<li> tags directly (more reliable than text.splitlines()
    # because soup.get_text() produces one long line without newlines in Jina mode).
    # Catches Zouq-style menus where category names appear as paragraph/list elements.
    for tag in soup.find_all(["p", "li"]):
        t = clean_text(tag.get_text(" ", strip=True))
        if not t or len(t) < 3 or len(t) > 70:
            continue
        if _MENU_META_HEADING_RE.match(t):
            continue
        if not _MENU_CAT_KW_RE.search(t):
            continue
        # Reject sentences (end with punctuation or very long)
        if re.search(r'[.!?]$', t):
            continue
        words = t.split()
        if len(words) > 8:
            continue
        # Must look like a heading: no price-like number
        if re.search(r'\d{3,}', t):
            continue
        _add_cat(t)

    return cats[:15]


# ---------------------------------------------------------------------------
# Trust signals, services, value propositions
# ---------------------------------------------------------------------------

_TRUST_KW_RE = re.compile(
    r'\b(?:sia[- ]licens(?:ed|e)|licensed|accredited|certified|'
    r'insured|bonded|vetted|dbs[- ]check(?:ed)?|crb[- ]check(?:ed)?|'
    r'iso[\s\-]\d+|award[- ]winning|industry[- ]leading|'
    r'trusted|guarantee(?:d)?|proven|verified|'
    r'\d+\+?\s*years?\s+(?:of\s+)?(?:experience|serving)|'
    r'\d+\+?\s*(?:clients?|customers?|projects?|businesses?)\s+(?:served|helped|supported)|'
    r'24/7|round[- ]the[- ]clock|emergency|rapid\s+response|'
    r'fully\s+(?:insured|licensed|bonded|vetted)|'
    r'no\s+hidden\s+(?:fees?|costs?|charges?)|transparent\s+pricing|'
    r'free\s+(?:quote|consultation|estimate|assessment))\b',
    re.I,
)


def _extract_trust_signals(soup, text):
    """Extract trust/credibility signals from page text."""
    signals = []
    seen = set()
    for m in _TRUST_KW_RE.finditer(text):
        sig = clean_text(m.group())
        k = sig.lower()
        if k not in seen and len(sig) > 3:
            seen.add(k)
            signals.append(sig)
    return signals[:10]


_VP_REJECT_RE = re.compile(
    r'^\s*(?:home|about|services?|contact|portfolio|gallery|blog|news|'
    r'login|sign\s+in|register|privacy|terms|sitemap|cookie|careers?|'
    r'our\s+(?:team|company|story)|learn\s+more|read\s+more|click\s+here|'
    r'see\s+(?:all|more)|view\s+(?:all|more)|'
    r'find\s+a\s+store|join\s+us|help|stores?|'
    r'shop\s+\w+(?:\s+\w+)?|'
    r'rep\s+your\s+team|rep\s+the\s+team|'
    # Samsung utility/nav strings
    r'buy\s+direct\s+get\s+more|samsung\s+rewards|samsung\s+offer\s+programs?|'
    r'samsung\s+care\+?|samsung\s+experience\s+stores?|certified\s+re[- ]newed|'
    r'apps\s*&\s*services|for\s+business|galaxy\s+smartphone|'
    r'mobile$|tv\s*&\s*av|accessories$|'
    # Samsung product-family nav labels (not value props)
    r'galaxy\s+(?:tab|book|watch|buds|ring|phones?|smartphones?)(?:\s|$)|'
    r'father.?s\s+day(?:\s+gifts?)?|samsung\s+trade[- ]?in|'
    r'sound\s+devices?|vacuum\s+cleaners?|memory\s+(?:&|and)\s+storage|'
    r'support\s+home|manual\s+(?:&|and)\s+software|'
    # Samsung support / account / warranty / recall strings (Issue 3)
    r'warranty\s+information|service\s+center|request\s+a\s+repair|'
    r'track\s+repair|order\s+help|samsung\s+community|'
    r'slide.?in\s+electric\s+range\s+recall|how\s+to\s+recycle|'
    r'why\s+samsung\s+account|product\s+registration|samsung\s+account\s+faq|'
    # Websouls/hosting nav labels (not value props)
    r'billing\s+area|generate\s+a\s+lead|'
    # Generic policy / legal nav labels (Issue 11)
    r'acceptable\s+use\s+policy|privacy\s+policy)\s*$',
    re.I,
)

# Compound nav-strip detector: multiple nav terms in one string
# e.g. "Find a Store Help Join Us Sign In" — these are nav bars, not value props
_NAV_COMPOUND_RE = re.compile(
    r'\b(?:find\s+a\s+store|sign\s+in|join\s+us|my\s+account|log\s+in|'
    r'create\s+account|order\s+status)\b',
    re.I,
)


def _extract_value_props(soup, text):
    """Extract short value proposition phrases from li/strong tags.

    Value propositions are SHORT (≤100 chars), non-navigational phrases
    that articulate a benefit or differentiator.
    """
    vps = []
    seen = set()

    _BARE_JINA_LINK_RE = re.compile(r'\[\]\([^)]*\)')

    def _add(t):
        # Strip bare Jina link patterns [](url) before processing
        t = _BARE_JINA_LINK_RE.sub('', t).strip()
        t = clean_text(t)
        k = t.lower()
        if not t or k in seen:
            return
        if len(t) < 5 or len(t) > 100:
            return
        if _VP_REJECT_RE.match(t):
            return
        # Filter video player / caption noise (Nike language list, player UI)
        if _is_video_noise_line(k):
            return
        # Filter Apple/utility nav fragments
        if _CTA_NAV_TEXT_REJECT_RE.match(t):
            return
        # Must have some substantive content
        if not re.search(r'[A-Za-z]{3,}', t):
            return
        # Reject single plain words (Apple nav labels: "iPhone", "Watch", "Entertainment")
        # Allow short tokens with special chars like "24/7", "SIA-licensed", "100% Guaranteed"
        words = [w for w in re.split(r'[\s&]+', t) if len(w) >= 3]
        if len(words) < 2 and not re.search(r'[-/+®™@%\d]', t):
            return
        # Reject compound nav strips: "Find a Store Help Join Us Sign In"
        if len(_NAV_COMPOUND_RE.findall(t)) >= 2:
            return
        seen.add(k)
        vps.append(t)

    # From <li> tags (bullet points) — skip nav/header/footer list items
    for li in soup.find_all("li"):
        if li.find_parent(["nav", "header", "footer"]):
            continue
        t = clean_text(li.get_text(" ", strip=True))
        _add(t)

    # From <strong> tags (bold callouts)
    for strong in soup.find_all("strong"):
        t = clean_text(strong.get_text(" ", strip=True))
        _add(t)

    return vps[:12]


def _extract_service_list(soup, text):
    """Extract service names from section headings, li, strong, and p elements.

    Supports Jina-mode HTML where services are expressed as ## / ### headings
    inside a "What we offer" parent section (e.g. ARFM security services).

    Returns a list of strings or objects {name, description}.
    """
    services = []
    seen = set()

    _SVC_NOISE_RE = re.compile(
        r'^\s*(?:home|about(?:\s+us)?|why\s+us|contact|privacy(?:\s+policy)?|'
        r'terms|sitemap|login|sign\s+in|careers?|news|blog|gallery|'
        r'portfolio|clients?|billing\s+area|generate\s+a\s+lead|'
        r'announcement|acceptable\s+use\s+policy|feedback|my\s+account|'
        r'our\s+team|get\s+(?:a\s+)?quote|'
        r'free\s+(?:quote|consultation)|learn\s+more|read\s+more|click|see\s+all|'
        r'view\s+(?:all|more)|find\s+out\s+more)\s*$',
        re.I,
    )

    def _add(name, description=None):
        name = clean_text(name)
        k = name.lower()
        if not name or k in seen or len(name) < 4 or len(name) > 80:
            return
        if _SVC_NOISE_RE.match(name):
            return
        if not re.search(r'[A-Za-z]{3,}', name):
            return
        seen.add(k)
        if description:
            services.append({"name": name, "description": clean_text(description)})
        else:
            services.append({"name": name})

    # Strategy 1: <section> elements whose heading matches SERVICE_HEADING_RE
    # (Jina mode — "## What we offer\n### Door security supervisors\n...")
    for sec in soup.find_all("section"):
        inner_h = sec.find(["h2", "h3"])
        if not inner_h:
            continue
        if not _SERVICE_HEADING_RE.search(inner_h.get_text(" ", strip=True)):
            continue
        # Items in this "What we offer" section may be:
        #   a) nested <section> elements (Jina h3 sub-sections)
        #   b) <ul><li> lists
        #   c) <p> tags
        for child in sec.find_all("section"):
            child_h = child.find(["h3", "h4"])
            if not child_h:
                continue
            svc_name = clean_text(child_h.get_text(" ", strip=True))
            desc_p = child_h.find_next_sibling("p")
            svc_desc = clean_text(desc_p.get_text(" ", strip=True)) if desc_p else None
            _add(svc_name, svc_desc)
        for li in sec.find_all("li"):
            _add(li.get_text(" ", strip=True))
        if not services:
            for p in sec.find_all("p"):
                _add(p.get_text(" ", strip=True))

    # Strategy 2: h2/h3 tags matching SERVICE_HEADING_RE with ul/li/p siblings
    for h_tag in soup.find_all(["h2", "h3"]):
        if not _SERVICE_HEADING_RE.search(h_tag.get_text(" ", strip=True)):
            continue
        for sib in h_tag.find_next_siblings():
            if sib.name in ("h2", "h3"):
                break
            if sib.name in ("ul", "ol"):
                for li in sib.find_all("li"):
                    _add(li.get_text(" ", strip=True))
            elif sib.name == "p":
                _add(sib.get_text(" ", strip=True))

    # Strategy 3: <strong> tags (bold service names) — only if strategies above found nothing
    if len(services) < 2:
        for strong in soup.find_all("strong"):
            _add(strong.get_text(" ", strip=True))

    # Strategy 4: fallback — any li that looks service-like (2–8 words)
    if len(services) < 3:
        for li in soup.find_all("li"):
            t = clean_text(li.get_text(" ", strip=True))
            words = t.split()
            if 2 <= len(words) <= 8:
                _add(t)

    return services[:12]


# ---------------------------------------------------------------------------
# Contact information
# ---------------------------------------------------------------------------

def extract_contact_info(soup, text, url, primary_model=None):
    """Extract phone, email, service area, and WhatsApp links from page text.

    For global ecommerce brands (Apple, Nike, Samsung) serviceArea is
    suppressed because language/region strings in Jina text would otherwise
    produce false service area matches.
    """
    phone = None
    email = None
    service_area = []
    whatsapp_links = []

    # Phone
    for m in _PHONE_DIGITS_RE.finditer(text):
        candidate = m.group()
        # Skip years and copyright
        if _YEAR_RANGE_RE.search(candidate) or _COPYRIGHT_RE.search(candidate):
            continue
        digits = re.sub(r'\D', '', candidate)
        if 7 <= len(digits) <= 15:
            phone = clean_text(candidate)
            break

    # Email
    m_email = re.search(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', text)
    if m_email:
        email = m_email.group()

    # Service area — suppressed for global ecommerce brands and hosting providers
    # (hosting providers have Lahore/Pakistan in text but serve globally)
    _is_global_brand = primary_model in (
        "ecommerce_brand",
        "retail_ecommerce",
        "brand_editorial_homepage",
        "contentPublisher",
        "web_hosting_provider",
    )

    if not _is_global_brand:
        area_map = {
            "london": "London",
            "birmingham": "Birmingham",
            "manchester": "Manchester",
            "leeds": "Leeds",
            "glasgow": "Glasgow",
            "sheffield": "Sheffield",
            "edinburgh": "Edinburgh",
            "liverpool": "Liverpool",
            "bristol": "Bristol",
            "cardiff": "Cardiff",
            "lahore": "Lahore",
            "karachi": "Karachi",
            "islamabad": "Islamabad",
            "dubai": "Dubai",
            "abu dhabi": "Abu Dhabi",
            "new york": "New York",
            "los angeles": "Los Angeles",
            "chicago": "Chicago",
            "houston": "Houston",
            "toronto": "Toronto",
            "sydney": "Sydney",
            "melbourne": "Melbourne",
        }
        tl = text.lower()
        for key, val in area_map.items():
            if key in tl:
                service_area.append(val)

    # WhatsApp links (wa.me or whatsapp.com click-to-chat links)
    if soup is not None:
        _WA_RE = re.compile(r'(?:wa\.me|whatsapp\.com/send)', re.I)
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            if _WA_RE.search(href):
                # Normalize: extract phone number from wa.me/+923001234567
                m = re.search(r'wa\.me/(\+?[\d]+)', href)
                wa_number = m.group(1) if m else None
                whatsapp_links.append({
                    "url": href,
                    "number": wa_number,
                    "label": clean_text(a.get_text(" ", strip=True)) or None,
                })
        # Deduplicate by URL
        seen_wa = set()
        deduped_wa = []
        for w in whatsapp_links:
            if w["url"] not in seen_wa:
                seen_wa.add(w["url"])
                deduped_wa.append(w)
        whatsapp_links = deduped_wa

    return {
        "phone": phone,
        "email": email,
        "serviceArea": service_area,
        "whatsappLinks": whatsapp_links,
    }


# ---------------------------------------------------------------------------
# Brand extensions (sub-brands, sister stores)
# ---------------------------------------------------------------------------

def _extract_brand_extensions(soup, url):
    """Return list of {name, type, links[], domain} grouped by external domain."""
    from urllib.parse import urlparse

    base_domain = ""
    try:
        parsed = urlparse(url or "")
        base_domain = parsed.netloc.lower().replace("www.", "")
    except Exception:
        pass

    _EXT_TYPE_MAP = {
        "food": "online food store",
        "shop": "online store",
        "store": "online store",
        "app": "mobile app",
        "blog": "blog",
        "delivery": "delivery service",
        "order": "online ordering",
        "book": "booking platform",
        "reserve": "reservation platform",
        "catering": "catering service",
    }

    by_domain = {}
    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        if not href.startswith("http"):
            continue
        try:
            link_domain = urlparse(href).netloc.lower().replace("www.", "")
        except Exception:
            continue
        if not link_domain or link_domain == base_domain:
            continue
        # Skip analytics/CDN/tracking/social domains
        if any(x in link_domain for x in [
            "google", "facebook", "twitter", "instagram", "youtube",
            "tiktok", "pinterest", "linkedin", "snapchat",
            "apple.com/app", "play.google", "cdn.", "static.", "fonts.",
            "analytics", "tracking", "pixel", "tag.", "attn.", "scdn.",
        ]):
            continue
        # Skip WhatsApp — WhatsApp goes to contact.whatsappLinks, not brandExtensions
        if "wa.me" in link_domain or "whatsapp.com" in link_domain:
            continue
        # Skip Apple ecosystem subdomains (TV, Music, Apps, etc.) — not third-party brands
        if link_domain in _APPLE_ECOSYSTEM_SUBDOMAINS or (
            link_domain.endswith(".apple.com") and link_domain != base_domain
        ):
            continue
        # Skip Samsung utility/account/support subdomains — not brand extensions
        _SAMSUNG_BASE = "samsung.com"
        if link_domain.endswith(_SAMSUNG_BASE) and link_domain != base_domain:
            if any(x in link_domain for x in [
                "account", "order-help", "csr", "community", "shop.",
                "news.", "insights.", "image-us.", "checkout",
                "design.",  # design.samsung.com is not a consumer brand extension
            ]):
                continue
        # Skip Samsung shortlink/redirect domains (e.g. shopsamsung.page.link)
        if "shopsamsung.page.link" in link_domain or "samsung.page.link" in link_domain:
            continue
        # Skip account/login/auth utility domains
        if any(x in link_domain for x in ["accounts.", "login.", "auth.", "signin.", "sso."]):
            continue

        tl = a.get_text(" ", strip=True).lower()
        # Determine type
        ext_type = "external site"
        for kw, ty in _EXT_TYPE_MAP.items():
            if kw in link_domain or kw in tl:
                ext_type = ty
                break

        if link_domain not in by_domain:
            # Try to build a clean brand name from the domain
            brand_slug = link_domain.split(".")[0].replace("-", " ").replace("_", " ")
            # Known overrides
            link_text_lower = a.get_text(" ", strip=True).lower()
            if "food to go" in link_text_lower or "foodtogo" in link_domain:
                brand_name = "Food To Go"
            else:
                brand_name = brand_slug.title()
            by_domain[link_domain] = {
                "name": brand_name,
                "type": ext_type,
                "links": [],
                "domain": link_domain,
            }

        href_clean = href.split("?")[0].split("#")[0]
        if href_clean not in by_domain[link_domain]["links"]:
            by_domain[link_domain]["links"].append(href_clean)

    return list(by_domain.values())[:5]


# ---------------------------------------------------------------------------
# Featured products / collections from DOM (CSS-rendered pages)
# ---------------------------------------------------------------------------

def extract_featured_products(soup, url):
    """Extract featured product cards from DOM (non-Jina HTML)."""
    products = []
    seen = set()
    base = url or ""

    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        if not looks_like_product_url(href):
            continue
        title = clean_text(a.get_text(" ", strip=True))
        if not title or len(title) < 2 or len(title) > 120:
            continue
        k = title.lower()
        if k in seen:
            continue
        seen.add(k)
        full_url = urljoin(base, href) if not href.startswith("http") else href
        # Find price nearby
        price = None
        parent = a.parent
        if parent:
            price_m = re.search(r'[$£€₹]\s*[\d,]+(?:\.\d{2})?', parent.get_text())
            if price_m:
                price = price_m.group()
        products.append({"title": title, "url": full_url, "price": price})

    return products[:20]


_COLL_PATH_RE = re.compile(
    r'/(?:collections?|categories?|category|shop|store|catalog|'
    r'w/[a-z0-9\-]{3,}|men|women|kids|sale|new\-arrivals|best\-sellers)',
    re.I,
)

# Utility paths that look like categories but are not meaningful collections
_COLL_UTILITY_URL_RE = re.compile(
    r'/(?:bag|cart|checkout|account|login|signin|wishlist|help|support'
    r'|accessibility|privacy|terms|cookie|sitemap|careers|newsroom|investor'
    r'|newsletter|unsubscribe|store/go|store/product/buy'
    r'|shop/goto|us/shop/goto)',
    re.I,
)


def extract_featured_categories(soup, url):
    """Extract featured category / collection links from DOM."""
    cats = []
    seen = set()
    base = url or ""

    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        if not looks_like_category_url(href):
            continue
        # Skip utility/account/footer paths that match category patterns superficially
        if _COLL_UTILITY_URL_RE.search(href):
            continue
        title = clean_text(a.get_text(" ", strip=True))
        if not title or len(title) < 2 or len(title) > 100:
            continue
        if title.lower() in _CTA_REJECT_EXACT:
            continue
        k = title.lower()
        if k in seen:
            continue
        seen.add(k)
        full_url = urljoin(base, href) if not href.startswith("http") else href
        cats.append({"text": title, "url": full_url})

    return cats[:20]


# ---------------------------------------------------------------------------
# Bot-protection / empty-shell detection
# ---------------------------------------------------------------------------

def _is_empty_shell_page(soup, html, headers):
    """Return True if the page is a bot-protection or empty-shell response.

    Detects:
    - Akamai bot-manager cookie injection (ak_bmsc in Set-Cookie header or meta)
    - Virtually no visible body text (< 120 chars after stripping tags)
    - Pages that have only a <head> and a tiny <body> (JS-rendered shell not yet loaded)
    """
    # Check response headers for Akamai bot cookie
    if headers:
        set_cookie = ""
        if isinstance(headers, dict):
            set_cookie = headers.get("set-cookie", "") or headers.get("Set-Cookie", "")
        if _EMPTY_SHELL_COOKIE_RE.search(set_cookie):
            return True

    # Check inline meta / script text for Akamai signature
    if html and _EMPTY_SHELL_COOKIE_RE.search(html[:4096]):
        return True

    # Check visible body text length
    if soup:
        body = soup.find("body")
        visible = body.get_text(" ", strip=True) if body else soup.get_text(" ", strip=True)
        if len(visible) < 120:
            return True

    return False


# ---------------------------------------------------------------------------
# Product teaser extraction for brand homepages (Nike /t/ links)
# ---------------------------------------------------------------------------

def _extract_product_teasers(soup, url):
    """Extract product teaser links from brand homepages (e.g. Nike /t/ paths).

    These are not full product cards but href links to product pages that
    appear in hero/campaign sections. Returns list of {title, url} dicts.

    Handles:
    - Standard <a href="/t/slug">Title</a> links (DOM and Jina)
    - Jina bare-link pattern: li/p elements with [](url) and adjacent text
    """
    teasers = []
    seen = set()
    base = url or ""

    def _add(title, href):
        if not title or len(title) < 2 or len(title) > 120:
            return
        k = title.lower()
        if k in seen:
            return
        seen.add(k)
        full_url = urljoin(base, href) if not href.startswith("http") else href
        teasers.append({"title": title, "url": full_url})

    # Pass 1: standard <a> tags (includes image-linked products from Jina HTML)
    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        if not _PRODUCT_TEASER_PATH_RE.search(href):
            continue
        title = clean_text(a.get_text(" ", strip=True))
        if not title:
            # Image-linked product (<a href="/t/..."><img/></a>) — generate from slug
            title = _slug_to_title(href) or ""
        _add(title, href)

    # Pass 2: Jina bare-link pattern [](https://...nike.com/t/slug)
    _BARE_LINK_RE2 = re.compile(r'\[\]\((https?://[^)]+/t/[^)]+)\)')
    for el in soup.find_all(["li", "p"]):
        el_html = str(el)
        for m in _BARE_LINK_RE2.finditer(el_html):
            href = m.group(1)
            # Extract surrounding text as title
            el_copy = BeautifulSoup(el_html, "lxml")
            for img in el_copy.find_all("img"):
                img.decompose()
            raw = _BARE_LINK_RE2.sub("", el_copy.get_text(" ", strip=True))
            title = clean_text(raw)
            if title:
                _add(title, href)

    return teasers[:20]


# ---------------------------------------------------------------------------
# Final normalization layer
# ---------------------------------------------------------------------------

def finalize_homepage_result(result):
    """Populate top-level content/ecommerce/products/crawl/success from homepage.

    This is the final normalization step that ensures downstream consumers
    (competitive_schema, quality scorer, etc.) can read standard fields
    without navigating into result["homepage"].
    """
    hp = result.get("homepage") or {}
    bm = hp.get("businessModel") or {}
    primary_model = (bm.get("primaryModel") or "").lower()

    # ---- content block (title, description, sections) ----------------------
    hero = hp.get("hero") or {}
    result.setdefault("content", {})
    result["content"].update({
        "title": hp.get("title") or result.get("content", {}).get("title"),
        # siteName: expose for competitive_schema scoring (prevents -0.05 penalty)
        "siteName": (
            result.get("content", {}).get("siteName")
            or hp.get("title")
        ),
        "description": hero.get("subheadline") or hero.get("supportingText"),
        "sections": hp.get("sections") or [],
    })

    # ---- ecommerce block ---------------------------------------------------
    result.setdefault("ecommerce", {})
    result["ecommerce"].update({
        "primaryModel": primary_model,
        "featuredCollections": result.get("ecommerce", {}).get("featuredCollections") or [],
        "featuredPrograms": result.get("ecommerce", {}).get("featuredPrograms") or [],
        "hasEcommerceSignals": result.get("ecommerce", {}).get("hasEcommerceSignals", False),
    })

    # ---- products list at root level (required by competitive schema) ------
    if "products" not in result or result["products"] is None:
        result["products"] = (
            result.get("ecommerce", {}).get("featuredProducts") or []
        )

    # ---- propagate productTeasers → products when products list is empty ----
    # For ecommerce_brand homepages (Nike, etc.) where product teaser links are
    # the only product signal, expose them as top-level products so downstream
    # consumers (competitive_schema, quality scorer) reflect them.
    if not result.get("products"):
        product_teasers = result.get("ecommerce", {}).get("productTeasers") or []
        if product_teasers:
            result["products"] = [
                {"title": t["title"], "url": t["url"], "source": "homepage_product_teaser"}
                for t in product_teasers
            ]
            # Mark ecommerce as having signals (affects hasProducts, productCountExtracted)
            ec = result.setdefault("ecommerce", {})
            if not ec.get("hasEcommerceSignals"):
                ec["hasEcommerceSignals"] = True

    # ---- success flag -------------------------------------------------------
    # A page is successful if it has ANY of: hero headline, sections, products,
    # services, menu items, or a non-empty title.
    _has_content = bool(
        hero.get("headline")
        or hero.get("campaignHero")
        or hero.get("supportingText")
        or (hp.get("sections") or [])
        or (result.get("products") or [])
        or (hp.get("services") or [])
        or (hp.get("menuItems") or [])
        or hp.get("title")
    )
    result["success"] = _has_content

    # ---- crawl metadata ----------------------------------------------------
    result.setdefault("crawl", {})
    result["crawl"].setdefault("extractionMethod", hp.get("extractionMethod", "dom"))

    return result


# ---------------------------------------------------------------------------
# Hosting plan extraction
# ---------------------------------------------------------------------------

_HOSTING_PLAN_NAME_RE = re.compile(
    r'^(?:starter|startup|basic|grow|growth|digital|business|'
    r'professional|pro|premium|enterprise|advanced|'
    r'personal|shared|managed|cloud|essential)\b',
    re.I,
)
# Plan names that indicate a server/infrastructure tier rather than shared hosting packages.
# These should be excluded from pricingPlans (they're service SKUs, not user-facing plan tiers).
_HOSTING_INFRA_PLAN_RE = re.compile(
    r'\b(?:vps|dedicated|server|bare\s+metal)\b',
    re.I,
)


def _feat_included(text, pattern):
    """Return True if pattern appears in text and isn't negated by 'Not Included' nearby."""
    for m in re.finditer(pattern, text, re.I):
        window_start = max(0, m.start() - 60)
        window = text[window_start: m.end() + 60]
        if re.search(r'not\s+included|not\s+available|✗|✕|❌', window, re.I):
            return False
        return True
    return False


def _extract_hosting_plans(sections, global_text=""):
    """Extract hosting/SaaS-style pricing plans from section headings.

    Websouls-style: section headings are plan names (Startup, Grow, Digital,
    Business) with plan details (storage, websites, bandwidth, etc.) in body text.

    global_text is used as fallback for features that appear page-wide (e.g. Free SSL).
    """
    plans = []
    seen = set()
    # Global-level flags: if present anywhere on the page, apply to all plans
    _global_ssl = bool(re.search(r'free\s+ssl|let\'?s\s+encrypt', global_text, re.I))
    _global_domain = bool(re.search(r'free\s+domain', global_text, re.I))

    for sec in sections:
        heading = (sec.get("heading") or "").strip()
        if not heading or heading.lower() in seen:
            continue
        if not _HOSTING_PLAN_NAME_RE.match(heading):
            continue
        # Exclude infrastructure tiers (VPS Hosting, Dedicated Server) — they're
        # service SKUs, not user-facing shared-hosting plan tiers.
        if _HOSTING_INFRA_PLAN_RE.search(heading):
            continue
        text = sec.get("text") or ""
        plan = {"name": heading}
        # Extract storage
        m_storage = re.search(
            r'(\d+\s*(?:GB|TB)\s*(?:SSD|NVMe)?(?:\s+Storage)?)', text, re.I
        )
        if m_storage:
            plan["storage"] = m_storage.group(1).strip()
        # Extract website count
        m_sites = re.search(r'(\d+)\s+Websites?', text, re.I)
        if m_sites:
            plan["websites"] = int(m_sites.group(1))
        # Feature flags — use negation-aware helper so "Not Included" suppresses the flag
        plan["freeDomain"] = (
            _feat_included(text, r'free\s+domain')
            or (_global_domain and not re.search(r'not\s+included', text[:80], re.I))
        )
        plan["freeBackup"] = _feat_included(text, r'free\s+backup')
        # freeSSL: check per-plan text first; fall back to page-global mention
        plan["freeSSL"] = (
            _feat_included(text, r'free\s+ssl|let\'?s\s+encrypt')
            or (_global_ssl and not re.search(r'not\s+included', text[:80], re.I))
        )
        # aiWebsiteBuilder: must be explicitly included (not "Not Included")
        plan["aiWebsiteBuilder"] = _feat_included(text, r'ai\s+website\s+builder')
        # Bandwidth
        m_bw = re.search(r'(unlimited|unmetered|\d+\s*GB)\s+bandwidth', text, re.I)
        if m_bw:
            plan["bandwidth"] = m_bw.group(1).strip().title()
        # Databases
        m_db = re.search(r'(unlimited|\d+)\s+(?:MySQL\s+)?databases?', text, re.I)
        if m_db:
            plan["databases"] = m_db.group(1).strip().title()
        seen.add(heading.lower())
        plans.append(plan)
    return plans[:8]


# ---------------------------------------------------------------------------
# Main analyzer function
# ---------------------------------------------------------------------------

def analyze_unknown_homepage(self, url, html, headers, page_type, level1):
    """Analyze an unknown-platform homepage.

    Supports:
    - Jina markdown fallback (Jina HTML produced by _jina_markdown_to_html)
    - Direct DOM (fully rendered HTML)
    - All business models: ecommerce_brand, restaurant, security_services,
      service_business, saas, lead_generation, local_business, etc.
    """
    result = self.base_result(url, html, headers, page_type, level1)
    result["source"]["extractor"] = "Unknown Homepage Extractor v3"

    # -----------------------------------------------------------------------
    # 1. Build soup; detect Jina mode
    # -----------------------------------------------------------------------
    raw_soup = BeautifulSoup(html or "", "lxml")
    jina_mode = _is_jina_mode(raw_soup)

    # Compute domain once (used for Samsung nav strip, brand products, etc.)
    _raw_domain = (url or "").lower().split("//")[-1].split("/")[0]
    domain = re.sub(r'^www\.', '', _raw_domain)

    soup = raw_soup
    # Samsung Jina: strip nav preamble sections before real homepage content
    if jina_mode and (domain == "samsung.com" or domain.endswith(".samsung.com")):
        soup = _strip_samsung_nav_from_jina_soup(soup)
    # Nike Jina: strip GNB preamble (Men/Women/Jordan etc.) before campaign sections
    elif jina_mode and (domain == "nike.com" or domain.endswith(".nike.com")):
        soup = _strip_nike_nav_from_jina_soup(soup)

    # -----------------------------------------------------------------------
    # 1b. Bot-protection / empty-shell guard (Zara, Akamai-blocked pages)
    # -----------------------------------------------------------------------
    if _is_empty_shell_page(soup, html, headers):
        result["success"] = False
        result["blocked"] = True
        result["homepage"] = {
            "title": None,
            "businessModel": {"primaryModel": "unknown", "secondaryModel": None,
                               "industry": None, "homepageStyle": [], "scores": {}},
            "hero": {},
            "sections": [],
            "ctas": [],
            "contact": {"phone": None, "email": None, "serviceArea": [],
                         "whatsappLinks": []},
            "trustSignals": {},
            "valuePropositions": [],
            "services": [],
            "serviceArea": [],
            "menuItems": [],
            "menuCategories": [],
            "brandExtensions": [],
            "warnings": ["bot_protection_or_empty_shell"],
            "extractionMethod": "jina" if jina_mode else "dom",
        }
        result["content"] = {"title": None, "description": None, "sections": []}
        result["ecommerce"] = {"primaryModel": "unknown", "featuredCollections": [],
                                "featuredPrograms": [], "hasEcommerceSignals": False}
        result["products"] = []
        result["crawl"] = {"extractionMethod": "jina" if jina_mode else "dom"}
        result["analysisReady"] = {
            "extractionQuality": {
                "score": 0,
                "warnings": ["bot_protection_or_empty_shell"],
                "missingFields": [],
            },
            "schemaVersion": "unknown-homepage-v3",
        }
        return result

    # -----------------------------------------------------------------------
    # 2. Core SEO fields
    # -----------------------------------------------------------------------
    title = get_meta(soup, property_name="og:title") \
        or (clean_text(soup.title.string) if soup.title and soup.title.string else None)
    meta_description = get_meta(soup, name="description") \
        or get_meta(soup, property_name="og:description")

    h1_tag = soup.find("h1")
    h1 = clean_text(h1_tag.get_text(" ", strip=True)) if h1_tag else None

    canonical_tag = soup.find("link", rel="canonical")
    canonical = canonical_tag.get("href") if canonical_tag else None

    full_text = soup.get_text(" ", strip=True)

    # -----------------------------------------------------------------------
    # 3. Business model classification (domain override first)
    # -----------------------------------------------------------------------
    override = _DOMAIN_OVERRIDES.get(domain)
    if not override:
        # Check parent domain (e.g. uk.samsung.com → samsung.com)
        for od, ov in _DOMAIN_OVERRIDES.items():
            if domain.endswith("." + od):
                override = ov
                break

    if override:
        business_model = {
            "primaryModel": override["primaryModel"],
            "secondaryModel": override.get("secondaryModel"),
            "industry": override.get("industry"),
            "homepageStyle": override.get("homepageStyle", []),
            "scores": {},
        }
    else:
        business_model = classify_business_model(url, full_text, soup, level1=level1)

    primary_model = (business_model.get("primaryModel") or "").lower()

    # -----------------------------------------------------------------------
    # 4. Hero extraction
    # -----------------------------------------------------------------------
    hero = extract_hero_v2(soup, jina_mode=jina_mode, url=url)

    # -----------------------------------------------------------------------
    # 5. Sections extraction
    # -----------------------------------------------------------------------
    sections = extract_sections_v2(soup, jina_mode=jina_mode)

    # -----------------------------------------------------------------------
    # 6. CTAs
    # -----------------------------------------------------------------------
    ctas = extract_ctas_v2(soup, url, business_model=primary_model)

    # Issue 6: For restaurant pages, supplement hero.primaryCtas with any
    # text_ctas from the main ctas list that are NOT already in hero.primaryCtas.
    # "Explore Our Menu" and "Book an Event" may appear outside the first hero
    # section (not captured by extract_hero_v2) but still valid hero CTAs.
    if primary_model == "restaurant":
        _hero_cta_texts = {
            c.get("text", "").lower()
            for c in hero.get("primaryCtas", [])
        }
        for _cta in ctas:
            if _cta.get("type") == "text_cta" and not _cta.get("url"):
                _ct = _cta.get("text", "").lower()
                if _ct not in _hero_cta_texts:
                    hero.setdefault("primaryCtas", []).append(_cta)
                    _hero_cta_texts.add(_ct)

    # -----------------------------------------------------------------------
    # 7. Contact info (pass primary_model to suppress serviceArea for global brands)
    # -----------------------------------------------------------------------
    contact_info = extract_contact_info(soup, full_text, url, primary_model=primary_model)

    # -----------------------------------------------------------------------
    # 8. Pricing extraction
    # -----------------------------------------------------------------------
    pricing_result = extract_pricing_v2(full_text, url, business_model=primary_model, soup=soup)

    # -----------------------------------------------------------------------
    # 9. Trust signals
    # -----------------------------------------------------------------------
    trust_signals = _extract_trust_signals(soup, full_text)

    # -----------------------------------------------------------------------
    # 10. Business-model-specific offerings
    # -----------------------------------------------------------------------
    offerings = {}

    if primary_model == "restaurant":
        # Restaurant: menus, categories, brand extensions
        menu_items_raw = pricing_result.get("menuItems", [])
        menu_categories = _extract_menu_categories(soup, full_text)
        brand_extensions = _extract_brand_extensions(soup, url)
        services = []
        value_props = _extract_value_props(soup, full_text)
        offerings = {
            "menuItems": menu_items_raw,
            "menuCategories": menu_categories,
            "brandExtensions": brand_extensions,
            "valuePropositions": value_props,
            "services": services,
        }

    elif primary_model in (
        "security_services", "service_business", "local_business",
        "lead_generation", "professional_services",
    ):
        services = _extract_service_list(soup, full_text)
        value_props = _extract_value_props(soup, full_text)
        offerings = {
            "services": services,
            "valuePropositions": value_props,
            "menuItems": [],
            "menuCategories": [],
            "brandExtensions": [],
        }

    elif primary_model == "web_hosting_provider":
        services = _extract_service_list(soup, full_text)
        value_props = _extract_value_props(soup, full_text)
        pricing_plans = _extract_hosting_plans(sections, full_text)
        offerings = {
            "services": services,
            "valuePropositions": value_props,
            "pricingPlans": pricing_plans,
            "menuItems": [],
            "menuCategories": [],
            "brandExtensions": [],
        }

    elif primary_model in ("saas", "plugin_software"):
        services = _extract_service_list(soup, full_text)
        value_props = _extract_value_props(soup, full_text)
        offerings = {
            "services": services,
            "valuePropositions": value_props,
            "menuItems": [],
            "menuCategories": [],
            "brandExtensions": [],
        }

    else:
        value_props = _extract_value_props(soup, full_text)
        offerings = {
            "services": [],
            "valuePropositions": value_props,
            "menuItems": [],
            "menuCategories": [],
            "brandExtensions": _extract_brand_extensions(soup, url),
        }

    # -----------------------------------------------------------------------
    # 11. Ecommerce signals (products, categories, collections)
    # -----------------------------------------------------------------------
    products = extract_featured_products(soup, url)
    categories = extract_featured_categories(soup, url)

    # Brand-specific product extraction from section headings (Apple, Samsung)
    brand_products = _extract_brand_products_from_sections(sections, domain)

    # Merge products with brand products
    all_products = list(products)
    seen_prod_titles = {(p.get("title") or "").lower() for p in all_products}
    for bp in brand_products:
        if (bp.get("title") or "").lower() not in seen_prod_titles:
            all_products.append(bp)

    # Samsung: apply domain-level product title filtering and " Buy" normalization
    if domain == "samsung.com" or domain.endswith(".samsung.com"):
        _samsung_filtered = []
        _samsung_seen = set()
        for _p in all_products:
            _t = (_p.get("title") or "").strip()
            # Normalize trailing " Buy" suffix (e.g. "New QLED QN80H Buy" → "New QLED QN80H")
            _t = re.sub(r'\s+buy\s*$', '', _t, flags=re.I).strip()
            if not _t:
                continue
            # Reject CTA/nav/category strings
            if _SAMSUNG_PRODUCT_REJECT_RE.match(_t):
                continue
            # Reject bare product-family names from section_text sources that have no URL
            # (e.g. "Galaxy S26", "Galaxy Buds4", "The Frame" are too generic without a URL)
            if (
                _p.get("source") == "section_text"
                and not _p.get("url")
                and _SAMSUNG_BARE_FAMILY_RE.match(_t)
            ):
                continue
            _tk = _t.lower()
            if _tk in _samsung_seen:
                continue
            _samsung_seen.add(_tk)
            _p2 = dict(_p)
            _p2["title"] = _t
            _samsung_filtered.append(_p2)
        all_products = _samsung_filtered

    # Featured collections from DOM category links
    featured_collections = [
        c for c in categories
        if _COLL_PATH_RE.search(c.get("url") or "")
    ]

    # Also pull collection URLs from CTAs (Nike /w/ bare-links come via Pass 3)
    _cta_url_set = {fc.get("url") for fc in featured_collections}
    for cta in ctas:
        cta_url = cta.get("url") or ""
        if _COLL_PATH_RE.search(cta_url) and cta_url not in _cta_url_set:
            featured_collections.append({"text": cta.get("text", ""), "url": cta_url})
            _cta_url_set.add(cta_url)
    featured_collections = featured_collections[:20]

    # For Apple: filter out utility/product-buy/trade-in URLs masquerading as collections
    if domain == "apple.com" or domain.endswith(".apple.com"):
        featured_collections = [
            c for c in featured_collections
            if not _APPLE_NON_COLLECTION_PATH_RE.search(c.get("url") or "")
        ]

    # Featured programs for ecommerce brands (Apple Trade In, Father's Day, etc.)
    featured_programs = []
    if primary_model in ("ecommerce_brand", "retail_ecommerce"):
        featured_programs = _extract_programs_from_sections(sections, all_products)

    # For Apple: split apple_program-tagged entries out of all_products and
    # merge them into featured_programs (they're not hardware products).
    _apple_prog_entries = [p for p in all_products if p.get("source") == "apple_program"]
    if _apple_prog_entries:
        all_products = [p for p in all_products if p.get("source") != "apple_program"]
        _prog_seen = {p["title"].lower() for p in featured_programs}
        for _ap in _apple_prog_entries:
            _k = _ap["title"].lower()
            if _k not in _prog_seen:
                featured_programs.append({"title": _ap["title"], "url": _ap.get("url")})
                _prog_seen.add(_k)

    # Product teasers (Nike /t/ paths, brand campaign hero links)
    product_teasers = _extract_product_teasers(soup, url)

    # hasEcommerceSignals: true for ecommerce models that have ANY signals
    _is_ecom_model = primary_model in (
        "ecommerce_brand", "retail_ecommerce", "hybrid_local_ecommerce",
    )
    _has_ecom_signals = (
        _is_ecom_model
        and (
            bool(all_products)
            or bool(categories)
            or bool(featured_collections)
            or bool(product_teasers)
            or any(
                any(k in (c.get("text") or "").lower() for k in ["shop", "buy"])
                for c in ctas
            )
        )
    )

    # -----------------------------------------------------------------------
    # 12. Restaurant menu items exposed at homepage level
    # -----------------------------------------------------------------------
    menu_items = offerings.get("menuItems", [])

    # -----------------------------------------------------------------------
    # 13. Quality scoring (business-model aware)
    # -----------------------------------------------------------------------
    confidence = _compute_homepage_quality(
        primary_model=primary_model,
        hero=hero,
        sections=sections,
        ctas=ctas,
        products=all_products,
        categories=categories,
        title=title,
        meta_description=meta_description,
        contact_info=contact_info,
        trust_signals=trust_signals,
        services=offerings.get("services", []),
        value_props=offerings.get("valuePropositions", []),
        menu_items=menu_items,
        menu_categories=offerings.get("menuCategories", []),
        brand_extensions=offerings.get("brandExtensions", []),
        jina_mode=jina_mode,
    )

    # -----------------------------------------------------------------------
    # 14. Warnings
    # -----------------------------------------------------------------------
    warnings = []
    # Only warn about missing hero when ALL hero text fields are empty
    _hero_has_text = bool(
        hero.get("headline")
        or hero.get("campaignHero")
        or hero.get("supportingText")
        or hero.get("subheadline")
    )
    if not _hero_has_text:
        warnings.append("hero_text_not_detected")
    if not sections:
        warnings.append("no_sections_extracted")

    # Only warn about missing ecommerce content for actual ecommerce brands
    if _is_ecom_model and not _has_ecom_signals:
        warnings.append("no_ecommerce_content_on_homepage")

    # -----------------------------------------------------------------------
    # 15. Assemble result
    # -----------------------------------------------------------------------
    result["seo"] = {
        "title": title,
        "metaDescription": meta_description,
        "canonical": canonical,
        "h1": h1,
    }

    result["homepage"] = {
        "title": h1 or title,
        "businessModel": business_model,
        "hero": hero,
        "sections": sections,
        "ctas": ctas,
        "contact": contact_info,
        "trustSignals": trust_signals,
        "valuePropositions": offerings.get("valuePropositions", []),
        "services": offerings.get("services", []),
        "serviceArea": contact_info.get("serviceArea", []),
        "pricingPlans": offerings.get("pricingPlans", []),
        "menuItems": menu_items,
        "menuCategories": offerings.get("menuCategories", []),
        "brandExtensions": offerings.get("brandExtensions", []),
        "warnings": warnings,
        "extractionMethod": "jina" if jina_mode else "dom",
    }

    result["ecommerce"] = {
        "primaryModel": primary_model,
        "featuredProducts": all_products,
        "productTeasers": product_teasers,
        "featuredCollections": featured_collections,
        "featuredPrograms": featured_programs,
        "hasEcommerceSignals": _has_ecom_signals,
    }

    result["products"] = all_products

    result["analysisReady"] = {
        "extractionQuality": {
            "score": confidence,
            "warnings": warnings,
            "missingFields": [w for w in warnings if "missing" in w],
        },
        "schemaVersion": "unknown-homepage-v3",
    }

    # Final normalization: populate content/success/crawl from homepage
    result = finalize_homepage_result(result)

    return result
