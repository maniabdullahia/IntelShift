"""Store & locale detection (store_locale_v1).

Detect whether a site exposes MULTIPLE regional storefronts / currencies, so the
app can ask the user WHICH store to track — instead of the crawler silently
landing on whatever region an IP or a geo-redirect happens to pick.

Pure function over (html, url). No network calls. Signals used, in order:

  1. <link rel="alternate" hreflang="xx-YY" href="..."> — the standard, richest
     signal (Gymshark, Nike, most enterprise stores expose full alternate sets).
  2. Shopify localization / country <select> forms (name="country_code").
  3. The CURRENT page's own locale + active currency (Shopify.currency,
     og:locale, og:price:currency, itemprop=priceCurrency, <html lang>, and a
     /en-pk/ style locale segment in the URL).

A regional variant's currency is INFERRED from its country when we only have the
entry page's HTML (we don't fetch every variant). That inference is a hint the
user confirms in the picker — it is never a silent decision.

Returned shape (store_locale_v1):
{
  "schemaVersion": "store_locale_v1",
  "multiRegion": bool,          # true when >1 distinct country/store found
  "multiCurrency": bool,        # true when >1 distinct currency found
  "current": { "url", "hreflang", "language", "country", "countryName", "currency" },
  "stores": [ { "hreflang", "language", "country", "countryName",
                "url", "currency", "isCurrent" }, ... ],
  "currencies": [ "AUD", "USD", ... ],
  "signals": [ "hreflang", "shopify_currency", ... ]   # what we detected from
}
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

try:
    from bs4 import BeautifulSoup
except Exception:  # pragma: no cover - bs4 is a hard dep of the analyzer
    BeautifulSoup = None


SCHEMA_VERSION = "store_locale_v1"

# ISO country code → likely default currency. Used to hint a regional variant's
# currency when we can't fetch that variant's own page. Covers the common
# ecommerce markets; unknown countries simply return no currency hint.
COUNTRY_CURRENCY = {
    "US": "USD", "GB": "GBP", "UK": "GBP", "EU": "EUR", "IE": "EUR",
    "DE": "EUR", "FR": "EUR", "ES": "EUR", "IT": "EUR", "NL": "EUR",
    "BE": "EUR", "AT": "EUR", "PT": "EUR", "FI": "EUR", "GR": "EUR",
    "CA": "CAD", "AU": "AUD", "NZ": "NZD", "JP": "JPY", "CN": "CNY",
    "HK": "HKD", "SG": "SGD", "IN": "INR", "PK": "PKR", "BD": "BDT",
    "LK": "LKR", "AE": "AED", "SA": "SAR", "QA": "QAR", "KW": "KWD",
    "BH": "BHD", "OM": "OMR", "TR": "TRY", "RU": "RUB", "UA": "UAH",
    "PL": "PLN", "CZ": "CZK", "HU": "HUF", "RO": "RON", "SE": "SEK",
    "NO": "NOK", "DK": "DKK", "CH": "CHF", "ZA": "ZAR", "NG": "NGN",
    "EG": "EGP", "KE": "KES", "MA": "MAD", "BR": "BRL", "MX": "MXN",
    "AR": "ARS", "CL": "CLP", "CO": "COP", "PE": "PEN", "KR": "KRW",
    "TH": "THB", "MY": "MYR", "ID": "IDR", "PH": "PHP", "VN": "VND",
    "IL": "ILS", "TW": "TWD",
}

# ISO country code → display name (only what we need for the picker labels).
COUNTRY_NAMES = {
    "US": "United States", "GB": "United Kingdom", "UK": "United Kingdom",
    "IE": "Ireland", "DE": "Germany", "FR": "France", "ES": "Spain",
    "IT": "Italy", "NL": "Netherlands", "BE": "Belgium", "AT": "Austria",
    "PT": "Portugal", "FI": "Finland", "GR": "Greece", "CA": "Canada",
    "AU": "Australia", "NZ": "New Zealand", "JP": "Japan", "CN": "China",
    "HK": "Hong Kong", "SG": "Singapore", "IN": "India", "PK": "Pakistan",
    "BD": "Bangladesh", "LK": "Sri Lanka", "AE": "United Arab Emirates",
    "SA": "Saudi Arabia", "QA": "Qatar", "KW": "Kuwait", "BH": "Bahrain",
    "OM": "Oman", "TR": "Turkey", "RU": "Russia", "UA": "Ukraine",
    "PL": "Poland", "CZ": "Czechia", "HU": "Hungary", "RO": "Romania",
    "SE": "Sweden", "NO": "Norway", "DK": "Denmark", "CH": "Switzerland",
    "ZA": "South Africa", "NG": "Nigeria", "EG": "Egypt", "KE": "Kenya",
    "MA": "Morocco", "BR": "Brazil", "MX": "Mexico", "AR": "Argentina",
    "CL": "Chile", "CO": "Colombia", "PE": "Peru", "KR": "South Korea",
    "TH": "Thailand", "MY": "Malaysia", "ID": "Indonesia", "PH": "Philippines",
    "VN": "Vietnam", "IL": "Israel", "TW": "Taiwan", "EU": "European Union",
}


_VALID_CURRENCIES = set(COUNTRY_CURRENCY.values())
_CUR_CODE_RE = re.compile(r"\b([A-Z]{3})\b")

# Markup that indicates an on-page currency switcher (WooCommerce WCML/WOOCS/
# CURCY plugins, Shopify currency selectors, generic widgets). Used both to read
# the offered currencies and to decide whether a JS render is worth trying.
_SWITCHER_HINT_RE = re.compile(
    r"(currency[-_ ]?switch|wcml[-_]currency|curency-chose|woocs|curcy|"
    r"wmc[-_]currency|currency[-_]selector|currency[-_]picker|wcml-cs)",
    re.I,
)


def has_currency_switcher_markup(html) -> bool:
    """True if the raw HTML hints at a currency switcher — even an empty one whose
    options get filled by JavaScript. Lets the caller decide to render the page."""
    return bool(html) and bool(_SWITCHER_HINT_RE.search(html))


def _currency_switcher_codes(soup) -> set:
    """ISO currency codes offered by an on-page currency switcher. These are
    same-URL currency options — the real signal that a store lets you change
    currency without leaving the page (unlike separate regional domains)."""
    if soup is None:
        return set()

    containers = []
    for el in soup.find_all(True, class_=_SWITCHER_HINT_RE):
        containers.append(el)
    for el in soup.find_all(True, id=_SWITCHER_HINT_RE):
        containers.append(el)
    # Any <select> whose name/id/class mentions currency.
    for sel in soup.find_all("select"):
        blob = " ".join(filter(None, [
            sel.get("name", ""), sel.get("id", ""), " ".join(sel.get("class") or []),
        ]))
        if re.search(r"currenc", blob, re.I):
            containers.append(sel)

    codes = set()

    def _take(value):
        v = (value or "").strip().upper()
        if re.fullmatch(r"[A-Z]{3}", v) and v in _VALID_CURRENCIES:
            codes.add(v)

    for c in containers:
        for opt in c.find_all("option"):
            _take(opt.get("value"))
            _take(opt.get("data-currency"))
            _take(opt.get_text())
        for a in c.find_all("a"):
            rel = a.get("rel")
            _take(" ".join(rel) if isinstance(rel, list) else rel)
            _take(a.get("data-currency"))
            _take(a.get_text())
        for node in c.find_all(attrs={"data-currency": True}):
            _take(node.get("data-currency"))
    return codes


def _split_hreflang(tag_value: str):
    """'en-AU' → ('en', 'AU'); 'fr' → ('fr', None); 'x-default' → (None, None)."""
    v = (tag_value or "").strip()
    if not v or v.lower() == "x-default":
        return None, None
    parts = re.split(r"[-_]", v)
    lang = parts[0].lower() if parts and parts[0] else None
    country = parts[1].upper() if len(parts) > 1 and parts[1] else None
    return lang, country


def _country_from_url(url: str):
    """Best-effort ISO country from a URL host/path.

    Handles common patterns: 'au.gymshark.com' subdomain, '/en-pk/' or '/pk/'
    path segments, and a country-code TLD like '.com.pk' / '.pk'.
    """
    try:
        p = urlparse(url if re.match(r"^https?://", url or "") else f"https://{url}")
    except Exception:
        return None
    host = (p.netloc or "").lower()
    path = (p.path or "").lower()

    # /en-pk/ or /pk/ locale segment
    m = re.search(r"/([a-z]{2})-([a-z]{2})(?:/|$)", path)
    if m:
        return m.group(2).upper()
    m = re.search(r"/([a-z]{2})(?:/|$)", path)
    if m and m.group(1).upper() in COUNTRY_NAMES:
        return m.group(1).upper()

    # country-code subdomain (au.example.com) — first label, 2 letters
    labels = host.split(".")
    if len(labels) >= 3 and len(labels[0]) == 2 and labels[0].upper() in COUNTRY_NAMES:
        return labels[0].upper()

    # ccTLD: example.com.pk / example.pk
    if labels:
        tld = labels[-1].upper()
        if tld in COUNTRY_NAMES:
            return tld
    return None


def _active_currency(html: str, soup):
    """Detect the CURRENT page's active currency. Returns an ISO code or None."""
    h = html or ""
    # Shopify.currency = { ... "active":"PKR" ... } — the ACTIVE (presentment)
    # currency the shopper actually sees. Tolerate a window. prefix, either quote
    # style, and any key order inside the object.
    m = re.search(
        r'(?:window\.)?Shopify\.currency\s*=\s*\{[^}]*?["\']active["\']\s*:\s*["\']([A-Za-z]{3})["\']',
        h,
    )
    if m:
        return m.group(1).upper()
    # NOTE: the generic `"currency":"XXX"` blob (the shop's BASE currency) is
    # handled separately as a LAST resort in detect_stores() — see _base_currency().
    # It's not returned here because for a Shopify Markets store the base differs
    # from the PRESENTMENT currency the customer sees (a .pk store renders PKR while
    # its base may be USD), so the ccTLD signal must beat it. Precedence lives in
    # detect_stores(): active → ccTLD → base.
    if soup is not None:
        for attrs in (
            {"property": "og:price:currency"},
            {"itemprop": "priceCurrency"},
            {"name": "currency"},
        ):
            tag = soup.find("meta", attrs=attrs)
            if tag and tag.get("content"):
                val = tag["content"].strip().upper()
                if re.fullmatch(r"[A-Z]{3}", val):
                    return val
        # Currency switchers mark the active option (WCML: .wcml-cs-active-currency
        # / .current-lang-currency). Read it as the page's active currency.
        active_el = soup.find(
            class_=re.compile(r"(wcml-cs-active-currency|current-lang-currency)", re.I)
        )
        if active_el:
            m = _CUR_CODE_RE.search((active_el.get_text() or "").strip().upper())
            if m and m.group(1) in _VALID_CURRENCIES:
                return m.group(1)
    return None


def _base_currency(html: str):
    """LAST-resort currency: the shop's BASE currency from Shopify's analytics /
    config blob (`"currency":"XXX"`). This is the merchant's base currency, which
    for a Shopify Markets store differs from the presentment currency — so it's
    used ONLY when there's no active-currency signal and no ccTLD hint (typically a
    gTLD single-currency store, where base == presentment). Returns ISO or None."""
    m = re.search(r'"currency"\s*:\s*"([A-Z]{3})"', html or "")
    return m.group(1) if m else None


# A currency ISO code sitting next to a number in visible text — "6.00 AED",
# "AED 6.00" — is an unambiguous PRESENTMENT-currency signal on ANY platform.
_PRICE_ISO_RE = re.compile(r'(?:\d[\d.,]{0,15}\s*([A-Z]{3})\b|\b([A-Z]{3})\s*\d[\d.,]{0,15})')
# Currency SYMBOLS that map to exactly ONE currency (so no ambiguity). We omit
# "$" (USD/CAD/AUD/…) and "Rs." (PKR/INR/LKR) on purpose — those are resolved by
# the ccTLD / base tiers instead.
_SYMBOL_CURRENCY = [
    ("€", "EUR"), ("£", "GBP"), ("₹", "INR"), ("د.إ", "AED"), ("﷼", "SAR"),
    ("₦", "NGN"), ("₩", "KRW"), ("₪", "ILS"), ("฿", "THB"), ("₺", "TRY"),
]


def _visible_currency(html: str, soup):
    """Detect the PRESENTMENT currency from VISIBLE prices — an unambiguous ISO
    code next to a number ("6.00 AED", "AED 6.00") or a single-currency symbol.
    Platform-agnostic: works for WooCommerce / Wix / custom stores that carry no
    Shopify currency object. Deliberately ignores ambiguous symbols ($, Rs.).
    Returns the most frequent valid ISO code, or None."""
    # Read visible text only, so we match on-page prices — not currency codes
    # buried in analytics/config scripts (which carry the base currency).
    text = html or ""
    if soup is not None:
        try:
            text = soup.get_text(" ", strip=True)
        except Exception:
            text = html or ""
    text = text[:200000]
    counts = {}
    for m in _PRICE_ISO_RE.finditer(text):
        code = (m.group(1) or m.group(2) or "").upper()
        if code in _VALID_CURRENCIES:
            counts[code] = counts.get(code, 0) + 1
    if counts:
        return max(counts, key=counts.get)
    for sym, code in _SYMBOL_CURRENCY:
        if sym in text:
            return code
    return None


def _current_locale(soup, url: str):
    """(language, country) for the page we actually fetched."""
    lang = None
    country = None
    if soup is not None:
        html_tag = soup.find("html")
        if html_tag and html_tag.get("lang"):
            lang, country = _split_hreflang(html_tag["lang"])
        if not country:
            og = soup.find("meta", attrs={"property": "og:locale"})
            if og and og.get("content"):
                _l, _c = _split_hreflang(og["content"])
                lang = lang or _l
                country = country or _c
    country = country or _country_from_url(url)
    return lang, country


def _mk_store(hreflang, lang, country, store_url, currency, is_current, country_name=None, same_url=False):
    return {
        "hreflang": hreflang or "",
        "language": lang or "",
        "country": country or "",
        "countryName": country_name or COUNTRY_NAMES.get(country or "", country or ""),
        "url": store_url or "",
        "currency": currency or "",
        "isCurrent": bool(is_current),
        # True when this variant lives on the SAME URL (a currency/market switch),
        # False for a distinct regional domain/path. Only same-URL variants form
        # a real "which currency?" choice for the entered store.
        "sameUrl": bool(same_url),
    }


def detect_stores(html: str, url: str) -> dict:
    """Detect available regional stores / currencies for a site. Pure function."""
    signals = []
    soup = BeautifulSoup(html or "", "lxml") if BeautifulSoup else None

    cur_currency = _active_currency(html, soup)
    if cur_currency:
        signals.append("active_currency")
    # Visible-price currency (presentment) — the AED next to every price on a
    # WooCommerce/custom store. Ranks just under the explicit active signal and
    # ABOVE ccTLD/base, so a .com store priced in AED resolves to AED, not a stray
    # base-currency USD.
    if not cur_currency:
        vis = _visible_currency(html, soup)
        if vis:
            cur_currency = vis
            signals.append("visible_currency")
    cur_lang, cur_country = _current_locale(soup, url)
    cur_host = (urlparse(url if re.match(r"^https?://", url or "") else f"https://{url}").netloc or "").lower()

    # ccTLD / locale fallback for the CURRENT store: a country-coded store with no
    # explicit active-currency signal takes its OWN country's currency — a .pk store
    # is PKR, not a stray base-currency USD. This sits ABOVE the base-currency blob
    # so a Markets store on a ccTLD resolves to its market, not its base.
    if not cur_currency and cur_country:
        _cc = COUNTRY_CURRENCY.get(cur_country)
        if _cc:
            cur_currency = _cc
            signals.append("cctld_currency")

    # Last resort: the shop's BASE currency (analytics/config blob). For a gTLD
    # store with no active signal and no ccTLD (e.g. a headless .com like Gymshark),
    # this is the only currency signal — and for a single-currency store base ==
    # presentment, so it's correct. It NEVER overrides active or ccTLD above.
    if not cur_currency:
        _base = _base_currency(html)
        if _base:
            cur_currency = _base
            signals.append("base_currency")

    stores = []
    seen_countries = set()

    def _same_url_variant(code):
        # Shopify Markets keeps the SAME URL and switches country/currency via
        # ?country=. Used for countries exposed by a selector/links rather than
        # a dedicated regional site.
        if code == cur_country:
            return url
        return f"{url}{'&' if '?' in (url or '') else '?'}country={code}"

    def _add_store(hreflang, lang, country, store_url, currency, is_current, country_name=None, same_url=False):
        if not country or country in seen_countries:
            return False
        seen_countries.add(country)
        stores.append(_mk_store(hreflang, lang, country, store_url, currency, is_current, country_name, same_url))
        return True

    # ── 1. hreflang alternates — distinct regional sites (real URLs) ─────────
    if soup is not None:
        added = 0
        for link in soup.find_all("link", rel=lambda v: v and "alternate" in (v if isinstance(v, str) else " ".join(v or [])).lower()):
            href = link.get("href")
            hl = link.get("hreflang")
            if not href or not hl:
                continue
            lang, country = _split_hreflang(hl)
            if not country:
                continue  # language-only / x-default alternates aren't a store
            store_host = (urlparse(href).netloc or "").lower()
            is_current = store_host == cur_host or (country == cur_country)
            currency = cur_currency if (is_current and cur_currency) else COUNTRY_CURRENCY.get(country)
            if _add_store(hl, lang, country, href, currency, is_current):
                added += 1
        if added:
            signals.append("hreflang")

    # ── 2. Country / localization <select> — same-store country variants ────
    #    (Shopify Markets, currency switchers). MERGED with hreflang (not an
    #    either/or), so a site that lists e.g. Pakistan only in its country
    #    selector still surfaces it alongside its hreflang regions.
    if soup is not None:
        select = (soup.find("select", attrs={"name": "country_code"})
                  or soup.find("select", attrs={"name": re.compile(r"country", re.I)}))
        added = 0
        if select is not None:
            for opt in select.find_all("option"):
                code = (opt.get("value") or "").strip().upper()
                if not re.fullmatch(r"[A-Z]{2}", code) or code in seen_countries:
                    continue
                text = re.sub(r"\s+", " ", opt.get_text(strip=True) or "")
                # Currency: a data-* attribute, else a 3-letter token in the
                # label (e.g. "Pakistan (PKR Rs.)"), else the country default.
                opt_currency = (opt.get("data-currency") or opt.get("data-currency-code") or "").strip().upper()
                if not re.fullmatch(r"[A-Z]{3}", opt_currency):
                    m = re.search(r"\b([A-Z]{3})\b", text)
                    opt_currency = m.group(1) if m else ""
                currency = opt_currency or COUNTRY_CURRENCY.get(code) or ""
                label = COUNTRY_NAMES.get(code) or re.sub(r"\s*\(.*?\)\s*", " ", text).strip() or code
                is_current = code == cur_country
                if _add_store(f"{(cur_lang or 'en')}-{code}", cur_lang, code,
                              _same_url_variant(code), currency, is_current, label, same_url=True):
                    added += 1
        if added:
            signals.append("country_select")

    # ── 3. Country-switcher links (?country=XX) — extra safety net ───────────
    if soup is not None:
        added = 0
        for a in soup.find_all("a", href=True):
            m = re.search(r"[?&]country=([A-Za-z]{2})\b", a["href"])
            if not m:
                continue
            code = m.group(1).upper()
            if code in seen_countries or code not in COUNTRY_NAMES:
                continue
            is_current = code == cur_country
            currency = (cur_currency if is_current and cur_currency else COUNTRY_CURRENCY.get(code)) or ""
            if _add_store(f"{(cur_lang or 'en')}-{code}", cur_lang, code,
                          _same_url_variant(code), currency, is_current, same_url=True):
                added += 1
        if added:
            signals.append("country_links")

    # ── 3. Single-store fallback — record what we actually fetched ──────────
    if not stores and (cur_country or cur_currency):
        stores.append(_mk_store(
            f"{cur_lang or ''}{'-' + cur_country if cur_country else ''}".strip("-"),
            cur_lang, cur_country, url, cur_currency, True,
        ))

    # Ensure exactly ONE store is flagged current across the merged sources.
    seen_current = False
    for s in stores:
        if s["isCurrent"] and not seen_current:
            seen_current = True
        elif s["isCurrent"]:
            s["isCurrent"] = False
    if stores and not seen_current:
        stores[0]["isCurrent"] = True

    # Current store first, then alphabetical by name — makes a long country list
    # (Shopify Markets can expose 100+) easy to scan for the one you want.
    stores.sort(key=lambda s: (not s["isCurrent"], (s["countryName"] or s["country"] or "").lower()))

    distinct_countries = {s["country"] for s in stores if s["country"]}

    # Currencies OFFERED ON THE ENTERED URL (a same-URL market/currency switch),
    # plus the page's own active currency. We deliberately EXCLUDE the currencies
    # of separate regional domains (hreflang alternates) — those aren't a currency
    # choice for this store, they're different stores. A currency picker is only
    # warranted when this single URL genuinely serves more than one currency.
    switcher_codes = _currency_switcher_codes(soup)
    if switcher_codes:
        signals.append("currency_switcher")
    currencies = sorted(
        {s["currency"] for s in stores if s.get("sameUrl") and s["currency"]} | switcher_codes
    )
    if cur_currency and cur_currency not in currencies:
        currencies = sorted(set(currencies) | {cur_currency})

    current = next((s for s in stores if s["isCurrent"]), stores[0] if stores else None)
    current_currency = (
        cur_currency
        or (current["currency"] if current else "")
        or (currencies[0] if currencies else "")
    )

    return {
        "schemaVersion": SCHEMA_VERSION,
        "multiRegion": len(distinct_countries) > 1,
        # Only true when the ENTERED URL itself offers several currencies.
        "multiCurrency": len(currencies) > 1,
        "current": (
            {
                "url": current["url"],
                "hreflang": current["hreflang"],
                "language": current["language"],
                "country": current["country"],
                "countryName": current["countryName"],
                "currency": current["currency"],
            }
            if current else None
        ),
        "currentCurrency": current_currency,
        "stores": stores,
        "currencies": currencies,
        "signals": signals,
    }
