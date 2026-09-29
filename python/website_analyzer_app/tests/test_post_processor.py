"""Offline regression tests for the competitive-schema post-processor.

Run from website_analyzer_app/:
    python tests/test_post_processor.py
No network needed.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from post_processors.competitive_schema import _enrich_collection_result


def make_result(**over):
    base = {
        "page": {"url": "https://shop.pk/collections/matte-lipstick", "pageType": "collection"},
        "seo": {}, "openGraph": {}, "content": {}, "products": [],
    }
    base.update(over)
    return base


def test_brand_h1_does_not_become_collection_name():
    r = make_result(
        seo={"h1": "Sivanna Colors"},
        openGraph={"site_name": "Sivanna Colors", "title": "Lips"},
        content={"collectionName": "Sivanna Colors"},
    )
    out = _enrich_collection_result(r)
    # Any non-brand name is acceptable; slug-matching "Matte Lipstick" preferred.
    assert out["content"]["collectionName"] in ("Matte Lipstick", "Lips")
    assert out["collectionSummary"]["name"] in ("Matte Lipstick", "Lips")


def test_rich_collection_summary_preserved():
    r = make_result(
        seo={"h1": "Matte Lipsticks"},
        collectionSummary={"name": "Matte Lipsticks", "category": "lipstick",
                           "dominantProductTypes": ["Lipstick"], "topBrands": ["X"],
                           "inStockCount": 5, "outOfStockCount": 5, "availabilityRatio": 0.5},
        products=[{"title": "A", "price": {"current": 975, "currency": "PKR"}}],
    )
    out = _enrich_collection_result(r)
    cs = out["collectionSummary"]
    for key in ("category", "dominantProductTypes", "topBrands", "inStockCount",
                "outOfStockCount", "availabilityRatio"):
        assert key in cs, f"post-processor dropped {key}"
    assert cs["name"] == "Matte Lipsticks"


def test_no_fake_usd_currency():
    r = make_result(
        seo={"h1": "Face Wash"},
        products=[{"title": "P1", "price": {"current": 500}}],  # no currency info
    )
    out = _enrich_collection_result(r)
    pr = out["ecommerce"]["productStats"]["priceRange"]
    assert "currency" not in pr, f"invented currency: {pr}"


def test_detected_currency_kept():
    r = make_result(products=[{"title": "P1", "price": {"current": 500, "currency": "PKR"}}])
    out = _enrich_collection_result(r)
    assert out["ecommerce"]["productStats"]["priceRange"]["currency"] == "PKR"


def test_all_brand_falls_back_to_url_handle():
    r = make_result(
        page={"url": "https://brand.com/collections/red-lipsticks", "pageType": "collection"},
        seo={"h1": "Brand Store"},
        openGraph={"site_name": "Brand Store", "title": "Brand Store"},
    )
    out = _enrich_collection_result(r)
    assert out["content"]["collectionName"] == "Red Lipsticks"


def test_good_existing_name_never_overwritten():
    r = make_result(
        seo={"h1": "Brand Store"},
        openGraph={"site_name": "Brand Store", "title": "Something Else"},
        content={"collectionName": "Waterproof Mascaras"},
    )
    out = _enrich_collection_result(r)
    assert out["content"]["collectionName"] == "Waterproof Mascaras"


def test_non_collection_pages_untouched():
    r = make_result(page={"url": "https://x.com/", "pageType": "homepage"})
    out = _enrich_collection_result(r)
    assert "collectionSummary" not in out


def test_string_prices_coerced_and_partial_flagged():
    r = make_result(
        products=(
            [{"title": f"P{i}", "price": "38"} for i in range(3)]
            + [{"title": f"Q{i}", "price": {"currency": None, "current": None}} for i in range(7)]
        ),
    )
    out = _enrich_collection_result(r)
    coerced = [p for p in out["products"] if isinstance(p.get("price"), dict) and p["price"].get("current") is not None]
    assert len(coerced) == 3
    assert coerced[0]["price"]["current"] == 38
    flags = (out.get("collectionSummary") or {}).get("consistencyFlags") or []
    assert "collection_prices_partial" in flags


def test_zero_prices_flagged_missing():
    r = make_result(products=[{"title": f"P{i}", "price": {"current": None}} for i in range(5)])
    out = _enrich_collection_result(r)
    flags = (out.get("collectionSummary") or {}).get("consistencyFlags") or []
    assert "collection_prices_missing" in flags


def test_detected_platform_promoted_over_unknown():
    from post_processors.competitive_schema import normalize_for_competitive_analysis
    r = {
        "page": {"url": "https://x.com/", "pageType": "homepage"},
        "platform": "Unknown",
        "level1": {"platform": "HubSpot CMS", "platformConfidence": 0.78},
        "seo": {}, "content": {}, "products": [],
    }
    out = normalize_for_competitive_analysis(r)
    assert out["platform"] == "HubSpot CMS"


if __name__ == "__main__":
    import traceback
    mod = sys.modules[__name__]
    fns = [getattr(mod, n) for n in dir(mod) if n.startswith("test_")]
    passed = failed = 0
    for fn in fns:
        try:
            fn(); passed += 1; print("PASS", fn.__name__)
        except Exception:
            failed += 1; print("FAIL", fn.__name__); traceback.print_exc()
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
