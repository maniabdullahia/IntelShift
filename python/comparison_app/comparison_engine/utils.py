from __future__ import annotations

from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
import re


def safe_get(data: Any, path: List[Any], default: Any = None) -> Any:
    current = data
    for key in path:
        if isinstance(current, dict):
            current = current.get(key)
        elif isinstance(current, list) and isinstance(key, int) and 0 <= key < len(current):
            current = current[key]
        else:
            return default
        if current is None:
            return default
    return current


def as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def domain_from_url(url: str) -> str:
    try:
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return ""


def normalize_price_value(price: Any) -> Optional[float]:
    if price is None:
        return None

    if isinstance(price, dict):
        for key in ["current", "amount", "value", "price", "min"]:
            val = price.get(key)
            parsed = normalize_price_value(val)
            if parsed is not None:
                return parsed
        raw = price.get("priceTextRaw") or price.get("text")
        return normalize_price_value(raw)

    if isinstance(price, (int, float)):
        # A price of 0 means "no price" (priced on request), not a real value —
        # treat it as absent so it never skews averages or shows as "0".
        return float(price) if float(price) != 0 else None

    text = str(price)
    text = text.replace(",", "")
    match = re.search(r"\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        val = float(match.group(0))
        return val if val != 0 else None
    except Exception:
        return None


def detect_currency(price: Any, fallback: Optional[str] = None) -> Optional[str]:
    if isinstance(price, dict):
        return price.get("currency") or detect_currency(price.get("priceTextRaw"), fallback)
    text = str(price or "")
    if "Rs" in text or "PKR" in text:
        return "PKR"
    if "$" in text or "USD" in text:
        return "USD"
    if "£" in text or "GBP" in text:
        return "GBP"
    if "€" in text or "EUR" in text:
        return "EUR"
    return fallback


def unique_by(items: List[Dict[str, Any]], key_fn) -> List[Dict[str, Any]]:
    seen = set()
    out = []
    for item in items:
        key = key_fn(item)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def pct(numerator: float, denominator: float) -> float:
    if not denominator:
        return 0.0
    return round(numerator / denominator, 4)
