"""Unit tests for the change detection engine.

Run from change_detection_app/:
    python tests/test_detector.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.detector import detect_changes


def snap(products=None, collections=None, pages=None, site_extra=None):
    site = {"domain": "shop.pk", "platform": "Shopify", "siteType": "ecommerce",
            "collections": collections or [], "catalog": {}, "navigation": {}}
    site.update(site_extra or {})
    return {
        "schemaVersion": "site_snapshot_v2",
        "generatedAt": "2026-07-01T00:00:00",
        "site": site,
        "pagesAnalyzed": pages or [],
        "products": products or [],
    }


def prod(name, price=None, url=None, on_sale=False, in_stock=None, rank=None, compare_at=None):
    p = {"name": name, "productUrl": url or f"https://shop.pk/products/{name.lower().replace(' ', '-')}"}
    if price is not None:
        p["price"] = {"current": price, "currency": "PKR", "isOnSale": on_sale}
        if compare_at:
            p["price"]["compareAt"] = compare_at
            p["price"]["discountPercent"] = round((compare_at - price) / compare_at * 100, 1)
    if in_stock is not None:
        p["availability"] = {"inStock": in_stock}
    if rank is not None:
        p["sourcePages"] = [{"url": "https://shop.pk/collections/all", "rank": rank}]
    return p


def types(result):
    return [c["type"] for c in result["changes"]]


def test_no_changes():
    a = snap(products=[prod("Serum", 1000)])
    r = detect_changes(a, snap(products=[prod("Serum", 1000)]))
    assert r["summary"]["totalChanges"] == 0
    assert r["shouldSendToAI"] is False
    assert r["changeScore"] == 0


def test_price_change_detected_with_threshold():
    r = detect_changes(
        snap(products=[prod("Serum", 1000)]),
        snap(products=[prod("Serum", 1200)]),
    )
    assert "price_change" in types(r)
    c = next(c for c in r["changes"] if c["type"] == "price_change")
    assert c["changePercent"] == 20.0 and c["severity"] == "high"
    # below threshold -> ignored
    r2 = detect_changes(snap(products=[prod("Serum", 1000)]), snap(products=[prod("Serum", 1020)]))
    assert "price_change" not in types(r2)


def test_new_and_removed_products():
    r = detect_changes(
        snap(products=[prod("Serum", 1000), prod("Toner", 800)]),
        snap(products=[prod("Serum", 1000), prod("Face Wash", 500)]),
    )
    assert "new_product" in types(r) and "removed_product" in types(r)


def test_sale_and_stock_changes():
    r = detect_changes(
        snap(products=[prod("Serum", 1000, in_stock=True)]),
        snap(products=[prod("Serum", 800, on_sale=True, compare_at=1000, in_stock=False)]),
    )
    t = types(r)
    assert "sale_started" in t and "out_of_stock" in t and "price_change" in t


def test_rank_change():
    r = detect_changes(
        snap(products=[prod("Serum", 1000, rank=12)]),
        snap(products=[prod("Serum", 1000, rank=2)]),
    )
    c = next(c for c in r["changes"] if c["type"] == "rank_change")
    assert c["positionsMoved"] == 10 and c["severity"] == "high"


def test_pricing_plan_changes():
    def page(plans):
        return {"pageType": "general", "url": "https://x.com/pricing",
                "pricing": {"hasPricing": True, "plans": plans}}
    old = snap(pages=[page([{"name": "Pro", "price": {"amount": 100}}])])
    new = snap(pages=[page([
        {"name": "Pro", "price": {"amount": 150}},
        {"name": "Enterprise", "price": {"amount": 500}},
    ])])
    r = detect_changes(old, new)
    t = types(r)
    assert "plan_price_change" in t and "pricing_plan_added" in t
    assert r["overallSeverity"] in ("high", "critical")
    assert r["shouldSendToAI"] is True


def test_collection_and_navigation_changes():
    old = snap(
        collections=[{"url": "https://shop.pk/collections/lips", "name": "Lips", "productCount": 10, "priceRange": {"min": 500}}],
        site_extra={"navigation": {"topLabels": ["Lips", "Eyes"]}},
    )
    new = snap(
        collections=[{"url": "https://shop.pk/collections/lips", "name": "Lips", "productCount": 18, "priceRange": {"min": 400}}],
        site_extra={"navigation": {"topLabels": ["Lips", "Eyes", "Skincare"]}},
    )
    r = detect_changes(old, new)
    t = types(r)
    assert "collection_size_change" in t and "collection_price_floor_change" in t and "navigation_change" in t


def test_hero_change():
    def hp(headline):
        return {"pageType": "homepage", "url": "https://shop.pk/",
                "homepageStrategy": {"hero": {"headline": headline}}, "features": {}}
    r = detect_changes(
        snap(pages=[hp("Best makeup in Pakistan")]),
        snap(pages=[hp("Flat 50% off everything - summer sale")]),
    )
    assert "hero_message_change" in types(r)


def test_domain_mismatch_warning():
    a = snap(); a["site"]["domain"] = "a.com"
    b = snap(); b["site"]["domain"] = "b.com"
    r = detect_changes(a, b)
    assert r["warnings"]


def test_low_changes_can_be_ignored():
    old = snap(products=[prod("Serum", 1000)])
    new = snap(products=[prod("Serum", 1000)])
    new["products"][0]["variants"] = [{"id": 1}, {"id": 2}]
    old["products"][0]["variants"] = [{"id": 1}]
    r = detect_changes(old, new, {"ignoreLowChanges": True})
    assert "variant_count_change" not in types(r)


def test_extraction_instability_dampens_add_remove():
    def snap_with_crawl(products, blocked):
        s = snap(products=products, pages=[{
            "url": "https://shop.pk/collections/all", "pageType": "collection",
            "crawl": {"crawlBlocked": blocked},
            "source": {"extractor": "jina" if blocked else "dom"},
        }])
        return s
    old = snap_with_crawl([prod(f"P{i}", 100) for i in range(10)], blocked=False)
    new = snap_with_crawl([prod(f"P{i}", 100) for i in range(5)], blocked=True)
    r = detect_changes(old, new)
    assert r["extractionStable"] is False
    assert r["warnings"]
    removed = [c for c in r["changes"] if c["type"] == "removed_product"]
    assert removed and all(c["severity"] == "low" and c.get("unreliable") for c in removed)
    assert r["shouldSendToAI"] is False


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
