# Shopify Homepage Extractor v2.0

import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qsl, urlencode, urlunparse

from extractors.dom_helpers import clean_text
from extractors.image_parser import normalize_image_url
from extractors.price_parser import parse_price, detect_currency

_SHOPIFY_API_HEADERS = {
    # Full browser UA — a bare "Mozilla/5.0" gets 403'd by many stores' bot
    # protection, dropping accurate products.json prices/availability.
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
}


NOISE_TEXTS = [
    "quickview", "quick view", "view cart", "continue shopping",
    "cart", "search", "open cart", "open search", "account",
    "skip carousel", "add to cart", "choose options", "previous", "next",
    "unmute video", "mute video", "play video", "navigate to next section"
]

FOOTER_HEADINGS = [
    "shop", "company", "information", "customer services", "customer service",
    "customer sevices", "catalog", "our newsletter", "join our mailing list",
    "support", "copyright", "about us", "contact us", "policies",
    "available on stores"
]

TRUST_KEYWORDS = [
    # Shipping / returns
    "free delivery", "free shipping", "free returns", "easy returns",
    "30 day return", "money back",
    # Security / authenticity
    "secure payment", "100% authentic", "genuine product",
    "certified", "verified",
    # Quality assurances
    "guarantee", "track your order", "cruelty-free",
    "dermatologist tested", "dermatologist approved",
    "hypoallergenic", "allergy tested",
    # Social proof badges (specific phrasing)
    "trusted by", "loved by", "5 star", "award winning",
]

# Brand story signals — these indicate an "About us / Our story" section, NOT a trust badge
_BRAND_STORY_SIGNALS = (
    "our story", "about us", "who we are", "our brand", "our mission",
    "our values", "our heritage", "our journey",
    "we are passionate", "passionate about", "we believe",
    "dedicated to", "we care", "our commitment",
    "family owned", "family-owned", "founded in", "since 19", "since 20",
    "best in", "we are proud", "proudly", "striving to",
)

PRODUCT_ACTION_WORDS = [
    "add to cart", "quick add", "quick shop", "choose options",
    "sale price", "regular price", "rs.", "pkr", "unit price"
]

# Primary CTA action keywords — short imperative phrases on homepage buttons.
# These are the only texts that qualify as primaryCtas.
_PRIMARY_CTA_KEYWORDS = {
    "shop now", "shop all", "shop collection", "shop the collection",
    "view all", "view collection", "view products", "view range",
    "explore", "explore collection", "explore products", "explore range",
    "buy now", "buy bundles", "buy",
    "discover", "discover more", "discover collection",
    "learn more", "see more", "see all",
    "get started", "order now",
}

_NAV_CONTAINER_CLASSES = (
    "header", "nav", "navigation", "menu", "navbar",
    "site-header", "top-bar", "topbar",
)


def is_noise_text(text):
    if not text:
        return True

    t = text.lower().strip()

    if t in NOISE_TEXTS:
        return True

    return any(x in t for x in [
        "cart error",
        "added to cart",
        "your cart is empty",
        "browser does not support the video"
    ])


def dedupe_items(items, key):
    seen = set()
    output = []

    for item in items:
        value = item.get(key)

        if not value:
            continue

        value_key = str(value).split("?variant=")[0].strip().lower()

        if value_key in seen:
            continue

        seen.add(value_key)
        output.append(item)

    return output


def canonical_shopify_image_url(url):
    if not url:
        return None

    url = str(url).strip()

    if url.startswith("//"):
        url = "https:" + url

    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query))

    keep = {}
    if "v" in query:
        keep["v"] = query["v"]

    return urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        "",
        urlencode(keep),
        ""
    ))


def strip_variant_url(url):
    if not url:
        return None

    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query))

    query.pop("variant", None)

    return urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        "",
        urlencode(query),
        ""
    ))


def dedupe_images(images):
    seen = set()
    output = []

    for img in images:
        url = img.get("url")

        if not url:
            continue

        canonical = canonical_shopify_image_url(url)

        if not canonical:
            continue

        if canonical.rstrip("/").endswith("/Liquid"):
            continue

        if canonical in seen:
            continue

        seen.add(canonical)

        output.append({
            **img,
            "url": canonical
        })

    return output


def get_best_src_from_srcset(srcset, base_url):
    if not srcset:
        return None

    candidates = []

    for part in srcset.split(","):
        part = part.strip()

        if not part:
            continue

        pieces = part.split()
        src = pieces[0]
        width = 0

        if len(pieces) > 1:
            match = re.search(r"(\d+)w", pieces[1])
            if match:
                width = int(match.group(1))

        candidates.append((width, src))

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0], reverse=True)
    return normalize_image_url(candidates[0][1], base_url)


def get_img_url(img, base_url):
    if not img:
        return None

    srcset = img.get("srcset") or img.get("data-srcset")

    if srcset:
        return get_best_src_from_srcset(srcset, base_url)

    src = (
        img.get("src")
        or img.get("data-src")
        or img.get("data-original")
        or img.get("data-lazy-src")
    )

    if not src:
        return None

    if "," in src and "w" in src:
        return get_best_src_from_srcset(src, base_url)

    return normalize_image_url(src.strip().split(" ")[0], base_url)


def _get_video_url(video_el):
    """Get the best video src from a <video> element or its <source> children."""
    for source in video_el.select("source"):
        src = source.get("src") or source.get("data-src")
        if src and src.strip():
            return src.strip()
    src = video_el.get("src") or video_el.get("data-src")
    return src.strip() if src else None


def _get_background_image(el, base_url):
    """Extract CSS background-image URL from an element's inline style."""
    style = el.get("style") or ""
    match = re.search(r"background(?:-image)?\s*:\s*url\(['\"]?([^'\")\s]+)['\"]?\)", style, re.I)
    if match:
        bg_url = match.group(1).strip()
        return normalize_image_url(bg_url, base_url)
    return None


def clean_link_url(href):
    if not href:
        return None

    href = href.replace("\\", "").strip()

    if href.startswith("javascript:") or href.startswith("#"):
        return None

    return href


def handle_to_title(handle):
    if not handle:
        return None

    return handle.replace("-", " ").replace("_", " ").title()


def get_handle_from_url(url):
    if not url:
        return None

    return url.rstrip("/").split("/")[-1].split("?")[0]


def clean_repeated_phrase(text, max_repeat=2):
    if not text:
        return None

    text = clean_text(text)
    chunks = re.split(r"\s{2,}|(?<=[.!?])\s+", text)

    unique = []
    counts = {}

    for chunk in chunks:
        chunk = clean_text(chunk)

        if not chunk:
            continue

        counts[chunk] = counts.get(chunk, 0) + 1

        if counts[chunk] <= max_repeat:
            unique.append(chunk)

    cleaned = " ".join(unique)

    words = cleaned.split()

    if len(words) > 8:
        half = len(words) // 2
        if words[:half] == words[half:]:
            cleaned = " ".join(words[:half])

    return clean_text(cleaned)


def clean_seo_alt_name(name, site_name=None):
    name = clean_text(name)

    if not name:
        return None

    remove_terms = [
        "pakistan",
        "online",
        "buy",
        "best",
        "original",
        "premium",
        "close-up",
        "close up",
        "wet food",
        "hair care products",
        "hair conditioner",
        "leave in conditioner",
        "makeup",
        "cosmetics"
    ]

    if site_name:
        site = clean_text(site_name)
        if site:
            site_words = re.split(r"\s+|-", site)
            for word in site_words:
                if len(word) > 2:
                    name = re.sub(rf"\b{re.escape(word)}\b", " ", name, flags=re.I)

    for term in remove_terms:
        name = re.sub(rf"\b{re.escape(term)}\b", " ", name, flags=re.I)

    name = re.sub(r"\s+", " ", name).strip(" -|")

    return clean_text(name)


def clean_product_name(name, site_name=None, handle=None):
    name = clean_text(name)

    if site_name and name:
        site = clean_text(site_name)
        if site:
            name = re.sub(re.escape(site), " ", name, flags=re.I)

    if name:
        patterns = [
            r"\bquick\s*add\b",
            r"\bquick\s*shop\b",
            r"\bquickview\b",
            r"\badd to cart\b",
            r"\bchoose options\b",
            r"\bsale price\b",
            r"\bregular price\b",
            r"\bout of stock\b",
            r"\bnew arrival\b",
            r"\bnew\b",
            r"\bno reviews\b",
            r"\d+\s*reviews?",
            r"-\s*\d+%",
            r"\d+%\s*off",
            r"\bget\s+at\s+checkout\b",
            r"Rs\.[\d,]+(?:\.\d+)?",
            r"PKR\s?[\d,]+(?:\.\d+)?"
        ]

        for pattern in patterns:
            name = re.sub(pattern, " ", name, flags=re.I)

        name = clean_seo_alt_name(name, site_name=site_name)
        name = clean_repeated_phrase(name)
        name = clean_text(name)

    if not name and handle:
        name = handle_to_title(handle)

    if name and len(name) <= 2 and handle:
        name = handle_to_title(handle)

    return name


def is_brand_only(text, site_name=None):
    text = clean_text(text)

    if not text:
        return True

    if site_name:
        site = clean_text(site_name)

        if site:
            site_l = site.lower()
            text_l = text.lower()

            if text_l in [site_l, f"{site_l} {site_l}"]:
                return True

    words = text.lower().split()

    if len(words) in [2, 4]:
        half = len(words) // 2
        if words[:half] == words[half:]:
            return True

    return False


def clean_cta_text(text, href=None, site_name=None):
    text = clean_text(text)

    if is_noise_text(text):
        return None

    if href and "/products/" in href:
        handle = get_handle_from_url(href)
        cleaned = clean_product_name(text, site_name=site_name, handle=handle)

        if not cleaned or is_brand_only(cleaned, site_name):
            return handle_to_title(handle)

        return cleaned

    if not text and href:
        if "/collections/" in href:
            return handle_to_title(get_handle_from_url(href))

        if "/products/" in href:
            return handle_to_title(get_handle_from_url(href))

    return text


def _in_nav_or_header(el):
    """Return True if el is nested inside a nav, header, footer, or nav-class container."""
    for parent in el.parents:
        tag = getattr(parent, "name", None)
        if tag in ("nav", "header", "footer"):
            return True
        classes = " ".join(parent.get("class", []) if parent else []).lower()
        pid = (parent.get("id") or "").lower() if parent else ""
        if any(k in classes or k in pid for k in _NAV_CONTAINER_CLASSES):
            return True
    return False


def extract_clean_navigation(soup, url):
    links = []

    for a in soup.select("header a, nav a"):
        text = clean_text(a.get_text(" ", strip=True))
        href = clean_link_url(a.get("href"))

        if not text or not href:
            continue

        if is_noise_text(text):
            continue

        if text.lower().startswith("cart "):
            continue

        if "customer_authentication" in href:
            continue

        full_url = strip_variant_url(urljoin(url, href))

        links.append({
            "text": text,
            "url": full_url
        })

    return dedupe_items(links, "url")


# Promotional phrases used to recognise a top-of-page announcement bar even when
# the theme doesn't use a conventional `.announcement` class (e.g. Sivanna's
# "Avail Free Delivery on Bank Deposit Payments"). Kept offer-specific (multi-word
# or unambiguous) so a bare nav item like "Sale" is not mistaken for a promo bar.
PROMO_BAR_KEYWORDS = (
    "free delivery", "free shipping", "free ship", "free returns",
    "cash on delivery", "bank deposit", "bank transfer", "easy paisa", "jazzcash",
    "% off", "percent off", "flat ", "off on", "delivery on",
    "use code", "promo code", "coupon", "discount code",
    "buy 1", "buy one", "bogo", "limited time", "clearance",
    "installment", "installments", "eid offer", "black friday",
)


# Offer categories → the phrases that identify them. Used to classify what KIND of
# promotion a store is running (shipping incentive vs price discount vs coupon), so
# the report can say "Sivanna competes on free delivery" rather than missing it.
_OFFER_PATTERNS = (
    ("free_shipping", ("free delivery", "free shipping", "free ship")),
    ("cash_on_delivery", ("cash on delivery",)),
    ("bank_deposit", ("bank deposit", "bank transfer")),
    ("local_wallet", ("easy paisa", "easypaisa", "jazzcash")),
    ("percent_off", ("% off", "percent off", "flat ", "off on")),
    ("coupon_code", ("use code", "promo code", "coupon", "discount code")),
    ("bundle", ("buy 1", "buy one", "bogo", "bundle")),
    ("seasonal", ("eid offer", "black friday", "clearance", "limited time")),
)


def _extract_promo_offers(ann_text: str, page_blob: str):
    """Classify promotional offers found in the announcement bar / page text.
    Returns a small list like [{"type": "free_shipping", "source": "announcement"}]."""
    offers = []
    blob = f"{ann_text} {page_blob}"
    for kind, keys in _OFFER_PATTERNS:
        if any(k in blob for k in keys):
            offers.append({
                "type": kind,
                "source": "announcement" if any(k in ann_text for k in keys) else "page",
            })
    return offers


def extract_announcement_bar(soup):
    selectors = [
        ".announcement-bar",
        ".announcement-bar__message",
        ".announcement",
        "[class*='announcement']",
        "[id*='announcement']",
        ".top-bar",
        "[class*='top-bar']",
        "[class*='topbar']",
        ".header-top",
        ".header__announcement",
        "[class*='promo-bar']",
        "[class*='promobar']",
        "[class*='marquee']",
        "[class*='ticker']",
        "[data-section-type*='announcement']",
    ]

    def _has_promo(t):
        low = (t or "").lower()
        return any(k in low for k in PROMO_BAR_KEYWORDS)

    # Gather ALL bar candidates from the conventional selectors — don't return on the
    # first match, because a theme can have BOTH a utility strip ("Find Store · email")
    # and a promo bar ("Free Delivery on Bank Deposit"), and the utility one often
    # matches an earlier selector. We pick promo-aware below.
    selector_candidates = []  # (text, selector)
    for selector in selectors:
        try:
            els = soup.select(selector)[:3]
        except Exception:
            els = []
        for el in els:
            text = clean_repeated_phrase(el.get_text(" ", strip=True), max_repeat=1)
            if text and 3 < len(text) <= 220:
                selector_candidates.append((text, selector))

    # Top-of-body scan for a short PROMO line, skipping menu/cart/footer noise.
    scan_candidates = []
    try:
        body = soup.body or soup
        for el in body.find_all(True, recursive=True, limit=50):
            if el.name in ("script", "style", "nav", "svg", "img", "video", "source", "picture"):
                continue
            text = clean_repeated_phrase(el.get_text(" ", strip=True), max_repeat=1)
            if not text or len(text) < 5 or len(text) > 160:
                continue
            low = text.lower()
            if any(n in low for n in ("cart", "search", "account", "menu", "copyright", "sign in", "log in")):
                continue
            if _has_promo(text):
                scan_candidates.append(text)
    except Exception:
        pass

    # 1) Prefer a candidate that actually carries a PROMO (from selectors OR the scan),
    #    shortest first — so "Free Delivery on Bank Deposit" wins over a utility strip.
    promo_texts = [t for (t, _s) in selector_candidates if _has_promo(t)] + scan_candidates
    if promo_texts:
        best = min(promo_texts, key=len)
        from_selector = any(best == t for (t, _s) in selector_candidates)
        return {
            "text": best[:350],
            "detected": True,
            "selector": next((s for (t, s) in selector_candidates if t == best), None),
            "source": "selector_promo" if from_selector else "top_scan_promo",
        }

    # 2) No promotional bar — but a bar element still exists (e.g. "Welcome to our
    #    store"). Report the first selector match so hasAnnouncementBar is accurate.
    if selector_candidates:
        text, selector = selector_candidates[0]
        return {"text": text[:350], "detected": True, "selector": selector, "source": "selector"}

    return {"text": None, "detected": False, "selector": None, "source": None}


def section_is_footer(section, heading=None):
    heading_l = (heading or "").lower().strip()

    if heading_l in FOOTER_HEADINGS:
        return True

    classes = " ".join(section.get("class", [])).lower()
    section_id = (section.get("id") or "").lower()

    return "footer" in classes or "footer" in section_id


def section_is_header(section):
    classes = " ".join(section.get("class", [])).lower()
    section_id = (section.get("id") or "").lower()

    return "header" in classes or "header" in section_id


def looks_like_menu_noise(section, text):
    lower = (text or "").lower()

    collection_links = len(section.select('a[href*="/collections/"]'))
    product_links = len(section.select('a[href*="/products/"]'))
    image_count = len(section.select("img"))
    price_count = count_prices(text)

    menu_terms = ["cart", "search", "account"]

    if any(term in lower for term in menu_terms) and collection_links >= 8 and image_count == 0:
        return True

    if collection_links >= 12 and product_links <= 2 and image_count == 0 and price_count == 0:
        return True

    if collection_links >= 20 and image_count <= 1:
        return True

    return False


def should_skip_section(section, text, heading=None):
    combined = clean_text(f"{heading or ''} {text or ''}") or ""
    lower = combined.lower()

    if len(lower) < 5:
        return True

    if section_is_header(section):
        return True

    if section_is_footer(section, heading):
        return True

    if looks_like_menu_noise(section, combined):
        return True

    noise_patterns = [
        "cart your cart is empty",
        "your browser does not support the video tag",
        "open navigation menu",
        "cart 0 item",
        "added to cart",
        "cart error",
        "copyright ©",
        "© copyright"
    ]

    return any(p in lower for p in noise_patterns)


def is_trust_badge_block(el):
    text = clean_text(el.get_text(" ", strip=True)) or ""
    lower = text.lower()

    if any(k in lower for k in TRUST_KEYWORDS):
        img_count = len(el.select("img"))
        link_count = len(el.select("a[href]"))

        if img_count <= 5 and link_count <= 2:
            return True

    return False


def count_prices(text):
    if not text:
        return 0

    return len(re.findall(r"(?:Rs\.?|PKR|\$|£|€)\s?[\d,]+(?:\.\d+)?", text, re.I))


def _infer_product_intent(heading_l, text_l=""):
    """Map a section heading to a normalised product intent string.

    Intent is derived from the HEADING only — discount prices or sale text
    in the product grid body must NOT change a Trending / Best Sellers section
    to intent="sale".  text_l is ignored for intent classification.
    """
    h = heading_l.strip()
    if any(k in h for k in ("trending", "trend")):
        return "trending"
    if any(k in h for k in ("top seller", "top sellers", "best seller", "best sellers",
                              "bestseller", "bestsellers", "best-seller",
                              "popular", "most popular")):
        return "bestsellers"
    if any(k in h for k in ("new arrival", "new arrivals", "new in", "latest")):
        return "new_arrivals"
    if any(k in h for k in ("bundle", "bundles", "kit")):
        return "bundles"
    if "shop the look" in h:
        return "shop_the_look"
    if any(k in h for k in ("featured", "recommended", "top picks",
                              "editor's pick", "editors pick")):
        return "featured"
    if any(k in h for k in ("sale", "clearance", "flash sale")):
        return "sale"
    if "range" in h:
        return "product_range"
    if any(k in h for k in ("pack", "packs", "treat", "treats",
                              "shop", "collection", "products", "picks")):
        return "category_showcase"
    return "general_product_grid"


# Product-implying heading keywords — a heading matching any of these signals
# a product section even when product links or prices are absent from the HTML
# (e.g. JS-rendered product grids whose heading/CTA block is a separate section).
_PRODUCT_HEADING_SIGNALS = (
    "best seller", "bestseller", "top seller", "popular", "trending", "trend",
    "new arrival", "new arrivals", "new in", "latest",
    "sale", "clearance", "flash sale", "% off",
    "bundle", "bundles", "kit",
    "shop the look", "shop the range", "shop our",
    "featured", "recommended", "top picks",
    "range", "products", "picks",
    "pack", "packs", "treat", "treats",
)


def classify_section(heading, text, product_count, collection_count, price_count):
    """
    Return {type, intent, label} for a homepage section.

    type values: product_section | collections | testimonials | blog_preview |
                 newsletter | trust_signal | promo | content_section
    intent: only set when type == product_section (trending, bestsellers, etc.)
    label: original heading text (preserved verbatim)
    """
    text_l = (text or "").lower()
    heading_l = (heading or "").lower().strip()

    # ── Social gallery — checked FIRST ───────────────────────────────────
    # Instagram/UGC feeds often contain tagged product links; if we let product_section
    # run first those sections get misclassified.  Anchor phrases are unambiguous enough
    # to take priority over product signals.
    if "instagram" in heading_l or any(k in text_l for k in (
        "instagram", "as seen on", "follow us on", "our community", "#shop", "ugc",
    )):
        return {"type": "social_gallery", "intent": None, "label": heading}

    # ── Product section detection ────────────────────────────────────────
    has_product_links = product_count > 0
    has_prices = price_count > 0
    has_cart_text = any(k in text_l for k in (
        "add to cart", "quick add", "quickadd", "choose options",
        "add to bag", "quick view", "quickview",
    ))
    # Heading alone implies products (for sections that are just heading+CTA)
    heading_implies_products = any(k in heading_l for k in _PRODUCT_HEADING_SIGNALS)

    is_product_section = has_product_links or has_prices or has_cart_text
    intent = _infer_product_intent(heading_l, text_l)

    if is_product_section or (heading_implies_products and intent != "general_product_grid"):
        # Override category_showcase when section has actual product cards (not just collection links).
        # Headings like "Single Packs" / "Cat Treats" trigger category_showcase in _infer_product_intent,
        # but if ≥3 product links are present they are real product grids, not category browsers.
        if intent == "category_showcase" and product_count >= 3:
            intent = "featured_products"
        return {"type": "product_section", "intent": intent, "label": heading}

    # ── Other section types (checked in priority order) ──────────────────

    # Countdown / flash-sale timer
    if any(k in text_l for k in ("ends in", "hurry", "hours left", "countdown",
                                   "limited time only", "sale ends")):
        return {"type": "countdown_sale", "intent": None, "label": heading}

    # Testimonials / reviews
    if any(k in text_l for k in ("review", "testimonial", "let customers speak",
                                   "what our customers", "customers say",
                                   "verified buyer", "customer reviews")):
        return {"type": "testimonial_section", "intent": None, "label": heading}

    # Brand story — checked BEFORE trust_signal to prevent misclassification
    if any(k in heading_l for k in _BRAND_STORY_SIGNALS):
        return {"type": "brand_story", "intent": None, "label": heading}
    if any(k in text_l for k in _BRAND_STORY_SIGNALS):
        return {"type": "brand_story", "intent": None, "label": heading}

    # Social / Instagram gallery
    if any(k in text_l for k in ("instagram", "as seen on", "follow us on",
                                   "our community", "#shop", "ugc")):
        return {"type": "social_gallery", "intent": None, "label": heading}
    if "instagram" in heading_l:
        return {"type": "social_gallery", "intent": None, "label": heading}

    # Newsletter — checked BEFORE blog_preview to avoid misclassifying signup sections
    if any(k in text_l for k in ("newsletter", "subscribe", "email address",
                                   "mailing list", "sign up", "join us")):
        return {"type": "newsletter", "intent": None, "label": heading}

    # Blog preview
    if any(k in text_l for k in ("blog", "article", "guide", "tips", "read more")):
        return {"type": "blog_preview", "intent": None, "label": heading}

    # Trust signals (specific phrases only — see TRUST_KEYWORDS)
    if any(k in text_l for k in TRUST_KEYWORDS):
        return {"type": "trust_signal", "intent": None, "label": heading}

    # Promotional banner (% off, sale, etc.)
    if any(k in text_l for k in ("% off", "save ", "special offer", "exclusive offer",
                                   "flash sale", "clearance", "discount")):
        return {"type": "promotion", "intent": None, "label": heading}
    if any(k in text_l for k in ("sale", "limited stock")):
        return {"type": "promotion", "intent": None, "label": heading}

    # Category showcase — "Shop By Category", "Browse By Category", etc.
    # More specific than generic "collections", so checked first
    if any(k in heading_l for k in ("shop by", "browse by", "shop by category",
                                      "browse category", "categories")):
        return {"type": "category_showcase", "intent": "category_showcase", "label": heading}
    if any(k in text_l for k in ("shop by category", "browse by category")):
        return {"type": "category_showcase", "intent": "category_showcase", "label": heading}

    # Sections with multiple collection links → category_showcase.
    # ≥ 3 collections: clearly a category browser even without a named heading.
    # ≥ 2 collections with a heading: named category grid (e.g. "Face Makeup", "Collections").
    if collection_count >= 2 and product_count == 0:
        if collection_count >= 3 or heading_l:
            return {"type": "category_showcase", "intent": "category_showcase", "label": heading}
        return {"type": "collections", "intent": None, "label": heading}

    # Generic collections grid (no heading, or collection text in body)
    if any(k in text_l for k in ("collection", "shop our collection")):
        return {"type": "collections", "intent": None, "label": heading}

    return {"type": "content_section", "intent": None, "label": heading}


def is_real_product_card(card):
    text = (clean_text(card.get_text(" ", strip=True)) or "").lower()

    has_price = bool(re.search(r"(rs\.?|pkr|\$|£|€)\s?[\d,]+", text, re.I))
    has_action = any(x in text for x in PRODUCT_ACTION_WORDS)
    has_image = bool(card.select_one("img"))
    has_product_link = bool(card.select_one('a[href*="/products/"]'))

    return has_product_link and has_image and (has_price or has_action)


def find_product_card(link):
    parent = link
    best = None

    for _ in range(9):
        if not parent:
            break

        classes = " ".join(parent.get("class", [])).lower()

        if any(k in classes for k in [
            "product-card", "product-item", "card-wrapper", "grid-product",
            "product-block", "product", "card", "grid__item", "productgrid"
        ]):
            best = parent

            if is_real_product_card(parent):
                return parent

        parent = parent.parent

    # If best was found but doesn't pass is_real_product_card (e.g. Shopify quickview
    # themes where the price lives in a sibling overlay outside the inner card element),
    # walk up a few more levels to find a wider wrapper that includes the price.
    if best is not None and not is_real_product_card(best):
        wider = best.parent
        for _ in range(3):
            if wider is None:
                break
            if is_real_product_card(wider):
                return wider
            wider = wider.parent

    return best or link.parent or link


def get_price_from_card(card):
    # 1. Try data-price attribute (Shopify often stores machine-readable price here)
    # Validate value >= 100 to avoid discount-percentage badges (e.g. data-price="26" → 26% off)
    for el in card.select("[data-price]"):
        raw = el.get("data-price", "").strip()
        if not raw:
            continue
        # If it contains a currency symbol, accept directly
        if re.search(r"(?:Rs\.?|PKR|\$|£|€)", raw, re.I):
            return raw
        # Otherwise validate it's a numeric price >= 100
        try:
            if float(raw.replace(",", "")) >= 100:
                return raw
        except ValueError:
            pass

    # 2. CSS class selectors for price elements
    selectors = [
        ".price__current",
        ".price-item--sale",
        ".price-item--regular",
        ".price",
        ".money",
        ".price-item",
        ".product-price",
        "[class*='price']"
    ]

    for selector in selectors:
        el = card.select_one(selector)

        if not el:
            continue

        # Skip visually-hidden labels (e.g. "Sale price", "Regular price")
        for hidden in el.select(".visually-hidden, .sr-only, [aria-hidden='true']"):
            hidden.decompose()

        text = clean_text(el.get_text(" ", strip=True))

        if text and re.search(r"\d", text):
            # If text contains a percentage (e.g. "Rs.550.00 -11%"), strip the % token
            # and return the remaining price rather than skipping the whole element.
            if re.search(r'\d+\s*%', text):
                text_stripped = re.sub(r'-?\s*\d+\s*%\s*(?:off)?', '', text, flags=re.I).strip()
                if text_stripped and re.search(r"(?:Rs\.?|PKR|\$|£|€)", text_stripped, re.I):
                    return text_stripped
                # No currency symbol left — skip this element
                continue
            return text

    # 3. Regex fallback on full card text (with currency symbol)
    text = clean_text(card.get_text(" ", strip=True)) or ""
    matches = re.findall(r"(?:Rs\.?\s?|PKR\s?|\$|£|€)\s?[\d,]+(?:\.\d+)?", text, re.I)

    if matches:
        return " ".join(matches[:2])

    # 4. Last resort: any number that looks like a price (e.g. "12.99" or "1,695")
    # Only use when card has a product link (confirming it's a product card).
    # Strip discount-percentage tokens (e.g. "-15%", "20% Off") first so we don't
    # accidentally pick up a percentage as a price.
    if card.select_one('a[href*="/products/"]'):
        text_stripped = re.sub(r'-?\s*\d+\s*%(?:\s*off)?', '', text, flags=re.I)
        price_matches = re.findall(r"\b\d{1,6}(?:,\d{3})*(?:\.\d{1,2})?\b", text_stripped)
        # Require > 50 to exclude small badge numbers and single-digit artefacts
        price_matches = [p for p in price_matches if float(p.replace(",", "")) > 50]
        if price_matches:
            return price_matches[0]

    return None


def get_compare_price_from_card(card):
    """Extract compare-at (was) price from a product card."""
    selectors = [
        ".price__compare",
        ".compare-at-price",
        ".was-price",
        "[class*='compare']",
        "del",
        "s",
    ]
    for selector in selectors:
        el = card.select_one(selector)
        if not el:
            continue
        for hidden in el.select(".visually-hidden, .sr-only, [aria-hidden='true']"):
            hidden.decompose()
        text = clean_text(el.get_text(" ", strip=True))
        if text and re.search(r"\d", text):
            return text
    return None


def get_name_from_card(card, link, handle, site_name=None):
    selectors = [
        ".card__heading",
        ".product-card__title",
        ".product-title",
        ".product-item__title",
        ".grid-product__title",
        ".product-block__title",
        "[class*='title']",
        "h3",
        "h2"
    ]

    for selector in selectors:
        el = card.select_one(selector)

        if not el:
            continue

        text = clean_product_name(el.get_text(" ", strip=True), site_name=site_name, handle=handle)

        if text and not is_brand_only(text, site_name):
            return text

    raw_link_text = clean_text(link.get_text(" ", strip=True))
    text = clean_product_name(raw_link_text, site_name=site_name, handle=handle)

    if text and not is_brand_only(text, site_name):
        return text

    img = card.select_one("img")
    alt = clean_text(img.get("alt")) if img else None

    if alt:
        text = clean_product_name(alt, site_name=site_name, handle=handle)
        if text and not is_brand_only(text, site_name):
            return text

    return handle_to_title(handle)


def extract_product_from_link(a, url, site_name=None):
    href = clean_link_url(a.get("href"))

    if not href or "/products/" not in href:
        return None

    product_url = strip_variant_url(urljoin(url, href).split("?")[0])
    # Normalize /collections/X/products/handle → /products/handle so that
    # the same product linked from different collection contexts deduplicates
    # correctly (Shopify serves both URL forms for the same product).
    _col_match = re.search(r'/products/([^/?#]+)', product_url)
    if _col_match and '/collections/' in product_url:
        _parsed_base = urlparse(product_url)
        product_url = f"{_parsed_base.scheme}://{_parsed_base.netloc}/products/{_col_match.group(1)}"
    handle = get_handle_from_url(product_url)

    card = find_product_card(a)

    img = card.select_one("img")
    image_url = canonical_shopify_image_url(get_img_url(img, url)) if img else None

    name = get_name_from_card(card, a, handle, site_name=site_name)
    price_raw = get_price_from_card(card)
    compare_raw = get_compare_price_from_card(card)
    currency = detect_currency(price_raw) or detect_currency(compare_raw)

    # Sale vs. compare price: CSS selectors use select_one and return only the FIRST
    # price element found.  Bundle cards (e.g. "Rs.1,920.00 Rs.1,700.00") often have
    # two sibling .price/.money elements with no explicit sale/compare markup.
    # Strategy: scan the FULL card text for ALL currency-annotated values, deduplicate,
    # and assign min→currentPrice (sale) and max→comparePrice (original).
    # Strip percentage tokens first so "20% off" never becomes a price candidate.
    _card_text_raw = clean_text(card.get_text(" ", strip=True)) or ""
    _card_no_pct = re.sub(r'-?\s*\d+\s*%(?:\s*off)?', '', _card_text_raw, flags=re.I)
    _all_vals = sorted({
        v for v in (
            parse_price(m.group(0))
            for m in re.finditer(r"(?:Rs\.?\s?|PKR\s?|\$|£|€)\s?[\d,]+(?:\.\d+)?", _card_no_pct, re.I)
        )
        if v is not None and v > 50
    })
    if len(_all_vals) >= 2:
        # Multiple prices in card: lowest = sale/current, highest = original/compare
        current_price = _all_vals[0]
        compare_price = _all_vals[-1]
    else:
        # Single price or no currency symbol found in card — use structured extractors
        _combined_raw = (price_raw or "") + " " + (compare_raw or "")
        _sp = [
            parse_price(m.group(0))
            for m in re.finditer(r"(?:Rs\.?\s?|PKR\s?|\$|£|€)\s?[\d,]+(?:\.\d+)?", _combined_raw, re.I)
        ]
        _sp = [v for v in _sp if v is not None]
        if len(_sp) >= 2:
            current_price = min(_sp)
            compare_price = max(_sp)
        else:
            current_price = parse_price(price_raw)
            compare_price = parse_price(compare_raw)

    return {
        "title": name,
        "url": product_url,
        "image": image_url,
        "currentPrice": current_price,
        "comparePrice": compare_price,
        "currency": currency,
        "handle": handle,
        "source": {
            "selector": "homepage_product_card_v2",
            "confidence": 0.88 if price_raw else 0.76
        }
    }


def extract_product_links(soup, url, site_name=None):
    products = []

    for a in soup.select('main a[href*="/products/"], .shopify-section a[href*="/products/"]'):
        card = find_product_card(a)

        if not is_real_product_card(card):
            continue

        product = extract_product_from_link(a, url, site_name=site_name)

        if product:
            products.append(product)

    return dedupe_items(products, "url")[:100]


def extract_section_links(section, url, site_name=None):
    links = []

    for a in section.select("a[href]"):
        href = clean_link_url(a.get("href"))

        if not href:
            continue

        full_url = strip_variant_url(urljoin(url, href))

        text = clean_cta_text(a.get_text(" ", strip=True), href, site_name=site_name)

        if "/products/" in href:
            product = extract_product_from_link(a, url, site_name=site_name)

            if product:
                text = product.get("name")

        if not text:
            continue

        if text.lower().startswith("cart "):
            continue

        links.append({
            "text": text,
            "url": full_url
        })

    return dedupe_items(links, "url")[:12]


def extract_section_images(section, url):
    images = []

    for img in section.select("img"):
        image_url = get_img_url(img, url)

        if image_url:
            images.append({
                "url": image_url,
                "alt": clean_text(img.get("alt"))
            })

    return dedupe_images(images)[:12]


def _merge_heading_sections(sections):
    """Merge a heading-only section with the immediately following product section.

    Shopify liquid often outputs a heading block as its own .shopify-section
    (containing only the title, e.g. "Single Packs") followed by a separate
    product-grid section.  Without merging, the heading becomes a dead
    content_section and the grid loses its label.

    Merge when ALL of:
      • current section has a heading
      • current section has no product/collection links and ≤1 image
      • current section text is short (≤15 words — essentially just the heading)
      • current section is NOT already a product_section
      • next section IS a product_section
      • next section has no heading of its own
    """
    if len(sections) < 2:
        return sections

    result = []
    skip_next = False

    for i, sec in enumerate(sections):
        if skip_next:
            skip_next = False
            continue

        if i + 1 < len(sections):
            nxt = sections[i + 1]
            heading = sec.get("heading")
            text_words = len((sec.get("textPreview") or "").split())
            no_links = not sec.get("links")
            few_images = len(sec.get("images") or []) <= 1
            # A heading stub has a heading but NO actual product links
            # (even if classify_section typed it as product_section from heading signals)
            has_actual_products = any(
                "/products/" in (l.get("url") or "")
                for l in (sec.get("links") or [])
            )
            is_heading_stub = (
                heading
                and not has_actual_products
                and few_images
                and text_words <= 15
            )
            nxt_is_product = nxt.get("type") == "product_section"
            nxt_no_heading = not nxt.get("heading")

            if is_heading_stub and nxt_is_product and nxt_no_heading:
                # Recompute classification using the stub heading + grid content
                nxt_text = nxt.get("textPreview", "")
                # Count product links from the links list; also fall back to the
                # products[] array (populated by section-level extraction) so that
                # quickview-theme sections — where product URLs don't appear in links[]
                # because the link text is empty — still get the correct product count.
                prod_count = max(
                    len([l for l in (nxt.get("links") or []) if "/products/" in (l.get("url") or "")]),
                    len(nxt.get("products") or [])
                )
                coll_count = len([
                    l for l in (nxt.get("links") or [])
                    if "/collections/" in (l.get("url") or "")
                ])
                price_count = nxt.get("source", {}).get("priceCount", 0)

                classification = classify_section(
                    heading, nxt_text,
                    product_count=prod_count,
                    collection_count=coll_count,
                    price_count=price_count
                )

                merged = {
                    "rank": sec["rank"],
                    "type": classification["type"],
                    "intent": classification.get("intent"),
                    "label": classification.get("label"),
                    "heading": heading,
                    "textPreview": nxt_text,
                    "links": nxt.get("links", []),
                    "images": nxt.get("images", []),
                    "source": {
                        "selector": "merged_heading_section",
                        "confidence": 0.85,
                        "priceCount": price_count,
                    },
                }
                # Carry over products[] from the grid section
                if nxt.get("products") is not None:
                    merged["products"] = nxt["products"]
                result.append(merged)
                skip_next = True
                continue

        result.append(sec)

    return result


def _dedupe_product_sections(sections):
    """Remove product sections whose product URLs are already covered (≥70% overlap)
    by an earlier section.

    Root cause: soup.select("main section, .shopify-section, section") can match the
    same DOM element multiple times.  After _merge_heading_sections the merged record
    carries the grid's products, but the original grid section may still be present
    in the list because skip_next only fires when i+1 is the target.  This pass
    removes such ghosts by comparing product-URL sets.
    """
    if len(sections) < 2:
        return sections

    def _prod_urls(sec):
        # Check products[] (rich objects from extract_product_from_link)
        from_products = frozenset(
            p.get("url", "") for p in (sec.get("products") or [])
            if p.get("url")
        )
        # Also check links[] for any product URLs
        from_links = frozenset(
            l.get("url", "") for l in (sec.get("links") or [])
            if "/products/" in (l.get("url") or "")
        )
        return from_products | from_links

    # Pre-scan: find headings that have a matching section WITH products.
    # A heading-stub (prods=0) that pairs with a later same-heading section (prods>0)
    # is a DOM artifact (separate liquid template block) — drop the stub.
    headings_with_products: set = set()
    for sec in sections:
        if sec.get("type") == "product_section" and (sec.get("products") or []):
            h = (sec.get("heading") or "").strip().lower()
            if h:
                headings_with_products.add(h)

    seen_url_sets: list = []
    result = []

    for sec in sections:
        if sec.get("type") != "product_section":
            result.append(sec)
            continue

        urls = _prod_urls(sec)

        if not urls:
            # Heading stub (no products, no links).
            # Drop it if a same-heading section with products appears elsewhere in the list.
            h = (sec.get("heading") or "").strip().lower()
            if h and h in headings_with_products:
                continue  # drop the empty stub — the real section follows
            result.append(sec)
            seen_url_sets.append(urls)
            continue

        # Duplicate if ≥70 % of this section's product URLs appeared earlier
        duplicate = any(
            prev and len(urls & prev) >= max(1, len(urls) * 0.7)
            for prev in seen_url_sets
        )

        if not duplicate:
            result.append(sec)
            seen_url_sets.append(urls)
        # else: drop the duplicate ghost

    return result


def dedupe_sections(sections):
    seen = set()
    output = []

    for section in sections:
        text_sig = clean_text(section.get("textPreview")) or ""
        link_sig = "|".join([link.get("url", "") for link in section.get("links", [])[:6]])

        # Social gallery sections may appear twice with different headings
        # (e.g. heading=None and heading="Instagram") for the same DOM element.
        # Dedupe by text only so both copies collapse to one.
        if section.get("type") == "social_gallery":
            signature = ("social_gallery", text_sig[:160].lower().strip())
        else:
            signature = (
                (section.get("heading") or "").lower().strip(),
                text_sig[:160].lower().strip(),
                link_sig.lower().strip()
            )

        if signature in seen:
            continue

        seen.add(signature)
        output.append(section)

    for index, section in enumerate(output, start=1):
        section["rank"] = index

    return output


def extract_homepage_sections(soup, url, site_name=None):
    sections = []

    for index, section in enumerate(soup.select("main section, .shopify-section, section"), start=1):
        text = clean_text(section.get_text(" ", strip=True))

        if not text:
            continue

        heading_el = section.select_one("h1, h2, h3")
        heading = clean_text(heading_el.get_text(" ", strip=True)) if heading_el else None

        if should_skip_section(section, text, heading):
            continue

        product_count = len(section.select('a[href*="/products/"]'))
        collection_count = len(section.select('a[href*="/collections/"]'))
        price_count = count_prices(text)

        links = extract_section_links(section, url, site_name=site_name)
        images = extract_section_images(section, url)

        classification = classify_section(
            heading, text,
            product_count=product_count,
            collection_count=collection_count,
            price_count=price_count
        )

        sec_dict = {
            "rank": index,
            "type": classification["type"],
            "intent": classification.get("intent"),
            "label": classification.get("label"),
            "heading": heading,
            "textPreview": text[:350],
            "links": links,
            "images": images,
            "source": {
                "selector": "section_or_shopify_section",
                "confidence": 0.8,
                "priceCount": price_count,
            }
        }

        # For product sections, extract rich product objects directly
        if classification["type"] == "product_section":
            section_products = []
            seen_product_urls = set()
            for a in section.select('a[href*="/products/"]'):
                product = extract_product_from_link(a, url, site_name=site_name)
                if product:
                    p_url = product.get("url") or product.get("handle") or ""
                    if p_url not in seen_product_urls:
                        seen_product_urls.add(p_url)
                        section_products.append(product)
            section_products = section_products[:12]

            # Section-level price fallback: if any products still have null prices,
            # extract all prices from the raw section text and assign by position order.
            null_price_products = [p for p in section_products if p.get("currentPrice") is None]
            if null_price_products:
                section_text_raw = section.get_text(" ", strip=True)
                # Extract prices in document order (currency symbol + digits)
                fallback_prices = re.findall(
                    r"(?:Rs\.?|PKR|₹|\$|£|€)\s?[\d,]+(?:\.\d+)?",
                    section_text_raw,
                    re.I,
                )
                # Dedupe while preserving order
                seen_fp = set()
                fallback_prices_deduped = []
                for fp in fallback_prices:
                    key = fp.strip().lower()
                    if key not in seen_fp:
                        seen_fp.add(key)
                        fallback_prices_deduped.append(fp.strip())
                for i, prod in enumerate(null_price_products):
                    if i < len(fallback_prices_deduped):
                        prod["currentPrice"] = parse_price(fallback_prices_deduped[i])
                        if prod["currentPrice"] is not None:
                            prod["source"]["confidence"] = 0.72
                            prod["currency"] = prod["currency"] or detect_currency(fallback_prices_deduped[i])

            sec_dict["products"] = section_products

        sections.append(sec_dict)

    sections = _merge_heading_sections(sections)
    sections = _dedupe_product_sections(sections)
    return dedupe_sections(sections)[:45]


def extract_section_headings(soup):
    headings = []

    for el in soup.select(
        "main h1, main h2, main h3, section h1, section h2, section h3, "
        ".shopify-section h1, .shopify-section h2, .shopify-section h3"
    ):
        text = clean_text(el.get_text(" ", strip=True))

        if not text or is_noise_text(text):
            continue

        if text.lower().strip() in FOOTER_HEADINGS:
            continue

        headings.append({
            "text": text,
            "tag": el.name
        })

    return dedupe_items(headings, "text")[:70]


def looks_like_collection_banner(el):
    images = el.select("img")
    links = el.select("a[href]")
    text = clean_text(el.get_text(" ", strip=True)) or ""

    has_collection_link = any("/collections/" in (a.get("href") or "") for a in links)
    has_product_link = any("/products/" in (a.get("href") or "") for a in links)

    if has_product_link:
        return False

    if len(images) >= 1 and has_collection_link:
        return True

    if len(images) >= 1 and any(k in text.lower() for k in ["shop collection", "view all", "discover", "shop now"]):
        return True

    return False


def _find_hero_container(soup):
    """
    Find the FIRST hero/slideshow container on the page.

    Priority order:
      1. Shopify section-type data attributes (slideshow / video / image-banner)
      2. Explicit class names (.slideshow, .hero)
      3. First .shopify-section or <section> containing a <video>
      4. First .shopify-section with an image and no product links

    Returns the container element or None.
    """
    def _is_valid(el):
        if not el:
            return False
        if _in_nav_or_header(el):
            return False
        if section_is_footer(el) or section_is_header(el):
            return False
        return True

    def _to_section_root(el):
        """Walk up to the nearest .shopify-section ancestor."""
        cur = el
        for _ in range(5):
            p = getattr(cur, "parent", None)
            if not p or not hasattr(p, "name"):
                break
            classes = " ".join(p.get("class", [])).lower()
            if "shopify-section" in classes:
                return p
            cur = p
        return el

    # 1. data-section-type attributes (Shopify liquid sections)
    for attr_val in ("slideshow", "video", "image-banner", "hero", "hero-banner"):
        el = soup.select_one(f'[data-section-type="{attr_val}"]')
        if _is_valid(el):
            return el

    # 2. Explicit class names — most specific first
    explicit_selectors = [
        ".slideshow",
        "[class*='slideshow']",
        "[class*='hero-banner']",
        "[class*='hero__']",
        ".hero",
    ]
    for sel in explicit_selectors:
        for el in soup.select(sel):
            if not _is_valid(el):
                continue
            # Accept: has video/img, OR has CSS background-image
            has_bg = bool(re.search(r"background(?:-image)?\s*:", el.get("style", ""), re.I))
            if el.select_one("video, img") or has_bg:
                return _to_section_root(el)

    # 3. First .shopify-section / <section> containing a <video>
    for section in soup.select(".shopify-section, main > section, main > div[class]"):
        if not _is_valid(section):
            continue
        if section.select_one("video"):
            return section

    # 4. First .shopify-section with image but no product links (above the fold)
    for section in soup.select(".shopify-section, main > section"):
        if not _is_valid(section):
            continue
        if section.select_one("img") and not section.select('a[href*="/products/"]'):
            return section

    return None


def _find_slides_in(container):
    """
    Find individual slide elements within a hero container.
    Tries named slide selectors first, then inner track/wrapper children,
    then direct children that contain media.
    Returns a list of elements (may be empty).
    """
    # Named slide selectors — ordered most-specific first
    slide_selectors = [
        # Shopify built-in / Dawn / Debut / Motion / Broadcast
        "[class*='slideshow__slide']",
        "[class*='slideshow-block']",
        # Swiper.js (very common in custom Shopify themes)
        "[class*='swiper-slide']",
        # Slick carousel
        "[class*='slick-slide']",
        # Splide.js
        "[class*='splide__slide']",
        # Generic BEM __slide pattern (hero__slide, banner__slide, slider__slide, etc.)
        "[class*='__slide']",
        # Flickity
        ".carousel-cell",
        # Glide.js
        "[class*='glide__slide']",
        # Data-attribute based (Symmetry theme, others)
        "[data-slide]",
        "[data-index]",
        # Simple .slide class (some themes)
        ".slide",
    ]
    for sel in slide_selectors:
        candidates = container.select(sel)
        if candidates:
            # Guard: make sure these aren't themselves containers
            # (e.g. [data-index] might match a 1-element wrapper)
            if len(candidates) > 1 or (len(candidates) == 1 and candidates[0] is not container):
                return candidates

    # Inner track/wrapper — get children that contain media
    track_selectors = [
        ".swiper-wrapper",
        "[class*='__slides']",
        "[class*='__track']",
        "[class*='__wrapper']",
        "[class*='slideshow__list']",
    ]
    for sel in track_selectors:
        wrapper = container.select_one(sel)
        if wrapper:
            children = [
                c for c in wrapper.children
                if hasattr(c, "name") and c.name
                and (c.select_one("video, img") or _get_background_image(c, None))
            ]
            if children:
                return children

    # Direct children of container that each hold media (for custom video blocks)
    direct = [
        c for c in container.children
        if hasattr(c, "name") and c.name
        and (c.select_one("video, img") or _get_background_image(c, None))
    ]
    if len(direct) > 1:
        return direct

    return []


def _extract_media_from_container(container, url, site_name, container_selector):
    """
    Extract ALL heroMedia items from a hero container.

    Strategy:
      1. Find discrete slides via _find_slides_in() → one item per slide.
      2. Fallback A: iterate all <video> elements in container → one item per video.
      3. Fallback B: iterate all <img> elements (up to 12) → one item per image.
      4. Fallback C: container-level CSS background-image.
    All paths deduplicate by URL.
    """
    items = []
    seen_urls = set()

    def _add(media_type, media_url, poster=None, heading=None, text=None,
             ctas=None, selector=None, confidence=0.9):
        canonical = (media_url or "").split("?")[0].rstrip("/")
        if canonical and canonical in seen_urls:
            return
        if canonical:
            seen_urls.add(canonical)
        items.append({
            "type": media_type,
            "url": media_url,
            "posterImage": poster,
            "heading": heading,
            "textPreview": (text or "")[:280] or None,
            "ctas": ctas or [],
            "sourceSelector": selector,
            "confidence": confidence,
        })

    def _extract_from_el(el, sel_suffix):
        """Extract the primary medium from a slide or standalone element."""
        video = el.select_one("video")
        if video:
            vsrc = _get_video_url(video)
            poster = video.get("poster") or video.get("data-poster")
            if poster:
                poster = normalize_image_url(poster.strip(), url)
            heading_el = el.select_one("h1, h2, h3")
            heading = clean_text(heading_el.get_text(" ", strip=True)) if heading_el else None
            text = clean_text(el.get_text(" ", strip=True)) or ""
            ctas = extract_section_links(el, url, site_name=site_name)[:3]
            _add("video", vsrc, poster=poster, heading=heading,
                 text=text, ctas=ctas, selector=sel_suffix, confidence=0.95)
            return True

        iframe = el.select_one("iframe")
        if iframe:
            src = iframe.get("src") or iframe.get("data-src") or ""
            if any(d in src for d in ("youtube.com", "youtu.be", "vimeo.com")):
                heading_el = el.select_one("h1, h2, h3")
                heading = clean_text(heading_el.get_text(" ", strip=True)) if heading_el else None
                text = clean_text(el.get_text(" ", strip=True)) or ""
                ctas = extract_section_links(el, url, site_name=site_name)[:3]
                _add("video", src, heading=heading, text=text, ctas=ctas,
                     selector=f"{sel_suffix}_iframe", confidence=0.85)
                return True

        img = el.select_one("img")
        if img:
            image_url = canonical_shopify_image_url(get_img_url(img, url))
            if image_url:
                heading_el = el.select_one("h1, h2, h3")
                heading = clean_text(heading_el.get_text(" ", strip=True)) if heading_el else None
                text = clean_text(el.get_text(" ", strip=True)) or ""
                ctas = extract_section_links(el, url, site_name=site_name)[:3]
                _add("image", image_url, heading=heading, text=text, ctas=ctas,
                     selector=sel_suffix, confidence=0.9)
                return True

        bg = _get_background_image(el, url)
        if bg:
            heading_el = el.select_one("h1, h2, h3")
            heading = clean_text(heading_el.get_text(" ", strip=True)) if heading_el else None
            text = clean_text(el.get_text(" ", strip=True)) or ""
            ctas = extract_section_links(el, url, site_name=site_name)[:3]
            _add("background_image", bg, heading=heading, text=text, ctas=ctas,
                 selector=f"{sel_suffix}_bg", confidence=0.8)
            return True

        return False

    # ── Path 1: Discrete slides ───────────────────────────────────────────
    slides = _find_slides_in(container)
    if slides:
        for slide in slides:
            _extract_from_el(slide, f"{container_selector}/slide")
        if items:
            return items

    # ── Path 2: All <video> elements in container (video-only heroes) ─────
    videos = container.select("video")
    if videos:
        for video in videos:
            vsrc = _get_video_url(video)
            poster = video.get("poster") or video.get("data-poster")
            if poster:
                poster = normalize_image_url(poster.strip(), url)
            # Walk up from each video to find the nearest heading/cta context
            ctx = video.parent
            heading_el = ctx.select_one("h1, h2, h3") if ctx else None
            heading = clean_text(heading_el.get_text(" ", strip=True)) if heading_el else None
            ctas = extract_section_links(ctx or container, url, site_name=site_name)[:3]
            _add("video", vsrc, poster=poster, heading=heading,
                 ctas=ctas, selector=f"{container_selector}/video", confidence=0.9)
        if items:
            return items

    # ── Path 3: All <img> elements (image-only heroes, no slide structure) ─
    imgs = container.select("img")
    for img in imgs[:12]:
        image_url = canonical_shopify_image_url(get_img_url(img, url))
        if not image_url:
            continue
        ctx = img.parent
        heading_el = ctx.select_one("h1, h2, h3") if ctx else None
        heading = clean_text(heading_el.get_text(" ", strip=True)) if heading_el else None
        ctas = extract_section_links(ctx or container, url, site_name=site_name)[:3]
        _add("image", image_url, heading=heading,
             ctas=ctas, selector=f"{container_selector}/img", confidence=0.85)
    if items:
        return items

    # ── Path 4: Container-level CSS background-image ──────────────────────
    bg = _get_background_image(container, url)
    if bg:
        heading_el = container.select_one("h1, h2, h3")
        heading = clean_text(heading_el.get_text(" ", strip=True)) if heading_el else None
        text = clean_text(container.get_text(" ", strip=True)) or ""
        ctas = extract_section_links(container, url, site_name=site_name)[:4]
        _add("background_image", bg, heading=heading, text=text,
             ctas=ctas, selector=f"{container_selector}_bg", confidence=0.75)

    return items


def extract_hero_media(soup, url, site_name=None):
    """
    Find the FIRST hero/slideshow section and extract all its media slides.
    Only collects from that one section — does NOT scan the rest of the page.

    Returns list of:
      {type, url, posterImage, heading, textPreview, ctas, sourceSelector, confidence}
    """
    container = _find_hero_container(soup)

    if not container:
        # Fallback: first section with an image, confidence 0.5
        main_el = soup.select_one("main") or soup
        for section in main_el.select(".shopify-section, section")[:4]:
            if _in_nav_or_header(section):
                continue
            if section_is_footer(section) or section_is_header(section):
                continue
            # Skip product-heavy sections — those are not hero
            if section.select('a[href*="/products/"]'):
                continue
            img = section.select_one("img")
            if not img:
                continue
            image_url = canonical_shopify_image_url(get_img_url(img, url))
            if not image_url:
                continue
            heading_el = section.select_one("h1, h2, h3")
            heading = clean_text(heading_el.get_text(" ", strip=True)) if heading_el else None
            text = clean_text(section.get_text(" ", strip=True)) or ""
            ctas = extract_section_links(section, url, site_name=site_name)[:4]
            return [{
                "type": "unknown",
                "url": image_url,
                "posterImage": None,
                "heading": heading,
                "textPreview": text[:280] or None,
                "ctas": ctas,
                "sourceSelector": "first_section_fallback",
                "confidence": 0.5
            }]
        return []

    container_classes = " ".join(container.get("class", [])).lower()
    container_selector = (
        container.get("data-section-type")
        or next((c for c in container.get("class", []) if any(
            k in c.lower() for k in ("slideshow", "hero", "banner", "slider", "swiper")
        )), None)
        or "hero_container"
    )

    return _extract_media_from_container(container, url, site_name, container_selector)[:16]


def extract_banner_sections(soup, url, site_name=None):
    """Extract collection banners only (hero detection moved to extract_hero_media)."""
    collection_banners = []

    selectors = [
        ".collection-banner",
        "[class*='collection-banner']",
        ".slideshow",
        ".hero",
        ".image-banner",
        "[class*='slideshow']",
        "[class*='hero']",
        "[class*='image-banner']",
        "[class*='banner']",
    ]

    seen_els = set()
    for selector in selectors:
        for el in soup.select(selector):
            el_id = id(el)
            if el_id in seen_els:
                continue
            seen_els.add(el_id)

            if is_trust_badge_block(el):
                continue
            if section_is_footer(el) or section_is_header(el):
                continue
            if not looks_like_collection_banner(el):
                continue

            img = el.select_one("img")
            image_url = canonical_shopify_image_url(get_img_url(img, url)) if img else None
            heading_el = el.select_one("h1, h2, h3")
            heading = clean_text(heading_el.get_text(" ", strip=True)) if heading_el else None
            text = clean_text(el.get_text(" ", strip=True))
            links = extract_section_links(el, url, site_name=site_name)

            if not image_url and not heading and not links:
                continue

            collection_banners.append({
                "heading": heading,
                "textPreview": text[:300] if text else None,
                "imageUrl": image_url,
                "ctas": links[:6],
                "source": {
                    "selector": selector,
                    "confidence": 0.8
                }
            })

    collection_banners = dedupe_items(collection_banners, "imageUrl")[:20]
    return collection_banners


def extract_all_images(soup, url, limit=120):
    images = []

    for img in soup.select("main img, section img, .shopify-section img"):
        image_url = get_img_url(img, url)

        if image_url:
            images.append({
                "url": image_url,
                "alt": clean_text(img.get("alt"))
            })

    return dedupe_images(images)[:limit]


def extract_collection_links(soup, url):
    """Extract featured collection links from homepage content sections only.

    Skips any link that lives inside a <nav>, <header>, <footer>, or an element
    whose class/id contains navigation-related keywords.  This prevents the full
    site navigation menu from appearing as 'featured collections'.
    """
    collections = []

    for a in soup.select('main a[href*="/collections/"], .shopify-section a[href*="/collections/"]'):
        # Skip nav/header/footer links — these are navigation, not featured content
        if _in_nav_or_header(a):
            continue

        href = clean_link_url(a.get("href"))

        if not href:
            continue

        full_url = strip_variant_url(urljoin(url, href).split("?")[0])

        if "/products/" in full_url:
            continue

        text = clean_cta_text(a.get_text(" ", strip=True), href)
        handle = get_handle_from_url(full_url)

        if not text:
            text = handle_to_title(handle)

        if is_noise_text(text):
            continue

        if text.lower().startswith("cart "):
            continue

        collections.append({
            "name": text,
            "handle": handle,
            "url": full_url
        })

    return dedupe_items(collections, "url")[:100]


def extract_primary_ctas(soup, url, site_name=None):
    """Extract primary action CTAs from homepage buttons/links.

    Only short imperative phrases qualify (Shop Now, View All, Explore, etc.).
    Navigation links and footer links are explicitly excluded.
    """
    found = []
    seen_texts = set()

    candidates = soup.select(
        "main a, main button, "
        ".shopify-section a, .shopify-section button"
    )

    for el in candidates:
        # Skip anything inside nav/header/footer
        if _in_nav_or_header(el):
            continue

        href = clean_link_url(el.get("href")) if el.name == "a" else None
        text = clean_text(el.get_text(" ", strip=True))

        if not text:
            continue

        # Max 8 words for a primary CTA button
        if len(text.split()) > 8:
            continue

        if is_noise_text(text):
            continue

        text_l = text.lower().strip()

        # Must match at least one primary CTA keyword
        is_primary = (
            text_l in _PRIMARY_CTA_KEYWORDS
            or any(kw in text_l for kw in [
                "shop now", "shop all", "shop collection",
                "view all", "view collection",
                "explore", "discover",
                "buy now", "buy bundles",
                "see all", "see more",
            ])
        )

        if not is_primary:
            continue

        if text_l in seen_texts:
            continue

        seen_texts.add(text_l)

        if not href:
            continue  # skip buttons/links without a real URL

        full_url = strip_variant_url(urljoin(url, href))

        found.append({
            "text": text,
            "url": full_url
        })

    return found[:15]


def extract_ctas(soup, url, site_name=None):
    """Full CTA list (collection + page + product CTAs). Excludes nav/footer.

    Scope note: many themes (e.g. Kalles) wrap their collection carousels in
    custom <div>s rather than <section>/.shopify-section, so a "SHOP ALL" /
    "VIEW ALL" link lived outside the old selector and was never counted. We
    also pull every /collections/ and /pages/ anchor in the body and rely on
    _in_nav_or_header to drop the menu/footer ones.
    """
    ctas = []

    for a in soup.select(
        "main a, section a, .shopify-section a, "
        "a[href*='/collections/'], a[href*='/pages/']"
    ):
        if _in_nav_or_header(a):
            continue

        href = clean_link_url(a.get("href"))

        if not href:
            continue

        full_url = strip_variant_url(urljoin(url, href))

        text = clean_cta_text(a.get_text(" ", strip=True), href, site_name=site_name)

        if "/products/" in href:
            product = extract_product_from_link(a, url, site_name=site_name)

            if not product:
                continue

            text = product.get("name")

        if not text:
            continue

        if text.lower() in FOOTER_HEADINGS:
            continue

        if text.lower().startswith("cart "):
            continue

        if any(x in href for x in ["/collections/", "/pages/"]):
            ctas.append({
                "text": text,
                "url": full_url
            })
            continue

        if "/products/" in href and product:
            ctas.append({
                "text": text,
                "url": full_url
            })
            continue

        if any(k in text.lower() for k in ["shop", "buy", "view", "explore", "discover", "learn", "order", "browse", "register"]):
            ctas.append({
                "text": text,
                "url": full_url
            })

    return dedupe_items(ctas, "url")[:50]


def extract_blog_links(soup, url):
    blogs = []

    for a in soup.select('a[href*="/blogs/"], a[href*="/blog/"], a[href*="/news/"]'):
        href = clean_link_url(a.get("href"))

        if not href:
            continue

        text = clean_cta_text(a.get_text(" ", strip=True), href)

        if not text:
            continue

        blogs.append({
            "title": text,
            "url": urljoin(url, href)
        })

    return dedupe_items(blogs, "url")[:40]


def extract_footer_links(soup, url):
    """Extract links from the site footer."""
    links = []
    for a in soup.select("footer a[href]"):
        href = clean_link_url(a.get("href"))
        if not href:
            continue
        text = clean_text(a.get_text(" ", strip=True))
        if not text or is_noise_text(text):
            continue
        if text.lower().startswith("cart "):
            continue
        full_url = strip_variant_url(urljoin(url, href))
        links.append({"text": text, "url": full_url})
    return dedupe_items(links, "url")[:40]


# ---------------------------------------------------------------------------
# Feature detection & metrics
# ---------------------------------------------------------------------------

def detect_features(sections, navigation_links, images, products, collections,
                    ctas, announcement, hero_media, collection_banners, footer_text=""):
    text_blob = " ".join([
        " ".join([s.get("textPreview") or "" for s in sections]),
        " ".join([n.get("text") or "" for n in navigation_links]),
    ]).lower()
    # Footers commonly hold the newsletter signup, trust badges and social
    # links — but footer sections are excluded from `sections`, so scan the
    # footer text too for those signals (otherwise a footer newsletter reads
    # as "No").
    footer_blob = (footer_text or "").lower()
    # The announcement bar text (e.g. "Free Delivery on Bank Deposit") is a real
    # promotional/trust signal but lives outside `sections`, so fold it into the
    # blobs the feature flags are derived from.
    ann_text = (announcement.get("text") or "").lower() if isinstance(announcement, dict) else ""
    text_blob = (text_blob + " " + ann_text).strip()
    footer_inclusive = (text_blob + " " + footer_blob)

    # Derive has-products / has-prices from section evidence (works for JS-rendered pages)
    has_product_sections = any(s.get("type") == "product_section" for s in sections)
    has_prices_in_sections = any(
        s.get("type") == "product_section" and (
            any(k in (s.get("textPreview") or "").lower()
                for k in ("rs.", "pkr", "£", "€", "$", "price", "sale price"))
            or (s.get("source", {}).get("priceCount", 0) or 0) > 0
        )
        for s in sections
    ) or len(products) > 0

    return {
        "hasAnnouncementBar": announcement.get("detected", False),
        "hasHero": len(hero_media) > 0,
        "hasCollectionBanners": len(collection_banners) > 0,
        "hasFeaturedProducts": len(products) > 0 or has_product_sections,
        "hasFeaturedCollections": len(collections) > 0,
        "hasBlogPreview": "/blogs/" in text_blob or "blog" in text_blob or "guide" in text_blob,
        "hasNewsletter": any(k in footer_inclusive for k in ("newsletter", "subscribe", "mailing list", "sign up")),
        "hasTestimonials": any(k in footer_inclusive for k in ("testimonial", "review", "customer", "trusted by", "loved by")),
        "hasTrustSignals": any(k in footer_inclusive for k in TRUST_KEYWORDS),
        "hasInstagramFeed": "instagram" in footer_inclusive,
        "hasWhatsapp": "whatsapp" in footer_inclusive,
        "hasDiscountMessaging": any(k in text_blob for k in ("sale", "discount", "% off")),
        # Shipping / payment incentives (free delivery, COD, bank deposit) are a
        # promotional lever even when NO product carries a % discount — Sivanna's
        # free-delivery bar is a good example. Kept distinct from hasDiscountMessaging
        # (which is product-price discounting) so the two postures don't get conflated.
        "hasFreeShippingOffer": any(k in footer_inclusive for k in ("free delivery", "free shipping", "free ship")),
        "hasPromotionalOffer": bool(ann_text) and any(
            k in ann_text for k in PROMO_BAR_KEYWORDS
        ),
        "promotionalOffers": _extract_promo_offers(ann_text, text_blob),
        "hasProducts": len(products) > 0 or has_product_sections,
        "hasPrices": has_prices_in_sections,
    }


def build_homepage_metrics(sections, images, products, collections, ctas, blogs,
                           announcement, hero_media, collection_banners):
    priced_products = [p for p in products if p.get("currentPrice") is not None]

    product_sections = [s for s in sections if s.get("type") == "product_section"]
    product_sections_with_prices = [
        s for s in product_sections
        if any(k in (s.get("textPreview") or "").lower()
               for k in ("rs.", "pkr", "£", "€", "$", "price", "sale price"))
        or (s.get("source", {}).get("priceCount", 0) or 0) > 0
        or len([l for l in (s.get("links") or []) if l.get("type") == "product"]) > 0
    ]

    # Estimate product cards by counting product links across all product sections
    product_card_estimate = sum(
        len([l for l in (s.get("links") or []) if "/products/" in (l.get("url") or "")])
        for s in product_sections
    ) or len(products)

    return {
        "sectionCount": len(sections),
        "heroCount": len(hero_media),
        "collectionBannerCount": len(collection_banners),
        "imageCount": len(images),
        "featuredProductCount": len(products),
        "featuredProductWithPriceCount": len(priced_products),
        "featuredCollectionCount": len(collections),
        "ctaCount": len(ctas),
        "blogLinkCount": len(blogs),
        "hasAnnouncementBar": announcement.get("detected", False),
        "productSectionCount": len(product_sections),
        "productSectionWithPriceCount": len(product_sections_with_prices),
        "productCardEstimate": product_card_estimate,
    }


# Per-category keyword sets used to infer store vertical from nav/headings/collections.
# Ordered from most-specific to most-generic within each vertical.
_CATEGORY_KEYWORDS = {
    "makeup": [
        "makeup", "cosmetics", "lipstick", "lip gloss", "lip liner", "foundation",
        "mascara", "eyeshadow", "eyeliner", "blush", "bronzer", "concealer",
        "primer", "setting spray", "highlighter", "contour", "bb cream", "cc cream",
        "lash", "lashes", "brow", "eyebrow", "color corrector",
    ],
    "skincare": [
        "skincare", "skin care", "moisturizer", "moisturiser", "serum", "toner",
        "cleanser", "face wash", "sunscreen", "spf", "retinol", "vitamin c",
        "hyaluronic", "niacinamide", "face cream", "eye cream", "face mask",
        "exfoliant", "exfoliator", "essence", "ampoule", "pore", "acne",
    ],
    "haircare": [
        "haircare", "hair care", "shampoo", "conditioner", "hair mask", "hair oil",
        "hair serum", "scalp", "hair treatment", "hair loss", "dry shampoo",
        "leave-in", "keratin", "argan oil", "hair growth",
    ],
    "kids_fashion": [
        "kids", "children", "toddler", "baby", "infant", "newborn",
        "boys clothing", "girls clothing", "children's wear", "kids fashion",
        "little ones", "ages 0", "ages 2", "play wear",
        "kidswear", "babywear", "sleepsuits", "sleepsuit", "bathrobe", "bodysuits",
        "bodysuit", "romper", "rompers", "swaddle", "swaddles", "night suit",
        "baby clothes", "baby clothing", "onesie", "onesies",
    ],
    "pet": [
        "pet", "dog", "cat", "puppy", "kitten", "bird", "fish", "rabbit",
        "hamster", "paw", "kibble", "cat food", "dog food", "pet food",
        "treats", "vet", "pet care", "grooming", "collar", "leash",
    ],
    "electronics": [
        "electronics", "phone", "smartphone", "laptop", "tablet", "gadget",
        "tech", "headphones", "earbuds", "speaker", "charger", "cable",
        "smart watch", "smartwatch", "wireless", "bluetooth", "gaming",
        "computer", "monitor", "keyboard", "mouse",
    ],
    "fashion": [
        "fashion", "clothing", "apparel", "shirt", "dress", "pants", "jeans",
        "jacket", "coat", "shoes", "sneakers", "accessories", "handbag", "bag",
        "jewellery", "jewelry", "watch", "belt", "scarf", "hat",
    ],
    "wellness": [
        "wellness", "yoga", "fitness", "health", "supplement", "natural",
        "organic", "herbal", "vitamin", "protein", "nutrition", "detox",
        "mindfulness", "meditation", "sleep", "immunity",
    ],
    "home": [
        "home", "furniture", "decor", "interior", "living room", "kitchen",
        "bedroom", "garden", "cushion", "candle", "lamp", "rug",
    ],
    "sports": [
        "sports", "gym", "athletic", "workout", "running", "training",
        "cycling", "swimming", "hiking", "outdoor", "activewear",
    ],
    "food": [
        "food", "grocery", "snack", "beverage", "drink", "coffee", "tea",
        "chocolate", "candy", "biscuit", "sauce", "spice", "condiment",
    ],
    "natural_food": [
        "honey", "raw honey", "pure honey", "beeswax", "bee wax", "bees wax",
        "pollen", "propolis", "bee pollen", "bee propolis", "mead",
        "natural honey", "organic honey", "wildflower honey", "manuka",
        "apiary", "apiculture", "honeycomb", "natural food", "organic food",
    ],
}

# Maps detected category → homepageType value
_CATEGORY_TO_HOMEPAGE_TYPE = {
    "makeup":       "beauty_cosmetics",
    "skincare":     "skincare_beauty",
    "haircare":     "haircare_beauty",
    "kids_fashion": "kids_fashion",
    "pet":          "pet_food",
    "electronics":  "electronics",
    "fashion":      "general_ecommerce",
    "wellness":     "general_ecommerce",
    "home":         "general_ecommerce",
    "sports":       "general_ecommerce",
    "food":         "general_ecommerce",
    "natural_food": "natural_food_wellness",
}

# Keep old alias for backward compatibility
_BEAUTY_CATEGORY_TYPES = _CATEGORY_TO_HOMEPAGE_TYPE


def _detect_main_category(navigation_links, sections, collections):
    """Infer the primary product category from nav labels, section headings, and collection names."""
    from collections import Counter

    sources = (
        [n.get("text", "") for n in navigation_links]
        + [s.get("heading") or "" for s in sections]
        + [s.get("textPreview", "")[:100] for s in sections]
        + [c.get("name", "") for c in collections]
        + [c.get("title", "") for c in collections]
    )
    blob = " ".join(sources).lower()

    counter = Counter()
    for category, keywords in _CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in blob:
                counter[category] += 1

    if not counter:
        return None

    return counter.most_common(1)[0][0]


def _detect_homepage_type(sections, featured_products, featured_collections, features, primary_category=None):
    """Classify the homepage layout type."""
    # Vertical override — known category → specific type
    if primary_category and primary_category in _CATEGORY_TO_HOMEPAGE_TYPE:
        return _CATEGORY_TO_HOMEPAGE_TYPE[primary_category]

    product_count = len(featured_products)
    collection_count = len(featured_collections)
    section_types = [s.get("type") for s in sections]
    product_section_count = sum(1 for t in section_types if t == "product_section")
    has_any_ecommerce = product_count > 0 or product_section_count > 0 or collection_count > 0

    has_sale = "promo" in section_types or features.get("hasDiscountMessaging")
    has_testimonials = features.get("hasTestimonials", False)

    if has_sale and (product_count >= 3 or product_section_count >= 1):
        return "sale_promo"
    if product_section_count >= 2 or product_count >= 6:
        return "general_ecommerce"
    if collection_count >= 4 and product_count <= 4:
        return "collection_showcase"
    if has_testimonials and product_count <= 4:
        return "brand_story"
    if has_any_ecommerce:
        return "general_ecommerce"
    return "general"


# ── Sub-category keyword maps per store vertical ─────────────────────────────
# Keys are the canonical sub-category slug; values are keyword lists to match
# against nav link text, section headings, and collection names (all lowercased).
_SUBCATEGORY_MAPS = {
    "makeup": {
        "face_makeup": ["foundation", "concealer", "face powder", "blush", "bronzer",
                        "primer", "setting powder", "setting spray", "face makeup",
                        "bb cream", "cc cream", "compact", "cushion"],
        "eye_makeup": ["mascara", "eyeliner", "eyebrow", "eye shadow", "eyeshadow",
                       "eyes makeup", "lash", "lashes", "brow", "eye liner",
                       "kajal", "kohl"],
        "lip_makeup": ["lipstick", "lip gloss", "lip tint", "lip balm", "lip liner",
                       "lip color", "lips", "lip makeup", "lip product", "lip stain"],
        "skincare": ["skincare", "skin care", "serum", "toner", "sunscreen", "spf",
                     "moisturizer", "moisturiser", "cleanser", "face wash", "essence",
                     "ampoule", "face mist", "primer", "skin mist"],
        "makeup_remover": ["makeup remover", "cleansing oil", "micellar"],
        "nail": ["nail polish", "nail color", "nail lacquer", "nail care", "nail"],
    },
    "skincare_beauty": {
        "moisturizer": ["moisturizer", "moisturiser", "face cream", "day cream", "night cream"],
        "serum": ["serum", "essence", "ampoule", "booster"],
        "cleanser": ["cleanser", "face wash", "cleansing", "cleanse"],
        "sunscreen": ["sunscreen", "spf", "sun protection", "uv"],
        "toner": ["toner", "mist", "skin mist"],
        "eye_care": ["eye cream", "eye serum", "eye care"],
        "mask": ["mask", "face mask", "sheet mask", "clay mask"],
        "exfoliant": ["exfoliant", "exfoliator", "scrub", "peel"],
    },
    "haircare": {
        "shampoo": ["shampoo"],
        "conditioner": ["conditioner", "co-wash"],
        "hair_oil": ["hair oil", "oil treatment", "argan oil", "coconut oil"],
        "hair_serum": ["hair serum", "serum"],
        "hair_mask": ["hair mask", "deep conditioning", "treatment mask"],
        "scalp_care": ["scalp", "scalp treatment", "anti-dandruff"],
        "styling": ["styling", "gel", "wax", "mousse", "spray", "pomade"],
        "hair_color": ["hair color", "hair dye", "hair colour", "highlights"],
    },
    "pet_food": {
        "wet_cat_food": ["wet food", "wet cat food", "creamy", "pouch", "sachet",
                         "gravy", "broth", "cat food"],
        "dry_cat_food": ["dry food", "dry cat food", "kibble", "biscuit"],
        "cat_treats": ["treat", "treats", "cat treats", "snack", "toppers"],
        "cat_bundles": ["bundle", "bundles", "pack", "packs", "combo", "value pack"],
        "dog_food": ["dog food", "dog treats", "puppy"],
        "fish_food": ["fish food", "aquarium", "pond"],
    },
    "kids_fashion": {
        "baby_clothes": ["baby", "infant", "newborn", "onesie", "romper", "swaddle"],
        "toddler": ["toddler", "ages 2", "ages 3", "ages 4"],
        "boys_clothing": ["boys", "boys clothing", "boys wear"],
        "girls_clothing": ["girls", "girls clothing", "girls wear"],
        "sleepwear": ["sleepsuit", "pajama", "night suit", "sleep"],
        "accessories": ["bib", "hat", "socks", "shoes", "blanket"],
    },
    "natural_food_wellness": {
        "honey": ["honey", "raw honey", "organic honey", "wildflower", "manuka"],
        "beeswax": ["beeswax", "bee wax"],
        "pollen": ["pollen", "bee pollen"],
        "propolis": ["propolis"],
        "organic_food": ["organic food", "natural food", "superfood"],
    },
    "electronics": {
        "phones": ["phone", "smartphone", "mobile"],
        "accessories": ["case", "cover", "charger", "cable", "accessory"],
        "audio": ["headphones", "earphones", "earbuds", "speaker"],
        "computers": ["laptop", "tablet", "computer"],
        "wearables": ["watch", "smartwatch", "fitness tracker"],
    },
    "sports": {
        "cricket": ["cricket", "bat", "batting", "bowling"],
        "padel": ["padel"],
        "pickleball": ["pickleball"],
        "sportswear": ["sportswear", "activewear", "jersey", "shorts", "track"],
        "footwear": ["shoes", "boots", "cleats", "sneakers"],
    },
}


def _derive_business_classification(sections, featured_collections, navigation_links,
                                    primary_category, homepage_type=None):
    """Derive businessClassification: homepageType + subCategories from site signals.

    primary_category: raw key from _detect_main_category (e.g. "pet", "makeup")
    homepage_type:    mapped key from _detect_homepage_type (e.g. "pet_food", "beauty_cosmetics")

    _SUBCATEGORY_MAPS uses raw category keys for some verticals ("makeup", "haircare")
    and mapped keys for others ("pet_food", "skincare_beauty").  We try both so that
    "pet" (raw) finds "pet_food" map, and "makeup" (raw) finds "makeup" map directly.
    """
    # Collect candidate text from navigation, section headings, collection names
    candidate_texts = []
    for link in (navigation_links or []):
        t = (link.get("text") or "").strip().lower()
        if t:
            candidate_texts.append(t)
    for sec in (sections or []):
        h = (sec.get("heading") or "").strip().lower()
        if h:
            candidate_texts.append(h)
    for col in (featured_collections or []):
        n = (col.get("name") or "").strip().lower()
        h = (col.get("handle") or "").strip().lower()
        if h:
            candidate_texts.append(h.replace("-", " "))

    combined = " | ".join(candidate_texts)

    # Resolve the subcategory map.
    # _detect_main_category returns raw keys ("pet", "makeup") while
    # _detect_homepage_type maps them to typed keys ("pet_food", "beauty_cosmetics").
    # _SUBCATEGORY_MAPS uses raw keys for some verticals and typed keys for others,
    # so we try both to cover all cases.
    sub_map = (
        _SUBCATEGORY_MAPS.get(primary_category or "")
        or _SUBCATEGORY_MAPS.get(homepage_type or "")
    )
    if not sub_map:
        # Partial-match fallback
        for key in _SUBCATEGORY_MAPS:
            if primary_category and (key in primary_category or primary_category in key):
                sub_map = _SUBCATEGORY_MAPS[key]
                break

    subcategories = []
    if sub_map:
        for slug, keywords in sub_map.items():
            if any(kw in combined for kw in keywords):
                subcategories.append(slug)

    return {
        "homepageType": homepage_type or primary_category,
        "subCategories": subcategories[:8],
    }


def build_homepage_summary(
    site_name, sections, featured_products, featured_collections,
    primary_ctas, features, hero_media, announcement, navigation_links
):
    """Build a lightweight summary of the homepage for competitive analysis."""
    top_section_types = []
    seen_types = set()
    for s in sections:
        t = s.get("type")
        if t and t not in seen_types:
            seen_types.add(t)
            top_section_types.append(t)

    main_category = _detect_main_category(navigation_links, sections, featured_collections)
    homepage_type = _detect_homepage_type(sections, featured_products, featured_collections,
                                          features, main_category)
    business_classification = _derive_business_classification(
        sections, featured_collections, navigation_links, main_category,
        homepage_type=homepage_type
    )

    testimonial_count = sum(1 for s in sections if s.get("type") in ("testimonials", "testimonial_section"))
    trust_count = sum(1 for s in sections if s.get("type") == "trust_signal")
    product_section_count = sum(1 for s in sections if s.get("type") == "product_section")

    # Derive positioning from hero text and section headings
    positioning = []
    seen_pos = set()
    for source in (
        [b.get("heading") or "" for b in hero_media]
        + [b.get("textPreview") or "" for b in hero_media[:3]]
        + [s.get("heading") or "" for s in sections[:8]]
    ):
        text = (source or "").strip()
        if text and len(text) > 3 and text.lower() not in seen_pos:
            seen_pos.add(text.lower())
            positioning.append(text[:120])

    # Determine hero media type
    hero_has_video = any(h.get("type") == "video" or h.get("url", "").endswith((".mp4", ".webm")) for h in hero_media)
    hero_has_image = any(h.get("type") in ("image", "banner") or h.get("posterImage") for h in hero_media)
    hero_has_text = any((h.get("heading") or "").strip() or (h.get("textPreview") or "").strip() for h in hero_media)
    if hero_has_video and hero_has_image:
        hero_type = "mixed"
    elif hero_has_video:
        hero_type = "video"
    elif hero_has_image:
        hero_type = "image"
    else:
        hero_type = "unknown" if hero_media else None

    # heroStyle: carousel vs single + media type
    n_hero = len(hero_media)
    if n_hero > 1:
        if hero_has_video and hero_has_image:
            hero_style = "mixed_media_carousel"
        elif hero_has_video:
            hero_style = "video_carousel"
        else:
            hero_style = "image_carousel"
    elif n_hero == 1:
        hero_style = "single_video" if hero_has_video else "single_image" if hero_has_image else None
    else:
        hero_style = None

    return {
        "siteName": site_name,
        "primaryCategory": main_category,
        "positioning": positioning[:6],
        "heroCount": n_hero,
        "heroType": hero_type,
        "heroStyle": hero_style,
        "heroHasText": hero_has_text,
        "collectionCount": len(featured_collections),
        "featuredProductCount": len(featured_products),
        "productSectionCount": product_section_count,
        "testimonialCount": testimonial_count,
        "trustSignalCount": trust_count,
        "primaryCtas": [c for c in primary_ctas if c.get("url")][:8],
        "topSections": top_section_types[:8],
        "homepageType": homepage_type,
        "businessClassification": business_classification,
    }


def analyze_homepage(self, url, html, headers, page_type, level1):
    result = self.base_result(url, html, headers, page_type, level1)
    platform = result.get("platform", "Shopify")
    # Pull base-result fields into local variables used in the final result dict.
    seo             = result.get("seo") or {}
    open_graph      = result.get("openGraph") or {}
    response_headers = result.get("technical", {}).get("responseHeaders") or {}
    # Shopify homepage confidence: elevated above the base 0.5 since platform is confirmed.
    confidence      = 0.85
    soup = BeautifulSoup(html or "", "lxml")

    site_name = result.get("openGraph", {}).get("site_name") or result.get("seo", {}).get("h1")

    announcement = extract_announcement_bar(soup)
    clean_navigation = extract_clean_navigation(soup, url)
    footer_links = extract_footer_links(soup, url)
    images = extract_all_images(soup, url)
    sections = extract_homepage_sections(soup, url, site_name=site_name)
    hero_media = extract_hero_media(soup, url, site_name=site_name)
    collection_banners = extract_banner_sections(soup, url, site_name=site_name)
    featured_products = extract_product_links(soup, url, site_name=site_name)
    featured_collections = extract_collection_links(soup, url)
    primary_ctas = extract_primary_ctas(soup, url, site_name=site_name)
    ctas = extract_ctas(soup, url, site_name=site_name)
    # JS-rendered themes (e.g. Kalles) inject the section "Shop All / View All"
    # anchors client-side, so they're absent from the raw HTML and the anchor
    # scan above finds none — even though the store clearly has them. Each
    # featured collection and each collection/banner CTA IS one of those buttons,
    # so derive them from what we already extracted (from section JSON) instead.
    _cta_urls = {c.get("url") for c in ctas if c.get("url")}
    def _add_cta(text, u):
        if u and u not in _cta_urls:
            ctas.append({"text": text or "Shop collection", "url": u})
            _cta_urls.add(u)
    for _fc in (featured_collections or []):
        _add_cta(_fc.get("title") or _fc.get("text"), _fc.get("url"))
    for _b in (collection_banners or []):
        _add_cta(_b.get("heading") or _b.get("title"), _b.get("url"))
        for _c in (_b.get("ctas") or []):
            _add_cta(_c.get("text"), _c.get("url"))
    # Identify merchandising CTAs by their TEXT INTENT ("Shop All", "View All",
    # etc.) rather than DOM container. Themes like Kalles wrap section carousels
    # in nav-classed wrappers, so container-based filtering wrongly drops the
    # section "SHOP ALL" buttons — but matching on the call-to-action wording
    # catches them wherever they sit, while ignoring plain mega-menu links (whose
    # text is a collection NAME, not a CTA verb).
    _all_coll_anchors = soup.select("a[href*='/collections/']")
    _raw_coll = len(_all_coll_anchors)
    _raw_prod = len(soup.select("a[href*='/products/']"))
    _CTA_TEXT_KW = (
        "shop all", "view all", "see all", "shop now", "shop the collection",
        "shop collection", "view collection", "view more", "explore", "discover",
        "browse", "shop the",
    )
    for _a in _all_coll_anchors + soup.select("a[href*='/pages/']"):
        _href = _a.get("href")
        if not _href:
            continue
        _txt = clean_text(_a.get_text(" ", strip=True)) or ""
        if any(k in _txt.lower() for k in _CTA_TEXT_KW):
            _add_cta(_txt, strip_variant_url(urljoin(url, _href)))
    print(f"🏠 [homepage] raw anchors: collections={_raw_coll}, products={_raw_prod}, htmlLen={len(str(soup))}")
    print(f"🏠 [homepage] CTAs found: {len(ctas)} (featuredCollections={len(featured_collections or [])}, banners={len(collection_banners or [])})" + (f" e.g. {[c.get('text') for c in ctas[:4]]}" if ctas else ""))
    section_headings = extract_section_headings(soup)
    blog_links = extract_blog_links(soup, url)

    # Aggregate products from all product sections into featured_products.
    # extract_product_links() walks raw <a> tags; section-level extraction via
    # extract_product_from_link() is richer (card context, price fallback).
    # Merge both pools, deduplicating by URL so metrics reflect true totals.
    _sec_product_urls = {p.get("url", "") for p in featured_products if p.get("url")}
    for _sec in sections:
        if _sec.get("type") == "product_section":
            for _sp in (_sec.get("products") or []):
                _sp_url = _sp.get("url", "")
                if _sp_url and _sp_url not in _sec_product_urls:
                    _sec_product_urls.add(_sp_url)
                    featured_products.append(_sp)
    # A homepage genuinely SHOWS only a curated handful of products (hero picks,
    # a "new arrivals" strip, best-sellers carousel) — this is NOT the store's
    # catalog, it's what they chose to put on the front page. 60 (was 30) so big
    # multi-carousel homepages aren't clipped, while staying bounded. Named
    # honestly downstream as "products found on the homepage", not a catalog count.
    featured_products = featured_products[:60]

    # --- Product accuracy supplement via Shopify /products.json API --------
    # DOM extraction of homepage product cards is unreliable for NAMES and
    # PRICES alike (lazy-loaded prices, "from" ranges, and — worst — carousels
    # that pair the WRONG title/price with a product's link). Shopify's
    # /products.json is the source of truth, so we look each product up by the
    # handle in its URL (the link is authoritative; the scraped name/handle may
    # be mismatched) and OVERRIDE name/price/availability — not just fill blanks.
    def _handle_from_product(fp):
        return (
            get_handle_from_url(fp.get("url") or fp.get("productUrl") or "")
            or fp.get("handle")
        )

    _featured_with_handles = [p for p in featured_products if _handle_from_product(p)]
    print(f"🏠 [homepage] product supplement v2: {len(_featured_with_handles)}/{len(featured_products)} products found on homepage have a URL handle")
    if _featured_with_handles:
        try:
            _parsed_url = urlparse(url)
            _store_base = f"{_parsed_url.scheme}://{_parsed_url.netloc}"
            # Reuse any Cloudflare clearance cookies the page fetch earned (when
            # it came via Playwright) so bot-protected stores don't 403 the API.
            _cf_cookies = headers.get("cookies") if isinstance(headers, dict) else None
            try:
                import cloudscraper
                _session = cloudscraper.create_scraper(
                    browser={"browser": "chrome", "platform": "windows", "mobile": False}
                )
            except Exception:
                _session = requests
            # Public product JSON — tolerate stale local CA bundles (some envs
            # report valid Shopify certs as "expired"). Silence the noise too.
            try:
                import urllib3
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            except Exception:
                pass

            _wanted = {_handle_from_product(p) for p in _featured_with_handles}
            _handle_info: dict = {}
            _page = 1
            while True:
                _page_url = f"{_store_base}/products.json?limit=250&page={_page}"
                try:
                    # Primary: cloudscraper (its TLS fingerprint clears Cloudflare).
                    _pr = _session.get(
                        _page_url, headers=_SHOPIFY_API_HEADERS,
                        cookies=_cf_cookies, timeout=20
                    )
                except Exception:
                    # Fallback: a stale local CA bundle can misreport valid certs
                    # as "expired". Public product JSON, so retry with plain
                    # requests and verification off (handles verify=False cleanly,
                    # unlike cloudscraper's custom SSL context).
                    _pr = requests.get(
                        _page_url, headers=_SHOPIFY_API_HEADERS,
                        cookies=_cf_cookies, timeout=20, verify=False
                    )
                if not _pr.ok:
                    break
                _batch = _pr.json().get("products") or []
                if not _batch:
                    break
                for _ap in _batch:
                    _h = _ap.get("handle")
                    if not _h:
                        continue
                    _variants = _ap.get("variants") or []
                    _price = None
                    _available = None
                    if _variants:
                        try:
                            _pv = float(_variants[0].get("price") or 0)
                            # 0 = "no price set" (priced on request), not free.
                            _price = _pv if _pv > 0 else None
                        except (TypeError, ValueError):
                            _price = None
                        _available = any(v.get("available") for v in _variants)
                    _handle_info[_h] = {
                        "title": _ap.get("title"),
                        "price": _price,
                        "available": _available,
                    }
                if _wanted.issubset(set(_handle_info.keys())):
                    break
                if len(_batch) < 250:
                    break  # last page
                _page += 1
                if _page > 10:
                    break  # safety cap

            print(f"🏠 [homepage] products.json returned {len(_handle_info)} handles")
            if _handle_info:
                from utils.currency import currency_from_url
                _store_currency = currency_from_url(url) or "USD"
                _corrected = 0
                for _fp in featured_products:
                    _handle = _handle_from_product(_fp)
                    _info = _handle_info.get(_handle) if _handle else None
                    if not _info:
                        continue
                    # Keep the handle consistent with the (authoritative) URL.
                    _fp["handle"] = _handle
                    # products.json is authoritative — correct name AND price.
                    if _info.get("title"):
                        _fp["title"] = _info["title"]
                        _fp["name"] = _info["title"]
                    if _info.get("price") is not None:
                        _fp["price"] = {
                            # Keep the DOM-detected currency (e.g. "Rs." → PKR)
                            # over the TLD guess, which fails for subdomain stores.
                            "currency": _fp.get("currency") or _store_currency,
                            "current": _info["price"],
                            "compareAt": None,
                            "isOnSale": False,
                            "priceTextRaw": str(_info["price"]),
                        }
                    if _info.get("available") is not None:
                        _fp["availability"] = "in_stock" if _info["available"] else "out_of_stock"
                    _corrected += 1
                print(f"🏠 [homepage] corrected {_corrected} featured products from products.json")
        except Exception as _e:
            # Don't stay silent — a swallowed error here looks exactly like the
            # DOM data being 'right', so surface it.
            print(f"🏠 [homepage] product supplement FAILED: {type(_e).__name__}: {_e}")

    # Normalize any 0 price (from products.json, DOM, or elsewhere) to absent —
    # 0 here means "price not mentioned" (priced on request), never a real price.
    for _fp in featured_products:
        _pr = _fp.get("price")
        if isinstance(_pr, dict) and (_pr.get("current") == 0 or _pr.get("current") == 0.0):
            _pr["current"] = None
            _pr["priceTextRaw"] = None
            _pr["isOnSale"] = False

    footer_text = " ".join(f.get_text(" ", strip=True) for f in soup.find_all("footer"))

    # --- Vision read of image-only banners --------------------------------
    # Stores often bake their live promo into a hero IMAGE with no HTML text
    # (e.g. "Flat 25% on activewear ... 11th–16th Aug"). Those slides are
    # invisible to text extraction. Read them with a vision model so the offer
    # and its MEANING are captured. Mutates hero_media / collection_banners in
    # place (they're referenced in the result payload). Cost-capped + env-gated;
    # a normal text hero triggers zero calls. Never breaks the pipeline.
    try:
        from analyzers.shopify.banner_vision import enrich_media_with_vision
        enrich_media_with_vision(hero_media, collection_banners)
    except Exception as _bv_e:
        print(f"🖼️  [banner-vision] enrichment error (continuing): {type(_bv_e).__name__}: {_bv_e}")

    features = detect_features(
        sections=sections,
        navigation_links=clean_navigation,
        images=images,
        products=featured_products,
        collections=featured_collections,
        ctas=ctas,
        announcement=announcement,
        hero_media=hero_media,
        collection_banners=collection_banners,
        footer_text=footer_text,
    )

    # WhatsApp / floating chat detection. The visible-text check in
    # detect_features only catches the literal word "whatsapp"; floating buttons
    # are usually a bare wa.me link or a widget with no on-page text, so scan the
    # markup itself (hrefs, class/id/aria names, widget script domains).
    _markup_l = str(soup).lower()
    _wa_markers = (
        "wa.me/", "api.whatsapp.com", "web.whatsapp.com", "whatsapp://",
        "chat.whatsapp.com", "send?phone=",
    )
    features["hasWhatsapp"] = bool(
        features.get("hasWhatsapp")
        or any(p in _markup_l for p in _wa_markers)
        or soup.select_one(
            "a[href*='wa.me'], a[href*='whatsapp'], "
            "[class*='whatsapp'], [id*='whatsapp'], "
            "[class*='wa-chat'], [class*='wa-float'], [class*='ws-float'], "
            "[aria-label*='whatsapp' i], [data-widget*='whatsapp' i]"
        )
    )

    # Video presence on the homepage — native <video> (incl. lazy data-src) or
    # embedded players (YouTube/Vimeo/Wistia), plus common background-video and
    # lazy-loaded patterns Shopify themes use for hero videos.
    _video_nodes = soup.select(
        "video, video source, "
        "iframe[src*='youtube'], iframe[src*='youtu.be'], "
        "iframe[src*='vimeo'], iframe[src*='wistia'], "
        "iframe[data-src*='youtube'], iframe[data-src*='vimeo'], "
        "[class*='video-background'], [class*='background-video'], "
        "[class*='hero-video'], [data-video-id], [data-video-url], deferred-media"
    )
    features["hasVideo"] = bool(_video_nodes) or any(
        (m.get("type") == "video") for m in (hero_media or []) if isinstance(m, dict)
    )
    features["videoCount"] = len(_video_nodes)

    metrics = build_homepage_metrics(
        sections=sections,
        images=images,
        products=featured_products,
        collections=featured_collections,
        ctas=ctas,
        blogs=blog_links,
        announcement=announcement,
        hero_media=hero_media,
        collection_banners=collection_banners
    )

    homepage_summary = build_homepage_summary(
        site_name=site_name,
        sections=sections,
        featured_products=featured_products,
        featured_collections=featured_collections,
        primary_ctas=primary_ctas,
        features=features,
        hero_media=hero_media,
        announcement=announcement,
        navigation_links=clean_navigation,
    )

    # Warning: media present but no text detected (text likely baked into image/video).
    # If vision already read the slide, it's no longer "unreadable" — only warn
    # when vision ALSO found nothing (or wasn't available).
    hero_warnings = []
    for item in hero_media:
        _vision = item.get("vision") or {}
        _vision_text = (_vision.get("textInImage") or "").strip() if isinstance(_vision, dict) else ""
        if ((item.get("url") or item.get("posterImage"))
                and not item.get("heading")
                and not item.get("textPreview")
                and not _vision_text):
            hero_warnings.append({"type": "media_no_text", "url": item.get("url") or item.get("posterImage")})

    # Roll the vision-read promos up to a single homepage-level list so the AI /
    # frontend can use them without walking every slide. Empty when no image-only
    # promos were found (or vision was off).
    homepage_promos = []
    for _src, _label in ((hero_media, "hero"), (collection_banners, "banner")):
        for _it in (_src or []):
            _v = _it.get("vision") if isinstance(_it, dict) else None
            if isinstance(_v, dict) and (_v.get("textInImage") or _v.get("isPromotional")):
                homepage_promos.append({
                    "placement": _label,
                    "image": _it.get("url") or _it.get("imageUrl") or _it.get("posterImage"),
                    "textInImage": _v.get("textInImage"),
                    "isPromotional": _v.get("isPromotional"),
                    "offer": _v.get("offer"),
                    "headline": _v.get("headline"),
                    "callToAction": _v.get("callToAction"),
                    "meaning": _v.get("meaning"),
                })

    result = {
        "platform": platform,
        "page": {"url": url, "pageType": "homepage"},
        "seo": seo,
        "openGraph": open_graph,
        "navigation": {
            "links": clean_navigation,
            "footerLinks": footer_links
        },
        "content": {
            "siteName": site_name,
            "announcementBar": announcement,
            "heroMedia": hero_media,
            "collectionBanners": collection_banners,
            "sections": sections,
            # Promos read out of image-only banners via vision (offer + meaning).
            "homepagePromos": homepage_promos,
        },
        "ecommerce": {
            "primaryModel": homepage_summary.get("businessModel", {}).get("primaryModel"),
            "featuredProducts": [
                {
                    "title": p.get("title") or p.get("name"),
                    "url": p.get("url"),
                    "price": p.get("price"),
                }
                for p in featured_products[:100]
            ],
            "productTeasers": [],
            "featuredCollections": featured_collections[:10],
            "featuredPrograms": [],
            "hasEcommerceSignals": features.get("hasEcommerceSignals", False),
            "products": [
                {
                    "name": p.get("title") or p.get("name"),
                    "price": p.get("price"),
                    "url": p.get("url"),
                    "availability": p.get("availability"),
                    "category": p.get("category"),
                    "badges": p.get("badges", []),
                }
                for p in featured_products[:100]
            ],
        },
        "products": featured_products[:100],
        "technical": {"finalUrl": url, "responseHeaders": response_headers},
        "source": {
            "extractor": "Shopify Homepage Extractor v2",
            "confidence": confidence,
            "pageTypeValidated": True,
            "pageTypeMismatchReason": None,
        },
        "homepage": {
            **homepage_summary,
            "warnings": hero_warnings,
            "extractionMethod": "dom",
        },
        "metrics": metrics,
        "features": features,
    }

    return result

