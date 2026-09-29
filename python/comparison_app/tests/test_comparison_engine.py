"""Unit tests for comparison_engine v5 (vertical-agnostic matching).

Run from comparison_app/:
    python -m pytest tests/ -q   (or python tests/test_comparison_engine.py)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from comparison_engine.matching import (
    detect_brand_tokens,
    infer_category_label,
    infer_product_type,
    match_collections,
    match_products,
    price_closeness,
    relative_price_band,
    stem,
)
from comparison_engine.comparator import compare_sites


def P(name, price=None, cur="PKR", desc=None, category=None):
    return {"name": name, "priceValue": price, "currency": cur,
            "descriptionText": desc, "category": category, "sourcePages": []}


def test_stemming():
    assert stem("mascaras") == "mascara"
    assert stem("dresses") == "dress"
    assert stem("lips") == "lip"
    assert stem("dress") == "dress"


def test_category_inference_across_verticals():
    cases = {
        "Air Fryer 5L Digital": "kitchen_appliances",
        "Treadmill X200 Pro": "fitness_equipment",
        "Men Slim Fit Jeans": "bottoms",
        "Gaming Laptop RTX 4060": "computers",
        "Matte Lipstick Crayon": "lip_color",
        "Waterproof Mascara Long Lash": "mascara",
        "Leather Jacket Classic": "outerwear",
        "Bed Sheet King Size Cotton": "bedding_bath",
    }
    for name, expected in cases.items():
        assert infer_product_type({"name": name}) == expected, name


def test_cross_category_products_never_match():
    # Same marketing adjectives, different product types -> no match.
    r = match_products(
        [P("Waterproof Matte Blusher Professional Long Lasting", 2000)],
        [P("Waterproof Matte Lipstick Professional Long Lasting", 2000)],
    )
    assert r["matchedProductCount"] == 0


def test_same_category_products_match_across_brands():
    r = match_products(
        [P("Sivanna Air Fryer 5L Digital Touch", 25000)],
        [P("Gabrini Deluxe Digital Air Fryer 5L", 24000)],
    )
    assert r["matchedProductCount"] == 1
    reasons = r["matches"][0]["matchReasons"]
    assert any("same_product_type" in x for x in reasons)
    assert any("shared_attributes" in x for x in reasons)


def test_brand_tokens_detected_dynamically_but_not_category_words():
    products = [P(f"Gabrini Mascara Style {i}") for i in range(6)]
    brand = detect_brand_tokens(products)
    assert "gabrini" in brand
    assert "mascara" not in brand  # taxonomy word, never a brand token


def test_price_closeness_requires_same_currency():
    assert price_closeness(100, 105, True) > 0.8
    assert price_closeness(100, 105, False) == 0.0
    assert price_closeness(100, 400, True) == 0.0  # >3x apart


def test_relative_price_band_is_distribution_based():
    ref = [100, 200, 300, 400, 500, 600, 700, 800]
    assert relative_price_band(100, ref) == "entry"
    assert relative_price_band(800, ref) == "premium"
    # Same function works for any currency scale.
    ref_pkr = [x * 300 for x in ref]
    assert relative_price_band(240000, ref_pkr) == "premium"


def test_collection_matching_plural_and_synonyms():
    user = {"collections": [{"url": "https://a.com/collections/smudge-proof-mascara", "title": "Mascara Collection"}]}
    comp = {"collections": [{"url": "https://b.com/collections/mascaras", "title": "Mascaras"}]}
    matches = match_collections(user, comp)
    assert len(matches) == 1
    assert matches[0]["category"] == "mascara"


def test_collection_matching_rejects_different_categories():
    user = {"collections": [{"url": "https://a.com/collections/lipsticks", "title": "Lipsticks"}]}
    comp = {"collections": [{"url": "https://b.com/collections/washing-machines", "title": "Washing Machines"}]}
    assert match_collections(user, comp) == []


def make_snapshot(domain, products, site_type="ecommerce"):
    return {
        "schemaVersion": "site_snapshot_v2",
        "site": {"domain": domain, "platform": "Shopify", "siteType": site_type,
                 "siteName": domain, "categoriesDetected": [], "vendorsDetected": []},
        "pagesAnalyzed": [{
            "url": f"https://{domain}/", "pageType": "homepage", "platform": "Shopify",
            "seo": {"title": domain, "metaDescription": "x", "h1": domain},
            "content": {}, "ecommerce": {}, "products": [],
        }],
        "products": products,
    }


def snap_product(name, current, compare_at=None, cur="PKR"):
    price = {"currency": cur, "current": current, "priceTextRaw": str(current)}
    if compare_at:
        price["compareAt"] = compare_at
        price["isOnSale"] = compare_at > current
        price["discountPercent"] = round((compare_at - current) / compare_at * 100, 1)
    return {"name": name, "productUrl": f"https://x/{name.replace(' ', '-')}", "price": price}


def test_compare_sites_end_to_end_new_modules():
    user = make_snapshot("user.pk", [
        snap_product("Air Fryer 5L", 25000),
        snap_product("Electric Kettle 1.7L", 6000),
    ])
    comp = make_snapshot("comp.pk", [
        snap_product("Digital Air Fryer 5L", 22000, compare_at=27000),
        snap_product("Washing Machine 8kg", 90000),
    ])
    result = compare_sites(user, [comp])
    assert result["schemaVersion"] == "comparison_engine_v5"
    assert result["summary"]["userSiteType"] == "ecommerce"

    cc = result["categoryCoverageComparison"]
    assert "large_appliances" in cc["userGapCategories"]  # washing machine gap

    sd = result["saleAndDiscountComparison"]["rows"]
    comp_row = next(r for r in sd if r["domain"] == "comp.pk")
    assert comp_row["onSaleCount"] == 1

    assert result["priceComparison"]["sameCurrency"] is True

    oto = result["oneToOneComparison"]["competitors"][0]
    assert oto["catalogWideProductMatching"]["matchedProductCount"] == 1  # air fryer pair only


def test_compare_sites_currency_guard():
    user = make_snapshot("user.com", [snap_product("Air Fryer 5L", 100, cur="USD")])
    comp = make_snapshot("comp.pk", [snap_product("Air Fryer 5L", 25000, cur="PKR")])
    result = compare_sites(user, [comp])
    assert result["priceComparison"]["sameCurrency"] is False
    assert result["priceComparison"]["currencyWarning"]


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
