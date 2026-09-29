import re
from normalizers.text_normalizer import clean_text, title_case_from_handle
from normalizers.product_normalizer import normalize_products

# Pattern for product codes / SKUs that look like "HN -18", "SKU-04", "NP-A9", "ABC-123".
# These sometimes end up in H1 on WooCommerce/theme pages and should never be used
# as a collection name — we fall back to the SEO title or URL handle instead.
_PRODUCT_CODE_RE = re.compile(
    r'^[A-Z0-9]{1,6}\s*[-–]\s*[A-Z0-9]+\s*$',
    re.I
)

# Marketing suffixes stripped from the SEO title first-segment when deriving a
# fallback collection name (e.g. " – Happy Nails", " | Official Store").
_SEO_TITLE_SUFFIX_RE = re.compile(r'\s*[\|–\-]\s*[^|–\-]+$')


def normalize_collection_name(collection_name, url_handle=None, seo_title=None):
    """Return a human-readable collection name.

    Priority:
    1. ``collection_name`` as-is, unless it looks like a product SKU/code.
    2. First segment of ``seo_title`` (before `` | ``, `` – ``, `` - ``).
    3. Title-cased URL handle (e.g. ``press-on-gel-nails`` → ``Press On Gel Nails``).

    Product-code patterns like "HN -18" or "SKU-04" that themes sometimes put
    in the page <h1> are rejected so callers receive the real category name.
    """
    collection_name = clean_text(collection_name)

    # Accept the name only when it exists AND doesn't look like a product code.
    if collection_name and not _PRODUCT_CODE_RE.match(collection_name):
        return collection_name

    # If collection_name was a product code (or missing), try the SEO title first.
    if seo_title:
        seg = _SEO_TITLE_SUFFIX_RE.sub('', clean_text(seo_title) or '').strip()
        if (
            seg
            and len(seg) > 3
            and seg.lower() not in ('shop', 'store', 'home', 'products')
            and not _PRODUCT_CODE_RE.match(seg)
        ):
            return seg

    return title_case_from_handle(url_handle)


def build_normalized_product_stats(products, default_currency="PKR"):
    prices = []

    for p in products or []:
        current = p.get("price", {}).get("current")
        if isinstance(current, (int, float)):
            prices.append(current)

    in_stock_count = len([
        p for p in products or []
        if p.get("availability", {}).get("inStock") is True
    ])

    out_stock_count = len([
        p for p in products or []
        if p.get("availability", {}).get("inStock") is False
    ])

    currencies = [
        p.get("price", {}).get("currency")
        for p in products or []
        if p.get("price", {}).get("currency")
    ]

    return {
        "currency": currencies[0] if currencies else default_currency,
        "productCount": len(products or []),
        "priceRange": {
            "min": min(prices) if prices else None,
            "max": max(prices) if prices else None
        },
        "inStockCount": in_stock_count,
        "outOfStockCount": out_stock_count
    }


def normalize_collection_result(result, collection_handle=None, default_currency=None):
    """Minimal stub — returns result unchanged (full implementation was truncated)."""
    return result
