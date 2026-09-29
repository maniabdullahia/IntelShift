"""
marketplace_gate.py — decide whether a store is self-serve or must go Enterprise.

WHY (calibrated from real data)
--------------------------------
Catalog SIZE cannot be the block signal. Measured on live stores, normal single-
brand shops the product should ALLOW already run huge by product-URL count
(Outfitters ~18K, Gymshark ~50K, Engine ~85K — Shopify counts each colourway as a
separate product), and mega-brands / marketplaces are BOTH uncountable by the
Shopify/Woo methods (Nike is on a custom platform; Daraz is a Lazada marketplace) —
so size alone can't tell Nike (allow) from Daraz (block).

The real line is MARKETPLACE vs BRAND:
  • Marketplace (Amazon, Daraz, eBay…) — millions of third-party listings, many
    sellers, no single brand. The comparison model doesn't apply → Enterprise.
  • Brand store (Sivanna, Gymshark, Nike, Khaadi…) — one brand, fits the model →
    self-serve, regardless of catalog size.

So: block on marketplace signals (denylist + structure). Use size only as a very
high backstop for unlisted marketplaces, and otherwise as a pricing/tier hint.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse


# Known marketplaces / multi-seller giants. Matched against the registrable domain,
# so "www.amazon.co.uk" and "amazon.in" both hit "amazon".
MARKETPLACE_DENYLIST = {
    "amazon", "ebay", "daraz", "aliexpress", "alibaba", "walmart", "etsy",
    "shein", "temu", "flipkart", "noon", "jumia", "lazada", "shopee",
    "mercadolibre", "mercadolivre", "rakuten", "wish", "wayfair", "newegg",
    "olx", "gumtree", "target", "bestbuy", "kohls", "macys", "trendyol",
    "meesho", "myntra", "snapdeal", "zalando", "allegro", "coupang",
    "taobao", "tmall", "jd", "ozon", "bol", "cdiscount", "backmarket",
    "poshmark", "depop", "mercari", "reverb", "stockx", "goat",
}

# High-confidence marketplace structural markers (in HTML / scripts / robots). Kept
# strict to avoid flagging a brand store that merely says "sold out".
MARKETPLACE_MARKERS = (
    "ships from and sold by", "sold by third-party", "sold and shipped by",
    "become a seller", "seller center", "sellercenter", "open a store",
    "list your products", "vendor dashboard", "marketplace",
    "mirakl", "lazada", "shopee", "/seller/", "/sellers/", "sold by seller",
    "third-party sellers", "multiple sellers", "buy from other sellers",
)

# Only catalogs bigger than this (product URLs) get force-routed to Enterprise as an
# unlisted-marketplace backstop. Set high on purpose — real brand stores (Engine
# ~85K) must stay well under it.
DEFAULT_SIZE_BACKSTOP = 250_000
# Distinct-vendor count that looks like a marketplace rather than a brand (+ a few
# stockists). A single brand shows 1–2 vendors; a marketplace shows hundreds.
DEFAULT_VENDOR_BACKSTOP = 40


def _registrable_domain(url: str) -> Optional[str]:
    """Best-effort registrable name (the label before the public suffix) without a
    PSL dependency: strips www and returns the domain's main label."""
    if not url:
        return None
    try:
        netloc = urlparse(url if "://" in url else f"https://{url}").netloc.lower()
    except Exception:
        return None
    if not netloc:
        return None
    netloc = netloc.split(":")[0]
    parts = [p for p in netloc.split(".") if p]
    if len(parts) < 2:
        return netloc or None
    # Handle multi-part suffixes like co.uk / com.pk / com.au: the registrable label
    # is the part before a (2-label) public suffix.
    two = ".".join(parts[-2:])
    common_second_level = {"co", "com", "net", "org", "gov", "edu", "ac"}
    if parts[-2] in common_second_level and len(parts) >= 3:
        return parts[-3]
    return parts[-2]


def _hit_denylist(url: str, extra_denylist: Optional[set] = None) -> Optional[str]:
    reg = _registrable_domain(url)
    if not reg:
        return None
    deny = MARKETPLACE_DENYLIST | (extra_denylist or set())
    return reg if reg in deny else None


def _hit_markers(*texts: str) -> Optional[str]:
    blob = " ".join(t for t in texts if t).lower()
    for m in MARKETPLACE_MARKERS:
        if m in blob:
            return m
    return None


def classify_scale(
    url: str,
    platform: str = "",
    total_products: Optional[int] = None,
    html: str = "",
    robots: str = "",
    vendor_count: Optional[int] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Return { scaleTier, isMarketplace, totalProducts, reason }.

    scaleTier ∈ { "self_serve", "enterprise" }.
    Block reasons are marketplace-first; size is only a high backstop.
    """
    cfg = config or {}
    allowlist = set(cfg.get("allowlist") or [])
    extra_denylist = set(cfg.get("extraDenylist") or [])
    size_backstop = int(cfg.get("sizeBackstop") or DEFAULT_SIZE_BACKSTOP)
    vendor_backstop = int(cfg.get("vendorBackstop") or DEFAULT_VENDOR_BACKSTOP)

    reg = _registrable_domain(url)

    # Manual allowlist wins (support override for false positives).
    if reg and reg in allowlist:
        return {"scaleTier": "self_serve", "isMarketplace": False,
                "totalProducts": total_products, "reason": "allowlisted"}

    # 1) Known marketplace domain.
    deny_hit = _hit_denylist(url, extra_denylist)
    if deny_hit:
        return {"scaleTier": "enterprise", "isMarketplace": True,
                "totalProducts": total_products, "reason": f"marketplace_denylist:{deny_hit}"}

    # 2) Marketplace structure in the page / robots.
    marker = _hit_markers(html, robots)
    if marker:
        return {"scaleTier": "enterprise", "isMarketplace": True,
                "totalProducts": total_products, "reason": f"marketplace_signal:{marker}"}

    # 3) Many distinct vendors → multi-seller.
    if isinstance(vendor_count, int) and vendor_count >= vendor_backstop:
        return {"scaleTier": "enterprise", "isMarketplace": True,
                "totalProducts": total_products, "reason": f"many_vendors:{vendor_count}"}

    # 4) Absurd catalog size → unlisted-marketplace backstop (NOT a normal brand).
    if isinstance(total_products, int) and total_products >= size_backstop:
        return {"scaleTier": "enterprise", "isMarketplace": False,
                "totalProducts": total_products, "reason": f"size_backstop:{total_products}"}

    # Otherwise a brand store (any countable size, or uncountable custom/SFCC) → allow.
    return {"scaleTier": "self_serve", "isMarketplace": False,
            "totalProducts": total_products,
            "reason": "brand_store" if total_products is None else f"brand_store:{total_products}"}
