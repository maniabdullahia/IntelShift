"""
business_type.py — Step 2 of the competitor-analysis flow: what KIND of business
is this store? Single source of truth for the onboarding gate AND competitor
suggestions (the Node side fetches the lists below via /api/v1/business-type/lists
instead of keeping its own copies).

  Type 1  Large Marketplace          Amazon, Daraz, eBay            → enterprise
  Type 2  Global / Multinational Brand  Nike, Adidas, Zara          → enterprise
  Type 3  General Marketplace        multi-brand, many industries   → continue
  Type 4  Niche / Category Marketplace  multi-brand, one vertical    → continue
  Type 5  Single-Brand Store         one company, own products      → continue

Decision order (first match wins):
  0. Support allowlist (false-positive override)          → Type 5/4/3 path
  1. Known marketplace domain                              → Type 1
  2. Strong marketplace structure (seller sign-up etc.)    → Type 1 (Type 3 if small)
  3. Absurd catalog size (unlisted marketplace backstop)   → Type 1
  4. Known multinational brand domain                      → Type 2
  5. Many regional storefronts (hreflang countries)        → Type 2
  6. Multi-brand catalog + ≥3 industries                   → Type 3
  7. Multi-brand catalog                                   → Type 4
  8. Otherwise                                             → Type 5

Pure functions, no network. Every input is optional; missing signals lower the
confidence instead of guessing.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlparse

# ── Type 1: marketplaces / multi-seller giants (registrable label) ──────────
MARKETPLACE_DENYLIST = {
    "amazon", "ebay", "daraz", "aliexpress", "alibaba", "walmart", "etsy",
    "shein", "temu", "flipkart", "noon", "jumia", "lazada", "shopee",
    "mercadolibre", "mercadolivre", "rakuten", "wish", "wayfair", "newegg",
    "olx", "gumtree", "kohls", "macys", "trendyol", "meesho", "myntra",
    "snapdeal", "zalando", "allegro", "coupang", "taobao", "tmall", "ozon",
    "cdiscount", "backmarket", "poshmark", "depop", "mercari", "reverb",
    "stockx", "takealot", "kaspi", "hepsiburada", "tokopedia", "bukalapak",
    "otto", "ajio", "nykaa", "tatacliq", "jiomart", "bigbasket", "namshi",
    "ounass", "konga", "souq", "carrefouruae", "bestbuy", "costco",
    # Giant multi-brand retailers — same treatment as marketplaces.
    "sephora", "ulta", "selfridges", "nordstrom", "johnlewis", "asos",
    "farfetch", "net-a-porter", "netaporter", "harrods",
}
# Labels too generic to match on the label alone — require the exact host.
# (target.pk, jd.co.uk, bol-shoes.com must not be blocked as Target/JD/bol.)
MARKETPLACE_EXACT_HOSTS = {
    "target.com", "jd.com", "bol.com", "goat.com", "mall.cz", "qoo10.com",
}

# ── Type 2: global / multinational brands (registrable label) ───────────────
MULTINATIONAL_BRANDS = {
    "nike", "adidas", "puma", "reebok", "underarmour", "newbalance", "asics",
    "converse", "vans", "skechers", "fila", "lululemon", "zara", "hm", "uniqlo",
    "mango", "gap", "oldnavy", "bershka", "pullandbear", "stradivarius",
    "massimodutti", "primark", "levi", "levis", "tommy", "calvinklein",
    "ralphlauren", "hugoboss", "gucci", "louisvuitton", "prada", "chanel",
    "dior", "hermes", "burberry", "versace", "armani", "michaelkors",
    "ikea", "apple", "samsung", "sony", "dell", "hp", "lenovo", "microsoft",
    "loreal", "maybelline", "lancome", "esteelauder", "lego", "disney", "decathlon", "northface", "thenorthface",
    "patagonia", "columbia", "timberland", "crocs", "birkenstock", "ecco",
    "clarks", "pandora", "swarovski", "rolex", "casio", "fossil", "victoriassecret",
    "bathandbodyworks", "theordinary", "nespresso", "dyson", "philips",
}
MULTINATIONAL_EXACT_HOSTS = {"www2.hm.com", "hm.com", "mac-cosmetics.com", "levi.com"}

# Strong, unambiguous multi-seller signals (any ONE is enough). Deliberately
# excludes generic words like "marketplace" or "/sellers/" that brand stores use
# ("available on Amazon Marketplace", "find a seller near you").
STRONG_MARKETPLACE_MARKERS = (
    "ships from and sold by", "sold by third-party", "sold and shipped by",
    "become a seller", "seller center", "sellercenter",
    "seller centre", "vendor dashboard", "register as a seller",
    "register as a vendor", "third-party sellers", "buy from other sellers",
    "mirakl",
)

DEFAULT_SIZE_BACKSTOP = 250_000      # product URLs; real brands (Engine ~85K) stay under
DEFAULT_REGION_BACKSTOP = 25         # distinct hreflang storefront countries → multinational
MULTI_BRAND_VENDOR_MIN = 5           # distinct vendors that make a catalog multi-brand
LARGE_MARKETPLACE_MIN = 20_000      # products: a multi-seller site this big is a Large Marketplace
GENERAL_INDUSTRY_MIN = 3             # distinct industries that make a multi-brand store "general"

TYPE_LABELS = {
    1: "Large Marketplace",
    2: "Global / Multinational Brand",
    3: "General Marketplace",
    4: "Niche / Category Marketplace",
    5: "Single-Brand Store",
}


def host_of(url: str) -> str:
    try:
        netloc = urlparse(url if "://" in (url or "") else f"https://{url}").netloc.lower()
    except Exception:
        return ""
    netloc = netloc.split("@")[-1].split(":")[0]
    return netloc[4:] if netloc.startswith("www.") else netloc


def registrable_label(url: str) -> Optional[str]:
    """The label before the public suffix (amazon.co.uk → amazon), PSL-free."""
    host = host_of(url)
    parts = [p for p in host.split(".") if p]
    if not parts:
        return None
    if len(parts) == 1:
        return parts[0]
    if parts[-2] in {"co", "com", "net", "org", "gov", "edu", "ac"} and len(parts) >= 3:
        return parts[-3]
    return parts[-2]


def _norm_label(label: Optional[str]) -> str:
    return (label or "").replace("-", "").lower()


def marketplace_domain_hit(url: str, extra: Optional[Iterable[str]] = None) -> Optional[str]:
    host = host_of(url)
    if host in MARKETPLACE_EXACT_HOSTS:
        return host
    label = _norm_label(registrable_label(url))
    deny = MARKETPLACE_DENYLIST | {_norm_label(x) for x in (extra or [])}
    return label if label and label in deny else None


def multinational_domain_hit(url: str) -> Optional[str]:
    host = host_of(url)
    if host in MULTINATIONAL_EXACT_HOSTS:
        return host
    label = _norm_label(registrable_label(url))
    return label if label and label in MULTINATIONAL_BRANDS else None


def strong_marketplace_marker(*texts: str) -> Optional[str]:
    blob = " ".join(t for t in texts if t).lower()
    for m in STRONG_MARKETPLACE_MARKERS:
        if m in blob:
            return m.strip()
    return None


def _result(t: int, confidence: str, reason: str, **extra) -> Dict[str, Any]:
    out = {
        "businessType": t,
        "businessTypeLabel": TYPE_LABELS[t],
        "scaleTier": "enterprise" if t in (1, 2) else "self_serve",
        "isMarketplace": t in (1, 3, 4),
        "isMultiBrand": t in (1, 3, 4),
        "confidence": confidence,
        "reason": reason,
    }
    out.update(extra)
    return out


def classify_business_type(
    url: str,
    *,
    html: str = "",
    robots: str = "",
    total_products: Optional[int] = None,
    vendor_count: Optional[int] = None,
    brand_model: Optional[str] = None,       # "single_brand" | "multi_brand" (AI read of titles)
    industry_count: Optional[int] = None,     # distinct industries in the taxonomy profile
    region_count: Optional[int] = None,       # distinct hreflang storefront countries
    marketplace_marker: Optional[str] = None,  # pre-computed strong marker (validate_site)
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    cfg = config or {}
    allow = {_norm_label(x) for x in (cfg.get("allowlist") or [])}
    size_backstop = int(cfg.get("sizeBackstop") or DEFAULT_SIZE_BACKSTOP)
    region_backstop = int(cfg.get("regionBackstop") or DEFAULT_REGION_BACKSTOP)
    vendor_min = int(cfg.get("multiBrandVendorMin") or MULTI_BRAND_VENDOR_MIN)
    general_min = int(cfg.get("generalIndustryMin") or GENERAL_INDUSTRY_MIN)
    large_min = int(cfg.get("largeMarketplaceMin") or LARGE_MARKETPLACE_MIN)

    label = _norm_label(registrable_label(url))
    signals = {
        "totalProducts": total_products, "vendorCount": vendor_count,
        "brandModel": brand_model, "industryCount": industry_count,
        "regionCount": region_count,
    }
    allowlisted = bool(label and label in allow)

    if not allowlisted:
        hit = marketplace_domain_hit(url, cfg.get("extraDenylist"))
        if hit:
            return _result(1, "high", f"marketplace_denylist:{hit}", signals=signals)
        marker = marketplace_marker or strong_marketplace_marker(html, robots)
        if marker:
            # Multi-seller structure. "Large" (Type 1) when the catalog is big or
            # uncountable (custom platforms — typically the big ones); a small
            # countable multi-vendor shop is a General Marketplace (Type 3).
            if not isinstance(total_products, int) or total_products >= large_min:
                return _result(1, "medium", f"marketplace_signal:{marker}", signals=signals)
            return _result(3, "medium", f"small_marketplace:{marker}:{total_products}", signals=signals)
        if isinstance(total_products, int) and total_products >= size_backstop:
            return _result(1, "medium", f"size_backstop:{total_products}", signals=signals)
        brand_hit = multinational_domain_hit(url)
        if brand_hit:
            return _result(2, "high", f"multinational_brand:{brand_hit}", signals=signals)
        if isinstance(region_count, int) and region_count >= region_backstop:
            return _result(2, "medium", f"regional_storefronts:{region_count}", signals=signals)

    multi = None
    if isinstance(vendor_count, int):
        multi = vendor_count >= vendor_min
    if brand_model in ("single_brand", "multi_brand"):
        # The AI read of product titles catches multi-brand stores whose vendor
        # field is unset (non-Shopify) and single brands with sub-label vendors.
        ai_multi = brand_model == "multi_brand"
        multi = ai_multi if multi is None else (multi or ai_multi)

    reason_prefix = "allowlisted:" if allowlisted else ""
    if multi:
        if isinstance(industry_count, int) and industry_count >= general_min:
            return _result(3, "medium", f"{reason_prefix}multi_brand:{industry_count}_industries", signals=signals)
        conf = "medium" if isinstance(industry_count, int) else "low"
        return _result(4, conf, f"{reason_prefix}multi_brand_niche", signals=signals)
    conf = "medium" if multi is False else "low"
    return _result(5, conf, f"{reason_prefix}single_brand" if multi is False else f"{reason_prefix}no_multi_brand_signal",
                   signals=signals)


def lists_payload() -> Dict[str, List[str]]:
    """Exposed to Node so competitor suggestions exclude exactly the same giants."""
    return {
        "marketplaces": sorted(MARKETPLACE_DENYLIST),
        "marketplaceHosts": sorted(MARKETPLACE_EXACT_HOSTS),
        "multinationalBrands": sorted(MULTINATIONAL_BRANDS),
        "multinationalHosts": sorted(MULTINATIONAL_EXACT_HOSTS),
    }
