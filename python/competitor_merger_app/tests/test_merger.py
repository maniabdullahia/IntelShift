"""Unit tests for the site snapshot merger (site_snapshot_v2).

Run from competitor_merger_app/:
    python -m pytest tests/ -q
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.merger import (  # noqa: E402
    clean_category,
    merge_page_jsons,
    normalize_price,
    normalize_url,
)


def make_page(url, page_type, products=None, **extra):
    page = {
        "page": {"url": url, "pageType": page_type},
        "platform": "Shopify",
        "seo": {"title": f"Title of {url}"},
        "success": True,
        "analysisReady": True,
        "products": products or [],
    }
    page.update(extra)
    return page


# ---- price ----------------------------------------------------------------

def test_price_from_dict():
    price = normalize_price({"currency": "PKR", "current": 1890, "compareAt": 2100})
    assert price["current"] == 1890
    assert price["compareAt"] == 2100
    assert price["isOnSale"] is True
    assert price["discountPercent"] == 10.0


def test_price_from_legacy_homepage_fields():
    price = normalize_price(None, fallback={"currentPrice": 565, "comparePrice": 595, "currency": "PKR"})
    assert price["current"] == 565
    assert price["compareAt"] == 595
    assert price["currency"] == "PKR"
    assert price["isOnSale"] is True


def test_price_from_raw_text():
    price = normalize_price("Rs. 1,250")
    assert price["current"] == 1250
    assert price["currency"] == "PKR"


# ---- url / category ---------------------------------------------------------

def test_normalize_url_strips_www_only_prefix():
    assert normalize_url("https://www.example.com/a/") == "https://example.com/a"
    assert normalize_url("https://shop.wwwx.com/") == "https://shop.wwwx.com/"


def test_clean_category():
    assert clean_category("matte-lipstick") == "Matte Lipstick"
    assert clean_category("Face Wash") == "Face Wash"
    assert clean_category("x" * 100) is None  # page titles are not categories


# ---- merging ----------------------------------------------------------------

def test_homepage_card_products_keep_price_and_get_clean_schema():
    home = make_page("https://shop.pk/", "homepage", products=[{
        "title": "Serum", "url": "https://shop.pk/products/serum",
        "image": "https://cdn.shop.pk/serum.jpg",
        "currentPrice": 565, "comparePrice": 595, "currency": "PKR",
        "handle": "serum",
    }])
    snap = merge_page_jsons([home])
    product = snap["products"][0]
    assert product["name"] == "Serum"
    assert product["productUrl"] == "https://shop.pk/products/serum"
    assert product["price"]["current"] == 565
    assert product["price"]["isOnSale"] is True
    for legacy_key in ("title", "url", "image", "currentPrice", "comparePrice"):
        assert legacy_key not in product
    assert snap["site"]["productsWithPrice"] == 1


def test_products_deduped_across_pages_product_page_wins():
    collection = make_page("https://shop.pk/collections/face", "collection", products=[{
        "rank": 1, "name": "Serum", "handle": "serum",
        "productUrl": "https://shop.pk/products/serum",
        "price": {"currency": "PKR", "current": 565},
    }])
    product_page = make_page("https://shop.pk/products/serum", "product", products=[{
        "rank": 1, "name": "Serum", "handle": "serum",
        "productUrl": "https://shop.pk/products/serum",
        "price": {"currency": "PKR", "current": 565, "compareAt": 700},
        "description": {"html": "<p>Rich <b>description</b></p>"},
        "variants": [{"id": 1, "title": "30ml"}],
    }])
    snap = merge_page_jsons([collection, product_page])
    assert len(snap["products"]) == 1
    product = snap["products"][0]
    assert product["description"]["text"] == "Rich description"
    assert product["price"]["compareAt"] == 700
    assert len(product["sourcePages"]) == 2


def test_internal_keys_and_html_are_stripped():
    page = make_page(
        "https://shop.pk/products/serum", "product",
        products=[{"name": "Serum", "productUrl": "https://shop.pk/products/serum"}],
        _html="<html>huge</html>",
        _raw_product={"secret": True},
        technical={"finalUrl": "https://shop.pk/products/serum", "responseHeaders": {"x": "y"}},
    )
    snap = merge_page_jsons([page])
    import json
    raw = json.dumps(snap)
    assert "_html" not in raw
    assert "_raw_product" not in raw
    assert "responseHeaders" not in raw
    assert snap["pagesAnalyzed"][0]["technical"]["finalUrl"]


def test_mixed_domain_warning():
    snap = merge_page_jsons([
        make_page("https://a.com/", "homepage"),
        make_page("https://b.com/", "homepage"),
    ])
    assert any("multiple domains" in w for w in snap["quality"]["warnings"])


def test_non_ecommerce_site_has_no_catalog():
    snap = merge_page_jsons([
        make_page("https://biz.com/", "homepage"),
        make_page("https://biz.com/blog/post-1", "blog"),
    ])
    assert "catalog" not in snap["site"]
    assert snap["site"]["totalUniqueProducts"] == 0
    assert snap["quality"]["coverage"]["blogPages"] == 1



def test_blocked_contract_propagates():
    blocked = {"status": "website_blocked", "success": False, "blocked": True,
               "blockedReason": "bot_protection", "userMessage": "This website blocks automated analysis.",
               "page": {"url": "https://blocked.com/", "pageType": "blocked"},
               "crawl": {"success": False, "crawlBlocked": True}, "products": []}
    ok = make_page("https://blocked.com/shop", "collection", products=[{
        "name": "P", "productUrl": "https://blocked.com/products/p",
        "price": {"current": 5, "currency": "USD"},
    }])

    all_blocked = merge_page_jsons([blocked])
    assert all_blocked["status"] == "website_blocked"
    assert all_blocked["userMessage"]
    assert all_blocked["pagesAnalyzed"][0]["blockedReason"] == "bot_protection"

    partial = merge_page_jsons([blocked, ok])
    assert partial["status"] == "partial_blocked"
    assert partial["quality"]["coverage"]["blockedPages"] == ["https://blocked.com/"]
    assert partial["site"]["totalUniqueProducts"] == 1

    clean = merge_page_jsons([ok])
    assert "status" not in clean


def test_www_variants_normalized_to_same_domain():
    from app.merger import domain_from_url
    assert domain_from_url("https://www2.hm.com/en_us/x.html") == "hm.com"
    assert domain_from_url("https://www.hm.com/") == "hm.com"

def test_summary_features_metrics_preserved():
    home = make_page(
        "https://shop.pk/", "homepage",
        homepage={"siteName": "Shop PK", "positioning": ["Best"], "businessClassification": {"homepageType": "beauty"}},
        features={"hasHero": True},
        metrics={"sectionCount": 5},
    )
    snap = merge_page_jsons([home])
    page = snap["pagesAnalyzed"][0]
    assert page["summary"]["siteName"] == "Shop PK"
    assert page["features"]["hasHero"] is True
    assert page["metrics"]["sectionCount"] == 5
    assert snap["site"]["siteName"] == "Shop PK"
    assert snap["site"]["businessCategory"] == "beauty"
