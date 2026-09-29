from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin

from analyzers.pagination_helper import fetch_extra_pages


def clean_text(text):
    return re.sub(r"\s+", " ", text or "").strip()


def unique_list(items):
    seen = set()
    output = []

    for item in items:
        if not item:
            continue

        key = str(item).strip()

        if not key or key in seen:
            continue

        seen.add(key)
        output.append(item)

    return output


def unique_list_by_url(items):
    seen = set()
    output = []

    for item in items:
        url = item.get("url")

        if not url or url in seen:
            continue

        seen.add(url)
        output.append(item)

    return output


def get_meta_content(soup, name=None, property_name=None):
    if name:
        tag = soup.find("meta", attrs={"name": name})
        if tag:
            return clean_text(tag.get("content"))

    if property_name:
        tag = soup.find("meta", attrs={"property": property_name})
        if tag:
            return clean_text(tag.get("content"))

    return None


def normalize_price(price):
    if not price:
        return None

    price = clean_text(price)

    invalid_prices = {
        "$0",
        "$0.0",
        "$0.00",
        "£0",
        "£0.0",
        "£0.00",
        "€0",
        "€0.0",
        "€0.00",
        "0",
        "0.0",
        "0.00",
        "rs 0",
        "rs. 0",
        "pkr 0"
    }

    if price.lower() in invalid_prices:
        return None

    return price


# Amount grammar: comma-grouped numbers ("1,299", "1,299.00") OR plain numbers
# ("129", "1299", "49.97"). The comma-group alternative uses "+" so plain
# 4+ digit prices fall through to the second alternative intact — the previous
# pattern truncated "1,299" to "1" and "$1,299.00" to "$1,29".
_PRICE_AMT = r"(?:\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)"

# Prefix-symbol currencies ($ £ € ₹, plus Rs / PKR / INR / AED / SAR written
# before the number) and suffix currency CODES written after the number
# ("2,499 PKR", "500 AED") — common on non-western / template storefronts that
# route to the Unknown analyzer.
_PRICE_PREFIX_RE = re.compile(
    rf"(?P<cur>\$|£|€|₹|rs\.?|pkr|inr|aed|sar)\s*(?P<amt>{_PRICE_AMT})",
    re.I,
)
_PRICE_SUFFIX_RE = re.compile(
    rf"(?P<amt>{_PRICE_AMT})\s*(?P<cur>PKR|INR|AED|SAR|BDT|LKR|NPR|MYR|THB|IDR|PHP|USD|GBP|EUR|Rs\.?)\b",
    re.I,
)


def _price_currency_key(price):
    p = price.lower()
    if price.startswith("$") or "usd" in p:
        return "USD"
    if price.startswith("£") or "gbp" in p:
        return "GBP"
    if price.startswith("€") or "eur" in p:
        return "EUR"
    if "₹" in price or "inr" in p:
        return "INR"
    if "pkr" in p or p.startswith("rs"):
        return "PKR"
    return "OTHER"


def extract_prices(text):
    if not text:
        return []

    prices = []

    for m in _PRICE_PREFIX_RE.finditer(text):
        price = normalize_price(f"{m.group('cur')}{m.group('amt')}")
        if price:
            prices.append(price)

    for m in _PRICE_SUFFIX_RE.finditer(text):
        price = normalize_price(f"{m.group('amt')} {m.group('cur').upper()}")
        if price:
            prices.append(price)

    # Dominant-currency filter: if >70% of prices are a single currency, drop the
    # minority currencies — they're typically locale-selector noise (a shop shows
    # its catalogue in one currency; stray others are region switchers).
    if prices:
        buckets = {}
        for p in prices:
            buckets.setdefault(_price_currency_key(p), []).append(p)
        dominant = max(buckets.values(), key=len)
        if len(dominant) / len(prices) > 0.70:
            prices = dominant

    return unique_list(prices)


def is_bad_link(href):
    href_l = (href or "").lower()

    return any(x in href_l for x in [
        "mailto:",
        "tel:",
        "javascript:",
        "#",
        "/cart",
        "/checkout",
        "/account",
        "/login",
        "/wishlist",
        "/privacy",
        "/terms",
        "/returns",
        "/shipping",
        "/help"
    ])


def is_bad_category_link(text, href):
    text_l = (text or "").lower()
    href_l = (href or "").lower()

    bad_terms = [
        "help",
        "contact",
        "feedback",
        "accessibility",
        "shipping",
        "returns",
        "membership",
        "sign in",
        "signin",
        "login",
        "register",
        "privacy",
        "terms",
        "faq",
        "orders",
        "order status",
        "size chart",
        "size charts",
        "cancellation",
        "promo",
        "discount",
        "store locator",
        "find a store",
        "payment",
        "address",
        "dashboard",
        "profile"
    ]

    return any(term in text_l or term in href_l for term in bad_terms)


def looks_like_product_url(href):
    href_l = (href or "").lower()

    bad_product_terms = [
        "/blog/",
        "/guide/",
        "/gift",
        "/calendar",
        "/playbooks/",
        "/rewards",
        "/shipping",
        "/account",
        "/support",
        "/help",
        "/discover",
        "/technology/",
        "/sports/",
        "/t/",
        "/size-guide",
        "/sitemap",
        "/affiliate",
        "/corporate",
        "/student",
        "/change-location",
        "about."
    ]

    if any(x in href_l for x in bad_product_terms):
        return False

    product_url_signals = [
        "/product/",
        "/products/",
        "/product-page/",
        "/item/",
        "/pd/",
        "/p/",
        ".html"
    ]

    if any(x in href_l for x in product_url_signals):
        return True

    # "/shop/product-slug" pattern — retailers like Urban Outfitters use /shop/<product-slug>.
    # Only treat as a product URL when the slug has 4+ hyphen-separated parts; that rules out
    # short category slugs (/shop/sale, /shop/womens-tops) while catching specific product
    # names (/shop/bdg-short-sleeve-spill-the-tee, /shop/uo-petal-kitten-heel-sandal).
    if "/shop/" in href_l:
        slug = href_l.split("/shop/", 1)[-1].split("?")[0].split("/")[0]
        if len(slug.split("-")) >= 4:
            return True

    return False


def looks_like_category_url(href):
    href_l = (href or "").lower()

    category_signals = [
        "/collections/",
        "/collection/",
        "/category/",
        "/categories/",
        "/product-category/",
        "/shop/",
        "/store/",
        "/catalog/",
        "/w/",
        "/c/",
        "/men",
        "/women",
        "/kids",
        "/sale",
        "/new-arrivals",
        "/best-sellers",
        "/clothing",
        "/shoes",
        "/accessories",
        "/sports",
        "/running",
        "/training",
        "/lifestyle",
        "/basketball",
        "/football",
        "/golf",
        "/soccer"
    ]

    return any(x in href_l for x in category_signals)


def is_valid_product(product):
    title = clean_text(product.get("title"))
    url = product.get("url") or ""
    image = product.get("image")
    price = product.get("price")
    all_prices = product.get("allPrices") or []

    url_l = url.lower()
    title_l = title.lower()

    if not url:
        return False

    bad_titles = {
        "filter",
        "sort",
        "filter/sort",
        "size guide",
        "sitemap",
        "student discount",
        "affiliates",
        "corporate sales",
        "ua community",
        "investor relations",
        "ua newsroom",
        # Generic CTA / button labels that are never product names
        "view product",
        "view item",
        "shop now",
        "buy now",
        "add to cart",
        "add to bag",
        "add to basket",
        "learn more",
        "see details",
        "shop the look",
        "quick view",
        "quick add",
        "select options",
        "choose options",
        "out of stock",
        "notify me",
        "coming soon",
        "see more",
        "load more",
        "view all",
    }

    if title_l in bad_titles:
        return False

    bad_url_terms = [
        "/t/",
        "/help",
        "/shipping",
        "/returns",
        "/account",
        "/rewards",
        "/playbooks",
        "/discover",
        "/technology",
        "/gift",
        "/calendar",
        "/sitemap",
        "/size-guide",
        "/affiliate",
        "/corporate",
        "/unidays",
        "/change-location",
        "about."
    ]

    if any(term in url_l for term in bad_url_terms):
        return False

    if not looks_like_product_url(url):
        return False

    if not title and not image and not price and not all_prices:
        return False

    return True


def extract_collection_heading(soup):
    h1 = soup.find("h1")

    if h1:
        return clean_text(h1.get_text(" ", strip=True))

    og_title = soup.find("meta", property="og:title")

    if og_title:
        return clean_text(og_title.get("content"))

    if soup.title and soup.title.string:
        return clean_text(soup.title.string)

    return None


def improve_title_from_url(title, url):
    if not title or len(title) > 8:
        return title

    url_l = url.lower()

    if "/pd/" not in url_l and "/p/" not in url_l:
        return title

    slug = url_l.split("/pd/")[-1].split("/p/")[-1].split("?")[0].split("#")[0]
    slug = slug.split("/")[-2] if "/" in slug else slug

    slug = re.sub(r"[-_]+", " ", slug)
    slug = re.sub(r"\b\d+\b", "", slug)
    slug = clean_text(slug)

    if not slug:
        return title

    words = [w.capitalize() for w in slug.split()]
    improved = " ".join(words)

    if title.lower() not in improved.lower():
        return title

    return improved


def extract_product_cards(soup, base_url):
    cards = []

    selectors = [
        ".product",
        ".product-card",
        ".grid-product",
        ".collection-item",
        ".woocommerce-LoopProduct-link",
        "li.product",
        "[class*='product-card']",
        "[class*='product-item']",
        "[class*='product-tile']",
        "[class*='product-grid']",
        "[data-product-id]",
        "[data-testid*='product']",
        "[data-hook*='product']"
    ]

    seen_links = set()
    seen_base_paths = set()  # dedup same product in multiple ?color= / ?size= variants

    for selector in selectors:
        for card in soup.select(selector):
            link_tag = card.find("a", href=True)
            href = link_tag.get("href") if link_tag else None

            if not href or is_bad_link(href):
                continue

            full_url = urljoin(base_url, href)
            clean_url = full_url.split("#")[0]

            # Deduplicate by URL path without query string so that the same product
            # in multiple colour variants (?color=004, ?color=050 …) is counted once.
            _base_path = clean_url.split("?")[0]
            if _base_path in seen_base_paths:
                continue
            seen_base_paths.add(_base_path)

            if clean_url in seen_links:
                continue

            seen_links.add(clean_url)

            title = None

            title_candidates = card.select(
                """
                h1, h2, h3, h4,
                .product-title,
                .product__title,
                .product-name,
                .name,
                .woocommerce-loop-product__title,
                [class*='title'],
                [class*='name'],
                [data-test-id*='title'],
                [data-testid*='title'],
                [data-hook*='title']
                """
            )

            for candidate in title_candidates:
                text = clean_text(candidate.get_text(" ", strip=True))

                if text and 3 <= len(text) <= 220:
                    title = text
                    break

            if not title and link_tag:
                link_text = clean_text(link_tag.get_text(" ", strip=True))

                if link_text and 3 <= len(link_text) <= 220:
                    title = link_text

            image = None
            img = card.find("img")

            if img:
                image = (
                    img.get("src")
                    or img.get("data-src")
                    or img.get("data-lazy-src")
                    or img.get("srcset")
                )

                if image and "," in image:
                    image = image.split(",")[0].strip().split(" ")[0]

                if image and image.startswith("data:image"):
                    image = None

                if image:
                    image = urljoin(base_url, image)

            card_text = clean_text(card.get_text(" ", strip=True))
            prices = extract_prices(card_text)

            title = improve_title_from_url(title, clean_url)

            # Strip trailing price text that gets concatenated when the <a> tag's
            # full text is used as a fallback title (e.g. "Product Name $ 88" or
            # "Product Name Sale Price $ 49 Regular Price $ 98").
            if title:
                title = re.sub(
                    r'\s+(?:Sale\s+Price\s+)?\$\s*\d.*$',
                    '',
                    title,
                    flags=re.I,
                ).strip() or title

            # --- Short description: first <p> or description element in the card ---
            short_desc = None
            for desc_sel in [
                "p.product-description", "p.description", "[class*='description'] p",
                "[class*='subtitle']", "[class*='short-desc']", "p",
            ]:
                desc_el = card.select_one(desc_sel)
                if desc_el:
                    dt = clean_text(desc_el.get_text(" ", strip=True))
                    # Must be real descriptive text: 10–300 chars, not a price or title
                    if dt and 10 <= len(dt) <= 300 and dt != title and not dt.startswith("$"):
                        short_desc = dt
                        break

            # --- Variant count + colour swatches ---
            variant_count = None
            swatches = []
            _swatch_noise_re = re.compile(
                r"^(shop\s+by|select\s+(a\s+)?|choose\s+|filter\s+|all\s+colo(?:u)?r)",
                re.I,
            )
            # Count color/size swatch elements and extract their labels
            swatch_els = card.select(
                "[class*='swatch'], [class*='color-option'], [class*='color-dot'], "
                "[class*='variant'], [data-color], [data-variant], "
                "[class*='color-circle'], [class*='color-chip'], "
                "[data-swatch], [data-swatch-handle], [data-color-swatch], "
                "[class*='colorSwatch'], [class*='colourSwatch'], "
                "[class*='color-swatch'], [class*='colour-swatch'], "
                "input[type='radio'][name*='color' i], "
                "input[type='radio'][name*='colour' i]"
            )
            if swatch_els:
                variant_count = len(swatch_els)
                _seen_sw: set = set()
                for _sel in swatch_els:
                    _lbl = (
                        _sel.get("data-swatch")
                        or _sel.get("data-color-swatch")
                        or _sel.get("data-color")
                        or _sel.get("data-colour")
                        or _sel.get("aria-label")
                        or _sel.get("title")
                        or _sel.get("value")
                        or _sel.get_text(strip=True)
                    )
                    if not _lbl:
                        continue
                    _lbl = _lbl.strip()
                    if not _lbl or len(_lbl) > 60:
                        continue
                    if _swatch_noise_re.match(_lbl):
                        continue
                    _key = _lbl.lower()
                    if _key in _seen_sw:
                        continue
                    _seen_sw.add(_key)
                    _img_el = _sel.select_one("img") or (_sel if _sel.name == "img" else None)
                    _img_src = None
                    if _img_el:
                        _img_src = (
                            _img_el.get("src")
                            or _img_el.get("data-src")
                            or _img_el.get("data-lazy-src")
                        )
                    swatches.append({"label": _lbl, "imageUrl": _img_src})
            else:
                # Look for "X colors" or "X options" text in the card
                _vc_match = re.search(
                    r"(\d+)\s+(?:color(?:s|ways)?|option(?:s)?|style(?:s)?|variant(?:s)?)",
                    card_text, re.I
                )
                if _vc_match:
                    try:
                        variant_count = int(_vc_match.group(1))
                    except ValueError:
                        pass

            # --- Discount: compare two prices from the card ---
            card_discount = None
            if len(prices) >= 2:
                try:
                    p1 = float(re.sub(r"[^\d.]", "", prices[0]))
                    p2 = float(re.sub(r"[^\d.]", "", prices[1]))
                    higher, lower = (p1, p2) if p1 > p2 else (p2, p1)
                    if higher > lower > 0:
                        saved   = round(higher - lower, 2)
                        percent = round((saved / higher) * 100)
                        card_discount = {
                            "percent":       percent,
                            "savedAmount":   saved,
                            "originalPrice": higher,
                            "currentPrice":  lower,
                        }
                except (ValueError, ZeroDivisionError):
                    pass
            if card_discount is None:
                card_discount = "unfetched"

            product = {
                "title": title,
                "url": clean_url,
                "image": image,
                "price": prices[0] if prices else "unfetched",
                "allPrices": prices[:5] if prices else "unfetched",
                "shortDescription": short_desc if short_desc else "unfetched",
                "variantCount": variant_count if variant_count is not None else "unfetched",
                "swatches": swatches if swatches else "unfetched",
                "discount": card_discount,
            }

            if is_valid_product(product):
                cards.append(product)

    # ── Fallback: LINK-based product cards (platform-agnostic). Custom / headless
    #    storefronts (React/Tailwind SPAs like stdbeauty) don't use any known
    #    product-card class, so the selector pass above finds nothing. But every
    #    product is still a LINK to a product page, so treat each such link's
    #    container as a card and pull title / price / image from it. Runs only when
    #    the selector pass came up short, so it never overrides a clean structured read.
    if len(cards) < 3:
        for a in soup.find_all("a", href=True):
            href = a.get("href")
            if not href or is_bad_link(href) or not looks_like_product_url(href):
                continue
            full_url = urljoin(base_url, href).split("#")[0]
            base_path = full_url.split("?")[0]
            if base_path in seen_base_paths or full_url in seen_links:
                continue

            # Card container = walk up to the nearest ancestor that also holds an
            # image or a price (i.e. the visual product tile), max 4 levels.
            container = a
            for _ in range(4):
                parent = container.find_parent()
                if parent is None:
                    break
                container = parent
                if container.find("img") or extract_prices(clean_text(container.get_text(" ", strip=True))):
                    break

            ctext = clean_text(container.get_text(" ", strip=True))
            prices = extract_prices(ctext)

            # Title: the link's own text, else an image alt, else a heading nearby.
            title = clean_text(a.get_text(" ", strip=True))
            if not title:
                _img = container.find("img")
                if _img and _img.get("alt"):
                    title = clean_text(_img.get("alt"))
            if not title:
                _h = container.find(["h1", "h2", "h3", "h4"])
                if _h:
                    title = clean_text(_h.get_text(" ", strip=True))

            image = None
            _img = container.find("img")
            if _img:
                image = _img.get("src") or _img.get("data-src") or _img.get("data-srcset")
                if not image and _img.get("srcset"):
                    image = _img.get("srcset").split(" ")[0]
                if image:
                    image = urljoin(base_url, image)

            product = {
                "title": title,
                "url": full_url,
                "image": image,
                "price": prices[0] if prices else "unfetched",
                "allPrices": prices[:5] if prices else "unfetched",
                "shortDescription": "unfetched",
                "variantCount": "unfetched",
                "swatches": "unfetched",
                "discount": "unfetched",
            }
            if is_valid_product(product):
                seen_base_paths.add(base_path)
                seen_links.add(full_url)
                cards.append(product)

    return cards


def extract_product_links(soup, base_url):
    links = []
    seen_links      = set()   # full URL dedup (existing logic below)
    seen_base_paths = set()   # path-only dedup — prevents same product in
                               # different ?color= variants counting as separate products

    for a in soup.find_all("a", href=True):
        href = a.get("href")

        if not href or is_bad_link(href):
            continue

        if not looks_like_product_url(href):
            continue

        full_url = urljoin(base_url, href)
        clean_url = full_url.split("#")[0]

        # Deduplicate by URL path without query string so that the same product
        # in multiple color variants (?color=004, ?color=050 …) is counted once.
        _base_path = clean_url.split('?')[0]
        if _base_path in seen_base_paths:
            continue
        seen_base_paths.add(_base_path)

        if clean_url in seen_links:
            continue
        seen_links.add(clean_url)

        text = clean_text(a.get_text(" ", strip=True))

        # Strip markdown heading markers (## from H2 elements nested inside <a>)
        # and ecommerce badge prefixes that get prepended to the actual product name.
        # e.g. "Top Rated ## BDG Short Sleeve Tee" → "BDG Short Sleeve Tee"
        # e.g. "## Kimchi Blue Keepsake Maxi Dress" → "Kimchi Blue Keepsake Maxi Dress"
        _badge_re = re.compile(
            r'^(?:Top Rated|Best Seller|New Arrival|New|Sale|Popular|'
            r'Editor\'s Pick|Staff Pick|Fan Fave|Trending|Limited)\s*',
            re.I
        )
        text = _badge_re.sub('', text).strip()
        text = re.sub(r'^#+\s*', '', text).strip()  # strip leading ## / ### markers

        product = {
            "title": text if text and 3 <= len(text) <= 220 else None,
            "url": clean_url,
            "image": None,
            "price": None,
            "allPrices": []
        }

        product["title"] = improve_title_from_url(product["title"], clean_url)

        if is_valid_product(product):
            links.append(product)

    return unique_list_by_url(links)


def extract_category_links(soup, base_url):
    links = []

    for a in soup.find_all("a", href=True):
        href = a.get("href")

        if not href or is_bad_link(href):
            continue

        text = clean_text(a.get_text(" ", strip=True))

        if not text or len(text) > 90:
            continue

        if is_bad_category_link(text, href):
            continue

        if not looks_like_category_url(href):
            continue

        # Exclude URLs that also match product patterns (e.g. /shop/<long-slug>?color=004)
        if looks_like_product_url(href):
            continue

        full_url = urljoin(base_url, href)
        clean_url = full_url.split("?")[0].split("#")[0]

        links.append({
            "text": text,
            "url": clean_url
        })

    return unique_list_by_url(links)


def filter_relevant_category_links(category_links, collection_title):
    if not collection_title:
        return category_links[:40]

    title_words = set(re.findall(r"[a-z0-9]+", collection_title.lower()))

    priority = []
    secondary = []

    for item in category_links:
        text = (item.get("text") or "").lower()
        url = (item.get("url") or "").lower()

        score = 0

        for word in title_words:
            if len(word) >= 3 and (word in text or word in url):
                score += 3

        if any(x in text or x in url for x in [
            "shoe",
            "running",
            "basketball",
            "training",
            "lifestyle",
            "jordan",
            "sale",
            "new",
            "pants",
            "clothing",
            "men"
        ]):
            score += 1

        if any(x in text for x in [
            "women",
            "kids",
            "girls",
            "boys",
            "baby",
            "bras",
            "socks"
        ]):
            score -= 3

        if score >= 2:
            priority.append(item)
        else:
            secondary.append(item)

    return (priority + secondary)[:40]


def extract_collection_filters(soup):
    filters = []

    filter_selectors = [
        "select",
        ".filter",
        ".filters",
        ".facet",
        ".facets",
        ".sidebar",
        ".woocommerce-widget-layered-nav",
        "[class*='filter']",
        "[class*='facet']"
    ]

    noisy_reject_terms = [
        "skip to",
        "privacy",
        "terms",
        "newsletter",
        "copyright"
    ]

    for selector in filter_selectors:
        for block in soup.select(selector):
            text = clean_text(block.get_text(" ", strip=True))

            if not text:
                continue

            text_l = text.lower()

            if any(term in text_l for term in noisy_reject_terms):
                continue

            if len(text) > 300:
                text = text[:300]

            filters.append(text)

    return unique_list(filters)[:20]


def extract_sorting_options(soup):
    options = []

    for select in soup.find_all("select"):
        select_text = clean_text(select.get_text(" ", strip=True)).lower()
        class_text = " ".join(select.get("class", [])).lower()
        name_text = (select.get("name") or "").lower()
        id_text = (select.get("id") or "").lower()

        sort_context = f"{select_text} {class_text} {name_text} {id_text}"

        if "sort" not in sort_context and "order" not in sort_context:
            continue

        for option in select.find_all("option"):
            text = clean_text(option.get_text(" ", strip=True))

            if text:
                options.append(text)

    for a in soup.find_all("a", href=True):
        href = a.get("href") or ""
        text = clean_text(a.get_text(" ", strip=True))

        href_l = href.lower()
        text_l = text.lower()

        if "srule=" in href_l or "sort=" in href_l or "orderby=" in href_l:
            if text and len(text) <= 60:
                options.append(text)

        if text_l in [
            "sort by",
            "now trending",
            "best sellers",
            "price low to high",
            "price high to low",
            "price (low - high)",
            "price (high - low)",
            "top rated",
            "top sellers",
            "newest",
            "new arrivals",
            "recommended"
        ]:
            options.append(text)

    return unique_list(options)


def is_pagination_url(href):
    href_l = (href or "").lower()

    bad_pagination_terms = [
        "filter",
        "size",
        "color",
        "prefn",
        "prefv",
        "sort",
        "srule",
        "gender",
        "price",
        "rating"
    ]

    if any(term in href_l for term in bad_pagination_terms):
        return False

    good_pagination_terms = [
        "page=",
        "p=",
        "offset=",
        "start=",
        "/page/",
        "pagination"
    ]

    return any(term in href_l for term in good_pagination_terms)


def detect_pagination(soup, base_url):
    page_links = []

    for a in soup.find_all("a", href=True):
        href = a.get("href") or ""
        text = clean_text(a.get_text(" ", strip=True))

        if not text:
            continue

        text_l = text.lower()

        if text_l in ["next", "previous", "prev"] or text.isdigit():
            if is_pagination_url(href):
                page_links.append({
                    "text": text,
                    "url": urljoin(base_url, href)
                })

    page_text = clean_text(soup.get_text(" ", strip=True))

    total_products_text = None

    patterns = [
        r"showing\s+\d+\s*[–-]\s*\d+\s+of\s+\d+",
        r"\d+\s+products",
        r"\d+\s+items",
        r"\d+\s+results"
    ]

    for pattern in patterns:
        match = re.search(pattern, page_text, re.I)

        if match:
            total_products_text = match.group(0)
            break

    return {
        "detected": bool(page_links or total_products_text),
        "totalProductsText": total_products_text,
        "pageLinks": page_links[:20]
    }


def extract_products_from_headings(soup, base_url, existing_urls=None):
    """
    Extract product-like entries from H2/H3 headings when DOM product cards are absent.
    Handles Jina-rendered / JavaScript-heavy collection pages (e.g. kookaburra.com/cricket/)
    where products appear as bold headings in the Jina markdown but have no standard DOM cards.

    Returns a list of lightweight product dicts (title only, no URL/image since those
    aren't reliably available in this fallback mode).
    """
    existing_urls = existing_urls or set()
    products = []
    seen_titles = set()

    # Words that mark non-product headings
    _NAV_HEADINGS = {
        "filter", "sort", "view all", "see all", "shop all", "shop by",
        "about", "contact", "menu", "navigation", "footer", "header",
        "categories", "brands", "quick view", "newsletter", "subscribe",
        "free shipping", "payment", "returns", "faq", "help",
        # Geographic / regional locale selectors (footer menus, region pickers)
        "asia pacific", "middle east", "north america", "south america",
        "latin america", "central america", "europe", "africa", "oceania",
        "southeast asia", "south asia", "east asia", "north africa",
        "sub-saharan africa", "australia", "new zealand", "canada",
        "united states", "united kingdom", "select region", "select country",
        "choose region", "choose country", "global", "worldwide",
    }
    # Min/max word count for a product-name heading
    _MIN_WORDS = 2
    _MAX_WORDS = 10

    for h in soup.find_all(["h2", "h3"]):
        title = clean_text(h.get_text(" ", strip=True))
        if not title:
            continue

        words = title.split()
        if not (_MIN_WORDS <= len(words) <= _MAX_WORDS):
            continue

        title_l = title.lower()

        # Skip clearly non-product headings
        if any(nav in title_l for nav in _NAV_HEADINGS):
            continue

        # Must start with an uppercase letter (product names are typically proper-cased)
        if not title[0].isupper():
            continue

        # Skip headings that are pure numbers or short codes
        if re.match(r'^[\d\s\-/]+$', title):
            continue

        key = title_l
        if key in seen_titles:
            continue
        seen_titles.add(key)

        # Try to find a price adjacent to this heading
        price = None
        next_sib = h.find_next_sibling()
        if next_sib:
            sib_text = clean_text(next_sib.get_text(" ", strip=True))
            prices = extract_prices(sib_text)
            if prices:
                price = prices[0]

        products.append({
            "title": title,
            "url": None,
            "image": None,
            "price": price,
            "allPrices": [price] if price else [],
            "_source": "heading_fallback"
        })

        if len(products) >= 60:
            break

    return products


def detect_dynamic_rendering(html, product_count, price_count, category_count, level1, page_text=None):
    html_l = (html or "").lower()
    platform = (level1 or {}).get("platform", "")

    framework_signals = [
        "__next_data__",
        "/_next/static",
        "__nuxt__",
        "webpack",
        "hydration",
        "react",
        "next.js",
        "vercel"
    ]

    has_framework_signal = any(x in html_l for x in framework_signals)

    is_framework_platform = platform in [
        "Next.js / React",
        "React",
        "Vue"
    ]

    # Framework-based dynamic rendering (existing logic)
    if (
        (has_framework_signal or is_framework_platform)
        and product_count == 0
        and (price_count > 0 or category_count > 0)
    ):
        return True

    # Text-based: filter facets + product-count patterns with 0 products detected.
    # Catches Jina-rendered pages like kookaburra.com/cricket/ where "Filter Results"
    # and "(37)" count facets appear in the text but products are JS-rendered.
    if product_count == 0 and page_text:
        text_l = page_text.lower()
        has_filter_ui = (
            "filter results" in text_l
            or "refine results" in text_l
            or ("filter by" in text_l and "sort by" in text_l)
        )
        has_count_facets = bool(re.search(r'[A-Za-z][A-Za-z\s\-]{2,30}\s*\(\d{1,4}\)', text_l))
        if has_filter_ui or has_count_facets:
            return True

    return False


def infer_intended_page_type_from_url(url):
    """
    Guess what kind of page a URL was meant to be, even if it's now blocked/empty.
    Used to populate `intendedPageType` in blocked result objects.
    """
    url_l = (url or "").lower().split("?")[0].split("#")[0]

    collection_signals = [
        "/collections/", "/collection/", "/c/", "/w/", "/category/",
        "/categories/", "/product-category/", "/shop/", "/catalog/",
        "/best-sellers", "/new-arrivals", "/sale", "/leggings",
        "/hoodies", "/shoes", "/clothing", "/accessories",
    ]
    if any(x in url_l for x in collection_signals):
        return "collection"

    category_landing_signals = [
        "/women", "/men", "/kids", "/girls", "/boys",
        "/womens", "/mens", "/juniors", "/baby", "/toddler",
        "/woman-", "/man-", "-l1", "-l2",
    ]
    if any(x in url_l for x in category_landing_signals):
        return "category_landing"

    if any(x in url_l for x in ["/", "home", "index"]) and url_l.count("/") <= 3:
        return "homepage"

    return "unknown"


# ---------------------------------------------------------------------------
# Blocked / unusable content detection
# ---------------------------------------------------------------------------

# Titles / first-H1 text that unmistakably signals the crawl returned an
# error page rather than the intended content.
_BLOCKED_TITLE_PATTERNS = re.compile(
    r'\b(?:access\s+denied|access\s+forbidden|you\s+don\'?t\s+have\s+permission'
    r'|just\s+a\s+moment|robot\s+or\s+human|checking\s+your\s+browser'
    r'|security\s+check|please\s+enable\s+javascript|enable\s+cookies'
    r'|403\s+forbidden|404\s+not\s+found|too\s+many\s+requests'
    r'|rate\s+limit|service\s+unavailable|gateway\s+timeout)\b',
    re.I,
)

# Patterns in the raw HTML body that indicate error/blocked responses
_BLOCKED_BODY_PATTERNS = re.compile(
    r'(?:'
    r'"message"\s*:\s*"Bad\s+Request"'       # Lululemon JSON error
    r'|"errorCode"\s*:\s*"GE\d+'             # Lululemon error code
    r'|errors\.edgesuite\.net'               # Akamai error ref
    r'|Reference\s+#\d+\.\d+'               # Akamai reference block
    r'|ak_bmsc'                              # Akamai bot-management cookie
    r'|_abck='                               # Akamai bot-management cookie
    r'|Unable\s+to\s+give\s+you\s+access'
    r'|This\s+page\s+is\s+protected\s+by\s+Cloudflare'
    r'|DDoS\s+protection\s+by'
    r'|verify\s+that\s+you\'?re?\s+human'
    r')',
    re.I,
)


def detect_blocked_or_unusable_content(html, url, soup=None):
    """
    Determine whether the fetched HTML represents a blocked/unusable page rather
    than the intended content. Returns a tuple:
        (is_blocked: bool, blocked_reason: str|None, intended_page_type: str)

    blocked_reason values: "access_denied" | "bad_request" | "empty_shell" |
                           "bot_protection" | "json_error"
    """
    html_s = html or ""
    intended = infer_intended_page_type_from_url(url)

    # --- 1. Null / completely empty HTML ---
    if not html_s.strip():
        return True, "empty_shell", intended

    # --- 2. Body-level error patterns (scanned in first 4000 chars) ---
    head_chunk = html_s[:4000]
    if _BLOCKED_BODY_PATTERNS.search(head_chunk):
        if '"message"' in head_chunk and '"errorCode"' in head_chunk:
            return True, "bad_request", intended
        if "ak_bmsc" in head_chunk or "_abck=" in head_chunk or "errors.edgesuite.net" in head_chunk:
            return True, "bot_protection", intended
        return True, "bot_protection", intended

    # --- 3. Parse soup once if not provided ---
    if soup is None:
        try:
            soup = BeautifulSoup(html_s, "lxml")
        except Exception:
            return True, "empty_shell", intended

    # --- 4. Title / H1 blocked wording ---
    title_text = ""
    if soup.title and soup.title.string:
        title_text = clean_text(soup.title.string)

    h1_tag = soup.find("h1")
    h1_text = clean_text(h1_tag.get_text(" ", strip=True)) if h1_tag else ""

    check_text = f"{title_text} {h1_text}".strip()

    # Artifact from JSON being used as title (Lululemon `{` as title)
    if title_text and title_text.strip().startswith("{"):
        return True, "json_error", intended

    if check_text and _BLOCKED_TITLE_PATTERNS.search(check_text):
        reason = "access_denied" if "denied" in check_text.lower() or "permission" in check_text.lower() else "bot_protection"
        return True, reason, intended

    # --- 5. Empty shell: nothing useful in page ---
    body_text = clean_text(soup.get_text(" ", strip=True))

    has_title = bool(title_text and len(title_text) > 3 and not title_text.startswith("{"))
    has_h1 = bool(h1_text and len(h1_text) > 3)
    has_body = bool(body_text and len(body_text) > 80)
    has_links = bool(soup.find("a", href=True))

    if not has_title and not has_h1 and not has_body and not has_links:
        return True, "empty_shell", intended

    # Very short body with no meaningful content (Zara anti-bot shell)
    if len(body_text) < 120 and not has_h1:
        return True, "empty_shell", intended

    return False, None, intended


# ---------------------------------------------------------------------------
# Text-based product extraction (for JS-heavy PLPs like Under Armour)
# ---------------------------------------------------------------------------

_TEXT_PRODUCT_REJECT_TERMS = {
    "filter", "sort", "product type", "features", "customer rating",
    "sports", "color", "colour", "size", "size range", "fit", "collection",
    "price", "live chat", "need help", "about", "payment", "order history",
    "profile", "locations nearby", "ua social", "footer", "support",
    "customer service", "accessibility", "sign in", "sign up", "login",
    "register", "privacy", "terms", "help", "faq", "shipping", "returns",
    "new arrivals", "best sellers", "sale", "view all", "see all", "shop all",
    "shop by", "gender", "rating", "preferred sizes", "saved items",
    "newsletter", "subscribe", "gift card", "gift cards",
}

_TEXT_PRODUCT_PRICE_RE = re.compile(
    r'^(?:.*?(?:new\s+colors?|save\s+this\s+item|\+\d+\s+new\s+colors?)\s+)?'
    r'([A-Z][^$£€\n]{5,80}?)\s+'
    r'([$£€]\s?\d+(?:[,.]\d{1,2})?)'
    r'(?:\s+([$£€]\s?\d+(?:[,.]\d{1,2})?))?',
    re.MULTILINE,
)


def extract_products_from_text(page_text, max_products=80):
    """
    Parse product-name + price pairs from Jina/text-rendered collection pages.
    Handles Under Armour style:
      "UA Icon Fleece Men's Hoodie $60 $54.97"
      "Save this item +25 New Colors UA Rival Fleece Men's Hoodie $55 $49.97"
    Returns a list of lightweight product dicts.
    """
    if not page_text:
        return []

    products = []
    seen_titles = set()

    for line in page_text.splitlines():
        line = line.strip()
        if not line or len(line) < 8:
            continue

        m = _TEXT_PRODUCT_PRICE_RE.match(line)
        if not m:
            continue

        raw_title = clean_text(m.group(1))
        price1 = normalize_price(m.group(2))
        price2 = normalize_price(m.group(3)) if m.group(3) else None

        if not raw_title or len(raw_title) < 5:
            continue

        words = raw_title.split()
        if not (2 <= len(words) <= 12):
            continue

        title_l = raw_title.lower()
        if any(bad in title_l for bad in _TEXT_PRODUCT_REJECT_TERMS):
            continue

        if not raw_title[0].isupper():
            continue

        key = title_l
        if key in seen_titles:
            continue
        seen_titles.add(key)

        # First price is usually original, second is sale — pick lower as current
        if price1 and price2:
            try:
                v1 = float(re.sub(r'[^\d.]', '', price1))
                v2 = float(re.sub(r'[^\d.]', '', price2))
                current = price1 if v1 <= v2 else price2
                compare = price1 if v1 > v2 else price2
            except Exception:
                current, compare = price1, price2
        else:
            current, compare = price1, None

        products.append({
            "title": raw_title,
            "url": None,
            "image": None,
            "price": current,
            "compareAtPrice": compare,
            "allPrices": [p for p in [current, compare] if p],
            "_source": "text_pattern",
        })

        if len(products) >= max_products:
            break

    return products


def detect_ecommerce_collection_context(url, soup, page_type, products, prices, category_links):
    url_l = (url or "").lower()

    title = clean_text(soup.title.string) if soup.title and soup.title.string else ""
    meta_description = get_meta_content(soup, name="description") or ""
    canonical_tag = soup.find("link", rel="canonical")
    canonical = canonical_tag.get("href") if canonical_tag else ""

    combined = f"{url_l} {title} {meta_description} {canonical}".lower()

    score = 0
    signals = []

    if products:
        score += 4
        signals.append("products_detected")

    if prices:
        score += 2
        signals.append("prices_detected")

    if category_links:
        score += 2
        signals.append("category_links_detected")

    if page_type == "collection":
        score += 2
        signals.append("page_type_collection")

    ecommerce_terms = [
        "shop", "shopping", "store", "buy", "sale", "products", "collection",
        "collections", "speakers", "shoes", "clothing", "accessories", "sound systems"
    ]

    term_hits = 0
    for term in ecommerce_terms:
        if term in combined:
            term_hits += 1

    if term_hits:
        score += min(4, term_hits)
        signals.append("ecommerce_seo_terms")

    if "/shop" in combined:
        score += 3
        signals.append("shop_url_or_canonical")

    return {
        "hasEcommerceSignals": score >= 3,
        "ecommerceScore": score,
        "ecommerceSignals": unique_list(signals)
    }


def estimate_extraction_confidence(product_count, category_count, price_count, dynamic_rendering_likely):
    score = 0

    if product_count > 0:
        score += 0.45

    if product_count >= 6:
        score += 0.20

    if category_count > 0:
        score += 0.15

    if price_count > 0:
        score += 0.10

    if dynamic_rendering_likely:
        score = max(score, 0.35)

    return round(min(0.95, max(0.25, score)), 2)


def _blocked_collection_result(self, url, html, headers, page_type, level1,
                               blocked_reason, intended_page_type):
    """Return a structured blocked result instead of running full extraction."""
    result = self.base_result(url, html, headers, page_type, level1)
    result["success"] = False
    result["crawlBlocked"] = True
    result["pageType"] = "blocked"
    result["page"]["pageType"] = "blocked"
    result["blockedReason"] = blocked_reason
    result["intendedPageType"] = intended_page_type
    result["collection"] = None
    result["products"] = []
    result["ecommerce"] = {
        "hasEcommerceSignals": False,
        "crawlBlocked": True,
        "blockedReason": blocked_reason,
    }
    result["content"] = {
        "heading": None,
        "dynamicRenderingLikely": False,
        "note": f"Page could not be extracted: {blocked_reason.replace('_', ' ')}.",
    }
    result["source"] = {
        "extractor": "Unknown Collection Extractor",
        "extractorFamily": "Unknown",
        "platformDetected": (level1 or {}).get("platform", "Unknown"),
        "confidence": 0.0,
    }
    return result


def analyze_unknown_collection(self, url, html, headers, page_type, level1):
    # --- Blocked / unusable content guard ---
    # Must run before any extraction to avoid producing garbage output for
    # "Access Denied", bad-request JSON, or empty anti-bot shells.
    is_blocked, blocked_reason, intended_page_type = detect_blocked_or_unusable_content(
        html, url
    )
    if is_blocked:
        return _blocked_collection_result(
            self, url, html, headers, page_type, level1,
            blocked_reason, intended_page_type
        )

    result = self.base_result(url, html, headers, page_type, level1)

    soup = BeautifulSoup(html or "", "lxml")

    heading = extract_collection_heading(soup)

    product_cards = extract_product_cards(soup, url)
    product_links = extract_product_links(soup, url)

    raw_category_links = extract_category_links(soup, url)
    category_links = filter_relevant_category_links(
        raw_category_links,
        heading
    )

    merged_products = product_cards[:]
    existing_urls = {p.get("url") for p in merged_products}

    for link in product_links:
        if link.get("url") not in existing_urls:
            merged_products.append(link)
            existing_urls.add(link.get("url"))

    merged_products = [
        product for product in merged_products
        if is_valid_product(product)
    ]

    # Use full page text (not just scoped) to catch Jina-rendered price/filter text
    page_text = clean_text(soup.get_text(" ", strip=True))
    prices = extract_prices(page_text)

    filters = extract_collection_filters(soup)
    sorting_options = extract_sorting_options(soup)
    pagination = detect_pagination(soup, url)

    # Follow numeric pagination (WooCommerce-style /page/N/ and ?paged= links) and
    # merge products from the remaining pages so the full catalog is captured.
    def _unknown_page_products(page_html, page_base):
        _s = BeautifulSoup(page_html or "", "lxml")
        _items = extract_product_cards(_s, page_base) + extract_product_links(_s, page_base)
        return [x for x in _items if is_valid_product(x)]

    _extra_pages, _fetched_all_pages = fetch_extra_pages(url, soup, _unknown_page_products)
    if _extra_pages:
        for _pp in _extra_pages:
            _u = _pp.get("url")
            if _u and _u not in existing_urls:
                merged_products.append(_pp)
                existing_urls.add(_u)
    if isinstance(pagination, dict):
        pagination["fullCatalogFetched"] = _fetched_all_pages

    dynamic_rendering_likely = detect_dynamic_rendering(
        html=html,
        product_count=len(merged_products),
        price_count=len(prices),
        category_count=len(category_links),
        level1=level1,
        page_text=page_text
    )

    # --- Phantom-product check -------------------------------------------
    # Products were found but every card has a generic CTA name ("View Product",
    # "Add to Cart", etc.) AND no prices. This is the fingerprint of a fully
    # client-rendered SPA (React/Vue) where SSR only emits card shells with
    # anchor text but real data lives in JS state we cannot reach.
    # Generic names threshold: >50% generic AND >50% price-less → SPA.
    if not dynamic_rendering_likely and merged_products:
        _GENERIC_CTA_NAMES = {
            "view product", "add to cart", "shop now", "click here",
            "product", "buy now", "see details", "learn more",
        }
        _n_generic = sum(
            1 for p in merged_products
            if (p.get("name") or p.get("title") or "").strip().lower()
            in _GENERIC_CTA_NAMES
        )
        _n_no_price = sum(
            1 for p in merged_products
            if not p.get("price") and not p.get("allPrices")
        )
        _total = len(merged_products)
        if _n_generic / _total > 0.5 and _n_no_price / _total > 0.5:
            dynamic_rendering_likely = True

    # --- Collection card sentinel resolution ----------------------------
    # extract_product_cards() marks missing price/shortDescription/variantCount/discount
    # as "unfetched" because it runs before dynamic_rendering_likely is known.
    # Now that we know whether the page is JS-rendered, demote "unfetched" to None
    # on static pages (the card rendered fully — the field is genuinely absent).
    if not dynamic_rendering_likely:
        _SENTINEL_FIELDS = ("price", "allPrices", "shortDescription", "variantCount", "discount")
        for _card in product_cards:
            for _f in _SENTINEL_FIELDS:
                if _card.get(_f) == "unfetched":
                    _card[_f] = None

    # --- Fallback product extraction chain (when DOM cards/links absent) ---
    # All fallback variables pre-initialised to avoid NameError in later references.
    heading_products = []
    text_products = []
    has_heading_fallback = False
    has_text_fallback = False

    if len(merged_products) == 0 and dynamic_rendering_likely:
        # Attempt 1: H2/H3 headings as product candidates
        heading_products = extract_products_from_headings(soup, url, existing_urls)

        # Attempt 2: line-by-line "Product Name $price $sale" pattern from full text
        if len(heading_products) == 0:
            text_products = extract_products_from_text(page_text)

    has_heading_fallback = bool(heading_products) and len(merged_products) == 0
    has_text_fallback = bool(text_products) and not has_heading_fallback and len(merged_products) == 0

    ecommerce_context = detect_ecommerce_collection_context(
        url=url,
        soup=soup,
        page_type="collection",
        products=merged_products,
        prices=prices,
        category_links=category_links
    )

    # Effective product count for confidence calculation
    _fallback_count = len(heading_products) if has_heading_fallback else (len(text_products) if has_text_fallback else 0)
    extraction_confidence = estimate_extraction_confidence(
        product_count=len(merged_products) or _fallback_count,
        category_count=len(category_links),
        price_count=len(prices),
        dynamic_rendering_likely=dynamic_rendering_likely
    )

    detected_platform = level1.get("platform", "Unknown") if level1 else "Unknown"

    result["platform"] = detected_platform
    result["page"]["pageType"] = "collection"

    # Choose best available product list
    if merged_products:
        _output_products = merged_products[:100]
        _products_detected = len(merged_products)
        _fallback_meta = {}
    elif has_heading_fallback:
        _output_products = heading_products[:60]
        _products_detected = len(heading_products)
        _fallback_meta = {"headingFallback": True, "headingProductsDetected": len(heading_products)}
    elif has_text_fallback:
        _output_products = text_products[:80]
        _products_detected = len(text_products)
        _fallback_meta = {"textFallback": True, "textProductsDetected": len(text_products)}
    else:
        _output_products = []
        _products_detected = 0
        _fallback_meta = {}

    result["collection"] = {
        "title": heading,
        "productsDetected": _products_detected,
        "products": _output_products,
        "categoryLinksDetected": len(category_links),
        "categoryLinks": category_links[:100],
        "pricesDetected": len(prices),
        "samplePrices": prices[:50],
        "filters": filters,
        "sortingOptions": sorting_options,
        "pagination": pagination,
        **_fallback_meta,
    }

    result["content"] = {
        "heading": heading,
        "dynamicRenderingLikely": dynamic_rendering_likely,

        "note": None,
        "collectionName": heading or "",
    }

    result["ecommerce"] = {
        "hasEcommerceSignals": ecommerce_context.get("hasEcommerceSignals", False),
        "ecommerceScore": ecommerce_context.get("ecommerceScore", 0),
        "ecommerceSignals": ecommerce_context.get("ecommerceSignals", []),
        "hasProductCards": len(product_cards) > 0,
        "hasProductLinks": len(product_links) > 0,
        "hasCategoryLinks": len(category_links) > 0,
        "hasPrices": len(prices) > 0,
        "hasFilters": len(filters) > 0,
        "hasSorting": len(sorting_options) > 0,
        "hasPagination": bool(pagination.get("hasNextPage") or pagination.get("totalPages")),
        "dynamicRenderingLikely": dynamic_rendering_likely,
    }

    result["products"] = _output_products
    result["source"] = {
        "extractor": "Unknown Collection Extractor",
        "extractorFamily": "Unknown",
        "platformDetected": detected_platform,
        "confidence": extraction_confidence,
        "pageTypeValidated": True,
        "pageTypeMismatchReason": None,
    }

    return result

