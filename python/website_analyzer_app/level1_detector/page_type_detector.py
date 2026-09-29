from bs4 import BeautifulSoup
import json
import re
from urllib.parse import urlparse


def clean_text(text):
    return re.sub(r"\s+", " ", text or "").strip()


def safe_lower(value):
    return (value or "").lower()


def get_path_only(url):
    try:
        parsed = urlparse(url or "")
        path = parsed.path or "/"
        return path.lower().split("?")[0].split("#")[0]
    except Exception:
        url_lower = safe_lower(url)
        path = url_lower.split("//")[-1].split("/", 1)
        path_only = "/" + path[1] if len(path) > 1 else "/"
        return path_only.split("?")[0].split("#")[0]


def normalize_platform(platform):
    return safe_lower(platform).replace("_", " ").replace("-", " ")


def is_homepage_path(url):
    path = get_path_only(url).strip("/").lower()

    if path == "":
        return True

    parts = [p for p in path.split("/") if p]

    def _locale_like(seg):
        # en, us, en-us, eu_en, au_en, us-en …
        return bool(re.match(r"^[a-z]{2}([-_][a-z]{2})?$", seg))

    if len(parts) == 1 and _locale_like(parts[0]):
        return True

    # Two-segment locale roots: /eg/en/ (Lenovo), /us/en/ (Coca-Cola, Nespresso)
    if len(parts) == 2 and _locale_like(parts[0]) and _locale_like(parts[1]):
        return True

    # Locale + explicit home document: /us-en/home.html (HP)
    if len(parts) == 2 and _locale_like(parts[0]) and parts[1] in (
        "home.html", "home", "index.html", "index", "homepage"
    ):
        return True

    return False


def flatten_json_ld_items(item):
    output = []

    if isinstance(item, list):
        for child in item:
            output.extend(flatten_json_ld_items(child))

    elif isinstance(item, dict):
        output.append(item)

        graph = item.get("@graph")
        if isinstance(graph, list):
            for child in graph:
                output.extend(flatten_json_ld_items(child))

    return output


def has_jsonld_type(soup, target_type):
    target_type = target_type.lower()

    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            raw = script.string or script.get_text()
            if not raw:
                continue

            parsed = json.loads(raw)
            flattened = flatten_json_ld_items(parsed)

            for item in flattened:
                item_type = item.get("@type")

                if isinstance(item_type, list):
                    item_types = [str(t).lower() for t in item_type]
                else:
                    item_types = [str(item_type).lower()] if item_type else []

                if target_type in item_types:
                    return True

        except Exception:
            continue

    return False


def get_meta_content(soup, attr_type, attr_value):
    tag = soup.find("meta", attrs={attr_type: attr_value})
    if tag:
        return clean_text(tag.get("content"))
    return None


def extract_seo_text(soup):
    title = soup.title.string if soup.title and soup.title.string else ""

    meta_description = ""
    meta = soup.find("meta", attrs={"name": "description"})
    if meta:
        meta_description = meta.get("content") or ""

    h1 = ""
    h1_tag = soup.find("h1")
    if h1_tag:
        h1 = h1_tag.get_text(" ", strip=True)

    return clean_text(f"{title} {meta_description} {h1}").lower()


def is_nike_style_product_url(url):
    path = get_path_only(url)

    return bool(re.search(r"/t/[^/]+/[a-z0-9-]+$", path, re.I))


def detect_cart_checkout(url):
    path = get_path_only(url)
    return any(x in path for x in ["/cart", "/checkout", "/basket"])


def get_main_content_soup(soup):
    main_container = (
        soup.find("main")
        or soup.find(attrs={"role": "main"})
        or soup.select_one("#MainContent")
        or soup.select_one("#main-content")
        or soup.select_one(".main-content")
        or soup.select_one(".page-content")
        or soup.select_one(".content")
        or soup.body
        or soup
    )

    scoped = BeautifulSoup(str(main_container), "lxml")

    for tag in scoped.select(
        "header, nav, footer, "
        ".header, .site-header, .main-header, "
        ".footer, .site-footer, .main-footer, "
        ".menu, .navigation, .navbar, .nav, "
        ".mega-menu, .megamenu, .drawer, .mobile-menu, "
        ".announcement-bar, .breadcrumb, .breadcrumbs, "
        ".account, .login, .newsletter, .modal, .popup"
    ):
        tag.decompose()

    return scoped


def count_product_links_scoped(scoped_soup):
    product_links = scoped_soup.select(
        "a[href*='/product/'], "
        "a[href*='/products/'], "
        "a[href*='/product-page/'], "
        "a[href*='/item/'], "
        "a[href*='/pd/'], "
        "a[href*='/p/'], "
        "a[href*='/t/']"
    )

    bad_terms = [
        "/cart", "/checkout", "/basket", "mailto:", "tel:",
        "/help", "/support", "/blog/", "/blogs/",
        "/article/", "/articles/", "/news/", "/guide/",
        "/shipping", "/returns", "/privacy", "/terms",
        "/account", "/login", "/register"
    ]

    unique_links = set()

    for a in product_links:
        href = safe_lower(a.get("href"))

        if not href:
            continue

        if any(x in href for x in bad_terms):
            continue

        clean_href = href.split("?")[0].split("#")[0].rstrip("/")

        if clean_href:
            unique_links.add(clean_href)

    return len(unique_links)


def count_category_like_links_scoped(scoped_soup):
    terms = [
        "/collections/", "/collection/", "/product-category/",
        "/category/", "/categories/", "/shop/", "/store/",
        "/catalog/", "/c/", "/men", "/women", "/kids",
        "/sale", "/new-arrivals", "/best-sellers",
        "/clothing", "/shoes", "/accessories", "/bags",
        "/beauty", "/skincare", "/makeup", "/hair",
        "/fragrance", "/electronics", "/speakers", "/headphones"
    ]

    unique_links = set()

    for a in scoped_soup.find_all("a", href=True):
        href = safe_lower(a.get("href")).split("?")[0].split("#")[0].rstrip("/")

        if any(term in href for term in terms):
            unique_links.add(href)

    return len(unique_links)


def has_product_grid_dom_scoped(scoped_soup):
    return bool(
        scoped_soup.select_one(
            ".products, ul.products, .woocommerce-products, "
            ".product-grid, .product-list, .collection-grid, .collection-list, "
            ".grid-product, .product-card, .product-tile, .product-item, "
            "[class*='product-card'], [class*='product-grid'], "
            "[class*='product-tile'], [class*='product-item'], "
            "[data-hook*='product-list'], [data-hook*='product-grid'], "
            "[data-testid*='product'], [data-product-id]"
        )
    )


def detect_blog_signals(url, soup):
    url_lower = safe_lower(url)
    path = get_path_only(url)
    score = 0
    signals = []

    blog_url_terms = [
        "/blog/", "/blogs/", "/post/", "/posts/",
        "/article/", "/articles/", "/news/",
        "/insights/", "/resources/"
    ]

    blog_listing_paths = [
        "/blog", "/blogs", "/news", "/articles",
        "/resources", "/insights"
    ]

    has_blog_url = any(term in url_lower for term in blog_url_terms)
    is_blog_listing_url = path.rstrip("/") in blog_listing_paths

    # WordPress date-based post URLs: /YYYY/MM/DD/slug/
    has_wp_date_url = bool(re.search(r'/\d{4}/\d{2}/\d{2}/', path))

    if has_blog_url:
        score += 6
        signals.append("blog_url")

    if is_blog_listing_url:
        score += 4
        signals.append("blog_listing_url")

    if has_wp_date_url:
        score += 6
        signals.append("wp_date_url")

    # og:type = "article" — WordPress sets this by default on all pages,
    # so award only 1 point here (not 3).  URL-based signals are the real
    # differentiator for blogs vs. service/landing pages.
    og_type_meta = soup.select_one("meta[property='og:type']")
    og_type = clean_text(og_type_meta.get("content") or "") if og_type_meta else ""
    if og_type.lower() in ("article", "blog"):
        score += 1
        signals.append("og_type_article")

    # Article JSON-LD is also a WordPress default on non-blog pages — 1 point.
    if (
        has_jsonld_type(soup, "Article")
        or has_jsonld_type(soup, "BlogPosting")
        or has_jsonld_type(soup, "NewsArticle")
    ):
        score += 1
        signals.append("article_jsonld")

    # <article> DOM element is common in WordPress themes regardless of page type — 1 point.
    if soup.select_one("article, .post, .blog-post, [class*='blog'], [class*='article']"):
        score += 1
        signals.append("article_dom")

    page_text = clean_text(soup.get_text(" ")).lower()

    if any(x in page_text for x in ["published on", "posted on", "read time", "min read", "author"]):
        score += 2
        signals.append("blog_text_terms")

    service_terms = [
        "our services",
        "service",
        "services",
        "request a call",
        "get quote",
        "book consultation",
        "call us",
        "how it works",
        "work process",
        "our work process",
        "contact us",
        "reach out to us"
    ]

    has_service_intent = any(term in page_text for term in service_terms)

    # A blog should have either a blog URL, a WP date URL, or multiple article-style signals.
    # Article schema alone should not be enough, especially on service pages.
    is_blog = (
        has_blog_url
        or is_blog_listing_url
        or has_wp_date_url
        or (
            score >= 7
            and not has_service_intent
            and (
                "article_dom" in signals
                or "blog_text_terms" in signals
            )
        )
    )

    return {
        "isBlog": is_blog,
        "score": score,
        "signals": signals
    }


def detect_product_signals(url, html, soup):
    url_lower = safe_lower(url)
    html_lower = safe_lower(html)
    path = get_path_only(url)

    score = 0
    signals = []

    if is_nike_style_product_url(url):
        score += 18
        signals.append("nike_product_url")

    product_url_rules = [
        ("/product/", 6, "url_product"),
        ("/products/", 6, "url_products"),
        ("/product-page/", 6, "url_wix_product_page"),
        ("/item/", 4, "url_item"),
        ("/pd/", 6, "url_pd"),
        ("/p/", 5, "url_p"),
        ("/t/", 4, "url_t")
    ]

    for term, points, name in product_url_rules:
        if term in url_lower and not path.rstrip("/").endswith(term.rstrip("/")):
            score += points
            signals.append(name)

    if "/shop/" in url_lower:
        after_shop = url_lower.split("/shop/", 1)[-1].strip("/")
        parts = [p for p in after_shop.split("/") if p]

        if len(parts) >= 2:
            score += 5
            signals.append("deep_shop_product_url")
        elif len(parts) == 1:
            score += 2
            signals.append("possible_shop_product_url")

    og_type = soup.select_one("meta[property='og:type'], meta[name='og:type']")
    if og_type and safe_lower(og_type.get("content")) == "product":
        score += 7
        signals.append("og_type_product")

    price_meta = (
        get_meta_content(soup, "property", "product:price:amount")
        or get_meta_content(soup, "property", "og:price:amount")
        or get_meta_content(soup, "property", "price:amount")
    )

    if price_meta:
        score += 6
        signals.append("price_meta")

    body = soup.find("body")
    body_classes = " ".join(body.get("class", [])).lower() if body else ""

    body_product_classes = [
        "single-product",
        "post-type-product",
        "product-template-default",
        "template-product"
    ]

    if any(x in body_classes for x in body_product_classes):
        score += 7
        signals.append("product_body_class")

    if soup.select_one("h1.product_title, .product_title, [class*='product-title']"):
        score += 4
        signals.append("product_title_dom")

    if soup.select_one(
        "form.cart, .single_add_to_cart_button, button[name='add-to-cart'], "
        "button[data-hook*='add-to-cart'], [data-hook*='add-to-cart'], "
        "form[action*='/cart/add'], button[class*='add-to-cart'], "
        "button[class*='add_to_cart']"
    ):
        score += 7
        signals.append("add_to_cart_dom")

    if soup.select_one(
        ".woocommerce-product-gallery, .summary.entry-summary, "
        ".product-single, .product__info, .product-form, "
        "[data-hook='product-page'], [data-hook*='product-page']"
    ):
        score += 5
        signals.append("product_page_dom")

    if soup.select_one(
        ".stock, .availability, .sku, .posted_in, "
        "[data-hook*='sku'], [class*='sku']"
    ):
        score += 3
        signals.append("stock_sku_dom")

    if soup.select_one(
        ".woocommerce-tabs, #tab-description, "
        ".woocommerce-Tabs-panel, .product-tabs"
    ):
        score += 3
        signals.append("product_tabs")

    if has_jsonld_type(soup, "Product"):
        score += 8
        signals.append("jsonld_product")

    if "/wp-json/wp/v2/product/" in html_lower or "/wp/v2/product/" in html_lower:
        score += 7
        signals.append("wp_product_endpoint")

    page_text = clean_text(soup.get_text(" ")).lower()

    if any(x in page_text for x in ["add to cart", "buy now", "add to bag", "add to basket"]):
        score += 4
        signals.append("add_to_cart_text")

    if any(x in page_text for x in ["in stock", "out of stock", "sold out", "availability"]):
        score += 2
        signals.append("stock_text")

    if "description" in page_text and any(
        x in page_text for x in ["ingredients", "how to use", "specifications", "sku", "style:"]
    ):
        score += 2
        signals.append("product_content_sections")

    # Retail PDP signals: model number, web code, SKU lines, ship availability
    if re.search(r'\bmodel\s*[:#]\s*[A-Z0-9][A-Z0-9\-]{3,}', page_text, re.I):
        score += 6
        signals.append("sku_model_text")

    if re.search(r'\bweb\s*code\s*[:#]?\s*\d{5,}', page_text, re.I):
        score += 6
        signals.append("web_code_text")

    if re.search(r'\b(?:sku|item\s*(?:no|number|#))\s*[:#]\s*[A-Z0-9\-]{4,}', page_text, re.I):
        score += 5
        signals.append("explicit_sku_text")

    if re.search(r'\bavailable\s+to\s+ship\b', page_text, re.I):
        score += 4
        signals.append("ship_availability_text")

    if re.search(r'\b(?:sold\s+and\s+shipped\s+by|fulfilled\s+by)\b', page_text, re.I):
        score += 3
        signals.append("sold_shipped_by_text")

    # Wix product attribute selectors — e.g. "Color*", "Material*", "Shape*", "Brand*"
    # These appear on Wix product detail pages even when the URL is /collection/{slug}
    wix_attr_matches = re.findall(
        r"\b(?:Color|Colour|Material|Shape|Size|Brand|Style|Lens|Frame|SKU|Collection)\s*\*",
        page_text, re.I
    )
    if len(wix_attr_matches) >= 2:
        score += 8
        signals.append("wix_product_attributes")
    elif len(wix_attr_matches) == 1:
        score += 3
        signals.append("wix_product_attribute")

    # Wix-specific product content sections
    wix_product_section_terms = [
        "product info", "virtual try-on", "find a store near you",
        "find a retailer", "store locator", "product details"
    ]
    wix_section_hits = sum(1 for s in wix_product_section_terms if s in page_text.lower())
    if wix_section_hits >= 2:
        score += 4
        signals.append("wix_product_sections")
    elif wix_section_hits == 1:
        score += 2
        signals.append("wix_product_section")

    return {
        "isProduct": score >= 6,
        "score": score,
        "signals": signals
    }


def _detect_text_collection_signals(full_text_l):
    """
    Detect collection signals from full page text (not just scoped DOM).
    Handles Jina-rendered and JavaScript-heavy pages where the DOM is sparse
    but the full text contains filter UI, product counts, and price facets.

    Returns (score_boost, signal_names, contributes_to_structure).
    """
    boost = 0
    sigs = []
    contributes = False

    # "Filter Results" or "Refine Results" literal text — Kookaburra / faceted nav
    if re.search(r'\bfilter\s+results\b', full_text_l):
        boost += 7
        sigs.append("text_filter_results")
        contributes = True

    # Faceted navigation: "Category Name (N)" pattern repeated >= 3 times
    facet_count_matches = re.findall(r'[A-Za-z][A-Za-z\s\-]{2,40}\(\d{1,4}\)', full_text_l)
    if len(facet_count_matches) >= 3:
        boost += 5
        sigs.append("text_product_facet_counts")
        contributes = True
    elif len(facet_count_matches) >= 1:
        boost += 2
        sigs.append("text_product_facet_hint")

    # Price range facets: "Under $X", "$X-$Y", "Over $X" repeated >= 2 times
    price_range_matches = re.findall(
        r'(?:under\s+[$£€]\d+|[$£€]\d+\s*[-–]\s*[$£€]\d+|over\s+[$£€]\d+)',
        full_text_l
    )
    if len(price_range_matches) >= 2:
        boost += 3
        sigs.append("text_price_range_facets")
        contributes = True

    # "Sort By" in text (may appear as Jina markdown heading)
    if re.search(r'\bsort\s+by\b', full_text_l):
        boost += 3
        sigs.append("text_sort_by")
        contributes = True

    # "X Results" / "X Products" / "X Items" in full text
    if re.search(r'\b\d+\s+(?:results?|products?|items?)\b', full_text_l):
        boost += 3
        sigs.append("text_result_count")
        contributes = True

    # "Showing X of Y" — full text version
    if re.search(r'showing\s+\d+\s*[–\-]\s*\d+\s+of\s+\d+', full_text_l):
        boost += 4
        sigs.append("text_showing_x_of_y")
        contributes = True

    return boost, sigs, contributes


def detect_collection_signals(url, html, soup):
    url_lower = safe_lower(url)
    html_lower = safe_lower(html)
    path = get_path_only(url)

    score = 0
    signals = []

    scoped_soup = get_main_content_soup(soup)

    product_link_count = count_product_links_scoped(scoped_soup)
    category_link_count = count_category_like_links_scoped(scoped_soup)
    has_grid = has_product_grid_dom_scoped(scoped_soup)

    seo_text = extract_seo_text(soup)
    page_text = clean_text(scoped_soup.get_text(" "))
    page_text_l = page_text.lower()

    # Full page text (unscoped) — catches Jina-rendered content that the scoped DOM misses
    full_page_text_l = clean_text(soup.get_text(" ")).lower()

    collection_url_rules = [
        ("/collections/", 7, "url_collections"),
        ("/collection/", 6, "url_collection"),
        ("/product-category/", 7, "url_product_category"),
        ("/category/", 5, "url_category"),
        ("/categories/", 5, "url_categories"),
        ("/store/", 4, "url_store"),
        ("/catalog/", 4, "url_catalog"),
        ("/c/", 4, "url_c")
    ]

    for term, points, name in collection_url_rules:
        if term in url_lower:
            score += points
            signals.append(name)
            break

    if path.rstrip("/") == "/shop" or path.endswith("/shop"):
        score += 7
        signals.append("shop_listing_url")

    if "/shop/" in url_lower:
        after_shop = url_lower.split("/shop/", 1)[-1].strip("/")
        parts = [p for p in after_shop.split("/") if p]

        if len(parts) == 1:
            score += 4
            signals.append("shop_category_url")

    modern_terms = [
        "/men", "/women", "/kids", "/sale", "/new-arrivals",
        "/best-sellers", "/clothing", "/shoes", "/accessories",
        "/bags", "/beauty", "/skincare", "/makeup", "/hair",
        "/fragrance", "/electronics", "/speakers", "/headphones",
        "/pants", "/hoodies", "/jackets"
    ]

    if any(term in path for term in modern_terms):
        score += 3
        signals.append("modern_collection_url")

    seo_terms = [
        "shop", "collection", "collections", "category",
        "new arrivals", "best sellers", "sale", "products",
        "clothing", "shoes", "accessories", "skincare",
        "makeup", "hair care", "speakers", "headphones"
    ]

    seo_hits = sum(1 for term in seo_terms if term in seo_text)

    if seo_hits >= 1:
        score += min(4, seo_hits)
        signals.append("seo_collection_terms")

    if "product_cat" in html_lower or "woocommerce-loop-product" in html_lower:
        score += 6
        signals.append("woocommerce_collection_signal")

    if has_grid:
        score += 6
        signals.append("product_grid_dom")

    if scoped_soup.select_one(
        "select.orderby, .woocommerce-ordering, "
        "[data-hook*='sort'], [class*='sort-by'], [class*='filter']"
    ):
        score += 4
        signals.append("sort_filter_dom")

    if re.search(r"showing\s+\d+\s*[–-]\s*\d+\s+of\s+\d+", page_text, re.I):
        score += 5
        signals.append("showing_x_of_y_text")

    if product_link_count >= 3:
        score += 5
        signals.append("multiple_product_links")

    if product_link_count >= 8:
        score += 4
        signals.append("high_product_link_density")

    if category_link_count >= 8:
        score += 2
        signals.append("category_link_density_medium")

    if category_link_count >= 15:
        score += 3
        signals.append("category_link_density_high")

    price_matches = re.findall(
        r"(?:[$£€]\s?\d+(?:[,.]\d{1,2})?)|(?:\b(?:Rs|PKR|AED|USD)\s?\d+(?:[,.]\d{1,2})?)",
        page_text,
        re.I
    )

    if len(price_matches) >= 3:
        score += 4
        signals.append("multiple_price_texts")

    ecommerce_words = [
        "filter", "sort by", "shop by", "view all",
        "color", "size", "gender", "price", "availability"
    ]

    word_hits = sum(1 for word in ecommerce_words if word in page_text_l)

    if word_hits >= 2:
        score += 3
        signals.append("ecommerce_collection_wording")

    # Filter by + Sort by UI — strong Wix/catalog collection signal
    # (appears in Jina markdown from Wix collection filter panels)
    if "filter by" in page_text_l and "sort by" in page_text_l:
        score += 6
        signals.append("filter_sort_ui")

    # Multiple unique /collection/{slug} links — Wix B2B catalog style (OGI /seraphin)
    wix_catalog_slugs = set()
    for a in scoped_soup.find_all("a", href=True):
        href = a.get("href", "").lower()
        m = re.search(r"/collection/([^/?#]+)", href)
        if m and "/collections/" not in href:
            wix_catalog_slugs.add(m.group(1))
    if len(wix_catalog_slugs) >= 5:
        score += 5
        signals.append("wix_collection_product_links")

    # Load More / ?page= pagination — strong collection indicator
    # Wix collection pages typically have paginated product grids.
    _has_load_more = "load more" in page_text_l or "show more" in page_text_l
    _has_page_param = bool(re.search(r"[?&]page=\d+", str(scoped_soup)))
    if _has_load_more or _has_page_param:
        score += 4
        signals.append("wix_load_more_or_paginated")

    # Text-based collection signals (catches Jina-rendered / JS-heavy pages)
    _text_boost, _text_sigs, _text_contributes = _detect_text_collection_signals(full_page_text_l)
    if _text_boost > 0:
        score += _text_boost
        signals.extend(_text_sigs)

    real_collection_structure = (
        has_grid
        or product_link_count >= 5
        or (len(price_matches) >= 3 and product_link_count >= 3)
        or "showing_x_of_y_text" in signals
        or "sort_filter_dom" in signals
        or "filter_sort_ui" in signals
        or "wix_collection_product_links" in signals
        or ("wix_load_more_or_paginated" in signals and product_link_count >= 3)
        or _text_contributes  # text-based filter/facet/sort signals on Jina pages
    )

    if not real_collection_structure:
        score = min(score, 4)
        signals.append("collection_score_capped_no_real_structure")

    return {
        "isCollection": score >= 6,
        "score": score,
        "signals": signals,
        "metrics": {
            "productLinkCount": product_link_count,
            "categoryLinkCount": category_link_count,
            "hasProductGrid": has_grid,
            "priceTextCount": len(price_matches),
            "textCollectionBoost": _text_boost
        }
    }


def detect_informational_page(url):
    path = get_path_only(url).rstrip("/")

    informational_terms = [
        "/about", "/about-us", "/our-story", "/story",
        "/mission", "/vision", "/values", "/company",
        "/who-we-are", "/sustainability", "/careers",
        "/career", "/contact", "/contact-us", "/faq",
        "/help", "/support", "/privacy", "/privacy-policy",
        "/terms", "/terms-conditions", "/terms-and-conditions",
        "/shipping", "/delivery", "/returns", "/refund",
        "/refund-policy", "/pages/about", "/pages/about-us",
        "/pages/our-story", "/pages/mission", "/pages/sustainability",
        "/pages/contact", "/pages/contact-us", "/o-nas",
        "/kontakt", "/dostawa", "/zwroty", "/regulamin",
        "/polityka-prywatnosci"
    ]

    return any(term in path for term in informational_terms)


_PTD_TOUR_KEYWORDS = [
    "tour", "excursion", "activity", "what to expect",
    "pickup", "pick-up", "guide", "guided", "itinerary", "duration",
    "safari", "atv", "quad", "adventure", "bedouin",
    "book your tour", "reserve your spot",
]

_PTD_SERVICE_KEYWORDS = [
    "service", "consultation", "corporate", "workshop", "team building",
    "event", "application form", "request information",
    "book a", "request a call", "get quote", "free consultation",
    "candle part", "group booking", "hire us", "book us",
    "how it works", "our process", "our services",
]

_PTD_TOOL_KEYWORDS = [
    "app", "virtual try-on", "virtual try on", "try-on", "try on",
    "software", "platform", "dashboard",
    "3d rendering", "real-time tracking", "augmented reality",
    "web app", "desktop app",
]

_PTD_ABOUT_KEYWORDS = [
    "founder", "our story", "about us", "brand story", "mission",
    "who we are", "our team",
]


def _is_overwhelming_collection(collection_detection):
    """
    True when collection evidence is so strong (massive product links / prices / score)
    that it should override a wix_product_attributes-driven product classification.
    MAC Cosmetics /bestsellers is a canonical example: collection score 22,
    97 product links, 58 price texts — clearly a collection, not a single PDP.
    """
    metrics = collection_detection.get("metrics", {}) or {}
    return (
        collection_detection.get("score", 0) >= 18
        or metrics.get("productLinkCount", 0) >= 30
        or metrics.get("priceTextCount", 0) >= 20
    )


# Keywords that identify product family landing pages (Apple /ipad/, Samsung /galaxy-s25/)
# NOTE: "find your" was removed — too generic, fires on any fashion site ("find your style")
_PTD_PRODUCT_FAMILY_COMPARE_KW = [
    "compare all", "compare models", "compare all models", "view all models",
    "all models", "explore the lineup", "see all models", "compare ipad",
    "compare mac", "compare iphone", "compare galaxy", "compare pixel",
    "compare watch", "which model",
]

# Keywords that identify editorial category landing pages (Nike /women)
_PTD_CATEGORY_LANDING_PATHS = [
    "/women", "/men", "/kids", "/girls", "/boys",
    "/womens", "/mens", "/juniors", "/baby", "/toddler",
]
_PTD_CATEGORY_SECTION_KW = [
    "shoes", "clothing", "accessories", "new arrivals", "sale",
    "tops", "bottoms", "outerwear", "activewear", "sportswear",
]


def _detect_product_family_landing(soup, text):
    """
    Detect Apple iPad / Samsung Galaxy product family landing pages.
    These are NOT product detail pages but showcase a family of related models.
    Signals:
    - A "compare" or "explore the lineup" style link
    - Multiple short H2/H3 headings that are model names
    - Multiple "Buy" and/or "Learn more" CTAs (one per model)
    - No sort/filter/pagination UI
    """
    # Must have a compare/explore signal
    has_compare = any(k in text for k in _PTD_PRODUCT_FAMILY_COMPARE_KW)

    # Count product-family CTAs
    buy_count = len(re.findall(r'\bbuy\b', text))
    learn_count = text.count("learn more")
    cta_count = buy_count + learn_count

    if not has_compare and cta_count < 4:
        return False

    # Bail out early if lots of prices are visible — product family pages have 2-6 prices
    # (one per model), not 20+. High price count = ecommerce collection, not tech lineup.
    price_count = len(re.findall(r'[\$£€]\s*\d+|\d+\s*(?:USD|EUR|GBP)', text))
    if price_count > 15:
        return False

    # Must have multiple short H2/H3 headings that look like product names
    h_tags = soup.find_all(["h2", "h3"])
    h_texts = [clean_text(h.get_text(" ", strip=True)) for h in h_tags]
    # Model-name headings: 1-6 words, capitalized, short.
    # Exclude generic nav/filter words AND fashion/retail category words.
    _model_name_excludes = [
        "filter", "sort", "view all", "see all", "shop all",
        "about", "contact", "menu", "navigation",
        # Fashion / retail category headings — NOT product model names:
        "shoes", "clothing", "accessories", "new arrivals", "sale",
        "tops", "bottoms", "outerwear", "activewear", "sportswear",
        "dresses", "skirts", "jeans", "shorts", "pants", "jackets",
        "swimwear", "intimates", "rompers", "jumpsuits", "vintage",
        "brands", "gifts", "home", "beauty", "wellness",
    ]
    model_like = [
        h for h in h_texts
        if 1 <= len(h.split()) <= 6
        and h and h[0].isupper()
        and not any(nav in h.lower() for nav in _model_name_excludes)
    ]
    if len(model_like) < 3:
        return False

    # Must have at least one compare signal OR enough CTAs
    if not has_compare and cta_count < 6:
        return False

    # Must NOT have sort/filter signals (those are collection pages)
    # ("default sorting" = WooCommerce's sort dropdown label)
    if any(k in text for k in ["sort by", "filter by", "filter results", "default sorting"]):
        return False

    # Must NOT have a real product grid DOM — Apple/Samsung family pages
    # showcase models in hero sections, not commerce grids. A shop page with
    # a product grid (e.g. magnatiles.com/shop) is a collection, not a lineup.
    if soup.select_one(
        "[class*='product-grid'], [class*='product-card'], [data-product-id], "
        ".product-card, .product-tile, .grid-product, "
        "ul.products li.product, .wc-block-grid__product, "
        ".woocommerce-loop-product__title"
    ):
        return False

    return True


def _detect_category_landing(url, soup, text):
    """
    Detect editorial category landing pages like Nike /women or Nike /men.
    These are navigation hubs to sub-categories, not true product listing pages.
    Signals:
    - Top-level gender/age path OR multiple category-section headings
    - No sort/filter/pagination
    - No real product grid DOM
    """
    path = get_path_only(url).rstrip("/")

    # Path match: /women, /men, /kids, /boys, /girls (top-level only)
    is_category_path = any(
        path == p or (path.startswith(p) and len(path) <= len(p) + 3)
        for p in _PTD_CATEGORY_LANDING_PATHS
    )

    # Editorial layout: multiple H2s that are category section names
    if not is_category_path:
        h2_texts = [clean_text(h.get_text(" ", strip=True)).lower() for h in soup.find_all("h2")]
        category_h2_count = sum(
            1 for h in h2_texts
            if any(k in h for k in _PTD_CATEGORY_SECTION_KW)
        )
        if category_h2_count < 2:
            return False

    # Must NOT have sort/filter signals
    # ("default sorting" = WooCommerce's sort dropdown label on /shop/ archives)
    if any(k in text for k in ["sort by", "filter by", "filter results", "default sorting"]):
        return False

    # Bail out if many prices are visible — true editorial hubs have no product prices
    # (Nike /women has 0; a UO /womens-clothing product grid has 100+)
    price_count = len(re.findall(r'[\$£€]\s*\d+|\d+\s*(?:USD|EUR|GBP)', text))
    if price_count > 20:
        return False

    # Must NOT have a real product grid DOM (that would be a collection).
    # Includes WooCommerce archive markup (ul.products > li.product,
    # .wc-block-grid) — /shop/ pages were misrouted to "general" without it.
    if soup.select_one(
        "[class*='product-grid'], [class*='product-card'], [data-product-id], "
        ".product-card, .product-tile, .grid-product, "
        "ul.products li.product, .wc-block-grid__product, "
        ".woocommerce-loop-product__title"
    ):
        return False

    return True


def detect_general_subtype(url, soup):
    path = get_path_only(url).rstrip("/")
    text = clean_text(soup.get_text(" ")).lower()

    # Path-based hard matches (high precision)
    if any(x in path for x in ["/contact", "/contact-us", "/get-in-touch"]):
        return "contact"

    if any(x in path for x in ["/about", "/about-us", "/our-story", "/story", "/company", "/who-we-are"]):
        return "about"

    if any(x in path for x in ["/pricing", "/plans", "/packages"]):
        return "pricing"

    if any(x in path for x in ["/faq", "/faqs"]):
        return "faq"

    if any(x in path for x in ["/privacy", "/terms", "/refund", "/shipping", "/returns", "/delivery"]):
        return "legal"

    # Product family landing page (Apple /ipad/, Samsung /galaxy/)
    # Checked before tour_page because product family pages often contain "guide" etc.
    if _detect_product_family_landing(soup, text):
        return "product_family_landing"

    # Editorial category landing page (Nike /women, Nike /men)
    # Checked before tour_page to avoid misclassifying gender nav hubs.
    if _detect_category_landing(url, soup, text):
        return "category_landing"

    # Tour page detection
    tour_hits = sum(1 for k in _PTD_TOUR_KEYWORDS if k in text)
    if tour_hits >= 3:
        return "tour_page"

    # Tool/app page detection (checked before about — nav "our story" links are common)
    tool_hits = sum(1 for k in _PTD_TOOL_KEYWORDS if k in text)
    if tool_hits >= 2:
        return "tool_app_page"

    # About — text-based; require 2+ keywords to avoid nav-link false positives
    about_hits = sum(1 for k in _PTD_ABOUT_KEYWORDS if k in text)
    if about_hits >= 2:
        return "about"

    # Service page (workshop, corporate events, consultation, etc.)
    service_path_terms = [
        "/service", "/services", "/solution", "/solutions",
        "/automation", "/installation", "/consulting", "/agency",
        "/support", "/workshop", "/events",
    ]
    service_hits = sum(1 for k in _PTD_SERVICE_KEYWORDS if k in text)
    if any(term in path for term in service_path_terms) or service_hits >= 2:
        return "service_page"

    # Landing page
    landing_terms = ["get started", "start now", "why choose", "trusted by"]
    landing_hits = sum(1 for k in landing_terms if k in text)
    if landing_hits >= 2:
        return "landing_page"

    return "unknown"


def has_strong_product_evidence(product_detection):
    signals = product_detection.get("signals", [])
    score = product_detection.get("score", 0)

    strong_signals = [
        "nike_product_url",
        "jsonld_product",
        "og_type_product",
        "price_meta",
        "product_body_class",
        "product_title_dom",
        "add_to_cart_dom",
        "product_page_dom",
        "stock_sku_dom",
        "product_tabs",
        "wp_product_endpoint",
        "wix_product_attributes",
        # Retail-site hard signals (BestBuy, Target, etc.)
        "sku_model_text",
        "web_code_text",
        "explicit_sku_text",
        "ship_availability_text",
        "sold_shipped_by_text",
    ]

    strong_count = sum(1 for signal in strong_signals if signal in signals)

    return strong_count >= 2 or (
        score >= 18 and any(signal in signals for signal in strong_signals)
    )


def has_real_buying_intent(html, soup):
    html_l = safe_lower(html)
    text_l = clean_text(soup.get_text(" ")).lower()

    dom_intent = bool(
        soup.select_one(
            "form.cart, form[action*='/cart/add'], .product-form, "
            "button[name='add-to-cart'], .single_add_to_cart_button, "
            "button[data-hook*='add-to-cart'], [data-hook*='add-to-cart'], "
            "button[class*='add-to-cart'], button[class*='add_to_cart'], "
            "input[name='quantity'], select[name='id'], [name='quantity'], "
            "[class*='variant'], [data-product-form]"
        )
    )

    html_intent_terms = [
        "add-to-cart", "add_to_cart", "/cart/add",
        "product-form", "productform", "variant-picker",
        "variant-selector", "quantity-selector",
        "name=\"quantity\"", "data-product-form"
    ]

    text_intent_terms = [
        "add to cart", "add to bag", "add to basket",
        "buy now", "choose size", "select size", "quantity"
    ]

    return (
        dom_intent
        or any(term in html_l for term in html_intent_terms)
        or any(term in text_l for term in text_intent_terms)
    )


def has_collection_override_evidence(collection_detection):
    """
    True when a URL-only "blog" route signal should be overridden because
    the page shows real collection/ecommerce evidence (product grid,
    multiple product links, sorting/filter controls, etc).

    Used so that URL structure alone (e.g. "/category/...") never forces
    pageType=blog when the page is clearly a product listing/collection.
    """
    if not collection_detection:
        return False

    metrics = collection_detection.get("metrics", {}) or {}
    signals = collection_detection.get("signals", []) or []

    return bool(
        collection_detection.get("isCollection")
        and (
            metrics.get("productLinkCount", 0) >= 3
            or metrics.get("hasProductGrid", False)
            or "multiple_product_links" in signals
            or "high_product_link_density" in signals
            or "product_grid_dom" in signals
            or "sort_filter_dom" in signals
        )
    )


def _is_consumer_brand_catalog(url, html):
    """Return True when a /products/ URL looks like a brand product catalog with no ecommerce.

    Signals: wp-content URLs in HTML, multiple size/weight mentions, no cart/price text.
    Used to override Shopify /products/ routing for WordPress brands (e.g. Haven Greens).
    """
    path = get_path_only(url)
    if "/products/" not in path:
        return False
    # Must look like a listing page, not a single product handle
    # e.g. /products/ or /products (not /products/red-dress/)
    trailing = path.split("/products/", 1)[-1].strip("/")
    if trailing and "/" not in trailing and len(trailing) > 2:
        # Has a slug after /products/ — likely a single product page; skip
        return False
    # Only intercept WordPress-hosted pages (wp-content is a reliable signal)
    if "wp-content" not in (html or ""):
        return False
    html_lower = (html or "").lower()
    # Must NOT have cart/checkout intent
    if any(k in html_lower for k in ["add-to-cart", "add_to_cart", "/cart/add", "add to cart", "buy now"]):
        return False
    # Must NOT have price signals
    if re.search(r'(?<![a-zA-Z])(?:\$|£|€|₹|rs\.?)\s*\d', html_lower):
        return False
    # Must have multiple size/weight mentions
    sizes = re.findall(r'\b\d+\s*(?:g|ml|oz|lb|lbs|kg)\b', html_lower)
    if len(sizes) < 2:
        return False
    # Must have several h3 headings (Jina section structure)
    if html_lower.count("<h3") < 3:
        return False
    return True


def detect_platform_route_priority(url, platform=None, collection_detection=None):
    path = get_path_only(url)
    platform_l = normalize_platform(platform)

    # Cross-platform: pricing / plans pages should always route to general,
    # regardless of platform, to prevent product/collection score overrides.
    _pricing_segments = ["/pricing", "/plans", "/packages", "/price-calculator",
                         "/pricing-plans", "/our-pricing", "/compare-plans"]
    if any(path.rstrip("/").endswith(s) or (s + "/") in path for s in _pricing_segments):
        return "general", 0.92, "pricing_page_url_priority"

    # Shopify has very reliable routing.
    if "shopify" in platform_l:
        if "/products/" in path:
            return "product", 0.99, "shopify_product_url_priority"

        if "/collections/" in path:
            return "collection", 0.99, "shopify_collection_url_priority"

        if "/blogs/" in path:
            return "blog", 0.95, "shopify_blog_url_priority"

        if "/pages/" in path:
            return "general", 0.92, "shopify_page_url_priority"

    # WooCommerce / WordPress routing.
    if "woocommerce" in platform_l:
        if "/product/" in path:
            return "product", 0.99, "woocommerce_product_url_priority"

        if "/product-category/" in path:
            return "collection", 0.98, "woocommerce_product_category_priority"

        if path.rstrip("/") == "/shop" or path.startswith("/shop/"):
            return "collection", 0.96, "woocommerce_shop_url_priority"

        if "/cart" in path or "/checkout" in path:
            return "cart_checkout", 0.99, "woocommerce_cart_checkout_priority"

    if "wordpress" in platform_l:
        if "/product/" in path:
            return "product", 0.96, "wordpress_product_url_priority"

        if "/product-category/" in path or path.rstrip("/") == "/shop" or path.startswith("/shop/"):
            return "collection", 0.94, "wordpress_shop_collection_priority"

        # WordPress date-based post URLs: /YYYY/MM/DD/slug/
        if re.search(r'/\d{4}/\d{2}/\d{2}/', path):
            return "blog", 0.94, "wordpress_date_url_priority"

        if any(x in path for x in ["/blog/", "/post/", "/article/", "/news/"]):
            return "blog", 0.94, "wordpress_blog_url_priority"

        if "/category/" in path:
            if has_collection_override_evidence(collection_detection):
                return "collection", 0.92, "wordpress_category_collection_override"

            return "blog", 0.82, "wordpress_category_url_priority"

    # Wix routing.
    if "wix" in platform_l:
        if "/product-page/" in path:
            return "product", 0.98, "wix_product_page_url_priority"

        if (
            "/category/" in path
            or path.rstrip("/") == "/shop"
            or path.startswith("/shop/")
            or path.startswith("/shop-")
        ):
            return "collection", 0.90, "wix_collection_url_priority"

        if "/blog/" in path or "/post/" in path:
            return "blog", 0.92, "wix_blog_url_priority"

    # Webflow usually has custom routes, so keep lighter priority.
    if "webflow" in platform_l:
        if "/product/" in path or "/products/" in path:
            return "product", 0.90, "webflow_product_url_priority"

        if any(x in path for x in ["/collection/", "/collections/", "/category/", "/shop/"]):
            return "collection", 0.86, "webflow_collection_url_priority"

        if any(x in path for x in ["/blog/", "/post/", "/article/", "/news/"]):
            return "blog", 0.90, "webflow_blog_url_priority"

    return None, None, None


def build_response(page_type, confidence, page_type_signals, reason, debug_signals=None, general_subtype=None):
    response = {
        "pageType": page_type,
        "pageTypeConfidence": round(confidence, 2),
        "pageTypeSignals": page_type_signals,
        "pageTypeDebug": {
            "reason": reason,
            "signals": debug_signals or {}
        }
    }

    if page_type == "general":
        response["generalSubtype"] = general_subtype or "unknown"

    return response


def detect_page_type(html, url, platform=None):
    html = html or ""
    url = url or ""
    platform = platform or ""

    soup = BeautifulSoup(html, "lxml")
    path = get_path_only(url)

    page_type_signals = {
        "homepage": 0,
        "collection": 0,
        "product": 0,
        "blog": 0,
        "cart_checkout": 0,
        "general": 0
    }

    if is_homepage_path(url):
        product_detection = detect_product_signals(url, html, soup)
        collection_detection = detect_collection_signals(url, html, soup)
        blog_detection = detect_blog_signals(url, soup)

        page_type_signals["homepage"] = 20

        return build_response(
            "homepage",
            0.98,
            page_type_signals,
            "homepage_path_priority",
            {
                "product": product_detection,
                "collection": collection_detection,
                "blog": blog_detection,
                "platform": platform
            }
        )

    if detect_cart_checkout(url):
        page_type_signals["cart_checkout"] = 10

        return build_response(
            "cart_checkout",
            0.99,
            page_type_signals,
            "cart_checkout_url"
        )

    product_detection = detect_product_signals(url, html, soup)
    collection_detection = detect_collection_signals(url, html, soup)
    blog_detection = detect_blog_signals(url, soup)
    general_subtype = detect_general_subtype(url, soup)

    page_type_signals["product"] = product_detection["score"]
    page_type_signals["collection"] = collection_detection["score"]
    page_type_signals["blog"] = blog_detection["score"]

    debug_signals = {
        "product": product_detection,
        "collection": collection_detection,
        "blog": blog_detection,
        "generalSubtype": general_subtype,
        "platform": platform
    }

    # --------------------------------------------------
    # 1a. Consumer brand catalog override (pre-route)
    # WordPress /products/ listing pages with product names + sizes but no
    # cart/prices should be classified as general, not Shopify product.
    # --------------------------------------------------

    if _is_consumer_brand_catalog(url, html):
        page_type_signals["general"] = 100
        return build_response(
            "general",
            0.88,
            page_type_signals,
            "consumer_brand_catalog_override",
            debug_signals,
            general_subtype="consumer_brand_products"
        )

    # --------------------------------------------------
    # 1. Platform-specific route priority
    # --------------------------------------------------

    route_page_type, route_confidence, route_reason = detect_platform_route_priority(
        url, platform, collection_detection
    )

    # WooCommerce /shop/{slug} permalinks can be SINGLE PRODUCTS (permalink
    # base "shop"), e.g. mahalo.care/shop/the-unveil/. When the URL rule says
    # collection but the DOM carries definitive single-product evidence
    # (single-product body class, add-to-cart form, SKU, product tabs), the
    # content wins over the URL.
    _shop_route_rules = {"woocommerce_shop_url_priority", "wordpress_shop_collection_priority"}
    _definitive_product_signals = {"product_body_class", "add_to_cart_dom", "stock_sku_dom", "product_tabs"}
    _pd_signals = set(product_detection.get("signals", []))
    if (
        route_page_type == "collection"
        and route_reason in _shop_route_rules
        and product_detection.get("isProduct")
        and product_detection.get("score", 0) >= 20
        # "single-product" body class is WooCommerce's definitive PDP marker —
        # shop GRIDS can fake add-to-cart/stock signals via per-card buttons
        # (gruum.com/shop), but never carry the single-product body class.
        and "product_body_class" in _pd_signals
        and len(_definitive_product_signals & _pd_signals) >= 2
    ):
        route_page_type, route_confidence, route_reason = (
            "product", 0.9, "shop_url_overridden_by_product_evidence"
        )

    if route_page_type:
        page_type_signals[route_page_type] = page_type_signals.get(route_page_type, 0) + 1000

        return build_response(
            route_page_type,
            route_confidence,
            page_type_signals,
            route_reason,
            debug_signals,
            general_subtype=general_subtype if route_page_type == "general" else None
        )

    # --------------------------------------------------
    # 2. Absolute Shopify-style fallback
    # This runs even when platform is accidentally empty.
    # /collections/x/products/y = product
    # /products/y = product
    # /collections/y = collection
    # --------------------------------------------------

    if "/products/" in path:
        page_type_signals["product"] = product_detection["score"] + 1000

        return build_response(
            "product",
            0.99,
            page_type_signals,
            "shopify_style_product_url_absolute_priority",
            debug_signals
        )

    if "/collections/" in path:
        page_type_signals["collection"] = collection_detection["score"] + 1000

        return build_response(
            "collection",
            0.99,
            page_type_signals,
            "shopify_style_collection_url_absolute_priority",
            debug_signals
        )

    if "/blogs/" in path:
        page_type_signals["blog"] = blog_detection["score"] + 1000

        return build_response(
            "blog",
            0.95,
            page_type_signals,
            "shopify_style_blog_url_absolute_priority",
            debug_signals
        )

    if "/pages/" in path:
        page_type_signals["general"] = 10

        return build_response(
            "general",
            0.92,
            page_type_signals,
            "shopify_style_page_url_absolute_priority",
            debug_signals,
            general_subtype=general_subtype
        )

    # --------------------------------------------------
    # 3. General subtype hard priority
    #
    # IMPORTANT:
    # Pricing pages can contain many prices, plan cards, and product-like links.
    # They must not be classified as ecommerce collections.
    #
    # Examples:
    # /pricing
    # /plans
    # /packages
    #
    # Shopify product/collection URL safety has already run above, so this
    # will not break /products/ or /collections/ ecommerce pages.
    # --------------------------------------------------

    blog_url_like = any(
        x in path
        for x in [
            "/blog", "/blogs", "/post", "/posts",
            "/article", "/articles", "/news"
        ]
    )

    if general_subtype == "pricing" and not blog_url_like:
        page_type_signals["general"] = max(page_type_signals.get("general", 0), 20)

        return build_response(
            "general",
            0.94,
            page_type_signals,
            "general_subtype_priority",
            debug_signals,
            general_subtype="pricing"
        )

    _GENERAL_SUBTYPE_STOPS = {
        "service_page", "tour_page", "tool_app_page",
        "about", "contact", "faq", "legal", "service",
        # Editorial pages that look like products/collections but are not:
        "product_family_landing",  # Apple /ipad/, Samsung /galaxy-s25/
        "category_landing",        # Nike /women, Nike /men
    }
    # product_family_landing and category_landing always route to general even when
    # product or collection signals also fire (they legitimately have product-like content).
    _force_general_subtypes = {"product_family_landing", "category_landing"}

    if general_subtype in _GENERAL_SUBTYPE_STOPS and not blog_url_like:
        force_general = general_subtype in _force_general_subtypes
        if force_general or not product_detection["isProduct"]:
            page_type_signals["general"] = max(page_type_signals.get("general", 0), 20)

            return build_response(
                "general",
                0.94,
                page_type_signals,
                "general_subtype_priority",
                debug_signals,
                general_subtype=general_subtype
            )

    # --------------------------------------------------
    # 4. Other product URL hard priority
    # --------------------------------------------------

    if is_nike_style_product_url(url) and product_detection["score"] >= 10:
        page_type_signals["product"] = product_detection["score"] + 100

        return build_response(
            "product",
            0.97,
            page_type_signals,
            "nike_product_url_priority",
            debug_signals
        )

    # --------------------------------------------------
    # 5. Blog URL priority
    # --------------------------------------------------

    blog_priority_terms = [
        "/blog", "/blogs", "/newsroom", "/news",
        "/stories", "/story", "/article", "/articles",
        "/post", "/posts", "/insights", "/resources"
    ]

    if any(x in path for x in blog_priority_terms) and not product_detection["isProduct"]:
        return build_response(
            "blog",
            0.95,
            page_type_signals,
            "blog_url_priority",
            debug_signals
        )

    # --------------------------------------------------
    # 6. Informational page override
    # --------------------------------------------------

    if detect_informational_page(url) and not has_strong_product_evidence(product_detection):
        page_type_signals["general"] = 10

        return build_response(
            "general",
            0.96,
            page_type_signals,
            "informational_page_override_weak_product_signals",
            debug_signals,
            general_subtype=general_subtype
        )

    # --------------------------------------------------
    # 7. Product detection
    # --------------------------------------------------

    # Guard: Wix collection filter UIs contain attribute labels (Color, Brand, Material,
    # Shape, Size...) that can trigger wix_product_attributes. When the page has strong
    # collection-filter evidence (Filter by + Sort by UI + collection structure evidence,
    # with collection score >= 15) AND the only product signals come from those attribute
    # signals, suppress product classification so the collection wins in step 8.
    #
    # Collection structure evidence (any of):
    #   - 5+ /collection/{slug} links (Wix B2B catalog, e.g. OGI /seraphin)
    #   - 5+ product links (e.g. /product-page/ links on C&C /shop-candles)
    #   - Load More / ?page= pagination
    _prod_signals_set = set(product_detection.get("signals", []))
    _attr_only_signals = {
        "wix_product_attributes", "wix_product_attribute",
        "wix_product_sections", "wix_product_section",
    }
    _coll_filter_signals = collection_detection.get("signals", [])
    _coll_metrics = collection_detection.get("metrics", {})
    _coll_has_strong_structure = (
        "wix_collection_product_links" in _coll_filter_signals
        or _coll_metrics.get("productLinkCount", 0) >= 5
        or "wix_load_more_or_paginated" in _coll_filter_signals
    )
    _is_collection_filter_page = (
        collection_detection.get("score", 0) >= 15
        and "filter_sort_ui" in _coll_filter_signals
        and _coll_has_strong_structure
        and _prod_signals_set <= _attr_only_signals  # product signals are ONLY attr/section
    )
    if _is_collection_filter_page:
        product_detection = {
            **product_detection,
            "isProduct": False,
            "signals": product_detection.get("signals", [])
                       + ["suppressed_collection_filter_guard"],
        }

    if product_detection["isProduct"]:
        strong_product = has_strong_product_evidence(product_detection)
        buying_intent = has_real_buying_intent(html, soup)

        if strong_product or (
            product_detection["score"] >= 14
            and buying_intent
            and any(
                x in product_detection["signals"]
                for x in [
                    "url_product",
                    "url_products",
                    "deep_shop_product_url",
                    "url_wix_product_page",
                    "url_pd",
                    "url_p",
                    "url_t",
                    "nike_product_url"
                ]
            )
        ) or (
            # Wix /collection/{slug} product override:
            # Multiple attribute selectors (Color*, Material*, Shape*, Brand*...) on the
            # same page is definitive evidence of a Wix product detail page, regardless
            # of URL structure.
            # DISABLED when the collection-filter guard has already fired (those attribute
            # labels are collection filter navigation, not product variant selectors).
            # ALSO DISABLED when collection evidence is overwhelming (MAC Cosmetics /bestsellers:
            # collection score 22, 97 product links, 58 prices -- clearly a collection, not a PDP).
            "wix_product_attributes" in product_detection["signals"]
            and "suppressed_collection_filter_guard" not in product_detection["signals"]
            and product_detection["score"] >= 10
            and not _is_overwhelming_collection(collection_detection)
        ):
            page_type_signals["product"] = product_detection["score"] + 100

            confidence = min(
                0.99,
                0.74 + product_detection["score"] * 0.02
            )

            return build_response(
                "product",
                confidence,
                page_type_signals,
                "product_hard_priority_strong_evidence",
                debug_signals
            )

    # --------------------------------------------------
    # 7b. /product/ URL with product evidence overrides collection
    #
    # Retail sites (BestBuy, Target, Currys, etc.) use /product/{slug}/{id}
    # URLs. These pages can have many prices (financing, warranties, accessories)
    # that inflate collection score. When the URL explicitly contains /product/
    # and product signals confirm it's a product page, don't let collection win.
    # --------------------------------------------------

    if "/product/" in path and product_detection["isProduct"]:
        page_type_signals["product"] = product_detection["score"] + 100
        confidence = min(0.95, 0.75 + product_detection["score"] * 0.02)
        return build_response(
            "product",
            confidence,
            page_type_signals,
            "product_url_with_product_evidence",
            debug_signals
        )

    # --------------------------------------------------
    # 7c. Product-family landing page
    #
    # Samsung /us/smartphones/galaxy-s25/ and similar brand PDP-family pages:
    # - isProduct=True with product score >= 6
    # - Has real buying intent (Add to Cart / Buy Now)
    # - Collection score was capped because it has no real collection structure
    #   (many variant prices but only 1 product link)
    # --------------------------------------------------

    if (
        product_detection["isProduct"]
        and product_detection["score"] >= 6
        and "collection_score_capped_no_real_structure" in collection_detection.get("signals", [])
    ):
        buying_intent_7c = buying_intent if "buying_intent" in dir() else has_real_buying_intent(html, soup)
        if buying_intent_7c:
            page_type_signals["product"] = product_detection["score"] + 100
            confidence = min(0.85, 0.70 + product_detection["score"] * 0.02)
            return build_response(
                "product",
                confidence,
                page_type_signals,
                "product_family_landing_buying_intent",
                debug_signals
            )

    # --------------------------------------------------
    # 8. Collection detection
    # --------------------------------------------------

    if collection_detection["isCollection"]:
        page_type_signals["collection"] = collection_detection["score"] + 100

        confidence = min(
            0.98,
            0.72 + collection_detection["score"] * 0.025
        )

        return build_response(
            "collection",
            confidence,
            page_type_signals,
            "collection_signals",
            debug_signals
        )

    # --------------------------------------------------
    # 9. Blog detection
    # --------------------------------------------------

    if blog_detection["isBlog"]:
        confidence = min(
            0.95,
            0.72 + blog_detection["score"] * 0.025
        )

        return build_response(
            "blog",
            confidence,
            page_type_signals,
            "blog_signals",
            debug_signals
        )

    # --------------------------------------------------
    # 10. Generic URL fallbacks
    # --------------------------------------------------

    if any(x in path for x in ["/product/", "/item/", "/p/", "/pd/"]):
        return build_response(
            "product",
            0.75,
            page_type_signals,
            "product_url_fallback",
            debug_signals
        )

    if any(x in path for x in ["/collection/", "/category/", "/product-category/"]):
        platform_l = normalize_platform(platform)
        if "wix" in platform_l and "/collection/" in path and "/collections/" not in path:
            pass
        else:
            return build_response(
                "collection",
                0.75,
                page_type_signals,
                "collection_url_fallback",
                debug_signals
            )

    if any(x in path for x in ["/blog", "/news", "/stories", "/articles", "/resources"]):
        return build_response(
            "blog",
            0.82,
            page_type_signals,
            "blog_url_fallback",
            debug_signals
        )

    page_type_signals["general"] = 1

    return build_response(
        "general",
        0.90,
        page_type_signals,
        "fallback",
        debug_signals,
        general_subtype=general_subtype
    )
