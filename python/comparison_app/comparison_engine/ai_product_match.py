"""
ai_product_match.py — AI-first product-to-product matching (Growth / Pro).

The old local matcher paired products by word overlap. It was unreliable (it
missed "Sivanna Air Fryer 5L" ↔ "Gabrini Digital Fryer 5 Litre" and paired
lookalike names that were different items) and is now OFF by default.

Here the AI makes the decision. We only use cheap local scoring to NARROW each
user product to a handful of plausible candidates (so a 40×150 collection pair
is ~6 candidates per product, not 150), then ask the model to pick the genuine
like-for-like match — or none. Matching stays scoped to a collection pair the
user (or Pro auto-select) already mapped, so both sides are the same category.

Output has exactly the shape of matching.match_products(), so the comparison UI
and the AI-insights payload consume it unchanged; each match carries
matchReasons = ["ai", "<short reason>"] and source "ai".

Fail-open: no AI key / AI error → {"source": "none"} with every product left
unmatched (we never fall back to the unreliable fuzzy pairs).
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
from collections import OrderedDict
from statistics import median
from typing import Any, Callable, Dict, List, Optional, Tuple

from .matching import (
    attribute_tokens,
    compact_product,
    compare_product_positioning,
    core_tokens,
    infer_product_type,
    jaccard,
    match_tier,
    price_gap,
)

MAX_USER = int(os.environ.get("AI_MATCH_MAX_USER", "40"))
MAX_COMP = int(os.environ.get("AI_MATCH_MAX_COMP", "150"))
CANDIDATES_PER_PRODUCT = int(os.environ.get("AI_MATCH_CANDIDATES", "6"))
BATCH = int(os.environ.get("AI_MATCH_BATCH", "12"))
MIN_CONFIDENCE = float(os.environ.get("AI_MATCH_MIN_CONFIDENCE", "0.6"))

SYSTEM = (
    "You match e-commerce products between two competing stores for a like-for-like "
    "price comparison. A match must be the SAME kind of item a shopper would compare "
    "directly: same product type and purpose, comparable size/capacity/quantity and "
    "spec tier. Different brands are expected and fine. Being in the same category is "
    "NOT enough (a 5L air fryer vs a 2L air fryer, a lipstick vs a lip liner, a single "
    "item vs a bundle of 3 are not matches). If no candidate is a genuine match, "
    "answer null. Never invent ids."
)

_cache: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
_cache_lock = threading.Lock()
_CACHE_MAX = 2000


def _price(p: Dict[str, Any]) -> Optional[float]:
    for k in ("priceValue", "price"):
        v = p.get(k)
        try:
            if v not in (None, ""):
                return float(v)
        except (TypeError, ValueError):
            continue
    return None


def _name(p: Dict[str, Any]) -> str:
    return str(p.get("name") or p.get("title") or "").strip()


def _norm(p: Dict[str, Any]) -> Dict[str, Any]:
    q = dict(p)
    q["name"] = _name(p)
    q["priceValue"] = _price(p)
    q.setdefault("productUrl", p.get("url"))
    return q


def _prefilter_score(u: Dict[str, Any], c: Dict[str, Any]) -> float:
    """Cheap plausibility score used ONLY to shortlist candidates for the AI."""
    ut, ct = infer_product_type(u), infer_product_type(c)
    if ut and ct and ut != ct:
        return -1.0  # different inferred type: never a candidate
    s = 0.0
    if ut and ut == ct:
        s += 0.4
    s += jaccard(core_tokens(u["name"]), core_tokens(c["name"]))
    if attribute_tokens(u["name"]) & attribute_tokens(c["name"]):
        s += 0.2
    pu, pc = u.get("priceValue"), c.get("priceValue")
    if pu and pc:
        s += 0.15 * (min(pu, pc) / max(pu, pc))
    return s


def _shortlist(u: Dict[str, Any], comps: List[Dict[str, Any]], k: int) -> List[int]:
    scored = [(i, _prefilter_score(u, c)) for i, c in enumerate(comps)]
    scored = [x for x in scored if x[1] >= 0]
    scored.sort(key=lambda x: x[1], reverse=True)
    top = [i for i, s in scored[:k] if s > 0]
    if len(top) < k:
        # Names may share nothing ("Sivanna" vs "Gabrini") — within an already
        # category-matched pair, nearest price is the next best plausibility cue.
        pu = u.get("priceValue")
        rest = [i for i, _ in scored if i not in top]
        if pu:
            rest.sort(key=lambda i: abs((comps[i].get("priceValue") or 1e18) - pu))
        top += rest[: k - len(top)]
    return top


def _default_ai() -> Optional[Callable[[str, str, int], Optional[Dict[str, Any]]]]:
    try:
        from level1_detector.ai_assist import ai_enabled, ai_json  # type: ignore
    except Exception:
        return None
    if not ai_enabled():
        return None
    return lambda system, user, max_tokens: ai_json(system, user, max_tokens=max_tokens)


def _cache_key(users: List[Dict[str, Any]], comps: List[Dict[str, Any]]) -> str:
    sig = json.dumps(
        [[(_name(p), _price(p)) for p in users], [(_name(p), _price(p)) for p in comps]],
        sort_keys=True, default=str,
    )
    return hashlib.sha256(sig.encode("utf-8")).hexdigest()


def _ask_ai(ai, users, comps, shortlists, currency) -> Dict[int, Tuple[int, float, str]]:
    """{user_index: (comp_index, confidence, reason)} for the AI's picks."""
    picks: Dict[int, Tuple[int, float, str]] = {}
    idxs = [i for i in range(len(users)) if shortlists[i]]
    for start in range(0, len(idxs), BATCH):
        chunk = idxs[start:start + BATCH]
        items = []
        for ui in chunk:
            u = users[ui]
            items.append({
                "u": ui,
                "product": u["name"][:140],
                "price": u.get("priceValue"),
                "candidates": [
                    {"id": f"c{ci}", "product": comps[ci]["name"][:140], "price": comps[ci].get("priceValue")}
                    for ci in shortlists[ui]
                ],
            })
        prompt = (
            f"Prices are in {currency or 'the same currency'}. For each item, pick the candidate id that "
            "is a genuine like-for-like match, or null.\n"
            'Reply ONLY JSON: {"matches":[{"u":<int>,"c":"<id>"|null,"confidence":0..1,'
            '"reason":"<max 12 words>"}]}\n\n' + json.dumps(items, ensure_ascii=False)
        )
        try:
            out = ai(SYSTEM, prompt, 1400) or {}
        except Exception as exc:  # one failed batch never sinks the rest
            print(f"[ai_product_match] batch failed: {exc}")
            continue
        for m in out.get("matches") or []:
            if not isinstance(m, dict):
                continue
            ui, cid = m.get("u"), m.get("c")
            if not isinstance(ui, int) or ui not in chunk or not isinstance(cid, str) or not cid.startswith("c"):
                continue
            try:
                ci = int(cid[1:])
            except ValueError:
                continue
            if ci not in shortlists[ui]:
                continue  # the model may only choose from the shortlist
            try:
                conf = max(0.0, min(1.0, float(m.get("confidence", 0))))
            except (TypeError, ValueError):
                conf = 0.0
            picks[ui] = (ci, conf, str(m.get("reason") or "")[:120])
    return picks


def ai_match_products(
    user_products: List[Dict[str, Any]],
    competitor_products: List[Dict[str, Any]],
    *,
    category: Optional[str] = None,
    currency: Optional[str] = None,
    ai: Optional[Callable[[str, str, int], Optional[Dict[str, Any]]]] = None,
    use_cache: bool = True,
) -> Dict[str, Any]:
    users = [_norm(p) for p in (user_products or []) if _name(p)][:MAX_USER]
    comps = [_norm(p) for p in (competitor_products or []) if _name(p)][:MAX_COMP]
    ref = [p["priceValue"] for p in users + comps if p.get("priceValue") is not None]

    def _unmatched_result(source: str, matches=None, used_u=frozenset(), used_c=frozenset()):
        matches = matches or []
        gaps = [m["priceGap"]["percentVsUser"] for m in matches if m["priceGap"]["percentVsUser"] is not None]
        return {
            "matchedProductCount": len(matches),
            "userUnmatchedCount": len(users) - len(used_u),
            "competitorUnmatchedCount": len(comps) - len(used_c),
            "medianPriceGapPercentVsUser": round(median(gaps), 2) if gaps else None,
            "matches": sorted(matches, key=lambda m: m["confidence"], reverse=True),
            "userUnmatchedProducts": [compact_product(users[i], ref) for i in range(len(users)) if i not in used_u][:250],
            "competitorUnmatchedProducts": [compact_product(comps[i], ref) for i in range(len(comps)) if i not in used_c][:250],
            "source": source,
        }

    if not users or not comps:
        return _unmatched_result("none")
    ai = ai or _default_ai()
    if ai is None:
        return _unmatched_result("none")

    key = _cache_key(users, comps) if use_cache else None
    if key:
        with _cache_lock:
            hit = _cache.get(key)
            if hit is not None:
                _cache.move_to_end(key)
                return json.loads(json.dumps(hit))

    shortlists = [_shortlist(u, comps, CANDIDATES_PER_PRODUCT) for u in users]
    picks = _ask_ai(ai, users, comps, shortlists, currency)

    # Enforce 1:1 — when two user products claim the same competitor product,
    # the more confident pick wins.
    ranked = sorted(picks.items(), key=lambda kv: kv[1][1], reverse=True)
    used_u, used_c, matches = set(), set(), []
    for ui, (ci, conf, reason) in ranked:
        if conf < MIN_CONFIDENCE or ci in used_c:
            continue
        used_u.add(ui)
        used_c.add(ci)
        up, cp = users[ui], comps[ci]
        matches.append({
            "confidence": round(conf, 3),
            "matchTier": match_tier(conf),
            "matchReasons": ["ai"] + ([reason] if reason else []),
            "userProduct": compact_product(up, ref),
            "competitorProduct": compact_product(cp, ref),
            "priceGap": price_gap(up.get("priceValue"), cp.get("priceValue")),
            "positioningComparisonSignals": compare_product_positioning(up, cp),
        })
    out = _unmatched_result("ai", matches, used_u, used_c)
    out["category"] = category
    if key:
        with _cache_lock:
            _cache[key] = out
            _cache.move_to_end(key)
            while len(_cache) > _CACHE_MAX:
                _cache.popitem(last=False)
    return out


def ai_match_pairs(pairs: List[Dict[str, Any]], *, ai=None) -> List[Dict[str, Any]]:
    """Batch API: pairs = [{key, category, currency, userProducts, competitorProducts}].
    Returns [{key, productMatching}] in the same order."""
    out = []
    for p in pairs or []:
        try:
            pm = ai_match_products(
                p.get("userProducts") or [], p.get("competitorProducts") or [],
                category=p.get("category"), currency=p.get("currency"), ai=ai,
            )
        except Exception as exc:  # fail-open per pair
            print(f"[ai_product_match] pair {p.get('key')} failed: {exc}")
            pm = None
        out.append({"key": p.get("key"), "productMatching": pm})
    return out
