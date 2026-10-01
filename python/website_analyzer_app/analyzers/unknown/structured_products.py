"""
structured_products.py — product lists from STRUCTURED data on a listing page.

Custom / headless / JS storefronts (Next.js, Nuxt, Remix, Magento, BigCommerce,
Squarespace, SFCC…) often render a product grid the DOM extractor reads poorly
(missing prices, generic card text), yet ship the same data machine-readably:

  1. JSON-LD  — schema.org ItemList (itemListElement → Product / ListItem) and
                standalone Product nodes with offers.price + priceCurrency.
  2. Hydration state — __NEXT_DATA__, __NUXT__, __INITIAL_STATE__, Apollo cache,
                generic application/json scripts (via react_hydration.py).

Output matches the Unknown collection extractor's product dicts (title, url,
image, price as a display string, allPrices, source) so it merges by URL.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from .react_hydration import extract_react_hydration_products

_SYMBOL = {"USD": "$", "CAD": "$", "AUD": "$", "NZD": "$", "SGD": "$", "GBP": "£", "EUR": "€", "INR": "₹"}


def _fmt_price(amount: Any, currency: Optional[str]) -> Optional[str]:
    try:
        v = float(str(amount).replace(",", ""))
    except (TypeError, ValueError):
        return None
    if v <= 0:
        return None
    num = f"{v:,.2f}".rstrip("0").rstrip(".") if v != int(v) else f"{int(v):,}"
    cur = (currency or "").upper()
    if cur in _SYMBOL:
        return f"{_SYMBOL[cur]}{num}"
    return f"{num} {cur}" if cur else num


def _first(v: Any) -> Any:
    return v[0] if isinstance(v, list) and v else v


def _image(v: Any, base_url: str) -> Optional[str]:
    v = _first(v)
    if isinstance(v, dict):
        v = v.get("url") or v.get("contentUrl")
    return urljoin(base_url, v) if isinstance(v, str) and v else None


def _offer_price(offers: Any) -> tuple:
    offers = _first(offers)
    if not isinstance(offers, dict):
        return None, None
    price = offers.get("price") or offers.get("lowPrice")
    if price is None and isinstance(offers.get("priceSpecification"), dict):
        price = offers["priceSpecification"].get("price")
    return price, offers.get("priceCurrency")


def _iter_nodes(data: Any) -> Iterable[Dict[str, Any]]:
    stack = [data]
    while stack:
        node = stack.pop()
        if isinstance(node, list):
            stack.extend(node)
        elif isinstance(node, dict):
            yield node
            for k in ("@graph", "itemListElement", "item", "mainEntity", "hasPart"):
                if k in node:
                    stack.append(node[k])


def _types(node: Dict[str, Any]) -> set:
    t = node.get("@type")
    return {str(x).lower() for x in (t if isinstance(t, list) else [t]) if x}


def jsonld_products(soup: BeautifulSoup, base_url: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for s in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(s.string or s.get_text() or "")
        except Exception:
            continue
        for node in _iter_nodes(data):
            types = _types(node)
            if "product" in types or ("listitem" in types and isinstance(node.get("url"), str) and node.get("name")):
                name = node.get("name")
                url = node.get("url") or node.get("@id")
                if not isinstance(name, str) or not isinstance(url, str):
                    continue
                price, cur = _offer_price(node.get("offers"))
                p = _fmt_price(price, cur)
                out.append({
                    "title": re.sub(r"\s+", " ", name).strip(),
                    "url": urljoin(base_url, url.split("#")[0]),
                    "image": _image(node.get("image"), base_url),
                    "price": p,
                    "allPrices": [p] if p else [],
                    "currency": cur,
                    "source": "jsonld",
                })
    return out


def _path(u: Optional[str]) -> str:
    try:
        return urlparse(u or "").path.rstrip("/").lower()
    except Exception:
        return ""


def structured_collection_products(html: str, soup: BeautifulSoup, base_url: str, limit: int = 120) -> Dict[str, Any]:
    """{ products:[...], counts:{jsonld, hydration} } — deduped by URL path,
    JSON-LD first (it carries exact price + currency)."""
    ld = jsonld_products(soup, base_url)
    try:
        hyd = extract_react_hydration_products(html or "", base_url, limit=limit)
    except Exception:
        hyd = []
    merged, seen = [], set()
    for p in ld + hyd:
        k = _path(p.get("url"))
        if not k or k in seen:
            continue
        seen.add(k)
        if p.get("source") == "react_hydration":
            # hydration prices are raw values; keep display strings consistent
            pr = p.get("price")
            if pr is not None and not isinstance(pr, str):
                pr = _fmt_price(pr, None)
            p = {**p, "price": pr, "allPrices": [pr] if pr else []}
        merged.append(p)
    return {"products": merged[:limit], "counts": {"jsonld": len(ld), "hydration": len(hyd)}}


def merge_structured_into(products: List[Dict[str, Any]], structured: List[Dict[str, Any]], is_valid) -> Dict[str, int]:
    """Fill missing price/image/title on DOM products by URL, then append
    structured-only products that pass the extractor's own validity check.
    Mutates `products`; returns {"filled": n, "added": m}."""
    by_path = {_path(p.get("url")): p for p in products if p.get("url")}
    filled = added = 0
    for sp in structured:
        k = _path(sp.get("url"))
        if not k:
            continue
        dom = by_path.get(k)
        if dom is not None:
            changed = False
            if sp.get("price") and dom.get("price") in (None, "", "unfetched"):
                dom["price"] = sp["price"]
                dom["allPrices"] = sp.get("allPrices") or [sp["price"]]
                changed = True
            if sp.get("image") and not dom.get("image"):
                dom["image"] = sp["image"]
                changed = True
            if sp.get("title") and not dom.get("title"):
                dom["title"] = sp["title"]
                changed = True
            filled += int(changed)
        elif is_valid(sp):
            products.append(dict(sp))
            by_path[k] = sp
            added += 1
    return {"filled": filled, "added": added}
