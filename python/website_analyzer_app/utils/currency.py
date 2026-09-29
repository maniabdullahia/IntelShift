"""
utils/currency.py — single source of truth for currency detection and price normalisation.

All platform analyzers (Shopify, WordPress, Wix, Unknown) should delegate to these
helpers rather than maintaining their own copies of the TLD map and normalize logic.

Public API
----------
currency_from_url(url) -> str | None
    Infer the most likely ISO-4217 currency code from the URL's TLD / path locale.
    Returns None when no confident signal is found (caller should keep their own
    extracted currency rather than overriding with a guess).

normalize_price_text(raw, page_url=None) -> dict | None
    Parse a raw price string into {raw, amount, currency}.
    Returns None when `raw` is falsy.
    Returns {raw, amount=None, currency} when the numeric part can't be parsed.
    Zero amounts are treated as "unfetched" and return amount=None.
"""

import re
from urllib.parse import urlparse


# ---------------------------------------------------------------------------
# TLD / path-locale → currency  (single authoritative copy)
# ---------------------------------------------------------------------------

# TLD-based map — ordered longest-first so .com.au matches before .au
_TLD_CURRENCY = [
    (".com.pk",  "PKR"),
    (".com.au",  "AUD"),
    (".com.sg",  "SGD"),
    (".com.hk",  "HKD"),
    (".com.mx",  "MXN"),
    (".com.br",  "BRL"),
    (".co.uk",   "GBP"),
    (".co.in",   "INR"),
    (".co.nz",   "NZD"),
    (".co.za",   "ZAR"),
    (".co.ke",   "KES"),
    (".pk",      "PKR"),
    (".in",      "INR"),
    (".ae",      "AED"),
    (".sa",      "SAR"),
    (".de",      "EUR"),
    (".fr",      "EUR"),
    (".it",      "EUR"),
    (".es",      "EUR"),
    (".nl",      "EUR"),
    (".be",      "EUR"),
    (".at",      "EUR"),
    (".pt",      "EUR"),
    (".ie",      "EUR"),
    (".fi",      "EUR"),
    (".gr",      "EUR"),
    (".jp",      "JPY"),
    (".cn",      "CNY"),
    (".kr",      "KRW"),
    (".sg",      "SGD"),
    (".hk",      "HKD"),
    (".nz",      "NZD"),
    (".ca",      "CAD"),
    (".mx",      "MXN"),
    (".br",      "BRL"),
    (".ng",      "NGN"),
    (".gh",      "GHS"),
    (".eg",      "EGP"),
    (".za",      "ZAR"),
    (".ke",      "KES"),
    (".bd",      "BDT"),
    (".lk",      "LKR"),
    (".np",      "NPR"),
    (".my",      "MYR"),
    (".th",      "THB"),
    (".id",      "IDR"),
    (".ph",      "PHP"),
    (".vn",      "VND"),
    (".tr",      "TRY"),
    (".ru",      "RUB"),
    (".ch",      "CHF"),
    (".se",      "SEK"),
    (".no",      "NOK"),
    (".dk",      "DKK"),
    (".pl",      "PLN"),
]

# Path-locale → currency (matches /en-gb/, /en-au/, /fr-fr/ etc.)
_LOCALE_CURRENCY = {
    "en-pk": "PKR", "en-in": "INR",  "en-gb": "GBP",
    "en-au": "AUD", "en-ca": "CAD",  "en-ae": "AED",
    "en-sa": "SAR", "en-eu": "EUR",  "en-sg": "SGD",
    "en-nz": "NZD", "en-hk": "HKD", "en-mx": "MXN",
    "de-de": "EUR", "fr-fr": "EUR",  "it-it": "EUR",
    "es-es": "EUR", "nl-nl": "EUR",  "ja-jp": "JPY",
    "zh-cn": "CNY", "ko-kr": "KRW",
}

# Symbol / keyword prefix detection (ordered: multi-char first)
_SYMBOL_CURRENCY = [
    ("ca$",  "CAD"),
    ("a$",   "AUD"),
    ("nz$",  "NZD"),
    ("hk$",  "HKD"),
    ("s$",   "SGD"),
    ("£",    "GBP"),
    ("€",    "EUR"),
    ("₹",    "INR"),
    ("₨",    "PKR"),
    ("¥",    "JPY"),
    ("₩",    "KRW"),
    ("﷼",   "SAR"),
    ("د.إ",  "AED"),
    ("฿",    "THB"),
    ("₺",    "TRY"),
]

# Suffix / inline currency codes
_CODE_CURRENCY = [
    "PKR", "INR", "AED", "SAR", "BDT", "LKR", "NPR",
    "MYR", "THB", "IDR", "PHP", "VND", "NGN", "KES",
    "GHS", "EGP", "ZAR", "CAD", "AUD", "NZD", "SGD",
    "HKD", "MXN", "BRL", "JPY", "CNY", "KRW", "GBP",
    "EUR", "CHF", "SEK", "NOK", "DKK", "PLN", "TRY",
    "RUB", "USD",
]


def currency_from_url(url):
    """
    Infer ISO-4217 currency from URL TLD or path locale.

    Returns the currency code (str) if a confident signal is found, else None.
    Deliberately does NOT return "USD" as a fallback — callers should keep their
    own extracted value or handle the None themselves.
    """
    if not url:
        return None

    url_lower = url.lower()

    # 1. Path locale  (/en-gb/, /fr-fr/, …)
    for loc, cur in _LOCALE_CURRENCY.items():
        if f"/{loc}/" in url_lower:
            return cur

    # 2. TLD (longest match first)
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        host = url_lower

    for tld, cur in _TLD_CURRENCY:
        if host.endswith(tld):
            return cur

    # 3. 2-letter country-code subdomain (e.g. pk.lamaretail.com → PKR,
    #    ae.brand.com → AED, sa.brand.com → SAR).
    #    Only fire when the host has ≥3 parts and the leftmost part is exactly
    #    2 chars — avoids false positives on short domain names like "go.com".
    parts = host.split(".")
    if len(parts) >= 3 and len(parts[0]) == 2:
        candidate_tld = f".{parts[0]}"
        for tld, cur in _TLD_CURRENCY:
            if tld == candidate_tld:
                return cur

    return None


def _currency_from_symbols(raw_lower, raw):
    """Detect currency from symbols/codes in a price string. Returns str|None."""
    # Symbol detection (case-insensitive prefix/infix)
    for sym, cur in _SYMBOL_CURRENCY:
        if sym in raw_lower:
            return cur

    # Inline currency code (word boundary)
    for code in _CODE_CURRENCY:
        if re.search(rf'\b{re.escape(code)}\b', raw, re.I):
            return code

    # Rs. / rs shorthand (PKR)
    if re.search(r'\brs\.?\s', raw_lower) or raw_lower.startswith("rs"):
        return "PKR"

    return None


def currency_from_text(text, page_url=None):
    """
    Infer ISO-4217 currency from a block of free-form text (e.g. markdown).

    Scans the entire text for currency symbols and ISO codes, then falls back
    to TLD-based inference from page_url when only `$` is found.

    Returns the currency code (str) if a signal is found, else None.
    Callers should apply their own default (e.g. "USD") when None is returned.
    """
    if not text:
        return currency_from_url(page_url)

    text_str = str(text)
    text_lower = text_str.lower()

    # Symbol scan (ordered: multi-char symbols first)
    for sym, cur in _SYMBOL_CURRENCY:
        if sym in text_lower:
            return cur

    # Inline ISO code scan (word-boundary match)
    for code in _CODE_CURRENCY:
        if code == "USD":
            continue  # defer USD — disambiguate via TLD below
        if re.search(rf'\b{re.escape(code)}\b', text_str, re.I):
            return code

    # Rs. / rs shorthand → PKR
    if re.search(r'\brs\.?\s', text_lower):
        return "PKR"

    # $ present — disambiguate via TLD; if no TLD signal, USD
    if "$" in text_str:
        return currency_from_url(page_url) or "USD"

    # USD literal
    if re.search(r'\bUSD\b', text_str, re.I):
        return currency_from_url(page_url) or "USD"

    # No symbol found — try URL alone
    return currency_from_url(page_url)


def normalize_price_text(raw, page_url=None):
    """
    Parse a raw price string into a normalised dict.

    Returns:
        None                           — if raw is empty/None
        {raw, amount, currency}        — always; amount=None when unparseable or zero
    """
    if not raw:
        return None

    raw_str = re.sub(r"\s+", " ", str(raw)).strip()
    if not raw_str:
        return None

    raw_lower = raw_str.lower()

    # --- Currency ---
    currency = _currency_from_symbols(raw_lower, raw_str)

    # $ disambiguation: use TLD when raw only contains $
    if currency is None and "$" in raw_str:
        currency = currency_from_url(page_url) or "USD"

    # --- Amount ---
    # Strip currency symbols/codes before parsing the number
    cleaned = re.sub(
        r'[£€₹₨¥₩﷼฿₺]|'
        r'\b(?:' + '|'.join(_CODE_CURRENCY) + r')\b|'
        r'\brs\.?\b',
        '', raw_str, flags=re.I
    )
    # Remove thousands separators; keep decimal point
    cleaned = re.sub(r'[,\s]+', '', cleaned)

    m = re.search(r'(\d+(?:\.\d{1,2})?)', cleaned)
    amount = None
    if m:
        try:
            amount = float(m.group(1))
            if amount == 0.0:
                amount = None          # zero-price guard
            elif amount == int(amount):
                amount = int(amount)
            else:
                amount = round(amount, 2)
        except (ValueError, OverflowError):
            amount = None

    return {"raw": raw_str, "amount": amount, "currency": currency}
