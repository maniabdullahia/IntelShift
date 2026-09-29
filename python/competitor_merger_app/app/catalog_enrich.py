"""
catalog_enrich.py — authoritative product-depth enrichment for a merged snapshot.

WHY
----
Collection-page cards only expose what the grid shows: one thumbnail and a couple
of visible swatches. So the merged snapshot reports ~1 image and ~3 variants for a
product that actually has a full gallery and a dozen shades. Price / stock / currency
are reliable at the collection level, but *depth* (variant range, image richness,
full description) is not.

The fix is NOT to render every product page — that doesn't scale. Instead we pull
the store's BULK product source once and merge accurate depth into each product:

    1. Shopify              /products.json           (variants[], images[], body_html)
    2. WooCommerce          Store API /wp-json/...    (variations[], images[], description)
    3. Headless / JS Shopify Storefront GraphQL       (token captured in-browser)
    4. Custom SPA fallback  same-origin /products/<handle>.json  (SAMPLED + tagged)

Every path degrades gracefully: if nothing works, the card-level approximation is
kept untouched and the snapshot records depthSource="cards" so the UI can say so.

Matching is by product handle (from the handle field or the /products/<handle> URL
segment), which is stable across the bulk feed and the crawled pages.
"""

from __future__ import annotations

import json
import os
import re
from html import unescape
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

# Reuse the existing fetch stack (website_analyzer_app is on sys.path in the API).
try:  # pragma: no cover - import wiring depends on the API's sys.path
    from level1_detector.fetcher import (  # type: ignore
        fetch_with_requests,
        fetch_with_cloudscraper,
        fetch_same_origin_json,
    )
except Exception:  # pragma: no cover
    fetch_with_requests = None  # type: ignore
    fetch_with_cloudscraper = None  # type: ignore
    fetch_same_origin_json = None  # type: ignore


# ── Tunables ────────────────────────────────────────────────────────────────
PRODUCTS_JSON_PER_PAGE = 250        # Shopify hard cap per page
PRODUCTS_JSON_MAX_PAGES = 8         # up to 2000 products via REST
WOO_PER_PAGE = 100
WOO_MAX_PAGES = 15
SAMPLE_CAP = 10                     # capped per-product JSON probes for custom SPAs
MAX_IMAGE_URLS_KEPT = 20           # gallery URLs stored per product (counts are exact)


def _enabled() -> bool:
    # Escape hatch: CATALOG_DEPTH_ENRICH=0 disables the whole pass.
    return os.getenv("CATALOG_DEPTH_ENRICH", "1").strip().lower() not in ("0", "false", "no")


# ── Small helpers ─────────────────────────────────────────────────────────────
def _origin(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    try:
        p = urlparse(url if "://" in url else f"https://{url}")
        if p.scheme and p.netloc:
            return f"{p.scheme}://{p.netloc}"
    except Exception:
        return None
    return None


def _handle_from_url(url: Optional[str]) -> Optional[str]:
    """Pull the <handle> out of .../products/<handle>(.json)?(?...)."""
    if not url:
        return None
    m = re.search(r"/products/([^/?#.]+)", str(url))
    return m.group(1).strip().lower() if m else None


def _product_handle(product: Dict[str, Any]) -> Optional[str]:
    h = product.get("handle")
    if isinstance(h, str) and h.strip():
        return h.strip().lower()
    return _handle_from_url(product.get("productUrl") or product.get("url"))


_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(value: Any) -> str:
    if not value:
        return ""
    if isinstance(value, dict):
        value = value.get("text") or value.get("html") or ""
    text = _TAG_RE.sub(" ", str(value))
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _get_text(url: str) -> Optional[str]:
    """Direct fetch of a text/JSON endpoint via requests → cloudscraper.

    Returns the body text (may be an app-shell for SPAs; the callers validate that
    it parses as JSON before trusting it)."""
    for fetcher in (fetch_with_requests, fetch_with_cloudscraper):
        if not fetcher:
            continue
        try:
            html, _final, _headers = fetcher(url)
        except Exception:
            html = None
        # safe_response marks bot-blocked bodies as None; a real JSON body survives.
        if html and html.strip():
            return html
    # Last-ditch raw attempt (some hosts flag the shared UA as "blocked" wrongly).
    try:
        import requests  # local import keeps module import cheap

        r = requests.get(url, timeout=25, allow_redirects=True,
                         headers={"Accept": "application/json, */*",
                                  "User-Agent": "Mozilla/5.0 (compatible; IntelShiftBot/1.0)"})
        if r.status_code == 200 and r.text.strip():
            return r.text
    except Exception:
        pass
    return None


def _parse_json(text: Optional[str]) -> Optional[Any]:
    if not text:
        return None
    t = text.strip()
    if not (t.startswith("{") or t.startswith("[")):
        return None
    try:
        return json.loads(t)
    except Exception:
        return None


# ── Depth extraction from platform-native product objects ─────────────────────
def _depth_from_shopify_product(prod: Dict[str, Any]) -> Optional[Tuple[str, Dict[str, Any]]]:
    """A product object from /products.json or /products/<handle>.json."""
    if not isinstance(prod, dict):
        return None
    handle = (prod.get("handle") or "").strip().lower()
    if not handle:
        return None
    variants = [v for v in (prod.get("variants") or []) if isinstance(v, dict)]
    images = prod.get("images") or []
    image_urls: List[str] = []
    for im in images:
        if isinstance(im, dict) and im.get("src"):
            image_urls.append(im["src"])
        elif isinstance(im, str):
            image_urls.append(im)
    desc = _strip_html(prod.get("body_html"))
    # Distinct option-value labels (shade / size names) for the UI, not just a count.
    option_values: List[str] = []
    seen = set()
    for v in variants:
        for key in ("option1", "option2", "option3"):
            val = v.get(key)
            if isinstance(val, str) and val.strip() and val.strip().lower() not in seen:
                seen.add(val.strip().lower())
                option_values.append(val.strip())
    return handle, {
        "variantCount": len(variants),
        "imageCount": len(image_urls),
        "images": image_urls,
        "descriptionText": desc,
        "variantOptions": option_values[:30],
    }


def _depth_from_woo_product(prod: Dict[str, Any]) -> Optional[Tuple[str, Dict[str, Any]]]:
    """A product object from the WooCommerce Store API."""
    if not isinstance(prod, dict):
        return None
    permalink = prod.get("permalink") or prod.get("slug")
    handle = _handle_from_url(permalink) or (str(prod.get("slug")).strip().lower() if prod.get("slug") else None)
    if not handle:
        return None
    variations = prod.get("variations") or []
    # Simple products report no variations; count them as 1 buyable variant.
    variant_count = len(variations) if variations else 1
    images = prod.get("images") or []
    image_urls = [im.get("src") for im in images if isinstance(im, dict) and im.get("src")]
    desc = _strip_html(prod.get("description") or prod.get("short_description"))
    return handle, {
        "variantCount": variant_count,
        "imageCount": len(image_urls),
        "images": image_urls,
        "descriptionText": desc,
        "variantOptions": [],
    }


# ── Bulk source readers ───────────────────────────────────────────────────────
def _read_shopify_products_json(origin: str) -> Dict[str, Dict[str, Any]]:
    """Paginate /products.json (direct first, then in-browser same-origin)."""
    depth: Dict[str, Dict[str, Any]] = {}

    def _ingest(products: List[Any]) -> int:
        added = 0
        for prod in products or []:
            got = _depth_from_shopify_product(prod)
            if got:
                depth[got[0]] = got[1]
                added += 1
        return added

    # 1) Direct pagination (fast path for standard Shopify).
    got_any = False
    for page in range(1, PRODUCTS_JSON_MAX_PAGES + 1):
        url = f"{origin}/products.json?limit={PRODUCTS_JSON_PER_PAGE}&page={page}"
        data = _parse_json(_get_text(url))
        products = (data or {}).get("products") if isinstance(data, dict) else None
        if not products:
            break
        got_any = True
        _ingest(products)
        if len(products) < PRODUCTS_JSON_PER_PAGE:
            break

    if got_any:
        return depth

    # 2) In-browser same-origin fallback (Cloudflare / cookie-gated Shopify).
    if fetch_same_origin_json:
        paths = [f"/products.json?limit={PRODUCTS_JSON_PER_PAGE}&page={p}" for p in range(1, 4)]
        try:
            results = fetch_same_origin_json(origin, paths) or {}
        except Exception:
            results = {}
        for _path, text in results.items():
            data = _parse_json(text)
            products = (data or {}).get("products") if isinstance(data, dict) else None
            if products:
                _ingest(products)
    return depth


def _read_woo_products(origin: str) -> Dict[str, Dict[str, Any]]:
    depth: Dict[str, Dict[str, Any]] = {}
    base = f"{origin}/wp-json/wc/store/v1/products"
    got_any = False
    for page in range(1, WOO_MAX_PAGES + 1):
        url = f"{base}?per_page={WOO_PER_PAGE}&page={page}"
        data = _parse_json(_get_text(url))
        if not isinstance(data, list) or not data:
            break
        got_any = True
        for prod in data:
            got = _depth_from_woo_product(prod)
            if got:
                depth[got[0]] = got[1]
        if len(data) < WOO_PER_PAGE:
            break
    return depth if got_any else {}


def _read_shopify_graphql_depth(origin: str) -> Dict[str, Dict[str, Any]]:
    """Headless / JS Shopify: capture the Storefront token in-browser and query
    variants/images/description by handle. Mirrors fetch_shopify_graphql_catalog's
    token-capture approach but asks for depth fields."""
    depth: Dict[str, Dict[str, Any]] = {}
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except Exception:
        return depth
    try:
        from level1_detector.fetcher import _ensure_subprocess_capable_loop_policy, BROWSER_HEADERS  # type: ignore
        _ensure_subprocess_capable_loop_policy()
        ua = BROWSER_HEADERS.get("User-Agent", "Mozilla/5.0")
    except Exception:
        ua = "Mozilla/5.0"

    captured = {"token": None, "endpoint": None}
    query = (
        "{ products(first: 250) { edges { node { handle "
        "variants(first: 100) { edges { node { id } } } "
        "images(first: 50) { edges { node { url } } } description } } } }"
    )
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=[
                "--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-dev-shm-usage"])
            context = browser.new_context(user_agent=ua, locale="en-US")
            page = context.new_page()

            def _on_request(req):
                try:
                    tok = req.headers.get("x-shopify-storefront-access-token")
                    if tok and not captured["token"]:
                        captured["token"] = tok
                        captured["endpoint"] = req.url
                    elif ("graphql" in req.url.lower()) and not captured["endpoint"]:
                        captured["endpoint"] = req.url
                except Exception:
                    pass

            page.on("request", _on_request)
            try:
                page.goto(origin, wait_until="domcontentloaded", timeout=45000)
                try:
                    page.wait_for_load_state("networkidle", timeout=15000)
                except Exception:
                    pass
                for _ in range(5):
                    if captured["token"]:
                        break
                    page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
                    page.wait_for_timeout(700)
            except Exception:
                browser.close()
                return depth

            token, endpoint = captured["token"], captured["endpoint"]
            if token and (not endpoint or "graphql" not in (endpoint or "").lower()):
                _pp = urlparse(origin)
                endpoint = f"{_pp.scheme}://{_pp.netloc}/api/2024-10/graphql.json"
            if not token or not endpoint:
                browser.close()
                return depth

            text = page.evaluate(
                """async ({endpoint, token, query}) => {
                    try {
                        const r = await fetch(endpoint, { method: 'POST',
                            headers: { 'Content-Type': 'application/json', 'X-Shopify-Storefront-Access-Token': token },
                            body: JSON.stringify({ query }), credentials: 'include' });
                        if (!r.ok) return null; return await r.text();
                    } catch (e) { return null; }
                }""",
                {"endpoint": endpoint, "token": token, "query": query},
            )
            browser.close()
            data = _parse_json(text)
            edges = (((data or {}).get("data") or {}).get("products") or {}).get("edges") or []
            for e in edges:
                node = (e or {}).get("node") or {}
                handle = (node.get("handle") or "").strip().lower()
                if not handle:
                    continue
                vcount = len((((node.get("variants") or {}).get("edges")) or []))
                imgs = [((i or {}).get("node") or {}).get("url")
                        for i in (((node.get("images") or {}).get("edges")) or [])]
                imgs = [u for u in imgs if u]
                depth[handle] = {
                    "variantCount": vcount,
                    "imageCount": len(imgs),
                    "images": imgs,
                    "descriptionText": _strip_html(node.get("description")),
                    "variantOptions": [],
                }
    except Exception:
        return depth
    return depth


def _sample_custom_product_json(origin: str, handles: List[str]) -> Dict[str, Dict[str, Any]]:
    """Custom SPA fallback: many Shopify-shaped custom stores still serve
    /products/<handle>.json. Fetch a CAPPED sample in ONE in-browser session.
    Tagged as sampled by the caller so the UI can say the depth is estimated."""
    depth: Dict[str, Dict[str, Any]] = {}
    if not fetch_same_origin_json or not handles:
        return depth
    sample = handles[:SAMPLE_CAP]
    paths = [f"/products/{h}.json" for h in sample]
    try:
        results = fetch_same_origin_json(origin, paths) or {}
    except Exception:
        return depth
    for path, text in results.items():
        data = _parse_json(text)
        prod = (data or {}).get("product") if isinstance(data, dict) else None
        if not isinstance(prod, dict):
            # Some stores return the bare product object.
            prod = data if isinstance(data, dict) and data.get("handle") else None
        if not isinstance(prod, dict):
            continue
        got = _depth_from_shopify_product(prod)
        if got:
            depth[got[0]] = got[1]
    return depth


# ── Public entry point ────────────────────────────────────────────────────────
def enrich_products(
    products: List[Dict[str, Any]],
    base_url: Optional[str],
    platform_hint: Optional[str] = None,
) -> Dict[str, Any]:
    """Merge authoritative variant/image/description depth into `products` in place.

    Returns a meta dict for the snapshot quality block:
        { source, sampled, productsMatched, productsTotal, coverageRate, note }
    """
    meta: Dict[str, Any] = {
        "source": "cards",
        "sampled": False,
        "productsMatched": 0,
        "productsTotal": len(products or []),
        "coverageRate": 0.0,
        "note": None,
    }
    if not _enabled():
        meta["note"] = "Depth enrichment disabled (CATALOG_DEPTH_ENRICH=0)."
        return meta
    if not products:
        return meta

    origin = _origin(base_url)
    if not origin:
        origin = _origin((products[0] or {}).get("productUrl"))
    if not origin:
        meta["note"] = "No resolvable origin; kept card-level depth."
        return meta

    hint = (platform_hint or "").strip().lower()
    depth: Dict[str, Dict[str, Any]] = {}
    source = "cards"
    sampled = False

    # Order the bulk readers by the platform hint, but always try the others as
    # fallbacks — a store can be mislabeled, and custom SPAs mimic Shopify URLs.
    def _try_shopify():
        return _read_shopify_products_json(origin), "shopify-products-json"

    def _try_woo():
        return _read_woo_products(origin), "woocommerce-store-api"

    def _try_graphql():
        return _read_shopify_graphql_depth(origin), "shopify-graphql"

    if "woo" in hint or "wordpress" in hint:
        order = [_try_woo, _try_shopify, _try_graphql]
    else:
        order = [_try_shopify, _try_woo, _try_graphql]

    for reader in order:
        try:
            got, src = reader()
        except Exception:
            got, src = {}, None
        if got:
            depth, source = got, src
            break

    # Custom SPA fallback: no bulk feed worked → sample product JSONs (tagged).
    if not depth:
        handles = [h for h in (_product_handle(p) for p in products) if h]
        # de-dupe, preserve order
        seen, uniq = set(), []
        for h in handles:
            if h not in seen:
                seen.add(h)
                uniq.append(h)
        got = _sample_custom_product_json(origin, uniq)
        if got:
            depth, source, sampled = got, "custom-product-json-sample", True

    if not depth:
        meta["note"] = "No bulk product source reachable; kept card-level depth."
        return meta

    # ── Merge depth into products by handle ──────────────────────────────────
    matched = 0
    for product in products:
        handle = _product_handle(product)
        if not handle or handle not in depth:
            continue
        d = depth[handle]
        matched += 1

        # Variants: bulk count is authoritative; keep the richer of the two labels.
        if isinstance(d.get("variantCount"), int) and d["variantCount"] > 0:
            product["variantCount"] = d["variantCount"]
            product.setdefault("metrics", {})
            if isinstance(product["metrics"], dict):
                product["metrics"]["variantCount"] = d["variantCount"]
        if d.get("variantOptions"):
            existing_opts = product.get("variantOptions") or []
            if len(d["variantOptions"]) > len(existing_opts):
                product["variantOptions"] = d["variantOptions"]

        # Images: store exact count in metrics (the comparison normalizer reads it
        # first) and expand the gallery URLs for the UI.
        if isinstance(d.get("imageCount"), int) and d["imageCount"] > 0:
            product.setdefault("metrics", {})
            if isinstance(product["metrics"], dict):
                product["metrics"]["imageCount"] = d["imageCount"]
            imgs = d.get("images") or []
            primary = product.get("imageUrl")
            if imgs and not primary:
                product["imageUrl"] = imgs[0]
                primary = imgs[0]
            extras = [u for u in imgs if u and u != primary]
            if extras:
                product["additionalImageUrls"] = extras[:MAX_IMAGE_URLS_KEPT]

        # Description: replace only when the bulk copy is meaningfully longer.
        bulk_desc = d.get("descriptionText") or ""
        cur_desc = _strip_html(product.get("description"))
        if bulk_desc and len(bulk_desc) > len(cur_desc):
            product["description"] = {"text": bulk_desc, "html": None}

        product["depthSource"] = ("sampled" if sampled else source)

    total = len(products)
    meta.update({
        "source": source,
        "sampled": sampled,
        "productsMatched": matched,
        "productsTotal": total,
        "coverageRate": round(matched / total, 3) if total else 0.0,
        "note": (
            f"Depth from {source} for {matched}/{total} products."
            + (" Sampled subset; counts are estimates for unsampled products." if sampled else "")
        ),
    })
    return meta
