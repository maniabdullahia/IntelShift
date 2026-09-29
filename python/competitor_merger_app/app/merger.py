"""Site snapshot merger (site_snapshot_v2).

Merges page-analysis JSONs from the Website Analyzer into one clean,
OpenAI-ready site snapshot for competitor comparison.

Works for any site type (ecommerce, SaaS, business, content) and any
page type (homepage, collection, product, blog, service, general).

Public API (unchanged):
    merge_page_jsons(page_jsons) -> snapshot dict
    merge_files(input_files, output_file) -> snapshot dict
"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, urlunparse

JsonDict = Dict[str, Any]

SCHEMA_VERSION = "site_snapshot_v2"

# ---- Limits (keep payloads AI-friendly) -----------------------------------
MAX_STRING_LEN = 3000
MAX_DESCRIPTION_LEN = 2000
MAX_SHORT_DESCRIPTION_LEN = 700
MAX_IMAGES_PER_PRODUCT = 20
MAX_VARIANTS_PER_PRODUCT = 50
MAX_TAGS_PER_PRODUCT = 25
MAX_RELATED_PRODUCTS = 10
MAX_LIST_ITEMS = 100

# Analyzer keys that are internal/heavy and must never reach the snapshot.
DROP_KEY_PREFIXES = ("_",)
DROP_KEYS = {"responseHeaders"}

# Page-type specific summary keys emitted by the analyzer.
SUMMARY_KEYS = (
    "homepage", "homepageSummary", "collectionSummary", "productSummary",
    "blogSummary", "serviceSummary", "generalSummary", "pageSummary",
)


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def clean_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    value = re.sub(r"\s+", " ", value).strip()
    return value or None


def html_to_text(value: Any) -> Optional[str]:
    text = clean_text(value)
    if not text:
        return None
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return clean_text(text)


def truncate(value: Any, limit: int) -> Optional[str]:
    text = clean_text(value)
    if text is None:
        return None
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def is_empty(value: Any) -> bool:
    return value in (None, "", [], {})


def compact(data: JsonDict) -> JsonDict:
    """Drop empty values from a dict."""
    return {k: v for k, v in data.items() if not is_empty(v)}


def strip_internal(value: Any, depth: int = 0) -> Any:
    """Recursively remove private/heavy keys and cap very long strings."""
    if depth > 12:
        return None
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if not isinstance(key, str):
                key = str(key)
            if key.startswith(DROP_KEY_PREFIXES) or key in DROP_KEYS:
                continue
            cleaned = strip_internal(item, depth + 1)
            if not is_empty(cleaned) or isinstance(cleaned, (bool, int, float)):
                out[key] = cleaned
        return out
    if isinstance(value, list):
        return [strip_internal(item, depth + 1) for item in value[:MAX_LIST_ITEMS]]
    if isinstance(value, str) and len(value) > MAX_STRING_LEN:
        return value[: MAX_STRING_LEN - 1].rstrip() + "…"
    return value


def normalize_url(url: Any) -> Optional[str]:
    url = clean_text(url)
    if not url:
        return None
    if url.startswith("//"):
        url = "https:" + url

    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return url.rstrip("/")

    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    netloc = re.sub(r"^www\d*\.", "", netloc)  # www., www2., www3. ...
    path = re.sub(r"/{2,}", "/", parsed.path or "")
    if path != "/":
        path = path.rstrip("/")

    return urlunparse((scheme, netloc, path, "", parsed.query, ""))


def domain_from_url(url: Any) -> Optional[str]:
    normalized = normalize_url(url)
    if not normalized:
        return None
    return urlparse(normalized).netloc or None


def merge_unique_strings(*values: Any, limit: Optional[int] = None) -> List[str]:
    seen = set()
    output: List[str] = []
    for value in values:
        for item in safe_list(value):
            item = clean_text(item)
            if not item:
                continue
            key = item.lower()
            if key not in seen:
                seen.add(key)
                output.append(item)
                if limit and len(output) >= limit:
                    return output
    return output


def json_key(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, ensure_ascii=False)
    except Exception:
        return str(value)


def merge_lists_by_json(*lists: Any, limit: Optional[int] = None) -> List[Any]:
    seen = set()
    output: List[Any] = []
    for list_value in lists:
        for item in safe_list(list_value):
            key = json_key(item).lower()
            if key not in seen:
                seen.add(key)
                output.append(deepcopy(item))
                if limit and len(output) >= limit:
                    return output
    return output


def most_common(values: List[Any]) -> Any:
    values = [v for v in values if not is_empty(v)]
    if not values:
        return None
    return max(set(values), key=values.count)


# ---------------------------------------------------------------------------
# Price
# ---------------------------------------------------------------------------

CURRENCY_PATTERNS = [
    (r"(?:\bpkr\b|\brs\.?(?:\s|\d)|₨)", "PKR"),
    (r"£", "GBP"),
    (r"€", "EUR"),
    (r"\baed\b|د\.إ", "AED"),
    (r"\bsar\b", "SAR"),
    (r"\binr\b|₹", "INR"),
    (r"\busd\b|\$", "USD"),
]


def detect_currency(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    raw_l = raw.lower()
    for pattern, code in CURRENCY_PATTERNS:
        if re.search(pattern, raw_l):
            return code
    return None


def parse_number(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = clean_text(value)
    if not text:
        return None
    match = re.search(r"([0-9][0-9,]*(?:\.\d+)?)", text)
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", ""))
    except Exception:
        return None


def as_money(value: Optional[float]) -> Optional[float | int]:
    if value is None:
        return None
    return int(value) if float(value).is_integer() else round(value, 2)


def normalize_price(price: Any, fallback: Optional[JsonDict] = None) -> JsonDict:
    """Normalize any analyzer price shape into one canonical dict.

    fallback carries legacy top-level product fields:
    {"currentPrice": ..., "comparePrice": ..., "currency": ...}
    """
    source = price if isinstance(price, dict) else {}
    fallback = fallback or {}

    raw = clean_text(
        source.get("priceTextRaw") or source.get("text") or source.get("raw")
        or (price if not isinstance(price, dict) else None)
    )

    current = parse_number(
        source.get("current") if source.get("current") not in (None, "")
        else source.get("amount") if source.get("amount") not in (None, "")
        else source.get("value")
    )
    if current is None:
        current = parse_number(fallback.get("currentPrice"))
    if current is None and raw:
        current = parse_number(raw)

    compare_at = parse_number(
        source.get("compareAt") if source.get("compareAt") not in (None, "")
        else source.get("compareAtPrice") if source.get("compareAtPrice") not in (None, "")
        else source.get("comparePrice")
    )
    if compare_at is None:
        compare_at = parse_number(fallback.get("comparePrice"))
    if compare_at is None:
        # Fallback fetchers (e.g. Firecrawl) emit allPrices: ["$88", "$110"]
        # where the higher second value is the compare-at price.
        all_prices = [parse_number(x) for x in safe_list(fallback.get("allPrices"))]
        all_prices = [x for x in all_prices if x is not None]
        if len(all_prices) >= 2 and current is not None and max(all_prices) > current:
            compare_at = max(all_prices)

    currency = clean_text(source.get("currency")) or clean_text(fallback.get("currency")) or detect_currency(raw)

    is_on_sale = bool(current is not None and compare_at is not None and compare_at > current)
    discount_percent = None
    if is_on_sale and compare_at:
        discount_percent = round((compare_at - current) / compare_at * 100, 1)

    return compact({
        "currency": currency,
        "current": as_money(current),
        "compareAt": as_money(compare_at),
        "isOnSale": is_on_sale or None,
        "discountPercent": discount_percent,
        "priceTextRaw": raw,
    })


def price_richness(price: JsonDict) -> int:
    score = 0
    if price.get("current") is not None:
        score += 4
    if price.get("compareAt") is not None:
        score += 2
    if price.get("currency"):
        score += 1
    if price.get("priceTextRaw"):
        score += 1
    return score


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------

SLUG_RE = re.compile(r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$")


def clean_category(value: Any) -> Optional[str]:
    text = clean_text(value)
    if not text:
        return None
    if len(text) > 80:  # page titles / taglines are not categories
        return None
    if SLUG_RE.match(text):
        text = text.replace("-", " ").replace("_", " ").title()
    return text


def normalize_availability(value: Any) -> Optional[JsonDict]:
    if isinstance(value, dict):
        return compact({
            "status": clean_text(value.get("status")),
            "label": clean_text(value.get("label") or value.get("stockTextRaw")),
            "inStock": value.get("inStock") if isinstance(value.get("inStock"), bool) else None,
        }) or None
    text = clean_text(value)
    if not text:
        return None
    lowered = text.lower()
    in_stock = None
    if any(t in lowered for t in ("in stock", "in_stock", "instock", "available")):
        in_stock = True
    elif any(t in lowered for t in ("out of stock", "out_of_stock", "sold out", "unavailable")):
        in_stock = False
    return compact({"label": text, "inStock": in_stock}) or None


def normalize_description(value: Any) -> Optional[JsonDict]:
    if isinstance(value, dict):
        text = clean_text(value.get("text")) or html_to_text(value.get("html"))
    else:
        text = html_to_text(value)
    text = truncate(text, MAX_DESCRIPTION_LEN)
    return {"text": text} if text else None


def normalize_related(products: Any) -> List[JsonDict]:
    out = []
    for item in safe_list(products)[:MAX_RELATED_PRODUCTS]:
        if not isinstance(item, dict):
            continue
        entry = compact({
            "name": clean_text(item.get("name") or item.get("title")),
            "productUrl": normalize_url(item.get("productUrl") or item.get("url")),
            "price": normalize_price(item.get("price")) or None,
        })
        if entry:
            out.append(entry)
    return out


# Accessibility/CTA noise that sometimes gets scraped as a product name.
JUNK_NAME_SUFFIX_RE = re.compile(r"\s*\((?:opens?|link opens?)[^)]*\)\s*$", re.I)
JUNK_NAME_PATTERNS = re.compile(
    r"^(?:explore|shop|view|see|browse|discover)\b.{0,40}$|^(?:shop now|view all|see all|learn more|read more)$",
    re.I,
)


def clean_product_name(value: Any) -> Optional[str]:
    name = clean_text(value)
    if not name:
        return None
    name = JUNK_NAME_SUFFIX_RE.sub("", name).strip()
    return name or None


def looks_like_cta_not_product(product: JsonDict) -> bool:
    """A name-only entry with CTA-style wording, no price and no handle is a
    scraped link (e.g. 'Explore the collection'), not a product."""
    name = clean_product_name(product.get("name") or product.get("title")) or ""
    has_price = isinstance(product.get("price"), dict) and product["price"].get("current") is not None
    has_price = has_price or product.get("currentPrice") is not None
    if has_price or product.get("handle") or product.get("productId"):
        return False
    return bool(JUNK_NAME_PATTERNS.match(name))


def product_identity(product: JsonDict) -> str:
    url = product.get("productUrl")
    if url:
        return f"url::{url}"
    handle = clean_text(product.get("handle"))
    if handle:
        return f"handle::{handle.lower()}"
    product_id = clean_text(product.get("productId"))
    if product_id:
        return f"id::{product_id.lower()}"
    name = clean_text(product.get("name"))
    if name:
        return f"name::{name.lower()}"
    return f"unknown::{json_key(product)[:120]}"


def normalize_product(product: JsonDict, page: JsonDict) -> JsonDict:
    """Build a canonical product from any analyzer product shape.

    Handles collection/product-page shape (name/productUrl/price{...})
    and homepage-card shape (title/url/image/currentPrice/comparePrice).
    """
    p = product or {}

    price = normalize_price(p.get("price"), fallback={
        "currentPrice": p.get("currentPrice"),
        "comparePrice": p.get("comparePrice"),
        "currency": p.get("currency"),
        "allPrices": p.get("allPrices"),
    })

    product_url = normalize_url(p.get("productUrl") or p.get("url"))
    page_url = normalize_url(page.get("url"))
    if (
        product_url and page_url and product_url == page_url
        and clean_text(page.get("pageType")) != "product"
    ):
        # On collection/homepage cards the analyzer sometimes stamps the PAGE
        # URL on every product; using it for identity would merge them all.
        product_url = None

    reviews = p.get("reviews") if isinstance(p.get("reviews"), dict) else {}
    reviews = compact({
        "averageRating": reviews.get("averageRating"),
        "reviewCount": reviews.get("reviewCount"),
        "source": clean_text(reviews.get("source")),
        "snippets": [truncate(s, 300) for s in safe_list(reviews.get("snippets"))[:5]],
    })

    source_page = compact({
        "url": normalize_url(page.get("url")),
        "pageType": clean_text(page.get("pageType")),
        "title": clean_text(page.get("title") or page.get("collectionName")),
        "rank": p.get("rank"),
    })

    normalized = compact({
        "name": clean_product_name(p.get("name") or p.get("title")),
        "handle": clean_text(p.get("handle")),
        "productId": clean_text(p.get("productId") or p.get("id")),
        "productUrl": product_url,
        "imageUrl": normalize_url(p.get("imageUrl") or p.get("image") or p.get("featuredImage")),
        "additionalImageUrls": merge_unique_strings(
            p.get("additionalImageUrls"), p.get("images"), limit=MAX_IMAGES_PER_PRODUCT
        ),
        "additionalImageCount": p.get("additionalImageCount"),
        "price": price or None,
        "availability": normalize_availability(p.get("availability") or p.get("stockStatus")),
        "category": clean_category(p.get("category"))
            or clean_category(page.get("collectionName"))
            or (clean_category(page.get("title")) if page.get("pageType") == "collection" else None),
        "vendor": clean_text(p.get("vendor") or p.get("brand")),
        "productType": clean_text(p.get("productType") or p.get("type")),
        "tags": merge_unique_strings(p.get("tags"), limit=MAX_TAGS_PER_PRODUCT),
        "shortDescription": truncate(
            p.get("shortDescription") if not isinstance(p.get("shortDescription"), dict)
            else (p.get("shortDescription") or {}).get("text"),
            MAX_SHORT_DESCRIPTION_LEN,
        ),
        "description": normalize_description(p.get("description")),
        "options": strip_internal(safe_list(p.get("options"))),
        "variants": strip_internal(safe_list(p.get("variants"))[:MAX_VARIANTS_PER_PRODUCT]),
        # Carry the crawled variant summary through so the UI can show colours/sizes.
        "variantCount": p.get("variantCount") or (len(safe_list(p.get("variants"))) or None),
        "variantOptions": merge_unique_strings(p.get("variantOptions"), limit=30),
        "swatches": strip_internal(safe_list(p.get("swatches"))[:50]),
        "badges": merge_unique_strings(p.get("badges"), limit=20),
        "discount": strip_internal(p.get("discount")) if isinstance(p.get("discount"), dict) else None,
        "reviews": reviews or None,
        "relatedProducts": normalize_related(p.get("relatedProducts")),
        "features": [truncate(x, 300) for x in safe_list(p.get("features"))[:15] if clean_text(x)],
        "benefits": [truncate(x, 300) for x in safe_list(p.get("benefits"))[:15] if clean_text(x)],
        "ingredients": [truncate(x, 300) for x in safe_list(p.get("ingredients"))[:30] if clean_text(x)],
        "metrics": strip_internal(p.get("metrics")) if isinstance(p.get("metrics"), dict) else None,
        "source": strip_internal(p.get("source")) if isinstance(p.get("source"), dict) else None,
        "sourcePages": [source_page] if source_page else [],
    })
    return normalized


def source_page_key(entry: JsonDict) -> str:
    return f"{entry.get('url')}::{entry.get('pageType')}"


def merge_source_pages(*lists: Any) -> List[JsonDict]:
    seen = set()
    out: List[JsonDict] = []
    for list_value in lists:
        for entry in safe_list(list_value):
            if not isinstance(entry, dict):
                continue
            key = source_page_key(entry)
            if key not in seen:
                seen.add(key)
                out.append(deepcopy(entry))
    return out


# Detail pages carry the richest data; prefer them when merging duplicates.
PAGE_TYPE_PRIORITY = {"product": 3, "collection": 2, "homepage": 1}


def product_page_priority(product: JsonDict) -> int:
    return max(
        (PAGE_TYPE_PRIORITY.get((sp or {}).get("pageType"), 0) for sp in product.get("sourcePages") or []),
        default=0,
    )


def merge_product(old: JsonDict, new: JsonDict) -> JsonDict:
    # The product coming from the richer page type wins field-by-field.
    if product_page_priority(new) > product_page_priority(old):
        primary, secondary = new, old
    else:
        primary, secondary = old, new

    merged = deepcopy(primary)
    for key, value in secondary.items():
        if is_empty(merged.get(key)):
            merged[key] = deepcopy(value)

    merged["sourcePages"] = merge_source_pages(old.get("sourcePages"), new.get("sourcePages"))
    merged["additionalImageUrls"] = merge_unique_strings(
        primary.get("additionalImageUrls"), secondary.get("additionalImageUrls"),
        limit=MAX_IMAGES_PER_PRODUCT,
    )
    merged["tags"] = merge_unique_strings(primary.get("tags"), secondary.get("tags"), limit=MAX_TAGS_PER_PRODUCT)
    merged["badges"] = merge_unique_strings(primary.get("badges"), secondary.get("badges"), limit=20)
    merged["swatches"] = merge_lists_by_json(primary.get("swatches"), secondary.get("swatches"), limit=50)
    merged["variants"] = merge_lists_by_json(primary.get("variants"), secondary.get("variants"), limit=MAX_VARIANTS_PER_PRODUCT)

    old_price = old.get("price") or {}
    new_price = new.get("price") or {}
    merged["price"] = old_price if price_richness(old_price) >= price_richness(new_price) else new_price

    return compact(merged)


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

def extract_page_summary(page_json: JsonDict) -> JsonDict:
    page = page_json.get("page") or {}
    seo = page_json.get("seo") or {}
    level1 = page_json.get("level1") or {}

    # Page-type specific summary blocks (homepage, collectionSummary, ...).
    type_summary: JsonDict = {}
    for key in SUMMARY_KEYS:
        value = page_json.get(key)
        if isinstance(value, dict) and value:
            type_summary = strip_internal(value)
            break

    summary = compact({
        "url": normalize_url(page.get("url") or page_json.get("url")),
        "pageType": clean_text(page.get("pageType") or page_json.get("pageType")),
        "platform": clean_text(page_json.get("platform")),
        # User-facing tech label (real framework/CMS or friendly fallback).
        "displayPlatform": clean_text(
            page_json.get("displayPlatform") or level1.get("displayPlatform")
        ),
        "title": clean_text(seo.get("title")),
        "success": bool(page_json.get("success", True)),
        # website_blocked contract (analyzer main.mark_website_blocked)
        "status": clean_text(page_json.get("status")),
        "blockedReason": clean_text(page_json.get("blockedReason")),
        "userMessage": clean_text(page_json.get("userMessage")),
        "analysisReady": page_json.get("analysisReady", False),
        "seo": strip_internal(seo),
        "openGraph": strip_internal(page_json.get("openGraph") or {}),
        "navigation": strip_internal(page_json.get("navigation") or {}),
        "content": strip_internal(page_json.get("content") or {}),
        "ecommerce": strip_internal(page_json.get("ecommerce") or {}),
        "technical": strip_internal(page_json.get("technical") or {}),
        "crawl": strip_internal(page_json.get("crawl") or {}),
        "source": strip_internal(page_json.get("source") or {}),
        "summary": type_summary or None,
        # SaaS / business / general-page analyzer blocks (pass through).
        "business": strip_internal(page_json.get("business") or {}) or None,
        "homepageStrategy": strip_internal(page_json.get("homepageStrategy") or {}) or None,
        "pricing": strip_internal(page_json.get("pricing") or {}) or None,
        "saas": strip_internal(page_json.get("saas") or {}) or None,
        "generalPage": strip_internal(page_json.get("generalPage") or {}) or None,
        "structuredData": strip_internal(page_json.get("structuredData") or {}) or None,
        "security": strip_internal(page_json.get("security") or {}) or None,
        "features": strip_internal(page_json.get("features") or {}) or None,
        "metrics": strip_internal(page_json.get("metrics") or {}) or None,
        # Full visible text + key zones (announcement/top, hero, footer). Kept so a
        # curated slice can be fed to the AI as recovery evidence for anything the
        # structured extractors missed. (rawTextEvidence, distinct from the comparison
        # engine's own structured `textEvidence`.)
        "rawTextEvidence": strip_internal(page_json.get("rawTextEvidence") or {}) or None,
        "warnings": strip_internal(safe_list(page_json.get("warnings"))) or None,
        "extractionQuality": strip_internal(page_json.get("extractionQuality") or {}) or None,
        "detection": compact({
            "platform": clean_text(level1.get("platform")),
            "platformConfidence": level1.get("platformConfidence"),
            "pageTypeConfidence": level1.get("pageTypeConfidence"),
        }) or None,
        "productCountOnPage": len(safe_list(page_json.get("products"))),
    })
    return summary


# ---------------------------------------------------------------------------
# Site summary
# ---------------------------------------------------------------------------

ECOMMERCE_PAGE_TYPES = {"collection", "product", "cart", "checkout"}


def infer_site_type(pages: List[JsonDict], products: List[JsonDict], homepage_summary: JsonDict) -> str:
    classification = (homepage_summary or {}).get("businessClassification") or {}
    homepage_type = clean_text(classification.get("homepageType") or (homepage_summary or {}).get("homepageType"))

    # Only PRICED products prove a catalog. URL-only "products" are often
    # service links extracted from listing pages (e.g. an agency's services).
    priced_products = [p for p in products if (p.get("price") or {}).get("current") is not None]
    has_ecom_signal = bool(priced_products) or any(
        (p.get("pageType") in ("product", "cart", "checkout"))
        or (p.get("ecommerce") or {}).get("hasEcommerceSignals")
        or (p.get("ecommerce") or {}).get("hasProducts")
        for p in pages
    )
    if has_ecom_signal:
        return "ecommerce"

    # SaaS / platform / lead-gen detection from analyzer business + saas blocks.
    for p in pages:
        if (p.get("saas") or {}).get("isSaaS"):
            return "saas"
        _plans = ((p.get("pricing") or {}).get("plans")) or []
        _plan_names = {clean_text(pl.get("name") or "").lower() for pl in _plans if isinstance(pl, dict)}
        if _plans and (_plan_names & {"free", "pro", "business", "enterprise", "team", "starter", "premium", "basic", "plus"}):
            return "saas"
        business = p.get("business") or {}
        summary_bm = ((p.get("summary") or {}).get("businessModel")) or {}
        primary = (
            (business.get("businessModel") or {}).get("primary")
            or (summary_bm.get("primary") if isinstance(summary_bm, dict) else None)
        )
        if primary in ("saas", "platform"):
            return "saas"
        if primary in ("leadGeneration", "services", "agency", "manufacturer", "general"):
            return "business"
    if homepage_type:
        if any(t in homepage_type for t in ("saas", "software", "app")):
            return "saas"
        if any(t in homepage_type for t in ("blog", "news", "magazine", "content")):
            return "content"
        return "business"
    blog_pages = sum(1 for p in pages if p.get("pageType") in ("blog", "article", "post"))
    if pages and blog_pages >= max(1, len(pages) // 2):
        return "content"
    # Non-catalog site with normal business pages -> business.
    if any(p.get("pageType") in ("homepage", "general", "service", "services", "about", "contact", "collection") for p in pages):
        return "business"
    return "unknown"


def build_catalog_summary(products: List[JsonDict]) -> JsonDict:
    if not products:
        return {}

    priced = [p for p in products if (p.get("price") or {}).get("current") is not None]
    prices = [p["price"]["current"] for p in priced]
    on_sale = [p for p in priced if (p.get("price") or {}).get("isOnSale")]
    currencies = [p["price"].get("currency") for p in priced if p["price"].get("currency")]

    in_stock = sum(1 for p in products if (p.get("availability") or {}).get("inStock") is True)
    out_of_stock = sum(1 for p in products if (p.get("availability") or {}).get("inStock") is False)

    return compact({
        "totalUniqueProducts": len(products),
        "productsWithPrice": len(priced),
        "productsWithoutPrice": len(products) - len(priced),
        "priceCoverageRate": round(len(priced) / len(products), 3),
        "currency": most_common(currencies),
        "priceRange": compact({
            "min": as_money(min(prices)) if prices else None,
            "max": as_money(max(prices)) if prices else None,
            "average": as_money(round(sum(prices) / len(prices), 2)) if prices else None,
        }) or None,
        "onSaleCount": len(on_sale),
        "maxDiscountPercent": max((p["price"].get("discountPercent") or 0 for p in on_sale), default=None),
        "inStockCount": in_stock or None,
        "outOfStockCount": out_of_stock or None,
        "categoriesDetected": merge_unique_strings([p.get("category") for p in products], limit=100),
        "vendorsDetected": merge_unique_strings([p.get("vendor") for p in products], limit=50),
        "productTypesDetected": merge_unique_strings([p.get("productType") for p in products], limit=50),
    })


def build_collections_summary(pages: List[JsonDict]) -> List[JsonDict]:
    out = []
    for page in pages:
        if page.get("pageType") != "collection":
            continue
        stats = (page.get("ecommerce") or {}).get("productStats") or {}
        summary = page.get("summary") or {}
        out.append(compact({
            "url": page.get("url"),
            "name": clean_text(summary.get("name"))
                or clean_text((page.get("content") or {}).get("collectionName"))
                or page.get("title"),
            "productCount": summary.get("productCount") or stats.get("productCount") or page.get("productCountOnPage"),
            "currency": stats.get("currency"),
            "priceRange": stats.get("priceRange") or summary.get("priceRange"),
            "inStockCount": stats.get("inStockCount"),
            "outOfStockCount": stats.get("outOfStockCount"),
            "hasFilters": stats.get("hasFilters"),
            "hasSort": stats.get("hasSort"),
        }))
    return out


def build_pricing_summary(pages: List[JsonDict]) -> JsonDict:
    """Site-level pricing/plan summary from analyzer pricing + saas blocks.

    When several pages carry pricing data (e.g. a homepage teaser AND the real
    pricing page), the block with the most plans wins."""
    candidates = []
    for page in pages:
        pricing = page.get("pricing") or (page.get("generalPage") or {}).get("pricing") or {}
        if pricing.get("hasPricing"):
            candidates.append((len(safe_list(pricing.get("plans"))), page, pricing))
    candidates.sort(key=lambda x: x[0], reverse=True)
    for _, page, pricing in candidates:
        saas = page.get("saas") or {}
        plans = safe_list(pricing.get("plans"))
        amounts = [
            (pl.get("price") or {}).get("amount")
            for pl in plans
            if isinstance(pl, dict) and isinstance((pl.get("price") or {}).get("amount"), (int, float))
        ]
        return compact({
            "sourceUrl": page.get("url"),
            "pricingModel": clean_text(pricing.get("pricingModel")),
            "currency": clean_text(pricing.get("currency")),
            "planCount": len(plans) or None,
            "planNames": merge_unique_strings(pricing.get("planOrder"), [
                (pl.get("name") if isinstance(pl, dict) else None) for pl in plans
            ], limit=15),
            "priceRange": compact({
                "min": as_money(min(amounts)) if amounts else None,
                "max": as_money(max(amounts)) if amounts else None,
            }) or None,
            "billing": strip_internal(pricing.get("billing") or {}) or None,
            "hasFreeTrial": saas.get("hasFreeTrial"),
            "hasEnterpriseOffering": saas.get("hasEnterpriseOffering"),
            "aiCapabilities": merge_unique_strings(saas.get("aiCapabilities"), limit=15),
        })
    return {}


def build_navigation_summary(pages: List[JsonDict]) -> JsonDict:
    for page in pages:
        nav = page.get("navigation") or {}
        links = [l for l in safe_list(nav.get("links")) if isinstance(l, dict)]
        if links:
            return compact({
                "mainLinkCount": len(links),
                "footerLinkCount": len(safe_list(nav.get("footerLinks"))),
                "topLabels": merge_unique_strings([l.get("text") for l in links], limit=15),
            })
    return {}


def build_site_summary(pages: List[JsonDict], products: List[JsonDict]) -> JsonDict:
    domains = [domain_from_url(p.get("url")) for p in pages]
    domains = [d for d in domains if d]
    domain = most_common(domains)

    platform = most_common([p.get("platform") for p in pages])
    platform_confidence = most_common([
        (p.get("detection") or {}).get("platformConfidence") for p in pages
    ])
    # User-facing tech label — prefer a confidently-named framework/CMS across
    # pages; fall back to the friendly "Custom / Undetected" rather than "Unknown".
    _display_candidates = [
        p.get("displayPlatform") for p in pages
        if p.get("displayPlatform") and p.get("displayPlatform") != "Custom / Undetected"
    ]
    display_platform = (
        most_common(_display_candidates)
        or most_common([p.get("displayPlatform") for p in pages])
        or "Custom / Undetected"
    )

    page_types: Dict[str, int] = {}
    for p in pages:
        pt = p.get("pageType") or "unknown"
        page_types[pt] = page_types.get(pt, 0) + 1

    homepage = next((p for p in pages if p.get("pageType") == "homepage"), {})
    homepage_summary = homepage.get("summary") or {}

    def plausible_name(value):
        name = clean_text(value)
        if not name or len(name) > 60 or len(name.split()) > 6:
            return None  # concatenated headings / junk, not a site name
        return name

    site_name = (
        plausible_name(homepage_summary.get("siteName"))
        or plausible_name((homepage.get("content") or {}).get("siteName"))
        or most_common([plausible_name((p.get("openGraph") or {}).get("siteName")) for p in pages])
        or most_common([plausible_name((p.get("openGraph") or {}).get("site_name")) for p in pages])
    )
    if not site_name and domain:
        site_name = domain.split(".")[0].replace("-", " ").title()

    business = homepage.get("business") or {}
    strategy = homepage.get("homepageStrategy") or {}

    catalog = build_catalog_summary(products)

    site = compact({
        "domain": domain,
        "siteName": site_name,
        "platform": platform,
        "displayPlatform": display_platform,
        "platformConfidence": platform_confidence,
        "siteType": infer_site_type(pages, products, homepage_summary),
        "businessCategory": clean_text(
            (homepage_summary.get("businessClassification") or {}).get("homepageType")
            or homepage_summary.get("homepageType")
            or (business.get("businessModel") or {}).get("primary")
        ),
        "valueProposition": truncate(strategy.get("valueProposition") or ((strategy.get("hero") or {}).get("headline")), 300),
        "targetAudience": merge_unique_strings(strategy.get("audience"), limit=10),
        "subCategories": merge_unique_strings(
            (homepage_summary.get("businessClassification") or {}).get("subCategories"), limit=15
        ),
        "positioning": [truncate(x, 200) for x in safe_list(homepage_summary.get("positioning"))[:10] if clean_text(x)]
            or [truncate(x, 200) for x in safe_list((homepage.get("homepageStrategy") or {}).get("positioning"))[:10] if clean_text(x)],
        "pagesAnalyzedCount": len(pages),
        "pageTypesAnalyzed": page_types,
        "analyzedUrls": [p.get("url") for p in pages if p.get("url")],
        "catalog": catalog or None,
        "pricingSummary": build_pricing_summary(pages) or None,
        "collections": build_collections_summary(pages) or None,
        "navigation": build_navigation_summary(pages) or None,
        "homepageFeatures": homepage.get("features"),
        "homepageMetrics": homepage.get("metrics"),
        # Backward-compatible flat fields (consumed by comparison_app).
        "totalUniqueProducts": catalog.get("totalUniqueProducts", 0) if catalog else 0,
        "productsWithPrice": catalog.get("productsWithPrice", 0) if catalog else 0,
        "productsWithoutPrice": catalog.get("productsWithoutPrice", 0) if catalog else 0,
        "categoriesDetected": catalog.get("categoriesDetected") if catalog else None,
        "vendorsDetected": catalog.get("vendorsDetected") if catalog else None,
    })
    # Counts of zero are meaningful; compact() drops them, so restore.
    site.setdefault("totalUniqueProducts", 0)
    site.setdefault("productsWithPrice", 0)
    site.setdefault("productsWithoutPrice", 0)
    return site


# ---------------------------------------------------------------------------
# Merge entry points
# ---------------------------------------------------------------------------

def merge_page_jsons(page_jsons: List[JsonDict]) -> JsonDict:
    if not page_jsons:
        raise ValueError("No page JSONs provided.")

    pages: List[JsonDict] = []
    product_map: Dict[str, JsonDict] = {}
    warnings: List[str] = []
    seen_urls = set()

    for index, page_json in enumerate(page_jsons, start=1):
        if not isinstance(page_json, dict):
            warnings.append(f"Input #{index} skipped: not a JSON object.")
            continue

        page_summary = extract_page_summary(page_json)

        url = page_summary.get("url")
        if url and url in seen_urls:
            warnings.append(f"Input #{index} ({url}) is a duplicate page URL; merged anyway.")
        if url:
            seen_urls.add(url)
        if page_summary.get("status") == "website_blocked":
            warnings.append(
                f"Input #{index} ({url or 'no url'}) was BLOCKED by the website "
                f"(reason: {page_summary.get('blockedReason') or 'unknown'}). "
                "Its data is missing from this snapshot."
            )
        elif not page_summary.get("success", True):
            warnings.append(f"Input #{index} ({url or 'no url'}) was marked success=false by the analyzer.")

        pages.append(page_summary)

        page_info = page_json.get("page") or {}
        page_context = {
            "url": page_info.get("url") or page_json.get("url"),
            "pageType": page_info.get("pageType") or page_json.get("pageType"),
            "title": (page_json.get("seo") or {}).get("title"),
            "collectionName": (page_json.get("content") or {}).get("collectionName"),
        }

        for raw_product in safe_list(page_json.get("products")):
            if not isinstance(raw_product, dict):
                continue
            if looks_like_cta_not_product(raw_product):
                continue
            product = normalize_product(raw_product, page_context)
            if not product.get("name") and not product.get("productUrl"):
                continue
            identity = product_identity(product)
            if identity in product_map:
                product_map[identity] = merge_product(product_map[identity], product)
            else:
                product_map[identity] = product

    # Mixed-domain guard.
    page_domains = sorted({domain_from_url(p.get("url")) for p in pages if p.get("url")} - {None})
    if len(page_domains) > 1:
        warnings.append(
            "Pages come from multiple domains: " + ", ".join(page_domains)
            + ". A snapshot should contain pages from ONE site only."
        )

    products = list(product_map.values())
    products.sort(key=lambda p: (p.get("category") or "", p.get("name") or ""))

    # Depth enrichment: collection cards only carry a thumbnail + a few visible
    # swatches, so variant/image/description depth is under-counted. Pull the
    # store's BULK product source once (Shopify products.json / Woo Store API /
    # headless-Shopify GraphQL / sampled custom-store JSON) and merge accurate
    # depth into each product by handle. Never fatal — on any failure the
    # card-level approximation is kept and depthMeta records depthSource="cards".
    depth_meta = None
    try:
        try:
            from .catalog_enrich import enrich_products  # loaded as app.merger
        except Exception:
            from catalog_enrich import enrich_products  # type: ignore  # app/ on sys.path

        base_url = next((p.get("url") for p in pages if p.get("url")), None)
        platform_hint = most_common([p.get("platform") for p in pages if p.get("platform")])
        depth_meta = enrich_products(products, base_url, platform_hint)
    except Exception as exc:  # pragma: no cover - enrichment is best-effort
        warnings.append(f"Product-depth enrichment skipped: {exc}")

    site = build_site_summary(pages, products)

    coverage = compact({
        "hasHomepage": any(p.get("pageType") == "homepage" for p in pages) or None,
        "collectionPages": sum(1 for p in pages if p.get("pageType") == "collection") or None,
        "productPages": sum(1 for p in pages if p.get("pageType") == "product") or None,
        "blogPages": sum(1 for p in pages if p.get("pageType") in ("blog", "article", "post")) or None,
        "otherPages": sum(
            1 for p in pages
            if p.get("pageType") not in ("homepage", "collection", "product", "blog", "article", "post")
        ) or None,
        "failedPages": [p.get("url") for p in pages if p.get("success") is False] or None,
        "blockedPages": [p.get("url") for p in pages if p.get("status") == "website_blocked"] or None,
    })

    snapshot_status = None
    user_message = None
    blocked_pages = [p for p in pages if p.get("status") == "website_blocked"]
    if pages and len(blocked_pages) == len(pages):
        # Every page was blocked: the snapshot is unusable; give React the
        # same contract shape the analyzer uses.
        snapshot_status = "website_blocked"
        user_message = next(
            (p.get("userMessage") for p in blocked_pages if p.get("userMessage")),
            "This website blocks automated analysis, so we can't crawl it. "
            "Please choose a different competitor website.",
        )
    elif blocked_pages:
        snapshot_status = "partial_blocked"

    return {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": now_iso(),
        **({"status": snapshot_status} if snapshot_status else {}),
        **({"userMessage": user_message} if user_message else {}),
        "site": site,
        "pagesAnalyzed": pages,
        "products": products,
        "quality": {
            "warnings": warnings,
            "coverage": coverage,
            **({"productDepth": depth_meta} if depth_meta else {}),
            "openAIReady": True,
            "notes": [
                "Products are deduped by productUrl, then handle, then productId, then name.",
                "When the same product appears on several pages, the richer page type (product > collection > homepage) wins field-by-field.",
                "Each product includes sourcePages so analysis can trace where it appeared.",
                "Internal keys (prefixed with _) and raw HTML are stripped; long text is truncated.",
                "site.catalog / site.collections / site.homepageFeatures summarize the site for AI comparison.",
                "SaaS/business analyzer blocks (pricing, saas, business, homepageStrategy, generalPage) are preserved per page; site.pricingSummary aggregates plans.",
            ],
        },
    }


def load_json_file(path: str | Path) -> JsonDict:
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def save_json_file(data: JsonDict, path: str | Path) -> None:
    path = Path(path)
    if path.parent and str(path.parent) not in (".", ""):
        path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def merge_files(input_files: List[str | Path], output_file: str | Path) -> JsonDict:
    page_jsons = [load_json_file(path) for path in input_files]
    snapshot = merge_page_jsons(page_jsons)
    save_json_file(snapshot, output_file)
    return snapshot


# end of module
