"""
store_profile.py — pure (no-network) readers for the store profile.

Step 1  Journey   — does the homepage expose search / cart entry points?
Step 3  Market    — WHERE the store operates and delivers:
                     • home country  (Shopify /meta.json, JSON-LD address, ccTLD,
                                      currency, phone code, country mentions)
                     • service scope (domestic / selected countries / worldwide)
                       from the shipping policy wording, the Shopify Markets
                       country selector, and JSON-LD shippingDestination.
        Language  — IntelShift supports ENGLISH stores only: <html lang> plus an
                    English stop-word ratio over the visible text (lang attributes
                    are often left at the theme default, so text decides).

site_validator.py does the fetching and calls these.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse

from .store_locale import COUNTRY_NAMES, _split_hreflang

# ccTLDs that are sold as generic vanity domains — never a country signal.
VANITY_TLDS = {"CO", "IO", "AI", "ME", "TV", "FM", "LY", "GG", "SO", "TO", "SH", "AC", "CC", "WS", "IS"}
# Eurozone ccTLDs that double as vanity domains (shop.it, get.at, be.de…): only
# trusted as a country when the store actually prices in EUR.
_EU_TLDS = {"IT", "AT", "BE", "DE"}

PHONE_PREFIX_COUNTRY = [
    ("+971", "AE"), ("+966", "SA"), ("+974", "QA"), ("+965", "KW"), ("+968", "OM"),
    ("+973", "BH"), ("+880", "BD"), ("+977", "NP"), ("+92", "PK"), ("+91", "IN"),
    ("+94", "LK"), ("+44", "GB"), ("+61", "AU"), ("+64", "NZ"), ("+65", "SG"),
    ("+60", "MY"), ("+63", "PH"), ("+62", "ID"), ("+27", "ZA"), ("+234", "NG"),
    ("+254", "KE"), ("+20", "EG"), ("+90", "TR"),
]
# Currencies that pin a single country (USD/EUR deliberately absent).
CURRENCY_HOME = {
    "PKR": "PK", "INR": "IN", "BDT": "BD", "LKR": "LK", "NPR": "NP", "GBP": "GB",
    "AED": "AE", "SAR": "SA", "QAR": "QA", "KWD": "KW", "OMR": "OM", "BHD": "BH",
    "AUD": "AU", "NZD": "NZ", "CAD": "CA", "SGD": "SG", "MYR": "MY", "PHP": "PH",
    "IDR": "ID", "ZAR": "ZA", "NGN": "NG", "KES": "KE", "EGP": "EG", "TRY": "TR",
    "JPY": "JP", "KRW": "KR", "HKD": "HK", "THB": "TH", "VND": "VN",
}
_NAME_TO_ISO = {v.lower(): k for k, v in COUNTRY_NAMES.items() if k != "UK"}
_NAME_TO_ISO.update({"uk": "GB", "usa": "US", "uae": "AE", "britain": "GB", "england": "GB"})


# ── Language (English only) ─────────────────────────────────────────────────
_EN_STOPWORDS = {
    "the", "and", "to", "of", "for", "with", "your", "you", "in", "on", "our",
    "is", "a", "all", "new", "shop", "free", "by", "from", "now", "more", "add",
    "cart", "sale", "off", "shipping", "sign", "up", "view", "collection",
}
_WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)


def detect_language(soup, visible_text: str) -> Dict[str, Any]:
    """{ htmlLang, isEnglish, englishRatio, latinRatio, englishAlternate }."""
    html_tag = soup.find("html") if soup is not None else None
    html_lang = (html_tag.get("lang") or "").strip().lower() if html_tag else ""
    words = _WORD_RE.findall((visible_text or "")[:20000])
    total = len(words) or 1
    lower = [w.lower() for w in words]
    en_hits = sum(1 for w in lower if w in _EN_STOPWORDS)
    latin = sum(1 for w in words if re.fullmatch(r"[A-Za-z]+", w))
    en_ratio = en_hits / total
    latin_ratio = latin / total

    # An English alternate (hreflang="en"/"en-xx") lets us point the user at the
    # English version of a multilingual store.
    alt = None
    if soup is not None:
        for link in soup.find_all("link", rel=lambda r: r and "alternate" in (r if isinstance(r, list) else [r])):
            lang, _c = _split_hreflang(link.get("hreflang") or "")
            if lang == "en" and link.get("href"):
                alt = link["href"]
                break

    if len(words) < 40:
        is_en = not html_lang or html_lang.startswith("en")  # too little text to judge
    elif latin_ratio < 0.5:
        is_en = False                                          # Arabic / Urdu / CJK script
    elif en_ratio >= 0.04:
        is_en = True                                           # English text, whatever lang says
    else:
        is_en = False                                          # Latin script, not English (de/fr/es…)
    return {
        "htmlLang": html_lang or None,
        "isEnglish": is_en,
        "englishRatio": round(en_ratio, 3),
        "latinRatio": round(latin_ratio, 3),
        "englishAlternate": alt,
    }


# ── Journey entry points (homepage) ─────────────────────────────────────────
_SEARCH_INPUT_NAMES = {"q", "s", "search", "query", "keyword", "keywords", "term", "search_query"}


def find_search(soup, base_url: str) -> Dict[str, Any]:
    """Detect a site search: a search input/form, or a link to /search."""
    if soup is None:
        return {"found": False}
    for inp in soup.find_all("input"):
        t = (inp.get("type") or "").lower()
        n = (inp.get("name") or "").lower()
        if t == "search" or n in _SEARCH_INPUT_NAMES:
            form = inp.find_parent("form")
            action = urljoin(base_url, form.get("action") or "/") if form else None
            return {"found": True, "via": "form", "action": action, "param": n or "q"}
    for a in soup.find_all("a", href=True):
        path = urlparse(urljoin(base_url, a["href"])).path.lower()
        if path.rstrip("/").endswith("/search"):
            return {"found": True, "via": "link", "action": urljoin(base_url, a["href"]), "param": "q"}
    return {"found": False}


def find_cart_link(soup, base_url: str) -> Optional[str]:
    if soup is None:
        return None
    for a in soup.find_all("a", href=True):
        full = urljoin(base_url, a["href"])
        path = urlparse(full).path.lower().rstrip("/")
        if path.endswith(("/cart", "/basket", "/bag", "/shopping-bag", "/shopping-cart")):
            return full
    return None


# ── Market / service area ───────────────────────────────────────────────────
def hreflang_countries(soup) -> Set[str]:
    out: Set[str] = set()
    if soup is None:
        return out
    for link in soup.find_all("link", hreflang=True):
        _lang, country = _split_hreflang(link.get("hreflang") or "")
        if country and country in COUNTRY_NAMES:
            out.add("GB" if country == "UK" else country)
    return out


def localization_countries(soup) -> Set[str]:
    """Countries offered by a Shopify Markets / localization country selector —
    the store's configured selling markets."""
    out: Set[str] = set()
    if soup is None:
        return out
    containers = []
    for form in soup.find_all("form"):
        if "localization" in (form.get("action") or "") or form.get("id", "").lower().startswith("localization"):
            containers.append(form)
    for sel in soup.find_all(["select", "input"], attrs={"name": re.compile(r"country_code", re.I)}):
        containers.append(sel.find_parent("form") or sel)
    for c in containers:
        for node in c.find_all(True):
            for attr in ("value", "data-value", "data-country-code", "data-iso-code"):
                v = (node.get(attr) or "").strip().upper()
                if len(v) == 2 and v in COUNTRY_NAMES:
                    out.add("GB" if v == "UK" else v)
    return out


def _iter_jsonld(soup) -> Iterable[Any]:
    if soup is None:
        return
    for s in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(s.string or s.get_text() or "")
        except Exception:
            continue
        stack = [data]
        while stack:
            node = stack.pop()
            if isinstance(node, list):
                stack.extend(node)
            elif isinstance(node, dict):
                yield node
                stack.extend(v for v in node.values() if isinstance(v, (dict, list)))


def _iso(value: Any) -> Optional[str]:
    if isinstance(value, dict):
        value = value.get("name") or value.get("addressCountry")
    if not isinstance(value, str):
        return None
    v = value.strip()
    if len(v) == 2 and v.upper() in COUNTRY_NAMES:
        return "GB" if v.upper() == "UK" else v.upper()
    return _NAME_TO_ISO.get(v.lower())


def jsonld_market(*soups) -> Tuple[Optional[str], Set[str]]:
    """(addressCountry of the Organization/Store, shippingDestination countries)."""
    home, ships = None, set()
    for soup in soups:
        for node in _iter_jsonld(soup):
            addr = node.get("address")
            if not home and isinstance(addr, (dict, list)):
                for a in (addr if isinstance(addr, list) else [addr]):
                    iso = _iso(a.get("addressCountry")) if isinstance(a, dict) else None
                    if iso:
                        home = iso
                        break
            dest = node.get("shippingDestination")
            for d in (dest if isinstance(dest, list) else [dest] if dest else []):
                iso = _iso(d.get("addressCountry")) if isinstance(d, dict) else None
                if iso:
                    ships.add(iso)
    return home, ships


_WORLDWIDE_RE = re.compile(
    r"\b(ship(?:ping)?|deliver(?:y|ies)?)\b[^.]{0,60}\b(worldwide|world[- ]wide|globally|internationally|all over the world|"
    r"to (?:over|more than) \d+ countries|to most countries)\b"
    r"|\binternational (?:shipping|delivery|orders) (?:is |are )?(?:available|offered)\b"
    r"|\bwe ship (?:to )?(?:anywhere|everywhere)\b",
    re.I,
)
_DOMESTIC_RE = re.compile(
    r"\b(?:we )?(?:only|currently only|exclusively) (?:ship|deliver)\w* (?:with)?in\b"
    r"|\b(?:ship|deliver)\w* (?:only )?(?:with)?in (?:the )?(?:uk|usa|us|united states|united kingdom|pakistan|india|uae|"
    r"canada|australia|new zealand|bangladesh|sri lanka|saudi arabia|south africa)\s+only\b"
    r"|\b(?:do not|don't|does not|cannot|can't) (?:currently )?(?:ship|deliver)\w* (?:internationally|outside|overseas|abroad)\b"
    r"|\bnationwide (?:delivery|shipping)\b|\bfree delivery (?:all )?across (?:the )?(?:country|pakistan|india|uk|uae)\b"
    r"|\bdomestic (?:orders|shipping|delivery) only\b",
    re.I,
)
_SELECTED_RE = re.compile(
    r"\bwe (?:currently )?(?:ship|deliver) to the following countries\b"
    r"|\b(?:ship|deliver)\w* to (?:select(?:ed)?|certain|a (?:limited|small) number of) countries\b",
    re.I,
)


def shipping_scope_from_text(text: str) -> Tuple[Optional[str], Optional[str]]:
    """('worldwide'|'domestic'|'selected'|None, evidence snippet)."""
    t = re.sub(r"\s+", " ", text or "")
    # Domestic phrasing is checked first: "we don't ship internationally" must
    # not be read as worldwide because it contains "internationally".
    for scope, rx in (("domestic", _DOMESTIC_RE), ("selected", _SELECTED_RE), ("worldwide", _WORLDWIDE_RE)):
        m = rx.search(t)
        if m:
            s = max(0, m.start() - 40)
            return scope, t[s: m.end() + 40].strip()
    return None, None


def countries_mentioned(text: str) -> Set[str]:
    low = f" {(text or '').lower()} "
    out = set()
    for name, iso in _NAME_TO_ISO.items():
        if len(name) <= 3:
            if re.search(rf"\b{re.escape(name)}\b", low):
                out.add(iso)
        elif name in low:
            out.add(iso)
    return out


def _tld_country(host: str, currency: Optional[str]) -> Optional[str]:
    labels = [l for l in (host or "").lower().split(".") if l]
    if len(labels) < 2:
        return None
    tld = labels[-1].upper()
    if tld == "UK":
        return "GB"
    if tld not in COUNTRY_NAMES:
        return None
    if tld in _EU_TLDS:
        return tld if currency == "EUR" else None
    if tld in VANITY_TLDS:
        return None
    return tld


def _phone_country(text: str) -> Optional[str]:
    for prefix, iso in PHONE_PREFIX_COUNTRY:
        if prefix in (text or ""):
            return iso
    return None


def resolve_market(
    *,
    url: str,
    currency: Optional[str],
    meta_country: Optional[str] = None,
    jsonld_home: Optional[str] = None,
    jsonld_ships: Optional[Set[str]] = None,
    localization: Optional[Set[str]] = None,
    hreflang: Optional[Set[str]] = None,
    policy_scope: Optional[str] = None,
    policy_evidence: Optional[str] = None,
    policy_countries: Optional[Set[str]] = None,
    page_text: str = "",
) -> Dict[str, Any]:
    """Combine every signal into store_market_v1:
    { country, countryName, scope, shipsTo[], currency, confidence, signals[], evidence }"""
    signals: List[str] = []
    cur = (currency or "").upper() or None
    host = urlparse(url if "://" in (url or "") else f"https://{url}").netloc

    # Home country — strongest first.
    country = None
    for source, value in (
        ("shopify_meta", _iso(meta_country) if meta_country else None),
        ("jsonld_address", jsonld_home),
        ("cctld", _tld_country(host, cur)),
        ("currency", CURRENCY_HOME.get(cur or "")),
        ("phone_code", _phone_country(page_text)),
    ):
        if value:
            country = value
            signals.append(f"country:{source}")
            break

    ships: Set[str] = set()
    for src, vals in (("localization", localization), ("jsonld_shipping", jsonld_ships)):
        if vals:
            ships |= set(vals)
            signals.append(f"ships:{src}")

    scope = None
    if policy_scope:
        scope = policy_scope
        signals.append("scope:shipping_policy")
        if policy_scope == "selected" and policy_countries:
            ships |= set(policy_countries)
    elif ships:
        n = len(ships | ({country} if country else set()))
        scope = "domestic" if n <= 1 else ("worldwide" if n >= 30 else "selected")
        signals.append("scope:country_list")
    elif hreflang and len(hreflang) >= 2:
        scope = "worldwide" if len(hreflang) >= 30 else "selected"
        ships |= set(hreflang)
        signals.append("scope:hreflang")

    if scope == "domestic" and country:
        ships = {country}

    strong = any(s in signals for s in ("country:shopify_meta", "country:jsonld_address")) and scope is not None
    weak = country is None and scope is None
    return {
        "schemaVersion": "store_market_v1",
        "country": country,
        "countryName": COUNTRY_NAMES.get(country) if country else None,
        "scope": scope or "unknown",
        "shipsTo": sorted(ships)[:60],
        "shipsToCount": len(ships),
        "currency": cur,
        "confidence": "high" if strong else ("low" if weak else "medium"),
        "signals": signals,
        "evidence": policy_evidence,
    }
