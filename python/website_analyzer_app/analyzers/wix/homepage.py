from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urlunparse
import re
import json


def clean_text(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


def normalize_url(raw_url, base_url=None):
    if not raw_url:
        return None

    raw_url = str(raw_url).strip()

    if raw_url.lower().startswith(("javascript:", "#")):
        return None

    full_url = urljoin(base_url or "", raw_url)
    parsed = urlparse(full_url)

    cleaned = parsed._replace(query="", fragment="")
    return urlunparse(cleaned)


def unique_items(items, key):
    seen = set()
    output = []

    for item in items:
        value = item.get(key)

        if not value or value in seen:
            continue

        seen.add(value)
        output.append(item)

    return output


def clean_wix_dom(html):
    soup = BeautifulSoup(html or "", "lxml")

    for selector in [
        "script", "style", "noscript", "iframe", "svg", "template",
        ".cookie", ".popup", ".modal",
        "[class*='cookie']", "[class*='popup']", "[class*='modal']"
    ]:
        for node in soup.select(selector):
            node.decompose()

    return soup


def extract_basic_seo(soup, url):
    title = soup.title.get_text(" ") if soup.title else None
    desc = soup.select_one("meta[name='description']")
    canonical = soup.select_one("link[rel='canonical']")
    h1 = soup.select_one("h1")

    return {
        "title": clean_text(title),
        "metaDescription": clean_text(desc.get("content")) if desc else None,
        "canonical": normalize_url(canonical.get("href"), url) if canonical else None,
        "h1": clean_text(h1.get_text(" ")) if h1 else None
    }


def extract_open_graph(soup):
    og = {}

    for meta in soup.select("meta[property^='og:']"):
        prop = meta.get("property", "").replace("og:", "")
        content = meta.get("content")

        if prop and content:
            og[prop] = clean_text(content)

    return og


def extract_json_ld_items(soup):
    items = []

    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            raw = script.string or script.get_text()

            if not raw:
                continue

            parsed = json.loads(raw)

            if isinstance(parsed, list):
                items.extend(parsed)
            else:
                items.append(parsed)

        except Exception:
            continue

    return items


def extract_navigation_links(soup, base_url):
    links = []

    for a in soup.select("a[href]"):
        text = clean_text(a.get_text(" "))
        href = a.get("href")

        if not text or not href:
            continue

        if len(text) > 120:
            continue

        url = normalize_url(href, base_url)

        if not url:
            continue

        links.append({
            "text": text,
            "url": url
        })

    return unique_items(links, "url")[:100]


def extract_home_sections(soup):
    main = soup.select_one("main") or soup.body or soup

    sections = []

    candidates = main.select(
        """
        section,
        article,
        div[data-testid],
        .section,
        .container,
        [class*='section'],
        [class*='content']
        """
    )

    if not candidates:
        candidates = [main]

    for node in candidates:
        text = clean_text(node.get_text(" "))

        if len(text) < 40:
            continue

        heading = None
        h = node.select_one("h1, h2, h3")

        if h:
            heading = clean_text(h.get_text(" "))

        sections.append({
            "heading": heading,
            "text": text[:2200]
        })

    deduped = []
    seen = set()

    for section in sections:
        normalized = re.sub(r"\s+", " ", section["text"].lower())
        key = normalized[:180]

        if key in seen:
            continue

        if any(key in existing or existing in key for existing in seen):
            continue

        seen.add(key)
        deduped.append(section)

    return deduped[:35]


def extract_headings(soup):
    headings = []

    main = soup.select_one("main") or soup.body or soup

    for h in main.select("h1, h2, h3, h4"):
        text = clean_text(h.get_text(" "))

        if text and len(text) <= 180:
            headings.append({
                "level": h.name,
                "text": text
            })

    return headings[:40]


def extract_images(soup, base_url):
    images = []

    main = soup.select_one("main") or soup.body or soup

    for img in main.select("img"):
        src = (
            img.get("data-src")
            or img.get("data-lazy-src")
            or img.get("src")
        )

        if not src or src.startswith("data:image"):
            continue

        alt = clean_text(img.get("alt"))
        src_lower = src.lower()
        alt_lower = alt.lower()

        if "blur_" in src_lower:
            continue

        small_dimension_match = re.search(
            r"/w_(\d+),h_(\d+)",
            src_lower
        )

        if small_dimension_match:
            w = int(small_dimension_match.group(1))
            h = int(small_dimension_match.group(2))

            if w < 180 or h < 180:
                continue

        if src_lower.endswith(".gif"):
            continue

        if any(k in src_lower for k in [
            "logo",
            "icon",
            "loader",
            "spinner",
            "placeholder",
            "social",
            "/w_22,",
            "/h_22,",
            "/w_25,",
            "/h_25,",
            "/w_50,",
            "/h_50,"
        ]):
            continue

        if any(k in alt_lower for k in [
            "logo",
            "instagram",
            "facebook",
            "twitter",
            "pinterest",
            "youtube",
            "icon",
            "social"
        ]):
            continue

        width = img.get("width")
        height = img.get("height")

        try:
            if width and int(width) < 120:
                continue

            if height and int(height) < 120:
                continue
        except Exception:
            pass

        normalized_image = normalize_url(src, base_url)

        if not normalized_image:
            continue

        images.append({
            "url": normalized_image,
            "alt": alt
        })

    return unique_items(images, "url")[:50]


def extract_ctas(soup, base_url):
    ctas = []

    keywords = [
        "shop",
        "buy",
        "view",
        "browse",
        "learn more",
        "read more",
        "contact",
        "book",
        "subscribe",
        "sign up",
        "discover",
        "add to cart"
    ]

    for node in soup.select("a[href], button"):
        text = clean_text(node.get_text(" "))

        if not text:
            continue

        if len(text) > 120:
            continue

        if any(k in text.lower() for k in keywords):
            href = node.get("href")

            ctas.append({
                "text": text,
                "url": normalize_url(href, base_url) if href else None
            })

    return unique_items(ctas, "url")[:40]


def _dollar_currency_from_url(url):
    """Delegate to shared currency utility."""
    from utils.currency import currency_from_url
    return currency_from_url(url) or "USD"


def normalize_price(raw, page_url=None):
    if not raw:
        return None

    raw = clean_text(raw)
    _rl = raw.lower()
    currency = None

    if "ca$" in _rl or (re.search(r'\bca\b', _rl) and "$" in raw):
        currency = "CAD"
    elif "a$" in _rl or "aud" in _rl:
        currency = "AUD"
    elif "£" in raw or "\xa3" in raw:
        currency = "GBP"
    elif "€" in raw:
        currency = "EUR"
    elif "aed" in _rl or "د.إ" in raw:
        currency = "AED"
    elif "sar" in _rl or "﷼" in raw:
        currency = "SAR"
    elif "inr" in _rl or "₹" in raw:
        currency = "INR"
    elif "pkr" in _rl or "₨" in raw or re.search(r'\brs\.?\b', _rl):
        currency = "PKR"
    elif "$" in raw:
        currency = _dollar_currency_from_url(page_url)

    match = re.search(r"(\d[\d,]*(?:\.\d{1,2})?)", raw)
    amount = None
    if match:
        try:
            amount = float(match.group(1).replace(",", ""))
        except Exception:
            amount = None

    # Zero-price guard
    if amount == 0.0:
        amount = None

    return {
        "raw": raw,
        "amount": amount,
        "currency": currency
    }


def extract_featured_products(soup, base_url):
    products = []

    for a in soup.select("a[href]"):
        href = a.get("href")
        text = clean_text(a.get_text(" "))

        # Fallback: image-only links (Jina markdown converted HTML)
        if not text:
            img = a.find("img")
            if img:
                text = clean_text(img.get("alt") or "")

        if not href:
            continue

        url = normalize_url(href, base_url)
        path = urlparse(url).path.lower() if url else ""

        # Accept /product-page/ links even with no price text
        if "/product-page/" not in path and not re.search(r"[$\xa3€]\s?\d+", text):
            continue

        if len(text) > 240:
            continue

        price_match = re.search(r"([$\xa3€]\s?\d+(?:[,.]\d{1,2})?)", text)
        price = price_match.group(1) if price_match else None

        name = text

        if price_match:
            name = text[:price_match.start()]

        name = re.sub(r"\bquick view\b", "", name, flags=re.I)
        name = re.sub(r"\bprice\b", "", name, flags=re.I)
        name = clean_text(name)

        if not name or name.lower() in ["quick view", "view"]:
            parent = a

            for _ in range(4):
                parent = parent.parent

                if not parent:
                    break

                nearby = clean_text(parent.get_text(" "))

                if len(nearby) > 10:
                    nearby = re.sub(r"\bquick view\b", "", nearby, flags=re.I)
                    nearby = re.sub(r"\bprice\b.*$", "", nearby, flags=re.I)
                    nearby = clean_text(nearby)

                    if nearby:
                        name = nearby[:140]
                        break

        # Last resort: derive name from URL slug (common with Jina fallback)
        if not name and url:
            slug = urlparse(url).path.rstrip("/").split("/")[-1]
            if slug:
                name = slug.replace("-", " ").replace("_", " ").title()

        if not name:
            continue

        # Discard placeholder names like "Image 29"
        if re.match(r'^image\s*\d+', name, re.IGNORECASE):
            if url:
                slug = urlparse(url).path.rstrip("/").split("/")[-1]
                if slug:
                    name = slug.replace("-", " ").replace("_", " ").title()
                else:
                    continue
            else:
                continue

        products.append({
            "name": name[:140],
            "url": url,
            "price": price,
            "priceNormalized": normalize_price(price, page_url=base_url),
            "image": None
        })

    return unique_items(products, "url")[:30]


def _is_jina_placeholder(text):
    """Return True if text looks like a Jina Reader auto-generated image alt."""
    if not text:
        return False
    t = text.strip()
    if re.match(r'^image\s*\d+', t, re.IGNORECASE):
        return True
    if re.search(r'\.(jpg|jpeg|png|webp|gif|svg)(\s*$|:)', t, re.IGNORECASE):
        return True
    return False


def _slug_to_title(url_str):
    """Derive a human-readable label from the last path segment of a URL."""
    if not url_str:
        return None
    slug = urlparse(url_str).path.rstrip("/").split("/")[-1]
    if not slug:
        return None
    return slug.replace("-", " ").replace("_", " ").title()


def extract_category_links(soup, base_url):
    categories = []

    text_keywords = [
        "shop", "collection", "collections", "coloring pages", "prints",
        "fabric", "fabrics", "clothing", "cards", "stationery", "gifts",
        "accessories", "skincare", "haircare", "makeup", "beauty",
        "home", "decor", "kitchen", "bath", "soaps", "textiles",
        "baskets", "pottery", "ceramics", "art", "sale", "new",
        "women", "men", "kids", "for her", "for him",
    ]

    _skip_paths = {
        "product-page", "blog", "post", "about", "contact", "faq",
        "privacy", "terms", "cart", "checkout", "account", "login",
        "signup", "search", "404", "home",
    }

    for a in soup.select("a[href]"):
        text = clean_text(a.get_text(" "))
        href = a.get("href")

        if not href:
            continue

        if not text:
            img = a.find("img")
            if img:
                text = clean_text(img.get("alt") or "")

        if _is_jina_placeholder(text):
            text = _slug_to_title(normalize_url(href, base_url)) or ""

        if len(text) > 90:
            continue

        href_lower = href.lower()
        text_lower = text.lower()

        if "/product-page/" in href_lower:
            continue

        if "mailto:" in href_lower or "tel:" in href_lower:
            continue

        normalized_url = normalize_url(href, base_url)

        if not normalized_url:
            continue

        if normalized_url.startswith(("mailto:", "tel:")):
            continue

        matched = False

        if any(k in text_lower for k in text_keywords) or any(k in href_lower for k in text_keywords):
            matched = True

        if not matched and base_url:
            try:
                parsed_base = urlparse(base_url)
                parsed_link = urlparse(normalized_url)
                same_domain = parsed_link.netloc == parsed_base.netloc
                path_parts = [p for p in parsed_link.path.strip("/").split("/") if p]
                if (
                    same_domain
                    and len(path_parts) == 1
                    and path_parts[0] not in _skip_paths
                    and len(path_parts[0]) >= 3
                ):
                    matched = True
            except Exception:
                pass

        if matched:
            label = text or _slug_to_title(normalized_url) or ""
            if not label:
                continue
            categories.append({
                "text": label,
                "url": normalized_url
            })

    return unique_items(categories, "url")[:50]


def extract_brand_story(main_text, seo):
    """Extract brand founding year, founder name, and origin signals."""
    story = {}

    founded_match = re.search(
        r'(?:founded|established|created|launched|started)\s+in\s+(\d{4})',
        main_text, re.IGNORECASE
    )
    if founded_match:
        story["founded"] = founded_match.group(1)

    founder_match = re.search(
        r'(?:founded|created|launched|started)\s+(?:in\s+\d{4}\s+)?by\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})',
        main_text
    )
    if founder_match:
        story["founder"] = founder_match.group(1)

    origin_match = re.search(
        r'(?:based in|from|originating (?:in|from))\s+([A-Z][a-zA-Z\s]+?)(?:\.|,|\s+(?:and|we|our|the)\s)',
        main_text
    )
    if origin_match:
        origin = origin_match.group(1).strip()
        if len(origin) < 60:
            story["origin"] = origin

    return story if story else None


# Navigation/section headings that should never appear in positioning
_POSITIONING_NAV_FILTER = {
    "home", "menu", "navigation", "footer", "cookie", "cart", "checkout",
    "shop", "about", "contact", "faq", "search", "login", "sign up",
    "in the shop", "featured", "products", "collections", "new arrivals",
    "sale", "wishlist", "bag", "new", "all", "store",
}

# Section-break markers: subtext stops here
_SECTION_BREAK_RE = re.compile(
    r'\b(?:IN THE SHOP|ABOUT US?|FEATURED|PRODUCTS?|COLLECTIONS?|NEW ARRIVALS|MENU|NAVIGATION)\b'
)


def extract_positioning(headings, sections, seo, page_title=None):
    """Extract brand positioning from headings, section headings, and meta description."""
    positioning = []
    seen_lower = set()

    # Build brand name filter from page_title
    brand_filter = set()
    if page_title:
        brand_filter.add(page_title.lower().strip())
        if "|" in page_title:
            for part in page_title.split("|"):
                brand_filter.add(part.strip().lower())

    def _accept(text):
        if not text or len(text) < 6 or len(text) > 140:
            return False
        low = text.lower().strip()
        # Filter nav/section words
        if low in _POSITIONING_NAV_FILTER:
            return False
        # Filter all-caps short strings (section headings like "IN THE SHOP")
        if text.upper() == text and len(text) <= 40:
            return False
        # Filter brand name
        if low in brand_filter:
            return False
        # Filter if already seen
        if low in seen_lower:
            return False
        return True

    # From headings (H1/H2 are strongest signals)
    for h in headings:
        text = h.get("text", "").strip()
        if _accept(text):
            seen_lower.add(text.lower())
            positioning.append(text)

    # From section headings
    for s in sections[:6]:
        heading = (s.get("heading") or "").strip()
        if _accept(heading):
            seen_lower.add(heading.lower())
            positioning.append(heading)

    # From meta description — split on punctuation into short phrases
    desc = (seo.get("metaDescription") or "").strip()
    if desc:
        for sent in re.split(r'[.!|]+', desc):
            sent = sent.strip()
            # Strip leading brand name from each sentence
            if page_title:
                for part in brand_filter:
                    sent = re.sub(r'^' + re.escape(part) + r'\s*[.|]?\s*', '', sent, flags=re.I).strip()
            if _accept(sent):
                seen_lower.add(sent.lower())
                positioning.append(sent)

    return positioning[:8]


def extract_trust_signals(main_text, headings, sections):
    """Extract trust indicators: founding year, collaborations, artisan signals."""
    signals = []
    seen = set()

    def _add(sig):
        if sig and sig not in seen:
            seen.add(sig)
            signals.append(sig)

    m = re.search(
        r'(?:founded|established|since|in business since)\s+(?:in\s+)?(\d{4})',
        main_text, re.IGNORECASE
    )
    if m:
        _add(f"Founded {m.group(1)}")

    for c in re.findall(
        r'[Cc]ollaboration\s+with\s+([A-Z][A-Za-z\s&\-]+?)(?:\.|,|\s+and\s|\s+we\s)',
        main_text
    )[:3]:
        _add(f"Collaboration with {c.strip()}")

    for a in re.findall(
        r'(?:as seen in|featured in)\s+([A-Z][A-Za-z\s&,]+?)(?:\.|,|$)',
        main_text, re.IGNORECASE
    )[:2]:
        sig = a.strip()
        if 3 < len(sig) < 80:
            _add(f"As seen in {sig}")

    trust_words = [
        ("handmade", "Handmade"),
        ("hand-crafted", "Hand-crafted"),
        ("handcrafted", "Handcrafted"),
        ("artisan", "Artisan"),
        ("artisanal", "Artisanal"),
        ("organic", "Organic"),
        ("sustainable", "Sustainable"),
        ("family-owned", "Family-owned"),
        ("award-winning", "Award-winning"),
        ("authentic", "Authentic"),
        ("traditional", "Traditional"),
    ]
    text_lower = main_text.lower()
    for keyword, label in trust_words:
        if keyword in text_lower:
            _add(label)

    return signals[:10]


def detect_business_model(text, products, categories, ctas):
    text_lower = text.lower()
    cta_text = " ".join([c.get("text", "") for c in ctas]).lower()

    ecommerce_score = 0
    leadgen_score = 0
    portfolio_score = 0

    if products:
        ecommerce_score += 6

    ecommerce_categories = [
        c for c in categories
        if not any(x in (c.get("url") or "").lower() for x in ["mailto:", "tel:"])
    ]

    if ecommerce_categories:
        ecommerce_score += 2

    ecommerce_keywords = [
        "add to cart",
        "checkout",
        "buy now",
        "shopping bag",
        "shopping cart"
    ]

    if any(k in text_lower for k in ecommerce_keywords):
        ecommerce_score += 4

    if products and any(k in cta_text for k in ["shop", "buy", "browse", "add to cart"]):
        ecommerce_score += 2

    if any(k in text_lower for k in [
        "contact",
        "commission",
        "custom",
        "inquire",
        "enquiry",
        "book",
        "booking",
        "tour",
        "private tour",
        "packages and services"
    ]):
        leadgen_score += 4

    if any(k in text_lower for k in [
        "portfolio",
        "gallery",
        "artist",
        "illustration",
        "design",
        "studio"
    ]):
        portfolio_score += 4

    scores = {
        "ecommerce": ecommerce_score,
        "leadGeneration": leadgen_score,
        "portfolio": portfolio_score,
        "general": 1
    }

    if portfolio_score >= 4 and ecommerce_score < 5:
        primary = "portfolio"
    else:
        primary = max(scores, key=scores.get)

    return {
        "primary": primary,
        "scores": scores
    }


def _strip_title_prefix(text, page_title):
    """Remove a leading page-title duplication from subtext."""
    if not text or not page_title:
        return text
    title_norm = re.sub(r"\s+", " ", page_title).strip()
    pattern = r"^\s*" + re.escape(title_norm) + r"\s*(?:[|.\-:]\s*)?"
    stripped = re.sub(pattern, "", text, count=1, flags=re.IGNORECASE).strip()
    if stripped and len(stripped) < len(text):
        return stripped
    return text


def _build_hero_subtext(sections, seo, page_title):
    """
    Build clean hero subtext:
    1. Prefer meta description (always clean for Jina-rendered pages)
    2. Fall back to first section text, truncated at section-break markers
    """
    # Option 1: meta description
    meta = (seo.get("metaDescription") or "").strip()
    if meta:
        # Strip leading brand prefix if present
        cleaned = _strip_title_prefix(meta, page_title)
        if cleaned and len(cleaned) >= 15:
            return cleaned

    # Option 2: first section, truncated at break markers
    if sections:
        raw = sections[0]["text"]
        # Strip title prefix first
        raw = _strip_title_prefix(raw, page_title)
        # Stop at section break markers
        m = _SECTION_BREAK_RE.search(raw)
        raw = raw[:m.start()].strip() if m else raw[:300]
        if raw and len(raw) >= 20:
            return raw[:300]

    return None


def build_hero_headline(sections, page_title, seo=None):
    bad_starts = [
        "workshop login",
        "shop now",
        "learn more",
        "view some pieces",
        "subscribe",
        "contact",
        "follow me",
        "home",
        "menu"
    ]

    for section in sections[:8]:
        text = clean_text(section.get("text"))

        if not text or len(text) < 40:
            continue

        # Strip title prefix before working with it
        text = _strip_title_prefix(text, page_title)

        if not text:
            continue

        text_lower = text.lower()

        if any(text_lower.startswith(x) for x in bad_starts):
            continue

        sentences = re.split(r'(?<=[.!?])\s+', text)
        candidate = sentences[0] if sentences else text
        candidate = clean_text(candidate)

        candidate = re.sub(r"\bSHOP NOW\b.*", "", candidate, flags=re.I)
        candidate = re.sub(r"\bEXPLORE OUR NEWEST PIECES\b.*", "", candidate, flags=re.I)
        candidate = clean_text(candidate)

        # If candidate still starts with the page title (Jina double-title),
        # strip it again and use remainder
        if page_title:
            candidate = _strip_title_prefix(candidate, page_title)

        if len(candidate) > 160:
            candidate = candidate[:160].rsplit(" ", 1)[0]

        if len(candidate) >= 20:
            return candidate

    # Fallback: use first meaningful sentence from meta description
    if seo:
        meta = (seo.get("metaDescription") or "").strip()
        if meta:
            cleaned_meta = _strip_title_prefix(meta, page_title)
            for sent in re.split(r'(?<=[.!?])\s+', cleaned_meta):
                sent = sent.strip().rstrip(".")
                if len(sent) >= 20:
                    return sent

    return clean_text(page_title)


def analyze_homepage(self, url, html, headers, page_type, level1):
    result = self.base_result(
        url,
        html,
        headers,
        page_type,
        level1
    )

    raw_soup = BeautifulSoup(html or "", "lxml")
    content_soup = clean_wix_dom(html)

    result["source"]["extractor"] = "Wix Homepage Extractor"

    seo = extract_basic_seo(raw_soup, url)
    open_graph = extract_open_graph(raw_soup)
    json_ld_items = extract_json_ld_items(raw_soup)

    headings = extract_headings(content_soup)
    sections = extract_home_sections(content_soup)
    images = extract_images(content_soup, url)
    ctas = extract_ctas(content_soup, url)
    navigation_links = extract_navigation_links(raw_soup, url)
    products = extract_featured_products(content_soup, url)
    categories = extract_category_links(raw_soup, url)

    main_text = clean_text(content_soup.get_text(" "))

    page_title = (
        seo.get("h1")
        or open_graph.get("title")
        or seo.get("title")
    )

    # --- Intelligence extraction ---
    brand_story = extract_brand_story(main_text, seo)
    positioning = extract_positioning(headings, sections, seo, page_title=page_title)
    trust_signals = extract_trust_signals(main_text, headings, sections)

    business_model = detect_business_model(
        main_text,
        products,
        categories,
        ctas
    )

    has_cart_or_checkout = any(
        k in main_text.lower()
        for k in [
            "add to cart",
            "checkout",
            "buy now",
            "shopping cart",
            "shopping bag"
        ]
    )

    has_ecommerce_signals = any([
        bool(products),
        has_cart_or_checkout,
        business_model["scores"]["ecommerce"] >= 6
    ])

    hero_headline = build_hero_headline(sections, page_title, seo=seo)
    subtext = _build_hero_subtext(sections, seo, page_title)

    # CTA fallback: for blocked/Jina pages, buttons are absent — use categories/products
    primary_ctas = ctas[:5]
    if not primary_ctas and categories:
        primary_ctas = [{"text": c["text"], "url": c["url"]} for c in categories[:5]]
    if not primary_ctas and products:
        primary_ctas = [{"text": p["name"], "url": p["url"]} for p in products[:3]]

    result["seo"] = seo
    result["openGraph"] = open_graph

    result["homepage"] = {
        "title": page_title,
        "businessModel": business_model,
        "brandStory": brand_story,
        "positioning": positioning,
        "trustSignals": trust_signals,
        "hero": {
            "headline": hero_headline,
            "subtext": subtext,
            "primaryCtas": primary_ctas
        },
        "sections": sections,
        "headings": headings,
        "ctas": ctas,
        "images": images
    }

    result["navigation"] = {
        "links": navigation_links
    }

    result["ecommerce"] = {
        "hasEcommerceSignals": has_ecommerce_signals,
        "featuredProductsCount": len(products),
        "featuredProducts": products[:30],
        "categoryLinks": categories,
        "hasProductGrid": len(products) >= 3,
        "hasCategories": bool(categories),
        "hasCartOrCheckout": has_cart_or_checkout
    }

    result["content"] = {
        "pageTitle": page_title,
        "pageIntent": "homepage",
        "mainText": main_text[:15000],
        "headings": headings,
        "sections": sections,
        "links": navigation_links,
        "images": images,
        "ctas": ctas
    }

    result["structuredData"] = {
        "jsonLdCount": len(json_ld_items),
        "items": json_ld_items[:20]
    }

    confidence = 0.60

    if page_title:
        confidence += 0.10

    if headings:
        confidence += 0.10

    if sections:
        confidence += 0.10

    if categories:
        confidence += 0.03

    if products:
        confidence += 0.07

    result["source"]["confidence"] = round(
        min(max(confidence, 0.35), 0.95),
        2
    )

    # H-F2: expose canonical products path used by all other platforms
    result["products"] = products[:30]

    return result
