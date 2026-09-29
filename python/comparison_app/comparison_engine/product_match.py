"""
product_match.py — suggest product-to-product matches WITHIN a chosen collection pair.

Scoped and suggestion-only (never auto-asserted globally): the user has already
paired the collections, so both sides are the same category. We auto-match locally
(cheap, deterministic) and, on Growth+, let a cheap model CONFIRM/prune the shortlist
— "a few products our system matched, AI confirms." The user still approves.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


_STOP = {
    "the", "a", "an", "and", "for", "with", "of", "in", "to", "by", "on",
    "new", "best", "premium", "original", "pack", "set", "ml", "gm", "g",
    "makeup", "make", "up", "long", "lasting", "waterproof", "matte", "finish",
    "natural", "look", "color", "colour", "shade", "professional",
}


def _tokens(name: str) -> set:
    words = re.findall(r"[a-z0-9]+", (name or "").lower())
    return {w for w in words if len(w) > 1 and w not in _STOP}


def _get(p: Dict[str, Any], *keys):
    for k in keys:
        v = p.get(k)
        if v not in (None, ""):
            return v
    return None


def _price(p: Dict[str, Any]) -> Optional[float]:
    v = _get(p, "priceValue", "price")
    try:
        return float(v) if v is not None else None
    except Exception:
        return None


def _similarity(a: Dict[str, Any], b: Dict[str, Any]) -> float:
    ta, tb = _tokens(_get(a, "name", "title") or ""), _tokens(_get(b, "name", "title") or "")
    if not ta or not tb:
        return 0.0
    jac = len(ta & tb) / len(ta | tb)
    # Price proximity bonus (same category → similar price is corroborating).
    pa, pb = _price(a), _price(b)
    price_bonus = 0.0
    if pa and pb and max(pa, pb) > 0:
        ratio = min(pa, pb) / max(pa, pb)
        if ratio >= 0.6:
            price_bonus = 0.15 * ratio
    return min(1.0, jac + price_bonus)


def suggest_matches(
    user_products: List[Dict[str, Any]],
    competitor_products: List[Dict[str, Any]],
    use_ai: bool = False,
    min_confidence: float = 0.34,
    max_suggestions: int = 40,
) -> Dict[str, Any]:
    """Return { suggestions:[{...}], source }. Each suggestion pairs one user product
    with its best competitor match above the confidence floor."""
    suggestions = []
    used_comp = set()
    # Greedy best-match per user product (highest similarity first, 1:1).
    pairs = []
    for i, up in enumerate(user_products or []):
        best_j, best_s = None, 0.0
        for j, cp in enumerate(competitor_products or []):
            s = _similarity(up, cp)
            if s > best_s:
                best_s, best_j = s, j
        if best_j is not None and best_s >= min_confidence:
            pairs.append((best_s, i, best_j))
    pairs.sort(reverse=True)
    for s, i, j in pairs:
        if j in used_comp:
            continue
        used_comp.add(j)
        up, cp = user_products[i], competitor_products[j]
        suggestions.append({
            "userName": _get(up, "name", "title"),
            "userUrl": _get(up, "productUrl", "url"),
            "userPrice": _price(up),
            "competitorName": _get(cp, "name", "title"),
            "competitorUrl": _get(cp, "productUrl", "url"),
            "competitorPrice": _price(cp),
            "confidence": round(s, 3),
            "source": "heuristic",
        })
        if len(suggestions) >= max_suggestions:
            break

    source = "heuristic"
    if use_ai and suggestions:
        confirmed = _ai_confirm(suggestions)
        if confirmed is not None:
            suggestions = confirmed
            source = "ai_confirmed"

    return {"suggestions": suggestions, "source": source, "count": len(suggestions)}


def _ai_confirm(suggestions: List[Dict[str, Any]]) -> Optional[List[Dict[str, Any]]]:
    """Ask a cheap model to confirm/prune the shortlist. Returns the kept subset with
    an AI confidence, or None to keep the heuristic result."""
    try:
        import sys, os
        # ai_assist lives in the website analyzer app (on sys.path in the API).
        from level1_detector.ai_assist import ai_json, ai_enabled  # type: ignore
    except Exception:
        return None
    if not ai_enabled():
        return None
    shortlist = [{"i": i, "user": s["userName"], "competitor": s["competitorName"],
                  "userPrice": s.get("userPrice"), "competitorPrice": s.get("competitorPrice")}
                 for i, s in enumerate(suggestions)]
    system = ("You confirm whether two e-commerce products are the same or directly "
              "comparable item (same product type/purpose), for a like-for-like price "
              "comparison. Be strict: reject pairs that are merely the same category.")
    user = ('For each pair, decide if it is a genuine match. Return JSON '
            '{"matches":[{"i":index,"match":true|false,"confidence":0..1}]}.\n\n'
            + __import__("json").dumps(shortlist)[:8000])
    out = ai_json(system, user, max_tokens=800)
    matches = (out or {}).get("matches")
    if not isinstance(matches, list):
        return None
    keep = []
    by_i = {m.get("i"): m for m in matches if isinstance(m, dict)}
    for i, s in enumerate(suggestions):
        m = by_i.get(i)
        if m and m.get("match"):
            s = dict(s)
            s["source"] = "ai_confirmed"
            if isinstance(m.get("confidence"), (int, float)):
                s["confidence"] = round(float(m["confidence"]), 3)
            keep.append(s)
    return keep
