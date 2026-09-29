"""
level1_detector/storefront_api.py
===================================
Shopify Storefront API (GraphQL) helpers.

Used when Playwright intercepts a Storefront access token from a headless
Shopify store's network requests.  Provides complete pricing and variant
data that isn't available in the static or Playwright-rendered HTML.
"""

import requests
import json
import re


_STOREFRONT_API_VERSION = "2024-01"

_COLLECTION_QUERY = """
query GetCollectionProducts($handle: String!, $first: Int!) {
  collection(handle: $handle) {
    title
    products(first: $first) {
      edges {
        node {
          handle
          title
          availableForSale
          priceRange {
            minVariantPrice { amount currencyCode }
            maxVariantPrice { amount currencyCode }
          }
          compareAtPriceRange {
            minVariantPrice { amount currencyCode }
          }
          variants(first: 50) {
            edges {
              node {
                id
                title
                availableForSale
                price { amount currencyCode }
                compareAtPrice { amount currencyCode }
                selectedOptions { name value }
              }
            }
          }
          featuredImage { url altText }
        }
      }
    }
  }
}
"""

_PRODUCT_QUERY = """
query GetProduct($handle: String!) {
  product(handle: $handle) {
    handle
    title
    availableForSale
    priceRange {
      minVariantPrice { amount currencyCode }
      maxVariantPrice { amount currencyCode }
    }
    compareAtPriceRange {
      minVariantPrice { amount currencyCode }
    }
    variants(first: 50) {
      edges {
        node {
          id
          title
          availableForSale
          price { amount currencyCode }
          compareAtPrice { amount currencyCode }
          selectedOptions { name value }
        }
      }
    }
    featuredImage { url altText }
    description
    vendor
  }
}
"""


def _api_url(shop_domain: str, explicit_api_url: str = None) -> str:
    """Return the GraphQL endpoint. Uses explicit_api_url if captured from
    Playwright interception (most reliable), otherwise builds from domain."""
    if explicit_api_url:
        return explicit_api_url
    return f"{shop_domain.rstrip('/')}/api/{_STOREFRONT_API_VERSION}/graphql.json"


def _headers(token: str) -> dict:
    return {
        "Content-Type": "application/json",
        "X-Shopify-Storefront-Access-Token": token,
        "Accept": "application/json",
    }


def _parse_money(money_node) -> float | None:
    if not money_node:
        return None
    try:
        return float(money_node.get("amount") or 0) or None
    except (TypeError, ValueError):
        return None


def _parse_currency(money_node) -> str:
    if not money_node:
        return "USD"
    return money_node.get("currencyCode") or "USD"


def fetch_collection_prices(shop_domain: str, token: str, collection_handle: str, limit: int = 50, explicit_api_url: str = None, currency_override: str = None) -> dict:
    """
    Query the Storefront API for all products in a collection.

    Returns a dict keyed by product handle:
        {
            "handle": {
                "name": str,
                "price": float | None,
                "compareAt": float | None,
                "currency": str,
                "inStock": bool,
                "imageUrl": str | None,
                "variants": [...],
                "options": [...],
            }
        }
    Returns {} on any failure.
    """
    try:
        resp = requests.post(
            _api_url(shop_domain, explicit_api_url),
            headers=_headers(token),
            json={"query": _COLLECTION_QUERY, "variables": {"handle": collection_handle, "first": limit}},
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"STOREFRONT API: collection query failed — {e}")
        return {}

    errors = data.get("errors")
    if errors:
        print(f"STOREFRONT API: GraphQL errors — {errors}")
        return {}

    try:
        products_edges = (
            data.get("data", {})
                .get("collection") or {}
        ).get("products", {}).get("edges") or []
    except Exception:
        return {}

    result = {}
    for edge in products_edges:
        node = edge.get("node") or {}
        handle = node.get("handle")
        if not handle:
            continue

        min_price_node = (node.get("priceRange") or {}).get("minVariantPrice")
        max_price_node = (node.get("priceRange") or {}).get("maxVariantPrice")
        compare_node = (node.get("compareAtPriceRange") or {}).get("minVariantPrice")
        currency = currency_override or _parse_currency(min_price_node)

        # Variants
        raw_variants = [e["node"] for e in (node.get("variants") or {}).get("edges", [])]
        variants = []
        options_map = {}
        for v in raw_variants:
            v_price = _parse_money(v.get("price"))
            v_compare = _parse_money(v.get("compareAtPrice"))
            v_opts = {o["name"]: o["value"] for o in (v.get("selectedOptions") or [])}
            variants.append({
                "id": v.get("id"),
                "title": v.get("title"),
                "price": v_price,
                "compareAt": v_compare,
                "currency": currency_override or _parse_currency(v.get("price")),
                "available": v.get("availableForSale", False),
                "options": v_opts,
            })
            for opt_name, opt_val in v_opts.items():
                options_map.setdefault(opt_name, set()).add(opt_val)

        options = [{"name": k, "values": sorted(v)} for k, v in options_map.items()]

        featured = node.get("featuredImage") or {}

        result[handle] = {
            "name": node.get("title"),
            "price": _parse_money(min_price_node),
            "priceMax": _parse_money(max_price_node),
            "compareAt": _parse_money(compare_node),
            "currency": currency,
            "inStock": node.get("availableForSale", False),
            "imageUrl": featured.get("url"),
            "variants": variants,
            "options": options,
        }

    print(f"STOREFRONT API: fetched {len(result)} products for collection '{collection_handle}'")
    return result


def fetch_product_prices(shop_domain: str, token: str, product_handle: str, explicit_api_url: str = None) -> dict:
    """
    Query the Storefront API for a single product's full pricing + variants.
    Returns a flat dict of fields or {} on failure.
    """
    try:
        resp = requests.post(
            _api_url(shop_domain, explicit_api_url),
            headers=_headers(token),
            json={"query": _PRODUCT_QUERY, "variables": {"handle": product_handle}},
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"STOREFRONT API: product query failed — {e}")
        return {}

    node = (data.get("data") or {}).get("product") or {}
    if not node:
        return {}

    min_price_node = (node.get("priceRange") or {}).get("minVariantPrice")
    compare_node = (node.get("compareAtPriceRange") or {}).get("minVariantPrice")
    currency = _parse_currency(min_price_node)

    raw_variants = [e["node"] for e in (node.get("variants") or {}).get("edges", [])]
    variants = []
    options_map = {}
    for v in raw_variants:
        v_price = _parse_money(v.get("price"))
        v_compare = _parse_money(v.get("compareAtPrice"))
        v_opts = {o["name"]: o["value"] for o in (v.get("selectedOptions") or [])}
        variants.append({
            "id": v.get("id"),
            "title": v.get("title"),
            "price": v_price,
            "compareAt": v_compare,
            "currency": _parse_currency(v.get("price")),
            "available": v.get("availableForSale", False),
            "options": v_opts,
        })
        for opt_name, opt_val in v_opts.items():
            options_map.setdefault(opt_name, set()).add(opt_val)

    options = [{"name": k, "values": sorted(v)} for k, v in options_map.items()]
    featured = node.get("featuredImage") or {}

    return {
        "name": node.get("title"),
        "price": _parse_money(min_price_node),
        "compareAt": _parse_money(compare_node),
        "currency": currency,
        "inStock": node.get("availableForSale", False),
        "imageUrl": featured.get("url"),
        "description": node.get("description"),
        "vendor": node.get("vendor"),
        "variants": variants,
        "options": options,
    }


def infer_shop_domain(storefront_url: str) -> str | None:
    """
    Try to infer the myshopify.com domain from a storefront URL.
    e.g. "https://skims.com" → tries "https://skims.myshopify.com"
    Only used as a fallback when Playwright didn't capture the domain.
    """
    try:
        from urllib.parse import urlparse
        parsed = urlparse(storefront_url)
        brand = parsed.netloc.split(".")[0]  # "skims" from "skims.com"
        candidate = f"https://{brand}.myshopify.com"
        # Quick probe — Shopify returns 200/301 for valid stores
        r = requests.head(candidate, timeout=8, allow_redirects=True)
        if r.status_code < 400:
            return candidate
    except Exception:
        pass
    return None
