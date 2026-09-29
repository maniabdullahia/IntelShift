from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urlunparse
import re
import json
import html as _html  # noqa: F401


def clean_text(text):
    return re.sub(r"\s+", " ", text or "").strip()


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


def normalize_url(raw_url, base_url=None):
    if not raw_url:
        return None

    full_url = urljoin(base_url or "", raw_url)
    parsed = urlparse(full_url)

    cleaned = parsed._replace(
        query="",
        fragment=""
    )

    return urlunparse(cleaned)


def _dollar_currency_from_url(url):
    """Infer regional dollar currency from page URL TLD/locale."""
    u = (url or "").lower()
    if ".com.au" in u or u.endswith(".au") or "/en-au/" in u:
        return "AUD"
    if ".co.nz" in u or ".com.nz" in u or u.endswith(".nz") or "/en-nz/" in u:
        return "NZD"
    if ".ca/" in u or u.endswith(".ca") or "/en-ca/" in u:
        return "CAD"
    if ".com.sg" in u or u.endswith(".sg") or "/en-sg/" in u:
        return "SGD"
    if ".com.hk" in u or u.endswith(".hk") or "/en-hk/" in u:
        return "HKD"
    if ".com.ph" in u or u.endswith(".ph"):
        return "PHP"
    return "USD"


def normalize_price(price_text, page_url=None):

    if not price_text:
        return {
            "raw": None,
            "amount": None,
            "currency": None
        }

    raw = clean_text(price_text)

    if not raw or not re.search(r"\d", raw):
        return {
            "raw": raw,
            "amount": None,
            "currency": None
        }

    currency = None
    raw_lower = raw.lower()

    if "₨" in raw or "rs" in raw_lower or "pkr" in raw_lower:
        currency = "PKR"
    elif "aed" in raw_lower or "د.إ" in raw or "د.ا" in raw:
        currency = "AED"
    elif "sar" in raw_lower or "﷼" in raw:
        currency = "SAR"
    elif "inr" in raw_lower or "₹" in raw:
        currency = "INR"
    elif "€" in raw:
        currency = "EUR"
    elif "$" in raw:
        # $ is ambiguous — infer regional dollar from page URL if available
        currency = _dollar_currency_from_url(page_url)
    elif "£" in raw:
        currency = "GBP"

    cleaned = raw
    cleaned = re.sub(r"current price is:", "", cleaned, flags=re.I)
    cleaned = re.sub(r"original price was:", "", cleaned, flags=re.I)
    cleaned = re.sub(r"(₨|rs\.?|pkr|aed|sar|€|\$|£|﷼|د\.إ|د\.ا)", "", cleaned, flags=re.I)
    cleaned = clean_text(cleaned)

    if currency == "EUR" and re.search(r"\d+,\d{2}", cleaned):
        cleaned = cleaned.replace(".", "")
        cleaned = cleaned.replace(",", ".")
    else:
        cleaned = cleaned.replace(",", "")

    number_match = re.search(r"\d+(?:\.\d+)?", cleaned)

    amount = None

    if number_match:
        try:
            amount = float(number_match.group(0))
            if amount == 0:
                return {
                    "raw": raw,
                    "amount": None,
                    "currency": currency
                }
        except Exception:
            amount = None
    

    return {
        "raw": raw,
        "amount": amount,
        "currency": currency
    }


def _is_zero_price(price_text):
    """Return True for prices that are zero (e.g. ₨0.00, ₨ 0, 0.00 AED)."""
    if not price_text:
        return False
    normed = normalize_price(price_text)
    raw = (price_text or "").strip()
    # Check for explicit zero amount
    if normed.get("amount") == 0.0:
        return True
    # Catch "0" / "0.00" with any currency prefix/suffix
    if re.search(r"^[^\d]*0(?:\.0+)?[^\d]*$", raw.replace(",", "")):
        return True
    return False


def get_product_summary_soup(soup):
    """
    Return a BeautifulSoup scoped to the product summary area only,
    with cart/mini-cart/wishlist/header/sidebar elements removed.
    This prevents cart totals (₨0.00, 0.00 AED) from polluting price extraction.
    """
    _CART_SELECTORS = (
        ".cart, .mini-cart, .widget_shopping_cart, "
        ".woocommerce-mini-cart, .cart-contents, "
        ".shopping-cart, #cart, #mini-cart, "
        "[class*='cart-total'], [class*='cart-subtotal'], "
        "[class*='subtotal'], [class*='order-total'], "
        "[class*='checkout'], [class*='wishlist'], "
        "[class*='mini-cart'], [class*='minicart'], "
        "[class*='account'], [class*='login'], "
        "header, nav, footer, aside, "
        ".site-header, .main-header, .header-area, "
        ".widget_product_search, .woocommerce-widget-layered-nav"
    )
    # Prefer explicit summary containers
    for selector in [
        ".summary.entry-summary",
        ".summary",
        ".entry-summary",
    ]:
        node = soup.select_one(selector)
        if node:
            scoped = BeautifulSoup(str(node), "lxml")
            for bad in scoped.select(_CART_SELECTORS):
                bad.decompose()
            return scoped

    # Fallback: main product node stripped of cart zones
    product_node = (
        soup.select_one(".product")
        or soup.select_one(".single-product")
        or soup.select_one("main")
        or soup.body
        or soup
    )
    scoped = BeautifulSoup(str(product_node), "lxml")
    for bad in scoped.select(_CART_SELECTORS):
        bad.decompose()
    return scoped


def extract_price_from_text(text):
    text = clean_text(text)

    if not text:
        return None

    variable_price_phrases = [
        "price varies",
        "contact for price",
        "call for price",
        "request price",
        "ask for price"
    ]

    if any(phrase in text.lower() for phrase in variable_price_phrases):
        return None

    # Strip "per piece / per unit / per kg" qualifiers before matching
    text = re.sub(r"\s+per\s+(?:piece|unit|item|kg|g|ml|l|pair|pack|set)\b", "", text, flags=re.I)

    patterns = [
        r"Current price is:\s*(₨|Rs\.?|PKR)\s*([\d,]+(?:\.\d{2})?)",
        r"Current price is:\s*(\$|£|€)\s*([\d,]+(?:[,.]\d{2})?)",
        r"(₨|Rs\.?|PKR)\s*([\d,]+(?:\.\d{2})?)\s*Current price",
        r"(\$|£|€)\s*([\d,]+(?:[,.]\d{2})?)\s*Current price",
        r"(₨|Rs\.?|PKR)\s*([\d,]+(?:\.\d{2})?)",
        r"([\d,]+(?:\.\d{2})?)\s*(AED|aed)",
        r"(AED|aed)\s*([\d,]+(?:\.\d{2})?)",
        r"(\$|£|€)\s*([\d,]+(?:[,.]\d{2})?)",
        r"([\d,]+(?:[,.]\d{2})?)\s*(€)"
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.I)

        if match:
            value = clean_text(match.group(0))

            if re.search(r"\d", value):
                return value

    return None


def extract_pricing_details(text, fallback_price=None, page_url=None):
    text = clean_text(text)

    original_price = None
    current_price = None
    discount_percent = None

    original_patterns = [
        r"Original price was:\s*(₨|Rs\.?|PKR|\$|£|€)\s*([\d,]+(?:[,.]\d{2})?)",
        r"(₨|Rs\.?|PKR|\$|£|€)\s*([\d,]+(?:[,.]\d{2})?)\s*Original price was"
    ]

    current_patterns = [
        r"Current price is:\s*(₨|Rs\.?|PKR|\$|£|€)\s*([\d,]+(?:[,.]\d{2})?)",
        r"(₨|Rs\.?|PKR|\$|£|€)\s*([\d,]+(?:[,.]\d{2})?)\s*Current price"
    ]

    discount_match = re.search(
        r"(save|off|discount|sale|up to)[^\d]{0,20}(\d+(?:\.\d+)?)\s*%",
        text,
        re.I
    )

    if discount_match:
        try:
            discount_percent = float(discount_match.group(2))
        except Exception:
            discount_percent = None

    for pattern in original_patterns:
        match = re.search(pattern, text, re.I)

        if match:
            original_price = clean_text(match.group(0))
            break

    for pattern in current_patterns:
        match = re.search(pattern, text, re.I)

        if match:
            current_price = clean_text(match.group(0))
            break

    if not current_price:
        current_price = fallback_price or extract_price_from_text(text)

    original_normalized = normalize_price(original_price, page_url=page_url)
    current_normalized = normalize_price(current_price, page_url=page_url)
    
    if current_normalized.get("amount") is None:
        current_price = None

    if (
        discount_percent is None
        and original_normalized.get("amount")
        and current_normalized.get("amount")
        and original_normalized["amount"] > current_normalized["amount"]
    ):
        try:
            discount_percent = round(
                (
                    (original_normalized["amount"] - current_normalized["amount"])
                    / original_normalized["amount"]
                ) * 100,
                2
            )
        except Exception:
            discount_percent = None

    on_sale = (
        original_normalized.get("amount") is not None
        and current_normalized.get("amount") is not None
        and original_normalized["amount"] > current_normalized["amount"]
    )

    if not on_sale:
        discount_percent = None

    return {
        "currentPrice": current_price,
        "currentPriceNormalized": current_normalized,
        "originalPrice": original_price,
        "originalPriceNormalized": original_normalized,
        "discountPercent": discount_percent,
        "onSale": on_sale
    }


def is_valid_product_image(url, alt=""):
    url_lower = (url or "").lower()
    alt_lower = (alt or "").lower()

    blocked_keywords = [
        "logo",
        "icon",
        "banner",
        "review",
        "reviews",
        "payment",
        "shipping",
        "trustpilot",
        "badge",
        "etsy",
        "news",
        "facebook",
        "instagram",
        "placeholder",
        "avatar",
        "secured",
        "safe-checkout",
        "checkout",
        "paypal",
        "visa",
        "mastercard",
        "featured-in"
    ]

    blocked_extensions = [
        ".svg",
        ".gif"
    ]

    if not url_lower:
        return False

    if url_lower.startswith("data:image"):
        return False

    if any(k in url_lower for k in blocked_keywords):
        return False

    if any(k in alt_lower for k in blocked_keywords):
        return False

    if any(url_lower.endswith(ext) for ext in blocked_extensions):
        return False

    return True


def extract_json_ld_items(soup):
    json_ld_items = []

    for script in soup.find_all(
        "script",
        attrs={"type": "application/ld+json"}
    ):
        try:
            raw = script.string or script.get_text()

            if not raw:
                continue

            parsed = json.loads(raw)

            if isinstance(parsed, list):
                json_ld_items.extend(parsed)
            else:
                json_ld_items.append(parsed)

        except Exception:
            continue

    return json_ld_items


def flatten_json_ld_items(item):
    output = []

    if isinstance(item, list):
        for child in item:
            output.extend(flatten_json_ld_items(child))

    elif isinstance(item, dict):
        output.append(item)

        graph = item.get("@graph")

        if isinstance(graph, list):
            for child in graph:
                output.extend(flatten_json_ld_items(child))

    return output


def extract_rating_from_schema(item):
    aggregate = item.get("aggregateRating")

    if not isinstance(aggregate, dict):
        return {
            "ratingValue": None,
            "reviewCount": None,
            "source": None
        }

    rating_value = aggregate.get("ratingValue")
    review_count = (
        aggregate.get("reviewCount")
        or aggregate.get("ratingCount")
    )

    try:
        rating_value = float(rating_value) if rating_value is not None else None
    except Exception:
        rating_value = None

    try:
        review_count = int(review_count) if review_count is not None else None
    except Exception:
        review_count = None

    return {
        "ratingValue": rating_value,
        "reviewCount": review_count,
        "source": "jsonld"
    }


def extract_product_from_json_ld(json_ld_items, base_url):
    flattened = []

    for item in json_ld_items:
        flattened.extend(flatten_json_ld_items(item))

    for item in flattened:
        item_type = item.get("@type")

        if isinstance(item_type, list):
            item_types = [str(t).lower() for t in item_type]
        else:
            item_types = [str(item_type).lower()] if item_type else []

        if "product" not in item_types:
            continue

        name = clean_text(item.get("name"))
        product_url = normalize_url(item.get("url"), base_url)

        image = item.get("image")

        if isinstance(image, list):
            first_image = image[0] if image else None

            if isinstance(first_image, dict):
                image = first_image.get("url") or first_image.get("contentUrl")
            else:
                image = first_image

        elif isinstance(image, dict):
            image = image.get("url") or image.get("contentUrl")

        image = normalize_url(image, base_url) if image else None

        offers = item.get("offers", {})

        if isinstance(offers, list):
            offers = offers[0] if offers else {}

        price_text_raw = None
        price_normalized = None
        currency = None
        availability = None
        price_valid_until = None

        if isinstance(offers, dict):
            offer_type = (offers.get("@type") or "").strip()
            currency = offers.get("priceCurrency")
            availability = offers.get("availability")
            price_valid_until = offers.get("priceValidUntil")

            if offer_type == "AggregateOffer":
                # Build a price range string from lowPrice / highPrice
                low = offers.get("lowPrice")
                high = offers.get("highPrice")
                if low is not None:
                    try:
                        low_f = float(str(low).replace(",", ""))
                        high_f = float(str(high).replace(",", "")) if high is not None else low_f
                    except (ValueError, TypeError):
                        low_f = high_f = None
                    if low_f is not None:
                        cur = currency or ""
                        if cur == "PKR":
                            price_text_raw = f"₨ {low_f:.2f} – ₨ {high_f:.2f}"
                        elif cur == "USD":
                            price_text_raw = f"$ {low_f:.2f} – $ {high_f:.2f}"
                        elif cur == "GBP":
                            price_text_raw = f"£ {low_f:.2f} – £ {high_f:.2f}"
                        elif cur == "EUR":
                            price_text_raw = f"{low_f:.2f} € – {high_f:.2f} €"
                        else:
                            # e.g. "5.00 AED – 77.00 AED"
                            price_text_raw = f"{low_f:.2f} {cur} – {high_f:.2f} {cur}".strip()
                        price_normalized = {
                            "amount": low_f,
                            "min": low_f,
                            "max": high_f,
                            "currency": cur or None,
                            "raw": price_text_raw,
                        }
            else:
                price = offers.get("price")
                if price is not None:
                    if currency == "USD":
                        price_text_raw = f"$ {price}"
                    elif currency == "GBP":
                        price_text_raw = f"£ {price}"
                    elif currency == "EUR":
                        price_text_raw = f"{price} €"
                    elif currency == "PKR":
                        price_text_raw = f"₨ {price}"
                    elif currency == "AED":
                        price_text_raw = f"{price} AED"
                    else:
                        price_text_raw = str(price)

        if price_normalized is None:
            price_normalized = normalize_price(price_text_raw)
            if currency and not price_normalized.get("currency"):
                price_normalized["currency"] = currency

        schema_rating = extract_rating_from_schema(item)

        additional_properties = []

        for prop in item.get("additionalProperty", []) or []:
            if isinstance(prop, dict):
                additional_properties.append({
                    "name": clean_text(prop.get("name")),
                    "value": clean_text(prop.get("value"))
                })

        # Clean HTML entities from JSON-LD description
        raw_desc = item.get("description") or ""
        jsonld_description = None
        if raw_desc:
            decoded = _html.unescape(_html.unescape(str(raw_desc)))
            decoded = re.sub(r"&nbsp;|\xa0", " ", decoded)
            decoded = clean_text(re.sub(r"[\r\n]+", " ", decoded))
            if decoded and len(decoded) > 20:
                jsonld_description = decoded[:3000]

        # Extract SKU — may be numeric (WooCommerce uses post ID as SKU in JSON-LD)
        _jld_sku_raw = item.get("sku")
        _jld_sku = str(_jld_sku_raw).strip() if _jld_sku_raw is not None else None
        if _jld_sku and _jld_sku.upper() in ("N/A", "SKU", "NONE", ""):
            _jld_sku = None

        return {
            "name": name,
            "url": product_url,
            "description": jsonld_description,
            "sku": _jld_sku,
            "price": price_text_raw,
            "priceTextRaw": price_text_raw,
            "priceNormalized": price_normalized,
            "image": image,
            "availability": availability,
            "priceValidUntil": price_valid_until,
            "rating": schema_rating,
            "additionalProperties": additional_properties,
            "source": "jsonld"
        }

    return None


def extract_images(soup, base_url):
    images = []

    product_scope = (
        soup.select_one(".woocommerce-product-gallery")
        or soup.select_one(".product")
        or soup.select_one(".single-product")
        or soup.select_one("main")
        or soup
    )

    selectors = [
        ".woocommerce-product-gallery img",
        ".product-gallery img",
        ".product-images img",
        ".woocommerce-product-gallery__image img",
        ".summary img"
    ]

    for selector in selectors:
        for img in product_scope.select(selector):
            src = (
                img.get("data-large_image")
                or img.get("data-src")
                or img.get("data-lazy-src")
                or img.get("data-original")
                or img.get("src")
            )

            alt = clean_text(img.get("alt"))

            if not src:
                continue

            src = normalize_url(src, base_url)

            if not is_valid_product_image(src, alt):
                continue

            images.append({
                "url": src,
                "alt": alt
            })

    return unique_items(images, "url")[:20]


def extract_breadcrumbs(soup, base_url):
    breadcrumbs = []

    for a in soup.select(
        ".woocommerce-breadcrumb a, .breadcrumb a, .breadcrumbs a, nav.breadcrumb a"
    ):
        text = clean_text(a.get_text(" "))
        href = a.get("href")

        if not text or not href:
            continue

        if text.lower() in ["en", "pl", "de", "fr"]:
            continue

        breadcrumbs.append({
            "text": text,
            "url": normalize_url(href, base_url)
        })

    return unique_items(breadcrumbs, "url")


def extract_categories(soup, base_url):
    categories = []

    product_meta = soup.select_one(".product_meta, .posted_in")

    scope = product_meta if product_meta else soup

    for a in scope.select(
        "a[rel='tag'], .posted_in a, .product_meta a, a[href*='/product-category/']"
    ):
        text = clean_text(a.get_text(" "))
        href = a.get("href")

        if not text or not href:
            continue

        text_lower = text.lower()

        if text_lower in [
            "tag",
            "category",
            "en",
            "pl",
            "de",
            "fr",
            "my account",
            "cart",
            "checkout"
        ]:
            continue

        categories.append({
            "text": text,
            "url": normalize_url(href, base_url)
        })

    return unique_items(categories, "url")[:20]


def clean_section_text(text):
    text = clean_text(text)
    text = re.sub(r"^\+\s*", "", text)
    return clean_text(text)


# ---------------------------------------------------------------------------
# Section heading detection (case-SENSITIVE — avoids matching "ingredients"
# mid-sentence, e.g. "contains 3 active ingredients").
# Headings in WooCommerce accordion pages are always ALL-CAPS.
# ---------------------------------------------------------------------------
_SECTION_HEADING_RE = re.compile(
    r"(?<!\w)"
    r"(DESCRIPTION|DECRIPTION|HOW TO USE|PRODUCT DNA"
    r"|ADDITIONAL INFORMATION|CUSTOMER REVIEWS|REVIEWS"
    r"|RELATED PRODUCTS"
    r"|KEY BENEFITS|BENEFITS"
    r"|ACTIVE INGREDIENTS|INGREDIENTS|INCI"
    r"|FEATURES|TECHNOLOGY|CLAIMS|WARNINGS|SUITABLE FOR)"
    r"(?!\w)"
    r"\s*[+:]?\s*"
)

# Maps output field names to the UPPERCASE heading(s) that populate them.
# Order matters: first match wins.
_SECTION_FIELD_MAP = [
    ("description",           ["DESCRIPTION", "DECRIPTION"]),
    ("howToUse",              ["HOW TO USE"]),
    ("ingredients",           ["INGREDIENTS"]),
    ("productDNA",            ["PRODUCT DNA"]),
    ("benefits",              ["KEY BENEFITS", "BENEFITS"]),
    ("features",              ["FEATURES"]),
    ("activeIngredients",     ["ACTIVE INGREDIENTS"]),
    ("technology",            ["TECHNOLOGY"]),
    ("claims",                ["CLAIMS"]),
    ("warnings",              ["WARNINGS"]),
    ("suitableFor",           ["SUITABLE FOR"]),
    ("additionalInformation", ["ADDITIONAL INFORMATION"]),
    ("reviews",               ["REVIEWS", "CUSTOMER REVIEWS"]),
]

# Fields whose content should be returned as a list rather than a raw string.
_LIST_SECTION_FIELDS = {"benefits", "features", "activeIngredients"}


def _text_to_list(text, max_items=20):
    """
    Convert a flat section string into a list of items.
    Tries (in order): bullet characters, pipe/semicolon delimiters, sentence split.
    Falls back to a single-item list when no list structure is detected.
    """
    if not text:
        return []

    # Bullet / symbol delimiters that survive HTML→text
    if re.search(r"[•◦▸▷→✓✔➤★]", text):
        parts = re.split(r"\s*[•◦▸▷→✓✔➤★]\s*", text)
        items = [clean_text(p) for p in parts if 5 < len(clean_text(p)) <= 400]
        if len(items) > 1:
            return items[:max_items]

    # Pipe or semicolon delimited
    if re.search(r"[|;]", text):
        parts = re.split(r"\s*[|;]\s*", text)
        items = [clean_text(p) for p in parts if 5 < len(clean_text(p)) <= 400]
        if len(items) > 1:
            return items[:max_items]

    # Sentence split — only treat as a list when sentences are short (≤ 200 chars each)
    sentences = re.split(r"\.\s+(?=[A-Z])", text)
    short = [clean_text(s) for s in sentences if 5 < len(clean_text(s)) <= 200]
    if len(short) > 1:
        return short[:max_items]

    # No list structure — return as a single item
    return [text[:400]] if text else []


def _split_page_sections(page_text):
    """
    Split page_text into named sections by detecting standalone UPPERCASE headings.
    Uses case-SENSITIVE matching so lowercase occurrences of section words inside
    body text (e.g. 'active ingredients') are never treated as headings.
    When a heading appears more than once, the occurrence with the most content wins.
    INCI content is merged into INGREDIENTS (or ACTIVE INGREDIENTS as fallback).
    """
    boundaries = [
        (m.start(), m.group(1), m.end())
        for m in _SECTION_HEADING_RE.finditer(page_text)
    ]

    if not boundaries:
        return {}

    sections = {}
    for i, (_, heading, content_start) in enumerate(boundaries):
        end = boundaries[i + 1][0] if i + 1 < len(boundaries) else len(page_text)
        content = clean_section_text(page_text[content_start:end])
        # Keep whichever occurrence has the most content
        if len(content) > len(sections.get(heading, "")):
            sections[heading] = content

    # Merge INCI list into INGREDIENTS (or ACTIVE INGREDIENTS if that's all we have)
    inci = sections.pop("INCI", "")
    if inci:
        if "INGREDIENTS" in sections:
            if inci not in sections["INGREDIENTS"]:
                sections["INGREDIENTS"] = sections["INGREDIENTS"] + " " + inci
        elif "ACTIVE INGREDIENTS" in sections:
            if inci not in sections["ACTIVE INGREDIENTS"]:
                sections["ACTIVE INGREDIENTS"] = sections["ACTIVE INGREDIENTS"] + " " + inci
        else:
            sections["INGREDIENTS"] = inci

    return sections


# ---------------------------------------------------------------------------
# Generic DOM-based section extractor (Task #98).
# Detects headings in ANY case/style (h1-h6, dt, summary, standalone
# strong/b) and maps them to canonical product fields, independent of
# platform, theme, or product category. This complements (does not replace)
# _split_page_sections, which only handles ALL-CAPS accordion text.
# ---------------------------------------------------------------------------

_GENERIC_HEADING_MAP = {
    "features": "features",
    "key features": "features",
    "product features": "features",
    "highlights": "features",
    "key highlights": "features",

    "benefits": "benefits",
    "key benefits": "benefits",
    "advantages": "benefits",
    "why buy": "benefits",
    "why choose": "benefits",
    "why choose this": "benefits",
    "why you'll love it": "benefits",
    "why shop with us": "benefits",

    "materials": "materials",
    "material": "materials",
    "materials & care": "materials",
    "fabric": "materials",
    "fabric & care": "materials",
    "fabric and care": "materials",
    "composition": "materials",
    "material composition": "materials",

    "included": "includedItems",
    "what's included": "includedItems",
    "whats included": "includedItems",
    "in the box": "includedItems",
    "package includes": "includedItems",
    "package contents": "includedItems",
    "bundle includes": "includedItems",
    "this bundle includes": "includedItems",

    "technical data": "technicalSpecifications",
    "technical specifications": "technicalSpecifications",
    "technical specification": "technicalSpecifications",
    "specifications": "technicalSpecifications",
    "specification": "technicalSpecifications",
    "specs": "technicalSpecifications",

    "compatible vehicles": "compatibility",
    "vehicle fitment": "compatibility",
    "fitment": "compatibility",
    "compatibility": "compatibility",

    "artist": "artist",
    "about the artist": "artist",
    "meet the artist": "artist",
    "designed by": "artist",

    "care instructions": "careInstructions",
    "care guide": "careInstructions",
    "fabric care": "careInstructions",
    "washing instructions": "careInstructions",
    "product care": "careInstructions",

    "shipping & returns": "shippingInfo",
    "shipping and returns": "shippingInfo",
    "shipping information": "shippingInfo",
    "shipping & delivery": "shippingInfo",
    "shipping and delivery": "shippingInfo",
    "delivery & returns": "shippingInfo",
    "returns policy": "shippingInfo",
    "returns & exchanges": "shippingInfo",
}

# Fields whose content should be returned as a list of items
_GENERIC_LIST_FIELDS = {
    "features", "benefits", "materials", "includedItems",
    "technicalSpecifications", "compatibility",
}

_HEADING_TAGS = ("h1", "h2", "h3", "h4", "h5", "h6")
_INLINE_HEADING_TAGS = ("strong", "b", "dt", "summary")
_CONTENT_TAGS = ("li", "p", "td", "dd", "span", "div")


def _normalize_heading_text(text):
    text = clean_text(text)
    text = text.replace("’", "'").replace("‘", "'")
    text = text.lower()
    text = re.sub(r"[:+\-–—]+$", "", text).strip()
    text = re.sub(r"\s+", " ", text)
    return text


def extract_generic_sections(soup):
    """
    Walk all heading-like elements (h1-h6, dt, summary, standalone strong/b)
    and capture the content that follows each one, up to the next heading.

    Returns {canonical_field: content}, where content is a list (for
    list-type fields) or a cleaned string. First match wins per field.
    """
    sections = {}

    candidates = []
    for tag in soup.find_all(_HEADING_TAGS + _INLINE_HEADING_TAGS):
        raw_text = clean_text(tag.get_text(" "))
        if not raw_text or len(raw_text) > 60:
            continue

        # For inline tags (strong/b), only treat as a heading if it is
        # essentially the whole content of its parent block (not a bolded
        # phrase inside a longer sentence).
        if tag.name in ("strong", "b"):
            parent_text = clean_text(tag.parent.get_text(" ")) if tag.parent else raw_text
            if parent_text != raw_text:
                continue

        norm = _normalize_heading_text(raw_text)
        field = _GENERIC_HEADING_MAP.get(norm)
        if not field:
            continue

        candidates.append((tag, field))

    if not candidates:
        return sections

    heading_tag_ids = {id(tag) for tag, _ in candidates}

    for tag, field in candidates:
        if field in sections:
            continue  # first (highest) occurrence wins

        list_items = []
        text_parts = []
        char_budget = 3000
        steps = 0

        for el in tag.find_all_next():
            steps += 1
            if steps > 200 or char_budget <= 0:
                break

            # Stop at the next heading element, or the next matched
            # generic heading (even if it's an inline strong/b).
            if el.name in _HEADING_TAGS:
                break
            if id(el) in heading_tag_ids and el is not tag:
                break

            if el.name not in _CONTENT_TAGS:
                continue

            if el.name == "li":
                item_text = clean_text(el.get_text(" "))
                if item_text and item_text not in list_items:
                    list_items.append(item_text)
                    char_budget -= len(item_text)
            elif not el.find(["li", "p", "div", "table", "dd"]):
                item_text = clean_text(el.get_text(" "))
                if item_text and 1 < len(item_text) <= 500:
                    text_parts.append(item_text)
                    char_budget -= len(item_text)

        if field in _GENERIC_LIST_FIELDS:
            if list_items:
                sections[field] = list_items[:20]
            elif text_parts:
                sections[field] = _text_to_list(" ".join(text_parts))
        else:
            combined = clean_text(" ".join(text_parts) or " ".join(list_items))
            if combined:
                sections[field] = combined[:2000]

    return sections


def extract_tabs(soup):
    tabs = {}

    # 1. WooCommerce structured HTML tab panels (highest confidence)
    possible_sections = {
        "description": [
            "#tab-description",
            ".woocommerce-Tabs-panel--description",
            "[id='description']"
        ],
        "additionalInformation": [
            "#tab-additional_information",
            ".woocommerce-Tabs-panel--additional_information"
        ],
        "reviews": [
            "#tab-reviews",
            ".woocommerce-Tabs-panel--reviews"
        ]
    }

    for key, selectors in possible_sections.items():
        for selector in selectors:
            node = soup.select_one(selector)

            if node:
                text = clean_section_text(node.get_text(" "))

                if text:
                    tabs[key] = text[:6000]
                    break

    # 2. Accordion / flat-text extraction via section boundary splitter
    page_text = clean_text(soup.get_text(" "))
    section_map = _split_page_sections(page_text)

    for field, headings in _SECTION_FIELD_MAP:
        if field in tabs and tabs[field]:
            continue
        for heading in headings:
            content = section_map.get(heading, "")
            if content:
                if field in _LIST_SECTION_FIELDS:
                    tabs[field] = _text_to_list(content)
                else:
                    tabs[field] = content[:6000]
                break

    return tabs


def extract_variants_and_options(soup):
    options = []

    blocked_option_names = [
        "product_cat",
        "orderby",
        "filter",
        "rating",
        "min_price",
        "max_price",
        "quantity",
        "add-to-cart"
    ]

    allowed_name_prefixes = [
        "attribute_",
        "pa_",
        "variation",
        "size",
        "color",
        "colour",
        "capacity",
        "flavour",
        "flavor"
    ]

    main_product_scope = (
        soup.select_one("form.cart")
        or soup.select_one(".summary.entry-summary")
        or soup.select_one(".entry-summary")
        or soup.select_one(".single-product .product")
        or soup
    )

    for select in main_product_scope.select(
        "form.variations_form select, table.variations select, .variations select"
    ):
        option_name = clean_text(
            select.get("name")
            or select.get("id")
            or ""
        )

        option_name_lower = option_name.lower()

        if not option_name:
            continue

        if option_name_lower in blocked_option_names:
            continue

        if not any(prefix in option_name_lower for prefix in allowed_name_prefixes):
            continue

        values = []

        for option in select.select("option"):
            text = clean_text(option.get_text(" "))
            value = clean_text(option.get("value"))

            if not text:
                continue

            if text.lower() in [
                "choose an option",
                "select option",
                "select",
                "clear"
            ]:
                continue

            values.append({
                "text": text,
                "value": value
            })

        if values:
            options.append({
                "name": option_name,
                "values": values
            })

    deduped = []
    seen = set()

    for option in options:
        key = (
            option.get("name"),
            json.dumps(option.get("values", []), sort_keys=True)
        )

        if key in seen:
            continue

        seen.add(key)
        deduped.append(option)

    return deduped[:20]


_RELATED_HEADING_RE = re.compile(
    r"^(related products?|you (?:may|might) also like|similar products?"
    r"|customers also (?:bought|viewed)|people also (?:bought|viewed)"
    r"|recommended( products?)?|you may like|more from this collection"
    r"|complete the look|frequently bought together|also available in)$"
)

# Wishlist/cart/account/compare links that should never be treated as
# related-product links or names.
_NON_RELATED_LINK_RE = re.compile(
    r"^(add to|wishlist|compare|quick view|quickview|cart|checkout"
    r"|my account|view cart|login|register|sign in)\b", re.I
)


def _parse_related_card(node, base_url):
    """
    Extract {name, url, price, priceNormalized} from a product-card-like
    node. Returns None if no usable name/link is found.
    """
    text = clean_text(node.get_text(" "))

    if len(text) < 10:
        return None

    link = node.select_one("a[href]")

    if not link:
        return None

    name = None

    for selector in [
        ".woocommerce-loop-product__title",
        ".product-title",
        ".product-name",
        "h2",
        "h3",
        "a[title]"
    ]:
        found = node.select_one(selector)

        if found:
            if selector == "a[title]":
                name = clean_text(found.get("title"))
            else:
                name = clean_text(found.get_text(" "))

            if name:
                break

    if not name:
        # Prefer non-action links (skip "Add to wishlist", "Add to compare" etc.)
        for a in node.select("a[href]"):
            a_text = clean_text(a.get_text(" "))
            if a_text and not _NON_RELATED_LINK_RE.search(a_text):
                name = a_text
                link = a
                break
        if not name:
            name = clean_text(link.get_text(" "))

    # Strip action phrases and junk
    name = re.sub(
        r"\b(add to cart|add to wishlist|add to compare|add to"
        r"|quick view|quickview|wishlist|compare|choose an option"
        r"|read more|check|select options|clear|out of stock|in stock)\b",
        " ", name, flags=re.I
    )

    # Strip price text that leaked into the name
    name = re.sub(r"\s*[₨$€£﷼]\s*[\d,]+(?:[.,]\d{1,3})?(?:\s*[₨$€£﷼]\s*[\d,]+(?:[.,]\d{1,3})?)*", " ", name)

    name = clean_text(name)

    # Skip if name is too short, junk, or itself an action phrase
    if not name or len(name) < 3:
        return None
    if _NON_RELATED_LINK_RE.search(name):
        return None

    href = link.get("href") or ""
    if not href or href.startswith("#"):
        return None
    if re.search(
        r"/(cart|checkout|my-account|wishlist|compare|wp-login)\b",
        href, re.I
    ):
        return None

    price = extract_price_from_text(text)

    return {
        "name": name,
        "url": normalize_url(href, base_url),
        "price": price,
        "priceNormalized": normalize_price(price)
    }


def _find_related_section_cards(soup, base_url):
    """
    Fallback recovery: locate a heading like 'You May Also Like' /
    'Related Products' / 'Customers Also Bought' and extract product
    cards from the container that follows it.
    """
    found = []

    for tag in soup.find_all(("h1", "h2", "h3", "h4", "h5", "h6", "strong", "b", "span", "div")):
        heading_text = clean_text(tag.get_text(" "))
        if not heading_text or len(heading_text) > 60:
            continue
        if not _RELATED_HEADING_RE.match(_normalize_heading_text(heading_text)):
            continue

        # Find the nearest following container with multiple link-bearing children
        container = tag.find_next(["ul", "ol", "div"])
        steps = 0
        while container and steps < 10:
            steps += 1
            cards = container.find_all(["li", "div", "article"], recursive=True)
            cards = [
                c for c in cards
                if c.select_one("a[href]") and len(clean_text(c.get_text(" "))) >= 10
            ]
            if len(cards) >= 2:
                for card in cards:
                    parsed = _parse_related_card(card, base_url)
                    if parsed:
                        found.append(parsed)
                if found:
                    return found
            container = container.find_next(["ul", "ol", "div"])

    return found


def extract_related_products(soup, base_url):
    related = []

    related_nodes = soup.select(
        """
        .related.products li.product,
        .upsells.products li.product,
        .cross-sells li.product,
        [class*='related'] li.product,
        [class*='related'] .product
        """
    )

    for node in related_nodes:
        parsed = _parse_related_card(node, base_url)
        if parsed:
            related.append(parsed)

    related = unique_items(related, "url")

    # Recovery fallback: search for "You May Also Like" / "Related
    # Products" / etc. headings when the structured selectors found nothing.
    if not related:
        recovered = _find_related_section_cards(soup, base_url)
        related = unique_items(recovered, "url")

    return related[:20]


def extract_reviews_summary(soup, jsonld_product=None):
    rating_value = None
    review_count = None
    source = None

    if jsonld_product and jsonld_product.get("rating"):
        rating = jsonld_product.get("rating", {})

        if rating.get("ratingValue") is not None:
            rating_value = rating.get("ratingValue")
            source = "jsonld"

        if rating.get("reviewCount") is not None:
            review_count = rating.get("reviewCount")
            source = "jsonld"

    if rating_value is None:
        rating_node = soup.select_one(
            ".woocommerce-product-rating .star-rating, .star-rating"
        )

        if rating_node:
            rating_text = clean_text(
                rating_node.get("aria-label")
                or rating_node.get("title")
                or rating_node.get_text(" ")
            )

            match = re.search(r"([\d.]+)\s*out of\s*5", rating_text, re.I)

            if match:
                try:
                    rating_value = float(match.group(1))
                    source = source or "dom"
                except Exception:
                    pass

    if review_count is None:
        count_node = soup.select_one(
            ".woocommerce-review-link, .review-count, [class*='review-count']"
        )

        if count_node:
            count_text = clean_text(count_node.get_text(" "))
            match = re.search(r"(\d+)", count_text)

            if match:
                try:
                    review_count = int(match.group(1))
                    source = source or "dom"
                except Exception:
                    pass

    return {
        "ratingValue": rating_value,
        "reviewCount": review_count,
        "source": source
    }


def extract_stock(soup):
    stock_text = None

    for selector in [
        ".stock",
        ".availability",
        ".product-stock",
        "[class*='stock']"
    ]:
        node = soup.select_one(selector)

        if node:
            stock_text = clean_text(node.get_text(" "))

            if stock_text:
                break

    in_stock = None

    if stock_text:
        stock_lower = stock_text.lower()

        if "out of stock" in stock_lower or "sold out" in stock_lower:
            in_stock = False
        elif "in stock" in stock_lower:
            in_stock = True

    return stock_text, in_stock


# ── Description fallback chain ─────────────────────────────────────────────────

def _extract_description_fallback(soup, jsonld_product):
    """
    Fallback when extract_tabs found no description:
    1. JSON-LD Product.description (already decoded and stored in jsonld_product)
    2. WooCommerce short-description / [itemprop=description]
    3. og:description
    4. meta description
    """
    if jsonld_product:
        desc = jsonld_product.get("description")
        if desc and len(desc) > 20:
            return desc

    for sel in [
        ".woocommerce-product-details__short-description",
        ".product-short-description",
        ".short-description",
        "[itemprop='description']",
    ]:
        node = soup.select_one(sel)
        if node:
            text = clean_text(node.get_text(" "))
            if text and len(text) > 30:
                return text[:3000]

    og = soup.find("meta", attrs={"property": "og:description"})
    if og:
        desc = clean_text(og.get("content", ""))
        if desc and len(desc) > 20:
            return desc[:3000]

    meta = soup.find("meta", attrs={"name": "description"})
    if meta:
        desc = clean_text(meta.get("content", ""))
        if desc and len(desc) > 20:
            return desc[:3000]

    return None


# ── Features from DOM <li> and ALL-CAPS headings ────────────────────────────────

def _extract_features_from_content(soup, description_text):
    """
    Extract feature list from:
    1. <li> items in description/content area (e.g. s.json bullet list)
    2. ALL-CAPS heading + sentence pattern (e.g. BWT SIMPLE INSTALLATION ...)
    """
    features = []

    for sel in [
        ".woocommerce-Tabs-panel--description",
        "#tab-description",
        ".woocommerce-product-details__short-description",
        ".product-short-description",
        ".short-description",
        ".entry-content",
    ]:
        area = soup.select_one(sel)
        if not area:
            continue
        for li in area.find_all("li"):
            text = clean_text(li.get_text(" "))
            if 5 < len(text) <= 300 and not re.search(
                r"\b(add to|cart|checkout|wishlist|shipping|returns?|size guide)\b",
                text, re.I
            ):
                features.append(text)
        if features:
            return features[:20]

    # ALL-CAPS heading + sentence (BWT-style: "SIMPLE INSTALLATION All our…")
    if description_text:
        _caps = re.compile(r"(?<![a-z])([A-Z][A-Z ]{3,40}[A-Z])\s+([A-Z][^.!?]{20,250}[.!?])")
        _noise = re.compile(r"\b(ADD TO|OUT OF STOCK|RELATED|CUSTOMER REVIEWS?|WISHLIST|COMPARE)\b")
        for m in _caps.finditer(description_text):
            heading = clean_text(m.group(1))
            sentence = clean_text(m.group(2))
            if not _noise.search(heading):
                features.append(f"{heading}: {sentence}")
        if features:
            return features[:20]

    return features


# ── Product category detection ─────────────────────────────────────────────────

def _detect_product_category(name, product_text):
    """Return 'digital_product' | 'artwork' | 'automotive' | 'industrial' | None."""
    combined = ((name or "") + " " + (product_text or "")).lower()

    dig_kw = ["download", "bundle", "template", "preset", "motion", "asset",
              "plugin", "software", "license", "licence", "mockup"]
    if sum(1 for k in dig_kw if k in combined) >= 2:
        return "digital_product"

    art_kw = ["art paper print", "digital download", "wall art", "poster",
              "art print", "luster photo paper", "print on premium", "paper print"]
    if sum(1 for k in art_kw if k in combined) >= 2:
        return "artwork"

    auto_kw = ["compatible vehicles", "vehicle fitment", "fitment",
               "make model year"]
    if any(k in combined for k in auto_kw):
        return "automotive"

    ind_kw = ["heat pump", "inverter", "capacity", "kw", "hvac",
              "equipment", "machinery", "industrial"]
    if sum(1 for k in ind_kw if k in combined) >= 3:
        return "industrial"

    return None


# ── Digital product data ───────────────────────────────────────────────────────

def _extract_digital_product_data(product_text, json_ld_items):
    """
    For digital products: extract includedItems and licenseOptions.
    Prefers raw JSON-LD (has newlines) for included items.
    """
    included_items = []
    license_options = []

    # Parse newline-separated items from raw JSON-LD description
    raw_desc = ""
    for item in json_ld_items:
        for flat in flatten_json_ld_items(item):
            if "product" in str(flat.get("@type", "")).lower():
                raw_desc = flat.get("description") or ""
                break
        if raw_desc:
            break

    if raw_desc and ("\n" in raw_desc or "\r" in raw_desc):
        lines = [l.strip() for l in re.split(r"[\r\n]+", raw_desc)]
        in_includes = False
        for line in lines:
            clean_line = _html.unescape(_html.unescape(line))
            clean_line = re.sub(r"&nbsp;|\xa0", " ", clean_line).strip()
            if re.search(r"bundle includes?|what.?s included|includes?:", clean_line, re.I):
                in_includes = True
                continue
            if in_includes:
                if not clean_line or re.search(
                    r"purchased licenses?|add to cart|view licens", clean_line, re.I
                ):
                    in_includes = False
                    continue
                if 2 < len(clean_line) <= 80:
                    included_items.append(clean_text(clean_line))

    # Text fallback for included items
    if not included_items:
        m = re.search(
            r"(?:bundle includes?|what.?s included|includes?)\s*:?\s+"
            r"((?:[A-Z][^\n.!?]{2,60}(?:\s+|$)){1,20})",
            product_text, re.I
        )
        if m:
            parts = re.split(r"\s{2,}", m.group(1))
            included_items = [clean_text(p) for p in parts
                              if 2 < len(clean_text(p)) <= 80][:20]

    # License options
    lic_m = re.search(
        r"(?:(?:view\s+)?licens(?:e|es)|purchased licens(?:e|es))\s+"
        r"((?:Individual|Commercial\s*\+?|Personal|Professional|Business|"
        r"Enterprise|Standard|Premium)[^\n€$₨]{0,30}(?:\s+(?:Individual|"
        r"Commercial\s*\+?|Personal|Professional|Business|Enterprise|"
        r"Standard|Premium)[^\n€$₨]{0,30})*)",
        product_text, re.I
    )
    if lic_m:
        lic_text = lic_m.group(1)
        parts = re.split(
            r"\s+(?=Individual|Commercial|Personal|Professional|Business|"
            r"Enterprise|Standard|Premium\b)",
            lic_text
        )
        license_options = [clean_text(p) for p in parts if clean_text(p)][:10]

    return {
        "includedItems": included_items[:20],
        "licenseOptions": license_options[:10],
    }




def _extract_artwork_data(soup, product_text, options):
    """For artwork/print products: artist, paperType, printSizes, downloadAvailable."""
    artist = None
    paper_type = None
    print_sizes = []
    download_available = False

    m = re.search(
        r"(?:designed by|by artist|artist[:\s]+|created by)\s+([A-Z][a-zA-Z\s\.]{2,40}?)(?:[.,]|$)",
        product_text, re.I
    )
    if m:
        artist = clean_text(m.group(1))

    pm = re.search(
        r"(?:printed on|print on|paper[:\s]+)\s+([a-zA-Z\s]{3,60}?(?:paper|stock|canvas|board))",
        product_text, re.I
    )
    if pm:
        paper_type = clean_text(pm.group(1))

    # Sizes from variant options
    for opt in options:
        opt_name = (opt.get("name") or "").lower()
        if any(k in opt_name for k in ["size", "art-size", "dimension"]):
            for val in (opt.get("values") or []):
                text = val.get("text", "")
                if re.search(r"\d+\s*[x\xd7]\s*\d+|\d+\s*in\b|\d+\s*cm\b", text):
                    print_sizes.append(text)

    if re.search(r"digital download", product_text, re.I):
        download_available = True
    for opt in options:
        for val in (opt.get("values") or []):
            if "digital download" in (val.get("text", "")).lower():
                download_available = True

    return {
        "artist": artist,
        "paperType": paper_type,
        "printSizes": print_sizes[:10],
        "downloadAvailable": download_available,
    }


# ── Automotive compatibility ──────────────────────────────────────────

_JUNK_COMPAT_VALUES = {
    "n/a", "-", "—", "", "make", "model", "year", "engine",
    "transmission", "trim", "all", "various", "tbd", "n.a", "none"
}


def _clean_compat_value(val):
    val = clean_text(val or "")
    if not val or val.lower() in _JUNK_COMPAT_VALUES:
        return None
    return val


def _normalize_compatibility(entries):
    """
    Clean, validate, and dedupe a list of compatibility entries.
    Drops rows that are empty/header-leakage and removes exact-duplicate
    {make, model, year, engine, transmission, trim} combinations.
    """
    seen = set()
    cleaned = []
    for entry in entries or []:
        normalized = {}
        for key in ("make", "model", "year", "engine", "transmission", "trim"):
            val = _clean_compat_value(entry.get(key))
            if val:
                normalized[key] = val

        make = normalized.get("make", "")
        model = normalized.get("model", "")
        # Require at least a real make or model (≥2 chars)
        if len(make) < 2 and len(model) < 2:
            continue

        sig = tuple(
            normalized.get(k, "")
            for k in ("make", "model", "year", "engine", "transmission", "trim")
        )
        if sig in seen:
            continue
        seen.add(sig)
        cleaned.append(normalized)

    return cleaned[:50]


def _parse_compatibility_text_items(items):
    """
    Fallback for the generic 'Compatibility'/'Fitment' section: parse
    free-text lines like 'Toyota Corolla 2015-2020' or
    'Honda Civic 2018 1.5L Turbo' into {make, model, year, ...} dicts.
    """
    entries = []
    for item in items or []:
        m = re.match(
            r"^([A-Z][A-Za-z\-]+)\s+([A-Za-z0-9\-]+(?:\s+[A-Za-z0-9\-]+){0,2}?)\s+"
            r"(\d{4}(?:\s*[-–]\s*\d{2,4})?)",
            item
        )
        if m:
            entries.append({
                "make": m.group(1),
                "model": clean_text(m.group(2)),
                "year": m.group(3).replace(" ", ""),
            })
    return entries


def _extract_automotive_compatibility(product_text, soup):
    """
    Parse Compatible Vehicles / Fitment table.
    Returns list of {make, model, year, engine, transmission, trim}.
    """
    compatibility = []
    _compat_re = re.compile(
        r"compatible vehicles?|vehicle fitment|fitment|compatibility", re.I
    )

    # DOM: find a table near the compatibility heading
    compat_table = None
    for tag in soup.find_all(["h2", "h3", "h4", "h5", "th", "div", "p"]):
        tag_text = clean_text(tag.get_text(" "))[:80]
        if _compat_re.search(tag_text):
            table = tag.find_next("table")
            if not table and tag.parent:
                table = tag.parent.find_next("table")
            if table:
                compat_table = table
                break

    if compat_table:
        headers = []
        for row in compat_table.find_all("tr"):
            cells = [clean_text(c.get_text(" ")) for c in row.find_all(["th", "td"])]
            cells = [c for c in cells if c]
            if not cells:
                continue
            if not headers and any(c.lower() in ("make", "model", "year") for c in cells):
                headers = [c.lower() for c in cells]
                continue
            if headers:
                entry = {}
                for i, val in enumerate(cells):
                    if i < len(headers) and headers[i] in (
                        "make", "model", "year", "engine", "transmission", "trim"
                    ):
                        if val and val.lower() not in ("n/a", "-", ""):
                            entry[headers[i]] = val
                if entry.get("make") or entry.get("model"):
                    compatibility.append(entry)
        if compatibility:
            return _normalize_compatibility(compatibility)

    # Text fallback: "Make Model Year..." rows
    m = re.search(
        r"compatible vehicles?\s+make\s+model\s+year"
        r"(?:\s+engine)?(?:\s+transmission)?(?:\s+trim)?\s+"
        r"((?:[A-Z][A-Z0-9 ]+\s+\d{4}[-*\d]*\s*)+)",
        product_text, re.I
    )
    if m:
        for vm in re.finditer(r"([A-Z]+)\s+([A-Z0-9]+)\s+(\d{4}[-*\d]*)", m.group(1)):
            compatibility.append({
                "make": vm.group(1),
                "model": vm.group(2),
                "year": vm.group(3),
            })

    return _normalize_compatibility(compatibility)


# ── Technical specifications ──────────────────────────────────────────

def _extract_technical_specs(product_text, soup):
    """
    Extract spec tables for industrial / equipment products.
    Returns list of {name, value} dicts.
    """
    specs = []

    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue
        headers = []
        table_specs = []
        for row in rows:
            cells = [clean_text(c.get_text(" ")) for c in row.find_all(["th", "td"])]
            cells = [c for c in cells if c]
            if not cells:
                continue
            if not headers:
                headers = cells
                continue
            if len(cells) == 2:
                table_specs.append({"name": cells[0], "value": cells[1]})
            elif len(cells) > 2:
                table_specs.append({"name": cells[0], "value": " | ".join(cells[1:])})
        if table_specs:
            specs.extend(table_specs[:50])
            break

    if specs:
        return specs

    # Text fallback: "SpecName val1 val2 ..." rows
    spec_kw = (r"Model|Capacity|Power|Heating Capacity|Voltage|Frequency"
               r"|COP|Noise|Weight|Flow Rate|Refrigerant|EER|SCOP")
    for name, value in re.findall(
        r"(" + spec_kw + r")\s+([^\n]{5,200}?)(?=" + spec_kw + r"|$)",
        product_text, re.I
    ):
        specs.append({"name": clean_text(name), "value": clean_text(value)})

    return specs[:50]



def infer_currency_from_url(url):
    """Return ISO currency code inferred from URL domain/path, or None.

    Used as a final fallback when JSON-LD and DOM symbol detection both fail
    to identify currency (e.g. '$' on a .ca domain is CAD, not USD).
    """
    if not url:
        return None
    url_l = url.lower()
    from urllib.parse import urlparse as _up
    host = _up(url_l).hostname or ""
    if host.endswith(".ca") or "/en-ca/" in url_l:
        return "CAD"
    if host.endswith(".com.au") or "/en-au/" in url_l:
        return "AUD"
    if host.endswith(".co.uk") or host.endswith(".uk") or "/en-gb/" in url_l:
        return "GBP"
    if host.endswith(".ae") or "/en-ae/" in url_l or "/ae/" in url_l:
        return "AED"
    _eu = (".de", ".fr", ".it", ".es", ".nl", ".be", ".at", ".pt",
           ".pl", ".se", ".dk", ".fi", ".no", ".ch")
    if any(host.endswith(t) for t in _eu):
        return "EUR"
    if host.endswith(".in") or "/en-in/" in url_l:
        return "INR"
    if host.endswith(".sg") or "/en-sg/" in url_l:
        return "SGD"
    return None


# Selectors for button-group / swatch variant pickers in WooCommerce themes
_WP_BG_OPTION_SELECTORS = [
    # WooCommerce variation-swatches plugin fieldsets
    ("fieldset[data-attribute_name]",            None),
    ("fieldset[class*='variation-selector']",    None),
    ("fieldset[class*='swatch']",                None),
    # Aria-labelled radiogroups
    ("[role='radiogroup'][aria-label*='size']",   "Size"),
    ("[role='radiogroup'][aria-label*='Size']",   "Size"),
    ("[role='radiogroup'][aria-label*='color']",  "Color"),
    ("[role='radiogroup'][aria-label*='Color']",  "Color"),
    # Explicit aria-labelled fieldsets
    ("fieldset[aria-label*='size']",              "Size"),
    ("fieldset[aria-label*='Size']",              "Size"),
    ("fieldset[aria-label*='color']",             "Color"),
    ("fieldset[aria-label*='Color']",             "Color"),
]

_WP_BG_VALUE_NOISE_RE = re.compile(
    r'^(?:choose|select|pick)\s', re.I
)


def _extract_button_group_options_wp(soup):
    """Extract variant options from button-group/swatch UIs in WooCommerce.

    Modern WooCommerce themes (Flatsome, Divi, WooSwatches, Variation Swatches)
    render colour/size pickers as styled buttons inside <fieldset> or
    [role=radiogroup] elements instead of <select> dropdowns.
    Supplements extract_variants_and_options() which only reads <select>.
    """
    options = []
    seen_names = set()

    main_scope = (
        soup.select_one("form.cart")
        or soup.select_one(".summary.entry-summary")
        or soup.select_one(".entry-summary")
        or soup.select_one(".single-product")
        or soup
    )

    for selector, hint_name in _WP_BG_OPTION_SELECTORS:
        for container in main_scope.select(selector):
            if container.find_parent(["header", "nav", "footer"]):
                continue

            opt_name = None
            legend = container.find("legend")
            if legend:
                opt_name = clean_text(legend.get_text(" ", strip=True))
                opt_name = re.sub(
                    r'^(?:select|choose|pick)\s+(?:a\s+)?', '', opt_name, flags=re.I
                ).strip()
            if not opt_name:
                opt_name = clean_text(container.get("aria-label") or "")
            if not opt_name:
                attr = (container.get("data-attribute_name")
                        or container.get("data-attribute") or "")
                attr = re.sub(r'^attribute_pa_', '', attr)
                opt_name = attr.replace("-", " ").replace("_", " ").strip().title()
            if not opt_name and hint_name:
                opt_name = hint_name
            if not opt_name or len(opt_name.split()) > 4 or len(opt_name) > 50:
                continue

            key = opt_name.lower()
            if key in seen_names:
                continue

            values = []
            seen_vals = set()

            for el in container.find_all(["button", "input", "label", "a"]):
                if el == legend:
                    continue
                label = (
                    el.get("aria-label")
                    or el.get("title")
                    or el.get("data-value")
                    or el.get("value")
                    or clean_text(el.get_text(" ", strip=True))
                )
                label = clean_text(label or "")
                if not label or len(label) > 40:
                    continue
                label = re.sub(
                    r'\s*[-\u2013\u2014]\s*(?:sold\s*out|unavailable|out\s*of\s*stock).*',
                    '', label, flags=re.I
                ).strip()
                if not label or _WP_BG_VALUE_NOISE_RE.match(label):
                    continue
                lkey = label.lower()
                if lkey not in seen_vals:
                    seen_vals.add(lkey)
                    values.append({"text": label, "value": label})

            if len(values) >= 2:
                options.append({"name": opt_name, "values": values})
                seen_names.add(key)

    return options


def analyze_product(self, url, html, headers, page_type, level1):

    result = self.base_result(
        url,
        html,
        headers,
        page_type,
        level1
    )

    soup = BeautifulSoup(html or "", "lxml")

    result["source"]["extractor"] = "WordPress Product Extractor"

    json_ld_items = extract_json_ld_items(soup)
    jsonld_product = extract_product_from_json_ld(json_ld_items, url)

    product_node = (
        soup.select_one(".product")
        or soup.select_one(".single-product")
        or soup.select_one("main")
        or soup.body
        or soup
    )

    product_text = clean_text(product_node.get_text(" "))

    title = None

    for selector in [
        "h1.product_title",
        ".product_title",
        "h1.entry-title",
        "h1",
        ".product-name"
    ]:
        node = soup.select_one(selector)

        if node:
            title = clean_text(node.get_text(" "))

            if title:
                break

    # Scope price search to product summary; strip cart/header zones first
    summary_soup = get_product_summary_soup(soup)
    price_text_raw = None

    for selector in [
        ".summary .price",
        ".product .summary .price",
        ".entry-summary .price",
        ".woocommerce-Price-amount"
    ]:
        node = summary_soup.select_one(selector)

        if node:
            candidate = extract_price_from_text(node.get_text(" "))

            if candidate and not _is_zero_price(candidate):
                price_text_raw = candidate
                break

    if not price_text_raw:
        candidate = extract_price_from_text(product_text)
        if candidate and not _is_zero_price(candidate):
            price_text_raw = candidate

    pricing = extract_pricing_details(product_text, price_text_raw, page_url=url)

    if pricing.get("currentPrice"):
        price_text_raw = pricing.get("currentPrice")

    price_normalized = normalize_price(price_text_raw, page_url=url)

    stock_text, in_stock = extract_stock(soup)

    sku = None

    sku_node = soup.select_one(".sku, [itemprop='sku']")

    if sku_node:
        sku = clean_text(sku_node.get_text(" "))

    if sku and sku.upper() in ["N/A", "SKU"]:
        sku = None

    images = extract_images(soup, url)
    categories = extract_categories(soup, url)
    breadcrumbs = extract_breadcrumbs(soup, url)
    tabs = extract_tabs(soup)
    options = extract_variants_and_options(soup)
    related_products = extract_related_products(soup, url)
    reviews_summary = extract_reviews_summary(soup, jsonld_product)

    # ── Generic DOM-based section extraction (Task #98) ───────────────────
    generic_sections = extract_generic_sections(soup)

    # ── Description fallback chain ───────────────────────────────────────
    description_final = tabs.get("description")
    if not description_final:
        description_final = _extract_description_fallback(soup, jsonld_product)

    # ── Features fallback chain: ALL-CAPS tabs → ALL-CAPS DOM heading
    # pattern → generic Title-Case heading sections ─────────────────────
    features_final = tabs.get("features") or []
    if not features_final:
        features_final = _extract_features_from_content(soup, description_final or "")
    if not features_final:
        features_final = generic_sections.get("features") or []

    # ── Benefits fallback chain ────────────────────────────────────────
    benefits_final = tabs.get("benefits") or []
    if not benefits_final:
        benefits_final = generic_sections.get("benefits") or []

    # ── Materials (new field) ──────────────────────────────────────────
    materials_final = generic_sections.get("materials") or []

    # ── Care instructions / shipping info (new fields) ────────────────
    care_instructions_final = generic_sections.get("careInstructions")
    shipping_info_final = generic_sections.get("shippingInfo")

    # ── Product category detection ───────────────────────────────────────
    product_category = _detect_product_category(title or "", product_text)

    # ── Category-specific extraction, with generic-section fallbacks ──────
    compatibility = []
    technical_specifications = []
    included_items = []
    license_options = []
    artist = None
    paper_type = None
    print_sizes = []
    download_available = False

    if product_category == "automotive":
        compatibility = _extract_automotive_compatibility(product_text, soup)

    elif product_category == "industrial":
        technical_specifications = _extract_technical_specs(product_text, soup)

    elif product_category == "digital_product":
        _digital = _extract_digital_product_data(product_text, json_ld_items)
        included_items = _digital.get("includedItems", [])
        license_options = _digital.get("licenseOptions", [])

    elif product_category == "artwork":
        _art = _extract_artwork_data(soup, product_text, options)
        artist = _art.get("artist")
        paper_type = _art.get("paperType")
        print_sizes = _art.get("printSizes", [])
        download_available = _art.get("downloadAvailable", False)

    # Generic-section fallbacks (apply regardless of detected category)
    if not compatibility:
        compatibility = _normalize_compatibility(
            _parse_compatibility_text_items(generic_sections.get("compatibility"))
        )

    if not technical_specifications and generic_sections.get("technicalSpecifications"):
        for line in generic_sections["technicalSpecifications"]:
            if ":" in line:
                name, _, value = line.partition(":")
                technical_specifications.append({"name": clean_text(name), "value": clean_text(value)})
            else:
                technical_specifications.append({"name": line, "value": None})
        technical_specifications = technical_specifications[:50]

    if not included_items and generic_sections.get("includedItems"):
        included_items = generic_sections["includedItems"][:20]

    if not artist and generic_sections.get("artist"):
        _artist_text = generic_sections["artist"]
        _artist_m = re.search(
            r"(?:designed by|by artist|artist[:\s]+|created by)\s+([A-Z][a-zA-Z\s\.]{2,40}?)(?:[.,]|$)",
            _artist_text, re.I
        )
        artist = clean_text(_artist_m.group(1)) if _artist_m else _artist_text[:120]

    product = {
        "name": title,
        "url": normalize_url(url),
        "sku": sku,
        "price": price_text_raw,
        "priceTextRaw": price_text_raw,
        "priceNormalized": price_normalized,
        "pricing": pricing,
        "stockText": stock_text,
        "inStock": in_stock,
        "availability": None,
        "image": images[0]["url"] if images else None,
        "images": images,
        "categories": categories,
        "breadcrumbs": breadcrumbs,
        "options": options,
        "description": description_final,
        "howToUse": tabs.get("howToUse"),
        "ingredients": tabs.get("ingredients"),
        "productDNA": tabs.get("productDNA"),
        "benefits": benefits_final,
        "features": features_final,
        "materials": materials_final,
        "activeIngredients": tabs.get("activeIngredients") or [],
        "technology": tabs.get("technology"),
        "claims": tabs.get("claims"),
        "warnings": tabs.get("warnings"),
        "suitableFor": tabs.get("suitableFor"),
        "additionalInformation": tabs.get("additionalInformation"),
        "careInstructions": care_instructions_final,
        "shippingInfo": shipping_info_final,
        "reviewsText": tabs.get("reviews"),
        "reviews": reviews_summary,
        "relatedProducts": related_products,
        # ── Category-specific fields ─────────────────────────────────────────────────
        "productType": product_category or "singleProduct",
        "compatibility": compatibility,
        "technicalSpecifications": technical_specifications,
        "includedItems": included_items,
        "licenseOptions": license_options,
        "artist": artist,
        "paperType": paper_type,
        "printSizes": print_sizes,
        "downloadAvailable": download_available,
        "source": "dom",
        "fieldConfidence": {
            "name": 0.85 if title else 0.0,
            "price": 0.75 if price_normalized.get("amount") is not None else 0.0,
            "images": 0.85 if images else 0.0,
            "stock": 0.75 if stock_text else 0.0,
            "description": 0.80 if description_final else 0.0,
            "options": 0.75 if options else 0.0
        }
    }

    if jsonld_product:
        product["source"] = "merged"

        if jsonld_product.get("name") and not product.get("name"):
            product["name"] = jsonld_product.get("name")
            product["fieldConfidence"]["name"] = 0.95

        if jsonld_product.get("url"):
            product["url"] = jsonld_product.get("url")

        _jsonld_pn = jsonld_product.get("priceNormalized") or {}
        _jsonld_has_valid_price = (
            _jsonld_pn.get("amount") is not None
            and not _is_zero_price(jsonld_product.get("priceTextRaw") or "")
        )
        if _jsonld_has_valid_price:
            product["price"] = jsonld_product.get("price")
            product["priceTextRaw"] = jsonld_product.get("priceTextRaw")
            product["priceNormalized"] = _jsonld_pn

            product["pricing"]["currentPrice"] = jsonld_product.get("priceTextRaw")
            product["pricing"]["currentPriceNormalized"] = _jsonld_pn

            if not product["pricing"].get("onSale"):
                product["pricing"]["discountPercent"] = None

            product["fieldConfidence"]["price"] = 0.98

        if jsonld_product.get("image") and not product.get("image"):
            product["image"] = jsonld_product.get("image")
            product["images"].insert(0, {
                "url": jsonld_product.get("image"),
                "alt": product.get("name") or ""
            })
            product["images"] = unique_items(product["images"], "url")
            product["fieldConfidence"]["images"] = 0.90

        if jsonld_product.get("availability"):
            product["availability"] = jsonld_product.get("availability")
            availability_lower = jsonld_product.get("availability", "").lower()

            if "instock" in availability_lower:
                product["inStock"] = True
            elif "outofstock" in availability_lower:
                product["inStock"] = False

            product["fieldConfidence"]["stock"] = 0.95

        if jsonld_product.get("priceValidUntil"):
            product["priceValidUntil"] = jsonld_product.get("priceValidUntil")

        if jsonld_product.get("additionalProperties"):
            product["additionalProperties"] = jsonld_product.get("additionalProperties")

        if jsonld_product.get("rating", {}).get("ratingValue") is not None:
            product["reviews"] = jsonld_product.get("rating")
            product["fieldConfidence"]["reviews"] = 0.95

    product["images"] = unique_items(product.get("images", []), "url")[:20]

    # ── Availability fallback: derive from DOM inStock flag when JSON-LD
    # is absent (e.g. happynails.pk has no JSON-LD but "In Stock" in DOM text).
    if not product.get("availability") and product.get("inStock") is not None:
        product["availability"] = (
            "http://schema.org/InStock"
            if product["inStock"]
            else "http://schema.org/OutOfStock"
        )

    product["options"] = extract_variants_and_options(soup)

    # Supplement with button-group options for modern WooCommerce themes
    # (Flatsome, Divi, WooSwatches use fieldset/radiogroup pickers, not <select>)
    # Normalise WooCommerce raw attribute names (e.g. "attribute_pa_size" → "size")
    # before dedup so hidden <select> and visible <fieldset> for the same attribute
    # are not both included.
    def _norm_wp_opt(name):
        return re.sub(r"^attribute_pa_", "", (name or "")).replace("-", "_").lower()

    _existing_opt_names = {_norm_wp_opt(o["name"]) for o in product["options"]}
    for _bg_opt in _extract_button_group_options_wp(soup):
        if _norm_wp_opt(_bg_opt["name"]) not in _existing_opt_names:
            product["options"].append(_bg_opt)
            _existing_opt_names.add(_norm_wp_opt(_bg_opt["name"]))
    product["options"] = product["options"][:20]

    # URL-based currency inference: fills when JSON-LD and DOM symbol detection
    # both fail (e.g. '$' on a .ca WooCommerce store → CAD, not USD)
    if not (product.get("priceNormalized") or {}).get("currency"):
        _url_currency = infer_currency_from_url(url)
        if _url_currency and product.get("priceNormalized"):
            product["priceNormalized"]["currency"] = _url_currency

    # Convert raw price string to standard {current, currency, compareAt, isOnSale} dict
    # so downstream consumers don't need to handle both string and dict formats.
    _pn = product.get("priceNormalized") or {}
    _pricing = product.get("pricing") or {}
    _orig_pn = (_pricing.get("originalPriceNormalized") or {})
    _norm_price = {
        "current": _pn.get("amount"),
        "currency": _pn.get("currency") or "EUR",
        "compareAt": _orig_pn.get("amount"),
        "isOnSale": bool(_pricing.get("onSale")),
        "priceTextRaw": product.get("priceTextRaw"),
    }
    _wp_cur = _pn.get("amount")
    _wp_cmp = _orig_pn.get("amount")
    if _wp_cmp and _wp_cur and _wp_cmp > _wp_cur:
        _norm_price["discount"] = {
            "percent": round(((_wp_cmp - _wp_cur) / _wp_cmp) * 100),
            "savedAmount": round(_wp_cmp - _wp_cur, 2),
            "originalPrice": _wp_cmp,
            "currentPrice": _wp_cur,
        }
    else:
        _norm_price["discount"] = None if _wp_cmp is not None else "unfetched"
    if _norm_price["current"] is not None:
        product["price"] = _norm_price

    result["product"] = product

    # ── seo.h1 fix: soup.find("h1") in base_result picks the FIRST <h1>
    # on the page which is often a widget/breadcrumb ("Shop", "Home", etc.)
    # on WooCommerce product pages.  Override with the product title when the
    # product-specific selector found a better value.
    _product_h1 = None
    for _sel in ("h1.product_title", ".entry-title h1", "h1.entry-title"):
        _n = soup.select_one(_sel)
        if _n:
            _product_h1 = clean_text(_n.get_text(" "))
            break
    # If no class-specific H1 found but the product title is available and
    # differs from what base_result captured, prefer the product title.
    if not _product_h1 and product.get("name"):
        _generic_h1 = (result.get("seo") or {}).get("h1") or ""
        if _generic_h1.lower() != (product["name"] or "").lower():
            _product_h1 = product["name"]
    if _product_h1:
        result.setdefault("seo", {})["h1"] = _product_h1

    # ── SKU fallback: DOM .sku is often "N/A" on WooCommerce variable products;
    # use the JSON-LD sku (numeric product ID) when DOM gives nothing useful.
    if not product.get("sku") and jsonld_product and jsonld_product.get("sku"):
        _jld_sku = str(jsonld_product["sku"]).strip()
        if _jld_sku and _jld_sku.upper() not in ("N/A", "SKU", ""):
            product["sku"] = _jld_sku
            result["product"]["sku"] = _jld_sku

    # ── option name cleanup: strip WooCommerce "attribute_" / "attribute_pa_"
    # prefixes from option names so "attribute_quantity" → "Quantity".
    for _opt in (product.get("options") or []):
        _opt_name = _opt.get("name") or ""
        if _opt_name.lower().startswith("attribute_"):
            _clean = re.sub(r"^attribute_(?:pa_)?", "", _opt_name, flags=re.I)
            _clean = _clean.replace("_", " ").replace("-", " ").strip().title()
            if _clean:
                _opt["name"] = _clean

    result["ecommerce"] = {
        "productType": product.get("productType", "singleProduct"),
        "product": product,
        "hasPrice": (
            (product.get("priceNormalized") or {}).get("amount") is not None
            and not _is_zero_price(product.get("priceTextRaw") or "")
        ),
        "hasImages": bool(product.get("images")),
        "hasOptions": bool(product.get("options")),
        "hasRelatedProducts": bool(related_products),
        "relatedProductsCount": len(related_products)
    }

    # Populate result["products"] with the extracted product (mirrors the
    # Shopify product analyzer). This was previously an empty list, which made
    # every downstream consumer — accuracy checks, comparison engine, AI
    # payload — see WordPress product pages as having NO product at all.
    _plist_entry = dict(product)
    _plist_imgs = [
        (i.get("url") or i.get("src")) if isinstance(i, dict) else i
        for i in (product.get("images") or [])
    ]
    _plist_imgs = [i for i in _plist_imgs if i]
    if _plist_imgs:
        _plist_entry.setdefault("imageUrl", _plist_imgs[0])
        _plist_entry.setdefault("additionalImageUrls", _plist_imgs[1:])
    _plist_entry.setdefault("productUrl", url)
    result["products"] = [_plist_entry] if product.get("name") else []

    result["content"] = {
        "title": product.get("name"),
        "mainText": product_text[:12000],
        "description": product.get("description"),
        "howToUse": product.get("howToUse"),
        "ingredients": product.get("ingredients"),
        "productDNA": product.get("productDNA"),
        "benefits": product.get("benefits"),
        "features": product.get("features"),
        "materials": product.get("materials") or None,
        "activeIngredients": product.get("activeIngredients"),

        "texts": None,
    }

    return result
