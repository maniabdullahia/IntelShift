import re
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from normalizers.collection_normalizer import normalize_collection_result
from analyzers.unknown.react_hydration import extract_react_hydration_products

from extractors.price_parser import parse_price, detect_currency
from extractors.image_parser import normalize_image_url
from extractors.dom_helpers import clean_text


HEADERS = {
    # A full browser UA — a bare "Mozilla/5.0" gets 403'd by Shopify's bot
    # protection on many stores, which silently dropped us to DOM scraping and
    # produced wrong stock/price data. This matches the main fetcher's UA.
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
}

# CTAs commonly found on collection product cards
_COLLECTION_CTA_PATTERNS = [
    "add to cart",
    "add to bag",
    "quick view",
    "quickview",      # same concept, no space variant
    "quick add",
    "choose options",
    "select options",
    "select shade",
    "select colour",
    "select color",
    "view product",
    "view details",
    "shop now",
    "buy now",
    "sold out",
    "out of stock",
    "notify me",
    "pre-order",
    "pre order",
]

# Tokens that appear in brand names but NOT in collection names.
# "beauty", "makeup", "skincare" etc. are category terms — do NOT include here.
_BRAND_SUFFIX_TOKENS = {
    "pakistan", "store", "official", "online", "shop", "pk", "brand",
    "co", "ltd", "inc", "corp",
}


def _detect_store_currency(html, soup, url=None):
    """Detect the store's base currency from the page HTML.

    Priority order:
    1. Shopify-injected JS variables (window.Shopify.currency, currency_code, etc.)
    2. OG / meta currency tags
    3. DOM price symbol ($ → USD, £ → GBP, € → EUR)
    4. TLD-based heuristic (.pk → PKR, .in → INR, etc.)
    5. Fall back to "USD"
    """
    html_text = html or ""

    # 1. Shopify theme currency JS injection
    _CURRENCY_PATTERNS = [
        r'Shopify\.currency\.active\s*[=:]\s*["\']([A-Z]{3})["\']',
        r'currency_code["\']?\s*:\s*["\']([A-Z]{3})["\']',
        r'window\.currency\s*=\s*["\']([A-Z]{3})["\']',
        r'Shopify\.currency\s*=\s*["\']([A-Z]{3})["\']',
    ]
    for pat in _CURRENCY_PATTERNS:
        m = re.search(pat, html_text)
        if m:
            return m.group(1)

    # 2. Meta / OG tags
    if soup:
        for attr, key in [("property", "og:price:currency"), ("name", "currency")]:
            meta = soup.find("meta", attrs={attr: key})
            if meta and meta.get("content"):
                val = meta["content"].strip().upper()
                if len(val) == 3:
                    return val

    # 3. DOM price symbol scan (first few price elements)
    if soup:
        price_texts = []
        for sel in ["[class*='price']", ".money", "[data-product-price]"]:
            for el in (soup.select(sel) or [])[:5]:
                price_texts.append(el.get_text())
        combined = " ".join(price_texts)
        if "£" in combined:
            return "GBP"
        if "€" in combined:
            return "EUR"
        if "₹" in combined:
            return "INR"
        if "Rs." in combined or "PKR" in combined:
            return "PKR"

    # 4. TLD-based heuristic
    _TLD_CURRENCY = {
        ".com.pk": "PKR", ".pk": "PKR",
        ".co.in": "INR", ".in": "INR",
        ".co.uk": "GBP", ".co.nz": "NZD",
        ".com.au": "AUD", ".ca": "CAD",
        ".ae": "AED", ".sa": "SAR",
        ".de": "EUR", ".fr": "EUR", ".it": "EUR",
        ".es": "EUR", ".nl": "EUR",
        ".jp": "JPY", ".sg": "SGD",
    }
    _url_str = url or ""
    try:
        from urllib.parse import urlparse as _up
        _host = _up(_url_str).netloc.lower() if _url_str else ""
    except Exception:
        _host = ""
    for tld, cur in _TLD_CURRENCY.items():
        if _host.endswith(tld):
            return cur

    return "USD"


def _is_brand_only_name(name, site_name=None):
    """Return True if `name` is just the brand/site name rather than a collection.

    Strategy:
    1. Exact case-insensitive match against known site_name.
    2. Name ends with a pure brand-suffix token (pakistan, store, shop, …)
       AND the name is short (≤ 3 words) — avoids falsely flagging real names.
    """
    if not name:
        return True

    name_norm = name.lower().strip()

    # 1. Exact match
    if site_name and name_norm == (site_name or "").lower().strip():
        return True

    words = name_norm.split()

    # 2. Ends with a brand-suffix token (and is short enough to be a brand name)
    if words and len(words) <= 4 and words[-1] in _BRAND_SUFFIX_TOKENS:
        return True

    return False


def money_from_shopify_cents(value):
    if value is None:
        return None

    try:
        number = float(str(value).strip())
        # A price of 0 means "no price set" (e.g. bridal pieces priced on
        # request), NOT a free product — represent it as absent, never 0.
        if number == 0:
            return None
        return int(number) if number.is_integer() else number
    except Exception:
        return None


def get_collection_handle(url):
    path_parts = urlparse(url).path.strip("/").split("/")

    if "collections" in path_parts:
        index = path_parts.index("collections")
        if len(path_parts) > index + 1:
            return path_parts[index + 1]

    return None


def fetch_shopify_collection_json(url, cookies=None, max_pages=40):
    """Fetch ALL products in a Shopify collection via its products.json endpoint.

    Shopify's products.json is paginated with ?page=N. Different stores use
    different page sizes: many honour limit=250, but a lot of themes/proxies
    cap it at ~30 per page while STILL paginating. So a short page is NOT a
    reliable "last page" signal — we keep paging until a page is empty or
    returns no NEW products (the latter guards against stores that ignore the
    ?page= param and keep echoing page 1). Capped at max_pages so a store that
    ignores pagination can't loop forever.
    """
    handle = get_collection_handle(url)

    if not handle:
        return []

    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"

    # Use cloudscraper (Cloudflare-aware) so bot-protected stores don't 403 the
    # products.json endpoint and silently drop us to the partial DOM render
    # (which only sees the ~30 products the collection page renders up-front).
    # Reused across pages; falls back to plain requests if unavailable.
    try:
        import cloudscraper
        session = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "mobile": False}
        )
    except Exception:
        session = requests
    # Public product JSON — tolerate stale local CA bundles (some envs report
    # valid Shopify certs as "expired") and keep the log clean.
    try:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    except Exception:
        pass

    all_products = []
    seen_ids = set()
    for page in range(1, max_pages + 1):
        json_url = f"{base_url}/collections/{handle}/products.json?limit=250&page={page}"
        try:
            try:
                response = session.get(json_url, headers=HEADERS, cookies=cookies, timeout=25)
            except Exception:
                # Stale local CA bundle can misreport valid certs as expired —
                # retry this page with plain requests + verification off before
                # giving up (public product JSON, safe to skip verify).
                response = requests.get(
                    json_url, headers=HEADERS, cookies=cookies, timeout=25, verify=False
                )
            response.raise_for_status()
            batch = (response.json() or {}).get("products", []) or []
        except Exception:
            break

        if not batch:
            break

        # Keep only products we haven't seen. If a page adds nothing new, the
        # store is echoing page 1 (ignoring ?page=) — stop to avoid a loop.
        new_items = [p for p in batch if p.get("id") not in seen_ids]
        if not new_items:
            break
        for p in new_items:
            seen_ids.add(p.get("id"))
        all_products.extend(new_items)

    # Fallback: if requests + cloudscraper were both blocked (bot protection),
    # pull products.json through a real browser (Playwright), which solves the
    # Cloudflare challenge. Without this the analyzer drops to scraping the
    # collection HTML, which under-counts (JS-loaded products) and over-counts
    # (related-product links), and can't read real stock.
    if not all_products:
        try:
            from level1_detector.fetcher import fetch_json_with_playwright
        except Exception:
            fetch_json_with_playwright = None

        if fetch_json_with_playwright:
            pw_seen = set()
            for page in range(1, max_pages + 1):
                json_url = f"{base_url}/collections/{handle}/products.json?limit=250&page={page}"
                txt = fetch_json_with_playwright(json_url)
                if not txt:
                    break
                try:
                    batch = (json.loads(txt) or {}).get("products", []) or []
                except Exception:
                    break
                if not batch:
                    break
                new_items = [p for p in batch if p.get("id") not in pw_seen]
                if not new_items:
                    break
                for p in new_items:
                    pw_seen.add(p.get("id"))
                all_products.extend(new_items)

    return all_products


def _extract_color_swatches_from_variants(item_options, variants):
    """Extract color swatches from Shopify products.json variant data.

    Returns a list of {"label": str, "imageUrl": str|None} dicts, one per
    unique color value, preserving variant order.
    """
    if not variants:
        return []

    # Find which option position (option1/option2/option3) holds the colour.
    # Fallback to option1 when no explicit colour option is named.
    # NOTE: Shopify sometimes returns options as plain strings
    # (["Color", "Size"]) instead of dicts — this crashed with
    # "'str' object has no attribute 'get'" (e.g. pelacase.ca).
    color_key = "option1"
    for idx, opt in enumerate(item_options or []):
        if isinstance(opt, str):
            opt_name, pos = opt.lower(), idx + 1
        elif isinstance(opt, dict):
            opt_name = (opt.get("name") or "").lower()
            pos = opt.get("position", idx + 1)
        else:
            continue
        if re.search(r"colo(?:u)?r|shade|style|finish|hue|tone", opt_name):
            color_key = f"option{pos}"
            break

    seen: dict = {}   # label → imageUrl
    for v in variants:
        if not isinstance(v, dict):
            continue
        val = (v.get(color_key) or "").strip()
        if not val or val.lower() in ("default title", "default"):
            continue
        if val in seen:
            continue
        img_src = None
        fi = v.get("featured_image")
        if isinstance(fi, dict):
            img_src = fi.get("src")
        seen[val] = img_src

    return [{"label": lbl, "imageUrl": img} for lbl, img in seen.items()]


# Swatch element selectors tried in priority order for DOM-based extraction.
_SWATCH_SELECTORS = [
    # Explicit data attributes — most reliable
    "[data-swatch]",
    "[data-swatch-handle]",
    "[data-color-swatch]",
    "[data-color]",
    "[data-colour]",
    # ARIA / accessible patterns
    "[aria-label][class*='swatch']",
    "[aria-label][class*='color']",
    "[aria-label][class*='colour']",
    # Common class fragments (Shopify themes + headless)
    "[class*='color-swatch']",
    "[class*='colour-swatch']",
    "[class*='colorSwatch']",
    "[class*='colourSwatch']",
    "[class*='swatch__item']",
    "[class*='swatch-item']",
    "[class*='color-option']",
    "[class*='colour-option']",
    "[class*='colorOption']",
    # Radio inputs named "color" / "colour" (classic Shopify themes)
    "input[type='radio'][name*='color' i]",
    "input[type='radio'][name*='colour' i]",
    # Buttons / links inside a colour container
    "[class*='color'] button[aria-label]",
    "[class*='colour'] button[aria-label]",
]

# Labels that are UI chrome, not actual colour names — skip these.
_SWATCH_NOISE_RE = re.compile(
    r"^(shop\s+by|select\s+(a\s+)?|choose\s+|filter\s+|all\s+colo(?:u)?r)",
    re.I,
)


def _extract_swatches_from_card(card):
    """Scan a product card element for colour swatch elements.

    Returns a list of {"label": str, "imageUrl": str|None} dicts, deduplicated
    by lower-cased label.
    """
    swatches = []
    seen_labels: set = set()

    for selector in _SWATCH_SELECTORS:
        try:
            elements = card.select(selector)
        except Exception:
            continue

        for el in elements:
            # Try every reasonable attribute for the colour label.
            label = (
                el.get("data-swatch")
                or el.get("data-color-swatch")
                or el.get("data-color")
                or el.get("data-colour")
                or el.get("aria-label")
                or el.get("title")
                or el.get("value")
                or el.get_text(strip=True)
            )
            if not label:
                continue
            label = label.strip()
            if not label or len(label) > 60:
                continue
            if _SWATCH_NOISE_RE.match(label):
                continue

            key = label.lower()
            if key in seen_labels:
                continue
            seen_labels.add(key)

            # Look for a per-swatch image (small colour thumbnail).
            img_src = None
            img_el = el.select_one("img") or (
                el if el.name == "img" else None
            )
            if img_el:
                img_src = (
                    img_el.get("src")
                    or img_el.get("data-src")
                    or img_el.get("data-lazy-src")
                )

            swatches.append({"label": label, "imageUrl": img_src})

        if swatches:
            # Stop at the first selector that finds something — avoids
            # re-processing the same elements via broader selectors.
            break

    return swatches


# Season-code suffix found at the end of per-color-variant Shopify handles
# e.g. "gymshark-soft-sculpt-leggings-black-ss25", "-aw24", "-ss26-b1a2b-kdfx"
_SEASON_SUFFIX_RE = re.compile(
    r'[-_](?:ss|aw|fw|resort|pre|pe|fall|spring|summer|winter)[-_]?\d{2}(?:[-_][a-z0-9]+)*$',
    re.I,
)

# Common product-category words that can appear after the product name in a handle
# but are NOT colours.
_HANDLE_CATEGORY_WORDS = {
    "leggings", "hoodie", "hoodies", "shorts", "tee", "tank", "top", "tops",
    "bra", "sports", "jacket", "joggers", "vest", "pants", "crop", "bikini",
    "swimwear", "training", "running", "gym", "seamless", "regular", "flared",
    "straight", "slim", "relaxed", "oversized", "midlayer", "pullover",
    "sweatshirt", "sweatpants", "tracksuit", "zip", "logo",
}


def _longest_common_prefix(strings):
    """Return the longest common prefix of a list of strings."""
    if not strings:
        return ""
    prefix = strings[0]
    for s in strings[1:]:
        while not s.startswith(prefix):
            prefix = prefix[:-1]
            if not prefix:
                return ""
    return prefix


def _color_from_handle_diff(handle, common_prefix):
    """Extract a human-readable colour name from a per-colour-variant handle.

    Strategy:
      1. Strip the common-prefix shared by all colour variants of this product.
      2. Strip trailing season/release codes (ss25, aw24, …) and random SKU garbage.
      3. Filter out category words.
      4. What remains are the colour word(s) — capitalise and return.

    E.g. given common_prefix="gymshark-soft-sculpt-leggings-" and
    handle="gymshark-soft-sculpt-leggings-leggings-black-marl-aw24":
      → strip prefix → "leggings-black-marl-aw24"
      → strip season  → "leggings-black-marl"
      → filter cats   → ["black", "marl"]
      → return         → "Black Marl"
    """
    if not handle:
        return None
    h = handle.lower().strip("-")
    pfx = (common_prefix or "").lower().strip("-")
    if pfx and h.startswith(pfx):
        h = h[len(pfx):]
    h = h.strip("-")
    h = _SEASON_SUFFIX_RE.sub("", h).strip("-")
    if not h:
        return None
    words = [w for w in h.split("-") if w and w not in _HANDLE_CATEGORY_WORDS and len(w) > 1]
    if not words:
        return None
    # Cap at 3 words (avoids absorbing product-name remnants)
    return " ".join(w.capitalize() for w in words[:3])


def _enrich_swatches_from_title_groups(products):
    """Post-processing: group products by title, then cross-assign colour swatches.

    Some headless Shopify stores (e.g. Gymshark) list each colour variant as a
    separate product card on the collection page, each with its own handle:
        gymshark-soft-sculpt-leggings-black-ss25
        gymshark-soft-sculpt-leggings-leggings-blue-aw25

    When we detect two+ products with the same title, we treat them as colour
    siblings, extract the colour from handle differences, and populate `swatches`
    on every card in the group so the consumer knows all available colours.

    Products with already-populated swatches (from variant data or DOM) are skipped.
    """
    from collections import defaultdict

    # Group by normalised title.  Ignore products with no handle (can't extract colour).
    groups: dict = defaultdict(list)
    for p in products:
        title_key = re.sub(r"\s+", " ", (p.get("name") or "")).strip().lower()
        if title_key and p.get("handle"):
            groups[title_key].append(p)

    for title_key, group in groups.items():
        if len(group) < 2:
            continue  # Only one card → no siblings to build swatches from

        # Already enriched (any product in group has swatches)? skip.
        if any(p.get("swatches") for p in group):
            continue

        handles = [p["handle"] for p in group]
        common_pfx = _longest_common_prefix(handles).rstrip("-")

        colour_entries = []
        seen_colours: set = set()
        for p in group:
            colour = _color_from_handle_diff(p["handle"], common_pfx)
            if not colour:
                continue
            key = colour.lower()
            if key in seen_colours:
                continue
            seen_colours.add(key)
            colour_entries.append({
                "label": colour,
                "imageUrl": p.get("imageUrl"),
                "url": p.get("productUrl"),
            })

        if colour_entries:
            for p in group:
                p["swatches"] = colour_entries


def normalize_shopify_json_products(raw_products, url, currency="USD"):
    products = []
    category = get_collection_handle(url)

    for item in raw_products:
        # Defensive: some stores return malformed products.json entries
        # (strings, nulls) — skip anything that isn't a dict.
        if not isinstance(item, dict):
            continue
        variants = [v for v in (item.get("variants") or []) if isinstance(v, dict)]
        images = item.get("images") or []

        first_variant = variants[0] if variants else {}

        price = money_from_shopify_cents(first_variant.get("price"))
        compare_at = money_from_shopify_cents(first_variant.get("compare_at_price"))

        available_variants = [
            v for v in variants
            if v.get("available") is True
        ]

        image_url = None
        additional_images = []

        def _img_src(img):
            # images can be dicts ({"src": ...}) or plain URL strings
            if isinstance(img, dict):
                return img.get("src")
            return img if isinstance(img, str) else None

        if images:
            image_url = _img_src(images[0])
            additional_images = [
                src for src in (_img_src(img) for img in images[1:]) if src
            ]

        handle = item.get("handle")
        product_url = urljoin(url, f"/products/{handle}") if handle else None

        # Extract variant option names for display (e.g. shade names) without
        # storing the full variant objects (which include featured_image per variant).
        variant_options = list({
            v.get("option1") for v in variants
            if v.get("option1") and v.get("option1").lower() not in ("default title", "default")
        })

        # Short description: strip HTML, cap at 150 chars — no full product copy on collection cards
        raw_body = clean_text(item.get("body_html")) or ""
        short_desc = raw_body[:150] if raw_body else None

        # Extract colour swatches from variant data (preferred — has image URLs per colour).
        swatches = _extract_color_swatches_from_variants(
            item.get("options"), variants
        )

        products.append({
            "rank": len(products) + 1,
            "name": item.get("title"),
            "handle": handle,
            "productUrl": product_url,
            "imageUrl": image_url,
            # Store count only — storing every image URL bloats collection JSON significantly
            "additionalImageCount": len(additional_images),
            "price": {
                "currency": currency,
                "current": price,
                "compareAt": compare_at,
                "isOnSale": bool(compare_at and price and compare_at > price),
                "priceTextRaw": None
            },
            "availability": {
                "status": "in_stock" if available_variants else "out_of_stock",
                "inStock": bool(available_variants),
                "stockTextRaw": None
            },
            "category": category,
            "vendor": item.get("vendor"),
            "shortDescription": short_desc,
            "productType": item.get("product_type") or None,
            "tags": item.get("tags") or [],
            "swatches": swatches,
            "badges": ["out_of_stock"] if not available_variants else [],
            # Count only — full variant objects (with featured_image per shade) are very heavy
            "variantCount": len(variants),
            "variantOptions": variant_options[:20],  # cap at 20 option values
            "source": {
                "cardSelector": "shopify_products_json",
                "confidence": 0.92
            }
        })

    return products


def get_best_src_from_srcset(srcset, base_url):
    if not srcset:
        return None

    candidates = []

    for part in srcset.split(","):
        part = part.strip()
        if not part:
            continue

        pieces = part.split()
        src = pieces[0]
        width = 0

        if len(pieces) > 1:
            match = re.search(r"(\d+)w", pieces[1])
            if match:
                width = int(match.group(1))

        candidates.append((width, src))

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0], reverse=True)
    return normalize_image_url(candidates[0][1], base_url)


def get_image_url(img, base_url):
    if not img:
        return None

    srcset = img.get("srcset") or img.get("data-srcset")
    if srcset:
        return get_best_src_from_srcset(srcset, base_url)

    src = (
        img.get("src")
        or img.get("data-src")
        or img.get("data-original")
        or img.get("data-lazy-src")
    )

    return normalize_image_url(src, base_url) if src else None


def clean_product_name(name):
    if not name:
        return None

    name = clean_text(name)

    bad_names = [
        "sivanna colors",
        "cheow peow - cat food",
        "shade:",
        "quick view",
        "add to cart",
        "sale",
        "sold out",
        "view product",
        "choose options"
    ]

    if name.lower() in bad_names:
        return None

    if len(name.strip()) <= 1:
        return None

    return name


def get_name_from_card(card, product_url):
    selectors = [
        ".card__heading a",
        ".card__heading",
        ".product-card__title",
        ".product-title",
        ".product-item__title",
        ".grid-product__title",
        ".product-block__title",
        ".product-card-title",
        "h3 a",
        "h3",
        "h2 a",
        "h2"
    ]

    for selector in selectors:
        el = card.select_one(selector)
        if el:
            name = clean_product_name(el.get_text(" ", strip=True))
            if name:
                return name

    img = card.select_one("img")
    if img:
        alt = clean_product_name(img.get("alt"))
        if alt:
            return alt

    handle = product_url.rstrip("/").split("/")[-1]
    return handle.replace("-", " ").title()


def get_price_from_card(card):
    selectors = [
        ".price",
        ".price-item",
        ".money",
        ".product-price",
        ".grid-product__price",
        ".card-information .price",
        "[class*='price']"
    ]

    for selector in selectors:
        el = card.select_one(selector)
        if el:
            text = clean_text(el.get_text(" ", strip=True))
            if text and re.search(r"\d", text):
                return text

    text = clean_text(card.get_text(" ", strip=True))
    match = re.search(r"(Rs\.?|PKR|\$|£|€)\s?[\d,]+(?:\.\d+)?", text or "", re.I)

    return match.group(0) if match else None


def detect_stock(card):
    text = card.get_text(" ", strip=True).lower()

    # Only treat clear, product-level sold-out signals as out of stock. We
    # deliberately DON'T match bare "unavailable" — themes use it for a single
    # unavailable size/variant, which shouldn't flag the whole product.
    if any(x in text for x in ["out of stock", "sold out"]):
        return {
            "status": "out_of_stock",
            "inStock": False,
            "stockTextRaw": "Out of stock"
        }

    if any(x in text for x in ["add to cart", "buy now", "choose options"]):
        return {
            "status": "in_stock",
            "inStock": True,
            "stockTextRaw": None
        }

    return {
        "status": "unknown",
        "inStock": None,
        "stockTextRaw": None
    }


def get_main_product_area(soup):
    selectors = [
        "#product-grid",
        ".collection",
        ".collection-products",
        ".product-grid",
        ".grid--view-items",
        ".main-collection-product-grid",
        "main"
    ]

    for selector in selectors:
        area = soup.select_one(selector)
        if area and area.select('a[href*="/products/"]'):
            return area

    return soup


def find_product_card(link):
    parent = link

    for _ in range(8):
        if not parent:
            break

        classes = " ".join(parent.get("class", [])).lower()

        if any(x in classes for x in [
            "product-card",
            "card-wrapper",
            "product-item",
            "grid__item",
            "grid-product",
            "product-block",
            "card"
        ]):
            return parent

        parent = parent.parent

    return link.parent or link


def _parse_next_data_swatch_map(html):
    """Parse __NEXT_DATA__ / embedded JSON from a Next.js page and build a
    handle → [swatch, ...] map.

    Gymshark and similar headless Shopify + Next.js sites embed the full
    product list (with variant colour data) in a <script id="__NEXT_DATA__">
    tag.  This is more reliable than DOM class selectors whose names are
    obfuscated by CSS modules or styled-components.

    Returns a dict:  {handle: [{"label": str, "imageUrl": str|None}, ...]}
    """
    import json as _json

    swatch_map: dict = {}

    if not html:
        return swatch_map

    # ── 1. Try <script id="__NEXT_DATA__"> ──────────────────────────────────
    from bs4 import BeautifulSoup as _BS
    _soup = _BS(html, "html.parser")
    nd_script = _soup.find("script", id="__NEXT_DATA__")
    nd_objects = []
    if nd_script and nd_script.string:
        try:
            nd_objects.append(_json.loads(nd_script.string))
        except Exception:
            pass

    # ── 2. Fallback: any <script> that looks like it has product/variant data ──
    if not nd_objects:
        for sc in _soup.find_all("script"):
            txt = sc.string or ""
            if not txt or len(txt) < 200:
                continue
            if not ("variant" in txt.lower() and "option" in txt.lower()):
                continue
            try:
                nd_objects.append(_json.loads(txt))
            except Exception:
                pass

    def _walk_for_products(obj, depth=0):
        """Recursively yield dicts that look like Shopify product objects."""
        if depth > 15 or obj is None:
            return
        if isinstance(obj, dict):
            # A dict looks like a Shopify product if it has handle + variants/options
            if (
                obj.get("handle")
                and (obj.get("variants") or obj.get("options"))
                and obj.get("title")
            ):
                yield obj
            for v in obj.values():
                if isinstance(v, (dict, list)):
                    yield from _walk_for_products(v, depth + 1)
        elif isinstance(obj, list):
            for item in obj:
                yield from _walk_for_products(item, depth + 1)

    for nd in nd_objects:
        for prod in _walk_for_products(nd):
            handle = (prod.get("handle") or "").strip()
            if not handle:
                continue
            if handle in swatch_map:
                continue  # first occurrence wins
            swatches = _extract_color_swatches_from_variants(
                prod.get("options"), prod.get("variants") or []
            )
            if swatches:
                swatch_map[handle] = swatches

    return swatch_map


def extract_products_from_dom(soup, url, html=None):
    products = []
    seen_handles = set()

    main_area = get_main_product_area(soup)
    collection_handle = get_collection_handle(url)

    # Build a handle → swatches map from __NEXT_DATA__ / embedded JSON once
    # upfront.  This covers headless Next.js sites (Gymshark etc.) where
    # class-based selectors don't work because class names are obfuscated.
    next_data_swatches = _parse_next_data_swatch_map(html)

    for link in main_area.select('a[href*="/products/"]'):
        href = link.get("href")

        if not href:
            continue

        product_url = urljoin(url, href).split("?")[0]
        handle = product_url.rstrip("/").split("/")[-1]

        if handle in seen_handles:
            continue

        seen_handles.add(handle)

        card = find_product_card(link)

        name = get_name_from_card(card, product_url)
        img = card.select_one("img")
        image_url = get_image_url(img, url)

        price_raw = get_price_from_card(card)
        current_price = parse_price(price_raw)
        currency = detect_currency(price_raw)

        availability = detect_stock(card)
        # Prefer __NEXT_DATA__-sourced swatches (accurate, image URLs included);
        # fall back to DOM card scan for classic Shopify themes.
        swatches = (
            next_data_swatches.get(handle)
            or _extract_swatches_from_card(card)
        )

        products.append({
            "rank": len(products) + 1,
            "name": name,
            "handle": handle,
            "productUrl": product_url,
            "imageUrl": image_url,
            "additionalImageUrls": [],
            "price": {
                "currency": currency,
                "current": current_price,
                "compareAt": None,
                "isOnSale": False,
                "priceTextRaw": price_raw
            },
            "availability": availability,
            "category": collection_handle,
            "vendor": None,
            "shortDescription": None,
            "productType": None,
            "tags": [],
            "swatches": swatches,
            "badges": ["out_of_stock"] if availability["inStock"] is False else [],
            "variants": [],
            "source": {
                "cardSelector": "shopify_dom_v3",
                "confidence": 0.72
            }
        })

    # Attempt React hydration merge
    hydration_products = []
    try:
        hydration_products = extract_react_hydration_products(html or "", url)
    except Exception:
        hydration_products = []

    if hydration_products:
        existing_keys = set()

        for p in products:
            key = (
                (p.get("title") or p.get("name") or "").strip().lower(),
                (p.get("url") or p.get("productUrl") or "").strip().lower()
            )
            existing_keys.add(key)

        for p in hydration_products:
            key = (
                (p.get("title") or p.get("name") or "").strip().lower(),
                (p.get("url") or p.get("productUrl") or "").strip().lower()
            )

            if key not in existing_keys:
                products.append(p)
                existing_keys.add(key)

    return _drop_non_product_junk(products, collection_handle)


# Payment providers, shipping/returns badges and generic UI labels that get
# scraped as "products" when a page's markup wraps them in /products/-ish anchors
# or the card-name scan grabs nearby badge text (seen on Gymshark: 'Klarna',
# 'Afterpay', 'Free Standard Shipping Over $75', 'Delivery Information'). These are
# never real products, so they pollute counts/prices and can break downstream math.
# Standalone badge labels — must be the WHOLE name (end-anchored), so real
# products like "Zip Hoodie" or "Gift Set" aren't caught by 'zip'/'gift'.
_JUNK_EXACT_RE = re.compile(
    r"^\s*(klarna|afterpay|clearpay|sezzle|affirm|paypal|zip|laybuy|"
    r"shop\s*pay|apple\s*pay|google\s*pay|amazon\s*pay|"
    r"delivery\s+information|shipping\s+information|size\s+guide|"
    r"buy\s+now\s+pay\s+later|bnpl)\s*$",
    re.I,
)
# Shipping/delivery/returns promo phrases — allowed to have trailing text
# ("Free Standard Shipping Over $75", "Express Delivery Available").
_JUNK_PREFIX_RE = re.compile(
    r"^\s*(free\s+(standard\s+|express\s+)?(shipping|delivery|returns?)|"
    r"(standard|express|next[\s-]*day|international)\s+(shipping|delivery)|"
    r"free\s+returns?|returns?\s+&\s+exchanges?)\b",
    re.I,
)


def _is_junk_product_name(name):
    return bool(_JUNK_EXACT_RE.match(name) or _JUNK_PREFIX_RE.match(name))


def _drop_non_product_junk(products, collection_handle):
    """Filter out entries that clearly aren't products: payment/shipping badges,
    empty names, and self-links back to the collection itself (handle == the
    collection's own handle, e.g. a 'Crop Tops' tile on /collections/crop-tops)."""
    cleaned = []
    dropped = 0
    for p in products or []:
        if not isinstance(p, dict):
            dropped += 1
            continue
        name = (p.get("name") or p.get("title") or "").strip()
        handle = (p.get("handle") or "").strip().lower()
        if not name:
            dropped += 1
            continue
        if _is_junk_product_name(name):
            dropped += 1
            continue
        # A link whose handle IS the collection handle is the collection's own
        # tile/self-link, not a product in it.
        if handle and collection_handle and handle == str(collection_handle).lower():
            dropped += 1
            continue
        cleaned.append(p)
    if dropped:
        # Re-rank so downstream rank/index stays contiguous after filtering.
        for i, p in enumerate(cleaned):
            if isinstance(p, dict) and "rank" in p:
                p["rank"] = i + 1
        print(f"🧹 [collection] dropped {dropped} non-product junk entries (badges/self-links)")
    return cleaned


def normalize_name(value):
    if not value:
        return None
    return clean_text(value).lower().strip()


def _strip_brand_suffix(title, site_name=""):
    """Strip trailing brand/site suffix from a page title.

    Handles patterns like:
      "Face Powder – IN2IT Pakistan"   → "Face Powder"
      "Nails | Eveline Pakistan"       → "Nails"
      "Lip Color"                      → "Lip Color" (no change)
    """
    if not title:
        return title

    # Step 1: strip known site_name if provided
    if site_name:
        cleaned = re.sub(
            r"\s*[\|–\-]\s*" + re.escape(site_name) + r"\s*$",
            "",
            title,
            flags=re.IGNORECASE,
        ).strip()
        if cleaned and cleaned != title:
            return cleaned

    # Step 2: generic last-separator strip (handles unknown brand names)
    # Only strip if what remains on the LEFT looks like a real collection name
    # (non-empty and not just a single common word)
    sep_match = re.search(r"\s*[\|–]\s*", title)  # | or em-dash only (not hyphen — too common)
    if sep_match:
        left = title[:sep_match.start()].strip()
        if left and len(left) > 2:
            return left

    return title


def get_collection_name(result, url, content_collection_name=None):
    """Resolve the best collection name using a prioritised fallback chain.

    Priority:
    1. content.collectionName (already resolved by previous pass)
    2. SEO H1 — only if it is NOT just the brand/site name
    3. OpenGraph title — strip brand suffix if present
    4. SEO title — strip brand suffix
    5. URL handle converted to Title Case
    """
    seo = result.get("seo") or {}
    og = result.get("openGraph") or {}

    site_name = og.get("site_name") or ""
    h1 = seo.get("h1") or ""
    og_title = og.get("title") or ""
    seo_title = seo.get("title") or ""

    # 1. Previously resolved collectionName
    if content_collection_name and not _is_brand_only_name(content_collection_name, site_name):
        return content_collection_name

    # 2. H1 — reject brand-only values
    if h1 and not _is_brand_only_name(h1, site_name):
        return clean_text(h1)

    # 3. OG title — strip trailing "| Brand" or "– Brand" suffix
    if og_title:
        cleaned_og = _strip_brand_suffix(og_title, site_name)
        if cleaned_og and not _is_brand_only_name(cleaned_og, site_name):
            return clean_text(cleaned_og)

    # 4. SEO title — same suffix stripping
    if seo_title:
        cleaned_seo = _strip_brand_suffix(seo_title, site_name)
        if cleaned_seo and not _is_brand_only_name(cleaned_seo, site_name):
            return clean_text(cleaned_seo)

    # 5. URL handle
    handle = get_collection_handle(url)
    return handle.replace("-", " ").title() if handle else None


def build_product_stats(products, html):
    prices = [
        p["price"]["current"]
        for p in products
        if isinstance(p.get("price"), dict) and p["price"].get("current") is not None
    ]

    currencies = [
        p["price"]["currency"]
        for p in products
        if isinstance(p.get("price"), dict) and p["price"].get("currency")
    ]

    return {
        "currency": currencies[0] if currencies else None,
        "productCount": len(products),
        "priceRange": {
            "min": min(prices) if prices else None,
            "max": max(prices) if prices else None
        },
        "inStockCount": len([
            p for p in products
            if p.get("availability", {}).get("inStock") is True
        ]),
        "outOfStockCount": len([
            p for p in products
            if p.get("availability", {}).get("inStock") is False
        ]),
        "hasFilters": "filter" in (html or "").lower(),
        "hasSort": "sort" in (html or "").lower()
    }


def detect_collection_ctas(soup):
    """Scan product cards and buttons for CTA text on collection pages."""
    found = []
    seen = set()

    # Search buttons, links, and elements with CTA-like classes
    candidates = soup.select(
        "button, [type='submit'], "
        ".btn, .button, [class*='btn'], [class*='button'], "
        "[class*='add-to-cart'], [class*='atc'], "
        "[class*='quick-view'], [class*='quickview'], "
        "[class*='sold-out'], [class*='soldout']"
    )

    for el in candidates:
        text = (clean_text(el.get_text(" ", strip=True)) or "").lower()
        if not text or len(text) > 120:
            continue

        # Find ALL CTA patterns present in this element's text
        matched = [p for p in _COLLECTION_CTA_PATTERNS if p in text]
        if not matched:
            continue

        label_raw = clean_text(el.get_text(" ", strip=True))

        for pattern in matched:
            if pattern in seen:
                continue
            seen.add(pattern)

            if len(matched) == 1 and len(label_raw) <= 40:
                # Single clean CTA — use the actual button label
                label = label_raw
            else:
                # Multiple CTAs merged into one element, or text too long:
                # use the canonical pattern title instead of raw label
                label = pattern.title()

            found.append({"text": label, "source": "product_card"})

    return found


def _build_dominant_product_types(products):
    """Count product_type and tag occurrences; return top types."""
    from collections import Counter
    counter = Counter()

    for p in products:
        pt = (p.get("productType") or "").strip().lower()
        if pt and len(pt) > 2:
            counter[pt] += 1
        for tag in (p.get("tags") or []):
            tag = tag.strip().lower()
            if tag and len(tag) > 2 and not tag.isdigit():
                counter[tag] += 0.3  # tags are weaker signal

    # Return top 5 by count (only those seen >= 2 times, or the top one)
    top = [item for item, cnt in counter.most_common(10) if cnt >= 1.5]
    return top[:5]



def _build_top_brands(products):
    """Return distinct vendor names seen in the collection."""
    from collections import Counter
    counter = Counter()
    for p in products:
        vendor = (p.get("vendor") or "").strip()
        if vendor and len(vendor) > 1:
            counter[vendor] += 1
    return [brand for brand, _ in counter.most_common(5)]


def _detect_category_mismatch(products, collection_handle, collection_name):
    """Return (mismatch_flag, [example dicts]) when products don't belong to the collection.

    Logic: tokenise the collection handle + name (e.g. "foundation" -> {"foundation"}).
    For every product that has a non-empty productType, check whether ANY token in the
    product type overlaps with the collection tokens.  If more than 15 % of typed products
    are mismatched the collection is flagged -- this catches things like Primer / Concealer
    products sitting inside a Foundation collection.
    """
    if not products or not collection_handle:
        return False, []

    col_tokens = set(
        t.lower()
        for segment in [collection_handle or "", collection_name or ""]
        for t in re.split(r"[-_\s]+", segment)
        if len(t) > 2
    )
    col_tokens.discard("")

    if not col_tokens:
        return False, []

    mismatched = []
    typed_count = 0

    for p in products:
        pt = (p.get("productType") or "").strip()
        if not pt:
            continue
        typed_count += 1
        pt_tokens = set(t.lower() for t in re.split(r"[-_\s]+", pt) if t)
        if not pt_tokens.intersection(col_tokens):
            mismatched.append({
                "name": p.get("name"),
                "productType": pt
            })

    if typed_count > 0 and len(mismatched) / typed_count > 0.15:
        return True, mismatched[:5]

    return False, []


def build_collection_summary(products, collection_name, category, stats):
    """Build a lightweight summary of the collection for competitive analysis."""
    total = len(products)
    in_stock = stats.get("inStockCount", 0)
    out_of_stock = stats.get("outOfStockCount", 0)
    availability_ratio = round(in_stock / total, 2) if total > 0 else None

    mismatch, mismatch_examples = _detect_category_mismatch(products, category, collection_name)

    summary = {
        "name": collection_name,
        "category": category,
        "productCount": total,
        "inStockCount": in_stock,
        "outOfStockCount": out_of_stock,
        "priceRange": stats.get("priceRange") or {"min": None, "max": None},
        "dominantProductTypes": _build_dominant_product_types(products),
        "topBrands": _build_top_brands(products),
        "availabilityRatio": availability_ratio,
        "hasFilters": stats.get("hasFilters"),
        "hasSort": stats.get("hasSort"),
        "categoryMismatch": mismatch,
    }

    if mismatch and mismatch_examples:
        summary["categoryMismatchExamples"] = mismatch_examples

    return summary


def analyze_collection(self, url, html, headers, page_type, level1):
    result = self.base_result(url, html, headers, page_type, level1)
    soup = BeautifulSoup(html or "", "lxml")

    store_currency = _detect_store_currency(html, soup, url=url)

    # Reuse the Cloudflare clearance cookies the main page fetch earned (if the
    # page came via Playwright), so the products.json API call passes the same
    # bot check instead of getting blocked and dropping us to DOM scraping.
    _cf_cookies = (headers or {}).get("cookies") if isinstance(headers, dict) else None
    raw_json_products = fetch_shopify_collection_json(url, cookies=_cf_cookies)
    products = normalize_shopify_json_products(raw_json_products, url, currency=store_currency)
    print(f"🛒 [collection] products.json → {len(raw_json_products)} products for {url} (clearance_cookies={'yes' if _cf_cookies else 'no'})")

    if not products:
        products = extract_products_from_dom(soup, url, html=html)
        print(f"🛒 [collection] products.json blocked/empty → DOM fallback got {len(products)} products for {url}")
    else:
        # API products may still have empty swatches (headless stores sometimes
        # return variants without option data). Enrich from __NEXT_DATA__ if needed.
        _nd_swatches = _parse_next_data_swatch_map(html)
        if _nd_swatches:
            for _p in products:
                if not _p.get("swatches"):
                    _p["swatches"] = _nd_swatches.get(_p.get("handle") or "") or []

    # Enrich swatches from title-sibling grouping (headless stores where each
    # colour is a separate product card, e.g. Gymshark).
    _enrich_swatches_from_title_groups(products)

    # Diagnostic: surface the FINAL per-product name/price so price bugs are
    # visible in the analyzer log (each product should carry its own price).
    _src_tag = "json" if raw_json_products else "dom"
    for _dp in products[:6]:
        print(f"    • [collection:{_src_tag}] {_dp.get('name')!r} = {(_dp.get('price') or {}).get('current')}")

    collection_handle = get_collection_handle(url)

    # Resolve collection name using improved fallback chain
    existing_name = result.get("content", {}).get("collectionName")
    collection_name = get_collection_name(result, url, content_collection_name=existing_name)

    if "content" not in result:
        result["content"] = {}
    result["content"]["collectionName"] = collection_name

    stats = build_product_stats(products, html)
    result["ecommerce"]["productStats"] = stats
    result["products"] = products

    # Detect CTAs from product cards
    collection_ctas = detect_collection_ctas(soup)
    result["content"]["ctas"] = collection_ctas

    # Build collection summary
    result["collectionSummary"] = build_collection_summary(
        products, collection_name, collection_handle, stats
    )

    result["source"]["extractor"] = "Shopify Collection Extractor v4"
    result["source"]["confidence"] = 0.92 if raw_json_products else 0.72 if products else 0.45

    result = normalize_collection_result(
        result,
        collection_handle=collection_handle,
        default_currency=store_currency,
    )

    return result
