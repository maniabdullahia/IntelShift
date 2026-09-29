"""Generic deterministic pricing-plan card parser (DOM-based).

Fallback for pricing pages whose plan cards the text-based extractor misses.
Works on the common pattern shared by most pricing pages: repeated "card"
elements whose class mentions plan/pricing/tier/package, each containing a
short title and a money amount (possibly split across currency/amount spans,
e.g. WPBakery's `.plan-currency` + `.plan-price`).

Extracted per plan:
    name, price {raw, currency, amountRaw, amount, period}, compareAt
    (strikethrough / "Regular price $X"), features (li texts), type.
Output matches the analyzer's existing pricing.plans schema.
"""

from __future__ import annotations

import re

MONEY_RE = re.compile(
    r"(?P<cur>[$€£₹₨]|USD|EUR|GBP|PKR|Rs\.?)\s?(?P<amt>\d[\d,]*(?:\.\d+)?)"
    r"|(?P<amt2>\d[\d,]*(?:\.\d+)?)\s?(?P<cur2>[$€£]|USD|EUR|GBP|PKR)",
    re.I,
)
PERIOD_RE = re.compile(r"/\s*(mo(?:nth)?|yr|year|annual(?:ly)?|lifetime|one[- ]?time|user|seat|site)s?\b", re.I)
CARD_CLASS_RE = re.compile(r"\b(plan|pricing|tier|package|price[-_]?(table|box|card|column))\w*", re.I)
TITLE_CLASS_RE = re.compile(r"(title|name|heading)", re.I)
COMPARE_CLASS_RE = re.compile(r"(meta|regular|old[-_]?price|was[-_]?price|compare|strike)", re.I)

_CURRENCY_MAP = {"$": "$", "€": "EUR", "£": "GBP", "₹": "INR", "₨": "PKR",
                 "usd": "USD", "eur": "EUR", "gbp": "GBP", "pkr": "PKR", "rs": "PKR", "rs.": "PKR"}


def _parse_money(text):
    """Return (raw, currency, amountRaw, amount) for the first money in text."""
    m = MONEY_RE.search(text or "")
    if not m:
        return None
    cur = (m.group("cur") or m.group("cur2") or "").strip()
    amt_raw = (m.group("amt") or m.group("amt2") or "").strip()
    try:
        amount = float(amt_raw.replace(",", ""))
    except ValueError:
        return None
    currency = _CURRENCY_MAP.get(cur.lower(), cur) or None
    return {"raw": m.group(0).strip(), "currency": currency, "amountRaw": amt_raw, "amount": amount}


def _clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def _classes(el):
    return " ".join(el.get("class") or [])


def extract_plan_cards_from_dom(soup, max_plans=8):
    """Find pricing plan cards in the DOM. Returns [] when nothing looks like
    a plan grid (so callers can safely use it as a fallback)."""
    if soup is None:
        return []

    # Candidate cards: class mentions plan/pricing/tier/package AND the element
    # contains money. Use the OUTERMOST such elements (skip nested duplicates).
    candidates = []
    for el in soup.find_all(True, class_=CARD_CLASS_RE):
        text = el.get_text(" ", strip=True)
        if not text or len(text) > 2500:
            continue
        if not MONEY_RE.search(text):
            continue
        candidates.append(el)

    outer = []
    for el in candidates:
        if any(parent in candidates for parent in el.parents):
            continue
        outer.append(el)

    plans = []
    seen_names = set()
    for card in outer[: max_plans * 3]:
        card_text = card.get_text(" ", strip=True)

        # name: title-classed child, else first short heading
        name = None
        title_el = card.find(True, class_=TITLE_CLASS_RE)
        if title_el:
            t = _clean(title_el.get_text(" ", strip=True))
            if t and len(t) <= 60 and not MONEY_RE.search(t):
                name = t
        if not name:
            for h in card.find_all(re.compile(r"^h[2-6]$")):
                t = _clean(h.get_text(" ", strip=True))
                if t and len(t) <= 60 and not MONEY_RE.search(t):
                    name = t
                    break
        if not name:
            continue

        # compare-at FIRST (strikethrough / 'Regular price'), so we can exclude
        # its money from the main-price search.
        compare_at = None
        for cel in card.find_all(True, class_=COMPARE_CLASS_RE) + card.find_all(["del", "s", "strike"]):
            money = _parse_money(cel.get_text(" ", strip=True))
            if money:
                compare_at = money
                cel.extract()  # remove so main price search cannot pick it
                break

        money = _parse_money(card.get_text(" ", strip=True))
        if not money:
            continue

        # A real compare-at is HIGHER than the current price; anything else is
        # a mis-grabbed duplicate of the price itself.
        if compare_at and compare_at.get("amount", 0) <= money.get("amount", 0):
            compare_at = None

        period_match = PERIOD_RE.search(card_text)
        period = ("/" + period_match.group(1).lower()) if period_match else None
        if period:
            money["period"] = period

        features = []
        for li in card.find_all("li")[:10]:
            t = _clean(li.get_text(" ", strip=True))
            if t and len(t) <= 160:
                features.append(t)

        key = name.lower()
        if key in seen_names:
            continue
        seen_names.add(key)

        plan = {
            "name": name,
            "type": "enterprise" if "enterprise" in key else "core_plan",
            "description": None,
            "price": money,
            "priceMentions": [money],
            "features": features,
        }
        if compare_at:
            plan["compareAt"] = compare_at
        plans.append(plan)
        if len(plans) >= max_plans:
            break

    # A single "plan" is usually a false positive (promo banner); require 2+.
    return plans if len(plans) >= 2 else []
