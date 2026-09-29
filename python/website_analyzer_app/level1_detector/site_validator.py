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

from .fetcher import fetch_with_requests, fetch_with_cloudscraper, fetch_with_playwright


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
        return (urlparse(url).hostname or "").lower().lstrip("www.")
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


def _is_product_page(soup: BeautifulSoup) -> Tuple[bool, Optional[str]]:
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
    if has_price and (add_to_cart or currency):
        return True, currency
    if has_price:  # price alone still indicates a product page
        return True, currency
    return False, currency


def _raw_json_get(url: str) -> Any:
    """Raw JSON GET that bypasses safe_response (which nulls body-less API
    responses). Uses cloudscraper to clear Cloudflare, falling back to requests."""
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


def validate_site(url: str) -> Dict[str, Any]:
    """Run the three-stage readiness check. Returns:
    {
      ok, currency, fetchedUrl,
      stages: { homepage:{ok,...}, collection:{ok,url,productCount}, product:{ok,url,currency} }
    }
    """
    result: Dict[str, Any] = {"ok": False, "currency": None, "stages": {}}

    # ── Stage 1: homepage ────────────────────────────────────────────────────
    home_html, home_url = _fetch(url)
    if not home_html:
        result["stages"]["homepage"] = {"ok": False, "reason": "Could not load the homepage — the site may be down or blocking automated access."}
        return result
    soup = BeautifulSoup(home_html, "lxml")
    text = _visible_text(soup)
    links = _internal_links(soup, home_url)
    home_ok = len(text) >= MIN_HOME_TEXT and len(links) >= MIN_HOME_LINKS
    result["fetchedUrl"] = home_url
    result["stages"]["homepage"] = {
        "ok": home_ok,
        "textLength": len(text),
        "linkCount": len(links),
        "reason": None if home_ok else "The homepage loaded but has almost no readable content (likely a JS shell we couldn't render).",
    }
    if not home_ok:
        return result

    # ── Stage 2: a collection / category listing ─────────────────────────────
    coll_candidates = [l for l in links if any(h in urlparse(l).path.lower() for h in COLLECTION_HINTS)]
    # De-prioritise the exact homepage and obvious non-listing utility links.
    coll_candidates = [l for l in coll_candidates if l.rstrip("/") != home_url.rstrip("/")]
    # Add common fallback paths (Shopify /collections/all, generic /shop) if thin.
    origin = f"{urlparse(home_url).scheme}://{urlparse(home_url).netloc}"
    for p in COLLECTION_FALLBACK_PATHS:
        cand = origin + p
        if cand not in coll_candidates:
            coll_candidates.append(cand)

    collection = {"ok": False, "reason": "No category/collection page with products could be reached."}
    product_links: List[str] = []
    for cand in coll_candidates[:MAX_CANDIDATES]:
        c_html, c_url = _fetch(cand)
        if not c_html:
            continue
        c_soup = BeautifulSoup(c_html, "lxml")
        count, plinks = _count_products(c_soup, c_url)
        if count >= MIN_COLLECTION_PRODUCTS:
            collection = {"ok": True, "url": c_url, "productCount": count}
            product_links = plinks
            break
    result["stages"]["collection"] = collection
    if not collection["ok"]:
        return result

    # ── Stage 3: a single product page (+ currency) ──────────────────────────
    # Prefer products found on the collection; fall back to product-like homepage links.
    prod_candidates = product_links or [l for l in links if any(h in urlparse(l).path.lower() for h in PRODUCT_HINTS)]
    product = {"ok": False, "reason": "No individual product page could be reached or confirmed."}
    currency = None
    prod_soup = None
    for cand in prod_candidates[:MAX_CANDIDATES]:
        p_html, p_url = _fetch(cand)
        if not p_html:
            continue
        p_soup = BeautifulSoup(p_html, "lxml")
        ok, cur = _is_product_page(p_soup)
        if ok:
            currency = cur
            prod_soup = p_soup
            product = {"ok": True, "url": p_url, "currency": cur}
            break
    # If the product page priced in an ambiguous symbol (e.g. "Rs.") we may have a
    # confirmed product but no currency — fall back to Shopify's configured currency.
    cart_currency = None
    if product["ok"] and not currency:
        cart_currency = _shopify_currency(origin)
        currency = cart_currency or _policy_currency(origin)
        product["currency"] = currency
    # DEBUG — surface WHY currency didn't resolve: the price text as rendered and
    # what the Shopify endpoints returned. Remove once currency detection is solid.
    if prod_soup is not None:
        _ptext = _visible_text(prod_soup)
        _m = PRICE_NEAR_RE.search(_ptext)
        result["currencyDebug"] = {
            "priceSnippet": (_ptext[max(0, _m.start() - 40): _m.end() + 40] if _m else None),
            "domCurrency": _extract_currency(prod_soup),
            "cartJsonCurrency": cart_currency if cart_currency is not None else _shopify_currency(origin),
        }
    result["stages"]["product"] = product
    if not product["ok"]:
        return result

    result["ok"] = True
    result["currency"] = currency
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
