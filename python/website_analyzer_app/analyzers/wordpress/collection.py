from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urlunparse
import re
import json

from normalizers.collection_normalizer import normalize_collection_result
from analyzers.pagination_helper import fetch_extra_pages


def clean_text(text):
    return re.sub(r"\s+", " ", text or "").strip()


def unique_items(items, key):
    seen = set()
    output = []

    for item in items:
        value = item.get(key)
        if not value:
            continue
        # Normalise URLs for dedup: strip trailing slash and query string so
        # "https://example.com/product/foo" and ".../foo/" are treated as one.
        norm = value.rstrip("/").split("?")[0] if isinstance(value, str) else value
        if norm in seen:
            continue
        seen.add(norm)
        output.append(item)

    return output


def clean_collection_title(title):
    title = clean_text(title)

    if not title:
        return title

    title = re.sub(
        r"\s+archives\s*[-|]\s*.*$",
        "",
        title,
        flags=re.I
    )

    return clean_text(title)


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
    """Delegate to shared currency utility."""
    from utils.currency import currency_from_url
    return currency_from_url(url) or "USD"


def extract_price_from_text(text):
    text = clean_text(text)

    if not text:
        return None

    variable_price_phrases = [
        "price varies",
        "price variable",
        "variable price",
        "contact for price",
        "call for price",
        "request price",
        "ask for price"
    ]

    if any(phrase in text.lower() for phrase in variable_price_phrases):
        return None

    patterns = [
        r"Current price is:\s*(₨|Rs\.?|PKR)\s*([\d,]+(?:\.\d{2})?)",
        r"Current price is:\s*(\$|£|€|AED)\s*([\d,]+(?:[,.]\d{2})?)",
        r"(₨|Rs\.?|PKR)\s*([\d,]+(?:\.\d{2})?)\s*Current price",
        r"(\$|£|€|AED)\s*([\d,]+(?:[,.]\d{2})?)\s*Current price",
        r"(₨|Rs\.?|PKR)\s*([\d,]+(?:\.\d{2})?)",
        # AED: may appear as "AED 5.00", "5.00 AED", "5.00 AED – 77.00 AED"
        r"(AED)\s*([\d,]+(?:\.\d{2})?)",
        r"([\d,]+(?:\.\d{2})?)\s*(AED)",
        r"(\$|£|€)\s*([\d,]+(?:[,.]\d{2})?)",
        r"([\d,]+(?:[,.]\d{2})?)\s*(€)"
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            value = clean_text(match.group(0))

            if not re.search(r"\d", value):
                return None

            return value

    return None


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
    elif "aed" in raw_lower:
        currency = "AED"
    elif "sar" in raw_lower or "﷼" in raw:
        currency = "SAR"
    elif "inr" in raw_lower or "₹" in raw:
        currency = "INR"
    elif "€" in raw:
        currency = "EUR"
    elif "$" in raw:
        # $ is ambiguous — could be CAD, AUD, NZD, SGD, HKD, PHP, USD.
        # Use URL to disambiguate; fall back to USD if no clear signal.
        currency = _dollar_currency_from_url(page_url)
    elif "£" in raw:
        currency = "GBP"

    cleaned = raw
    cleaned = re.sub(r"current price is:", "", cleaned, flags=re.I)
    cleaned = re.sub(r"original price was:", "", cleaned, flags=re.I)
    cleaned = re.sub(r"(₨|rs\.?|pkr|aed|sar|inr|€|\$|£|₹|﷼)", "", cleaned, flags=re.I)
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
            # Zero is not a valid product price — treat as missing
            if amount == 0.0:
                amount = None
        except Exception:
            amount = None

    return {
        "raw": raw,
        "amount": amount,
        "currency": currency
    }


def clean_products(products, collection_title=None):
    cleaned = []

    normalized_collection_title = clean_text(collection_title or "").lower()

    bad_exact_names = {
        "check",
        "choose an option",
        "read more",
        "wishlist",
        "products",
        "shop",
        "category",
        "archives",
        "product",
        "view product"
    }

    bad_name_contains = [
        "add to cart",
        "quick view",
        "select options",
        "continue shopping"
    ]

    for product in products:
        name = clean_text(product.get("name"))
        url = product.get("url")

        if not name or not url:
            continue

        name_lower = name.lower()

        if normalized_collection_title and name_lower == normalized_collection_title:
            continue

        if name_lower in bad_exact_names:
            continue

        if any(phrase in name_lower for phrase in bad_name_contains):
            continue

        if len(name) <= 2:
            continue

        cleaned.append(product)

    return cleaned


def find_best_product_link(product):
    candidate_links = product.select("a[href]")

    link = None

    for candidate in candidate_links:
        href = candidate.get("href", "").strip()

        if not href:
            continue

        href_lower = href.lower()

        bad_parts = [
            "/product-category/",
            "wishlist",
            "compare",
            "add-to-cart",
            "cart",
            "checkout",
            "my-account",
            "#"
        ]

        if any(part in href_lower for part in bad_parts):
            continue

        if (
            "/product/" in href_lower
            or "/shop/" in href_lower
            or "/store/" in href_lower
            or "/products/" in href_lower
        ):
            link = candidate
            break

    if not link:
        for candidate in candidate_links:
            href = candidate.get("href", "").strip()

            if not href:
                continue

            href_lower = href.lower()

            if any(
                bad in href_lower
                for bad in [
                    "wishlist",
                    "compare",
                    "cart",
                    "checkout",
                    "#"
                ]
            ):
                continue

            link = candidate
            break

    return link


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


# =====================================================================
# Category archive title resolution (Requirement: Mubah Group
# /product-category/ pages where seo.h1 is hijacked by the first
# product's title, e.g. "Air Freshener ASSEL" instead of "Car Care")
# =====================================================================

def extract_breadcrumb_category_title(json_ld_items):
    """
    Find the most specific breadcrumb entry (excluding generic "Home" /
    "Shop" crumbs) from any BreadcrumbList JSON-LD item. This is used to
    recover the true category name on /product-category/ pages.
    """
    flattened = []

    for item in json_ld_items:
        flattened.extend(flatten_json_ld_items(item))

    best_names = []

    for item in flattened:
        item_type = item.get("@type")

        if isinstance(item_type, list):
            item_types = [str(t).lower() for t in item_type]
        else:
            item_types = [str(item_type).lower()] if item_type else []

        if "breadcrumblist" not in item_types:
            continue

        elements = item.get("itemListElement", [])

        if not isinstance(elements, list):
            continue

        positioned = []

        for element in elements:
            if not isinstance(element, dict):
                continue

            position = element.get("position")
            name = element.get("name")

            sub_item = element.get("item")

            if not name and isinstance(sub_item, dict):
                name = sub_item.get("name")

            name = clean_text(name)

            if name:
                positioned.append((
                    position if isinstance(position, int) else len(positioned),
                    name
                ))

        if len(positioned) > len(best_names):
            positioned.sort(key=lambda entry: entry[0])
            best_names = [name for _, name in positioned]

    for name in reversed(best_names):
        if name and name.lower() not in ("home", "shop", "store", "products"):
            return name

    return None


def find_category_archive_title(soup, json_ld_items):
    """
    For WooCommerce /product-category/ pages, find the true category /
    archive title. Prefers, in order:
      1. WooCommerce archive header element in the DOM
      2. Category breadcrumb title (JSON-LD BreadcrumbList)
      3. DOM breadcrumb trail
      4. The heading nearest a "Showing X results" text node
    Returns None if nothing usable is found, so callers can fall back to
    their existing title logic (seo.h1 / og.title / seo.title).
    """
    for selector in [
        ".woocommerce-products-header__title",
        "h1.woocommerce-products-header__title",
        ".page-title.woocommerce-products-header__title",
        ".archive-title",
        "h1.archive-title"
    ]:
        node = soup.select_one(selector)

        if node:
            text = clean_text(node.get_text(" "))

            if text:
                return text

    breadcrumb_title = extract_breadcrumb_category_title(json_ld_items)

    if breadcrumb_title:
        return breadcrumb_title

    for selector in [".woocommerce-breadcrumb", "[class*='breadcrumb']", "nav.breadcrumb"]:
        node = soup.select_one(selector)

        if not node:
            continue

        crumbs = [
            clean_text(part)
            for part in node.get_text("/").split("/")
        ]
        crumbs = [crumb for crumb in crumbs if crumb]

        for crumb in reversed(crumbs):
            if crumb.lower() not in ("home", "shop", "store", "products"):
                return crumb

    showing_node = soup.find(
        string=re.compile(r"showing\s+(?:all\s+)?\d+", re.I)
    )

    if showing_node:
        heading = showing_node.find_previous(["h1", "h2", "h3"])

        if heading:
            text = clean_text(heading.get_text(" "))

            if text and not re.search(r"showing\s+(?:all\s+)?\d+", text, re.I):
                return text

    return None


def extract_products_from_json_ld(json_ld_items, base_url):
    products = []

    flattened = []

    for item in json_ld_items:
        flattened.extend(flatten_json_ld_items(item))

    for item in flattened:
        item_type = item.get("@type")

        if isinstance(item_type, list):
            item_types = [str(t).lower() for t in item_type]
        else:
            item_types = [str(item_type).lower()] if item_type else []

        # ItemList support
        if "itemlist" in item_types:
            elements = item.get("itemListElement", [])

            for element in elements:
                product_item = element.get("item") if isinstance(element, dict) else None

                if not isinstance(product_item, dict):
                    continue

                product = build_product_from_schema(product_item, base_url)

                if product:
                    products.append(product)

        # Direct Product support
        if "product" in item_types:
            product = build_product_from_schema(item, base_url)

            if product:
                products.append(product)

    return unique_items(products, "url")


def build_product_from_schema(item, base_url):
    name = clean_text(item.get("name"))
    product_url = normalize_url(item.get("url"), base_url)

    if not name or not product_url:
        return None

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

    price = None
    currency = None
    availability = None

    if isinstance(offers, dict):
        price = offers.get("price")
        currency = offers.get("priceCurrency")
        availability = offers.get("availability")

    price_text_raw = None

    if price is not None:
        price_text_raw = str(price)

        if currency == "USD":
            price_text_raw = f"$ {price}"
        elif currency == "GBP":
            price_text_raw = f"£ {price}"
        elif currency == "EUR":
            price_text_raw = f"{price} €"
        elif currency == "PKR":
            price_text_raw = f"₨ {price}"

    price_normalized = normalize_price(price_text_raw, page_url=base_url)

    if currency and price_normalized.get("currency") is None:
        price_normalized["currency"] = currency

    availability_normalized = None

    if availability:
        availability_lower = str(availability).lower()

        if "outofstock" in availability_lower or "out_of_stock" in availability_lower:
            availability_normalized = "out_of_stock"
        elif "instock" in availability_lower or "in_stock" in availability_lower:
            availability_normalized = "in_stock"
        elif "backorder" in availability_lower:
            availability_normalized = "backorder"
        else:
            availability_normalized = availability

    return {
        "name": name,
        "url": product_url,
        "price": price_text_raw,
        "priceTextRaw": price_text_raw,
        "priceNormalized": price_normalized,
        "image": image,
        "imageUrl": image,
        "shortDescription": clean_text(item.get("description"))[:200] or None,
        "saleBadge": False,
        "availability": availability_normalized,
        "source": "jsonld"
    }


def merge_products(jsonld_products, dom_products):
    merged = {}

    for product in dom_products:
        url = product.get("url")

        if not url:
            continue

        merged[url] = product

    for product in jsonld_products:
        url = product.get("url")

        if not url:
            continue

        if url not in merged:
            merged[url] = product
            continue

        existing = merged[url]

        # Prefer JSON-LD price if available
        if product.get("priceNormalized", {}).get("amount") is not None:
            existing["price"] = product.get("price")
            existing["priceTextRaw"] = product.get("priceTextRaw")
            existing["priceNormalized"] = product.get("priceNormalized")

        # Prefer DOM image if JSON-LD image missing, otherwise keep existing
        if not existing.get("image") and product.get("image"):
            existing["image"] = product.get("image")
            existing["imageUrl"] = product.get("imageUrl") or product.get("image")

        existing.setdefault("imageUrl", existing.get("image"))

        if not existing.get("shortDescription") and product.get("shortDescription"):
            existing["shortDescription"] = product.get("shortDescription")

        if product.get("availability") and not existing.get("availability"):
            existing["availability"] = product.get("availability")

        existing["source"] = "merged"

        merged[url] = existing

    return list(merged.values())


# =====================================================================
# Error page guard (Requirement 1)
# =====================================================================

def is_error_page(result, headers):
    """
    Detect error / dead-link pages so product/collection extraction is skipped.

    Triggers when:
      - crawl statusCode is 404, OR
      - SEO title contains "page not found", OR
      - SEO H1 contains "dead link"
    """
    headers = headers or {}

    status_code = (
        headers.get("status_code")
        or headers.get("statusCode")
        or headers.get("Status-Code")
        or (result.get("crawl") or {}).get("statusCode")
    )

    try:
        status_code = int(status_code) if status_code is not None else None
    except Exception:
        status_code = None

    seo = result.get("seo") or {}
    title = (seo.get("title") or "").lower()
    h1 = (seo.get("h1") or "").lower()

    if status_code == 404:
        return True

    if "page not found" in title:
        return True

    if "dead link" in h1:
        return True

    return False


def build_error_result(result, soup):
    """
    Build a minimal "error" page result. Skips product and collection
    extraction entirely.
    """
    result["page"]["pageType"] = "error"
    result["success"] = False
    result["products"] = []

    empty_stats = {
        "productCount": 0,
        "productsWithPrices": 0,
        "productsWithoutPrices": 0,
        "productsWithImages": 0,
        "priceRange": {"min": None, "max": None, "currency": None},
        "availabilityBreakdown": {"inStock": 0, "outOfStock": 0, "unknown": 0}
    }

    result["ecommerce"] = {
        "hasProducts": False,
        "productCount": 0,
        "products": [],
        "categoryLinks": [],
        "hasSorting": False,
        "hasFilters": False,
        "saleProductsCount": 0,
        "productStats": empty_stats,
        "priceRange": empty_stats["priceRange"],
        "availabilityStats": empty_stats["availabilityBreakdown"],
        "productsWithImagesCount": 0,
        "pagination": {
            "detected": False,
            "totalProductsText": None,
            "pageLinks": [],
            "currentlyFetchedProducts": 0,
            "fullCatalogFetched": True
        }
    }

    body_text = ""

    if soup is not None:
        body_text = clean_text((soup.body or soup).get_text(" "))[:5000]

    result["content"] = {
        "collectionTitle": None,
        "collectionName": None,
        "mainText": body_text,
        "sortingOptions": [],
        "filters": [],
        "rawPossibleFilters": []
    }

    result["collectionSummary"] = None

    result["structuredData"] = {
        "jsonLdCount": 0,
        "items": [],
        "productsExtracted": 0
    }

    result["source"]["confidence"] = 0.3

    return result


# =====================================================================
# WooCommerce category priority detection (Requirement 2)
# =====================================================================

def is_woocommerce_collection_page(url, html, headers=None):
    """
    Detect WooCommerce/WordPress product-category (collection) pages, even
    when they were initially classified as a blog listing or general page.

    Returns True when ANY of the following hold:
      - URL contains "/product-category/"
      - response Link header references wp/v2/product_cat
      - page text contains "Showing all X results" / "Showing X-Y of Z results"
      - repeated "View Product" CTAs alongside multiple product links
        (e.g. BWT Pools "/category/..." pages)
    """
    url_lower = (url or "").lower()

    if "/product-category/" in url_lower:
        return True

    headers = headers or {}

    link_header = ""

    for key in ("Link", "link"):
        value = headers.get(key)
        if value:
            link_header += " " + str(value)

    technical_headers = headers.get("responseHeaders") if isinstance(headers, dict) else None

    if isinstance(technical_headers, dict):
        for key in ("Link", "link"):
            value = technical_headers.get(key)
            if value:
                link_header += " " + str(value)

    if "wp/v2/product_cat" in link_header:
        return True

    soup = BeautifulSoup(html or "", "lxml")
    page_text = clean_text(soup.get_text(" "))

    if re.search(r"showing\s+all\s+\d+\s+results", page_text, re.I):
        return True

    if re.search(r"showing\s+\d+\s*[–‐-]\s*\d+\s+of\s+\d+\s+results", page_text, re.I):
        return True

    view_product_count = len(re.findall(r"\bview product\b", page_text, re.I))

    product_links = soup.select(
        "a[href*='/product/'], a[href*='/products/'], a[href*='/shop/']"
    )

    if view_product_count >= 3 and len(product_links) >= 3:
        return True

    return False


# =====================================================================
# Price-less product card fallback (Requirement 3)
# =====================================================================

CTA_NOISE_PATTERN = re.compile(
    r"\b(view product|add to cart|select options|read more|quick view|"
    r"add to quickview|quickview|compare|wishlist|sale!?|choose an option|"
    r"add to wishlist|buy now|out of stock|in stock|on backorder)\b",
    re.I
)

# WooCommerce quickview block noise — longer phrases that appear verbatim
# in the card text when the Quickview plugin is active (e.g. mubahmart.com).
# These include the "Available Variations" banner and the variant-picker hint.
# "Available Variations: One Piece - 6.00 AED Box - 260.00 AED ..." may have
# multiple variation+price pairs; consume everything from the anchor to end of
# string so no second pair (e.g. "Box - 260.00 AED") leaks into shortDescription.
_WC_QUICKVIEW_NOISE_RE = re.compile(
    r"available variations\s*:.*",
    re.I | re.S
)
# Fallback: remove the variant-picker hint even when "Available Variations:"
# is absent (some Quickview themes render only the hint, not the list).
_WC_VARIANT_HINT_RE = re.compile(
    r"this product has multiple variants?\.?\s*the options? may be chosen on the\b.*",
    re.I | re.S
)


def extract_view_product_cards(soup, base_url):
    """
    Fallback extraction for collection pages whose product cards are not
    matched by the standard WooCommerce ".products li.product" selectors,
    but which repeat a "View Product" CTA next to each product link
    (e.g. BWT Pools category pages). Extracts name/url/image/shortDescription
    even when no price is present.
    """
    products = []
    seen_urls = set()

    candidates = soup.find_all(
        lambda tag: tag.name in ("li", "div", "article")
        and "view product" in clean_text(tag.get_text(" ")).lower()
    )

    for card in candidates:
        text = clean_text(card.get_text(" "))
        text_lower = text.lower()

        if "view product" not in text_lower:
            continue

        # Skip large wrapper containers that hold multiple cards
        if text_lower.count("view product") > 1:
            continue

        link = find_best_product_link(card)

        if not link:
            continue

        href = link.get("href")

        if not href:
            continue

        full_url = normalize_url(href, base_url)

        if not full_url or full_url in seen_urls:
            continue

        name = None

        for selector in [
            "h1", "h2", "h3", "h4",
            "[class*='title']",
            "[class*='name']",
            "a[title]"
        ]:
            found = card.select_one(selector)

            if found:
                if selector == "a[title]":
                    name_text = clean_text(found.get("title", ""))
                else:
                    name_text = clean_text(found.get_text(" "))

                if len(name_text) > 2 and "view product" not in name_text.lower():
                    name = name_text
                    break

        if not name:
            name = clean_text(link.get_text(" "))
            name = CTA_NOISE_PATTERN.sub("", name)
            name = clean_text(name)

        if not name or len(name) <= 2:
            continue

        image = None
        img = card.find("img")

        if img:
            image = (
                img.get("data-src")
                or img.get("data-lazy-src")
                or img.get("data-original")
                or img.get("src")
            )

            if image and image.startswith("data:image"):
                image = None

            if image:
                image = normalize_url(image, base_url)

        # Short description: whatever text remains once the name and CTA
        # noise are stripped out (e.g. "For pools up to 15 metres")
        remainder = CTA_NOISE_PATTERN.sub("", text)

        if name:
            remainder = re.sub(re.escape(name), "", remainder, count=1, flags=re.I)

        remainder = clean_text(remainder)

        short_description = remainder if 2 < len(remainder) <= 200 else None

        price_text_raw = extract_price_from_text(text)
        price_normalized = normalize_price(price_text_raw, page_url=base_url)

        seen_urls.add(full_url)

        products.append({
            "name": name,
            "url": full_url,
            "price": price_text_raw,
            "priceTextRaw": price_text_raw,
            "priceNormalized": price_normalized,
            "image": image,
            "imageUrl": image,
            "shortDescription": short_description,
            "saleBadge": False,
            "availability": None,
            "source": "view_product_fallback"
        })

    return products


# =====================================================================
# Collection stats (Requirement 5)
# =====================================================================

def compute_collection_stats(products):
    """
    Compute aggregate stats over a collection's products:
      - productStats (counts, priceRange)
      - availabilityStats
      - productsWithImagesCount
    Products with price=None are still counted as valid products.
    """
    total_products = len(products)

    products_with_prices = 0
    products_with_images = 0
    amounts = []
    currencies = []
    availability_counts = {"inStock": 0, "outOfStock": 0, "unknown": 0}

    for product in products:
        price_normalized = product.get("priceNormalized") or {}
        amount = price_normalized.get("amount")

        if amount is not None:
            products_with_prices += 1
            amounts.append(amount)

            currency = price_normalized.get("currency")
            if currency:
                currencies.append(currency)

        if product.get("image") or product.get("imageUrl"):
            products_with_images += 1

        availability = product.get("availability")

        if availability == "in_stock":
            availability_counts["inStock"] += 1
        elif availability == "out_of_stock":
            availability_counts["outOfStock"] += 1
        else:
            availability_counts["unknown"] += 1

    price_range = {
        "min": min(amounts) if amounts else None,
        "max": max(amounts) if amounts else None,
        "currency": currencies[0] if currencies else None
    }

    product_stats = {
        "productCount": total_products,
        "productsWithPrices": products_with_prices,
        "productsWithoutPrices": total_products - products_with_prices,
        "productsWithImages": products_with_images,
        "priceRange": price_range,
        "availabilityBreakdown": availability_counts
    }

    return product_stats, price_range, availability_counts, products_with_images


# =====================================================================
# Collection Text Parser fallback (Requirement: collections with
# productCount=0 whose visible text repeats "[Product Name]
# [Currency Symbol][Price]" pairs, e.g. size-assets.com/product-category/
# bundles/ - "Basement Beats Bundle € 99"). Covers Elementor loops,
# Bricks Builder loops, custom WooCommerce templates and headless-style
# collections that don't use standard WooCommerce product-card markup.
# =====================================================================

COLLECTION_TEXT_ITEM_PATTERN = re.compile(
    r"^(?P<name>.{2,120}?)\s+"
    r"(?P<price>"
    r"(?:[$€£¥₹₦₨₩]\s?\d[\d,]*(?:\.\d{1,2})?)"
    r"|(?:Rs\.?|PKR|AED|USD|EUR|GBP)\s?\d[\d,]*(?:\.\d{1,2})?"
    r"|\d[\d,]*(?:\.\d{1,2})?\s?[$€£¥₹₦₨₩]"
    r")$",
    re.IGNORECASE
)

# Body-text collection pattern: scans the raw page text string for repeating
# "Product Name [Currency][Price]" pairs.  Used when per-element DOM scanning
# yields 0 products because cards have trailing noise text after the price
# (e.g. "Basement Beats Bundle € 99 Add to wishlist").
_COLLECTION_BODY_TEXT_PATTERN = re.compile(
    r"(?P<name>[A-ZÀ-ÖĀ-ſ\d][^\n€$£¥₹₦₨₩\d.!?]{2,80}?)"
    r"\s+(?P<price>"
    r"(?:[$€£¥₹₦₨₩]\s?\d[\d,]*(?:\.\d{1,2})?)"
    r"|(?:Rs\.?|PKR|AED|USD|EUR|GBP)\s?\d[\d,]*(?:\.\d{1,2})?"
    r"|\d[\d,]*(?:\.\d{1,2})?\s?[$€£¥₹₦₨₩]"
    r")(?=\s|$)",
    re.IGNORECASE | re.UNICODE
)


def find_nearest_product_link(el, base_url):
    """
    Find the closest <a href> for a product name/price element: first
    check the element itself and its descendants, then walk up a few
    ancestor levels (e.g. an Elementor/Bricks loop-item wrapper).
    """
    if el.name == "a" and el.get("href"):
        return normalize_url(el["href"], base_url)

    found = el.find("a", href=True)

    if found:
        return normalize_url(found["href"], base_url)

    node = el

    for _ in range(6):
        node = node.parent

        if node is None or node.name in ("body", "html", "[document]"):
            break

        found = node.find("a", href=True)

        if found:
            return normalize_url(found["href"], base_url)

    return None


def find_nearest_product_image(el, base_url):
    """
    Find the closest <img> for a product name/price element, walking up
    a few ancestor levels if needed (mirrors find_nearest_product_link).
    """
    node = el

    for _ in range(7):
        if node is None or node.name in ("body", "html", "[document]"):
            break

        img = node.find("img")

        if img:
            src = (
                img.get("data-src")
                or img.get("data-lazy-src")
                or img.get("data-original")
                or img.get("src")
            )

            if src and src.startswith("data:image"):
                src = None

            if src:
                if "," in src and "http" in src:
                    src = src.split(",")[0].split(" ")[0]

                return normalize_url(src, base_url)

        node = node.parent

    return None


def extract_collection_text_fallback(content_node, base_url, collection_title=None):
    """
    Parse repeating "[Product Name] [Currency Symbol][Price]" text pairs
    (e.g. "Basement Beats Bundle € 99") into product entries. Only
    intended to run when standard DOM, JSON-LD and "View Product"
    extraction all returned zero products.
    """
    if content_node is None:
        return []

    normalized_collection_title = clean_text(collection_title or "").lower()

    matches = []
    match_elements = set()

    for el in content_node.find_all(True):
        if el.name in ("script", "style", "noscript"):
            continue

        text = clean_text(el.get_text(" "))

        if not text:
            continue

        match = COLLECTION_TEXT_ITEM_PATTERN.match(text)

        if not match:
            continue

        name = clean_text(match.group("name"))
        price_text = clean_text(match.group("price"))

        if not name or len(name) < 2:
            continue

        # A "name" that itself contains a price means this element wraps
        # multiple name/price pairs, not a single item.
        if extract_price_from_text(name) is not None:
            continue

        if CTA_NOISE_PATTERN.search(name.lower()):
            continue

        if re.search(r"showing\s+(?:all\s+)?\d+", name, re.I):
            continue

        if normalized_collection_title and name.lower() == normalized_collection_title:
            continue

        matches.append((el, name, price_text))
        match_elements.add(el)

    # Keep only the innermost matching element for each pair (an outer
    # wrapper with no other text would also match the same pattern).
    filtered = []

    for el, name, price_text in matches:
        if any(desc in match_elements for desc in el.find_all(True)):
            continue

        filtered.append((el, name, price_text))

    products = []
    seen_names = set()

    for el, name, price_text in filtered:
        key = name.lower()

        if key in seen_names:
            continue

        seen_names.add(key)

        price_normalized = normalize_price(price_text, page_url=base_url)
        link = find_nearest_product_link(el, base_url)
        image = find_nearest_product_image(el, base_url)

        products.append({
            "name": name,
            "url": link,
            "price": price_text,
            "priceTextRaw": price_text,
            "priceNormalized": price_normalized,
            "image": image,
            "imageUrl": image,
            "shortDescription": None,
            "saleBadge": False,
            "availability": None,
            "source": "collection_text_fallback"
        })

    return products


def extract_collection_body_text_products(body_text, base_url, collection_title=None):
    """
    Secondary body-text fallback: scan the raw page text string for repeating
    "Product Name [Currency][Price]" pairs.  Used when per-element DOM scanning
    yields too few results because product cards have trailing noise text after
    the price (e.g. "Basement Beats Bundle € 99 Add to wishlist"), which breaks
    the end-anchored COLLECTION_TEXT_ITEM_PATTERN.
    """
    if not body_text:
        return []

    normalized_title = clean_text(collection_title or "").lower()
    products = []
    seen_names = set()

    for m in _COLLECTION_BODY_TEXT_PATTERN.finditer(body_text):
        name = clean_text(m.group("name")).strip(" -–•→")
        price_text = clean_text(m.group("price"))

        if not name or len(name) < 3 or len(name) > 100:
            continue

        if CTA_NOISE_PATTERN.search(name.lower()):
            continue

        if normalized_title and name.lower() == normalized_title:
            continue

        if re.search(r"showing\s+(?:all\s+)?\d+", name, re.I):
            continue

        key = name.lower()
        if key in seen_names:
            continue
        seen_names.add(key)

        price_normalized = normalize_price(price_text, page_url=base_url)
        products.append({
            "name": name,
            "url": None,
            "price": price_text,
            "priceTextRaw": price_text,
            "priceNormalized": price_normalized,
            "image": None,
            "imageUrl": None,
            "shortDescription": None,
            "saleBadge": False,
            "availability": None,
            "source": "collection_body_text_fallback"
        })

    return products[:30]


def _page_products(html, url, collection_title):
    """Compact product extraction for follow-up pagination pages (JSON-LD +
    standard WooCommerce product cards). Reuses this module's helpers so pages
    2..N are parsed the same way page 1 is, then merged by the caller."""
    soup = BeautifulSoup(html or "", "lxml")

    json_ld_items = extract_json_ld_items(soup)
    jsonld_products = extract_products_from_json_ld(json_ld_items, url)

    dom_products = []
    for product in soup.select(
        "li.product, .product, .woocommerce-loop-product, .products li, "
        "ul.products li, article.product, .wc-block-grid__product, "
        "[data-product-id], [class*='product-item'], [class*='product-card']"
    ):
        product_text = clean_text(product.get_text(" "))
        if len(product_text) < 20:
            continue
        link = find_best_product_link(product)
        if not link:
            continue
        href = link.get("href")
        if not href:
            continue
        full_url = normalize_url(href, url)

        name = None
        for selector in [
            ".woocommerce-loop-product__title", ".product-title", ".product-name",
            ".product-card__title", ".wc-block-grid__product-title",
            "[class*='product-title']", "[class*='product-name']", "h2", "h3", "a[title]",
        ]:
            found = product.select_one(selector)
            if found:
                text = (clean_text(found.get("title", "")) if selector == "a[title]"
                        else clean_text(found.get_text(" ")))
                if len(text) > 2:
                    name = text
                    break
        if not name:
            name = clean_text(link.get_text(" "))
        if not name:
            continue
        name = clean_text(re.sub(
            r"\b(add to cart|quick view|wishlist|compare|choose an option|read more|check)\b",
            "", name, flags=re.I,
        ))
        if not name:
            continue

        price_raw = extract_price_from_text(product_text)
        price_norm = normalize_price(price_raw, page_url=url)

        image = None
        img = product.find("img")
        if img:
            image = (img.get("data-src") or img.get("data-lazy-src")
                     or img.get("data-original") or img.get("src"))
            if image and image.startswith("data:image"):
                image = None
            if image:
                if "," in image and "http" in image:
                    image = image.split(",")[0].split(" ")[0]
                image = normalize_url(image, url)

        text_l = product_text.lower()
        sale_badge = any(x in text_l for x in
                         ["sale", "discount", "%", "current price is", "original price was"])

        availability = None
        node_classes = " ".join(product.get("class", [])).lower()
        if "outofstock" in node_classes:
            availability = "out_of_stock"
        elif "instock" in node_classes:
            availability = "in_stock"
        elif "onbackorder" in node_classes:
            availability = "backorder"
        if availability is None:
            if "out of stock" in text_l or "sold out" in text_l:
                availability = "out_of_stock"
            elif "add to cart" in text_l or "in stock" in text_l:
                availability = "in_stock"

        dom_products.append({
            "name": name, "url": full_url, "price": price_raw,
            "priceTextRaw": price_raw, "priceNormalized": price_norm,
            "image": image, "imageUrl": image, "shortDescription": None,
            "saleBadge": sale_badge, "availability": availability,
            "source": "dom_paginated",
        })

    dom_products = unique_items(dom_products, "url")
    merged = merge_products(jsonld_products, dom_products)
    merged = clean_products(merged, collection_title)
    return unique_items(merged, "url")


def analyze_collection(self, url, html, headers, page_type, level1):

    result = self.base_result(
        url,
        html,
        headers,
        page_type,
        level1
    )

    soup = BeautifulSoup(html or "", "lxml")

    result["source"]["extractor"] = "WordPress Collection Extractor"

    # ---------------------------------------------------
    # Error page guard (Requirement 1)
    # ---------------------------------------------------

    if is_error_page(result, headers):
        return build_error_result(result, soup)

    # ---------------------------------------------------
    # JSON-LD
    # ---------------------------------------------------

    json_ld_items = extract_json_ld_items(soup)
    jsonld_products = extract_products_from_json_ld(json_ld_items, url)

    # ---------------------------------------------------
    # Clean DOM
    # ---------------------------------------------------

    soup_for_content = BeautifulSoup(html or "", "lxml")

    for selector in [
        "script",
        "style",
        "noscript",
        "iframe",
        "header",
        "footer",
        "nav",
        "aside",
        "form",

        ".header",
        ".footer",
        ".site-header",
        ".site-footer",
        ".announcement-bar",
        ".newsletter",
        ".popup",
        ".modal",
        ".drawer",
        ".cart-drawer",
        ".menu-drawer",
        ".search-modal",
        ".breadcrumb",
        ".breadcrumbs",
        ".social-share",
        ".pagination",

        "[class*='newsletter']",
        "[class*='popup']",
        "[class*='announcement']",
        "[class*='breadcrumb']",
        "[class*='social']",
        "[class*='share']"
    ]:
        for node in soup_for_content.select(selector):
            node.decompose()

    # ---------------------------------------------------
    # Main collection container
    # ---------------------------------------------------

    possible_containers = []

    priority_selectors = [
        ".products",
        ".woocommerce",
        ".woocommerce-products",
        ".products-grid",
        ".product-grid",
        "main",
        "#main",
        "#MainContent",
        ".archive",
        ".shop-container"
    ]

    for selector in priority_selectors:
        for node in soup_for_content.select(selector):
            text = clean_text(node.get_text(" "))

            if len(text) < 100:
                continue

            score = len(text)

            class_text = " ".join(
                node.get("class", [])
            ).lower()

            if "product" in class_text:
                score += 3000

            if "woocommerce" in class_text:
                score += 2500

            if "grid" in class_text:
                score += 1500

            possible_containers.append(
                (node, score)
            )

    if possible_containers:
        content_node = sorted(
            possible_containers,
            key=lambda x: x[1],
            reverse=True
        )[0][0]
    else:
        content_node = soup_for_content.body or soup_for_content

    # ---------------------------------------------------
    # Collection title
    # ---------------------------------------------------

    collection_title = (
        result.get("seo", {}).get("h1")
        or result.get("openGraph", {}).get("title")
        or result.get("seo", {}).get("title")
    )

    # Requirement: on /product-category/ pages some themes render the page
    # H1 as the first product's title instead of the actual category name
    # (e.g. Mubah Group h1="Air Freshener ASSEL" instead of "Car Care").
    # Prefer the WooCommerce archive title / category breadcrumb /
    # "Showing X results" heading over that H1 in that case.
    if "/product-category/" in (url or "").lower():
        archive_title = find_category_archive_title(soup, json_ld_items)

        # Derive the seo.title first segment now — used both for validation and
        # as the fallback when archive_title is rejected.
        _seo_title_raw = clean_text(result.get("seo", {}).get("title") or "")
        _seo_title_segment = ""
        if _seo_title_raw:
            _seo_title_segment = re.sub(
                r"\s*[\|–\-]\s*[^|–\-]+$", "", _seo_title_raw
            ).strip()

        if archive_title:
            # --- Reject product-name H1s masquerading as category titles ---
            #
            # Pattern 1: product SKU / code  (e.g. "HN -18", "SKU-04", "ABC-123")
            _PRODUCT_CODE_RE = re.compile(r"^[A-Z]{1,5}\s*[-–]\s*\d+\s*$", re.I)
            _is_sku = bool(_PRODUCT_CODE_RE.match(archive_title.strip()))

            # Pattern 2: archive title and seo.title first segment differ
            # substantially AND the seo segment is a plausible category name.
            # When a theme puts a product name in the H1 the seo.title will
            # reflect the actual category (it's set by WordPress/Yoast).
            # We compare case-insensitively and only reject if the seo segment
            # is at least 3 chars and doesn't share the archive title as a
            # prefix/substring (so "Press on Gel Nails" passes when both
            # sources agree, but "Air Freshener ASSEL" is rejected when the
            # seo says "Car Care").
            _seo_seg_lower = _seo_title_segment.lower().strip()
            _arc_lower = archive_title.lower().strip()
            _is_h1_product_name = (
                len(_seo_seg_lower) >= 3
                and _seo_seg_lower not in ("shop", "store", "home", "products")
                and _arc_lower not in _seo_seg_lower        # archive not inside seo
                and _seo_seg_lower not in _arc_lower        # seo not inside archive
                and not _arc_lower.startswith(_seo_seg_lower[:6])  # no common prefix
            )

            if _is_sku or _is_h1_product_name:
                archive_title = None

        if archive_title:
            collection_title = archive_title
        elif _seo_title_segment and _seo_title_segment.lower() not in (
            "shop", "store", "home", "products"
        ):
            # find_category_archive_title() found nothing usable — fall back to
            # the seo.title first segment, which is almost always the true
            # category name ("Press on Gel Nails – Happy Nails" → "Press on Gel Nails").
            collection_title = _seo_title_segment

    collection_title = clean_collection_title(collection_title)

    # ---------------------------------------------------
    # Main text
    # ---------------------------------------------------

    body_text = clean_text(
        content_node.get_text(" ")
    )

    bad_phrases = [
        "skip to content",
        "continue shopping",
        "my account",
        "bag(0)"
    ]

    for phrase in bad_phrases:
        body_text = re.sub(
            re.escape(phrase),
            "",
            body_text,
            flags=re.I
        )

    body_text = clean_text(body_text)

    # ---------------------------------------------------
    # DOM Products
    # ---------------------------------------------------

    dom_products = []

    product_nodes = soup.select(
        """
        li.product,
        .product,
        .woocommerce-loop-product,
        .products li,
        ul.products li,
        article.product,
        .wc-block-grid__product,
        [data-product-id],
        [class*='product-grid'] article,
        [class*='product-item'],
        [class*='product-card']
        """
    )

    for product in product_nodes:
        product_text = clean_text(
            product.get_text(" ")
        )

        if len(product_text) < 20:
            continue

        link = find_best_product_link(product)

        if not link:
            continue

        href = link.get("href")

        if not href:
            continue

        full_url = normalize_url(href, url)

        product_name = None

        for selector in [
            ".woocommerce-loop-product__title",
            ".product-title",
            ".product-name",
            ".product-card__title",
            ".wc-block-grid__product-title",

            "[class*='product-title']",
            "[class*='product-name']",
            "[class*='card-title']",
            "[class*='loop-product']",

            "h1",
            "h2",
            "h3",
            "h4",

            "a[title]"
        ]:
            found = product.select_one(selector)

            if found:
                if selector == "a[title]":
                    text = clean_text(
                        found.get("title", "")
                    )
                else:
                    text = clean_text(
                        found.get_text(" ")
                    )

                if len(text) > 2:
                    product_name = text
                    break

        if not product_name:
            product_name = clean_text(link.get_text(" "))

        if not product_name:
            continue

        product_name = re.sub(
            r"\b(add to cart|quick view|wishlist|compare|choose an option|read more|check)\b",
            "",
            product_name,
            flags=re.I
        )

        product_name = clean_text(product_name)

        if not product_name:
            continue

        price_text_raw = extract_price_from_text(product_text)
        price = price_text_raw

        if not price and product_name:
            # Use a tight 150-char window so we don't bleed into the next
            # product card and pick up its price instead.
            nearby_match = re.search(
                re.escape(product_name) + r".{0,150}",
                body_text,
                re.I
            )

            if nearby_match:
                price_text_raw = extract_price_from_text(nearby_match.group(0))
                price = price_text_raw

        if price and not re.search(r"\d", price):
            price = None
            price_text_raw = None

        price_normalized = normalize_price(price_text_raw)

        image = None

        img = product.find("img")

        if img:
            image = (
                img.get("data-src")
                or img.get("data-lazy-src")
                or img.get("data-original")
                or img.get("src")
            )

            if image and image.startswith("data:image"):
                image = None

            if image:
                if "," in image and "http" in image:
                    image = image.split(",")[0].split(" ")[0]

                image = normalize_url(image, url)

        sale_badge = False
        sale_text = product_text.lower()

        if (
            "sale" in sale_text
            or "discount" in sale_text
            or "%" in sale_text
            or "current price is" in sale_text
            or "original price was" in sale_text
        ):
            sale_badge = True

        # ---------------------------------------------------
        # Availability (WooCommerce stock-status classes / text)
        # ---------------------------------------------------

        availability = None

        # 1. Check <li>/card-root classes (standard WooCommerce stock-status)
        node_classes = " ".join(product.get("class", [])).lower()

        if "outofstock" in node_classes:
            availability = "out_of_stock"
        elif "instock" in node_classes:
            availability = "in_stock"
        elif "onbackorder" in node_classes:
            availability = "backorder"

        # 2. Check descendant .stock elements (some themes put the badge inside)
        if availability is None:
            for stock_el in product.select(".stock, [class*='stock-status'], [class*='stock_status']"):
                el_classes = " ".join(stock_el.get("class", [])).lower()
                el_text = clean_text(stock_el.get_text(" ")).lower()
                if "out-of-stock" in el_classes or "outofstock" in el_classes or "out of stock" in el_text or "sold out" in el_text:
                    availability = "out_of_stock"
                    break
                elif "in-stock" in el_classes or "instock" in el_classes or "in stock" in el_text:
                    availability = "in_stock"
                    break
                elif "backorder" in el_classes or "on backorder" in el_text or "available on backorder" in el_text:
                    availability = "backorder"
                    break

        # 3. Text signals from the card's full text
        if availability is None:
            if "out of stock" in sale_text or "sold out" in sale_text:
                availability = "out_of_stock"
            elif "in stock" in sale_text:
                availability = "in_stock"

        # 4. "Add to cart" button implies the product is purchasable / in stock
        if availability is None and "add to cart" in sale_text:
            availability = "in_stock"

        # ---------------------------------------------------
        # Short description (e.g. "For pools up to 15 metres")
        # Whatever remains of the card text once the name, price
        # and CTA noise are stripped out.
        # ---------------------------------------------------

        short_description = None

        remainder = CTA_NOISE_PATTERN.sub("", product_text)
        # Strip WooCommerce Quickview plugin artifacts
        remainder = _WC_QUICKVIEW_NOISE_RE.sub("", remainder)
        remainder = _WC_VARIANT_HINT_RE.sub("", remainder)

        if product_name:
            remainder = re.sub(re.escape(product_name), "", remainder, count=1, flags=re.I)

        if price_text_raw:
            remainder = remainder.replace(price_text_raw, "")

        # Strip the collection/category title when it leaks into card text as a
        # category badge (e.g. happynails.pk cards contain "Press on Gel Nails"
        # after name+price are removed).
        if collection_title and len(collection_title) > 3:
            remainder = re.sub(
                re.escape(collection_title), "", remainder, count=1, flags=re.I
            )

        remainder = clean_text(remainder)

        # Strip standalone price/currency fragments left by Quickview range prices.
        # Pattern 1: pure price fragments  e.g. "– 260.00 AED"
        # Pattern 2: Quickview header      e.g. "Paint – 35.00 AED"  (category – highPrice)
        #   where "category" is 1-3 short words with no sentence punctuation.
        _price_frag_re = re.compile(
            r"^(?:[\w\s]{1,30}\s*)?[-–\s]*[\d,]+(?:\.\d+)?\s*(?:[A-Z]{2,4}|€|\$|£|₨|₱|kr|zł)[-–\s]*$",
            re.I
        )
        if _price_frag_re.match(remainder.strip()):
            remainder = ""

        if 2 < len(remainder) <= 200:
            short_description = remainder

        # Price fallback: if still null, try extracting from shortDescription text
        # Handles WooCommerce variation ranges like "5.00 AED – 77.00 AED" that
        # end up in the card's descriptive text but weren't caught by the main pass.
        if not price_text_raw and short_description:
            sd_price = extract_price_from_text(short_description)
            if sd_price:
                price_text_raw = sd_price
                price = sd_price
                price_normalized = normalize_price(sd_price, page_url=url)

        dom_products.append({
            "name": product_name,
            "url": full_url,
            "price": price,
            "priceTextRaw": price_text_raw,
            "priceNormalized": price_normalized,
            "image": image,
            "imageUrl": image,
            "shortDescription": short_description,
            "saleBadge": sale_badge,
            "availability": availability,
            "source": "dom"
        })

    dom_products = unique_items(dom_products, "url")
    dom_products = clean_products(dom_products, collection_title)

    products = merge_products(jsonld_products, dom_products)
    products = clean_products(products, collection_title)
    products = unique_items(products, "url")

    # ---------------------------------------------------
    # Fallback: price-less "View Product" cards (Requirement 3)
    # Used when standard WooCommerce .products selectors find nothing,
    # but the page repeats a "View Product" CTA next to product links
    # (e.g. BWT Pools category pages).
    # ---------------------------------------------------

    if not products:
        fallback_products = extract_view_product_cards(soup, url)

        if fallback_products:
            fallback_products = clean_products(fallback_products, collection_title)
            products = unique_items(fallback_products, "url")

    # ---------------------------------------------------
    # Fallback: Collection Text Parser
    # Activates only when pageType == "collection" AND productCount == 0
    # after all other product extraction has been attempted. Handles
    # Elementor/Bricks "price list" loops and headless-style collections
    # whose product cards repeat "[Name] [Currency][Price]" text with no
    # standard WooCommerce markup (e.g. size-assets.com/product-category/bundles/).
    # ---------------------------------------------------

    if not products and page_type == "collection":
        text_fallback_products = extract_collection_text_fallback(
            content_node, url, collection_title
        )

        if len(text_fallback_products) >= 2:
            products = text_fallback_products
        else:
            # Per-element DOM scan yielded too few results.
            # Try direct body-text scan (handles trailing noise after price,
            # e.g. "Basement Beats Bundle € 99 Add to wishlist").
            body_text_fallback = extract_collection_body_text_products(
                result.get("content", {}).get("mainText", ""),
                url,
                collection_title
            )
            if len(body_text_fallback) >= 2:
                products = body_text_fallback

    # ---------------------------------------------------
    # Pagination: follow the remaining pages and merge their products so the
    # FULL catalog is captured, not just page 1 (e.g. clare.pro skincare = 2 pages).
    # ---------------------------------------------------

    extra_products, fetched_all_pages = fetch_extra_pages(
        url, soup, lambda h, u: _page_products(h, u, collection_title)
    )
    if extra_products:
        products = unique_items(products + extra_products, "url")
        products = clean_products(products, collection_title)

    # ---------------------------------------------------
    # Category links
    # ---------------------------------------------------

    category_links = []

    bad_category_url_patterns = [
        "add-to-cart",
        "wishlist",
        "compare",
        "cart",
        "checkout",
        "my-account",
        "login",
        "register",
        "per_page",
        "?s=",
    ]

    bad_category_texts = [
        "add to cart",
        "quick view",
        "wishlist",
        "compare",
        "login",
        "register",
        "my account",
        "cart",
        "checkout",
        "en",
        "pl",
        "de",
        "fr"
    ]

    for a in soup.select(
        """
        a[href*='/product-category/'],
        a[href*='filter_cat='],
        a[href*='filter_brand='],
        a[href*='min_price='],
        a[href*='max_price=']
        """
    ):
        href = a.get("href")
        text = clean_text(a.get_text(" "))

        if not href or not text:
            continue

        href_lower = href.lower()
        text_lower = text.lower().strip()

        if any(pattern in href_lower for pattern in bad_category_url_patterns):
            continue

        if text_lower in bad_category_texts:
            continue

        if text_lower.isdigit():
            continue

        full_url = normalize_url(href, url)

        category_links.append({
            "text": text,
            "url": full_url
        })

    category_links = unique_items(category_links, "url")

    # ---------------------------------------------------
    # Sorting
    # ---------------------------------------------------

    sorting_options = []

    for option in soup.select("select.orderby option"):
        text = clean_text(option.get_text(" "))

        if text:
            sorting_options.append(text)

    sorting_options = list(dict.fromkeys(sorting_options))

    # ---------------------------------------------------
    # Filters
    # ---------------------------------------------------

    filters = []

    filter_keywords = [
        "filter",
        "category",
        "brand",
        "price",
        "color",
        "size",
        "skin",
        "hair"
    ]

    for label in soup.find_all(["label", "h3", "h4", "button"]):
        text = clean_text(label.get_text(" "))

        if not text:
            continue

        if any(keyword in text.lower() for keyword in filter_keywords):
            filters.append(text)

    filters = list(dict.fromkeys(filters))

    # ---------------------------------------------------
    # Pagination
    # ---------------------------------------------------

    page_links = []
    total_products_text = None
    load_more_detected = False

    # Standard WooCommerce pagination selectors
    for a in soup.select(
        ".pagination a, .woocommerce-pagination a, "
        ".nav-links a, .page-numbers a, [class*='pagination'] a"
    ):
        href = a.get("href")
        text = clean_text(a.get_text(" "))
        if not href or not text:
            continue
        href_lower = href.lower()
        if any(p in href_lower for p in ["add-to-cart", "wishlist", "#"]):
            continue
        full_url = normalize_url(href, url)
        page_links.append({"text": text, "url": full_url})

    page_links = unique_items(page_links, "url")

    # "Showing X–Y of Z results" text (WooCommerce standard)
    showing_el = soup.select_one(
        ".woocommerce-result-count, [class*='result-count'], [class*='showing']"
    )
    if showing_el:
        total_products_text = clean_text(showing_el.get_text(" ")) or None

    # Load More / infinite scroll button
    for btn in soup.select("button, a"):
        btn_text = clean_text(btn.get_text(" ")).lower()
        if any(kw in btn_text for kw in ["load more", "show more", "view more", "load products"]):
            load_more_detected = True
            break

    # Also check class-based load-more signals
    if not load_more_detected:
        for el in soup.select(
            "[class*='load-more'], [class*='loadmore'], [data-action*='load']"
        ):
            load_more_detected = True
            break

    pagination_detected = bool(page_links) or load_more_detected

    # We followed numeric pagination above; the catalog is complete unless there
    # are JS-only "load more"/infinite-scroll products we can't reach by URL.
    full_catalog_fetched = fetched_all_pages and not (load_more_detected and not page_links)

    pagination = {
        "detected": pagination_detected,
        "totalProductsText": total_products_text,
        "pageLinks": page_links,
        "currentlyFetchedProducts": len(products),
        "fullCatalogFetched": full_catalog_fetched,
        "loadMoreDetected": load_more_detected,
    }

    # ---------------------------------------------------
    # Sale products count
    # ---------------------------------------------------

    sale_products_count = sum(1 for p in products if p.get("saleBadge"))

    # ---------------------------------------------------
    # Stats
    # ---------------------------------------------------

    product_stats, price_range, availability_breakdown, products_with_images = (
        compute_collection_stats(products)
    )

    # ---------------------------------------------------
    # Populate result
    # ---------------------------------------------------

    result["content"]["collectionTitle"] = collection_title
    result["content"]["collectionName"] = collection_title
    result["content"]["mainText"] = body_text
    result["content"]["sortingOptions"] = sorting_options
    result["content"]["filters"] = filters
    result["content"]["rawPossibleFilters"] = filters

    # Expose products at the top level for normalize_collection_result
    result["products"] = products

    result["ecommerce"] = {
        "hasProducts": len(products) > 0,
        "productCount": len(products),
        "products": products,
        "categoryLinks": category_links,
        "hasSorting": len(sorting_options) > 0,
        "hasFilters": len(filters) > 0,
        "saleProductsCount": sale_products_count,
        "productStats": product_stats,
        "priceRange": price_range,
        "availabilityStats": availability_breakdown,
        "productsWithImagesCount": products_with_images,
        "pagination": pagination,
    }

    result["source"]["confidence"] = 0.85 if products else 0.5

    # Normalize — runs collection name fallback + product normalization
    collection_handle = (
        urlparse(url).path.rstrip("/").split("/")[-1] if url else None
    )
    result = normalize_collection_result(result, collection_handle=collection_handle)

    return result

    pagination_text = None
    page_links = []

    pagination_candidates = soup.find_all(
        string=re.compile(
            r"showing\s+(?:all\s+)?\d+|showing\s+\d+\s*[–-]\s*\d+\s+of\s+\d+",
            re.I
        )
    )

    for candidate in pagination_candidates:
        text = clean_text(str(candidate))

        if "showing" in text.lower():
            pagination_text = text
            break

    for a in soup.select(
        """
        .page-numbers a,
        a.page-numbers,
        .pagination a,
        nav.pagination a,
        .woocommerce-pagination a,
        a[href*='/page/']
        """
    ):
        href = a.get("href")
        text = clean_text(a.get_text(" "))

        if not href:
            continue

        if not text:
            aria = a.get("aria-label")
            rel = " ".join(a.get("rel", [])) if a.get("rel") else ""

            if aria:
                text = clean_text(aria)
            elif rel:
                text = clean_text(rel)
            else:
                text = "next"

        page_links.append({
            "text": text,
            "url": normalize_url(href, url)
        })

    page_links = unique_items(page_links, "url")

    numeric_page_links = [
        link for link in page_links
        if clean_text(link.get("text")).isdigit()
    ]

    next_prev_links = [
        link for link in page_links
        if clean_text(link.get("text")).lower() in [
            "next",
            "previous",
            "prev",
            "→",
            "»",
            "next page",
            "previous page"
        ]
    ]

    pagination_detected = (
        bool(pagination_text)
        or bool(numeric_page_links)
        or bool(next_prev_links)
    )

    full_catalog_fetched = not pagination_detected

    if pagination_text and re.search(
        r"showing\s+all\s+\d+\s+results",
        pagination_text,
        re.I
    ):
        full_catalog_fetched = True

    # ---------------------------------------------------
    # Build content
    # ---------------------------------------------------

    result["content"] = {
        "collectionTitle": collection_title,
        "collectionName": collection_title or None,
        "mainText": body_text[:12000],
        "sortingOptions": sorting_options[:30],
        "filters": [],
        "rawPossibleFilters": filters[:50]
    }

    # ---------------------------------------------------
    # Collection stats (Requirements 4 & 5)
    # Products with price=None are still counted as valid products.
    # ---------------------------------------------------

    product_stats, price_range, availability_stats, products_with_images = (
        compute_collection_stats(products)
    )

    # ---------------------------------------------------
    # Ecommerce
    # ---------------------------------------------------

    result["ecommerce"] = {
        "hasProducts": bool(products),
        "productCount": len(products),
        "products": products[:100],
        "categoryLinks": category_links[:100],
        "hasSorting": bool(sorting_options),
        "hasFilters": False,
        "saleProductsCount": len([
            p for p in products
            if p.get("saleBadge")
        ]),
        "productStats": product_stats,
        "priceRange": price_range,
        "availabilityStats": availability_stats,
        "productsWithImagesCount": products_with_images,
        "pagination": {
            "detected": pagination_detected,
            "totalProductsText": pagination_text,
            "pageLinks": page_links[:20],
            "currentlyFetchedProducts": len(products),
            "fullCatalogFetched": full_catalog_fetched
        }
    }

    result["products"] = products[:100]

    # ---------------------------------------------------
    # Collection summary (Requirement 5)
    # ---------------------------------------------------

    collection_description = (
        clean_text(result.get("openGraph", {}).get("description"))
        or clean_text(result.get("seo", {}).get("metaDescription"))
        or None
    )

    result["collectionSummary"] = {
        "collectionName": collection_title or None,
        "collectionDescription": collection_description,
        "totalProducts": product_stats["productCount"],
        "productsWithPrices": product_stats["productsWithPrices"],
        "productsWithoutPrices": product_stats["productsWithoutPrices"],
        "productsWithImages": products_with_images,
        "priceRange": price_range,
        "availabilityStats": availability_stats
    }

    # ---------------------------------------------------
    # Structured data
    # ---------------------------------------------------

    result["structuredData"] = {
        "jsonLdCount": len(json_ld_items),
        "items": json_ld_items[:20],
        "productsExtracted": len(jsonld_products)
    }

    # ---------------------------------------------------
    # Confidence
    # ---------------------------------------------------

    confidence = 0.45

    if collection_title:
        confidence += 0.10

    if products:
        confidence += 0.25

    if len(products) >= 5:
        confidence += 0.10

    if jsonld_products:
        confidence += 0.05

    if category_links:
        confidence += 0.05

    if sorting_options:
        confidence += 0.05

    result["source"]["confidence"] = round(
        min(confidence, 0.95),
        2
    )

    # Normalize price dicts and sync products to top-level "products" key
    from urllib.parse import urlparse as _up
    _col_handle = _up(url).path.rstrip("/").split("/")[-1]
    result = normalize_collection_result(
        result,
        collection_handle=_col_handle,
        default_currency="EUR",  # WordPress stores default; price_normalizer will use detected currency
    )

    return result