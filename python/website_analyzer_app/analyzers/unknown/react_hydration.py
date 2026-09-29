import json
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin


PRODUCT_KEYS = [
    "product",
    "products",
    "productcard",
    "productgrid",
    "plp",
    "items",
    "results",
    "merchandise",
    "catalog"
]

NAME_KEYS = [
    "title",
    "name",
    "productName",
    "displayName",
    "label"
]

URL_KEYS = [
    "url",
    "href",
    "pdpUrl",
    "productUrl",
    "canonicalUrl",
    "path"
]

PRICE_KEYS = [
    "price",
    "currentPrice",
    "salePrice",
    "fullPrice",
    "listPrice",
    "formattedPrice",
    "priceText"
]

IMAGE_KEYS = [
    "image",
    "imageUrl",
    "imageURL",
    "src",
    "thumbnail",
    "primaryImage",
    "heroImage"
]


def clean_text(value):
    if value is None:
        return ""

    if isinstance(value, (int, float)):
        return str(value)

    if not isinstance(value, str):
        return ""

    return re.sub(r"\s+", " ", value).strip()


def looks_like_price(value):
    if value is None:
        return False

    text = clean_text(value)

    return bool(
        re.search(r"[$€£]\s?\d+", text)
        or re.search(r"\d+\s?(USD|EUR|GBP|PKR|AED|SAR|INR)", text, re.I)
    )


def normalize_price(value):
    if value is None:
        return None

    if isinstance(value, dict):
        for key in PRICE_KEYS:
            if key in value and value[key]:
                return normalize_price(value[key])

        for key in ["formatted", "display", "value", "amount"]:
            if key in value and value[key]:
                return normalize_price(value[key])

        return None

    if isinstance(value, list):
        for item in value:
            price = normalize_price(item)
            if price:
                return price
        return None

    text = clean_text(value)

    if not text:
        return None

    return text


def normalize_image(value, base_url):
    if value is None:
        return None

    if isinstance(value, dict):
        for key in IMAGE_KEYS:
            if key in value and value[key]:
                return normalize_image(value[key], base_url)

        for key in ["url", "uri", "src"]:
            if key in value and value[key]:
                return normalize_image(value[key], base_url)

        return None

    if isinstance(value, list):
        for item in value:
            img = normalize_image(item, base_url)
            if img:
                return img
        return None

    text = clean_text(value)

    if not text:
        return None

    if text.startswith("//"):
        return "https:" + text

    if text.startswith("/"):
        return urljoin(base_url, text)

    return text


def normalize_url(value, base_url):
    if value is None:
        return None

    if isinstance(value, dict):
        for key in URL_KEYS:
            if key in value and value[key]:
                return normalize_url(value[key], base_url)
        return None

    text = clean_text(value)

    if not text:
        return None

    if text.startswith("//"):
        return "https:" + text

    if text.startswith("/"):
        return urljoin(base_url, text)

    return text


def deep_find_value(obj, keys):
    if isinstance(obj, dict):
        for key in keys:
            if key in obj and obj[key]:
                return obj[key]

        for value in obj.values():
            found = deep_find_value(value, keys)
            if found:
                return found

    elif isinstance(obj, list):
        for item in obj:
            found = deep_find_value(item, keys)
            if found:
                return found

    return None


def is_probable_product(obj):
    if not isinstance(obj, dict):
        return False

    keys = {str(k).lower() for k in obj.keys()}

    has_name = any(k.lower() in keys for k in NAME_KEYS)
    has_url = any(k.lower() in keys for k in URL_KEYS)
    has_price = any(k.lower() in keys for k in PRICE_KEYS)
    has_image = any(k.lower() in keys for k in IMAGE_KEYS)

    if has_name and (has_url or has_price or has_image):
        return True

    text_blob = json.dumps(obj, ensure_ascii=False)[:2500].lower()

    product_words = [
        "productid",
        "stylecolor",
        "currentprice",
        "fullprice",
        "pdp",
        "producturl",
        "imageurl",
        "squarishurl",
        "merchproduct"
    ]

    return has_name and any(word in text_blob for word in product_words)


def normalize_product(obj, base_url):
    if not isinstance(obj, dict):
        return None

    title = deep_find_value(obj, NAME_KEYS)
    url = deep_find_value(obj, URL_KEYS)
    price = deep_find_value(obj, PRICE_KEYS)
    image = deep_find_value(obj, IMAGE_KEYS)

    title = clean_text(title)
    url = normalize_url(url, base_url)
    price = normalize_price(price)
    image = normalize_image(image, base_url)

    if not title:
        return None

    # Avoid false products from filters/nav
    bad_titles = [
        "men",
        "women",
        "kids",
        "sale",
        "new arrivals",
        "best sellers",
        "shoes",
        "clothing",
        "accessories"
    ]

    if title.lower() in bad_titles:
        return None

    if not any([url, price, image]):
        return None

    return {
        "title": title,
        "name": title,
        "url": url,
        "image": image,
        "price": price,
        "allPrices": [price] if price else [],
        "source": "react_hydration"
    }


def walk_json_for_products(obj, base_url, products=None, depth=0):
    if products is None:
        products = []

    if depth > 12:
        return products

    if isinstance(obj, dict):
        if is_probable_product(obj):
            product = normalize_product(obj, base_url)
            if product:
                products.append(product)

        for key, value in obj.items():
            key_l = str(key).lower()

            if any(term in key_l for term in PRODUCT_KEYS):
                walk_json_for_products(value, base_url, products, depth + 1)
            elif isinstance(value, (dict, list)):
                walk_json_for_products(value, base_url, products, depth + 1)

    elif isinstance(obj, list):
        for item in obj:
            walk_json_for_products(item, base_url, products, depth + 1)

    return products


def extract_json_from_script_text(text):
    candidates = []

    text = text.strip()

    if not text:
        return candidates

    # Plain JSON
    if text.startswith("{") or text.startswith("["):
        try:
            candidates.append(json.loads(text))
        except Exception:
            pass

    # window.__STATE__ = {...}
    patterns = [
        r"window\.__INITIAL_STATE__\s*=\s*({.*?});",
        r"window\.__PRELOADED_STATE__\s*=\s*({.*?});",
        r"window\.__APOLLO_STATE__\s*=\s*({.*?});",
        r"window\.__data\s*=\s*({.*?});",
        r"__NEXT_DATA__\s*=\s*({.*?});"
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.S):
            raw = match.group(1)
            try:
                candidates.append(json.loads(raw))
            except Exception:
                continue

    return candidates


def extract_hydration_json_objects(html):
    soup = BeautifulSoup(html or "", "html.parser")
    json_objects = []

    # Next.js
    next_script = soup.find("script", id="__NEXT_DATA__")
    if next_script and next_script.string:
        try:
            json_objects.append(json.loads(next_script.string))
        except Exception:
            pass

    # Remix / React Router / generic JSON scripts
    for script in soup.find_all("script"):
        script_type = (script.get("type") or "").lower()
        script_id = (script.get("id") or "").lower()
        text = script.string or script.get_text() or ""

        if not text or len(text) < 50:
            continue

        _tl = text.lower()
        if (
            "application/json" in script_type
            or "ld+json" in script_type
            or "__next_data__" in script_id
            or "__initial_state__" in _tl
            or "__preloaded_state__" in _tl
            or "currentprice" in _tl
            or "fullprice" in _tl
            or "pdpurl" in _tl
            or "producturl" in _tl
            or ("product" in _tl and ("price" in _tl or "cart" in _tl))
        ):
            json_objects.extend(extract_json_from_script_text(text))

    return json_objects


def dedupe_products(products):
    output = []
    seen = set()

    for product in products:
        title = clean_text(product.get("title") or product.get("name")).lower()
        url = clean_text(product.get("url")).lower()

        key = (title, url)

        if not title:
            continue

        if key in seen:
            continue

        seen.add(key)
        output.append(product)

    return output


def extract_react_hydration_products(html, base_url, limit=60):
    json_objects = extract_hydration_json_objects(html)

    products = []

    for obj in json_objects:
        products.extend(walk_json_for_products(obj, base_url))

    # Deduplicate by URL
    seen = set()
    deduped = []
    for p in products:
        key = (p.get("url") or p.get("productUrl") or "").lower().rstrip("/")
        if key and key not in seen:
            seen.add(key)
            deduped.append(p)
        elif not key:
            deduped.append(p)
    return deduped[:limit]
