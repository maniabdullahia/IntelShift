from __future__ import annotations

from typing import Any, Dict, List, Optional
from .utils import safe_get, as_list, clean_text, domain_from_url, normalize_price_value, detect_currency, unique_by, pct


def truncate(value: Any, limit: int = 700) -> str:
    text = clean_text(value)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def normalize_site_snapshot(raw: Dict[str, Any], key: str | None = None) -> Dict[str, Any]:
    site = raw.get("site", {}) if isinstance(raw.get("site"), dict) else {}
    pages = raw.get("pagesAnalyzed") or raw.get("pages") or []
    products = raw.get("products") or []

    domain = site.get("domain") or domain_from_url(safe_get(pages, [0, "url"], "")) or key or "unknown"
    platform = site.get("platform") or safe_get(pages, [0, "platform"], "Unknown")
    # User-facing tech label (real framework/CMS or a friendly fallback). Never
    # surface the internal "Unknown" routing key to users.
    display_platform = (
        site.get("displayPlatform")
        or safe_get(pages, [0, "displayPlatform"], None)
        or ("Custom / Undetected" if str(platform).strip().lower() in ("", "unknown") else platform)
    )

    normalized_pages = [normalize_page(p, domain=domain) for p in pages if isinstance(p, dict)]
    normalized_products = normalize_products(products, normalized_pages, domain=domain)

    page_type_counts: Dict[str, int] = {}
    for page in normalized_pages:
        page_type_counts[page["pageType"]] = page_type_counts.get(page["pageType"], 0) + 1

    categories = set(site.get("categoriesDetected") or [])
    vendors = set(site.get("vendorsDetected") or [])

    for product in normalized_products:
        if product.get("category"):
            categories.add(product["category"])
        if product.get("vendor"):
            vendors.add(product["vendor"])

    # Homepage products are excluded from the product LIST + totals (curated
    # showcase, not the catalog), but the categories/vendors they reveal are still
    # real signals the site sells. Fold them into the DETECTED sets so excluding
    # homepage products doesn't shrink categoriesDetected and fire a spurious
    # "categories removed" change alert for categories that are still on the site.
    for page in pages:
        if not isinstance(page, dict):
            continue
        if (page.get("pageType") or safe_get(page, ["page", "pageType"], "")) != "homepage":
            continue
        eco = page.get("ecommerce") or {}
        for p in list(as_list(page.get("products"))) + list(as_list(eco.get("featuredProducts"))):
            if not isinstance(p, dict):
                continue
            cat = clean_text(p.get("category"))
            if cat:
                categories.add(cat)
            ven = clean_text(p.get("vendor"))
            if ven:
                vendors.add(ven)

    priced = [p for p in normalized_products if p.get("priceValue") is not None]
    sections = extract_all_sections(normalized_pages, domain)

    return {
        "key": key or domain.replace(".", "_"),
        "domain": domain,
        "platform": platform,
        "displayPlatform": display_platform,
        "siteName": site.get("siteName"),
        "siteType": site.get("siteType"),
        "pricingSummary": site.get("pricingSummary") or {},
        "businessCategory": site.get("businessCategory"),
        "subCategories": site.get("subCategories") or [],
        "positioning": site.get("positioning") or [],
        "schemaVersion": raw.get("schemaVersion"),
        "generatedAt": raw.get("generatedAt"),
        "pagesAnalyzedCount": len(normalized_pages),
        "pageTypesAnalyzed": page_type_counts,
        "pages": normalized_pages,
        "sections": sections,
        "products": normalized_products,
        "catalog": {
            "totalUniqueProducts": len(normalized_products),
            "productsWithPrice": len(priced),
            "productsWithoutPrice": len(normalized_products) - len(priced),
            "priceCoverageRate": pct(len(priced), len(normalized_products)),
            "categoriesDetected": sorted([clean_text(x) for x in categories if clean_text(x)]),
            "vendorsDetected": sorted([clean_text(x) for x in vendors if clean_text(x)]),
            "priceMin": min([p["priceValue"] for p in priced], default=None),
            "priceMax": max([p["priceValue"] for p in priced], default=None),
            "currency": next((p.get("currency") for p in priced if p.get("currency")), None),
        },
        "homepage": extract_homepage_summary(normalized_pages),
        "collections": extract_collection_summaries(normalized_pages),
        "seo": extract_seo_summary(normalized_pages),
        "quality": extract_quality_summary(normalized_pages),
        "raw": raw,
    }


def normalize_page(page: Dict[str, Any], domain: str | None = None) -> Dict[str, Any]:
    seo = page.get("seo") or {}
    ecommerce = page.get("ecommerce") or {}
    content = page.get("content") or {}
    analysis_ready = page.get("analysisReady") or {}

    page_type = page.get("pageType") or safe_get(page, ["page", "pageType"], "unknown")
    url = page.get("url") or safe_get(page, ["page", "url"]) or safe_get(page, ["technical", "finalUrl"])

    text_sources = [
        content.get("heading"),
        content.get("title"),
        content.get("siteName"),
        content.get("collectionName"),
        content.get("summaryText"),
        content.get("mainText"),
    ]

    page_sections = normalize_page_sections(content.get("sections"), page_url=url, page_type=page_type, domain=domain)
    page_products = page.get("products") or safe_get(ecommerce, ["featuredProducts"], [])

    return {
        "url": url,
        "domain": domain or domain_from_url(url or ""),
        "pageType": page_type,
        "platform": page.get("platform"),
        "success": page.get("success", True),
        "seo": {
            "title": seo.get("title"),
            "metaDescription": seo.get("metaDescription"),
            "canonical": seo.get("canonical"),
            "h1": seo.get("h1"),
        },
        "openGraph": page.get("openGraph") or {},
        "navigation": page.get("navigation") or {},
        "content": content,
        "textEvidence": {
            "summary": truncate(" ".join([clean_text(x) for x in text_sources if clean_text(x)]), 1200),
            "headings": normalize_headings(content),
            "mainTextPreview": truncate(content.get("mainText") or content.get("summaryText") or "", 2500),
        },
        "sections": page_sections,
        # Raw full-text evidence captured by the analyzer (top/hero/footer/fullText).
        # Fed to the AI as a recovery net for anything structured extraction missed.
        "rawTextEvidence": page.get("rawTextEvidence") or {},
        "ecommerce": ecommerce,
        "productCountOnPage": page.get("productCountOnPage") or safe_get(ecommerce, ["productStats", "productCount"]) or len(page_products or []),
        "products": page_products,
        "analysisReady": analysis_ready,
        "extractionQuality": safe_get(analysis_ready, ["extractionQuality"], {}),
        "source": page.get("source") or {},
        "crawl": page.get("crawl") or {},
        "title": page.get("title") or seo.get("title") or content.get("siteName") or content.get("collectionName") or content.get("title"),
        "fallbackContent": page.get("fallbackContent"),
        # v2 snapshot page-level blocks (analyzer summaries preserved by the merger).
        "summary": page.get("summary") or {},
        "features": page.get("features") or {},
        "metrics": page.get("metrics") or {},
        # SaaS / business / general-page analyzer blocks.
        "pricing": page.get("pricing") or {},
        "saas": page.get("saas") or {},
        "business": page.get("business") or {},
        "homepageStrategy": page.get("homepageStrategy") or {},
        "generalPage": page.get("generalPage") or {},
    }


def normalize_headings(content: Dict[str, Any]) -> List[Dict[str, Any]]:
    headings = []
    for h in as_list(content.get("sectionHeadings")):
        if isinstance(h, dict):
            text = clean_text(h.get("text"))
            if text:
                headings.append({"text": text, "tag": h.get("tag")})
    for h in as_list(content.get("headings")):
        if isinstance(h, dict):
            text = clean_text(h.get("text"))
            if text:
                headings.append({"text": text, "tag": h.get("level") or h.get("tag")})
        else:
            text = clean_text(h)
            if text:
                headings.append({"text": text, "tag": None})
    return headings[:60]


def normalize_page_sections(sections: Any, page_url: str | None, page_type: str, domain: str | None) -> List[Dict[str, Any]]:
    out = []
    for idx, section in enumerate(as_list(sections), start=1):
        if not isinstance(section, dict):
            continue
        heading = clean_text(section.get("heading"))
        section_type = clean_text(section.get("type")) or "content_section"
        text_preview = truncate(section.get("textPreview"), 900)
        links = []
        for link in as_list(section.get("links"))[:25]:
            if isinstance(link, dict):
                links.append({"text": clean_text(link.get("text")), "url": link.get("url")})
        images = []
        for image in as_list(section.get("images"))[:12]:
            if isinstance(image, dict):
                images.append({"url": image.get("url"), "alt": clean_text(image.get("alt"))})
        rank = section.get("rank") or idx
        importance = score_section_importance(section_type, heading, text_preview, links, images, rank, page_type)
        out.append({
            "domain": domain,
            "pageUrl": page_url,
            "pageType": page_type,
            "rank": rank,
            "positionLabel": f"section_{rank}",
            "type": section_type,
            "heading": heading or None,
            "textPreview": text_preview,
            "links": links,
            "images": images,
            "linkCount": len(links),
            "imageCount": len(images),
            "importanceScore": importance["score"],
            "importanceLevel": importance["level"],
            "importanceReasons": importance["reasons"],
            "recommendedWorkspacePriority": workspace_priority(importance["score"]),
        })
    return out


def score_section_importance(section_type: str, heading: str, text: str, links: List[Dict[str, Any]], images: List[Dict[str, Any]], rank: int, page_type: str) -> Dict[str, Any]:
    score = 0
    reasons = []
    t = f"{section_type} {heading} {text}".lower()

    if rank <= 1:
        score += 25; reasons.append("above_the_fold_or_first_section")
    elif rank <= 3:
        score += 18; reasons.append("early_page_position")
    elif rank <= 6:
        score += 10; reasons.append("mid_page_position")

    type_weights = {
        "hero": 30,
        "hero_banner": 30,
        "collection_banner": 24,
        "collections": 22,
        "featured_products": 24,
        "bestsellers": 26,
        "promo": 24,
        "trust_signal": 28,
        "newsletter": 12,
        "blog_preview": 10,
        "content_section": 12,
    }
    for key, weight in type_weights.items():
        if key in section_type:
            score += weight; reasons.append(f"section_type_{key}"); break

    if any(x in t for x in ["sale", "off", "discount", "bundle", "deal", "flash"]):
        score += 18; reasons.append("promotion_or_discount_message")
    if any(x in t for x in ["shipping", "returns", "secure", "support", "authentic", "trusted", "cruelty free", "vegan"]):
        score += 18; reasons.append("trust_or_conversion_message")
    if any(x in t for x in ["best seller", "bestseller", "featured", "new", "collection", "shop"]):
        score += 12; reasons.append("merchandising_or_shop_intent")
    if len(links) >= 4:
        score += 8; reasons.append("multiple_cta_or_navigation_links")
    if images:
        score += 5; reasons.append("visual_merchandising_present")
    if page_type == "homepage":
        score += 5; reasons.append("homepage_section")

    score = min(100, score)
    level = "high" if score >= 70 else "medium" if score >= 40 else "low"
    return {"score": score, "level": level, "reasons": reasons}


def workspace_priority(score: int) -> str:
    if score >= 75:
        return "P1_show_prominently"
    if score >= 50:
        return "P2_show_in_details"
    if score >= 25:
        return "P3_keep_for_ai_context"
    return "P4_archive_context"


def normalize_products(products: List[Dict[str, Any]], pages: List[Dict[str, Any]], domain: str | None = None) -> List[Dict[str, Any]]:
    all_products: List[Dict[str, Any]] = []

    def add_product(product: Dict[str, Any], source_page: Dict[str, Any] | None = None):
        name = clean_text(product.get("name") or product.get("title"))
        url = product.get("productUrl") or product.get("url")
        price = product.get("price")
        price_value = normalize_price_value(price)
        currency = detect_currency(price)
        desc = product.get("description")
        if isinstance(desc, dict):
            description_text = desc.get("text") or desc.get("html")
        else:
            description_text = desc

        if not name and not url:
            return

        source_pages = product.get("sourcePages") or ([{"url": source_page.get("url"), "pageType": source_page.get("pageType"), "title": source_page.get("title"), "rank": product.get("rank")} ] if source_page else [])

        all_products.append({
            "domain": domain or (source_page or {}).get("domain"),
            "name": name,
            "handle": product.get("handle"),
            "productUrl": url,
            "imageUrl": product.get("imageUrl") or product.get("image"),
            "additionalImageUrls": product.get("additionalImageUrls") or [],
            "price": price,
            "priceValue": price_value,
            "currency": currency,
            "priceCompareAt": normalize_price_value(safe_get(price, ["compareAt"])) if isinstance(price, dict) else None,
            "isOnSale": bool(safe_get(price, ["isOnSale"])) if isinstance(price, dict) else False,
            "discountPercent": safe_get(price, ["discountPercent"]) if isinstance(price, dict) else None,
            "priceTextRaw": safe_get(price, ["priceTextRaw"]) if isinstance(price, dict) else clean_text(price),
            "availability": product.get("availability"),
            "category": product.get("category"),
            "vendor": product.get("vendor"),
            "productType": product.get("productType"),
            "tags": product.get("tags") or [],
            "badges": product.get("badges") or [],
            "shortDescription": truncate(product.get("shortDescription"), 700),
            "descriptionText": truncate(description_text, 1500),
            "options": product.get("options") or [],
            "variants": product.get("variants") or [],
            "variantCount": product.get("variantCount") or safe_get(product, ["metrics", "variantCount"], len(product.get("variants") or [])),
            # Variant labels (shades/sizes) + colour swatches so the catalog can
            # surface what we crawled instead of just a bare count.
            "variantOptions": product.get("variantOptions") or [],
            "swatches": product.get("swatches") or [],
            # Count the PRIMARY image too, not just the gallery: collection-card
            # extraction yields one main image and (usually) no additionalImageUrls,
            # so counting only the gallery falsely reports 0 images for every product.
            "imageCount": (
                safe_get(product, ["metrics", "imageCount"], 0)
                or ((1 if (product.get("imageUrl") or product.get("image")) else 0)
                    + len(product.get("additionalImageUrls") or []))
            ),
            "source": product.get("source") or {},
            "sourcePages": source_pages,
        })

    for product in products:
        if isinstance(product, dict):
            add_product(product)

    for page in pages:
        # Homepage products are curated marketing "featured" picks, not the real
        # catalog — and they duplicate items already sold in collections. We exclude
        # them entirely so product totals and comparisons reflect the actual catalog,
        # not the homepage showcase.
        if page.get("pageType") == "homepage":
            continue
        for product in as_list(page.get("products")):
            if isinstance(product, dict):
                add_product(product, page)
        for product in as_list(safe_get(page, ["ecommerce", "featuredProducts"], [])):
            if isinstance(product, dict):
                add_product(product, page)
        single = safe_get(page, ["ecommerce", "product"])
        if isinstance(single, dict):
            add_product(single, page)

    # A product can appear BOTH in the catalog list and on a crawled page. Dedup
    # keeps the FIRST record (catalog, added first, without page provenance), so we
    # first collect every occurrence's sourcePages per product and re-attach the
    # merged set — otherwise "this product was shown on page X" is lost, and on-page
    # filtering (products_for_collection) can't tell what was actually on the page.
    prod_key = lambda p: (clean_text(p.get("productUrl")).lower() or clean_text(p.get("name")).lower())
    sp_bucket: Dict[str, List[Dict[str, Any]]] = {}
    for p in all_products:
        bucket = sp_bucket.setdefault(prod_key(p), [])
        for sp in p.get("sourcePages") or []:
            if isinstance(sp, dict):
                bucket.append(sp)
    deduped = unique_by(all_products, prod_key)
    for p in deduped:
        merged, seen_urls = [], set()
        for sp in sp_bucket.get(prod_key(p)) or []:
            u = clean_text(sp.get("url")).lower()
            if u and u in seen_urls:
                continue
            seen_urls.add(u)
            merged.append(sp)
        if merged:
            p["sourcePages"] = merged

    # Policy (ecommerce): homepage products — featured picks, curated showcases, or
    # products unique to the homepage — are NEVER counted in totals or any analysis.
    # Only products seen on a tracked non-homepage page (collection, single product, or
    # any other product-bearing page) qualify. A product survives if it has at least one
    # non-homepage source page; a product whose ONLY provenance is the homepage is dropped.
    # (Products with no page provenance at all come from the catalog list, not the
    # homepage, so they are kept.)
    def _homepage_only(p: Dict[str, Any]) -> bool:
        sps = [sp for sp in (p.get("sourcePages") or []) if isinstance(sp, dict)]
        return bool(sps) and all(sp.get("pageType") == "homepage" for sp in sps)

    deduped = [p for p in deduped if not _homepage_only(p)]
    return deduped


def extract_all_sections(pages: List[Dict[str, Any]], domain: str) -> List[Dict[str, Any]]:
    sections = []
    for page in pages:
        sections.extend(page.get("sections") or [])
    return sorted(sections, key=lambda s: (s.get("pageType") != "homepage", s.get("rank") or 999))


def extract_homepage_summary(pages: List[Dict[str, Any]]) -> Dict[str, Any]:
    homepage = next((p for p in pages if p.get("pageType") == "homepage"), None)
    if not homepage:
        return {"detected": False}

    content = homepage.get("content") or {}
    ecommerce = homepage.get("ecommerce") or {}
    # v2 snapshots carry analyzer features/metrics/summary at page level.
    features = homepage.get("features") or content.get("detectedFeatures") or {}
    metrics = homepage.get("metrics") or ecommerce.get("metrics") or {}
    summary = homepage.get("summary") or {}

    # ── Footer-inclusive signal fallback ────────────────────────────────
    # Only the Shopify analyzer emits hasNewsletter/hasTrustSignals/etc. For
    # WordPress/Wix/other analyzers we derive them from whatever text the
    # homepage carries — INCLUDING the footer, where newsletter signups, trust
    # badges and social links usually live.
    features = dict(features) if isinstance(features, dict) else {}
    _sections = homepage.get("sections") or content.get("sections") or []
    _footer = homepage.get("footer") or content.get("footer") or {}
    _footer_links = (homepage.get("footerLinks") or content.get("footerLinks")
                     or (_footer.get("links") if isinstance(_footer, dict) else None) or [])
    _trust_list = (summary.get("trustSignals") or homepage.get("trustSignals")
                   or content.get("trustSignals") or [])
    _parts = []
    for _s in _sections:
        if isinstance(_s, dict):
            _parts.append(_s.get("textPreview") or _s.get("text") or _s.get("heading") or "")
    for _fl in _footer_links:
        _parts.append(_fl.get("text") if isinstance(_fl, dict) else str(_fl))
    if isinstance(_footer, dict):
        _parts.append(_footer.get("text") or "")
    _parts.append(content.get("bodyText") or content.get("mainText") or homepage.get("textPreview") or "")
    _blob = " ".join(str(p) for p in _parts if p).lower()

    def _blob_has(keys):
        return any(k in _blob for k in keys)

    if not features.get("hasNewsletter"):
        features["hasNewsletter"] = _blob_has(
            ("newsletter", "subscribe", "mailing list", "sign up for", "email address", "join our list"))
    if not features.get("hasTrustSignals"):
        features["hasTrustSignals"] = (
            bool(_trust_list) or bool(summary.get("trustSignalCount"))
            or _blob_has(("free shipping", "secure checkout", "money back", "money-back",
                          "satisfaction guarantee", "easy returns", "warranty", "100% authentic", "ssl secure")))
    if not features.get("hasDiscountMessaging"):
        features["hasDiscountMessaging"] = _blob_has(("sale", "discount", "% off", "promo code", "coupon"))
    if not features.get("hasHero"):
        features["hasHero"] = bool(summary.get("heroType"))
    if not features.get("hasBlogPreview"):
        features["hasBlogPreview"] = _blob_has(("blog", "article", "journal", "read more", "our stories"))
    if not features.get("hasTestimonials"):
        features["hasTestimonials"] = _blob_has(("testimonial", "reviews", "loved by", "what our customers", "rated"))
    if not features.get("hasInstagramFeed"):
        features["hasInstagramFeed"] = "instagram" in _blob
    if not features.get("hasWhatsapp"):
        features["hasWhatsapp"] = "whatsapp" in _blob
    if not features.get("hasVideo"):
        features["hasVideo"] = _blob_has(("youtube", "vimeo", "watch video", "play video", "wistia"))

    # Announcement bar / promotional offers: surface the actual promo message
    # (e.g. "Avail Free Delivery on Bank Deposit Payments") so the report can show
    # a store's promotional lever, not just a yes/no flag.
    _ann = content.get("announcementBar") or {}
    announcement_text = clean_text(_ann.get("text")) if isinstance(_ann, dict) else None
    promotional_offers = features.get("promotionalOffers") or []

    return {
        "detected": True,
        "url": homepage.get("url"),
        "title": homepage.get("seo", {}).get("title"),
        "announcementText": announcement_text or None,
        "promotionalOffers": promotional_offers,
        "metaDescriptionPresent": bool(homepage.get("seo", {}).get("metaDescription")),
        "h1Present": bool(homepage.get("seo", {}).get("h1")),
        "sectionCount": metrics.get("sectionCount") or len(content.get("sections") or []),
        "featuredProductCount": metrics.get("featuredProductCount") or len(ecommerce.get("featuredProducts") or []),
        "featuredCollectionCount": metrics.get("featuredCollectionCount") or len(ecommerce.get("featuredCollections") or []),
        "ctaCount": metrics.get("ctaCount") or len(content.get("ctas") or []),
        "imageCount": metrics.get("imageCount") or len(content.get("images") or []),
        "features": features,
        "metrics": metrics,
        "positioning": summary.get("positioning") or [],
        "heroType": summary.get("heroType"),
        "trustSignalCount": summary.get("trustSignalCount"),
        "testimonialCount": summary.get("testimonialCount"),
        "primaryCtas": summary.get("primaryCtas") or [],
        "businessClassification": summary.get("businessClassification") or {},
        "sections": homepage.get("sections") or [],
    }


def extract_collection_summaries(pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for page in pages:
        if page.get("pageType") != "collection":
            continue
        stats = safe_get(page, ["ecommerce", "productStats"], {}) or {}
        summary = page.get("summary") or {}
        out.append({
            "url": page.get("url"),
            "title": safe_get(page, ["content", "collectionName"]) or summary.get("name") or page.get("title"),
            "productCount": stats.get("productCount") or page.get("productCountOnPage"),
            "currency": stats.get("currency"),
            "priceMin": safe_get(stats, ["priceRange", "min"]),
            "priceMax": safe_get(stats, ["priceRange", "max"]),
            "inStockCount": stats.get("inStockCount"),
            "outOfStockCount": stats.get("outOfStockCount"),
            "inStockRate": pct(stats.get("inStockCount") or 0, stats.get("productCount") or page.get("productCountOnPage") or 0),
            "hasFilters": bool(stats.get("hasFilters")),
            "hasSort": bool(stats.get("hasSort")),
        })
    return out


def extract_seo_summary(pages: List[Dict[str, Any]]) -> Dict[str, Any]:
    rows = []
    for page in pages:
        seo = page.get("seo") or {}
        title = clean_text(seo.get("title"))
        meta = clean_text(seo.get("metaDescription"))
        h1 = clean_text(seo.get("h1"))
        rows.append({
            "pageType": page.get("pageType"),
            "url": page.get("url"),
            "title": title,
            "titleLength": len(title),
            "metaDescription": meta or None,
            "metaDescriptionLength": len(meta),
            "metaDescriptionPresent": bool(meta),
            "h1": h1 or None,
            "h1Present": bool(h1),
            "canonicalPresent": bool(seo.get("canonical")),
        })
    return {
        "pagesWithMissingMetaDescription": sum(1 for r in rows if not r["metaDescriptionPresent"]),
        "pagesWithMissingH1": sum(1 for r in rows if not r["h1Present"]),
        "rows": rows,
    }


def extract_quality_summary(pages: List[Dict[str, Any]]) -> Dict[str, Any]:
    scores = []
    warnings = []
    for page in pages:
        q = page.get("extractionQuality") or {}
        if isinstance(q.get("score"), (int, float)):
            scores.append(q["score"])
        for warning in as_list(q.get("warnings")):
            warnings.append({"url": page.get("url"), "warning": warning})
    return {
        "averageExtractionScore": round(sum(scores) / len(scores), 3) if scores else None,
        "warnings": warnings,
        "failedPages": [p.get("url") for p in pages if p.get("success") is False],
    }
