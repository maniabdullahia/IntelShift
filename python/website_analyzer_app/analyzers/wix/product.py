from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urlunparse
import re
import json  # noqa: F401


# ------------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------------

def clean_text(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _dollar_currency_from_url(url):
    """Delegate to shared currency utility."""
    from utils.currency import currency_from_url
    return currency_from_url(url) or "USD"


def truncate_words(text, limit=80):
    if not text:
        return None
    words = clean_text(text).split()
    if len(words) <= limit:
        return clean_text(text)
    return " ".join(words[:limit]).strip() + "..."


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


def get_wix_media_key(url):
    if not url:
        return None
    match = re.search(r"/media/([^/]+)", url)
    return match.group(1) if match else url


# ------------------------------------------------------------------
# JINA PLACEHOLDER DETECTION
# ------------------------------------------------------------------

def _is_jina_placeholder(text):
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
    if not url_str:
        return None
    slug = urlparse(url_str).path.rstrip("/").split("/")[-1]
    if not slug:
        return None
    return slug.replace("-", " ").replace("_", " ").title()


# ------------------------------------------------------------------
# RECOMMENDATION SECTION SPLITTER
# ------------------------------------------------------------------

# Text markers that indicate the start of a related/recommendation product section.
_RECOMMENDATION_MARKERS = [
    "you might also like",
    "you may also like",
    "customers also bought",
    "customers also viewed",
    "recommended products",
    "related products",
    "you might also enjoy",
    "similar products",
]


def _split_at_recommendation_section(html, page_text):
    """
    Return (product_html, product_text) — trimmed at the first recommendation
    section marker, so images and availability checks don't bleed into
    the related-products grid.
    """
    html_lower = html.lower()
    text_lower = page_text.lower()

    split_html = len(html)
    split_text = len(page_text)

    for marker in _RECOMMENDATION_MARKERS:
        pos_h = html_lower.find(marker)
        if pos_h > 30:
            split_html = min(split_html, pos_h)
        pos_t = text_lower.find(marker)
        if pos_t > 30:
            split_text = min(split_text, pos_t)

    return html[:split_html], page_text[:split_text]


# ------------------------------------------------------------------
# PRICE HELPERS
# ------------------------------------------------------------------

def format_price_display(raw, currency=None):
    if not raw:
        return None
    raw = clean_text(raw)
    symbol = "$" if "$" in raw else ("£" if "£" in raw else ("€" if "€" in raw else ""))
    match = re.search(r"(\d+(?:[,.]\d{1,2})?)", raw)
    if not match:
        return raw
    try:
        amount = float(match.group(1).replace(",", "."))
        return f"{symbol}{amount:.2f}" if symbol else f"{amount:.2f}"
    except Exception:
        return raw


def normalize_price(raw, currency_fallback=None, page_url=None):
    if not raw:
        return None
    raw = clean_text(raw)
    currency = currency_fallback
    if "$" in raw and not currency:
        currency = _dollar_currency_from_url(page_url)
    elif "£" in raw and not currency:
        currency = "GBP"
    elif "€" in raw and not currency:
        currency = "EUR"
    elif ("rs" in raw.lower() or "₨" in raw) and not currency:
        currency = "PKR"
    elif ("aed" in raw.lower()) and not currency:
        currency = "AED"
    elif ("sar" in raw.lower() or "﷼" in raw) and not currency:
        currency = "SAR"
    elif ("inr" in raw.lower() or "₹" in raw) and not currency:
        currency = "INR"
    match = re.search(r"(\d+(?:[,.]\d{1,2})?)", raw)
    amount = None
    if match:
        try:
            amount = float(match.group(1).replace(",", "."))
            if amount == 0.0:
                amount = None  # zero is not a valid product price
        except Exception:
            pass
    return {"raw": raw, "amount": amount, "currency": currency}


# ------------------------------------------------------------------
# DOM CLEANING
# ------------------------------------------------------------------

def clean_wix_dom(html):
    soup = BeautifulSoup(html or "", "lxml")
    remove_selectors = [
        "script", "style", "noscript", "iframe", "svg", "template",
        "header", "footer", "nav",
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


def flatten_json_ld(item):
    output = []
    if isinstance(item, list):
        for child in item:
            output.extend(flatten_json_ld(child))
    elif isinstance(item, dict):
        output.append(item)
        graph = item.get("@graph")
        if isinstance(graph, list):
            for child in graph:
                output.extend(flatten_json_ld(child))
    return output


def normalize_availability(raw):
    if not raw:
        return None
    value = str(raw).lower()
    if "instock" in value or "in stock" in value:
        return "in_stock"
    if "outofstock" in value or "out of stock" in value:
        return "out_of_stock"
    if "preorder" in value or "pre-order" in value:
        return "preorder"
    return clean_text(str(raw))


def extract_product_schema(json_ld_items):
    flattened = []
    for item in json_ld_items:
        flattened.extend(flatten_json_ld(item))
    for item in flattened:
        item_type = item.get("@type")
        types = [str(t).lower() for t in item_type] if isinstance(item_type, list) else (
            [str(item_type).lower()] if item_type else []
        )
        if "product" not in types:
            continue
        offers = item.get("offers") or item.get("Offers") or {}
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        price = offers.get("price") or offers.get("lowPrice") or offers.get("highPrice")
        currency = offers.get("priceCurrency") or offers.get("currency")
        availability = offers.get("availability") or offers.get("Availability")
        brand = item.get("brand")
        if isinstance(brand, dict):
            brand = brand.get("name")
        if not brand and isinstance(offers, dict):
            seller = offers.get("seller")
            if isinstance(seller, dict):
                brand = seller.get("name")
        return {
            "name": clean_text(item.get("name")),
            "description": clean_text(item.get("description")),
            "sku": item.get("sku"),
            "brand": clean_text(brand) or None,
            "image": item.get("image"),
            "price": str(price) if price else None,
            "currency": currency,
            "availability": normalize_availability(availability),
            "raw": item
        }
    return {}


# ------------------------------------------------------------------
# WIX PRODUCT ATTRIBUTES (OGI-style)
# ------------------------------------------------------------------

def extract_wix_product_attributes(page_text):
    """
    Extract Wix product attribute selectors like:
      "Color*", "Material* Plastic", "Shape* Geometric", "Brand* Red Rose by OGI"
    and structured sections like:
      "**Features** * Handmade in Japan * Geometric shape"
    """
    attrs = {}

    # Pattern: Key* Value  (terminated by next Key* or section marker)
    # e.g. "Material* Plastic Shape* Geometric"
    attr_pattern = re.compile(
        r"\b(Color|Colour|Material|Shape|Size|Brand|Collection|Style|Lens|Frame)\s*\*\s*([^\n*]{1,80}?)(?=\s*(?:Color|Colour|Material|Shape|Size|Brand|Collection|Style|Lens|Frame)\s*\*|##|\Z)",
        re.I | re.DOTALL
    )
    for m in attr_pattern.finditer(page_text):
        key = m.group(1).strip().lower()
        value = clean_text(m.group(2))
        # Remove any trailing A/B/etc that belong to the next attribute
        value = re.sub(r"\s+[A-Z]\s*$", "", value).strip()
        if value and len(value) < 80:
            attrs[key] = value

    # Eyewear dimensions: "A 49 | B 43| ED 53| DBL 17| TMPL 140"
    dim_match = re.search(
        r"\b(A\s+\d+)\s*[\|]\s*(B\s+\d+)\s*[\|]\s*(ED\s+\d+)\s*[\|]\s*(DBL\s+\d+)\s*[\|]\s*(TMPL\s+\d+)",
        page_text, re.I
    )
    if dim_match:
        dims = {}
        for part in [dim_match.group(i) for i in range(1, 6)]:
            kv = part.strip().split()
            if len(kv) == 2:
                try:
                    dims[kv[0].upper()] = int(kv[1])
                except ValueError:
                    dims[kv[0].upper()] = kv[1]
        if dims:
            attrs["dimensions"] = dims

    # Structured section extraction: "**Features** * item1 * item2"
    # In Jina HTML this becomes: <strong>Features</strong> <li>item1</li> <li>item2</li>
    # In raw text it's: "**Features** * item1 * item2"
    section_pattern = re.compile(
        r"\*\*(Features?|Materials?|Specifications?|Details?|Benefits?)\*\*\s*((?:\*\s+[^\n*]{2,100}\s*)+)",
        re.I
    )
    for m in section_pattern.finditer(page_text):
        raw_section = m.group(1).strip()
        # "Features"→"feature", "Materials"→"materials_list" (to avoid overwriting material attr)
        section_name = raw_section.lower()
        if section_name in ("material", "materials"):
            section_name = "materials_list"
        elif section_name.endswith("s"):
            section_name = section_name[:-1]  # "features"→"feature"
        items_raw = m.group(2)
        items = [clean_text(i) for i in re.split(r"\*\s+", items_raw) if clean_text(i)]
        if items:
            attrs[section_name] = items

    # Also extract from HTML <li> items that appear after a **Section** heading
    return attrs


# ------------------------------------------------------------------
# PRODUCT FIELD EXTRACTORS
# ------------------------------------------------------------------

def _strip_site_name(text):
    """Remove '| Site Name' suffix from a product title."""
    if not text:
        return text
    return re.sub(r"\s*\|\s*.+$", "", text).strip()


def extract_product_name(seo, open_graph, schema_product, page_text):
    if schema_product.get("name"):
        return schema_product.get("name")
    # Strip "| Site Name" from h1 and title candidates
    if seo.get("h1"):
        h1 = _strip_site_name(seo["h1"])
        if h1:
            return clean_text(h1)
    title = open_graph.get("title") or seo.get("title")
    if title:
        return clean_text(_strip_site_name(title))
    return None


def extract_brand(page_text, seo, schema_product, url):
    """
    Priority:
    1. JSON-LD brand
    2. Wix attribute: "Brand* Value"
    3. Title "| Brand Name" suffix (if not generic site/page name)
    4. Domain slug
    """
    if schema_product and schema_product.get("brand"):
        return schema_product.get("brand")

    # Wix "Brand* RedRose by OGI" pattern
    brand_match = re.search(
        r"\bBrand\s*\*\s*([A-Za-z][^\n*|]{2,60}?)(?=\s*(?:Collection\s*\*|Color\s*\*|Material\s*\*|Shape\s*\*|Size\s*\*|##|\Z))",
        page_text, re.I | re.DOTALL
    )
    if brand_match:
        brand = clean_text(brand_match.group(1))
        if brand and len(brand) <= 80:
            return brand

    # Title "Product Name | Brand" — take the part after last |
    title = seo.get("title") or ""
    if "|" in title:
        parts = [p.strip() for p in title.split("|")]
        # Last part is usually the brand/site name
        candidate = parts[-1]
        if candidate and 2 < len(candidate) <= 60:
            # Skip generic words
            if candidate.lower() not in {"shop", "store", "website", "home", "page", "online store"}:
                return candidate.title() if candidate == candidate.lower() else candidate

    # Domain: vivietmargot.com → "Vivi Et Margot", coal-and-canary.com → "Coal And Canary"
    try:
        domain = urlparse(url).netloc.lower()
        domain = re.sub(r"^www\.", "", domain).split(".")[0]
        if "-" in domain:
            return domain.replace("-", " ").title()
    except Exception:
        pass

    return None


def extract_prices(page_text, schema_product=None, url=None):
    schema_currency = schema_product.get("currency") if schema_product else None
    prices = []

    if schema_product and schema_product.get("price"):
        raw = schema_product["price"]
        symbol = {"USD": "$", "GBP": "£", "EUR": "€"}.get(schema_currency, "")
        prices.append(symbol + str(raw))

    sale_match = re.search(r"sale\s+price\s+([$£€]\s?\d+(?:[,.]\d{1,2})?)", page_text, re.I)
    regular_match = re.search(r"regular\s+price\s+([$£€]\s?\d+(?:[,.]\d{1,2})?)", page_text, re.I)
    price_label_match = re.search(r"(?<!\w)price\s+([$£€]\s?\d+(?:[,.]\d{1,2})?)", page_text, re.I)
    main_match = re.search(r"([$£€]\s?\d+(?:[,.]\d{1,2})?)", page_text, re.I)

    if sale_match:
        prices.append(sale_match.group(1))
    if regular_match:
        prices.append(regular_match.group(1))
    if price_label_match and not sale_match:
        prices.append(price_label_match.group(1))
    if main_match and not prices:
        prices.append(main_match.group(1))

    prices = list(dict.fromkeys([clean_text(p) for p in prices if p]))

    current_price = format_price_display(sale_match.group(1), schema_currency) if sale_match else None
    regular_price = format_price_display(regular_match.group(1), schema_currency) if regular_match else None
    if not current_price and prices:
        current_price = format_price_display(prices[0], schema_currency)
    # Reject $0.00 / £0 etc. — Wix draft/unpublished products can expose zero prices
    if _is_zero_price(current_price):
        current_price = None
    if _is_zero_price(regular_price):
        regular_price = None

    _wix_discount = None
    if sale_match and regular_price:
        try:
            _rp = float(re.sub(r"[^\d.]", "", regular_price))
            _sp = float(re.sub(r"[^\d.]", "", sale_match.group(1)))
            if _rp > _sp > 0:
                _wix_discount = {
                    "percent": round(((_rp - _sp) / _rp) * 100),
                    "savedAmount": round(_rp - _sp, 2),
                    "originalPrice": _rp,
                    "currentPrice": _sp,
                }
        except (ValueError, ZeroDivisionError):
            pass
    if _wix_discount is None:
        _wix_discount = None if regular_price is not None else "unfetched"

    return {
        "price": current_price,
        "priceNormalized": normalize_price(current_price, schema_currency, page_url=url),
        "regularPrice": regular_price,
        "regularPriceNormalized": normalize_price(regular_price, schema_currency, page_url=url),
        "salePrice": format_price_display(sale_match.group(1), schema_currency) if sale_match else None,
        "salePriceNormalized": normalize_price(sale_match.group(1) if sale_match else None, schema_currency, page_url=url),
        "allPricesFound": prices,
        "schemaCurrency": schema_currency,
        "discount": _wix_discount,
    }


def extract_availability(page_text, schema_product=None, product_html=None):
    """
    Availability is determined only from the main product section,
    NOT from the recommendations/related-products grid.
    Uses product_html (pre-split) when available.
    """
    if schema_product and schema_product.get("availability"):
        return schema_product.get("availability")

    # Use the truncated text (before recommendations section)
    text = page_text.lower()
    if "out of stock" in text or "sold out" in text:
        return "out_of_stock"
    if "in stock" in text or "add to cart" in text or "buy now" in text:
        return "in_stock"
    if "preorder" in text or "pre-order" in text:
        return "preorder"
    return None


def extract_product_images(raw_soup, product_soup, open_graph, schema_product, base_url):
    """
    Build product image list from: schema → og:image → DOM.
    Uses product_soup (pre-split at recommendation section) to avoid
    collecting images from the related-products grid.

    Additional skip keywords: award, badge, bbb, logo, footer, sponsor.
    """
    images = []

    def add_schema_image(img):
        if not img:
            return
        if isinstance(img, str):
            images.append({"url": normalize_url(img, base_url), "alt": schema_product.get("name"), "source": "schema"})
        elif isinstance(img, dict):
            cu = img.get("contentUrl") or img.get("url")
            if cu:
                images.append({"url": normalize_url(cu, base_url), "alt": schema_product.get("name"), "source": "schema"})
        elif isinstance(img, list):
            for nested in img:
                add_schema_image(nested)

    add_schema_image(schema_product.get("image"))

    if not images and open_graph.get("image"):
        images.append({
            "url": normalize_url(open_graph["image"], base_url),
            "alt": open_graph.get("image:alt"),
            "source": "og:image"
        })

    # Use the recommendation-trimmed soup for DOM images
    img_soup = product_soup if product_soup is not None else raw_soup

    skip_keywords = [
        "logo", "icon", "placeholder", "loader", "spinner",
        "avatar", "badge", "payment", "social",
        "site", "header", "footer", "award", "bbb",
        "sponsor", "partner", "certificate", "seal"
    ]

    for img in img_soup.select("img"):
        src = (img.get("data-src") or img.get("data-lazy-src") or img.get("src"))
        if not src or src.startswith("data:image"):
            continue

        src_lower = src.lower()
        if any(k in src_lower for k in skip_keywords):
            continue

        alt = clean_text(img.get("alt"))
        if _is_jina_placeholder(alt):
            alt = _slug_to_title(src) or schema_product.get("name") or None

        if alt and (alt.lower().endswith(".jpg") or alt.lower().endswith(".png") or alt.lower().endswith(".webp")):
            alt = None

        images.append({"url": normalize_url(src, base_url), "alt": alt, "source": "dom"})

    # De-duplicate and filter tiny/blur thumbnails
    cleaned = []
    seen_media = set()
    for image in unique_items(images, "url"):
        url = image.get("url")
        if not url:
            continue
        if "blur_" in url or "/w_22," in url or "/h_22," in url:
            continue
        media_key = get_wix_media_key(url)
        if media_key in seen_media:
            continue
        seen_media.add(media_key)
        cleaned.append(image)

    return cleaned[:20]


def extract_description(page_text, seo, schema_product):
    if schema_product.get("description"):
        return schema_product.get("description")
    if seo.get("metaDescription"):
        return seo.get("metaDescription")

    # Remove form-control noise
    cleaned = re.sub(r"quantity\s*\*.*$", "", page_text, flags=re.I)

    sentences = re.split(r"(?<=[.!?])\s+", cleaned)
    good = []
    for s in sentences:
        s = clean_text(s)
        if len(s) < 40:
            continue
        if _is_jina_placeholder(s):
            continue
        if any(k in s.lower() for k in [
            "sort by", "home", "instagram", "subscribe",
            "privacy", "terms", "add to cart", "buy now",
            "quick view", "cookie", "shop", "about"
        ]):
            continue
        good.append(s)

    return " ".join(good[:5])[:2000] if good else None


def extract_options(page_text, wix_attrs):
    """
    Extract selectable product variants (size, color) — NOT form controls or spec dimensions.
    Rules:
    - Skip "quantity" — always a form control, not a product variant
    - Skip Wix attribute sizes that are fixed specs (eyewear dimensions A/B/ED/DBL/TMPL)
    - Only emit size option if standard apparel sizes found (XS/S/M/L/XL) or explicit size list
    - Only emit color option if multiple colors are listed
    """
    options = []
    text_clean = clean_text(page_text)

    # Color — only if multiple colors listed
    color_match = re.search(
        r"(?:color|colour)\s*[*:]\s*([a-zA-Z\s,/|]{3,80})",
        text_clean, re.I
    )
    if color_match:
        raw = clean_text(color_match.group(1))
        values = [clean_text(x) for x in re.split(r",|\|/", raw) if clean_text(x)]
        # Only emit if more than 1 distinct color
        if len(values) > 1:
            options.append({"name": "color", "values": values[:20]})

    # Apparel sizes — only standard size codes, not eyewear dims
    # Skip if wix_attrs has dimension data (eyewear)
    has_eyewear_dims = "dimensions" in wix_attrs
    if not has_eyewear_dims:
        preferred_order = ["XS", "S", "M", "L", "XL", "XXL", "XXXL"]
        size_values = []
        # Must be multi-value: "SIZE XS S M L XL" or "select XS, S, M, L"
        multi_size = re.search(
            r"\bSIZE\s+(?:(XS|S|M|L|XL|XXL|XXXL)\s+){2,}",
            text_clean, re.I
        )
        if multi_size:
            found = re.findall(r"\b(XS|S|M|L|XL|XXL|XXXL)\b", text_clean, re.I)
            size_values = [s.upper() for s in found if s.upper() in set(preferred_order)]
            size_values = [s for s in preferred_order if s in set(size_values)]

        if len(size_values) >= 2:
            options.append({"name": "size", "values": size_values[:20]})

    return options


def extract_category(page_text, product_name, seo, url):
    """
    Infer product category from:
    1. Navigation-style text (short all-caps or title-case words in main text)
    2. Product description keyword matching
    3. URL path segments
    """
    product_lower = (product_name or "").lower()
    desc_lower = page_text.lower()

    # Category keyword → product keyword mapping
    category_map = [
        ("candle", ["candle", "wax", "wick", "fragrance", "burn", "scent"]),
        ("room spray", ["room spray", "room spritz", "spritz"]),
        ("diffuser", ["diffuser", "reed diffuser", "diffus"]),
        ("food & kitchen", ["board", "cheese", "serving", "olivewood", "olive wood", "cutlery", "cookbook", "recipe"]),
        ("baskets", ["basket", "wicker"]),
        ("textiles", ["linen", "towel", "textile", "cloth", "fabric"]),
        ("soaps", ["soap", "hand wash"]),
        ("bath", ["bath", "shower", "lotion", "body"]),
        ("eyewear", ["eyewear", "glasses", "frames", "lens", "optical", "acetate", "saddle bridge"]),
        ("clothing", ["dress", "shirt", "jacket", "pants", "top", "sweater"]),
        ("jewellery", ["jewel", "necklace", "ring", "bracelet", "earring"]),
        ("skincare", ["serum", "moisturiser", "cream", "skin care", "skincare"]),
        ("prints", ["print", "poster", "artwork", "illustration"]),
        ("books", ["book", "cookbook", "guide", "recipe"]),
    ]

    for category, keywords in category_map:
        if any(kw in product_lower or kw in desc_lower for kw in keywords):
            return category.title()

    # Fall back: check short nav-like links in the page text
    nav_candidates = re.findall(
        r"\b(?:Shop|Browse)\s+([A-Z][a-z]{2,20}(?:\s+[A-Z][a-z]{2,20})?)\b",
        page_text
    )
    if nav_candidates:
        return nav_candidates[0]

    # URL path segment
    path_parts = urlparse(url).path.strip("/").split("/")
    for part in path_parts[:-1]:  # exclude the slug itself
        if part and part not in {"product-page", "collection", "collections", "shop", "store"}:
            return part.replace("-", " ").title()

    return None


def _clean_related_name(raw_text, current_product_name=None):
    """
    Clean a related-product link text:
    - Remove "Quick View" prefix
    - Remove stock status ("In Stock", "Out of Stock", "Ready to ship", "NEW!")
    - Remove trailing "Price $X.XX" and beyond
    - Remove "| site-name" suffix
    - Truncate long text at description boundary
    """
    name = clean_text(raw_text or "")
    # Remove Quick View prefix and optional status
    name = re.sub(
        r"^(?:Quick View\s*)?(?:In Stock|Out of Stock|Sold Out|Ready to ship|NEW!)\s*",
        "", name, flags=re.I
    )
    name = re.sub(r"^Quick View\s*", "", name, flags=re.I)
    # Remove price and everything after
    name = re.sub(r"\s+(?:Price\s*)?[$£€]\d+.*$", "", name, flags=re.I)
    name = re.sub(r"\s+Price\b.*$", "", name, flags=re.I)
    # Remove site name suffix
    name = re.sub(r"\s*\|\s*.+$", "", name)
    # Remove description bleed (anything after the first sentence / 140 chars)
    if len(name) > 140:
        name = name[:140].rsplit(" ", 1)[0]
    name = clean_text(name)
    # Reject if same as current product
    if current_product_name and name.lower() == _strip_site_name(current_product_name).lower():
        return None
    return name if len(name) >= 3 else None


def _strip_site_name(text):
    if not text:
        return text
    return re.sub(r"\s*\|\s*.+$", "", text).strip()


def extract_related_products(soup, base_url, current_url, current_product_name=None, page_text=None):
    """
    Extract related/recommended products:
    1. DOM: find /product-page/ links and clean their text
    2. Text: parse "Quick View [Name] Price $X.XX" blocks from recommendation section
    """
    related = []
    seen_urls = set()
    current_url_norm = normalize_url(current_url, base_url)
    clean_current = _strip_site_name(current_product_name or "").lower()

    # DOM pass: /product-page/ links
    for a in soup.select("a[href]"):
        href = a.get("href")
        url = normalize_url(href, base_url)
        if not url or url == current_url_norm:
            continue
        if "/product-page/" not in urlparse(url).path.lower():
            continue
        if url in seen_urls:
            continue

        text = clean_text(a.get_text(" "))
        name = _clean_related_name(text, current_product_name)

        # If name still looks bad, derive from URL slug
        if not name or _is_jina_placeholder(name) or name.lower() in {"quick view", "view", "new!"}:
            name = _slug_to_title(url)

        if not name:
            continue

        # Extract inline price if present
        price_match = re.search(r"([$£€]\s?\d+(?:[,.]\d{1,2})?)", text)
        price = clean_text(price_match.group(1)) if price_match else None

        # Stock status
        stock = None
        text_lower = text.lower()
        if "out of stock" in text_lower or "sold out" in text_lower:
            stock = "out_of_stock"
        elif "in stock" in text_lower or "ready to ship" in text_lower:
            stock = "in_stock"

        seen_urls.add(url)
        related.append({"name": name, "url": url, "price": price, "availability": stock})

    # Text pass: parse Quick View blocks from recommendation section text
    # This catches cases where link text was just "Quick View In Stock"
    if page_text:
        rec_text = page_text
        text_lower = page_text.lower()
        for marker in _RECOMMENDATION_MARKERS:
            pos = text_lower.find(marker)
            if pos > 100:
                rec_text = page_text[pos:]
                break

        qv_pattern = re.compile(
            r"Quick View\s*(?:In Stock|Out of Stock|Sold Out|Ready to ship|NEW!)?\s*"
            r"([A-Z][^$£€\n]{3,120}?)\s+"
            r"(?:Price\s*)?([$£€]\s?\d+(?:[,.]\d{1,2})?)",
            re.I
        )
        for m in qv_pattern.finditer(rec_text):
            name = _clean_related_name(m.group(1), current_product_name)
            price = clean_text(m.group(2)) if m.group(2) else None
            if not name:
                continue
            # Find the URL for this name — look in the related list already extracted
            url = next(
                (r["url"] for r in related
                 if r["name"].lower() in name.lower() or name.lower() in r["name"].lower()),
                None
            )
            if url and url not in seen_urls:
                seen_urls.add(url)
                related.append({"name": name, "url": url, "price": price, "availability": None})
            elif not url:
                # Add without URL
                if name.lower() not in {r["name"].lower() for r in related}:
                    related.append({"name": name, "url": None, "price": price, "availability": None})

    # Final dedup by name
    seen_names = set()
    out = []
    for r in related:
        n_lower = (r.get("name") or "").lower()
        if n_lower in seen_names:
            continue
        if n_lower in {"", "quick view", "view", "new!"}:
            continue
        if clean_current and n_lower == clean_current:
            continue
        seen_names.add(n_lower)
        out.append(r)

    return out[:30]


def extract_ctas(soup, base_url):
    ctas = []
    purchase_keywords = [
        "add to cart", "buy now", "checkout", "cart",
        "notify me", "preorder", "pre-order", "purchase",
        "order now", "get it now", "shop now", "find a store",
        "find a retailer", "store locator", "request a sample"
    ]
    nav_keywords = {"home", "shop", "about", "contact", "blog", "faq", "menu", "search"}

    for node in soup.select("a[href], button"):
        text = clean_text(node.get_text(" "))
        if not text or len(text) > 80:
            continue
        if text.lower() in nav_keywords:
            continue
        if any(k in text.lower() for k in purchase_keywords):
            href = node.get("href")
            ctas.append({
                "text": text,
                "url": normalize_url(href, base_url) if href else None
            })

    return unique_items(ctas, "text")[:30]


def extract_content(soup, base_url):
    main = soup.select_one("main") or soup.body or soup
    headings = []
    for h in main.select("h1, h2, h3, h4"):
        text = clean_text(h.get_text(" "))
        if text and len(text) <= 160:
            headings.append({"level": h.name, "text": text})

    links = []
    for a in main.select("a[href]"):
        text = clean_text(a.get_text(" "))
        href = a.get("href")
        if not text or not href or len(text) > 160:
            continue
        if _is_jina_placeholder(text):
            continue
        links.append({"text": text, "url": normalize_url(href, base_url)})

    return {
        "pageTitle": None,
        "headings": headings[:40],
        "links": unique_items(links, "url")[:80],
        "mainText": clean_text(main.get_text(" "))[:15000]
    }



def _is_zero_price(price_text):
    """Return True if price_text represents a zero / blank price (e.g. '$0.00').

    Wix stores sometimes render $0.00 for unpublished or draft products;
    treat these the same as missing prices.
    """
    if not price_text:
        return False
    cleaned = re.sub(r"[^\d.]", "", str(price_text))
    if not cleaned:
        return False
    try:
        return float(cleaned) == 0.0
    except (ValueError, TypeError):
        return False


def extract_rating_from_text(soup, schema_product=None):
    """Extract aggregate rating from JSON-LD aggregateRating or page text.

    Priority:
    1. schema_product['aggregateRating'] (already parsed JSON-LD)
    2. Text: 'average rating … 4.7'
    3. Text: 'Rating: 4.7'
    4. Text: 'X out of 5' (last non-5.0 match wins)

    Returns dict with 'ratingValue' and 'reviewCount' (either may be None).
    """
    # 1. JSON-LD aggregateRating
    if schema_product:
        agg = schema_product.get("aggregateRating")
        if isinstance(agg, dict):
            rv = agg.get("ratingValue")
            rc = agg.get("reviewCount") or agg.get("ratingCount")
            if rv is not None:
                try:
                    return {
                        "ratingValue": float(rv),
                        "reviewCount": int(rc) if rc is not None else None
                    }
                except (ValueError, TypeError):
                    pass

    text = clean_text(soup.get_text(" ", strip=True))
    review_count = None
    agg_rating = None

    # 2. "X.X average rating" or "average rating … X.X"
    m = re.search(r"(?:^|[^\d])(\d+\.\d{1,2})[^\n]{0,60}?average\s+rating", text, re.I | re.MULTILINE)
    if not m:
        m = re.search(r"average\s+rating[^\n]{0,60}?(\d+\.\d{1,2})", text, re.I)
    if m:
        try:
            agg_rating = float(m.group(1))
        except ValueError:
            pass

    # 3. "Rating: X.X" or "rating X.X"
    if agg_rating is None:
        m = re.search(r"\brating[:\s]+(\d+\.\d{1,2})\b", text, re.I)
        if m:
            try:
                agg_rating = float(m.group(1))
            except ValueError:
                pass

    # Review count
    m2 = re.search(r"average\s+rating\s+based\s+on\s+(\d+)\s+reviews?", text, re.I)
    if not m2:
        m2 = re.search(r"reviews?\s*\((\d+)\)", text, re.I)
    if not m2:
        m2 = re.search(r"(\d{2,})\s+reviews?", text, re.I)
    if m2:
        try:
            review_count = int(m2.group(1))
        except ValueError:
            pass

    if agg_rating is not None:
        return {"ratingValue": agg_rating, "reviewCount": review_count}

    # 4. "X out of 5" fallback — prefer values < 5.0 (not the "5 out of 5" perfect scores)
    all_matches = list(re.finditer(r"([0-5](?:\.\d)?(?:\.\d)?)\s*out\s+of\s*5", text, re.I))
    if all_matches:
        for m in all_matches:
            try:
                val = float(m.group(1))
                if val < 5.0:
                    return {"ratingValue": val, "reviewCount": review_count}
            except ValueError:
                pass
        try:
            return {"ratingValue": float(all_matches[-1].group(1)), "reviewCount": review_count}
        except ValueError:
            pass

    return {"ratingValue": None, "reviewCount": review_count}


def infer_currency_from_url(url):
    """Delegate to shared currency utility (50+ TLDs, path-locale patterns)."""
    from utils.currency import currency_from_url
    return currency_from_url(url)


# ------------------------------------------------------------------
# MAIN ANALYZER
# ------------------------------------------------------------------

def analyze_product(self, url, html, headers, page_type, level1):
    result = self.base_result(url, html, headers, page_type, level1)

    raw_soup = BeautifulSoup(html or "", "lxml")
    content_soup = clean_wix_dom(html)

    result["source"]["extractor"] = "Wix Product Extractor"

    seo = extract_basic_seo(raw_soup, url)
    open_graph = extract_open_graph(raw_soup)
    json_ld_items = extract_json_ld_items(raw_soup)
    schema_product = extract_product_schema(json_ld_items)

    # Full page text for general extraction
    full_page_text = clean_text(content_soup.get_text(" "))

    # Recommendation-trimmed HTML and text for availability / images
    product_html, product_text = _split_at_recommendation_section(
        str(content_soup), full_page_text
    )
    product_soup_trimmed = BeautifulSoup(product_html, "lxml")

    # Product attributes (OGI-style attribute selectors + sections)
    wix_attrs = extract_wix_product_attributes(full_page_text)

    product_name = extract_product_name(seo, open_graph, schema_product, full_page_text)
    brand = extract_brand(full_page_text, seo, schema_product, url)
    pricing = extract_prices(product_text, schema_product, url=url)
    availability = extract_availability(product_text, schema_product, product_html)
    images = extract_product_images(raw_soup, product_soup_trimmed, open_graph, schema_product, url)
    description = extract_description(product_text, seo, schema_product)
    options = extract_options(product_text, wix_attrs)
    ctas = extract_ctas(product_soup_trimmed, url)
    related_products = extract_related_products(
        content_soup, url, url,
        current_product_name=product_name,
        page_text=full_page_text
    )
    content = extract_content(content_soup, url)
    category = extract_category(full_page_text, product_name, seo, url)
    rating = extract_rating_from_text(raw_soup, schema_product)

    page_title = product_name or seo.get("title") or open_graph.get("title")
    content["pageTitle"] = page_title

    has_cart_or_checkout = any(
        k in product_text.lower()
        for k in ["add to cart", "buy now", "checkout", "cart"]
    )

    is_jina = not json_ld_items and len(raw_soup.find_all("script")) <= 2

    # Build product dict — include wix_attrs extras
    product = {
        "name": product_name,
        "url": url,
        "description": description,
        "shortDescription": truncate_words(description, 80),
        "fullDescription": description,
        "category": category,
        "brand": brand,
        "sku": schema_product.get("sku") or _extract_sku(full_page_text),
        "price": pricing.get("price"),
        "priceNormalized": pricing.get("priceNormalized"),
        "regularPrice": pricing.get("regularPrice"),
        "regularPriceNormalized": pricing.get("regularPriceNormalized"),
        "salePrice": pricing.get("salePrice"),
        "salePriceNormalized": pricing.get("salePriceNormalized"),
        "allPricesFound": pricing.get("allPricesFound"),
        "currency": pricing.get("schemaCurrency"),
        "availability": availability,
        "images": images,
        "imageCount": len(images),
        "hasMultipleImages": len(images) > 1,
        "primaryImage": images[0] if images else None,
        "options": options,
        "ctas": ctas,
        "relatedProducts": related_products,
        "schema": schema_product,
        # Wix-specific structured attributes (OGI-style)
        "attributes": wix_attrs if wix_attrs else None,
        "rating": rating if rating.get("ratingValue") is not None else None,
    }

    # URL-based currency inference: fills when schema offers no priceCurrency
    # and the price symbol alone is ambiguous (e.g. '$' on a .ca Wix store)
    if not product.get("currency"):
        _url_currency = infer_currency_from_url(url)
        if _url_currency:
            product["currency"] = _url_currency

    # Promote wix_attrs to top-level product fields for convenience
    for attr_key in ("material", "shape", "color", "collection", "dimensions"):
        val = wix_attrs.get(attr_key)
        if val:
            # Prefer materials_list (full list) over single attr value for material
            if attr_key == "material" and wix_attrs.get("materials_list"):
                val = wix_attrs["materials_list"]
            product[attr_key] = val

    if wix_attrs.get("feature"):
        product["features"] = wix_attrs["feature"]
    if wix_attrs.get("materials_list") and not product.get("material"):
        product["material"] = wix_attrs["materials_list"]

    result["seo"] = seo
    result["openGraph"] = open_graph
    result["product"] = product

    # Populate result["products"] (mirrors the Shopify/WordPress analyzers).
    # Only result["product"] (singular) was set before, so every downstream
    # consumer — accuracy checks, comparison engine, AI payload — saw Wix
    # product pages as having NO product at all.
    _pn = product.get("priceNormalized") if isinstance(product.get("priceNormalized"), dict) else {}
    _price_current = _pn.get("amount")
    if _price_current is None and isinstance(product.get("price"), (int, float)):
        _price_current = product.get("price")
    _plist_imgs = [
        (i.get("url") or i.get("src")) if isinstance(i, dict) else i
        for i in (images or [])
    ]
    _plist_imgs = [i for i in _plist_imgs if isinstance(i, str) and i]
    _plist_entry = {
        **product,
        "productUrl": product.get("url") or url,
        "price": {
            "current": _price_current,
            "currency": _pn.get("currency") or product.get("currency"),
            "priceTextRaw": product.get("price") if not isinstance(product.get("price"), dict) else None,
        },
        "imageUrl": _plist_imgs[0] if _plist_imgs else None,
        "additionalImageUrls": _plist_imgs[1:],
    }
    result["products"] = [_plist_entry] if product.get("name") else []

    result["ecommerce"] = {
        "hasEcommerceSignals": True,
        "featuredProductsCount": 1,
        "featuredProducts": [{
            "name": product.get("name"),
            "url": product.get("url"),
            "price": product.get("price"),
            "priceNormalized": product.get("priceNormalized"),
            "currency": product.get("currency"),
            "availability": product.get("availability"),
            "category": product.get("category"),
            "brand": product.get("brand"),
            "primaryImage": product.get("primaryImage")
        }],
        "hasProductGrid": False,
        "hasCategories": bool(category),
        "hasCartOrCheckout": has_cart_or_checkout
    }

    result["content"] = content
    result["structuredData"] = {
        "jsonLdCount": len(json_ld_items),
        "items": json_ld_items[:20],
        "productSchema": schema_product
    }

    # Confidence scoring
    confidence = 0.40 if is_jina else 0.45
    if product_name:
        confidence += 0.15
    if pricing.get("price"):
        confidence += 0.15
    if images:
        confidence += 0.05
    if has_cart_or_checkout:
        confidence += 0.10
    if schema_product:
        confidence += 0.10
    if description:
        confidence += 0.05
    if brand:
        confidence += 0.05
    if wix_attrs:
        confidence += 0.05

    result["source"]["confidence"] = round(min(max(confidence, 0.35), 0.95), 2)
    return result


def _extract_sku(page_text):
    """Extract SKU from text like 'SKU: VMK-410' or 'SKU VMK-410'."""
    m = re.search(r"\bSKU\s*[:\-]?\s*([A-Za-z0-9\-]+)", page_text, re.I)
    return clean_text(m.group(1)) if m else None
