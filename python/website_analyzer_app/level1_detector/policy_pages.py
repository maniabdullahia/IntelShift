"""
policy_pages.py — discover an ecommerce store's policy / info pages.

WHY
----
Shipping, returns and payment pages carry high-signal competitive intel — free-
shipping thresholds, COD availability, delivery times, bank-deposit offers — but
nobody ever *selects* them to track. For any ecommerce site we should find and
analyze them automatically.

Discovery order per policy type:
  1. Footer / nav links the site actually exposes (most reliable — real URLs).
  2. Shopify canonical /policies/* paths (present on every Shopify store).
  3. Well-known /pages/* guesses (only when nothing better was found).

Returns a small, deduped set of {type, url, source} — capped to the types that
carry competitive value (shipping, returns, payment, faq). Privacy/terms are
skipped to save crawl budget.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse


# type -> (link keywords, shopify canonical paths, common /pages guesses)
POLICY_TYPES: Dict[str, Dict[str, Any]] = {
    "shipping": {
        "keywords": ["shipping", "delivery", "dispatch", "ship "],
        "shopify": ["/policies/shipping-policy"],
        "guesses": ["/pages/shipping-policy", "/pages/shipping", "/pages/delivery",
                    "/pages/shipping-and-returns", "/pages/shipping-and-returns-policy",
                    "/pages/shipping-returns"],
    },
    "returns": {
        "keywords": ["return", "refund", "exchange"],
        "shopify": ["/policies/refund-policy"],
        "guesses": ["/pages/return-policy", "/pages/returns", "/pages/refund-policy",
                    "/pages/returns-exchanges", "/pages/return-exchange"],
    },
    "payment": {
        "keywords": ["payment", "how to order", "how to pay", "how to buy",
                     "bank deposit", "cash on delivery", " cod", "checkout"],
        "shopify": [],
        "guesses": ["/pages/payment-methods", "/pages/payment", "/pages/how-to-order",
                    "/pages/how-to-buy", "/pages/payment-options"],
    },
    "faq": {
        "keywords": ["faq", "faqs", "frequently asked", "help center", "help centre"],
        "shopify": [],
        "guesses": ["/pages/faq", "/pages/faqs", "/pages/help"],
    },
}

# Order the crawl by competitive value.
PRIORITY = ["shipping", "returns", "payment", "faq"]


def _origin(url: str) -> Optional[str]:
    try:
        p = urlparse(url if "://" in url else f"https://{url}")
        if p.scheme and p.netloc:
            return f"{p.scheme}://{p.netloc}"
    except Exception:
        return None
    return None


def _classify(text: str, url: str) -> Optional[str]:
    blob = f"{(text or '').lower()} {(url or '').lower()}"
    for ptype in PRIORITY:
        if any(k in blob for k in POLICY_TYPES[ptype]["keywords"]):
            return ptype
    return None


def discover_policy_pages(
    base_url: str,
    footer_links: Optional[List[Dict[str, Any]]] = None,
    nav_links: Optional[List[Dict[str, Any]]] = None,
    platform: str = "",
    max_pages: int = 4,
) -> List[Dict[str, str]]:
    """Return [{type, url, source}] for the store's key policy/info pages."""
    origin = _origin(base_url)
    if not origin:
        return []

    is_shopify = "shopify" in (platform or "").lower()
    found: Dict[str, Dict[str, str]] = {}

    # 1) Real links the site exposes (footer first, then nav).
    for links, src in ((footer_links or [], "footer"), (nav_links or [], "nav")):
        for link in links:
            if not isinstance(link, dict):
                continue
            url = link.get("url") or link.get("href")
            text = link.get("text") or link.get("label") or ""
            if not url:
                continue
            ptype = _classify(text, url)
            if not ptype or ptype in found:
                continue
            abs_url = urljoin(origin + "/", url)
            # Keep same-origin links only.
            if _origin(abs_url) != origin:
                continue
            found[ptype] = {"type": ptype, "url": abs_url, "source": src}

    # 2) Shopify canonical /policies/* for anything still missing.
    if is_shopify:
        for ptype in PRIORITY:
            if ptype in found:
                continue
            for path in POLICY_TYPES[ptype]["shopify"]:
                found[ptype] = {"type": ptype, "url": origin + path, "source": "shopify_canonical"}
                break

    # 3) Well-known /pages guesses only for types with no evidence yet. These MAY
    # 404 — callers analyze them best-effort (a 404 is dropped downstream).
    for ptype in PRIORITY:
        if ptype in found:
            continue
        guesses = POLICY_TYPES[ptype]["guesses"]
        if guesses:
            found[ptype] = {"type": ptype, "url": origin + guesses[0], "source": "guess"}

    ordered = [found[t] for t in PRIORITY if t in found]
    return ordered[:max_pages]
