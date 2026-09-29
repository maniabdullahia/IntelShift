from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urlunparse
import re
import json


def clean_text(text):
    return re.sub(r"\s+", " ", text or "").strip()


def normalize_url(raw_url, base_url=None):
    if not raw_url:
        return None

    if str(raw_url).lower().startswith("javascript:"):
        return None

    full_url = urljoin(base_url or "", raw_url)
    parsed = urlparse(full_url)

    cleaned = parsed._replace(
        query="",
        fragment=""
    )

    return urlunparse(cleaned)


def unique_items(items, key):
    seen = set()
    output = []

    for item in items:
        value = item.get(key)

        if value is not None:
            # Deduplicate by the key value (e.g. URL)
            if value in seen:
                continue
            seen.add(value)
        else:
            # Key is absent/None (e.g. retailer CTAs with no URL):
            # deduplicate by a normalised text snippet instead so they
            # are not silently discarded.
            text_key = str(item.get("text", ""))[:60].lower().strip()
            if text_key in seen:
                continue
            seen.add(text_key)

        output.append(item)

    return output


def normalize_price(price_text):
    if not price_text:
        return {
            "raw": None,
            "amount": None,
            "currency": None
        }

    raw = clean_text(price_text)

    currency = None
    raw_lower = raw.lower()

    if "₨" in raw or "rs" in raw_lower or "pkr" in raw_lower:
        currency = "PKR"
    elif "zł" in raw_lower or "pln" in raw_lower:
        currency = "PLN"
    elif "€" in raw:
        currency = "EUR"
    elif "$" in raw:
        currency = "USD"
    elif "£" in raw:
        currency = "GBP"
    elif "aed" in raw_lower or "د.إ" in raw:
        currency = "AED"

    cleaned = raw
    cleaned = re.sub(r"current price is:", "", cleaned, flags=re.I)
    cleaned = re.sub(r"aktualna cena wynosi:", "", cleaned, flags=re.I)
    cleaned = re.sub(r"original price was:", "", cleaned, flags=re.I)
    cleaned = re.sub(r"pierwotna cena wynosiła:", "", cleaned, flags=re.I)
    cleaned = re.sub(r"(₨|rs\.?|pkr|zł|pln|€|\$|£)", "", cleaned, flags=re.I)
    cleaned = clean_text(cleaned)

    if currency in ["EUR", "PLN"] and re.search(r"\d+,\d{2}", cleaned):
        cleaned = cleaned.replace(".", "")
        cleaned = cleaned.replace(",", ".")
    else:
        cleaned = cleaned.replace(",", "")

    amount = None
    match = re.search(r"\d+(?:\.\d+)?", cleaned)

    if match:
        try:
            amount = float(match.group(0))
        except Exception:
            amount = None

    if amount == 0:
        amount = None

    return {
        "raw": raw,
        "amount": amount,
        "currency": currency
    }


def extract_price_from_text(text):
    text = clean_text(text)

    if not text:
        return None

    patterns = [
        r"Current price is:\s*(₨|Rs\.?|PKR|AED|\$|£|€)\s*([\d,]+(?:[,.]\d{2})?)",
        r"Sale price\s*(₨|Rs\.?|PKR|AED|\$|£|€)\s*([\d,]+(?:[,.]\d{2})?)",
        r"Regular price\s*(₨|Rs\.?|PKR|AED|\$|£|€)\s*([\d,]+(?:[,.]\d{2})?)",
        r"Price\s*(₨|Rs\.?|PKR|AED|\$|£|€)\s*([\d,]+(?:[,.]\d{2})?)",
        r"Aktualna cena wynosi:\s*([\d,]+(?:[,.]\d{2})?)\s*(zł|PLN)",
        r"(₨|Rs\.?|PKR|AED)\s*([\d,]+(?:[,.]\d{2})?)\s*Current price",
        r"([\d,]+(?:[,.]\d{2})?)\s*(zł|PLN)\s*Aktualna cena",
        r"(₨|Rs\.?|PKR|AED)\s*([\d,]+(?:\.\d{2})?)",
        r"(\$|£|€)\s*([\d,]+(?:[,.]\d{2})?)",
        r"([\d,]+(?:[,.]\d{2})?)\s*(€|zł|PLN)"
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.I)

        if match:
            value = clean_text(match.group(0))

            if re.search(r"\d", value):
                return value

    return None


def is_valid_image(url, alt=""):
    url_lower = (url or "").lower()
    alt_lower = (alt or "").lower()

    if not url_lower:
        return False

    if url_lower.startswith("data:image"):
        return False

    blocked_keywords = [
        "logo",
        "icon",
        "payment",
        "paypal",
        "visa",
        "mastercard",
        "placeholder",
        "avatar",
        "loader",
        "spinner",
        "trustpilot",
        "badge",
        "facebook",
        "instagram",
        "youtube",
        "linkedin"
    ]

    blocked_extensions = [
        ".svg",
        ".gif"
    ]

    if any(k in url_lower for k in blocked_keywords):
        return False

    if any(k in alt_lower for k in blocked_keywords):
        return False

    if any(url_lower.endswith(ext) for ext in blocked_extensions):
        return False

    return True


# ---------------------------------------------------------------------------
# Hero headline junk filter
# These are nav/cart/utility words that must never appear as the hero headline.
# ---------------------------------------------------------------------------

_HERO_NAV_JUNK = {
    "cart", "account", "wishlist", "checkout", "search", "menu",
    "login", "my account", "register", "compare", "sign in", "sign up",
    "close", "open", "home", "navigation", "back", "next", "skip",
    "view cart", "0 items", "my wishlist", "my orders", "track order",
    "log in", "log out", "logout"
}


def _is_hero_junk_heading(text):
    """
    Return True if a heading is nav/utility junk that should never become
    the hero headline.  E.g. 'Cart', 'Account', 'Wishlist', 'Checkout'.
    """
    tl = text.strip().lower()

    if tl in _HERO_NAV_JUNK:
        return True

    # Short single/two-word phrases that are pure utility
    words = tl.split()
    if len(words) <= 3 and any(k in tl for k in [
        "cart", "account", "wishlist", "checkout", "login",
        "sign in", "my account", "register"
    ]):
        return True

    return False


def extract_json_ld_items(soup):
    json_ld_items = []

    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            raw = script.string or script.get_text()

            if not raw:
                continue

            parsed = json.loads(raw)

            if isinstance(parsed, list):
                json_ld_items.extend(parsed)
            else:
                json_ld_items.append(parsed)

        except Exception:
            continue

    return json_ld_items


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


def extract_schema_summary(json_ld_items):
    flattened = []

    for item in json_ld_items:
        flattened.extend(flatten_json_ld_items(item))

    schema_types = []
    organization = {}
    website = {}
    local_business = {}

    business_types = [
        "localbusiness",
        "store",
        "clothingstore",
        "healthandbeautybusiness",
        "hvacbusiness",
        "diagnosticlab",
        "medicalbusiness"
    ]

    for item in flattened:
        item_type = item.get("@type")

        if isinstance(item_type, list):
            item_types = [str(t) for t in item_type]
        elif item_type:
            item_types = [str(item_type)]
        else:
            item_types = []

        schema_types.extend(item_types)

        lower_types = [t.lower() for t in item_types]

        if "organization" in lower_types and not organization:
            organization = {
                "name": clean_text(item.get("name")),
                "url": item.get("url"),
                "email": item.get("email"),
                "telephone": item.get("telephone"),
                "sameAs": item.get("sameAs", [])
            }

        if "website" in lower_types and not website:
            website = {
                "name": clean_text(item.get("name")),
                "url": item.get("url")
            }

        if any(t in lower_types for t in business_types) and not local_business:
            local_business = {
                "name": clean_text(item.get("name")),
                "priceRange": item.get("priceRange"),
                "telephone": item.get("telephone"),
                "email": item.get("email")
            }

    return {
        "types": list(dict.fromkeys(schema_types)),
        "organization": organization,
        "website": website,
        "localBusiness": local_business
    }


def clean_dom_for_content(html):
    soup = BeautifulSoup(html or "", "lxml")

    for selector in [
        "script",
        "style",
        "noscript",
        "iframe",
        "svg",
        "form",
        "template",
        ".modal",
        ".popup",
        ".drawer",
        ".cart-drawer",
        ".newsletter",
        ".compare-popup",
        ".mobile-menu",
        ".offcanvas",
        ".oxy-site-navigation",
        ".oxy-header",
        ".ct-code-block",
        ".elementor-nav-menu",
        ".menu-drawer",
        ".xoo-wsc-modal",
        ".xoo-wsc-cart-active",
        "[class*='popup']",
        "[class*='modal']",
        "[class*='drawer']",
        "[class*='newsletter']",
        "[class*='offcanvas']",
        "[class*='cookie']",
        "[class*='compare']"
    ]:
        for node in soup.select(selector):
            node.decompose()

    for tag in soup.find_all(True):
        for attr in list(tag.attrs):
            if (
                attr.startswith("x-")
                or attr.startswith("@")
                or attr.startswith(":")
                or attr in [
                    "onclick",
                    "onload",
                    "onmouseover",
                    "data-settings"
                ]
            ):
                del tag.attrs[attr]

    return soup


def clean_noise_text(text):
    text = clean_text(text)

    if not text:
        return ""

    noisy_patterns = [
        r"\$event\.target.*?(?=\s[A-ZÄÖÜA-Z][A-Za-zÄÖÜäöüß])",
        r"x-init=.*?(?=\s[A-ZÄÖÜA-Z][A-Za-zÄÖÜäöüß])",
        r"x-data=.*?(?=\s[A-ZÄÖÜA-Z][A-Za-zÄÖÜäöüß])",
        r"post_author.*?menu_item_parent.*?menu_image",
        r"\{'ID':.*?menu_image.*?\}",
        r"aria-label=.*?aria-expanded=.*?",
        r"\$refs\.[^\s]+"
    ]

    for pattern in noisy_patterns:
        text = re.sub(pattern, " ", text, flags=re.I | re.S)

    bad_fragments = [
        "$event.target",
        "x-init",
        "x-data",
        "post_author",
        "post_modified",
        "menu_item_parent",
        "menu-item-type",
        "aria-expanded",
        "current_item_parent",
        "current_item_ancestor"
    ]

    if any(fragment in text for fragment in bad_fragments) and len(text) > 500:
        parts = re.split(
            r"(Über uns|Technologie|Produkte|Publikationen|Kontakt|Home|About|Services|Gallery|Expert HVAC|Who We Are|Akustische KI)",
            text,
            flags=re.I
        )

        if len(parts) > 2:
            text = "".join(parts[1:])

    text = re.sub(r"\s+", " ", text).strip()

    return text


def is_bad_nav_or_utility_text(text):
    text_lower = clean_noise_text(text).lower()

    if not text_lower:
        return True

    bad_exact = {
        "menu",
        "home",
        "close",
        "open",
        "skip to content",
        "compare",
        "cart",
        "wishlist",
        "account",
        "login",
        "register",
        "de",
        "en",
        "pl"
    }

    if text_lower in bad_exact:
        return True

    if text_lower.startswith("menu home"):
        return True

    if "no products in the cart" in text_lower:
        return True

    if "no products in the compare" in text_lower:
        return True

    return False


def extract_navigation(soup, base_url):
    links = []

    nav_scope = soup.select_one("header") or soup

    blocked_texts = [
        "skip to content",
        "menu",
        "close",
        "open",
        "powered by joinchat",
        "cookie-einstellungen"
    ]

    for a in nav_scope.select("a[href]"):
        text = clean_noise_text(a.get_text(" "))
        href = a.get("href")

        if not text or not href:
            continue

        text_lower = text.lower()

        if text_lower in blocked_texts:
            continue

        if href.lower().startswith("javascript:"):
            continue

        links.append({
            "text": text,
            "url": normalize_url(href, base_url)
        })

    return unique_items(links, "url")[:100]


def extract_hero(soup, base_url):
    demo_keywords = [
        "xstore demo",
        "elementor demo",
        "sport demo",
        "theme demo"
    ]

    # Collect navigation link texts once for use in both step 1 and step 2.
    # Used to filter out short headings that are product-category nav labels
    # (e.g. "Skincare", "Makeup") rather than true brand headlines.
    _nav_texts = {
        clean_noise_text(a.get_text(" ")).lower()
        for a in soup.select(
            "nav a, header a, .nav a, [class*='navigation'] a, [class*='menu'] a"
        )
        if a.get("href")
    }

    # ----------------------------------------------------------------
    # Step 1: Try the page-level H1 first (highest-fidelity headline).
    # This prevents a nav/promo-bar heading from overriding the real
    # marketing headline (e.g. Elementor's "Build with … Up to 30%").
    # ----------------------------------------------------------------
    headings = []
    page_h1 = soup.find("h1")

    if page_h1:
        h1_text = clean_noise_text(page_h1.get_text(" "))

        if (
            h1_text
            and len(h1_text) > 3
            and not any(k in h1_text.lower() for k in demo_keywords)
            and not _is_hero_junk_heading(h1_text)
            # Skip if H1 is a short nav category label (e.g. "Skincare")
            and not (len(h1_text.split()) <= 3 and h1_text.lower() in _nav_texts)
        ):
            headings.append(h1_text)

    # ----------------------------------------------------------------
    # Step 2: Scan the hero section for additional sub-headings.
    # Prefer a semantic hero/banner container; fall back to main/body.
    # ----------------------------------------------------------------
    hero_node = (
        soup.select_one("section[class*='hero']")
        or soup.select_one(".hero")
        or soup.select_one(".banner")
        or soup.select_one("[class*='banner']")
        or soup.select_one("main section")
        or soup.select_one("main")
        or soup.body
        or soup
    )

    for h in hero_node.select("h1, h2, h3, .elementor-heading-title, .ct-headline"):
        text = clean_noise_text(h.get_text(" "))

        if not text or len(text) <= 2:
            continue

        if any(k in text.lower() for k in demo_keywords):
            continue

        if _is_hero_junk_heading(text):
            continue

        # Filter short headings that are navigation category labels
        # (≤ 3 words and the exact text appears as a nav link).
        if len(text.split()) <= 3 and text.lower() in _nav_texts:
            continue

        if text not in headings:
            headings.append(text)

    ctas = []

    cta_keywords = [
        "shop",
        "buy",
        "view",
        "explore",
        "contact",
        "book",
        "get started",
        "start",
        "learn more",
        "read more",
        "schedule",
        "demo",
        "quote",
        "whatsapp",
        "shop now",
        "buy now",
        "book service",
        "book service now",
        "request free quote",
        "free quote",
        "enquire today",
        "kup",
        "kup teraz",
        "zobacz",
        "więcej",
        "wiecej",
        "acheter",
        "voir",
        "jetzt kaufen",
        "mehr erfahren",
        "kontakt"
    ]

    blocked_ctas = [
        "facebook",
        "instagram",
        "youtube",
        "linkedin",
        "tiktok"
    ]

    for a in hero_node.select("a[href]"):
        text = clean_noise_text(a.get_text(" "))
        href = a.get("href")

        if not text or not href:
            continue

        text_lower = text.lower()

        if text_lower in blocked_ctas:
            continue

        if any(k in text_lower for k in cta_keywords):
            ctas.append({
                "text": text,
                "url": normalize_url(href, base_url)
            })

    image = None

    img = hero_node.find("img")

    if img:
        src = (
            img.get("data-src")
            or img.get("data-lazy-src")
            or img.get("data-original")
            or img.get("src")
        )

        if src:
            src = normalize_url(src, base_url)
            alt = clean_noise_text(img.get("alt"))

            if is_valid_image(src, alt):
                image = {
                    "url": src,
                    "alt": alt
                }

    # Story: first substantive paragraph in the hero section (brand taglines,
    # brand promises — e.g. "Love yourself. Know what you need.").
    # Excluded: the headline itself, demo/junk strings, very short snippets,
    # and preamble paragraphs (class="jina-preamble") which Jina emits as
    # pre-heading content / meta-description lines.
    story = None
    for p in hero_node.select("p"):
        # Skip Jina pre-heading / meta-description preamble paragraphs
        if "jina-preamble" in (p.get("class") or []):
            continue
        p_text = clean_noise_text(p.get_text(" "))
        if (
            p_text
            and len(p_text) > 15
            and not _is_hero_junk_heading(p_text)
            and not any(k in p_text.lower() for k in demo_keywords)
            and (not headings or p_text != headings[0])
        ):
            story = p_text[:500]
            break

    # ----------------------------------------------------------------
    # SEO-title cleanup:
    #   A) Promote the real marketing headline when headings[0] is an
    #      SEO/site-title (contains " | " separator, e.g. "Haven Greens |
    #      Fresh Lettuce & Greenhouse …").
    #   B) Remove ALL remaining SEO-title headings so none leak into
    #      subheadings or subheadline.
    #   C) Fall back to the old short-brand-name swap for the edge case
    #      where no " | " is present but headings[0] is still a bare
    #      brand name and headings[1] is a genuine tagline.
    # ----------------------------------------------------------------
    # Step A: if headings[0] is an SEO title, promote headings[1] first
    if len(headings) >= 2 and " | " in headings[0]:
        headings = headings[1:] + [headings[0]]

    # Step B: remove SEO-title strings from any position in the list
    _no_seo = [h for h in headings if " | " not in h]
    if _no_seo:
        headings = _no_seo

    # Step C: short-brand-name swap (no " | " present)
    if (
        len(headings) >= 2
        and len(headings[0].split()) <= 3
        and len(headings[1].split()) >= 5
    ):
        headings = [headings[1]] + headings[2:] + [headings[0]]

    # subheadline priority (highest to lowest):
    #
    #   1. First <p> inside the first <section> that matches the headline
    #      heading — this is the per-section tagline from Jina-structured HTML
    #      (e.g. "Taste the future of fresh" under the product hero heading).
    #      Kept only when it's a genuine tagline (3–20 words, no " | ").
    #
    #   2. The second heading when it reads like a real tagline (> 2 words
    #      and does not look like a short section label).
    #
    #   3. The story paragraph (first substantive <p> in the hero).
    subheadline = None

    # 1 — first-section tagline (Jina-structured HTML only)
    # Find the <section> whose heading matches the resolved headline,
    # then use its first content <p> as the subheadline.
    if headings:
        _first_section = None
        for _sec in soup.find_all("section"):
            _sec_heading = _sec.find(["h2", "h3", "h4"])
            if _sec_heading:
                _sec_htext = clean_noise_text(_sec_heading.get_text(" "))
                if _sec_htext == headings[0]:
                    _first_section = _sec
                    break
        if _first_section:
            for _sp in _first_section.select("p"):
                if "jina-preamble" in (_sp.get("class") or []):
                    continue
                _sp_text = clean_noise_text(_sp.get_text(" "))
                if (
                    _sp_text
                    and 3 <= len(_sp_text.split()) <= 20
                    and " | " not in _sp_text
                    and not _is_hero_junk_heading(_sp_text)
                ):
                    subheadline = _sp_text
                    break

    # 2 — second heading as tagline
    if not subheadline and len(headings) > 1 and len(headings[1].split()) > 2:
        subheadline = headings[1]

    # 3 — fallback to story paragraph
    if not subheadline:
        subheadline = story

    return {
        "headline": headings[0] if headings else None,
        "subheadline": subheadline,
        "subheadings": headings[1:9],
        "story": story,
        "ctas": unique_items(ctas, "url")[:10],
        "image": image,
        "text": clean_noise_text(hero_node.get_text(" "))[:3000]
    }


def _classify_section_type(heading, text=""):
    """Return a content-type label for a section based on its heading.

    Labels: story | value_prop | products | social_proof | faq |
            blog_section | general
    Used by homepageStrategy.sections to tag Jina markdown sections.
    """
    import re as _re_st
    if not heading:
        return "general"
    h = heading.lower()
    t = (text or "").lower()

    _story_kw = [
        "our journey", "our story", "our history", "about us",
        "our roots", "our beginning", "our origin", "who we are",
        "how we started", "heritage", "our passion", "meet the",
        "family farm", "family legacy",
    ]
    _value_prop_kw = [
        "sustainability", "sustainable", "our mission", "our values",
        "our commitment", "environmental", "why us", "why choose",
        "what makes us", "our promise", "our purpose", "our vision",
        "b corp", "carbon neutral", "regenerative", "certified",
        "pesticide-free", "organic", "responsibility",
    ]
    _social_proof_kw = [
        "testimonial", "review", "what our customers", "what clients say",
        "success stor", "case stud", "award", "press", "media",
        "as seen in", "featured in",
    ]
    _faq_kw = ["faq", "frequently asked", "questions", "q&a"]
    _product_kw = [
        "product", "blend", "variety", "range", "collection",
        "shop", "menu", "offering",
    ]
    # Blog / article section signals.  Detected first so they are never
    # mis-classified as services or value-props.
    _blog_heading_kw = [
        " — ", " - how to", " - why ", "explained", "top tips",
        "common mistakes", "what is ", "what are ", "a guide to",
        "guide to", "the truth about",
    ]
    _blog_body_kw = ["read full article", "read the full article", "posted on",
                     "min read", "minutes to read", "written by"]

    # Heading looks like a blog post title (contains em-dash or article phrase)
    if any(k in h for k in _blog_heading_kw):
        return "blog_section"
    # Body text contains multiple "Read Full Article" signals → blog listing block
    if t.count("read full article") >= 1 or any(k in t for k in _blog_body_kw):
        return "blog_section"
    # Heading ends with a past-participle phrase typical of article headlines
    if _re_st.search(r'\b(explained|revealed|solved|fixed|reviewed)$', h):
        return "blog_section"

    if any(k in h for k in _story_kw):
        return "story"
    if any(k in h for k in _value_prop_kw):
        return "value_prop"
    if any(k in h for k in _social_proof_kw):
        return "social_proof"
    if any(k in h for k in _faq_kw):
        return "faq"
    # Product section: heading has product-type keyword OR body text has prices
    if any(k in h for k in _product_kw):
        return "products"
    if any(k in t[:200] for k in ["$", "cad", "each", "per pack", "per bag", "per kg"]):
        return "products"
    return "general"


def dedupe_sections(sections):
    deduped = []
    seen = set()

    for section in sections:
        text = clean_noise_text(section.get("text", ""))
        heading = clean_noise_text(section.get("heading", ""))

        if not text:
            continue

        key = text[:160].lower()

        if key in seen:
            continue

        seen.add(key)

        deduped.append({
            "heading": heading or None,
            "text": text,
            "sectionType": _classify_section_type(heading, text),
        })

    return deduped


def extract_sections(soup):
    sections = []

    main = soup.select_one("main") or soup.body or soup

    candidates = main.select(
        """
        section,
        .section,
        [class*='section'],
        [class*='block'],
        .elementor-widget-container,
        .wp-block-group,
        .oxy-rich-text,
        .ct-section
        """
    )

    for node in candidates:
        text = clean_noise_text(node.get_text(" "))

        if len(text) < 40:
            continue

        if is_bad_nav_or_utility_text(text):
            continue

        heading = None

        h = node.select_one("h1, h2, h3, .elementor-heading-title, .ct-headline")

        if h:
            heading = clean_noise_text(h.get_text(" "))

        if heading and is_bad_nav_or_utility_text(heading):
            heading = None

        sections.append({
            "heading": heading,
            "text": text[:2000]
        })

    if not sections:
        for h in main.select("h1, h2, h3, .elementor-heading-title, .ct-headline"):
            heading = clean_noise_text(h.get_text(" "))

            if not heading:
                continue

            parent = h.find_parent(["section", "div", "article"]) or h.parent
            text = clean_noise_text(parent.get_text(" ")) if parent else heading

            if len(text) >= 40 and not is_bad_nav_or_utility_text(text):
                sections.append({
                    "heading": heading,
                    "text": text[:2000]
                })

    return dedupe_sections(sections)[:35]


def detect_product_grid(soup):
    selectors = [
        ".products",
        "ul.products",
        ".woocommerce",
        ".wc-block-grid",
        ".product-grid",
        ".shop-products",
        "[class*='product-grid']",
        "[class*='products']",
        "li.product",
        ".type-product"
    ]

    for selector in selectors:
        if soup.select_one(selector):
            return True

    return False


def extract_home_products(soup, base_url):
    products = []

    product_nodes = soup.select(
        """
        li.product,
        .product,
        .type-product,
        .woocommerce-loop-product,
        .products li,
        ul.products li,
        .wc-block-grid__product,
        [class*='product-card'],
        [class*='product-item']
        """
    )

    for node in product_nodes:
        text = clean_noise_text(node.get_text(" "))

        if len(text) < 15:
            continue

        node_classes = " ".join(node.get("class", [])).lower()

        is_woocommerce_product = (
            "product" in node.get("class", [])
            or "type-product" in node_classes
            or node.select_one(".price")
            or node.select_one(".woocommerce-Price-amount")
        )

        link = None

        for a in node.select("a[href]"):
            href = a.get("href", "")
            href_lower = href.lower()

            if any(
                x in href_lower
                for x in [
                    "add-to-cart",
                    "wishlist",
                    "compare",
                    "cart",
                    "checkout",
                    "#"
                ]
            ):
                continue

            if is_woocommerce_product:
                if href and href != "#":
                    link = a
                    break

            elif any(x in href_lower for x in ["/product/", "/products/", "/shop/", "/sklep/"]):
                link = a
                break

        if not link:
            continue

        name = None

        for selector in [
            ".woocommerce-loop-product__title",
            ".product-title",
            ".product-name",
            ".wc-block-grid__product-title",
            "h2",
            "h3",
            "a[title]"
        ]:
            found = node.select_one(selector)

            if found:
                if selector == "a[title]":
                    name = clean_noise_text(found.get("title"))
                else:
                    name = clean_noise_text(found.get_text(" "))

                if name:
                    break

        if not name:
            name = clean_noise_text(link.get_text(" "))

        name = re.sub(
            r"\b(add to cart|quick view|wishlist|compare|select options|read more|clear|zobacz|wybierz opcję|wybierz opcje)\b",
            "",
            name,
            flags=re.I
        )
        name = clean_noise_text(name)

        if not name:
            continue

        price = extract_price_from_text(text)

        img_url = None
        img = node.find("img")

        if img:
            src = (
                img.get("data-src")
                or img.get("data-lazy-src")
                or img.get("data-original")
                or img.get("src")
            )

            if src:
                src = normalize_url(src, base_url)
                alt = clean_noise_text(img.get("alt"))

                if is_valid_image(src, alt):
                    img_url = src

        # Badge / sale label
        badge = None
        badge_node = node.select_one(
            ".onsale, .badge, [class*='badge'], [class*='label'], "
            "[class*='sale-badge'], [class*='promo']"
        )
        if badge_node:
            badge = clean_noise_text(badge_node.get_text(" ")) or None

        section_name = _find_product_section_name(node)

        products.append({
            "name": name,
            "url": normalize_url(link.get("href"), base_url),
            "price": price,
            "priceNormalized": normalize_price(price),
            "image": img_url,
            "badge": badge,
            "sectionName": section_name,
            "source": "dom"
        })

    return unique_items(products, "url")[:50]


def extract_collections_or_categories(soup, base_url):
    categories = []

    blocked_texts = [
        "quick view",
        "select options",
        "add to cart",
        "read more",
        "wishlist",
        "compare",
        "cart",
        "checkout",
        "my account",
        "login",
        "register",
        "home",
        "menu",
        "view all",
        "zobacz",
        "wybierz opcję",
        "wybierz opcje",
        "facebook",
        "instagram",
        "youtube",
        "linkedin",
        "tiktok"
    ]

    allowed_category_patterns = [
        "/product-category/",
        "/collections/",
        "/category/",
        "/kategoria/",
        "/sklep/nowosci/",
        "/sklep/bestsellery/",
        "/sklep/promocje/",
        "/sklep/zestawy/",
        "/brand/"
    ]

    product_url_patterns = [
        "/product/",
        "/products/",
        "/shop/",
        "/sklep/makijaz/",
        "/sklep/pielegnacja/"
    ]

    for a in soup.select("a[href]"):
        text = clean_noise_text(a.get_text(" "))
        href = a.get("href")

        if not text or not href:
            continue

        text_lower = text.lower()
        href_lower = href.lower()

        if text_lower in blocked_texts:
            continue

        if text_lower.isdigit():
            continue

        if any(
            bad in href_lower
            for bad in [
                "add-to-cart",
                "wishlist",
                "compare",
                "cart",
                "checkout",
                "mailto:",
                "tel:",
                "wa.me",
                "facebook",
                "instagram",
                "youtube",
                "linkedin",
                "tiktok"
            ]
        ):
            continue

        is_allowed_category = any(
            x in href_lower
            for x in allowed_category_patterns
        )

        is_product = any(
            x in href_lower
            for x in product_url_patterns
        )

        if is_product and not is_allowed_category:
            continue

        if not is_allowed_category:
            continue

        if re.search(r"\d+[,.]\d{2}\s*(zł|€|\$|£|rs|₨|pkr)", text_lower, re.I):
            continue

        if len(text) > 90:
            continue

        categories.append({
            "text": text,
            "url": normalize_url(href, base_url)
        })

    return unique_items(categories, "url")[:60]


# ---------------------------------------------------------------------------
# Product section-name detection & text-based product fallback
# ---------------------------------------------------------------------------

_PRODUCT_SECTION_KEYWORDS = {
    "best seller", "bestseller", "bestsellers", "featured product",
    "featured items", "featured", "newly added", "new arrival",
    "new arrivals", "new products", "hot bundle", "top pick", "top picks",
    "popular", "our product", "fresh track", "top motion", "website showcase",
    "sale", "on sale", "clearance", "recommended"
}


def _find_product_section_name(node):
    """Return the nearest recognizable product-section heading for a node."""
    for ancestor in node.parents:
        if ancestor.name not in ["section", "div", "article", "li", "ul", "main"]:
            continue

        for heading in ancestor.find_all(["h2", "h3", "h4"], recursive=False):
            text = clean_text(heading.get_text(" ")).lower()
            if any(k in text for k in _PRODUCT_SECTION_KEYWORDS):
                return clean_text(heading.get_text(" "))

        # Check the nearest preceding sibling heading at this level
        for sib in ancestor.find_previous_siblings(["h2", "h3"]):
            text = clean_text(sib.get_text(" ")).lower()
            if any(k in text for k in _PRODUCT_SECTION_KEYWORDS):
                return clean_text(sib.get_text(" "))
            break  # only nearest

        if ancestor.name in ["main", "body"]:
            break

    return None


# Text-based product pattern: "Product Name €99" or "AED 299 Product Name"
# Character class excludes sentence-ending punctuation (.!?) so that
# "Studio Size exclusively. Pop Out $9" does NOT merge into one name.
_HP_TEXT_PRODUCT_PATTERN = re.compile(
    r"(?P<name>[A-ZÀ-ÖĀ-ſ][^\n€$£₨\d.!?]{2,70}?)"
    r"\s*(?P<price>(?:AED|€|£|\$|₨|Rs\.?|PKR)\s*[\d,.]+(?:\.\d{1,2})?)",
    re.UNICODE
)


def extract_homepage_text_products(body_text, url, sections=None):
    """
    Fallback parser: extract products from raw page text when no product-grid
    DOM is present.  Matches "Product Name [currency][price]" patterns.
    Useful for Jina markdown homepages and text-only product showcases.

    `sections` is the list returned by extract_sections(); when provided, each
    extracted product is attributed to its nearest preceding section heading
    via the `sectionName` field.
    """
    products = []
    seen_names = set()

    junk_name_words = {
        "cart", "checkout", "menu", "home", "view", "add to",
        "quick view", "select", "read more", "click",
        # Section headings / nav items that bleed into product names:
        "motion", "view item", "find out more", "fresh tracks",
        "website showcase", "top motion", "hot bundle", "mockups",
        "music", "bundles", "newsletter", "subscribe",
    }

    # Build a position map of section headings so we can attribute each
    # extracted product to the section it appears under.
    section_positions = []
    for sec in (sections or []):
        heading = (sec.get("heading") or "").strip()
        if heading and len(heading) > 2:
            pos = body_text.find(heading)
            if pos >= 0:
                section_positions.append((pos, heading))
    section_positions.sort(key=lambda x: x[0])

    def _find_section_name(match_pos):
        """Return the nearest section heading that precedes match_pos."""
        name = None
        for pos, heading in section_positions:
            if pos <= match_pos:
                name = heading
            else:
                break
        return name

    # Use re.search with explicit pos so that when a match is rejected
    # (junk heading prefix, too many words), we can retry from m.start()+1
    # instead of m.end() — this recovers product names that were consumed
    # inside a rejected "SectionHeading ProductName $Price" match.
    pos = 0
    while pos < len(body_text):
        m = _HP_TEXT_PRODUCT_PATTERN.search(body_text, pos)
        if not m:
            break

        name = clean_text(m.group("name")).strip(" -–•→")
        price = clean_text(m.group("price"))

        def _is_junk():
            if len(name) < 3 or len(name) > 80:
                return True
            if len(name.split()) > 8:
                return True
            name_l = name.lower()
            return any(k in name_l for k in junk_name_words)

        if _is_junk():
            # Advance by 1 from match start so the regex can find a valid
            # sub-name that was hidden inside this rejected match.
            pos = m.start() + 1
            continue

        name_l = name.lower()
        pos = m.end()

        if name_l in seen_names:
            continue

        seen_names.add(name_l)
        products.append({
            "name": name,
            "url": None,
            "price": price,
            "priceNormalized": normalize_price(price),
            "image": None,
            "badge": None,
            "sectionName": _find_section_name(m.start()),
            "source": "homepage_text_fallback"
        })

    return products[:20]


def extract_ctas(soup, base_url):
    ctas = []

    cta_keywords = [
        "shop now",
        "shop",
        "buy now",
        "view products",
        "view collection",
        "contact us",
        "contact",
        "book now",
        "book service",
        "book service now",
        "get quote",
        "request quote",
        "free quote",
        "get a free quote",
        "request free quote",
        "enquire today",
        "enquiry",
        "get started",
        "start free",
        "free trial",
        "schedule demo",
        "book demo",
        "learn more",
        "read more",
        "more about us",
        "whatsapp",
        "call us",
        "kup",
        "kup teraz",
        "zobacz",
        "więcej",
        "wiecej",
        "czytaj więcej",
        "czytaj wiecej",
        "mehr erfahren",
        "jetzt kaufen",
        "kontakt",
        "anfragen",
        # Retailer / consumer-brand availability CTAs
        "where to buy",
        "find us in stores",
        "find in store",
        "find a store",
        "store locator",
        "find a retailer",
        "find our products",
        "available in stores",
        "available at retailers",
        "available nationwide",
        "find us near",
    ]

    blocked_ctas = [
        "facebook",
        "instagram",
        "youtube",
        "linkedin",
        "tiktok",
        "cookie",
        "privacy policy",
        "datenschutz"
    ]

    for a in soup.select("a[href], button"):
        text = clean_noise_text(a.get_text(" "))

        if not text:
            continue

        text_lower = text.lower()

        if text_lower in blocked_ctas:
            continue

        if any(k in text_lower for k in cta_keywords):
            href = a.get("href")

            if href and href.lower().startswith("javascript:"):
                continue

            ctas.append({
                "text": text,
                "url": normalize_url(href, base_url) if href else None
            })

    # ----------------------------------------------------------------
    # Text-based retailer availability CTA detection.
    # Consumer-brand pages (e.g. havengreens.ca) express their primary
    # conversion action as a plain sentence, not a hyperlink:
    #   "Available exclusively through retailers!"
    # Scan visible page text for these patterns and add synthetic CTA
    # items (url=None) so they surface in competitive analysis.
    # ----------------------------------------------------------------
    _retail_cta_phrases = [
        "available exclusively through retailers",
        "available exclusively through",
        "available through retailers",
        "available at retailers",
        "available in stores",
        "available nationwide",
        "find us in stores",
        "find us at",
        "find in store",
        "store locator",
        "find a retailer",
        "where to buy",
        "stocked at",
        "retail partner",
    ]
    _page_text_lower = clean_noise_text(
        (soup.select_one("main") or soup.body or soup).get_text(" ")
    ).lower()
    for phrase in _retail_cta_phrases:
        if phrase in _page_text_lower:
            # Extract the actual sentence from text (first occurrence).
            # We use the page text (not the lowercased version) to preserve
            # original casing, and cut at the first sentence-ending character.
            idx = _page_text_lower.find(phrase)
            sentence_start = max(0, idx)
            _raw_page_text = clean_noise_text(
                (soup.select_one("main") or soup.body or soup).get_text(" ")
            )
            snippet = _raw_page_text[sentence_start:sentence_start + 120]
            # Cut at the first sentence-ending punctuation (prefer ! or ?)
            for _sep in ("!", "?", "."):
                if _sep in snippet:
                    snippet = snippet[:snippet.index(_sep) + 1]
                    break
            raw = snippet.strip()
            if raw and len(raw) > 5:
                ctas.append({"text": raw, "url": None})
            break  # one retail CTA is enough

    return unique_items(ctas, "url")[:40]


def is_valid_phone(phone):
    phone = clean_noise_text(phone)

    if not phone:
        return False

    if re.search(r"\d{4}-\d{2}-\d{2}", phone):
        return False

    digits = re.sub(r"\D", "", phone)

    if len(digits) < 8:
        return False

    if len(digits) > 15:
        return False

    return True


def extract_contact_signals(soup):
    text = clean_noise_text(soup.get_text(" "))

    emails = re.findall(
        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
        text
    )

    raw_phones = re.findall(
        r"(?:\+?\d[\d\s().-]{7,}\d)",
        text
    )

    phones = []

    for phone in raw_phones:
        phone = clean_noise_text(phone)

        if is_valid_phone(phone):
            phones.append(phone)

    whatsapp_links = []

    for a in soup.select("a[href*='wa.me'], a[href*='whatsapp'], a[href*='join.chat']"):
        href = a.get("href")

        if href:
            whatsapp_links.append(href)

    return {
        "emails": list(dict.fromkeys(emails))[:10],
        "phones": list(dict.fromkeys(phones))[:10],
        "whatsappLinks": list(dict.fromkeys(whatsapp_links))[:10]
    }


def detect_spam_injection(text):
    text_lower = clean_text(text).lower()

    spam_keywords = [
        "casino",
        "казино",
        "1win",
        "1вин",
        "pin up",
        "пин ап",
        "gamstop",
        "mostbet",
        "pokerdom",
        "pinco",
        "bookmaker",
        "bukmeker",
        "online kaszino"
    ]

    matches = []

    for keyword in spam_keywords:
        if keyword in text_lower:
            matches.append(keyword)

    return {
        "hasSpamInjection": bool(matches),
        "matches": list(dict.fromkeys(matches))
    }


def extract_trust_signals(text):
    text_lower = clean_text(text).lower()

    trust_keywords = {
        "reviews": [
            "review",
            "reviews",
            "testimonial",
            "testimonials",
            "trustpilot",
            "rated",
            "oceniono",
            "happy customers",
            "verified buyers"
        ],
        "shipping": [
            "free shipping",
            "fast delivery",
            "same-day service",
            "worldwide free shipping",
            "delivery",
            "shipping"
        ],
        "guarantee": [
            "guarantee",
            "warranty",
            "satisfaction guarantee",
            "authenticity guaranteed",
            "money back",
            "refund"
        ],
        "credentials": [
            "certified",
            "licensed",
            "arc-certified",
            "medical device",
            "klinisch",
            "clinically",
            "validated",
            "research",
            "peer-reviewed",
            "qualified experts"
        ],
        "support": [
            "24/7 support",
            "customer support",
            "support team",
            "help",
            "service"
        ]
    }

    found = {}

    for group, keywords in trust_keywords.items():
        matches = []

        for keyword in keywords:
            if keyword in text_lower:
                matches.append(keyword)

        found[group] = matches

    return {
        "hasTrustSignals": any(found.values()),
        "signals": found
    }


def classify_homepage_style(text, business_model):
    text_lower = clean_text(text).lower()
    styles = []

    if business_model.get("primary") == "ecommerce":
        styles.append("catalog_ecommerce" if any(k in text_lower for k in [
            "best sellers", "bestsellery", "nowości", "featured products", "product categories"
        ]) else "brand_ecommerce")

    if business_model.get("primary") == "leadGeneration":
        styles.append("lead_generation")

    if any(k in text_lower for k in ["medical", "medizin", "schlafapnoe", "diagnostic", "clinical", "klinisch", "health"]):
        styles.append("medical")

    if any(k in text_lower for k in ["hvac", "air conditioning", "epoxy", "flooring", "repair", "installation", "services"]):
        styles.append("service_business")

    if any(k in text_lower for k in ["software platform", "analytics dashboard", "free trial", "book demo", "schedule demo", "subscription"]):
        styles.append("saas")

    if any(k in text_lower for k in ["our story", "o nas", "sincerely", "brand", "mission", "vision"]):
        styles.append("brand_storytelling")

    if not styles:
        styles.append("corporate")

    return list(dict.fromkeys(styles))


def detect_business_model(soup, products, categories, ctas, has_product_grid=False):
    """
    Classify the homepage business model into one of:
      ecommerce | leadGeneration | saas | platform | general

    Priority order:
      platform/SaaS (website builders, developer tools, open-source platforms)
      > ecommerce   (real stores with products / categories / cart)
      > leadGen     (service businesses with quote/contact/call CTAs)
      > general

    Prevents WooCommerce plugin presence alone from inflating ecommerce score
    on platform/SaaS sites like WooCommerce.com or Elementor.com.
    """
    cleaned_soup = clean_dom_for_content(str(soup))
    text = clean_noise_text(cleaned_soup.get_text(" ")).lower()
    html_lower = str(soup).lower()

    ecommerce_score = 0
    saas_score = 0
    leadgen_score = 0

    # -------------------------------------------------------
    # Platform / SaaS detection  (checked first, wins early)
    # -------------------------------------------------------
    # Strong signals: the page IS a software platform / website builder
    strong_platform_keywords = [
        "website builder", "site builder", "drag and drop", "drag-and-drop",
        "no-code", "no coding required", "build websites", "build your website",
        "open-source ecommerce platform", "open source ecommerce platform",
        "open-source commerce platform", "open source commerce platform",
        "build stores for others", "developer tools", "developer resources",
        "plugin marketplace", "woocommerce plugin", "wordpress plugin",
        "theme marketplace", "extension marketplace"
    ]

    soft_platform_keywords = [
        "free trial", "start free", "book demo", "schedule demo",
        "software platform", "crm software", "analytics dashboard",
        "login to dashboard", "api integration", "subscription plan",
        "workspace", "21m+", "21 million", "million websites",
        "plugin", "extension", "theme store", "developer", "open source"
    ]

    strong_platform_count = sum(1 for k in strong_platform_keywords if k in text)
    soft_platform_count   = sum(1 for k in soft_platform_keywords if k in text)

    if strong_platform_count >= 1:
        saas_score += 10
    elif soft_platform_count >= 2:
        saas_score += 6
    elif soft_platform_count >= 1:
        saas_score += 3

    cta_text = " ".join([c.get("text", "") for c in ctas]).lower()

    if any(k in cta_text for k in ["demo", "trial", "get started"]):
        saas_score += 2

    # -------------------------------------------------------
    # Ecommerce scoring
    # -------------------------------------------------------
    ecommerce_platform_signals = [
        "wp-content/plugins/woocommerce",
        "woocommerce-page",
        "single_add_to_cart_button",
        "product_type_simple",
        "ajax_add_to_cart",
        "wc-block-grid",
        "woocommerce-price-amount",
        "add-to-cart",
        "cart_url",
        "checkout_url",
        "cdn.shopify.com"
    ]

    ecommerce_text_signals = [
        "add to cart",
        "view cart",
        "checkout",
        "select options",
        "product-category",
        "dodaj do koszyka",
        "koszyk",
        "kup teraz"
    ]

    soft_ecommerce_text_signals = [
        "shop now",
        "buy now",
        "products",
        "collections",
        "sklep"
    ]

    if products:
        ecommerce_score += 8

    if len(products) >= 3:
        ecommerce_score += 3

    if categories:
        ecommerce_score += 3

    if categories and products:
        ecommerce_score += 3

    if has_product_grid:
        ecommerce_score += 7

    if any(k in text for k in ecommerce_text_signals):
        ecommerce_score += 5

    if any(k in text for k in soft_ecommerce_text_signals):
        ecommerce_score += 2

    # Only count WP plugin signals when the site is NOT itself a platform/SaaS
    if any(k in html_lower for k in ecommerce_platform_signals) and saas_score < 6:
        ecommerce_score += 6

    if any(k in cta_text for k in ["shop", "buy", "cart", "checkout", "kup", "sklep"]):
        ecommerce_score += 3

    # -------------------------------------------------------
    # Lead generation scoring
    # -------------------------------------------------------
    leadgen_keywords = [
        "contact us",
        "request quote",
        "get quote",
        "get a quote",
        "get a qoute",
        "free quote",
        "request free quote",
        "enquire today",
        "enquiry",
        "whatsapp",
        "call now",
        "book now",
        "book service",
        "contact our team",
        "get in touch",
        "please contact us",
        "request a call",
        "service request",
        "fill out the",
        "price calculator",
        "callback"
    ]

    if any(k in text for k in leadgen_keywords):
        leadgen_score += 5

    if any(k in cta_text for k in ["contact", "quote", "qoute", "whatsapp", "book", "enquire", "call"]):
        leadgen_score += 3

    if any(k in text for k in ["medical", "diagnostic", "klinisch", "sleep apnea", "schlafapnoe"]):
        leadgen_score += 2

    # Service-site boost: has service descriptions but no real product evidence
    service_terms = ["what we offer", "our services", "automation", "security", "installation"]
    if any(k in text for k in service_terms) and not products and not has_product_grid:
        leadgen_score += 2

    # -------------------------------------------------------
    # Strong ecommerce proof
    # Only REAL product evidence counts — WP plugin HTML signals
    # (ajax_add_to_cart, wc-block-grid etc.) appear on ALL WooCommerce
    # pages even when there are zero products, so we exclude them here.
    # They contribute to ecommerce_score but NEVER to strong_ecommerce.
    # -------------------------------------------------------
    strong_ecommerce = any([
        len(products) >= 2,
        has_product_grid,
        len(categories) >= 3 and bool(products),  # Need BOTH cats + products

        # WooCommerce price DOM element is a reliable signal (only appears on
        # actual product/shop pages, not on service/contact pages)
        "woocommerce-price-amount" in html_lower,

        # Visible "add to cart" text means cart buttons are actually rendered
        any(k in text for k in [
            "add to cart",
            "view cart",
            "dodaj do koszyka",
            "koszyk"
        ])
    ])

    # Strong product catalogue: 3+ categories + 3+ extracted products is
    # overwhelming ecommerce evidence.  Boost ecommerce score so that soft
    # SaaS signals from audience wording like "developers / artists / makers"
    # do not misclassify real stores as SaaS.  Dedicated platform sites
    # (saas_score >= 8 from strong_platform_keywords) still win.
    strong_catalogue = len(categories) >= 3 and len(products) >= 3
    if strong_catalogue:
        ecommerce_score += 10

    # -------------------------------------------------------
    # Consumer brand / manufacturer scoring
    # Signals: named products, no prices, no cart, retail
    # availability language, sustainability/production copy.
    # Typical examples: havengreens.ca, craft food/beverage
    # brands that sell only through retail partners.
    # -------------------------------------------------------
    retail_availability_keywords = [
        "available at retailers", "available exclusively through",
        "find us in stores", "available in stores", "in-store",
        "store locator", "find a retailer", "find in store",
        "available nationwide", "available at select", "where to buy",
        "major retailers", "grocery stores", "find our products",
        "find us near", "retail partner", "retail location",
        "find us at", "stocked at", "available at your local",
    ]
    sustainability_production_keywords = [
        "sustainab", "greenhouse", "locally grown", "local farm",
        "family farm", "organic", "certified", "b corp", "carbon neutral",
        "regenerative", "our farm", "our story", "our journey",
        "family legacy", "founded", "growers", "harvest",
        "production facility", "traceable", "non-gmo", "pesticide",
        "environmentally", "eco-friendly", "net zero", "biodegradable",
        "craft", "artisan", "handcrafted", "small batch",
    ]

    has_retail_availability = any(k in text for k in retail_availability_keywords)
    has_sustainability_copy = any(k in text for k in sustainability_production_keywords)
    no_cart_checkout = not any(
        k in text for k in ["add to cart", "checkout", "view cart", "buy now", "koszyk"]
    )

    manufacturer_score = 0
    if len(products) >= 3:
        manufacturer_score += 5
    if has_retail_availability:
        manufacturer_score += 6
    if has_sustainability_copy:
        manufacturer_score += 3
    if no_cart_checkout and not has_product_grid:
        manufacturer_score += 4
    # Products with size info (e.g. "113g", "500ml") are strong CPG signals
    if any(
        re.search(r'\b\d+\s*(?:g|kg|ml|oz|lb|lbs|cl|litre|liter)\b',
                  (p.get("name") or "") + " " + (p.get("size") or ""), re.I)
        for p in products
    ):
        manufacturer_score += 3

    scores = {
        "ecommerce": ecommerce_score,
        "saas": saas_score,
        "leadGeneration": leadgen_score,
        "manufacturer": manufacturer_score,
        "general": 1
    }

    # -------------------------------------------------------
    # Final decision  (platform/SaaS beats ecommerce, except
    # when strong product-catalogue evidence is present)
    # -------------------------------------------------------
    if saas_score >= 8 and not strong_catalogue:
        primary = "platform"

    elif saas_score >= 6 and not strong_catalogue:
        primary = "saas"

    elif ecommerce_score >= 8 and strong_ecommerce:
        primary = "ecommerce"

    elif leadgen_score >= 5:
        primary = "leadGeneration"

    elif leadgen_score >= 3 and not strong_ecommerce:
        primary = "leadGeneration"

    elif ecommerce_score >= 8:
        primary = "ecommerce"

    elif saas_score >= 3:
        primary = "saas"

    # Consumer brand / manufacturer: strong retail + production signals,
    # no real ecommerce evidence (no cart, no product grid, no prices)
    elif manufacturer_score >= 10 and not strong_ecommerce and saas_score < 6:
        primary = "consumer_brand"

    else:
        primary = "general"

    return {
        "primary": primary,
        "scores": scores,
        "strongEcommerceSignals": strong_ecommerce,
        "hasRetailAvailability": has_retail_availability,
        "hasSustainabilityCopy": has_sustainability_copy,
    }
    
def build_homepage_strategy(hero, sections, products, categories, ctas, contact,
                            trust_signals, business_model, schema_summary,
                            feature_bullets=None):
    """
    Classify homepage sections into typed strategy buckets.
    Returns a structured dict describing the homepage's intent and layout.
    """
    text_lower = " ".join([(s.get("text") or "") for s in sections]).lower()

    # --- audience ---
    audience_hints = []
    for kw, label in [
        ("small business", "small businesses"), ("enterprise", "enterprise"),
        ("developer", "developers"), ("designer", "designers"),
        ("agency", "agencies"), ("freelancer", "freelancers"),
        ("startup", "startups"), ("homeowner", "homeowners"),
        ("ecommerce store", "ecommerce merchants"),
        ("medium business", "medium businesses"),
        ("medium-sized business", "medium businesses"),
        ("smes", "SMEs"), ("sme ", "SMEs"),
        ("charit", "charities"),
        ("public sector", "public sector"),
        ("home user", "home users"),
        ("nonprofit", "nonprofits"), ("non-profit", "nonprofits"),
        ("school", "schools"), ("education", "educational organisations"),
    ]:
        if kw in text_lower:
            audience_hints.append(label)

    # --- value proposition ---
    # Prefer hero text that is NOT an SEO site-title (contains " | ").
    # Check subheadline first (the tagline), then headline, then fall back
    # to whichever is populated even if it contains " | ".
    value_prop = None
    for _vp_candidate in [
        hero.get("subheadline"),
        hero.get("headline"),
    ]:
        if _vp_candidate and " | " not in _vp_candidate:
            value_prop = _vp_candidate
            break
    if value_prop is None:
        # All candidates contained " | " — use subheadline/headline anyway
        value_prop = hero.get("subheadline") or hero.get("headline")

    # --- services ---
    def _sec_text(s):
        """Safe concatenation of section heading + text, both defaulting to ''."""
        return ((s.get("heading") or "") + " " + (s.get("text") or "")).lower()

    service_keywords = [
        "services", "solutions", "what we offer", "what we do",
        "capabilities", "features", "how it works"
    ]
    services_sections = [
        s for s in sections
        if any(k in _sec_text(s) for k in service_keywords)
        and s.get("sectionType") != "blog_section"
    ]

    # Prefer explicit service names from hero subheadings when the first
    # subheading is a "services" label (e.g. "Our Services" → followed by
    # individual service items: "IT consulting", "Cloud and remote working").
    _service_heading_labels = {
        "our services", "services", "what we offer", "what we do",
        "our offerings", "what we provide", "capabilities", "our solutions",
    }
    _hero_subs = hero.get("subheadings") or []
    _services_from_hero = []
    if _hero_subs and _hero_subs[0].strip().lower() in _service_heading_labels:
        _services_from_hero = [
            h.strip() for h in _hero_subs[1:]
            if h and 0 < len(h.split()) <= 7
        ][:8]

    # --- stats / social proof ---
    stats_keywords = ["customers", "users", "websites", "clients", "5-star",
                      "rating", "reviews", "downloads", "installs", "%"]
    stats_sections = [
        s for s in sections
        if any(k in _sec_text(s) for k in stats_keywords)
    ]

    # --- testimonials ---
    testimonial_keywords = ["testimonial", "review", "what our", "what clients",
                            "success story", "case study", "case studies",
                            "customer story"]
    testimonial_sections = [
        s for s in sections
        if any(k in _sec_text(s) for k in testimonial_keywords)
    ]

    # --- FAQ ---
    faq_sections = [
        s for s in sections
        if any(k in _sec_text(s) for k in ["faq", "frequently asked", "questions"])
    ]

    # --- consumer brand: narrative / sustainability / story sections ---
    brand_narrative_keywords = [
        "sustainability", "sustainable", "our story", "our journey",
        "family legacy", "family farm", "our mission", "our values",
        "about us", "our roots", "origin", "founded", "heritage",
        "greenhouse", "locally grown", "organic", "b corp", "certified",
        "carbon neutral", "regenerative", "harvest", "growers", "craft",
        "artisan", "handcrafted", "small batch", "production",
    ]
    brand_sections = [
        s for s in sections
        if any(k in _sec_text(s) for k in brand_narrative_keywords)
    ]

    # Feature bullets were pre-extracted in analyze_homepage() (which has soup
    # in scope) and passed in via feature_bullets=.  Fall back to empty list.
    _feature_bullets = feature_bullets or []

    # Service-business value props: look for "Why Choose Us" / "Why Us" sections
    # and collect the short-heading sections that follow them as individual
    # value-prop items (e.g. "We are a London Based IT Solutions Provider").
    _why_kw = [
        "why choose", "why us", "why pick", "what sets us apart",
        "our advantages", "our strengths", "what makes us different",
    ]
    _wcu_value_props: list = []
    for _wi, _wsec in enumerate(sections):
        _wh = (_wsec.get("heading") or "").lower()
        if any(k in _wh for k in _why_kw):
            for _sub in sections[_wi + 1: _wi + 9]:
                _sub_h = (_sub.get("heading") or "").strip()
                _sub_st = _sub.get("sectionType") or ""
                if (
                    _sub_h
                    and 2 <= len(_sub_h.split()) <= 12
                    and " | " not in _sub_h
                    and _sub_st not in ("blog_section", "products", "faq")
                ):
                    if _sub_h not in _wcu_value_props:
                        _wcu_value_props.append(_sub_h)
            break

    # Regex-based claim extraction: scan full section text for specific
    # credibility claims that are never short enough for the bullet scanner
    # (e.g. "over 25 years of experience", "24/7", "Security and Compliance").
    import re as _re_claims
    _claims_text = " ".join(
        (s.get("text") or "") + " " + (s.get("heading") or "")
        for s in sections
    )
    _claim_matchers = [
        # "over 25 years of experience" → "25+ years experience"
        (_re_claims.compile(r'\b(?:over\s+)?(\d+)\+?\s+years?\s+(?:of\s+)?experience\b',
                            _re_claims.IGNORECASE),
         lambda m: f"{m.group(1)}+ years experience"),
        # "24/7" anywhere → "24/7 support"
        (_re_claims.compile(r'\b24/7\b'),
         lambda _: "24/7 support"),
        # "Security and Compliance" → "Security & compliance"
        (_re_claims.compile(r'\bsecurity\s+and\s+compliance\b', _re_claims.IGNORECASE),
         lambda _: "Security & compliance"),
        # "same-day response" → "Same-day response"
        (_re_claims.compile(r'\bsame.?day\s+response\b', _re_claims.IGNORECASE),
         lambda _: "Same-day response"),
        # "no fix no fee" / "no fix, no fee" → "No fix, no fee"
        (_re_claims.compile(r'\bno\s+fix[,\s]+no\s+fee\b', _re_claims.IGNORECASE),
         lambda _: "No fix, no fee"),
    ]
    _claim_props: list = []
    for _pat, _fmt in _claim_matchers:
        _m = _pat.search(_claims_text)
        if _m:
            _val = _fmt(_m)
            if _val not in _claim_props:
                _claim_props.append(_val)

    # Merge sources: feature bullets first, then why-choose items, then brand sections.
    value_props = list(_feature_bullets[:10])
    for _item in _wcu_value_props:
        if _item not in value_props and len(value_props) < 10:
            value_props.append(_item)
    if not value_props:
        value_props = [
            (s.get("heading") or s.get("text") or "")[:100]
            for s in brand_sections[:5]
            if (s.get("heading") or s.get("text") or "")
        ]
    # Append regex-derived claims (always, regardless of other sources)
    for _item in _claim_props:
        if _item not in value_props and len(value_props) < 10:
            value_props.append(_item)

    # Content angles: use section headings when they are informative
    # (not SEO site-title strings), then supplement with theme keywords
    # found in the section body text.
    _angle_themes = [
        # (keyword_to_search, human_readable_label)
        ("family farm",          "Family farming heritage"),
        ("family legacy",        "Family farming legacy"),
        ("55-year",              "55-year farming legacy"),
        ("sustainab",            "Sustainability focus"),
        ("food insecur",         "Food security mission"),
        ("pesticide-free",       "Pesticide-free growing"),
        ("no pesticide",         "No pesticides"),
        ("locally grown",        "Locally grown produce"),
        ("locally supplied",     "Local supply chain"),
        ("local farm",           "Local farming"),
        ("advanced automat",     "Advanced growing automation"),
        ("automated greenhouse", "Automated greenhouse"),
        ("greenhouse",           "Greenhouse production"),
        ("year-round",           "Year-round availability"),
        ("b corp",               "B Corp certified"),
        ("carbon neutral",       "Carbon neutral operations"),
        ("regenerative",         "Regenerative agriculture"),
        ("organic",              "Organic practices"),
        ("artisan",              "Artisan craftsmanship"),
        ("small batch",          "Small-batch production"),
        ("craft",                "Craft production"),
        ("handcraft",            "Handcrafted products"),
        ("community",            "Community focus"),
    ]
    _brand_body_text = " ".join(
        (s.get("text") or "") + " " + (s.get("heading") or "")
        for s in brand_sections
    ).lower()
    _full_text_lower = text_lower  # already available in calling scope
    _combined_lower = _brand_body_text or _full_text_lower

    _angle_candidates: list = []
    # First: informative section headings (exclude SEO titles)
    for s in brand_sections:
        _h = (s.get("heading") or "").strip()
        if _h and " | " not in _h and len(_h.split()) >= 2:
            _angle_candidates.append(_h[:80])

    # Second: theme labels matched from body text
    for _kw, _label in _angle_themes:
        if _kw in _combined_lower and _label not in _angle_candidates:
            _angle_candidates.append(_label)

    content_angles = list(dict.fromkeys(_angle_candidates))[:8]

    # Retailer availability: any retail-channel language on the page
    retail_cta_keywords = [
        "where to buy", "find us in stores", "store locator",
        "find a retailer", "available nationwide", "available at retailers",
        "available exclusively through", "find in store", "available in stores",
        "stocked at", "retail partner", "find us at", "available at your local",
    ]
    retailer_availability = any(k in text_lower for k in retail_cta_keywords)

    # --- contact ---
    # extract_contact_signals returns plural list keys: "emails", "phones", "whatsappLinks"
    _contact_emails = contact.get("emails") or []
    _contact_phones = contact.get("phones") or []
    _contact_whatsapp = contact.get("whatsappLinks") or []
    has_contact = bool(_contact_emails or _contact_phones or _contact_whatsapp)

    primary = business_model.get("primary", "general")

    return {
        "hero": {
            "headline": hero.get("headline"),
            "subheadline": hero.get("subheadline"),
            "ctas": hero.get("ctas", []),
            "image": hero.get("image"),
        },
        "valueProposition": value_prop,
        "audience": audience_hints,
        "businessModel": primary,
        "services": _services_from_hero or [
            (s.get("heading") or s.get("text") or "")[:80].strip()
            for s in services_sections[:5]
            if (s.get("heading") or s.get("text") or "").strip()
        ],
        "categories": [c.get("name") or c.get("text", "")
                       for c in categories[:10]],
        "featuredProducts": [
            {"name": p.get("name"), "price": p.get("price"),
             "section": p.get("sectionName")}
            for p in products[:50]
        ],
        "trustSignals": trust_signals,
        "valueProps": value_props,
        "contentAngles": content_angles,
        # Structured brand sections with sectionType classification.
        # Populated from brand_sections (narrative / sustainability content).
        # Each entry: {heading, sectionType, text[:200]}
        "brandSections": [
            {
                "heading": s.get("heading"),
                "sectionType": s.get("sectionType") or _classify_section_type(
                    s.get("heading"), s.get("text")
                ),
                "text": (s.get("text") or "")[:200],
            }
            for s in brand_sections[:8]
            if (s.get("heading") or s.get("text"))
        ],
        "retailerAvailability": retailer_availability,
        "stats": [(s.get("text") or "")[:120] for s in stats_sections[:3]],
        "testimonials": bool(testimonial_sections),
        "caseStudies": any(
            "case stud" in (s.get("heading") or "").lower() for s in testimonial_sections
        ),
        "faq": bool(faq_sections),
        "contact": {
            "hasContact": has_contact,
            "phone": _contact_phones[0] if _contact_phones else None,
            "email": _contact_emails[0] if _contact_emails else None,
            "whatsapp": _contact_whatsapp[0] if _contact_whatsapp else None,
        },
        "ctas": [c.get("text") for c in ctas[:8] if c.get("text")],
        "schema": {
            "hasOrganization": bool(schema_summary.get("organization")),
            "hasWebSite": bool(schema_summary.get("website")),
        },
    }


def analyze_homepage(self, url, html, headers, page_type, level1):
    result = self.base_result(
        url,
        html,
        headers,
        page_type,
        level1
    )

    soup = BeautifulSoup(html or "", "lxml")
    content_soup = clean_dom_for_content(html)

    result["source"]["extractor"] = "WordPress Homepage Extractor"

    json_ld_items = extract_json_ld_items(soup)
    schema_summary = extract_schema_summary(json_ld_items)

    # Schema-domain mismatch: flag when the schema Organization URL points to a
    # different domain than the page being analysed.  This commonly happens when
    # a WP theme ships with demo schema data that was never updated.
    try:
        import re as _re_schema
        _page_domain = _re_schema.sub(r'^www\.', '', url.split("//")[-1].split("/")[0].lower())
        _schema_org = (schema_summary.get("organization") or {})
        _schema_org_url = (_schema_org.get("url") or "").lower()
        _schema_org_domain = _re_schema.sub(r'^www\.', '', _schema_org_url.split("//")[-1].split("/")[0]) if _schema_org_url else ""
        if _schema_org_domain and _page_domain and _schema_org_domain != _page_domain:
            schema_summary["organizationDomainMismatch"] = True
            schema_summary["organizationConfidence"] = "low"
            schema_summary["_organizationNote"] = (
                f"Schema org '{_schema_org.get('name', '')}' uses domain '{_schema_org_domain}'"
                f", not '{_page_domain}'. Likely theme/template leftover."
            )
    except Exception:
        pass

    navigation = extract_navigation(soup, url)
    hero = extract_hero(content_soup, url)
    sections = extract_sections(content_soup)

    products = extract_home_products(soup, url)
    categories = extract_collections_or_categories(soup, url)

    body_text = clean_noise_text(content_soup.get_text(" "))

    if len(body_text) < 300:
        content_soup = soup
        body_text = clean_noise_text(soup.get_text(" "))

    # Text-based fallback: extract products from raw text when DOM finds none
    if not products:
        products = extract_homepage_text_products(body_text, url, sections=sections)

    ctas = extract_ctas(content_soup, url)
    contact = extract_contact_signals(content_soup)

    # Attempt to recover missing product URLs from CTA links that point to
    # product pages (e.g. text-fallback products have url: null, but the
    # hero or body already contains a "Pop Out → /product/pop-out/" CTA).
    if products and ctas:
        product_page_urls = [
            c["url"] for c in ctas
            if c.get("url") and (
                "/product/" in c.get("url", "")
                or "/shop/" in c.get("url", "")
                or "/item/" in c.get("url", "")
            )
        ]
        for product in products:
            if product.get("url") or not product_page_urls:
                continue
            slug = re.sub(r"[^a-z0-9]+", "-", product["name"].lower()).strip("-")
            for pu in product_page_urls:
                if slug in pu.lower():
                    product["url"] = pu
                    break

    has_product_grid = detect_product_grid(soup)

    # Category-card fallback: when a product grid is detected but no individual
    # products were extracted, the grid likely shows category cards (common on
    # automotive / industrial stores like SA Parts).  Create pseudo-products
    # from the category links so competitive analysis has catalogue data to
    # compare.  Only triggers when 4+ categories are present (strong signal
    # that this is a genuine category-card layout, not a data gap).
    if not products and has_product_grid and len(categories) >= 4:
        products = [
            {
                "name": cat["text"],
                "url": cat.get("url"),
                "price": None,
                "priceNormalized": None,
                "image": None,
                "badge": None,
                "sectionName": "Featured Categories",
                "source": "category_card_fallback",
                "type": "category",
            }
            for cat in categories[:20]
            if cat.get("text") and len(cat["text"]) > 2
        ]

    business_model = detect_business_model(
        soup=soup,
        products=products,
        categories=categories,
        ctas=ctas,
        has_product_grid=has_product_grid
    )

    nav_text = " ".join([
        link.get("text", "") + " " + link.get("url", "")
        for link in navigation
    ])

    spam = detect_spam_injection(body_text + " " + nav_text)

    trust_signals = extract_trust_signals(body_text)
    homepage_style = classify_homepage_style(body_text, business_model)

    # Build homepageTitle — always filter junk headings
    demo_keywords = ["xstore demo", "elementor demo", "sport demo", "theme demo"]

    seo_h1 = result.get("seo", {}).get("h1") or ""
    if seo_h1 and _is_hero_junk_heading(seo_h1):
        seo_h1 = ""

    hero_headline = hero.get("headline") or ""

    homepage_title = (
        seo_h1
        or hero_headline
        or result.get("seo", {}).get("title")
    )

    if homepage_title and any(k in homepage_title.lower() for k in demo_keywords):
        homepage_title = (
            hero_headline
            or result.get("openGraph", {}).get("title")
            or result.get("seo", {}).get("title")
        )

    result["content"] = {
        "homepageTitle": homepage_title,
        "hero": hero,
        "sections": sections,
        "mainText": body_text[:15000],
        "ctas": ctas
    }

    result["business"] = {
        "businessModel": business_model,
        "homepageStyle": homepage_style,
        "contact": contact,
        "trustSignals": trust_signals,
        "schema": schema_summary
    }

    result["security"] = spam

    has_cart_or_checkout = any(
        x in body_text.lower()
        for x in ["cart", "checkout", "add to cart", "koszyk", "dodaj do koszyka"]
    )

    has_categories = bool(categories)

    # hasEcommerceSignals requires real, visible product evidence.
    # DO NOT include strongEcommerceSignals here — WooCommerce plugin HTML
    # (ajax_add_to_cart etc.) appears on ALL WP sites even with no products.
    has_ecommerce_signals = bool(
        products                       # found product cards (DOM or text fallback)
        or has_product_grid            # detected a product grid in DOM
        or (has_categories and has_cart_or_checkout)   # nav cats + cart together
    )

    # Pre-extract feature bullets here where soup is in scope; passed down to
    # build_homepage_strategy() which otherwise has no access to the DOM.
    _feat_claim_kws = [
        # Consumer / food brand
        "grown", "free", "fresh", "local", "sustainab", "organic",
        "certified", "pesticide", "year-round", "greenhouse", "harvest",
        "handcraft", "craft", "artisan", "non-gmo", "natural",
        "carbon", "family", "farm", "supplied", "sourced",
        # Service / IT business
        "years experience", "year experience", "years of experience",
        "24/7", "same-day", "same day response",
        "no call-out", "no fix no fee",
        "certified technician", "certified engineer", "certified expert",
        "customer-centric", "customer centric",
        "london-based", "london based",
        "microsoft partner", "cisco partner", "iso certified",
    ]
    _feat_bullets: list = []
    _seen_feat: set = set()
    for _ftag in soup.select("li, p, h3, h4"):
        _fraw = clean_noise_text(_ftag.get_text(" "))
        if not _fraw or len(_fraw.split()) > 12 or len(_fraw) < 5:
            continue
        _flow = _fraw.lower()
        if any(k in _flow for k in _feat_claim_kws):
            _fkey = _flow[:40]
            if _fkey not in _seen_feat:
                _seen_feat.add(_fkey)
                _feat_bullets.append(_fraw)

    homepage_strategy = build_homepage_strategy(
        hero=hero,
        sections=sections,
        products=products,
        categories=categories,
        ctas=ctas,
        contact=contact,
        trust_signals=trust_signals,
        business_model=business_model,
        schema_summary=schema_summary,
        feature_bullets=_feat_bullets,
    )

    result["ecommerce"] = {
        "hasEcommerceSignals": has_ecommerce_signals,
        "featuredProductsCount": len(products),
        "featuredProducts": products[:50],
        "categoryLinks": categories[:60],
        "hasProductGrid": has_product_grid,
        "hasCategories": has_categories,
        "hasCartOrCheckout": has_cart_or_checkout
    }

    result["products"] = products[:50]

    result["navigation"] = {
        "links": navigation
    }

    result["structuredData"] = {
        "jsonLdCount": len(json_ld_items),
        "items": json_ld_items[:20],
        "schemaSummary": schema_summary
    }

    result["homepageStrategy"] = homepage_strategy

    confidence = 0.45

    if hero.get("headline"):
        confidence += 0.15

    if sections:
        confidence += 0.10

    if navigation:
        confidence += 0.05

    if products:
        confidence += 0.15

    if categories:
        confidence += 0.05

    if has_product_grid:
        confidence += 0.10

    if schema_summary.get("organization") or schema_summary.get("website"):
        confidence += 0.05

    if ctas:
        confidence += 0.05

    if spam.get("hasSpamInjection"):
        confidence -= 0.05

    result["source"]["confidence"] = round(
        min(max(confidence, 0.35), 0.95),
        2
    )

    return result
