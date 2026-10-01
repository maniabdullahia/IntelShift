"""Tests for the onboarding store profile: Step 1 journey, Step 2 business type,
Step 3 market + English-only language, and the SSRF guard.

All network calls are stubbed — run from website_analyzer_app/:
    python -m pytest tests/test_store_profile.py -q
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from bs4 import BeautifulSoup

from level1_detector import site_validator as sv
from level1_detector.business_type import classify_business_type, lists_payload
from level1_detector.net_guard import is_public_url
from level1_detector.store_profile import (
    detect_language, localization_countries, resolve_market, shipping_scope_from_text,
)

ORIGIN = "https://brand.pk"

FILLER = " ".join(["Shop the new collection with free shipping on all orders for you and your family."] * 12)
NAV = "".join(f'<a href="/collections/c{i}">Category {i}</a>' for i in range(10))
HOME = f"""<html lang="en"><head>
<link rel="alternate" hreflang="en-pk" href="{ORIGIN}/">
<script type="application/ld+json">{{"@type":"Organization","address":{{"addressCountry":"PK"}}}}</script>
</head><body>
<form action="/search"><input type="search" name="q"></form>
<a href="/cart">Cart</a>{NAV}<p>{FILLER}</p>
<p>Call us +92 300 1234567</p>
</body></html>"""
COLLECTION = "<html><body>" + "".join(
    f'<a href="/products/p{i}">Lawn Suit {i}</a><span>Rs. 4,500</span>' for i in range(6)
) + "</body></html>"
PRODUCT = """<html><body><h1>Lawn Suit</h1>
<script type="application/ld+json">{"@type":"Product","offers":{"price":"4500","priceCurrency":"PKR"}}</script>
<button>Add to cart</button></body></html>"""
SHIPPING = "<html><body><h1>Shipping</h1><p>" + ("We currently only ship within Pakistan. Delivery takes 3-5 days. " * 10) + "</p></body></html>"


@pytest.fixture
def fake_site(monkeypatch):
    pages = {
        ORIGIN: HOME, ORIGIN + "/": HOME,
        **{f"{ORIGIN}/collections/c{i}": COLLECTION for i in range(10)},
        **{f"{ORIGIN}/products/p{i}": PRODUCT for i in range(6)},
    }

    def fake_fetch(url, force_render=False):
        return pages.get(url), url

    quick = {
        f"{ORIGIN}/search?q=new": (200, "<html>search results</html>"),
        f"{ORIGIN}/cart": (200, "<html>Your cart is empty</html>"),
        f"{ORIGIN}/checkout": (200, "<html>cart</html>"),
        f"{ORIGIN}/policies/shipping-policy": (200, SHIPPING),
    }

    def fake_quick(url, timeout=12):
        st, body = quick.get(url, (404, "not found"))
        final = f"{ORIGIN}/cart" if url.endswith("/checkout") else url
        return st, final, body

    def fake_json(url):
        if url.endswith("/products.json?limit=250"):
            return {"products": [{"title": f"Lawn Suit {i}", "vendor": "Brand", "product_type": "Lawn"} for i in range(20)]}
        if url.endswith("/meta.json"):
            return {"country": "PK", "currency": "PKR"}
        return None

    monkeypatch.setattr(sv, "_fetch", fake_fetch)
    monkeypatch.setattr(sv, "_quick_get", fake_quick)
    monkeypatch.setattr(sv, "_raw_json_get", fake_json)
    return quick


def test_validate_site_full_profile(fake_site):
    r = sv.validate_site(ORIGIN)
    assert r["ok"] is True
    assert r["currency"] == "PKR"
    assert r["accessStatus"] == "complete"
    st = r["stages"]
    assert st["search"]["status"] == "ok"
    assert st["cart"]["status"] == "ok"
    assert st["checkout"]["status"] == "ok"
    m = r["market"]
    assert m["country"] == "PK"
    assert m["scope"] == "domestic"
    assert m["shipsTo"] == ["PK"]
    assert r["language"]["isEnglish"] is True
    cs = r["catalogSample"]
    assert cs["source"] == "shopify" and cs["vendorCount"] == 1 and cs["titles"]
    assert r["signals"]["marketplaceMarker"] is None


def test_blocked_cart_marks_incomplete(fake_site):
    fake_site[f"{ORIGIN}/cart"] = (403, "Access denied")
    r = sv.validate_site(ORIGIN)
    assert r["ok"] is True  # still analysable…
    assert r["accessStatus"] == "incomplete"  # …but flagged
    assert "cart" in r["accessIssues"]


def test_non_english_store_is_rejected_early(monkeypatch):
    arabic = '<html lang="ar"><body>' + ("تسوق المجموعة الجديدة مع شحن مجاني على جميع الطلبات " * 30) + "".join(
        f'<a href="/c/{i}">{i}</a>' for i in range(10)) + "</body></html>"
    calls = []

    def fake_fetch(url, force_render=False):
        calls.append(url)
        return arabic, url

    monkeypatch.setattr(sv, "_fetch", fake_fetch)
    r = sv.validate_site("https://store.ae")
    assert r["ok"] is False
    assert r["unsupportedLanguage"] is True
    assert calls == ["https://store.ae"]  # no collection/product renders wasted


def test_listing_url_with_price_is_not_a_product():
    soup = BeautifulSoup("<html><body><span>Rs. 4,500</span></body></html>", "lxml")
    ok, _ = sv._is_product_page(soup, "https://x.com/product-category/lawn/")
    assert ok is False
    ok, _ = sv._is_product_page(soup, "https://x.com/products/lawn-suit")
    assert ok is True


@pytest.mark.parametrize("url,kw,expected", [
    ("https://www.amazon.co.uk", {}, 1),
    ("https://daraz.pk", {}, 1),
    ("https://www.nike.com", {}, 2),
    ("https://www.zara.com/pk", {}, 2),
    ("https://bigbrand.com", {"region_count": 40}, 2),
    ("https://bigbrand.com", {"region_count": 40, "total_products": 20000}, 2),
    ("https://midbrand.com", {"region_count": 40, "total_products": 800, "vendor_count": 1}, 5),  # Shopify Markets brand
    ("https://store.pk", {"vendor_count": 60, "industry_count": 5}, 3),
    ("https://bazaar.pk", {"marketplace_marker": "become a seller", "total_products": 900}, 3),
    ("https://beauty.pk", {"vendor_count": 45, "industry_count": 1}, 4),
    ("https://beauty.pk", {"brand_model": "multi_brand", "industry_count": 2}, 4),
    ("https://brand.com", {"vendor_count": 1}, 5),
    ("https://brand.com", {"html": "Also available on Amazon Marketplace"}, 5),
    ("https://target.pk", {}, 5),          # label match alone must not block
    ("https://jdsports.co.uk", {}, 5),
])
def test_business_types(url, kw, expected):
    assert classify_business_type(url, **kw)["businessType"] == expected


def test_enterprise_tiers_and_allowlist():
    assert classify_business_type("https://nike.com")["scaleTier"] == "enterprise"
    assert classify_business_type("https://nike.com", config={"allowlist": ["nike"]})["scaleTier"] == "self_serve"
    lists = lists_payload()
    assert "amazon" in lists["marketplaces"] and "nike" in lists["multinationalBrands"]


def test_shipping_scope_phrases():
    assert shipping_scope_from_text("We ship worldwide to over 100 countries.")[0] == "worldwide"
    assert shipping_scope_from_text("We do not ship internationally.")[0] == "domestic"
    assert shipping_scope_from_text("We ship to the following countries: UK, France")[0] == "selected"
    assert shipping_scope_from_text("Returns within 30 days")[0] is None


def test_language_detection():
    de = BeautifulSoup('<html lang="de"><body>' + "Entdecken Sie unsere neue Kollektion mit kostenlosem Versand " * 10 + "</body></html>", "lxml")
    assert detect_language(de, de.get_text(" "))["isEnglish"] is False
    mislabelled = BeautifulSoup('<html lang="fr"><body>' + FILLER + "</body></html>", "lxml")
    assert detect_language(mislabelled, mislabelled.get_text(" "))["isEnglish"] is True


def test_market_from_country_selector():
    soup = BeautifulSoup('<form action="/localization"><select name="country_code">'
                         '<option value="PK"></option><option value="AE"></option><option value="GB"></option>'
                         '</select></form>', "lxml")
    m = resolve_market(url="https://brand.co", currency="PKR", localization=localization_countries(soup))
    assert m["country"] == "PK"  # .co is a vanity TLD, currency decides
    assert m["scope"] == "selected" and set(m["shipsTo"]) == {"PK", "AE", "GB"}


@pytest.mark.parametrize("url,ok", [
    ("http://127.0.0.1:8000/docs", False),
    ("http://169.254.169.254/latest/meta-data", False),
    ("http://[::ffff:10.0.0.1]/", False),
    ("http://localhost:27017", False),
    ("file:///etc/passwd", False),
    ("http://user:pw@shop.com", False),
    ("http://93.184.216.34/", True),
])
def test_ssrf_guard(url, ok):
    assert is_public_url(url) is ok
