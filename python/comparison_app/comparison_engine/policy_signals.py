"""
policy_signals.py — turn crawled policy/shipping/payment pages into structured,
comparable signals.

We auto-track each store's shipping/returns/payment/FAQ pages (nobody selects them),
and the text-evidence layer captures their full text. This module MINES that text
for the things that actually matter competitively — free-shipping threshold, COD /
bank-deposit availability, delivery time, returns window — so the report can show a
"Shipping & Payment" comparison instead of leaving the insight buried in raw text.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


_MONEY = r"(?:rs\.?|pkr|₨|rs|\$|usd|aed|£|€)\s?[\d,]+(?:\.\d+)?"
_POLICY_URL_HINTS = ("polic", "shipping", "refund", "return", "faq", "delivery", "payment", "how-to")


def _site_policy_text(site: Dict[str, Any]) -> str:
    """Concatenate text from policy/FAQ pages + homepage announcement + footers."""
    parts: List[str] = []
    for page in site.get("pages", []) or []:
        if not isinstance(page, dict):
            continue
        ptype = (page.get("pageType") or "").lower()
        url = (page.get("url") or "").lower()
        is_policy = ptype in ("general", "policy", "page") or any(h in url for h in _POLICY_URL_HINTS)
        if is_policy or ptype == "homepage":
            rte = page.get("rawTextEvidence") or {}
            if isinstance(rte, dict):
                parts.append(rte.get("fullText") or "")
                parts.append(rte.get("top") or "")
                parts.append(rte.get("footer") or "")
            # Also the structured section text, as a fallback when rawTextEvidence is thin.
            for s in page.get("sections", []) or []:
                if isinstance(s, dict):
                    parts.append(s.get("textPreview") or "")
    hp = site.get("homepage") or {}
    parts.append(hp.get("announcementText") or "")
    for o in (hp.get("promotionalOffers") or []):
        if isinstance(o, dict):
            parts.append(o.get("type") or "")
    return " ".join(p for p in parts if p)[:24000].lower()


def _first(pattern: str, text: str) -> Optional[str]:
    m = re.search(pattern, text, re.I)
    return m.group(1).strip() if m else None


def extract_shipping_payment_signals(site: Dict[str, Any]) -> Dict[str, Any]:
    text = _site_policy_text(site)
    empty = {
        "hasPolicyEvidence": False,
        "freeShipping": False, "freeShippingThreshold": None,
        "codAvailable": False, "bankDeposit": False, "cardPayment": False, "onlineWallet": False,
        "deliveryTime": None,
        "returnsAllowed": None, "returnWindowDays": None,
        "notes": [],
    }
    if not text or len(text) < 40:
        return empty

    notes: List[str] = []
    free_ship = bool(re.search(r"free\s+(?:shipping|delivery)", text))
    # Threshold: "free delivery on orders over Rs 2000" / "free shipping above 3000"
    threshold = _first(
        r"free\s+(?:shipping|delivery)[^.]{0,40}?(?:over|above|on orders? (?:over|above)|for orders? (?:over|above))\s*(" + _MONEY + r")",
        text,
    ) or _first(r"free\s+(?:shipping|delivery)[^.]{0,30}?(" + _MONEY + r")", text)

    cod = bool(re.search(r"cash\s+on\s+delivery|\bcod\b", text))
    bank = bool(re.search(r"bank\s+(?:deposit|transfer)|online\s+bank", text))
    card = bool(re.search(r"credit\s+card|debit\s+card|card\s+payment|\bvisa\b|master\s?card", text))
    wallet = bool(re.search(r"easy\s?paisa|jazz\s?cash|sadapay|nayapay|paypal|apple\s+pay|google\s+pay", text))

    # Delivery time near a delivery/shipping context.
    delivery = _first(
        r"(?:deliver(?:y|ed)?|dispatch|ship(?:ping|ped)?)[^.]{0,40}?(\d{1,2}\s?[-–to]{1,3}\s?\d{1,2}\s*(?:working |business )?(?:days|hours|hrs))",
        text,
    ) or _first(r"(\d{1,2}\s?[-–to]{1,3}\s?\d{1,2}\s*(?:working |business )?(?:days|hrs|hours))[^.]{0,20}?(?:deliver|dispatch|ship)", text)

    # Returns
    returns_allowed = None
    if re.search(r"no\s+returns?|not\s+accept(?:ed)?\s+returns?|non[- ]?returnable|no\s+exchange|all\s+sales?\s+final", text):
        returns_allowed = False
    elif re.search(r"return|refund|exchange", text):
        returns_allowed = True
    window = _first(r"(?:within|in)\s+(\d{1,2})\s*(?:working |business )?days", text) \
        or _first(r"(\d{1,2})[- ]day\s+(?:return|exchange|refund)", text)

    if free_ship and not threshold:
        notes.append("free shipping (no threshold stated)")
    if bank:
        notes.append("bank deposit accepted")

    return {
        "hasPolicyEvidence": True,
        "freeShipping": free_ship,
        "freeShippingThreshold": threshold,
        "codAvailable": cod,
        "bankDeposit": bank,
        "cardPayment": card,
        "onlineWallet": wallet,
        "deliveryTime": delivery,
        "returnsAllowed": returns_allowed,
        "returnWindowDays": int(window) if window and window.isdigit() else None,
        "notes": notes,
    }


def build_shipping_payment_comparison(sites: List[Dict[str, Any]]) -> Dict[str, Any]:
    rows = []
    for s in sites:
        rows.append({"domain": s.get("domain"), **extract_shipping_payment_signals(s)})
    return {
        "displayType": "shipping_payment_table",
        "description": "Fulfilment & payment posture from each store's shipping/returns/payment pages: "
                       "free-shipping thresholds, COD / bank-deposit options, delivery time, and returns "
                       "window. These are conversion levers a competitor can win on without touching price.",
        "rows": rows,
    }
