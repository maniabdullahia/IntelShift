from normalizers.text_normalizer import clean_text, normalize_vendor, normalize_category
from normalizers.description_normalizer import clean_html_description, extract_description_sections
from normalizers.price_normalizer import normalize_price
from normalizers.image_normalizer import normalize_image_url, dedupe_images


def _normalize_product_url(url):
    """Strip trailing slash and query string from a product URL for consistent dedup.

    Treats ``/product/foo`` and ``/product/foo/`` and ``/product/foo?ref=home``
    as the same canonical product URL across all platforms.
    """
    url = clean_text(url)
    if not url:
        return url
    # Strip query string first, then trailing slash
    url = url.split("?")[0].rstrip("/")
    return url or None


def normalize_availability(availability=None):
    # WordPress/WooCommerce collection parser returns plain strings like
    # "out_of_stock", "in_stock", "backorder" — convert before dict check.
    if isinstance(availability, str):
        _s = availability.lower().replace(" ", "_")
        if "out_of_stock" in _s or "outofstock" in _s:
            return {"status": "out_of_stock", "label": "Out of Stock",
                    "inStock": False, "stockTextRaw": None}
        if "in_stock" in _s or "instock" in _s:
            return {"status": "in_stock", "label": "In Stock",
                    "inStock": True, "stockTextRaw": None}
        if "backorder" in _s or "onbackorder" in _s:
            return {"status": "backorder", "label": "On Backorder",
                    "inStock": None, "stockTextRaw": None}
        # Unknown string value — fall through to dict path
        availability = {}

    if not isinstance(availability, dict):
        availability = {}
    availability = availability or {}

    status = availability.get("status")
    in_stock = availability.get("inStock")

    if in_stock is True:
        status = "in_stock"
        label = "In Stock"
    elif in_stock is False:
        status = "out_of_stock"
        label = "Out of Stock"
    else:
        status = status or "unknown"
        label = "Unknown"

    return {
        "status": status,
        "label": label,
        "inStock": in_stock,
        "stockTextRaw": availability.get("stockTextRaw")
    }


def normalize_variants(variants=None):
    normalized = []

    for variant in variants or []:
        if not isinstance(variant, dict):
            continue

        normalized.append({
            "id": variant.get("id"),
            "title": clean_text(variant.get("title")),
            "option1": clean_text(variant.get("option1")),
            "option2": clean_text(variant.get("option2")),
            "option3": clean_text(variant.get("option3")),
            "sku": clean_text(variant.get("sku")),
            "available": variant.get("available"),
            "price": variant.get("price"),
            "compare_at_price": variant.get("compare_at_price"),
            "featured_image": variant.get("featured_image")
        })

    return normalized


def _effective_price(product):
    """Return the best price input for normalize_price.

    When the raw price field is a string (e.g. "32,00 €") but the product
    already carries a pre-parsed priceNormalized.amount (e.g. from WordPress),
    use the pre-parsed value to avoid locale mis-parsing (comma as thousands
    separator → "32,00" being read as 3200 instead of 32.00).
    """
    raw = product.get("price")
    pn = product.get("priceNormalized") or {}
    if isinstance(raw, str) and pn.get("amount") is not None:
        return {
            "current": pn["amount"],
            "currency": pn.get("currency"),
            "priceTextRaw": raw,
        }
    return raw


def _resolve_image_url(product):
    """Return the best available image URL from a product dict.

    Different platform extractors store the primary image under different keys:
    - Most platforms / normalised output: ``imageUrl``
    - WordPress / WooCommerce collection extractor: ``image``
    - Jina extras: ``image_url``

    Falling back through these keys means we always capture the image regardless
    of which extractor produced the product dict.
    """
    return (
        product.get("imageUrl")
        or product.get("image")
        or product.get("image_url")
        or None
    )


def normalize_product(product, default_currency="PKR", enrich=True):
    if enrich:
        # Full normalization for product detail pages
        description = clean_html_description(product.get("shortDescription"))
        extracted_sections = extract_description_sections(description.get("text"))
        normalized = {
            **product,
            "name": clean_text(product.get("name")),
            "handle": clean_text(product.get("handle")),
            "productUrl": _normalize_product_url(product.get("productUrl")),
            "imageUrl": normalize_image_url(_resolve_image_url(product)),
            "additionalImageUrls": dedupe_images(product.get("additionalImageUrls", [])),
            "price": normalize_price(_effective_price(product), default_currency),
            "availability": normalize_availability(product.get("availability")),
            "category": normalize_category(product.get("category")),
            "vendor": normalize_vendor(product.get("vendor")),
            "description": {
                **description,
                **extracted_sections
            },
            "shortDescription": description.get("text"),
            "variants": normalize_variants(product.get("variants", [])),
            "badges": product.get("badges", []),
            "swatches": product.get("swatches", [])
        }
    else:
        # Lightweight normalization for collection page product cards.
        # Do NOT store full variants array, additionalImageUrls array, or description dict.
        short_raw = clean_text(product.get("shortDescription")) or ""
        variant_count = (
            product.get("variantCount")
            or len(product.get("variants") or [])
        )
        additional_count = (
            product.get("additionalImageCount")
            or len(product.get("additionalImageUrls") or [])
        )
        normalized = {
            **product,
            "name": clean_text(product.get("name")),
            "handle": clean_text(product.get("handle")),
            "productUrl": _normalize_product_url(product.get("productUrl")),
            "imageUrl": normalize_image_url(_resolve_image_url(product)),
            "additionalImageCount": additional_count,
            "price": normalize_price(_effective_price(product), default_currency),
            "availability": None,
        }
    return normalized


def normalize_products(products, default_currency="PKR", enrich=False):
    """Normalize a list of product dicts. enrich=False for collection cards."""
    if not isinstance(products, list):
        return []
    return [
        normalize_product(p, default_currency=default_currency, enrich=enrich)
        for p in products
        if isinstance(p, dict)
    ]
