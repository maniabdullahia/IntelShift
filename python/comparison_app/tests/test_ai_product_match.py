"""AI-first product matching — the model is stubbed, so these run offline."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from comparison_engine.ai_product_match import ai_match_products, ai_match_pairs, _shortlist, _norm


def P(name, price):
    return {"name": name, "priceValue": price, "currency": "PKR", "productUrl": f"https://x/{name.replace(' ', '-')}"}


USERS = [P("Sivanna Air Fryer 5L Digital Touch", 25000), P("Sivanna Electric Kettle 1.7L", 6000)]
COMPS = [P("Gabrini Deluxe Digital Fryer 5 Litre", 24000), P("Gabrini Kettle 1.8L Steel", 6500),
         P("Gabrini Air Fryer 2L Mini", 12000), P("Washing Machine 8kg", 90000)]


def fake_ai_factory(answer_fn):
    calls = []

    def ai(system, user, max_tokens):
        payload = json.loads(user.split("\n\n", 1)[1])
        calls.append(payload)
        return {"matches": [answer_fn(item) for item in payload]}

    ai.calls = calls
    return ai


def pick_by_name(item):
    want = {"Sivanna Air Fryer 5L Digital Touch": "Fryer 5 Litre", "Sivanna Electric Kettle 1.7L": "Kettle 1.8L"}
    target = want.get(item["product"])
    for c in item["candidates"]:
        if target and target in c["product"]:
            return {"u": item["u"], "c": c["id"], "confidence": 0.9, "reason": "same type and size"}
    return {"u": item["u"], "c": None, "confidence": 0}


def test_shortlist_keeps_name_disjoint_candidates():
    users, comps = [_norm(p) for p in USERS], [_norm(p) for p in COMPS]
    sl = _shortlist(users[0], comps, 3)
    assert 0 in sl  # "Digital Fryer 5 Litre" shares almost no words but must be offered


def test_ai_matches_like_for_like_and_shape():
    ai = fake_ai_factory(pick_by_name)
    out = ai_match_products(USERS, COMPS, ai=ai, use_cache=False)
    assert out["source"] == "ai"
    assert out["matchedProductCount"] == 2
    m = out["matches"][0]
    assert m["matchReasons"][0] == "ai"
    assert set(m) >= {"userProduct", "competitorProduct", "priceGap", "confidence", "matchTier"}
    assert out["competitorUnmatchedCount"] == 2


def test_ai_cannot_choose_outside_shortlist_or_below_threshold():
    ai = fake_ai_factory(lambda item: {"u": item["u"], "c": "c999", "confidence": 0.99})
    assert ai_match_products(USERS, COMPS, ai=ai, use_cache=False)["matchedProductCount"] == 0
    low = fake_ai_factory(lambda item: {"u": item["u"], "c": item["candidates"][0]["id"], "confidence": 0.3})
    assert ai_match_products(USERS, COMPS, ai=low, use_cache=False)["matchedProductCount"] == 0


def test_one_to_one_enforced():
    both_same = fake_ai_factory(lambda item: {"u": item["u"], "c": "c0", "confidence": 0.8 + 0.1 * item["u"]})
    out = ai_match_products(USERS, COMPS, ai=both_same, use_cache=False)
    assert out["matchedProductCount"] <= 1


def test_no_ai_means_no_fuzzy_fallback():
    from comparison_engine import ai_product_match as m
    orig = m._default_ai
    m._default_ai = lambda: None
    try:
        out = ai_match_products(USERS, COMPS, use_cache=False)
    finally:
        m._default_ai = orig
    assert out["source"] == "none" and out["matchedProductCount"] == 0
    assert len(out["userUnmatchedProducts"]) == 2


def test_cache_avoids_repeat_ai_calls():
    ai = fake_ai_factory(pick_by_name)
    ai_match_products(USERS, COMPS, ai=ai)
    n = len(ai.calls)
    ai_match_products(USERS, COMPS, ai=ai)
    assert len(ai.calls) == n


def test_pairs_api_fail_open():
    def boom(system, user, max_tokens):
        raise RuntimeError("provider down")
    res = ai_match_pairs([{"key": "k1", "userProducts": USERS, "competitorProducts": COMPS[:1] + [P("Other", 1)]}], ai=boom)
    assert res[0]["key"] == "k1"
    assert res[0]["productMatching"]["matchedProductCount"] == 0
