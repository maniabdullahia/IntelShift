"""
Site-readiness validation for onboarding.

Before we let a user confirm their own store (or a competitor), we must be sure we
can ACTUALLY read the three page types every analysis depends on — regardless of
platform (Shopify / WooCommerce / Wix / Squarespace / custom / fully JS-rendered):

  1. Homepage        — real content, not an empty JS app shell.
  2. Collection page — a category/listing that shows multiple products.
  3. Product page    — a single product with a price (and, ideally, a currency).

The key: many stores are client-side rendered, so a plain HTTP fetch returns a
1-2 KB shell with no products (this is exactly what stdbeauty.com does). We fetch
fast first (requests → cloudscraper) and, whenever the result looks like a shell
or is blocked, escalate to a REAL browser (Playwright) that executes the JS. The
product page is also where we read the store's currency.

Returns a structured, staged result so the UI can show progress and, on failure,
say which page type we couldn't reach.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

from .fetcher import fetch_with_requests, fetch_with_cloudscraper, fetch_with_playwright
from .net_guard import is_public_url
from .business_type import strong_marketplace_marker
from .store_profile import (
    countries_mentioned, detect_language, find_cart_link, find_search,
    hreflang_countries, jsonld_market, localization_countries, resolve_market,
    shipping_scope_from_text,
)


# ── Tunables ────────────────────────────────────────────────────────────────
MIN_HOME_TEXT = 400          # a real homepage renders far more visible text than a shell
MIN_HOME_LINKS = 8           # …and links to many internal pages
MIN_COLLECTION_PRODUCTS = 2  # a listing shows several products
MAX_CANDIDATES = 4           # how many collection/product URLs to try before giving up

# URL path fragments that usually denote a category/collection listing.
COLLECTION_HINTS = (
    "/collections", "/collection/", "/shop", "/category", "/categories",
    "/product-category", "/product-cat", "/products", "/store", "/c/", "/catalog",
)
# URL path fragments that usually denote a single product page.
PRODUCT_HINTS = ("/product/", "/products/", "/p/", "/dp/", "/item/", "/shop/")
# A URL shaped like a category listing (…/collections/x, /product-category/x,
# /shop/x) — a price alone on such a page doesn't make it a product page.
LISTING_PATH_RE = re.compile(r"/(collections|collection|category|categories|product-category|product-cat|shop|c)/[^/]+/?$")
# Common collection paths to try directly when the homepage exposes no obvious link.
COLLECTION_FALLBACK_PATHS = ("/collections/all", "/shop", "/products", "/store", "/catalog")
# Policy/info pages that often state the currency explicitly ("prices are in PKR").
POLICY_PATHS = (
    "/policies/shipping-policy", "/policies/refund-policy", "/policies/terms-of-service",
    "/pages/shipping-policy", "/pages/refund-policy", "/pages/shipping", "/pages/terms",
    "/shipping-policy", "/refund-policy",
)

# Unambiguous currency symbols → ISO code. Ambiguous ones ($ , Rs, kr) resolve via
# explicit codes, platform/analytics objects, or a country cue on the page.
SYMBOL_CURRENCY = {"£": "GBP", "€": "EUR", "₹": "INR", "₺": "TRY", "₩": "KRW", "₪": "ILS", "฿": "THB"}
# Every ISO code we accept from a script/analytics object (so a stray 3-letter key
# like "IMG" can't be mistaken for a currency).
CURRENCY_CODES = {
    "USD", "EUR", "GBP", "PKR", "INR", "AED", "SAR", "CAD", "AUD", "SGD", "MYR", "BDT",
    "LKR", "NPR", "ZAR", "NGN", "EGP", "JPY", "CNY", "TRY", "IDR", "PHP", "THB", "QAR",
    "KWD", "BHD", "OMR", "NZD", "HKD", "CHF", "SEK", "NOK", "DKK", "PLN", "MXN", "BRL",
    "RUB", "KRW", "ILS", "VND", "TWD", "CZK", "HUF", "RON", "CLP", "COP", "ARS",
}
ISO_NEAR_PRICE_RE = re.compile(r"\b(" + "|".join(sorted(CURRENCY_CODES)) + r")\b")
PRICE_NEAR_RE = re.compile(r"(?:[$£€₹₨]|Rs\.?|USD|EUR|GBP|PKR|INR|AED)\s?\d[\d.,]*", re.I)

# Currency named inside a rendered JS object — Shopify (ShopifyAnalytics.meta.currency,
# Shopify.currency.active), GA4/gtag/dataLayer (currency:'XXX'), Meta Pixel, and the
# generic "presentmentCurrency"/"shopCurrency"/"currencyCode"/"currency" keys.
SCRIPT_CURRENCY_RES = [
    re.compile(r'"active"\s*:\s*"([A-Za-z]{3})"'),
    re.compile(r'"presentmentCurrency"\s*:\s*"([A-Za-z]{3})"'),
    re.compile(r'"shopCurrency"\s*:\s*"([A-Za-z]{3})"'),
    re.compile(r'"currencyCode"\s*:\s*"([A-Za-z]{3})"'),
    re.compile(r'"currency"\s*:\s*"([A-Za-z]{3})"'),
    re.compile(r'''currency["']?\s*[:=]\s*["']([A-Za-z]{3})["']'''),
]

# Country name on the page → currency, to resolve an AMBIGUOUS symbol ($, Rs, kr).
# Ordered so multi-word names are matched before bare tokens.
COUNTRY_CURRENCY_CUE = [
    ("united arab emirates", "AED"), ("saudi arabia", "SAR"), ("sri lanka", "LKR"),
    ("united kingdom", "GBP"), ("united states", "USD"), ("new zealand", "NZD"),
    ("hong kong", "HKD"), ("south africa", "ZAR"), ("pakistan", "PKR"), ("india", "INR"),
    ("nepal", "NPR"), ("bangladesh", "BDT"), ("canada", "CAD"), ("australia", "AUD"),
    ("singapore", "SGD"), ("malaysia", "MYR"), ("indonesia", "IDR"), ("philippines", "PHP"),
    ("thailand", "THB"), ("nigeria", "NGN"), ("qatar", "QAR"), ("kuwait", "KWD"),
    ("bahrain", "BHD"), ("oman", "OMR"), ("sweden", "SEK"), ("norway", "NOK"),
    ("denmark", "DKK"), ("britain", "GBP"),
]
# Phone country-dialling codes → currency (from a footer/contact number).
PHONE_CODE_CURRENCY = [("+92", "PKR"), ("+91", "INR"), ("+94", "LKR"), ("+977", "NPR"),
                       ("+880", "BDT"), ("+971", "AED"), ("+966", "SAR"), ("+44", "GBP"),
                       ("+61", "AUD"), ("+64", "NZD"), ("+65", "SGD"), ("+63", "PHP")]
AMBIGUOUS_SYMBOL_RE = re.compile(r"[$₨]|\bRs\.?\b|\bkr\b", re.I)


def _host(url: str) -> str:
    try:
        host = (urlparse(url).hostname or "").lower()
        return host[4:] if host.startswith("www.") else host
    except Exception:
        return ""


def _same_site(a: str, b: str) -> bool:
    return _host(a) == _host(b)


def _visible_text(soup: BeautifulSoup) -> str:
    for tag in soup(["script", "style", "noscript", "template"]):
        tag.extract()
    return re.sub(r"\s+", " ", soup.get_text(" ", strip=True))


def _internal_links(soup: BeautifulSoup, base_url: str) -> List[str]:
    out, seen = [], set()
    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        full = urljoin(base_url, href)
        if not full.startswith("http"):
            continue
        if not _same_site(full, base_url):
            continue
        clean = full.split("#")[0]
        if clean in seen:
            continue
        seen.add(clean)
        out.append(clean)
    return out


def _looks_like_shell(html: str) -> bool:
    """True when the fetched HTML is an empty JS app shell (needs rendering)."""
    if not html:
        return True
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        return len(html) < 2000
    text = _visible_text(soup)
    links = soup.find_all("a", href=True)
    return len(text) < MIN_HOME_TEXT or len(links) < MIN_HOME_LINKS


def _fetch(url: str, force_render: bool = False) -> Tuple[Optional[str], str]:
    """Fetch a page, escalating to a real browser when the fast result is a shell
    or blocked. Returns (html, final_url). html is None only if nothing worked."""
    html, final = None, url
    if not force_render:
        for fn in (fetch_with_requests, fetch_with_cloudscraper):
            try:
                h, furl, _ = fn(url)
            except Exception:
                h, furl = None, None
            if h and not _looks_like_shell(h):
                return h, (furl or url)
            if h and not html:
                html, final = h, (furl or url)  # keep the shell as a last resort
    # Render: fast fetch failed or returned a shell → execute JS in a real browser.
    try:
        h, furl, _ = fetch_with_playwright(url)
        if h:
            return h, (furl or url)
    except Exception:
        pass
    return html, final


def _count_products(soup: BeautifulSoup, base_url: str) -> Tuple[int, List[str]]:
    """Count product links on a listing page and return them (deduped)."""
    prod, seen = [], set()
    for a in soup.find_all("a", href=True):
        full = urljoin(base_url, (a.get("href") or "").split("#")[0])
        if not full.startswith("http") or not _same_site(full, base_url):
            continue
        path = urlparse(full).path.lower()
        if any(h in path for h in PRODUCT_HINTS) and full not in seen:
            # A collection root like /products (no slug after it) isn't a product.
            tail = path.rstrip("/").rsplit("/", 1)[-1]
            if tail and tail not in ("product", "products", "p", "shop", "item"):
                seen.add(full)
                prod.append(full)
    # JSON-LD ItemList is a strong secondary signal even when links are JS-built.
    if len(prod) < MIN_COLLECTION_PRODUCTS:
        for s in soup.find_all("script", type="application/ld+json"):
            if s.string and ('"ItemList"' in s.string or '"Product"' in s.string):
                # Count Product entries as a proxy — we still return the link list.
                prod_count_hint = s.string.count('"Product"')
                if prod_count_hint >= MIN_COLLECTION_PRODUCTS:
                    return max(len(prod), prod_count_hint), prod
    return len(prod), prod


def _is_product_page(soup: BeautifulSoup, page_url: Optional[str] = None) -> Tuple[bool, Optional[str]]:
    """True + currency when a page looks like a single product (price present)."""
    currency = _extract_currency(soup)
    # JSON-LD Product with an offer price is the most reliable signal.
    for s in soup.find_all("script", type="application/ld+json"):
        if s.string and '"Product"' in s.string and ('"price"' in s.string or '"offers"' in s.string):
            return True, currency or _extract_currency(soup)
    # Add-to-cart control + a visible price is a strong platform-agnostic signal.
    text = _visible_text(soup)
    has_price = bool(PRICE_NEAR_RE.search(text))
    add_to_cart = bool(soup.find(
        lambda t: t.name in ("button", "a", "input")
        and re.search(r"add to (cart|bag|basket)|buy now|add to trolley", (t.get_text(" ") or "") + " " + " ".join(t.get("value", "") if isinstance(t.get("value"), str) else []), re.I)
    ))
    if has_price and add_to_cart:
        return True, currency
    # A price without a detectable add-to-cart control is ambiguous: listing
    # pages show prices too (WooCommerce /shop/<category>/ matched our "/shop/"
    # product hint). Reject it when the URL itself is shaped like a listing.
    # (We don't count product links — real product pages carry "related
    # products" carousels and would be rejected.)
    if has_price:
        path = urlparse(page_url).path.lower() if page_url else ""
        if path and LISTING_PATH_RE.search(path) and not re.search(r"/products?/", path):
            return False, currency
        return True, currency
    return False, currency


def _raw_json_get(url: str) -> Any:
    """Raw JSON GET that bypasses safe_response (which nulls body-less API
    responses). Uses cloudscraper to clear Cloudflare, falling back to requests."""
    if not is_public_url(url):
        return None
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "application/json,text/plain,*/*",
    }
    try:
        import cloudscraper
        sess = cloudscraper.create_scraper(browser={"browser": "chrome", "platform": "windows", "mobile": False})
    except Exception:
        import requests as sess  # type: ignore
    try:
        r = sess.get(url, headers=headers, timeout=15)
        if getattr(r, "ok", False):
            return r.json()
    except Exception:
        return None
    return None


def _shopify_currency(origin: str) -> Optional[str]:
    """The store's configured currency straight from Shopify's public endpoints —
    reliable even when the price on the page uses an ambiguous symbol like 'Rs.'."""
    for path in ("/cart.json", "/meta.json"):
        data = _raw_json_get(origin + path)
        if isinstance(data, dict):
            cur = data.get("currency") or (data.get("shop") or {}).get("currency")
            if isinstance(cur, str) and re.fullmatch(r"[A-Za-z]{3}", cur):
                return cur.upper()
    return None


def _country_currency_from_text(text: str) -> Optional[str]:
    """Resolve an ambiguous symbol via the country the page targets — the same cue a
    human uses (shipping/COD copy, footer address, a +NN phone code)."""
    low = text.lower()
    for kw, code in COUNTRY_CURRENCY_CUE:
        if kw in low:
            return code
    for prefix, code in PHONE_CODE_CURRENCY:
        if prefix in text:
            return code
    return None


def _extract_currency(soup: BeautifulSoup) -> Optional[str]:
    text = _visible_text_keep_scripts(soup)  # visible text only (for symbols/country)
    scripts_text = " ".join((s.string or s.get_text() or "") for s in soup.find_all("script"))

    # 1) Explicit meta / microdata currency codes (exact ISO).
    for sel in (
        ("meta", {"property": "product:price:currency"}),
        ("meta", {"property": "og:price:currency"}),
        ("meta", {"itemprop": "priceCurrency"}),
    ):
        tag = soup.find(sel[0], attrs=sel[1])
        if tag and tag.get("content"):
            code = str(tag["content"]).strip().upper()
            if code in CURRENCY_CODES:
                return code
    # 2) JSON-LD offers.priceCurrency.
    m = re.search(r'"priceCurrency"\s*:\s*"([A-Za-z]{3})"', scripts_text)
    if m and m.group(1).upper() in CURRENCY_CODES:
        return m.group(1).upper()
    # 3) Platform / analytics objects in the rendered JS (Shopify ShopifyAnalytics.meta
    #    .currency & Shopify.currency.active, GA4/gtag/dataLayer, Meta Pixel, generic
    #    presentmentCurrency/shopCurrency/currencyCode/currency keys). Exact ISO codes.
    for rx in SCRIPT_CURRENCY_RES:
        for cand in rx.findall(scripts_text):
            if cand.upper() in CURRENCY_CODES:
                return cand.upper()
    # 4) An ISO code sitting next to a price in the visible text ("PKR 354").
    m = ISO_NEAR_PRICE_RE.search(text)
    if m:
        return m.group(1).upper()
    # 5) Unambiguous symbol (£ € ₹ …).
    for sym, code in SYMBOL_CURRENCY.items():
        if sym in text:
            return code
    # 6) Ambiguous symbol ($, Rs, ₨, kr) → resolve by the country the page targets.
    if AMBIGUOUS_SYMBOL_RE.search(text):
        by_country = _country_currency_from_text(text)
        if by_country:
            return by_country
    return None


def _visible_text_keep_scripts(soup: BeautifulSoup) -> str:
    """Visible text WITHOUT mutating the soup (so script scanning still works after).
    _visible_text() strips <script>/<style> in place, which would blank scripts_text."""
    parts = []
    for el in soup.find_all(string=True):
        parent = getattr(el, "parent", None)
        if parent is not None and parent.name in ("script", "style", "noscript", "template"):
            continue
        parts.append(str(el))
    return re.sub(r"\s+", " ", " ".join(parts)).strip()


def _policy_currency(origin: str) -> Optional[str]:
    """Last resort: shipping/refund/terms pages usually state the currency outright
    ('All prices are in PKR') or at least name the country. Checked only when nothing
    on the product page resolved it."""
    for p in POLICY_PATHS[:5]:
        html, _ = _fetch(origin + p)
        if not html:
            continue
        soup = BeautifulSoup(html, "lxml")
        cur = _extract_currency(soup)
        if cur:
            return cur
        text = _visible_text_keep_scripts(soup)
        m = re.search(
            r'(?:all\s+)?prices?\s+(?:are\s+)?(?:quoted|charged|listed|shown|displayed|billed|processed)?\s*in\s+([A-Za-z]{3})\b',
            text, re.I,
        )
        if m and m.group(1).upper() in CURRENCY_CODES:
            return m.group(1).upper()
    return None


# ── Store-profile probes (fast HTTP only — no browser) ───────────────────────
QUICK_TIMEOUT = 12
POLICY_SCOPE_PATHS = (
    "/policies/shipping-policy", "/pages/shipping", "/pages/shipping-policy",
    "/pages/delivery", "/shipping-policy", "/shipping", "/delivery",
    "/pages/shipping-delivery", "/delivery-information",
)
_CHALLENGE_RE = re.compile(r"cf-chl|captcha|verify you are human|checking your browser|access denied", re.I)


def _quick_get(url: str, timeout: int = QUICK_TIMEOUT) -> Tuple[Optional[int], Optional[str], str]:
    """(status, final_url, text) with a plain browser-like GET. Never raises."""
    if not is_public_url(url):
        return None, url, ""
    import requests
    try:
        r = requests.get(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }, timeout=timeout, allow_redirects=True)
        if r.url and not is_public_url(r.url):
            return None, r.url, ""
        return r.status_code, r.url, (r.text or "")[:400_000]
    except Exception:
        return None, url, ""


def _stage_from_response(status: Optional[int], text: str, url: Optional[str]) -> Dict[str, Any]:
    if status is None:
        return {"ok": False, "status": "error", "url": url}
    if status in (401, 403, 418, 429, 451, 503) or (status >= 400 and _CHALLENGE_RE.search(text or "")):
        return {"ok": False, "status": "blocked", "url": url, "httpStatus": status}
    if status == 404:
        return {"ok": None, "status": "not_available", "url": url, "httpStatus": status}
    if status >= 400:
        return {"ok": False, "status": "error", "url": url, "httpStatus": status}
    if _CHALLENGE_RE.search((text or "")[:5000]) and len(text or "") < 15000:
        return {"ok": False, "status": "blocked", "url": url, "httpStatus": status}
    return {"ok": True, "status": "ok", "url": url, "httpStatus": status}


def _probe_search(home_soup, home_url: str, origin: str) -> Dict[str, Any]:
    info = find_search(home_soup, home_url)
    if not info.get("found"):
        # Shopify and WooCommerce always expose search even when the theme hides
        # the box — try the platform URLs before calling it unavailable.
        for cand in (f"{origin}/search?q=new", f"{origin}/?s=new&post_type=product"):
            st, final, text = _quick_get(cand)
            stage = _stage_from_response(st, text, final)
            if stage["status"] == "ok" and "search" in (final or "").lower() + text[:3000].lower():
                stage["via"] = "platform_url"
                return stage
        return {"ok": None, "status": "not_available", "url": None}
    action = info.get("action") or f"{origin}/search"
    param = info.get("param") or "q"
    sep = "&" if "?" in action else "?"
    st, final, text = _quick_get(f"{action}{sep}{param}=new")
    stage = _stage_from_response(st, text, final)
    stage["via"] = info.get("via")
    return stage


def _probe_cart(home_soup, home_url: str, origin: str) -> Dict[str, Any]:
    cands = [c for c in (find_cart_link(home_soup, home_url), f"{origin}/cart") if c]
    last = {"ok": False, "status": "error", "url": None}
    for cand in dict.fromkeys(cands):
        st, final, text = _quick_get(cand)
        stage = _stage_from_response(st, text, final)
        if stage["status"] in ("ok", "blocked"):
            return stage
        last = stage
    # Headless / JS carts: the Shopify cart API still answers.
    st, final, text = _quick_get(f"{origin}/cart.js")
    if st == 200 and text.strip().startswith("{"):
        return {"ok": True, "status": "ok", "url": final, "via": "cart_api"}
    return last


def _probe_checkout(origin: str) -> Dict[str, Any]:
    # With an empty cart Shopify/Woo redirect /checkout back to the cart — that
    # still proves the checkout route is reachable (we never place orders).
    st, final, text = _quick_get(f"{origin}/checkout")
    stage = _stage_from_response(st, text, final)
    if stage["status"] == "ok" and final and "/cart" in final.lower():
        stage["note"] = "redirects to cart when empty"
    return stage


def _catalog_sample(origin: str, collection_soup, collection_url: Optional[str]) -> Dict[str, Any]:
    """Titles / vendors / product types for business-type + taxonomy. Shopify
    products.json, then WooCommerce Store API, then the collection page links."""
    data = _raw_json_get(f"{origin}/products.json?limit=250")
    if isinstance(data, dict) and isinstance(data.get("products"), list) and data["products"]:
        prods = data["products"]
        vendors = [str(p.get("vendor") or "").strip() for p in prods if p.get("vendor")]
        return {
            "source": "shopify",
            "titles": [str(p.get("title") or "").strip() for p in prods if p.get("title")][:60],
            "vendorCount": len({v.lower() for v in vendors}),
            "vendorsTop": [v for v, _ in Counter(vendors).most_common(12)],
            "productTypes": [t for t, _ in Counter(str(p.get("product_type") or "").strip() for p in prods if p.get("product_type")).most_common(30)],
        }
    data = _raw_json_get(f"{origin}/wp-json/wc/store/v1/products?per_page=100")
    if isinstance(data, list) and data:
        brands = []
        for p in data:
            for b in (p.get("brands") or []):
                if isinstance(b, dict) and b.get("name"):
                    brands.append(str(b["name"]).strip())
        cats = Counter(c.get("name") for p in data for c in (p.get("categories") or []) if isinstance(c, dict) and c.get("name"))
        return {
            "source": "woocommerce",
            "titles": [re.sub(r"<[^>]+>", "", str(p.get("name") or "")).strip() for p in data if p.get("name")][:60],
            "vendorCount": len({b.lower() for b in brands}) if brands else None,
            "vendorsTop": [b for b, _ in Counter(brands).most_common(12)],
            "productTypes": [c for c, _ in cats.most_common(30)],
        }
    titles: List[str] = []
    if collection_soup is not None and collection_url:
        seen = set()
        for a in collection_soup.find_all("a", href=True):
            path = urlparse(urljoin(collection_url, a["href"])).path.lower()
            txt = re.sub(r"\s+", " ", a.get_text(" ", strip=True))
            if any(h in path for h in PRODUCT_HINTS) and 3 <= len(txt) <= 120 and txt.lower() not in seen:
                seen.add(txt.lower())
                titles.append(txt)
    return {"source": "collection_page", "titles": titles[:60], "vendorCount": None, "vendorsTop": [], "productTypes": []}


def _shipping_policy_text(origin: str) -> Tuple[Optional[str], Optional[str]]:
    for p in POLICY_SCOPE_PATHS:
        st, final, text = _quick_get(origin + p)
        if st == 200 and text:
            body = _visible_text(BeautifulSoup(text, "lxml"))
            if len(body) > 300:
                return body[:60000], final
    return None, None


def _shopify_meta(origin: str) -> Optional[Dict[str, Any]]:
    data = _raw_json_get(origin + "/meta.json")
    return data if isinstance(data, dict) else None


def _build_profile(result: Dict[str, Any], *, home_html: str, home_url: str, origin: str,
                   product_html: Optional[str], collection_html: Optional[str],
                   collection_url: Optional[str]) -> None:
    """Journey (Step 1), market (Step 3) and classification signals (Step 2/4).
    Best-effort: any failure leaves that part empty, never fails validation."""
    home_soup = BeautifulSoup(home_html, "lxml")
    prod_soup = BeautifulSoup(product_html, "lxml") if product_html else None
    coll_soup = BeautifulSoup(collection_html, "lxml") if collection_html else None

    jobs = {
        "search": lambda: _probe_search(home_soup, home_url, origin),
        "cart": lambda: _probe_cart(home_soup, home_url, origin),
        "checkout": lambda: _probe_checkout(origin),
        "catalog": lambda: _catalog_sample(origin, coll_soup, collection_url),
        "policy": lambda: _shipping_policy_text(origin),
        "meta": lambda: _shopify_meta(origin),
    }
    out: Dict[str, Any] = {}
    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        futs = {pool.submit(fn): name for name, fn in jobs.items()}
        for fut in as_completed(futs):
            try:
                out[futs[fut]] = fut.result()
            except Exception as exc:  # fail-open per probe
                out[futs[fut]] = None
                print(f"[validate_site] {futs[fut]} probe failed: {exc}")

    # ── Step 1: customer journey beyond the three critical pages ──
    journey = {k: (out.get(k) or {"ok": False, "status": "error", "url": None}) for k in ("search", "cart", "checkout")}
    result["stages"].update(journey)
    problems = [k for k, v in journey.items() if v.get("status") in ("blocked", "error")]
    result["accessStatus"] = "incomplete" if problems else "complete"
    result["accessIssues"] = problems

    # ── Step 3: market / service area ──
    policy_text, policy_url = out.get("policy") or (None, None)
    scope, evidence = shipping_scope_from_text(policy_text or "")
    if not scope:
        scope, evidence = shipping_scope_from_text(_visible_text(BeautifulSoup(home_html, "lxml")))
    jl_home, jl_ships = jsonld_market(home_soup, prod_soup)
    meta = out.get("meta") or {}
    if not result.get("currency") and policy_text:
        m = re.search(r"prices?\s+(?:are\s+)?(?:\w+\s+)?in\s+([A-Za-z]{3})\b", policy_text, re.I)
        if m and m.group(1).upper() in CURRENCY_CODES:
            result["currency"] = m.group(1).upper()
    hreflang = hreflang_countries(home_soup)
    result["market"] = resolve_market(
        url=home_url,
        currency=result.get("currency") or meta.get("currency"),
        meta_country=meta.get("country_code") or meta.get("country"),
        jsonld_home=jl_home,
        jsonld_ships=jl_ships,
        localization=localization_countries(home_soup),
        hreflang=hreflang,
        policy_scope=scope,
        policy_evidence=evidence,
        policy_countries=countries_mentioned(policy_text or "") if scope == "selected" else None,
        page_text=_visible_text_keep_scripts(home_soup),
    )
    if policy_url:
        result["market"]["policyUrl"] = policy_url

    # ── Step 2/4 inputs (final classification happens in /scale-check, once
    #    the taxonomy is known) ──
    link_blob = " ".join(a.get("href", "") for a in home_soup.find_all("a", href=True))
    result["signals"] = {
        "regionCount": len(hreflang),
        "marketplaceMarker": strong_marketplace_marker(_visible_text_keep_scripts(home_soup), link_blob),
    }
    result["catalogSample"] = out.get("catalog") or {"source": None, "titles": [], "vendorCount": None}


def validate_site(url: str) -> Dict[str, Any]:
    """Onboarding readiness + store profile. Returns:
    {
      ok, currency, fetchedUrl, accessStatus ("complete"|"incomplete"|"unable"),
      language: { htmlLang, isEnglish, englishAlternate, ... },
      stages: { homepage, collection, product,          ← critical (must pass)
                search, cart, checkout },               ← journey (reported)
      market: store_market_v1, signals: {...}, catalogSample: {...}
    }
    `ok` is True only when the three critical pages are readable AND the store is
    in English. Journey failures make the store "incomplete", not unreadable.
    """
    result: Dict[str, Any] = {"ok": False, "currency": None, "stages": {}, "accessStatus": "unable"}

    # ── Stage 1: homepage ────────────────────────────────────────────────────
    home_html, home_url = _fetch(url)
    if not home_html:
        result["stages"]["homepage"] = {"ok": False, "reason": "Could not load the homepage — the site may be down or blocking automated access."}
        return result
    soup = BeautifulSoup(home_html, "lxml")
    language = detect_language(soup, _visible_text_keep_scripts(soup))
    text = _visible_text(soup)
    links = _internal_links(soup, home_url)
    home_ok = len(text) >= MIN_HOME_TEXT and len(links) >= MIN_HOME_LINKS
    result["fetchedUrl"] = home_url
    result["language"] = language
    result["stages"]["homepage"] = {
        "ok": home_ok,
        "textLength": len(text),
        "linkCount": len(links),
        "reason": None if home_ok else "The homepage loaded but has almost no readable content (likely a JS shell we couldn't render).",
    }
    if not home_ok:
        return result
    # English-only product: stop before the slow collection/product renders.
    if not language.get("isEnglish"):
        result["unsupportedLanguage"] = True
        return result

    # ── Stage 2: a collection / category listing ─────────────────────────────
    coll_candidates = [l for l in links if any(h in urlparse(l).path.lower() for h in COLLECTION_HINTS)]
    coll_candidates = [l for l in coll_candidates if l.rstrip("/") != home_url.rstrip("/")]
    origin = f"{urlparse(home_url).scheme}://{urlparse(home_url).netloc}"
    for p in COLLECTION_FALLBACK_PATHS:
        cand = origin + p
        if cand not in coll_candidates:
            coll_candidates.append(cand)

    collection = {"ok": False, "reason": "No category/collection page with products could be reached."}
    product_links: List[str] = []
    collection_html = None
    for cand in coll_candidates[:MAX_CANDIDATES]:
        c_html, c_url = _fetch(cand)
        if not c_html:
            continue
        c_soup = BeautifulSoup(c_html, "lxml")
        count, plinks = _count_products(c_soup, c_url)
        if count >= MIN_COLLECTION_PRODUCTS:
            collection = {"ok": True, "url": c_url, "productCount": count}
            product_links = plinks
            collection_html = c_html
            break
    result["stages"]["collection"] = collection
    if not collection["ok"]:
        return result

    # ── Stage 3: a single product page (+ currency) ──────────────────────────
    prod_candidates = product_links or [l for l in links if any(h in urlparse(l).path.lower() for h in PRODUCT_HINTS)]
    product = {"ok": False, "reason": "No individual product page could be reached or confirmed."}
    currency = None
    product_html = None
    for cand in prod_candidates[:MAX_CANDIDATES]:
        p_html, p_url = _fetch(cand)
        if not p_html:
            continue
        p_soup = BeautifulSoup(p_html, "lxml")
        ok, cur = _is_product_page(p_soup, p_url)
        if ok:
            currency = cur
            product_html = p_html
            product = {"ok": True, "url": p_url, "currency": cur}
            break
    if product["ok"] and not currency:
        # Ambiguous symbol ("Rs.") → the store's configured currency.
        currency = _shopify_currency(origin) or _policy_currency(origin)
        product["currency"] = currency
    result["stages"]["product"] = product
    if not product["ok"]:
        return result

    result["ok"] = True
    result["currency"] = currency
    try:
        _build_profile(result, home_html=home_html, home_url=home_url, origin=origin,
                       product_html=product_html, collection_html=collection_html,
                       collection_url=collection.get("url"))
    except Exception as exc:  # never fail a readable store over profiling
        print(f"[validate_site] profile build failed for {url}: {exc}")
        result.setdefault("accessStatus", "complete")
    if result.get("accessStatus") == "unable":
        result["accessStatus"] = "complete"
    return result


def quick_catalog(url: str) -> Dict[str, Any]:
    """Lean category read for competitor suggestion: render the homepage ONCE and
    pull the category/collection names straight from the nav links (the same links
    the validator uses), plus the store currency. This works on Cloudflare-protected
    or JS-rendered Shopify stores where the plain /collections.json fetch is blocked
    and the full catalog render times out. Returns { categories:[...], currency }."""
    home_html, home_url = _fetch(url)
    if not home_html:
        return {"categories": [], "currency": None}
    soup = BeautifulSoup(home_html, "lxml")
    origin = f"{urlparse(home_url).scheme}://{urlparse(home_url).netloc}"
    cats: List[str] = []
    collections: List[Dict[str, str]] = []
    seen = set()
    for link in _internal_links(soup, home_url):
        path = urlparse(link).path.lower()
        if any(h in path for h in COLLECTION_HINTS):
            slug = path.rstrip("/").rsplit("/", 1)[-1]
            if slug and slug not in ("collections", "collection", "shop", "products", "store", "catalog", "all", "category", "categories") and slug not in seen:
                seen.add(slug)
                name = re.sub(r"[-_]+", " ", slug).strip()
                if 2 <= len(name) <= 40:
                    cats.append(name)
                    collections.append({"title": name.title(), "url": link})
    currency = _extract_currency(soup) or _shopify_currency(origin) or _policy_currency(origin)
    return {"categories": cats[:30], "collections": collections[:60], "currency": currency}
