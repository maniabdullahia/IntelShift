from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re
import json


def clean_text(text):
    return re.sub(r"\s+", " ", text or "").strip()


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


def _normalize_spaced_emails(text):
    """Collapse spaced email patterns like 'support @sivanna .com .pk' → 'support@sivanna.com.pk'.

    TLD parts must be lowercase-only to avoid absorbing sentence-starting words
    like 'Non' in 'support @sivanna .com .pk . Non-Returnable Items'.
    """
    pattern = re.compile(
        r'([A-Za-z0-9._%+-]+)\s+@\s*([A-Za-z0-9-]+(?:\s*\.\s*[a-z]{2,6})+)'
    )
    def _collapse(m):
        local  = m.group(1).strip()
        domain = re.sub(r'\s*\.\s*', '.', m.group(2)).strip()
        return f"{local}@{domain}"
    return pattern.sub(_collapse, text)


def _extract_policy_details(page_intent, main_text, emails):
    """Extract structured policy facts from shipping/return pages."""
    if page_intent not in ("shipping_policy", "return_policy"):
        return {}
    details = {}

    # Delivery window
    m = re.search(
        r'(?:delivery|delivered?)\s+within\s+([\d][\d\-]*\s+business\s+days?)',
        main_text, re.I
    )
    if not m:
        m = re.search(
            r'standard\s+shipping[^.]*?([\d][\d\-]*\s+business\s+days?)',
            main_text, re.I
        )
    if m:
        details["deliveryWindow"] = m.group(1).strip()

    # Return window
    m = re.search(r'returned?\s+within\s+([\d][\d\-]*\s+days?)', main_text, re.I)
    if not m:
        m = re.search(r'([\d][\d\-]*\s+days?)\s+of\s+receiv(?:ing|ed)', main_text, re.I)
    if m:
        details["returnWindow"] = m.group(1).strip()

    # Refund processing window
    m = re.search(
        r'refunds?\s+(?:will\s+be\s+)?process(?:ed)?\s+within\s+([\d][\d\-]*\s+business\s+days?)',
        main_text, re.I
    )
    if m:
        details["refundWindow"] = m.group(1).strip()

    # International shipping
    text_l = main_text.lower()
    if re.search(
        r"(?:do\s+not|don't)\s+offer\s+international\s+shipping"
        r"|no\s+international\s+shipping"
        r"|only\s+ship\s+within",
        text_l
    ):
        details["internationalShipping"] = False
    elif "international shipping" in text_l:
        details["internationalShipping"] = True

    # Ships-within region
    m = re.search(
        r'only\s+ship(?:ping)?\s+within\s+([A-Za-z][A-Za-z\s]+?)(?:\.|,|\d)',
        main_text, re.I
    )
    if m:
        details["shipsWithin"] = m.group(1).strip()

    # Contact email for this policy
    if emails:
        details["contactEmail"] = emails[0]

    return details


def _build_general_page_summary(page_intent, headings, emails, phones, main_text):
    """Build the normalised generalPageSummary object."""
    # Key facts: first substantive headings
    key_facts = [
        h.get("text", "") for h in headings
        if len(h.get("text", "")) > 8
    ][:5]

    # Brand claims (about pages only)
    brand_claims = []
    if page_intent == "about":
        _claim_patterns = [
            r'(?:operating|founded|established|in\s+operation)\s+since\s+\d{4}[^.]*',
            r'leading\s+\w+(?:\s+\w+)?\s+(?:manufacturer|producer|brand|company)[^.]*',
            r'available\s+in\s+over\s+\d+\s+countries[^.]*',
            r'retail\s+stores?\s+across\s+[A-Za-z\s,]+',
            r'(?:high|best)\s+quality\s+products?[^.]*',
            r'ethically\s+sourced[^.]*',
            r'over\s+\d+\s+years?\s+of[^.]*',
        ]
        for pat in _claim_patterns:
            m = re.search(pat, main_text, re.I)
            if m:
                snippet = m.group(0).strip().rstrip('.,;')
                if snippet and len(snippet) > 10 and snippet not in brand_claims:
                    brand_claims.append(snippet[:200])

    # Store locator signals
    # Common Title-Case words that are NOT geo entities (verbs, articles, generic nouns)
    _NON_GEO_WORDS = {
        "Explore", "Find", "Visit", "Search", "Click", "Contact", "Get",
        "Shop", "Learn", "See", "View", "Use", "Browse", "Discover", "Check",
        "Our", "The", "A", "An", "Your", "Their", "Its", "All", "No",
        "City", "Cities", "Town", "Towns", "Region", "Area", "Network",
        "Store", "Stores", "Retail", "Location", "Locations", "Map",
    }
    store_locator_signals = {}
    if page_intent == "store_locator":
        # Coverage: capture Title-Case words (proper geo nouns).
        # Post-filter: stop at the first word that's a common non-geo term.
        m = re.search(
            r'stores?\s+(?:in|across|throughout)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            main_text
        )
        if m:
            words = m.group(1).split()
            geo_words = []
            for w in words:
                if w in _NON_GEO_WORDS:
                    break
                geo_words.append(w)
            if geo_words:
                store_locator_signals["coverage"] = " ".join(geo_words)

        # Store count: JS-rendered pages may show "0 stores" in visible text.
        # Only accept counts > 0; otherwise signal that detection failed.
        m = re.search(r'(\d[\d,]*)\s+(?:retail\s+)?stores?', main_text, re.I)
        if m:
            n = int(m.group(1).replace(",", ""))
            if n > 0:
                store_locator_signals["storeCount"] = n
                store_locator_signals["storeCountDetected"] = True
            else:
                store_locator_signals["storeCount"] = None
                store_locator_signals["storeCountDetected"] = False
        else:
            store_locator_signals["storeCount"] = None
            store_locator_signals["storeCountDetected"] = False

    return {
        "subtype":  page_intent,
        "intent":   page_intent,
        "keyFacts": key_facts,
        "contactInfo": {
            "emails": emails[:10],
            "phones": phones[:10],
        },
        "policyDetails":       _extract_policy_details(page_intent, main_text, emails),
        "brandClaims":         brand_claims[:5],
        "storeLocatorSignals": store_locator_signals,
    }


def analyze_general(self, url, html, headers, page_type, level1):
    result = self.base_result(url, html, headers, page_type, level1)
    soup = BeautifulSoup(html or "", "lxml")

    result["source"]["extractor"] = "Shopify General Page Extractor"

    path = url.lower()

    page_intent = "general"

    if "/pages/about" in path or "about" in path:
        page_intent = "about"

    elif "/pages/contact" in path or "contact" in path:
        page_intent = "contact"

    elif "faq" in path or "frequently-asked" in path:
        page_intent = "faq"

    elif "shipping" in path or "delivery" in path:
        page_intent = "shipping_policy"

    elif "return" in path or "refund" in path:
        page_intent = "return_policy"

    elif "privacy" in path:
        page_intent = "privacy_policy"

    elif "terms" in path or "conditions" in path:
        page_intent = "terms_policy"

    elif any(kw in path for kw in [
        "find-store", "find-us", "store-locator", "store-finder",
        "locate-store", "our-stores", "where-to-buy", "stockist",
        "retailer", "outlet",
    ]):
        page_intent = "store_locator"

    # -------------------------
    # JSON-LD
    # -------------------------
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

    # -------------------------
    # Noise removal
    # -------------------------
    soup_for_content = BeautifulSoup(html or "", "lxml")

    for selector in [
        "script",
        "style",
        "noscript",
        "svg",
        "iframe",
        "header",
        "footer",
        "nav",
        "aside",
        "form",

        ".header",
        ".footer",
        ".site-header",
        ".site-footer",
        ".announcement-bar",
        ".top-bar",
        ".promo-bar",
        ".newsletter",
        ".popup",
        ".modal",
        ".drawer",
        ".cart-drawer",
        ".menu-drawer",
        ".predictive-search",
        ".search-modal",
        ".breadcrumb",
        ".breadcrumbs",
        ".share-buttons",
        ".social-share",
        ".pagination",

        "[class*='newsletter']",
        "[class*='popup']",
        "[class*='announcement']",
        "[class*='breadcrumb']",
        "[class*='social']",
        "[class*='share']",
        "[id*='newsletter']",
        "[id*='popup']"
    ]:
        for node in soup_for_content.select(selector):
            node.decompose()

    # -------------------------
    # Main content container
    # -------------------------
    possible_containers = []

    priority_selectors = [
        "main",
        "#MainContent",
        ".main-content",
        ".page",
        ".page-content",
        ".page-width",
        ".rte",
        ".shopify-policy__body",
        ".shopify-policy__container",
        "[class*='page']",
        "[class*='content']"
    ]

    for selector in priority_selectors:
        for node in soup_for_content.select(selector):
            text = clean_text(node.get_text(" "))

            if len(text) < 80:
                continue

            score = len(text)
            class_text = " ".join(node.get("class", [])).lower()
            node_id = node.get("id", "").lower()

            if "main" in node_id or "main" in class_text:
                score += 2000

            if "page" in class_text:
                score += 1500

            if "rte" in class_text:
                score += 1200

            if "policy" in class_text:
                score += 1500

            possible_containers.append((node, score))

    if possible_containers:
        content_node = sorted(
            possible_containers,
            key=lambda x: x[1],
            reverse=True
        )[0][0]
    else:
        content_node = soup_for_content.body or soup_for_content

    # -------------------------
    # Headings
    # -------------------------
    headings = []

    for h in content_node.find_all(["h1", "h2", "h3", "h4"]):
        text = clean_text(h.get_text(" "))
        if text:
            headings.append({
                "tag": h.name,
                "text": text
            })

    # -------------------------
    # Paragraphs
    # -------------------------
    paragraphs = []

    for p in content_node.find_all("p"):
        text = clean_text(p.get_text(" "))
        if len(text) >= 25:
            paragraphs.append(text)

    paragraphs = list(dict.fromkeys(paragraphs))

    # Content-based store locator detection (catches pages whose URL is generic)
    if page_intent == "general":
        _page_title = clean_text(
            result.get("openGraph", {}).get("title")
            or result.get("seo", {}).get("h1")
            or result.get("seo", {}).get("title")
            or ""
        )
        _heading_text = " ".join(h.get("text", "") for h in headings[:5])
        _check = (_page_title + " " + _heading_text).lower()
        _store_kws = [
            "find store", "find us", "store locator", "retail stores",
            "stores across", "city search", "near you", "where to buy",
            "our stores", "stockist",
        ]
        if any(kw in _check for kw in _store_kws):
            page_intent = "store_locator"

    # -------------------------
    # Lists / policy points
    # -------------------------
    list_items = []

    for li in content_node.find_all("li"):
        text = clean_text(li.get_text(" "))
        if len(text) >= 10:
            list_items.append(text)

    list_items = list(dict.fromkeys(list_items))

    # -------------------------
    # Images
    # -------------------------
    images = []

    for img in content_node.find_all("img"):
        src = (
            img.get("src")
            or img.get("data-src")
            or img.get("data-original")
            or img.get("data-lazy-src")
        )

        if not src:
            continue

        src_lower = src.lower()

        bad_patterns = [
            "icon",
            "logo",
            "placeholder",
            "avatar",
            "emoji",
            "whatsapp",
            "facebook",
            "instagram",
            "twitter",
            "pinterest",
            "linkedin",
            "svg"
        ]

        if any(pattern in src_lower for pattern in bad_patterns):
            continue

        if src.startswith("//"):
            src = "https:" + src
        elif src.startswith("/"):
            src = urljoin(url, src)

        images.append({
            "url": src,
            "alt": clean_text(img.get("alt", ""))
        })

    images = unique_items(images, "url")

    # -------------------------
    # Links
    # -------------------------
    internal_links = []
    external_links = []

    base_domain = url.split("/")[2].replace("www.", "")

    bad_link_patterns = [
        "facebook.com/sharer",
        "twitter.com/intent",
        "pinterest.com/pin",
        "linkedin.com/share",
        "whatsapp",
        ".atom"
    ]

    for a in content_node.find_all("a", href=True):
        text = clean_text(a.get_text(" "))
        href = a.get("href")

        if not href:
            continue

        if href.startswith("#") or href.startswith("mailto:") or href.startswith("tel:"):
            continue

        full_url = urljoin(url, href)

        if any(pattern in full_url.lower() for pattern in bad_link_patterns):
            continue

        link_obj = {
            "text": text,
            "url": full_url
        }

        if base_domain in full_url:
            internal_links.append(link_obj)
        else:
            external_links.append(link_obj)

    internal_links = unique_items(internal_links, "url")
    external_links = unique_items(external_links, "url")

    # -------------------------
    # Emails / phones / addresses
    # -------------------------
    body_text = clean_text(content_node.get_text(" "))

    # Normalize spaced emails (e.g. "support @sivanna .com .pk") before regex extraction
    _body_text_normalised = _normalize_spaced_emails(body_text)

    emails = list(set(re.findall(
        # Lookahead: after TLD must come whitespace, punctuation, period, or end-of-string.
        # Blocks over-greedy matches like 'support@sivanna.com.pk.Non' -> accepts '.pk' and
        # stops because the period before 'Non' satisfies (?=[\s,.;:)\]>"\'<.]|$).
        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?=[\s,;:)\]><.]|$)",
        _body_text_normalised
    )))

    phones = list(set(re.findall(
        r"(\+?\d[\d\s().-]{7,}\d)",
        body_text
    )))

    phones = [clean_text(p) for p in phones]

    # -------------------------
    # FAQ extraction
    # -------------------------
    faqs = []

    faq_nodes = content_node.find_all(["h2", "h3", "h4", "strong"])

    for node in faq_nodes:
        question = clean_text(node.get_text(" "))

        if "?" not in question:
            continue

        answer = ""
        current = node.find_next_sibling()

        while current:
            if current.name in ["h2", "h3", "h4"]:
                break

            text = clean_text(current.get_text(" "))

            if len(text) > 30:
                answer += " " + text

            current = current.find_next_sibling()

        answer = clean_text(answer)

        if len(answer) < 30:
            continue

        faqs.append({
            "question": question,
            "answer": answer[:1000]
        })

    # -------------------------
    # CTA detection
    # -------------------------
    cta_keywords = [
        "contact us",
        "shop now",
        "learn more",
        "get in touch",
        "send message",
        "call us",
        "email us",
        "start shopping",
        "browse products",
        "view collection",
        "read more"
    ]

    ctas = []

    for a in content_node.find_all("a", href=True):
        text = clean_text(a.get_text(" "))
        href = a.get("href")

        if not text or not href:
            continue

        if any(keyword in text.lower() for keyword in cta_keywords):
            ctas.append({
                "text": text,
                "url": urljoin(url, href)
            })

    ctas = unique_items(ctas, "url")

    # -------------------------
    # Commercial links
    # -------------------------
    collection_links = [
        link for link in internal_links
        if "/collections/" in link.get("url", "")
    ]

    product_links = [
        link for link in internal_links
        if "/products/" in link.get("url", "")
    ]

    # -------------------------
    # Clean main text
    # -------------------------
    bad_phrases = [
        "skip to main content",
        "continue reading",
        "rss",
        "cart 0 item",
        "share",
        "close"
    ]

    main_text = body_text

    for phrase in bad_phrases:
        main_text = re.sub(
            re.escape(phrase),
            "",
            main_text,
            flags=re.I
        )

    main_text = clean_text(main_text)

    # -------------------------
    # Result
    # -------------------------
    result["content"] = {
        "pageIntent": page_intent,
        "title": (
            result.get("openGraph", {}).get("title")
            or result.get("seo", {}).get("h1")
            or result.get("seo", {}).get("title")
        ),
        "headings": headings,
        "paragraphs": paragraphs[:100],
        "listItems": list_items[:100],
        "mainText": main_text[:15000],
        "images": images[:40],
        "internalLinks": internal_links[:100],
        "externalLinks": external_links[:50],
        "ctas": ctas[:30],
        "faqs": faqs[:30],
        "contactSignals": {
            "emails": emails[:20],
            "phones": phones[:20]
        }
    }

    result["ecommerce"] = {
        "collectionLinks": collection_links[:100],
        "productLinks": product_links[:100],
        "commercialIntent": bool(collection_links or product_links or ctas)
    }

    result["products"] = []

    result["structuredData"] = {
        "jsonLdCount": len(json_ld_items),
        "items": json_ld_items[:20]
    }

    # -------------------------
    # Confidence
    # -------------------------
    confidence = 0.45

    if main_text:
        confidence += 0.15

    if len(paragraphs) >= 1:
        confidence += 0.10

    if len(headings) >= 1:
        confidence += 0.10

    if page_intent != "general":
        confidence += 0.10

    if faqs:
        confidence += 0.05

    if emails or phones:
        confidence += 0.05

    result["source"]["confidence"] = round(min(confidence, 0.95), 2)

    # -------------------------
    # Store locator: propagate subtype to page + level1
    # -------------------------
    if page_intent == "store_locator":
        result["page"]["generalSubtype"] = "store_locator"
        if isinstance(result.get("level1"), dict):
            result["level1"]["generalSubtype"] = "store_locator"

    # -------------------------
    # General page summary
    # -------------------------
    result["generalPageSummary"] = _build_general_page_summary(
        page_intent=page_intent,
        headings=headings,
        emails=emails,
        phones=phones,
        main_text=main_text,
    )

    return result
