"""Structured-data recovery for custom / JS storefronts (Unknown analyzer)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bs4 import BeautifulSoup

from analyzers.unknown.structured_products import (
    jsonld_products, merge_structured_into, structured_collection_products,
)
from analyzers.unknown.collection import is_valid_product

BASE = "https://shop.example.com/collections/lipsticks"

ITEMLIST = {
    "@context": "https://schema.org", "@type": "ItemList",
    "itemListElement": [
        {"@type": "ListItem", "position": 1, "item": {
            "@type": "Product", "name": "Velvet Matte Lipstick", "url": "/products/velvet-matte",
            "image": "/img/1.jpg", "offers": {"@type": "Offer", "price": "1450", "priceCurrency": "PKR"}}},
        {"@type": "ListItem", "position": 2, "item": {
            "@type": "Product", "name": "Gloss Bomb", "url": "https://shop.example.com/products/gloss-bomb",
            "offers": {"@type": "AggregateOffer", "lowPrice": 19.5, "priceCurrency": "USD"}}},
    ],
}


def test_jsonld_itemlist_products_with_prices():
    soup = BeautifulSoup(f'<script type="application/ld+json">{json.dumps(ITEMLIST)}</script>', "lxml")
    out = jsonld_products(soup, BASE)
    assert {p["title"] for p in out} == {"Velvet Matte Lipstick", "Gloss Bomb"}
    by = {p["title"]: p for p in out}
    assert by["Velvet Matte Lipstick"]["url"] == "https://shop.example.com/products/velvet-matte"
    assert by["Velvet Matte Lipstick"]["price"] == "1,450 PKR"
    assert by["Gloss Bomb"]["price"] == "$19.5"


def test_next_data_hydration_products():
    next_data = {"props": {"pageProps": {"products": [
        {"name": "Cloud Runner", "url": "/products/cloud-runner", "price": "$120", "image": "/a.jpg"},
        {"name": "Trail Runner", "url": "/products/trail-runner", "price": "$140", "image": "/b.jpg"},
    ]}}}
    html = f'<html><body><script id="__NEXT_DATA__" type="application/json">{json.dumps(next_data)}</script></body></html>'
    sd = structured_collection_products(html, BeautifulSoup(html, "lxml"), BASE)
    assert sd["counts"]["hydration"] >= 2
    assert {p["title"] for p in sd["products"]} >= {"Cloud Runner", "Trail Runner"}


def test_merge_fills_missing_dom_prices_and_adds_missing_products():
    dom = [{"title": "Velvet Matte Lipstick", "url": "https://shop.example.com/products/velvet-matte/",
            "image": None, "price": "unfetched", "allPrices": "unfetched"}]
    soup = BeautifulSoup(f'<script type="application/ld+json">{json.dumps(ITEMLIST)}</script>', "lxml")
    res = merge_structured_into(dom, jsonld_products(soup, BASE), is_valid_product)
    assert res == {"filled": 1, "added": 1}
    assert dom[0]["price"] == "1,450 PKR" and dom[0]["image"].endswith("/img/1.jpg")
    assert dom[1]["title"] == "Gloss Bomb"


def test_unknown_collection_uses_structured_data_end_to_end():
    from analyzers.unknown.unknown_analyzer import UnknownAnalyzer
    html = ("<html><head><title>Lipsticks</title></head><body><h1>Lipsticks</h1>"
            f'<script type="application/ld+json">{json.dumps(ITEMLIST)}</script>'
            '<div id="root"></div></body></html>')
    res = UnknownAnalyzer().analyze(url=BASE, html=html, headers={"status_code": 200},
                                    page_type="collection", level1={"platform": "Unknown"})
    names = {(p.get("title") or p.get("name")) for p in res.get("products") or []}
    assert {"Velvet Matte Lipstick", "Gloss Bomb"} <= names
    assert res["source"]["structuredData"]["jsonld"] == 2
