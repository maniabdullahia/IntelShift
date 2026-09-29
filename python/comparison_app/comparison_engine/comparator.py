from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Set
import re
from difflib import SequenceMatcher
from .normalizer import normalize_site_snapshot, truncate
from .utils import pct, clean_text
from .matching import (
    build_one_to_one_comparison,
    infer_category_label,
    infer_product_type,
    price_stats,
)


def _safe_shipping_payment(all_sites: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Best-effort shipping/payment signal comparison from policy-page text-evidence."""
    try:
        from comparison_engine.policy_signals import build_shipping_payment_comparison  # type: ignore
        return build_shipping_payment_comparison(all_sites)
    except Exception as exc:
        return {"displayType": "shipping_payment_table", "rows": [], "error": str(exc)}


def compare_sites(user_raw: Dict[str, Any], competitor_raws: List[Dict[str, Any]] | None = None) -> Dict[str, Any]:
    competitor_raws = competitor_raws or []

    user = normalize_site_snapshot(user_raw, key="user")
    competitors = [normalize_site_snapshot(raw, key=f"competitor_{idx+1}") for idx, raw in enumerate(competitor_raws)]
    all_sites = [user] + competitors

    # Compute shared modules ONCE and reuse them in the AI blocks below.
    one_to_one = build_one_to_one_comparison(user, competitors)
    page_match = build_page_match_comparison(user, competitors)
    navigation = build_navigation_comparison(user, competitors)
    collection_gaps = build_collection_gap_analysis(user, competitors)
    pricing_pages = build_pricing_page_comparison(user, competitors)
    services = build_services_comparison(user, competitors)
    homepage = build_homepage_comparison(all_sites)
    category_coverage = build_category_coverage_comparison(all_sites)
    sales_discounts = build_sale_discount_comparison(all_sites)
    content_depth = build_content_depth_comparison(all_sites)

    shared_modules = {
        "homepageComparison": homepage,
        "navigationComparison": navigation,
        "pageMatchComparison": page_match,
        "collectionGapAnalysis": collection_gaps,
        "pricingPageComparison": pricing_pages,
        "servicesComparison": services,
        "oneToOneComparison": one_to_one,
        "categoryCoverageComparison": category_coverage,
        "saleAndDiscountComparison": sales_discounts,
    }

    comparison = {
        "schemaVersion": "comparison_engine_v5",
        "displayType": "comparison_dashboard",
        "summary": build_summary(user, competitors),
        "sites": [site_overview(site) for site in all_sites],
        "catalogComparison": build_catalog_comparison(all_sites),
        "categoryCoverageComparison": category_coverage,
        "saleAndDiscountComparison": sales_discounts,
        "contentDepthComparison": content_depth,
        "productDetailComparison": build_product_detail_comparison(all_sites),
        "oneToOneComparison": one_to_one,
        "pageMatchComparison": page_match,
        "navigationComparison": navigation,
        "collectionGapAnalysis": collection_gaps,
        "pricingPageComparison": pricing_pages,
        "servicesComparison": services,
        "marketCoverageComparison": build_market_coverage_comparison(user, competitors),
        "priceComparison": build_price_comparison(all_sites),
        "inventoryComparison": build_inventory_comparison(all_sites),
        "homepageComparison": homepage,
        "sectionComparison": build_section_comparison(all_sites),
        "pageContentComparison": build_page_content_comparison(all_sites),
        "seoComparison": build_seo_comparison(all_sites),
        "merchandisingComparison": build_merchandising_comparison(all_sites),
        "trustAndConversionComparison": build_trust_conversion_comparison(all_sites),
        "shippingPaymentComparison": _safe_shipping_payment(all_sites),
        "dataQuality": build_data_quality(all_sites),
        "rankedInsights": build_ranked_insights(user, competitors, one_to_one, category_coverage, sales_discounts, content_depth, pricing_pages),
        "recommendations": build_recommendations(user, competitors),
        "workspaceLayoutHints": build_workspace_layout_hints(user, competitors),
        "appIntegrationContract": build_app_integration_contract(),
        "aiAnalysisInput": build_ai_analysis_input(user, competitors, shared_modules),
        "openAiEvidencePack": build_openai_evidence_pack(user, competitors, shared_modules),
    }

    return comparison


def site_overview(site: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "key": site["key"],
        "domain": site["domain"],
        "platform": site.get("displayPlatform") or site.get("platform"),
        "pagesAnalyzedCount": site["pagesAnalyzedCount"],
        "pageTypesAnalyzed": site["pageTypesAnalyzed"],
        "uniqueProducts": site["catalog"]["totalUniqueProducts"],
        "priceCoverageRate": site["catalog"]["priceCoverageRate"],
        "collectionCount": len(site["collections"]),
        "sectionCount": len(site.get("sections") or []),
        "navigationLinkCount": len(extract_navigation_links(site)),
        "pricingPageCount": len(pages_by_intent(site, "pricing")),
        "servicePageCount": len(pages_by_intent(site, "services")),
    }


def build_summary(user: Dict[str, Any], competitors: List[Dict[str, Any]]) -> Dict[str, Any]:
    site_type = user.get("siteType") or ("ecommerce" if user["catalog"]["totalUniqueProducts"] else "unknown")
    focus_by_type = {
        "ecommerce": ["categoryCoverageComparison", "oneToOneComparison", "priceComparison", "saleAndDiscountComparison", "inventoryComparison"],
        "saas": ["pricingPageComparison", "pageMatchComparison", "navigationComparison"],
        "business": ["servicesComparison", "pageMatchComparison", "navigationComparison"],
        "content": ["pageMatchComparison", "seoComparison", "navigationComparison"],
    }
    return {
        "mode": "competitive_comparison" if competitors else "single_site_baseline",
        "userDomain": user["domain"],
        "userSiteName": user.get("siteName"),
        "userSiteType": site_type,
        "userBusinessCategory": user.get("businessCategory"),
        "competitorDomains": [c["domain"] for c in competitors],
        "competitors": [
            {"domain": c["domain"], "siteName": c.get("siteName"), "siteType": c.get("siteType"), "businessCategory": c.get("businessCategory")}
            for c in competitors
        ],
        "sitesCompared": 1 + len(competitors),
        "recommendedFocusModules": focus_by_type.get(site_type, focus_by_type["ecommerce"]),
        "note": "v5: vertical-agnostic matching (category-gated), category coverage, sale/discount and content-depth modules, currency-guarded price comparison."
    }


def build_catalog_comparison(sites: List[Dict[str, Any]]) -> Dict[str, Any]:
    rows = []
    for site in sites:
        cat = site["catalog"]
        rows.append({
            "domain": site["domain"],
            "platform": site.get("displayPlatform") or site.get("platform"),
            "uniqueProducts": cat["totalUniqueProducts"],
            "productsWithPrice": cat["productsWithPrice"],
            "productsWithoutPrice": cat["productsWithoutPrice"],
            "priceCoverageRate": cat["priceCoverageRate"],
            "categoriesDetected": cat["categoriesDetected"],
            "vendorsDetected": cat["vendorsDetected"],
            "categoriesDetectedCount": len(cat["categoriesDetected"]),
            "vendorsDetectedCount": len(cat["vendorsDetected"]),
        })
    return {"displayType": "table", "rows": rows}


def build_category_coverage_comparison(sites: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Canonical category -> per-site product counts and price stats.

    Vertical-agnostic: categories come from matching.infer_product_type, so
    'Matte Lipstick' and 'Lips' both land in lip_color; 'Air Fryer 5L' and
    'Digital Airfryer' both land in kitchen_appliances.
    """
    per_site: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
    all_categories: Set[str] = set()
    for site in sites:
        buckets: Dict[str, List[Dict[str, Any]]] = {}
        for p in site["products"]:
            label = infer_product_type(p) or "uncategorized"
            buckets.setdefault(label, []).append(p)
        per_site[site["domain"]] = buckets
        all_categories.update(k for k in buckets if k != "uncategorized")

    user_domain = sites[0]["domain"] if sites else None
    rows = []
    for category in sorted(all_categories):
        row: Dict[str, Any] = {"category": category, "sites": {}}
        for site in sites:
            products = per_site[site["domain"]].get(category, [])
            row["sites"][site["domain"]] = {
                "productCount": len(products),
                "priceStats": price_stats(products),
                "onSaleCount": sum(1 for p in products if p.get("isOnSale")),
                "exampleProducts": [
                    {"name": p.get("name"), "priceValue": p.get("priceValue"), "productUrl": p.get("productUrl")}
                    for p in products[:5]
                ],
            }
        user_count = row["sites"].get(user_domain, {}).get("productCount", 0) if user_domain else 0
        best_comp = max((row["sites"][s["domain"]]["productCount"] for s in sites[1:]), default=0)
        row["userProductCount"] = user_count
        row["bestCompetitorProductCount"] = best_comp
        row["coverageStatus"] = (
            "user_only" if user_count and not best_comp
            else "competitor_only" if best_comp and not user_count
            else "both" if user_count and best_comp
            else "none"
        )
        rows.append(row)

    # A category the user shows SITE-WIDE (in navigation, collection names or
    # homepage sections) is NOT a real gap even if no *analyzed* product landed
    # in it — the user may simply not have selected that page for analysis. This
    # prevents false "you don't cover X" gaps (e.g. eyebrow) when the store does
    # carry the category but that page wasn't analyzed.
    user_site = sites[0] if sites else None
    user_covered: Set[str] = set(
        k for k in per_site.get(user_domain, {}) if k != "uncategorized"
    ) if user_domain else set()
    if user_site:
        extra_texts: List[Any] = []
        for coll in (user_site.get("collections") or []):
            if isinstance(coll, dict):
                extra_texts.append(coll.get("name") or coll.get("title") or coll.get("handle"))
        for nav in extract_navigation_links(user_site):
            extra_texts.append(nav.get("text"))
        for sec in (user_site.get("sections") or []):
            if isinstance(sec, dict):
                extra_texts.append(sec.get("label") or sec.get("heading") or sec.get("textPreview"))
        for _t in extra_texts:
            _lbl = infer_category_label(_t) if _t else None
            if _lbl:
                user_covered.add(_lbl)

    gap_categories = [
        r["category"] for r in rows
        if r["coverageStatus"] == "competitor_only" and r["category"] not in user_covered
    ]

    return {
        "displayType": "category_coverage_matrix",
        "description": "Canonical, vertical-agnostic category coverage: which categories each site sells, how deep, and at what prices. competitor_only rows are assortment gaps; user_only rows are differentiators.",
        "rows": rows,
        "userGapCategories": gap_categories,
        "userExclusiveCategories": [r["category"] for r in rows if r["coverageStatus"] == "user_only"],
    }


def build_sale_discount_comparison(sites: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Promotional intensity per site, from compareAt/isOnSale/discountPercent."""
    rows = []
    for site in sites:
        products = site["products"]
        on_sale = [p for p in products if p.get("isOnSale")]
        discounts = [p.get("discountPercent") for p in on_sale if isinstance(p.get("discountPercent"), (int, float))]
        priced = [p for p in products if p.get("priceValue") is not None]
        rows.append({
            "domain": site["domain"],
            "productsAnalyzed": len(products),
            "onSaleCount": len(on_sale),
            "onSaleRate": pct(len(on_sale), len(priced)) if priced else 0.0,
            "averageDiscountPercent": round(sum(discounts) / len(discounts), 1) if discounts else None,
            "maxDiscountPercent": max(discounts) if discounts else None,
            "deepestDiscounts": sorted(
                [
                    {"name": p.get("name"), "priceValue": p.get("priceValue"), "compareAt": p.get("priceCompareAt"), "discountPercent": p.get("discountPercent"), "productUrl": p.get("productUrl")}
                    for p in on_sale
                ],
                key=lambda x: x.get("discountPercent") or 0, reverse=True,
            )[:10],
            "discountMessagingOnHomepage": bool(site["homepage"].get("features", {}).get("hasDiscountMessaging")),
        })
    return {
        "displayType": "sale_discount_table",
        "description": "Promotional posture: how much of each catalog is on sale and how deep the discounts go. High competitor promo intensity is a pricing-pressure signal.",
        "rows": rows,
    }


def build_content_depth_comparison(sites: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Product content quality per site: descriptions, images, variants."""
    rows = []
    for site in sites:
        products = site["products"]
        n = len(products) or 1
        with_desc = [p for p in products if clean_text(p.get("descriptionText") or p.get("shortDescription"))]
        desc_lengths = [len(clean_text(p.get("descriptionText") or p.get("shortDescription"))) for p in with_desc]
        rows.append({
            "domain": site["domain"],
            "productsAnalyzed": len(products),
            "descriptionCoverageRate": pct(len(with_desc), n),
            "averageDescriptionLength": round(sum(desc_lengths) / len(desc_lengths)) if desc_lengths else 0,
            "imageCoverageRate": pct(sum(1 for p in products if p.get("imageUrl")), n),
            "averageImageCount": round(sum(p.get("imageCount") or 0 for p in products) / n, 1),
            "variantCoverageRate": pct(sum(1 for p in products if p.get("variantCount")), n),
            "totalVariants": sum(int(p.get("variantCount") or 0) for p in products),
            "averageVariants": round(sum(int(p.get("variantCount") or 0) for p in products) / n, 1),
            "availabilityDataCoverageRate": pct(sum(1 for p in products if p.get("availability")), n),
        })
    return {
        "displayType": "content_depth_table",
        "description": "Product page content depth. Richer descriptions/images/variants usually mean better SEO and conversion; low availability coverage means stock insights are unreliable.",
        "rows": rows,
    }


def build_product_detail_comparison(sites: List[Dict[str, Any]]) -> Dict[str, Any]:
    site_blocks = []
    for site in sites:
        products = []
        for idx, p in enumerate(site["products"], start=1):
            products.append({
                "rank": idx,
                "domain": site["domain"],
                "name": p.get("name"),
                "productUrl": p.get("productUrl"),
                "category": p.get("category"),
                "vendor": p.get("vendor"),
                "priceValue": p.get("priceValue"),
                "currency": p.get("currency"),
                "priceTextRaw": p.get("priceTextRaw"),
                "availability": p.get("availability"),
                "shortDescription": p.get("shortDescription"),
                "descriptionText": p.get("descriptionText"),
                "variantCount": p.get("variantCount"),
                "imageCount": p.get("imageCount"),
                "sourcePages": p.get("sourcePages"),
                "aiUsefulness": score_product_ai_usefulness(p),
            })
        site_blocks.append({
            "domain": site["domain"],
            "productCount": len(products),
            "products": products,
        })
    return {"displayType": "detailed_product_table", "sites": site_blocks}


def score_product_ai_usefulness(p: Dict[str, Any]) -> Dict[str, Any]:
    score = 0
    reasons = []
    if p.get("name"):
        score += 20; reasons.append("has_name")
    if p.get("priceValue") is not None:
        score += 25; reasons.append("has_price")
    if p.get("descriptionText") or p.get("shortDescription"):
        score += 25; reasons.append("has_description")
    if p.get("category"):
        score += 10; reasons.append("has_category")
    if p.get("variantCount"):
        score += 10; reasons.append("has_variants")
    if p.get("imageUrl"):
        score += 10; reasons.append("has_image")
    score = min(score, 100)
    return {"score": score, "level": "high" if score >= 70 else "medium" if score >= 40 else "low", "reasons": reasons}



# -----------------------------------------------------------------------------
# v4 Comparison Intelligence Layer
# Covers: homepage, navigation, page matching, collection gaps, SaaS pricing,
# services pages, and a stable AI/app contract.
# -----------------------------------------------------------------------------

CONCEPT_ALIASES: Dict[str, Set[str]] = {
    # Ecommerce / beauty
    "foundation": {"foundation", "foundations", "base", "bb cream", "cc cream", "concealer", "coverage"},
    "eyeshadow": {"eyeshadow", "eye shadow", "palette", "palettes", "eye makeup"},
    "lip_products": {"lipstick", "lip gloss", "lipgloss", "lip liner", "lip"},
    "skincare": {"skincare", "skin care", "serum", "cream", "cleanser", "face wash", "moisturizer"},
    "primer": {"primer", "makeup base", "base makeup"},
    "blush": {"blush", "blusher", "cheek"},
    "mascara": {"mascara", "lash"},
    "eyeliner": {"eyeliner", "kajal", "eye liner"},
    "sale_offers": {"sale", "discount", "offer", "bundle", "clearance", "deal"},

    # SaaS / B2B
    "pricing": {"pricing", "plans", "packages", "subscription", "billing", "starter", "growth", "pro", "enterprise"},
    "features": {"features", "product", "platform", "solutions", "capabilities"},
    "integrations": {"integrations", "apps", "connectors", "api", "webhooks"},
    "customers": {"customers", "case studies", "reviews", "testimonials", "logos"},
    "resources": {"blog", "resources", "guides", "help", "learn", "academy"},
    "security": {"security", "compliance", "privacy", "gdpr", "soc", "trust"},
    "demo_trial": {"demo", "trial", "book a demo", "start free", "free trial", "contact sales"},

    # Services / agency / local business
    "services": {"services", "service", "what we do", "solutions"},
    "consulting": {"consulting", "consultation", "strategy", "advisory"},
    "development": {"development", "web development", "software", "app development", "website"},
    "marketing": {"marketing", "seo", "social media", "ads", "ppc", "branding"},
    "support": {"support", "maintenance", "managed", "care plan", "helpdesk"},
    "contact": {"contact", "quote", "estimate", "inquiry", "consultation"},
}

PAGE_INTENT_ALIASES: Dict[str, Set[str]] = {
    "homepage": {"homepage", "home"},
    "pricing": CONCEPT_ALIASES["pricing"],
    "services": CONCEPT_ALIASES["services"] | CONCEPT_ALIASES["consulting"] | CONCEPT_ALIASES["development"] | CONCEPT_ALIASES["marketing"] | CONCEPT_ALIASES["support"],
    "collection": {"collection", "collections", "category", "shop", "products"},
    "product": {"product", "products", "item"},
    "blog": {"blog", "article", "resources", "guide"},
    "about": {"about", "company", "story", "team"},
    "contact": CONCEPT_ALIASES["contact"],
}


def _blob(*parts: Any) -> str:
    return " ".join(clean_text(p).lower() for p in parts if clean_text(p))


def _tokens(value: Any) -> Set[str]:
    text = re.sub(r"[^a-z0-9]+", " ", clean_text(value).lower())
    stop = {"the", "and", "or", "for", "with", "of", "in", "on", "to", "a", "an", "shop", "online", "best", "new"}
    return {x for x in text.split() if len(x) > 1 and x not in stop}


def _jaccard(a: Set[str], b: Set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _seq(a: Any, b: Any) -> float:
    a_s, b_s = clean_text(a).lower(), clean_text(b).lower()
    if not a_s or not b_s:
        return 0.0
    return SequenceMatcher(None, a_s, b_s).ratio()


def infer_concepts(*parts: Any) -> List[str]:
    blob = _blob(*parts)
    found = []
    for concept, aliases in CONCEPT_ALIASES.items():
        if any(alias in blob for alias in aliases):
            found.append(concept)
    return sorted(set(found))


def infer_page_intent(page: Dict[str, Any]) -> str:
    page_type = clean_text(page.get("pageType")).lower()
    # A structured e-commerce page type is definitive. A product or collection
    # page must never be relabelled a "pricing" page just because it shows a
    # price / variant prices — "pricing pages" are a SaaS/services concept.
    if page_type in {"product", "products", "item"}:
        return "product"
    if page_type in {"collection", "collections", "category", "categories", "catalog"}:
        return "collection"
    # Structured analyzer signal wins over text heuristics (but a homepage with
    # a pricing teaser is still a homepage, and hasPricing without extracted
    # plans is too weak - service pages often mention prices in passing).
    _pricing_block = page.get("pricing") or {}
    if page_type not in {"homepage", "home"} and _pricing_block.get("hasPricing") and (_pricing_block.get("plans") or []):
        return "pricing"
    url = clean_text(page.get("url")).lower()
    title = _blob(page.get("title"), page.get("seo", {}).get("title"), page.get("seo", {}).get("h1"), page.get("textEvidence", {}).get("summary"))
    combined = f"{page_type} {url} {title}"

    if page_type in {"homepage", "home"} or url.rstrip("/").count("/") <= 2 and page_type == "homepage":
        return "homepage"
    for intent, aliases in PAGE_INTENT_ALIASES.items():
        if intent in page_type:
            return intent
        if any(alias in combined for alias in aliases):
            return intent
    return page_type or "general"


def pages_by_intent(site: Dict[str, Any], intent: str) -> List[Dict[str, Any]]:
    return [p for p in site.get("pages", []) if infer_page_intent(p) == intent]


def compact_page(page: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "url": page.get("url"),
        "pageType": page.get("pageType"),
        "pageIntent": infer_page_intent(page),
        "title": page.get("title") or page.get("seo", {}).get("title"),
        "h1": page.get("seo", {}).get("h1"),
        "metaDescription": page.get("seo", {}).get("metaDescription"),
        "summary": page.get("textEvidence", {}).get("summary"),
        "sectionCount": len(page.get("sections") or []),
        "topSections": (page.get("sections") or [])[:8],
        "detectedConcepts": infer_concepts(page.get("url"), page.get("title"), page.get("seo", {}).get("title"), page.get("textEvidence", {}).get("summary")),
    }


def page_match_score(user_page: Dict[str, Any], comp_page: Dict[str, Any]) -> Tuple[float, List[str]]:
    reasons = []
    score = 0.0
    u_intent, c_intent = infer_page_intent(user_page), infer_page_intent(comp_page)
    if u_intent == c_intent:
        score += 0.45; reasons.append("same_page_intent")
    u_concepts = set(infer_concepts(user_page.get("url"), user_page.get("title"), user_page.get("textEvidence", {}).get("summary")))
    c_concepts = set(infer_concepts(comp_page.get("url"), comp_page.get("title"), comp_page.get("textEvidence", {}).get("summary")))
    concept_overlap = _jaccard(u_concepts, c_concepts)
    if concept_overlap:
        score += min(0.25, concept_overlap * 0.5); reasons.append("shared_business_concepts")
    token_overlap = _jaccard(_tokens(_blob(user_page.get("url"), user_page.get("title"))), _tokens(_blob(comp_page.get("url"), comp_page.get("title"))))
    if token_overlap:
        score += min(0.2, token_overlap * 0.5); reasons.append("url_title_keyword_overlap")
    title_ratio = _seq(user_page.get("title") or user_page.get("seo", {}).get("title"), comp_page.get("title") or comp_page.get("seo", {}).get("title"))
    if title_ratio >= 0.35:
        score += min(0.1, title_ratio * 0.1); reasons.append("title_similarity")
    return min(score, 1.0), reasons


def build_page_match_comparison(user: Dict[str, Any], competitors: List[Dict[str, Any]]) -> Dict[str, Any]:
    blocks = []
    for comp in competitors:
        matches = []
        used = set()
        user_unmatched = []
        for up in user.get("pages", []):
            best = None
            for idx, cp in enumerate(comp.get("pages", [])):
                if idx in used:
                    continue
                score, reasons = page_match_score(up, cp)
                if best is None or score > best[0]:
                    best = (score, reasons, idx, cp)
            if best and best[0] >= 0.35:
                score, reasons, idx, cp = best
                used.add(idx)
                matches.append({
                    "confidence": round(score, 3),
                    "matchReasons": reasons,
                    "pageIntent": infer_page_intent(up),
                    "userPage": compact_page(up),
                    "competitorPage": compact_page(cp),
                    "sectionGap": len(cp.get("sections") or []) - len(up.get("sections") or []),
                    "aiPromptHint": "Use this as a like-for-like page comparison. Homepage must always be considered when available.",
                })
            else:
                user_unmatched.append(compact_page(up))
        competitor_unmatched = [compact_page(cp) for idx, cp in enumerate(comp.get("pages", [])) if idx not in used]
        blocks.append({
            "competitorKey": comp.get("key"),
            "competitorDomain": comp.get("domain"),
            "matchedPageCount": len(matches),
            "matches": sorted(matches, key=lambda x: (x.get("pageIntent") != "homepage", -x.get("confidence", 0))),
            "userUnmatchedPages": user_unmatched,
            "competitorUnmatchedPages": competitor_unmatched,
        })
    return {
        "displayType": "page_match_matrix",
        "description": "Matches user and competitor pages by intent, including homepage, pricing, services, product, collection, blog, about, and contact pages.",
        "userDomain": user.get("domain"),
        "competitors": blocks,
    }


def extract_navigation_links(site: Dict[str, Any]) -> List[Dict[str, Any]]:
    links = []
    for page in site.get("pages", []):
        nav = page.get("navigation") or {}
        candidates = []
        for key in ["links", "mainLinks", "headerLinks", "footerLinks", "menu", "items", "navigationLinks"]:
            val = nav.get(key) if isinstance(nav, dict) else None
            if isinstance(val, list):
                candidates.extend(val)
        # fallback: use section links from first/homepage sections because nav extraction varies by analyzer
        if infer_page_intent(page) == "homepage":
            for section in page.get("sections") or []:
                candidates.extend(section.get("links") or [])
        for item in candidates:
            if not isinstance(item, dict):
                continue
            text = clean_text(item.get("text") or item.get("label") or item.get("name"))
            url = item.get("url") or item.get("href")
            if not text and not url:
                continue
            blob = _blob(text, url)
            links.append({
                "text": text or url,
                "url": url,
                "sourcePage": page.get("url"),
                "inferredIntent": infer_nav_intent(text, url),
                "detectedConcepts": infer_concepts(blob),
            })
    # de-duplicate
    seen, out = set(), []
    for l in links:
        key = (clean_text(l.get("text")).lower(), clean_text(l.get("url")).lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(l)
    return out[:200]


def infer_nav_intent(text: Any, url: Any) -> str:
    blob = _blob(text, url)
    for intent, aliases in PAGE_INTENT_ALIASES.items():
        if any(alias in blob for alias in aliases):
            return intent
    return "general"


def build_navigation_comparison(user: Dict[str, Any], competitors: List[Dict[str, Any]]) -> Dict[str, Any]:
    user_links = extract_navigation_links(user)
    user_concepts = set(c for l in user_links for c in l.get("detectedConcepts", []))
    user_intents = set(l.get("inferredIntent") for l in user_links)
    blocks = []
    for comp in competitors:
        comp_links = extract_navigation_links(comp)
        comp_concepts = set(c for l in comp_links for c in l.get("detectedConcepts", []))
        comp_intents = set(l.get("inferredIntent") for l in comp_links)
        blocks.append({
            "competitorDomain": comp.get("domain"),
            "userNavLinkCount": len(user_links),
            "competitorNavLinkCount": len(comp_links),
            "sharedConcepts": sorted(user_concepts & comp_concepts),
            "userOnlyConcepts": sorted(user_concepts - comp_concepts),
            "competitorOnlyConcepts": sorted(comp_concepts - user_concepts),
            "sharedPageIntents": sorted(user_intents & comp_intents),
            "missingUserPageIntents": sorted(comp_intents - user_intents),
            "userNavigationLinks": user_links[:80],
            "competitorNavigationLinks": comp_links[:80],
            "aiPromptHint": "Navigation is a summary of what the business wants users to discover. Treat competitor-only nav concepts as potential gaps or positioning differences, not automatic recommendations.",
        })
    return {"displayType": "navigation_gap_matrix", "userDomain": user.get("domain"), "competitors": blocks}


def site_concepts(site: Dict[str, Any]) -> Set[str]:
    """Canonical concept set for a site.

    Raw category strings are mapped through the vertical-agnostic taxonomy so
    'Matte Lipstick' (user) and 'Lips' (competitor) resolve to the SAME concept
    (lip_color) instead of appearing as fake gaps.
    """
    concepts: Set[str] = set()
    for raw_cat in site.get("catalog", {}).get("categoriesDetected") or []:
        label = infer_category_label(raw_cat)
        concepts.add(label or clean_text(raw_cat).lower())
    for page in site.get("pages", []):
        concepts.update(infer_concepts(page.get("url"), page.get("title"), page.get("seo", {}).get("title"), page.get("textEvidence", {}).get("summary")))
        label = infer_category_label(page.get("url"), page.get("title"))
        if label:
            concepts.add(label)
    for product in site.get("products", []):
        label = infer_product_type(product)
        if label:
            concepts.add(label)
        concepts.update(infer_concepts(product.get("name"), product.get("category")))
    return {c for c in concepts if c}


def build_collection_gap_analysis(user: Dict[str, Any], competitors: List[Dict[str, Any]]) -> Dict[str, Any]:
    user_concepts = site_concepts(user)
    blocks = []
    for comp in competitors:
        comp_concepts = site_concepts(comp)
        competitor_only = sorted(comp_concepts - user_concepts)
        user_only = sorted(user_concepts - comp_concepts)
        blocks.append({
            "competitorDomain": comp.get("domain"),
            "sharedConcepts": sorted(user_concepts & comp_concepts),
            "competitorOnlyConcepts": competitor_only,
            "userOnlyConcepts": user_only,
            "potentialUserGaps": [
                {
                    "concept": c,
                    "severity": "high" if c in {"pricing", "demo_trial", "services"} or infer_category_label(c.replace("_", " ")) else "medium",
                    "whyImportant": "Competitor has visible coverage for this collection/page/service concept while user snapshot does not show it clearly.",
                }
                for c in competitor_only[:30]
            ],
            "aiPromptHint": "Use this to identify missing collections, services, SaaS pages, or positioning themes. Verify with evidence before recommending.",
        })
    return {"displayType": "concept_gap_analysis", "userDomain": user.get("domain"), "competitors": blocks}


def extract_pricing_signals(page: Dict[str, Any]) -> Dict[str, Any]:
    # Prefer the analyzer's STRUCTURED pricing/saas blocks when present.
    pricing = page.get("pricing") or (page.get("generalPage") or {}).get("pricing") or {}
    saas = page.get("saas") or {}
    if pricing.get("hasPricing") and (pricing.get("plans") or []):
        plans = [p for p in (pricing.get("plans") or []) if isinstance(p, dict)]
        plan_details = [{
            "name": p.get("name"),
            "type": p.get("type"),
            "description": p.get("description"),
            "priceRaw": (p.get("price") or {}).get("raw"),
            "amount": (p.get("price") or {}).get("amount"),
            "period": (p.get("price") or {}).get("period"),
        } for p in plans]
        billing = pricing.get("billing") or {}
        return {
            "page": compact_page(page),
            "structured": True,
            "pricingModel": pricing.get("pricingModel"),
            "currency": pricing.get("currency"),
            "planNamesDetected": [p.get("name") for p in plans if p.get("name")],
            "plans": plan_details,
            "priceMentions": [d["priceRaw"] for d in plan_details if d.get("priceRaw")][:30],
            "billing": billing,
            "hasFreeTrial": bool(saas.get("hasFreeTrial")),
            "hasEnterprise": bool(saas.get("hasEnterpriseOffering")) or any("enterprise" in clean_text(p.get("name")).lower() for p in plans),
            "hasMonthlyPricing": bool(billing.get("monthly")),
            "hasAnnualPricing": bool(billing.get("annual")),
            "moneyBackGuarantee": billing.get("moneyBackGuarantee"),
            "hasApi": saas.get("hasApi"),
            "hasFeatureComparison": saas.get("hasFeatureComparison"),
            "aiCapabilities": saas.get("aiCapabilities") or [],
            "ctaLinks": [],
        }

    # Fallback: text-based heuristics (legacy snapshots).
    text = _blob(page.get("url"), page.get("title"), page.get("seo", {}).get("title"), page.get("textEvidence", {}).get("summary"), page.get("textEvidence", {}).get("mainTextPreview"))
    sections = page.get("sections") or []
    plan_names = []
    known = ["free", "starter", "basic", "growth", "professional", "pro", "business", "team", "enterprise", "custom"]
    for name in known:
        if re.search(rf"\b{name}\b", text):
            plan_names.append(name)
    prices = []
    for m in re.finditer(r"(?:\$|£|€|rs\.?|pkr)?\s?\d+(?:,\d{3})*(?:\.\d+)?\s?(?:/\s?(?:mo|month|yr|year|user|seat))?", text, re.I):
        raw = clean_text(m.group(0))
        if raw and any(ch.isdigit() for ch in raw):
            prices.append(raw)
    ctas = []
    for s in sections:
        for l in s.get("links") or []:
            label = clean_text(l.get("text"))
            if any(x in label.lower() for x in ["start", "trial", "demo", "buy", "subscribe", "contact", "sales"]):
                ctas.append({"text": label, "url": l.get("url")})
    return {
        "page": compact_page(page),
        "planNamesDetected": sorted(set(plan_names)),
        "priceMentions": prices[:30],
        "ctaLinks": ctas[:20],
        "hasFreeTrial": "free trial" in text or "start free" in text,
        "hasEnterprise": "enterprise" in text or "contact sales" in text,
        "hasMonthlyPricing": any(x in text for x in ["/mo", "/month", "monthly"]),
        "hasAnnualPricing": any(x in text for x in ["/yr", "/year", "annual", "yearly"]),
    }


def build_pricing_page_comparison(user: Dict[str, Any], competitors: List[Dict[str, Any]]) -> Dict[str, Any]:
    def signal_rank(sig):
        return (1 if sig.get("structured") else 0, len(sig.get("plans") or []))

    user_pages = pages_by_intent(user, "pricing")
    user_signals = sorted([extract_pricing_signals(p) for p in user_pages], key=signal_rank, reverse=True)
    blocks = []
    for comp in competitors:
        comp_pages = pages_by_intent(comp, "pricing")
        comp_signals = sorted([extract_pricing_signals(p) for p in comp_pages], key=signal_rank, reverse=True)
        user_plans = set(x for sig in user_signals for x in sig["planNamesDetected"])
        comp_plans = set(x for sig in comp_signals for x in sig["planNamesDetected"])

        def plan_amounts(signals):
            return [p.get("amount") for sig in signals for p in (sig.get("plans") or []) if isinstance(p.get("amount"), (int, float))]

        def iso_currency(value):
            symbol_map = {"$": "USD", "US$": "USD", "£": "GBP", "€": "EUR", "₹": "INR", "₨": "PKR", "RS": "PKR", "RS.": "PKR"}
            v = clean_text(value).upper()
            return symbol_map.get(v, v or None)

        u_amounts, c_amounts = plan_amounts(user_signals), plan_amounts(comp_signals)
        u_cur = iso_currency(next((sig.get("currency") for sig in user_signals if sig.get("currency")), None))
        c_cur = iso_currency(next((sig.get("currency") for sig in comp_signals if sig.get("currency")), None))
        plan_price_comparison = None
        if u_amounts and c_amounts:
            plan_price_comparison = {
                "sameCurrency": bool(u_cur and c_cur and u_cur == c_cur),
                "userCurrency": u_cur,
                "competitorCurrency": c_cur,
                "userEntryPrice": min(u_amounts),
                "competitorEntryPrice": min(c_amounts),
                "userTopPrice": max(u_amounts),
                "competitorTopPrice": max(c_amounts),
                "userPlanCount": len(u_amounts),
                "competitorPlanCount": len(c_amounts),
            }

        blocks.append({
            "planPriceComparison": plan_price_comparison,
            "competitorDomain": comp.get("domain"),
            "userPricingPageDetected": bool(user_signals),
            "competitorPricingPageDetected": bool(comp_signals),
            "userPricingSignals": user_signals,
            "competitorPricingSignals": comp_signals,
            "sharedPlanNames": sorted(user_plans & comp_plans),
            "competitorOnlyPlanNames": sorted(comp_plans - user_plans),
            "userOnlyPlanNames": sorted(user_plans - comp_plans),
            "aiPromptHint": "For SaaS, pricing pages are high priority. Compare plan structure, trial/demo CTAs, enterprise motion, price visibility, and packaging differences.",
        })
    return {"displayType": "saas_pricing_comparison", "userDomain": user.get("domain"), "competitors": blocks}


def extract_service_signals(page: Dict[str, Any]) -> Dict[str, Any]:
    concepts = infer_concepts(page.get("url"), page.get("title"), page.get("seo", {}).get("title"), page.get("textEvidence", {}).get("summary"), page.get("textEvidence", {}).get("mainTextPreview"))
    return {
        "page": compact_page(page),
        "serviceConcepts": [c for c in concepts if c in {"services", "consulting", "development", "marketing", "support", "contact"}],
        "ctaCount": sum(len(s.get("links") or []) for s in page.get("sections") or []),
        "topSections": (page.get("sections") or [])[:10],
    }


def build_services_comparison(user: Dict[str, Any], competitors: List[Dict[str, Any]]) -> Dict[str, Any]:
    user_pages = [p for p in user.get("pages", []) if infer_page_intent(p) in {"services", "contact"}]
    user_signals = [extract_service_signals(p) for p in user_pages]
    user_services = set(c for sig in user_signals for c in sig["serviceConcepts"])
    blocks = []
    for comp in competitors:
        comp_pages = [p for p in comp.get("pages", []) if infer_page_intent(p) in {"services", "contact"}]
        comp_signals = [extract_service_signals(p) for p in comp_pages]
        comp_services = set(c for sig in comp_signals for c in sig["serviceConcepts"])
        blocks.append({
            "competitorDomain": comp.get("domain"),
            "userServicePageCount": len(user_pages),
            "competitorServicePageCount": len(comp_pages),
            "sharedServiceConcepts": sorted(user_services & comp_services),
            "competitorOnlyServiceConcepts": sorted(comp_services - user_services),
            "userOnlyServiceConcepts": sorted(user_services - comp_services),
            "userServiceSignals": user_signals,
            "competitorServiceSignals": comp_signals,
            "aiPromptHint": "For service businesses, compare service coverage, CTA strength, page depth, proof/trust sections, and contact/quote paths.",
        })
    return {"displayType": "services_comparison", "userDomain": user.get("domain"), "competitors": blocks}


def build_market_coverage_comparison(user: Dict[str, Any], competitors: List[Dict[str, Any]]) -> Dict[str, Any]:
    user_concepts = site_concepts(user)
    rows = [{"domain": user.get("domain"), "role": "user", "conceptCount": len(user_concepts), "concepts": sorted(user_concepts)}]
    for comp in competitors:
        concepts = site_concepts(comp)
        rows.append({
            "domain": comp.get("domain"),
            "role": "competitor", "conceptCount": len(concepts), "concepts": sorted(concepts),
            "coverageDifferenceVsUser": len(concepts) - len(user_concepts),
        })
    return {"displayType": "market_coverage_table", "rows": rows}


def build_app_integration_contract() -> Dict[str, Any]:
    return {
        "version": "comparison_ui_contract_v1",
        "recommendedDashboardModules": [
            {"key": "rankedInsights", "label": "Top Insights", "priority": 1},
            {"key": "categoryCoverageComparison", "label": "Category Coverage", "priority": 2},
            {"key": "oneToOneComparison", "label": "Product / Collection 1-vs-1", "priority": 3},
            {"key": "priceComparison", "label": "Prices", "priority": 4},
            {"key": "saleAndDiscountComparison", "label": "Promotions & Discounts", "priority": 5},
            {"key": "homepageComparison", "label": "Homepage", "priority": 6},
            {"key": "navigationComparison", "label": "Navigation Gaps", "priority": 7},
            {"key": "pageMatchComparison", "label": "Page Matchups", "priority": 8},
            {"key": "collectionGapAnalysis", "label": "Missing Collections / Concepts", "priority": 9},
            {"key": "contentDepthComparison", "label": "Product Content Depth", "priority": 10},
            {"key": "pricingPageComparison", "label": "SaaS Pricing", "priority": 11},
            {"key": "servicesComparison", "label": "Services", "priority": 12},
            {"key": "dataQuality", "label": "Data Quality", "priority": 13},
        ],
        "aiResultRecommendedSchema": {
            "executiveSummary": "string",
            "impactScore": "number_0_100",
            "priorityInsights": [{"title": "string", "severity": "low|medium|high|critical", "whyItMatters": "string", "evidenceRefs": ["string"]}],
            "recommendedActions": [{"action": "string", "priority": "P1|P2|P3", "owner": "marketing|pricing|product|sales|seo|ops"}],
            "dashboardCards": [{"moduleKey": "string", "title": "string", "summary": "string", "score": "number_0_100"}],
        },
    }


def build_ai_analysis_input(user: Dict[str, Any], competitors: List[Dict[str, Any]], shared_modules: Dict[str, Any] | None = None) -> Dict[str, Any]:
    modules = shared_modules or {
        "homepageComparison": build_homepage_comparison([user] + competitors),
        "navigationComparison": build_navigation_comparison(user, competitors),
        "pageMatchComparison": build_page_match_comparison(user, competitors),
        "collectionGapAnalysis": build_collection_gap_analysis(user, competitors),
        "pricingPageComparison": build_pricing_page_comparison(user, competitors),
        "servicesComparison": build_services_comparison(user, competitors),
        "oneToOneComparison": build_one_to_one_comparison(user, competitors),
    }
    return {
        "purpose": "Send this compact deterministic pack to AI for final narrative analysis. It is designed for JSON-only AI output and dashboard integration.",
        "rulesForAI": [
            "Do not invent facts, products, prices, plans, services, or pages.",
            "Use homepage and navigation as high-priority evidence because they represent front-face positioning.",
            "Use pageMatchComparison for like-for-like page analysis.",
            "Use oneToOneComparison only for related collections/products; matches are category-gated.",
            "Use categoryCoverageComparison for assortment gaps and saleAndDiscountComparison for promo pressure.",
            "For SaaS, prioritize pricingPageComparison. For services, prioritize servicesComparison. For ecommerce, prioritize category/product/price/inventory comparisons.",
            "If priceComparison.sameCurrency is false, never compare absolute prices across sites.",
        ],
        "userDomain": user.get("domain"),
        "userSiteType": user.get("siteType"),
        "competitorDomains": [c.get("domain") for c in competitors],
        "modules": modules,
    }


def _norm_col_url(u: Any) -> str:
    """Normalize a collection/product URL for cross-side matching. Strips scheme,
    a leading "www.", query/fragment and a trailing slash, and lowercases — so a
    mapped owner url (often with www / https) matches the same collection url stored
    on a product's sourcePages (which may lack www). Without this, an owner whose
    urls carry "www." has EVERY product filtered out of the scoped price/inventory
    aggregates → blank average price and 0% in-stock."""
    s = (clean_text(u) or "").lower().strip()
    s = s.split("?")[0].split("#")[0]
    s = re.sub(r"^https?://", "", s)
    s = re.sub(r"^www\.", "", s)
    return s.rstrip("/")


def _mapped_collection_scope(sites: List[Dict[str, Any]]):
    """From the user's EXPLICIT collection mappings, return the set of mapped OWNER
    collection urls and a {competitor_domain: mapped_urls} map. This lets aggregates
    (price, inventory) be scoped to the SAME categories on both sides — otherwise an
    owner tracking more pages than the competitor gets an unfairly different average
    (e.g. owner avg over 20 collections vs competitor avg over the 11 mapped ones)."""
    owner_urls: set = set()
    comp_urls: Dict[str, set] = {}
    for s in sites[1:]:
        maps = (
            s.get("_userCollectionMappings")
            or (s.get("raw") or {}).get("_userCollectionMappings")
            or []
        )
        for mp in maps:
            if not isinstance(mp, dict):
                continue
            ou = _norm_col_url(mp.get("ownerUrl"))
            cu = _norm_col_url(mp.get("competitorUrl"))
            if ou:
                owner_urls.add(ou)
            if cu:
                comp_urls.setdefault(s.get("domain"), set()).add(cu)
    return owner_urls, comp_urls


def _scoped_products(site: Dict[str, Any], urls: set) -> List[Dict[str, Any]]:
    """The site's products that live in the given (normalized) collection urls, via
    each product's sourcePages. Empty `urls` → all products (no scoping)."""
    if not urls:
        return site.get("products", [])
    out = []
    for p in site.get("products", []):
        for sp in p.get("sourcePages") or []:
            if _norm_col_url(sp.get("url")) in urls:
                out.append(p)
                break
    return out


def build_price_comparison(sites: List[Dict[str, Any]]) -> Dict[str, Any]:
    owner_urls, comp_urls = _mapped_collection_scope(sites)
    scoped = bool(owner_urls or comp_urls)
    currencies = {s["catalog"].get("currency") for s in sites if s["catalog"].get("currency")}
    same_currency = len(currencies) <= 1
    rows = []
    for i, site in enumerate(sites):
        cat = site["catalog"]
        urls = owner_urls if i == 0 else comp_urls.get(site.get("domain"), set())
        # Scope to the mapped collections so both sides cover the SAME categories.
        products = _scoped_products(site, urls) if (scoped and urls) else site["products"]
        priced = [p for p in products if p.get("priceValue") is not None]
        prices = [p["priceValue"] for p in priced]
        rows.append({
            "domain": site["domain"],
            "currency": cat.get("currency"),
            "priceMin": min(prices) if prices else None,
            "priceMax": max(prices) if prices else None,
            "pricedProducts": len(priced),
            "averagePrice": round(sum(prices) / len(prices), 2) if prices else None,
            "lowestPricedProducts": sorted([
                {"name": p.get("name"), "price": p.get("priceValue"), "url": p.get("productUrl")} for p in priced
            ], key=lambda x: x["price"])[:10],
            "highestPricedProducts": sorted([
                {"name": p.get("name"), "price": p.get("priceValue"), "url": p.get("productUrl")} for p in priced
            ], key=lambda x: x["price"], reverse=True)[:10],
        })
    return {
        "displayType": "side_by_side",
        "sameCurrency": same_currency,
        # True when numbers reflect only the user's mapped collections (like-for-like).
        "scopedToMappedCollections": scoped,
        "currencyWarning": None if same_currency else (
            "Sites use different currencies (" + ", ".join(sorted(currencies)) +
            "). Absolute price comparisons are NOT meaningful; compare relative positioning (bands, on-sale rates, assortment) instead."
        ),
        "rows": rows,
    }


def _avail_in_stock(p: Dict[str, Any]):
    """Product availability as True / False / None (unknown). Handles both the
    dict shape ({"inStock": bool}) and the string shape ("in_stock"/"out_of_stock")."""
    a = p.get("availability")
    if isinstance(a, dict):
        return a.get("inStock")
    if isinstance(a, str):
        s = a.lower()
        if "out" in s or "unavailable" in s or "sold" in s or "false" in s:
            return False
        if "in" in s or "avail" in s or "true" in s:
            return True
    return None


def build_inventory_comparison(sites: List[Dict[str, Any]]) -> Dict[str, Any]:
    owner_urls, comp_urls = _mapped_collection_scope(sites)
    scoped = bool(owner_urls or comp_urls)
    rows = []
    for i, site in enumerate(sites):
        urls = owner_urls if i == 0 else comp_urls.get(site.get("domain"), set())
        cols = site["collections"]
        # Scope inventory totals/rate to the mapped collections (same categories both
        # sides) so the numbers are like-for-like, not owner-full vs competitor-subset.
        if scoped and urls:
            cols = [c for c in cols if _norm_col_url(c.get("url")) in urls]
        # UNIQUE products that live in these collections — a true subset of the
        # store's "products found", NOT the sum of per-collection counts (which
        # double-counts any product shelved in several collections and can wrongly
        # exceed the unique total). Availability is read once per unique product.
        col_urls = {_norm_col_url(c.get("url")) for c in cols if c.get("url")}
        in_col = [
            p for p in site.get("products", [])
            if col_urls and any(_norm_col_url(sp.get("url")) in col_urls for sp in (p.get("sourcePages") or []))
        ]
        total_products = len(in_col)
        total_in_stock = sum(1 for p in in_col if _avail_in_stock(p) is True)
        total_oos = sum(1 for p in in_col if _avail_in_stock(p) is False)
        # Rate over products whose availability is KNOWN (in-stock + out-of-stock), so
        # products with no availability data don't drag the rate toward 0%.
        known_base = total_in_stock + total_oos
        # Unique products found on OTHER pages (homepage-featured, standalone product
        # pages, or collections not analyzed) — the gap between "products found" and
        # the unique-in-collections subset. Surfaced so the two numbers reconcile.
        unique_total = (site.get("catalog") or {}).get("totalUniqueProducts") or 0
        not_in_collections = max(0, unique_total - total_products)
        # Unique products featured on the homepage (an OVERLAY — can overlap with the
        # in-collections set, so it does NOT partition the total).
        on_homepage = sum(
            1 for p in site.get("products", [])
            if any((sp.get("pageType") == "homepage") for sp in (p.get("sourcePages") or []))
        )
        rows.append({
            "domain": site["domain"],
            "collectionProductCount": total_products,
            "notInCollections": not_in_collections,
            "onHomepageCount": on_homepage,
            "inStockCount": total_in_stock,
            "outOfStockCount": total_oos,
            "inStockRate": pct(total_in_stock, known_base) if known_base > 0 else None,
            "collections": cols,
        })
    return {"displayType": "bar_chart", "scopedToMappedCollections": scoped, "rows": rows}


def build_homepage_comparison(sites: List[Dict[str, Any]]) -> Dict[str, Any]:
    rows = []
    for site in sites:
        h = site["homepage"]
        rows.append({
            "domain": site["domain"],
            "homepageDetected": h.get("detected"),
            "sectionCount": h.get("sectionCount"),
            "featuredProductCount": h.get("featuredProductCount"),
            "featuredCollectionCount": h.get("featuredCollectionCount"),
            "ctaCount": h.get("ctaCount"),
            "imageCount": h.get("imageCount"),
            "hasHero": bool(h.get("features", {}).get("hasHero")),
            "hasVideo": bool(h.get("features", {}).get("hasVideo")),
            "hasAnnouncementBar": bool(h.get("features", {}).get("hasAnnouncementBar")),
            "hasCollectionBanners": bool(h.get("features", {}).get("hasCollectionBanners")),
            "hasNewsletter": bool(h.get("features", {}).get("hasNewsletter")),
            "hasBlogPreview": bool(h.get("features", {}).get("hasBlogPreview")),
            "hasTestimonials": bool(h.get("features", {}).get("hasTestimonials")),
            "hasTrustSignals": bool(h.get("features", {}).get("hasTrustSignals")),
            "hasInstagramFeed": bool(h.get("features", {}).get("hasInstagramFeed")),
            "hasWhatsapp": bool(h.get("features", {}).get("hasWhatsapp")),
            "hasDiscountMessaging": bool(h.get("features", {}).get("hasDiscountMessaging")),
            # Promotional posture beyond product discounts: the announcement-bar
            # message and the classified offers (free shipping, COD, bank deposit…).
            "hasFreeShippingOffer": bool(h.get("features", {}).get("hasFreeShippingOffer")),
            "announcementText": h.get("announcementText"),
            "promotionalOffers": h.get("promotionalOffers") or [],
            "topSections": h.get("sections", [])[:12],
        })
    return {"displayType": "homepage_deep_table", "rows": rows}


def build_section_comparison(sites: List[Dict[str, Any]]) -> Dict[str, Any]:
    rows = []
    for site in sites:
        sections = site.get("sections") or []
        rows.append({
            "domain": site["domain"],
            "sectionCount": len(sections),
            "highImportanceSections": sum(1 for s in sections if s.get("importanceLevel") == "high"),
            "mediumImportanceSections": sum(1 for s in sections if s.get("importanceLevel") == "medium"),
            "sectionsByPosition": sections,
            "topImportantSections": sorted(sections, key=lambda s: s.get("importanceScore") or 0, reverse=True)[:15],
        })
    return {"displayType": "ranked_sections", "rows": rows}


def build_page_content_comparison(sites: List[Dict[str, Any]]) -> Dict[str, Any]:
    rows = []
    for site in sites:
        page_rows = []
        for page in site["pages"]:
            page_rows.append({
                "domain": site["domain"],
                "pageType": page.get("pageType"),
                "url": page.get("url"),
                "title": page.get("seo", {}).get("title"),
                "h1": page.get("seo", {}).get("h1"),
                "metaDescription": page.get("seo", {}).get("metaDescription"),
                "textEvidence": page.get("textEvidence"),
                "sectionCount": len(page.get("sections") or []),
                "productCountOnPage": page.get("productCountOnPage"),
                "extractionQuality": page.get("extractionQuality"),
                "fallbackContentAvailable": bool(page.get("fallbackContent")),
            })
        rows.append({"domain": site["domain"], "pages": page_rows})
    return {"displayType": "page_content_evidence", "rows": rows}


def build_seo_comparison(sites: List[Dict[str, Any]]) -> Dict[str, Any]:
    rows = []
    for site in sites:
        seo = site["seo"]
        srows = seo["rows"]
        n = len(srows) or 1
        title_lens = [r.get("titleLength") or 0 for r in srows if r.get("title")]
        meta_lens = [r.get("metaDescriptionLength") or 0 for r in srows if r.get("metaDescriptionPresent")]
        # Duplicate <title> tags across pages — a real SEO issue (cannibalization).
        tcount = {}
        for r in srows:
            t = (r.get("title") or "").strip().lower()
            if t:
                tcount[t] = tcount.get(t, 0) + 1
        duplicate_title_pages = sum(c for c in tcount.values() if c > 1)
        rows.append({
            "domain": site["domain"],
            "pagesAnalyzed": len(srows),
            "pagesWithMissingMetaDescription": seo["pagesWithMissingMetaDescription"],
            "pagesWithMissingH1": seo["pagesWithMissingH1"],
            # Title quality (search-snippet best practice is ~30–60 chars).
            "avgTitleLength": round(sum(title_lens) / len(title_lens)) if title_lens else 0,
            "titlesTooShort": sum(1 for l in title_lens if l and l < 30),
            "titlesTooLong": sum(1 for l in title_lens if l > 60),
            # Meta-description quality (best practice ~120–160 chars).
            "metaPresentRate": pct(sum(1 for r in srows if r.get("metaDescriptionPresent")), n),
            "avgMetaLength": round(sum(meta_lens) / len(meta_lens)) if meta_lens else 0,
            "metaOutOfRange": sum(1 for l in meta_lens if l < 120 or l > 160),
            "h1PresentRate": pct(sum(1 for r in srows if r.get("h1Present")), n),
            "canonicalPresentRate": pct(sum(1 for r in srows if r.get("canonicalPresent")), n),
            "duplicateTitlePages": duplicate_title_pages,
            "seoRows": srows,
        })
    return {"displayType": "table", "rows": rows}


def build_merchandising_comparison(sites: List[Dict[str, Any]]) -> Dict[str, Any]:
    rows = []
    for site in sites:
        rows.append({
            "domain": site["domain"],
            "collectionsWithFilters": sum(1 for c in site["collections"] if c.get("hasFilters")),
            "collectionsWithSort": sum(1 for c in site["collections"] if c.get("hasSort")),
            "collectionCount": len(site["collections"]),
            "homepageFeaturedProducts": site["homepage"].get("featuredProductCount"),
            "homepageFeaturedCollections": site["homepage"].get("featuredCollectionCount"),
            "promotionSections": [s for s in site.get("sections", []) if "promo" in clean_text(s.get("type")).lower() or any(x in clean_text(s.get("textPreview")).lower() for x in ["sale", "off", "discount"])][:15],
            "collectionSections": [s for s in site.get("sections", []) if "collection" in clean_text(s.get("type")).lower()][:15],
        })
    return {"displayType": "table", "rows": rows}


def build_trust_conversion_comparison(sites: List[Dict[str, Any]]) -> Dict[str, Any]:
    rows = []
    for site in sites:
        trust_sections = [s for s in site.get("sections", []) if any(x in f"{s.get('type')} {s.get('heading')} {s.get('textPreview')}".lower() for x in ["trust", "shipping", "returns", "secure", "support", "authentic", "cruelty", "vegan"])]
        rows.append({
            "domain": site["domain"],
            "hasHomepageTrustSignals": bool(site["homepage"].get("features", {}).get("hasTrustSignals")),
            "trustSectionCount": len(trust_sections),
            "trustSections": trust_sections[:15],
            "newsletterDetected": bool(site["homepage"].get("features", {}).get("hasNewsletter")),
            "discountMessagingDetected": bool(site["homepage"].get("features", {}).get("hasDiscountMessaging")),
        })
    return {"displayType": "trust_conversion", "rows": rows}


def build_data_quality(sites: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "displayType": "detailed",
        "rows": [
            {
                "domain": site["domain"],
                "averageExtractionScore": site["quality"].get("averageExtractionScore"),
                "failedPages": site["quality"].get("failedPages"),
                "warnings": site["quality"].get("warnings"),
                "pagesWithFallbackContent": [p.get("url") for p in site["pages"] if p.get("fallbackContent")],
            }
            for site in sites
        ]
    }


def availability_coverage(site: Dict[str, Any]) -> float:
    products = site.get("products", [])
    if not products:
        return 0.0
    return pct(sum(1 for p in products if p.get("availability")), len(products))


def build_ranked_insights(
    user: Dict[str, Any],
    competitors: List[Dict[str, Any]],
    one_to_one: Dict[str, Any] | None = None,
    category_coverage: Dict[str, Any] | None = None,
    sales_discounts: Dict[str, Any] | None = None,
    content_depth: Dict[str, Any] | None = None,
    pricing_pages: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    items = []
    if not competitors:
        items.append(make_insight("data", "medium", "Only one site provided", "A full competitor comparison needs at least one competitor snapshot.", 60, {"sitesCompared": 1}))
        return {"displayType": "ranked_insights", "items": rank_items(items)}

    same_currency = len({s["catalog"].get("currency") for s in [user] + competitors if s["catalog"].get("currency")}) <= 1

    # --- Price positioning from MATCHED products (like-for-like, not averages) ---
    if one_to_one and same_currency:
        for block in one_to_one.get("competitors", []):
            gap = (block.get("catalogWideProductMatching") or {}).get("medianPriceGapPercentVsUser")
            matched = (block.get("catalogWideProductMatching") or {}).get("matchedProductCount") or 0
            if gap is not None and matched >= 3:
                if gap >= 10:
                    items.append(make_insight(
                        "price_positioning", "high",
                        f"You are priced ~{abs(round(gap))}% BELOW {block.get('competitorDomain')} on comparable products",
                        f"Across {matched} like-for-like matched products, the competitor's median price is {round(gap)}% higher. This is either a value advantage to promote, or margin left on the table.",
                        85, {"competitor": block.get("competitorDomain"), "medianPriceGapPercentVsUser": gap, "matchedProducts": matched}))
                elif gap <= -10:
                    items.append(make_insight(
                        "price_positioning", "high",
                        f"You are priced ~{abs(round(gap))}% ABOVE {block.get('competitorDomain')} on comparable products",
                        f"Across {matched} like-for-like matched products, the competitor's median price is {abs(round(gap))}% lower. Check whether your product content and positioning justify the premium.",
                        85, {"competitor": block.get("competitorDomain"), "medianPriceGapPercentVsUser": gap, "matchedProducts": matched}))

            # Assortment gaps in matched collections.
            for matchup in block.get("collectionMatchups", []):
                a_gap = matchup.get("assortmentGap") or {}
                if a_gap.get("direction") == "competitor_broader" and (a_gap.get("difference") or 0) >= 3:
                    # Name the collection, never the raw inferred category (which
                    # is often "unknown" for user-mapped, differently-named pairs).
                    _cat = (matchup.get("category") or "").strip()
                    _col = ((matchup.get("competitorCollection") or {}).get("title")
                            or (matchup.get("userCollection") or {}).get("title"))
                    if _col:
                        _where = f"in {_col}"
                    elif _cat and _cat.lower() != "unknown":
                        _where = f"in their {_cat} range"
                    else:
                        _where = "in the matched collection"
                    items.append(make_insight(
                        "assortment", "medium",
                        f"{block.get('competitorDomain')} carries {a_gap['difference']} more products {_where}",
                        "In the matched collection, the competitor offers materially more products. Deeper ranges usually win category search traffic and choice-driven buyers.",
                        72, {"category": matchup.get("category"), "user": a_gap.get("userProductCount"), "competitor": a_gap.get("competitorProductCount")}))

    # --- Category coverage gaps (canonical, vertical-agnostic) ---
    # When the user has explicitly mapped collections, category INFERENCE can't
    # be trusted to claim "categories you don't cover": the user already told us
    # what maps to what, and one side's products are often left "unknown", which
    # produced nonsense like "competitor sells dresses you don't" between two
    # dresses stores. Suppress inference-based category gaps in that case.
    _user_mapped_present = False
    if one_to_one:
        for _blk in one_to_one.get("competitors", []):
            for _m in _blk.get("collectionMatchups", []):
                if "user_mapped" in (_m.get("matchReasons") or []):
                    _user_mapped_present = True
                    break
            if _user_mapped_present:
                break

    if category_coverage and not _user_mapped_present:
        # Never surface "unknown" as a category — it's an inference failure, not
        # a real gap the user can act on.
        _clean = lambda xs: [x for x in (xs or []) if x and str(x).strip().lower() != "unknown"]
        gaps = _clean(category_coverage.get("userGapCategories"))
        if gaps:
            items.append(make_insight(
                "category_gap", "high",
                "Competitors sell in categories you don't cover: " + ", ".join(gaps[:6]),
                "These canonical categories appear in competitor catalogs but not in yours (within the analyzed pages). Verify on the full store; if real, these are assortment expansion candidates.",
                80, {"missingCategories": gaps}))
        exclusive = _clean(category_coverage.get("userExclusiveCategories"))
        if exclusive:
            items.append(make_insight(
                "differentiation", "low",
                "You have exclusive categories competitors don't show: " + ", ".join(exclusive[:6]),
                "Categories only you cover are differentiation and messaging opportunities.",
                55, {"exclusiveCategories": exclusive}))

    # --- Promotional pressure ---
    if sales_discounts:
        rows = {r["domain"]: r for r in sales_discounts.get("rows", [])}
        u_row = rows.get(user["domain"], {})
        for comp in competitors:
            c_row = rows.get(comp["domain"], {})
            if (c_row.get("onSaleRate") or 0) >= (u_row.get("onSaleRate") or 0) + 0.2:
                items.append(make_insight(
                    "promo_pressure", "medium",
                    f"{comp['domain']} runs far more promotions ({round((c_row.get('onSaleRate') or 0)*100)}% of catalog on sale vs your {round((u_row.get('onSaleRate') or 0)*100)}%)",
                    "Heavy competitor discounting creates price pressure on shared categories. Average discount depth: " + str(c_row.get("averageDiscountPercent")) + "%.",
                    70, {"competitorOnSaleRate": c_row.get("onSaleRate"), "userOnSaleRate": u_row.get("onSaleRate"), "competitorAvgDiscount": c_row.get("averageDiscountPercent")}))

    # --- Content depth ---
    if content_depth:
        rows = {r["domain"]: r for r in content_depth.get("rows", [])}
        u_row = rows.get(user["domain"], {})
        for comp in competitors:
            c_row = rows.get(comp["domain"], {})
            if (c_row.get("descriptionCoverageRate") or 0) >= (u_row.get("descriptionCoverageRate") or 0) + 0.25:
                items.append(make_insight(
                    "content_depth", "medium",
                    f"{comp['domain']} has richer product content ({round((c_row.get('descriptionCoverageRate') or 0)*100)}% products with descriptions vs your {round((u_row.get('descriptionCoverageRate') or 0)*100)}%)",
                    "Richer product descriptions typically improve SEO ranking and conversion. Consider enriching product pages in shared categories first.",
                    68, {"competitorDescriptionCoverage": c_row.get("descriptionCoverageRate"), "userDescriptionCoverage": u_row.get("descriptionCoverageRate")}))

    # --- Variant depth (sizes / shades / options per product) ---
    if content_depth:
        rows = {r["domain"]: r for r in content_depth.get("rows", [])}
        u_row = rows.get(user["domain"], {})
        u_avg = u_row.get("averageVariants") or 0
        for comp in competitors:
            c_row = rows.get(comp["domain"], {})
            c_avg = c_row.get("averageVariants") or 0
            # Only when the competitor is meaningfully deeper AND has enough coverage
            # for the number to be reliable.
            if c_avg >= u_avg + 1 and (c_row.get("variantCoverageRate") or 0) >= 0.5:
                items.append(make_insight(
                    "variant_depth", "medium",
                    f"{comp['domain']} offers more variants per product ({c_avg} avg vs your {u_avg}) — {c_row.get('totalVariants') or 0} variants across analyzed products",
                    "More sizes/shades/options per product widens the range a shopper can buy without leaving, and signals deeper stock. Consider expanding variants in your shared categories.",
                    64, {"competitorAvgVariants": c_avg, "userAvgVariants": u_avg, "competitorTotalVariants": c_row.get("totalVariants"), "userTotalVariants": u_row.get("totalVariants")}))

    # --- Navigation / page-intent gaps ---
    nav = build_navigation_comparison(user, competitors)
    for block in nav.get("competitors", []):
        only_them = block.get("competitorOnlyConcepts") or []
        missing = [i for i in (block.get("missingUserPageIntents") or []) if i and i not in ("unknown", "other", "home", "homepage")]
        if len(only_them) >= 3:
            items.append(make_insight(
                "nav_gap", "medium",
                f"{block['competitorDomain']} promotes categories in its nav that you don't: " + ", ".join(x.replace("_", " ") for x in only_them[:6]),
                "Categories a competitor surfaces in navigation but you don't can be assortment or positioning gaps worth reviewing.",
                62, {"competitorOnlyConcepts": only_them[:20]}))
        if missing:
            items.append(make_insight(
                "page_gap", "low",
                f"{block['competitorDomain']} links page types you don't: " + ", ".join(x.replace("_", " ") for x in missing[:6]),
                "Pages like size guides, shipping/returns or a store locator build trust and SEO. Consider adding the ones relevant to you.",
                56, {"missingPageIntents": missing[:20]}))

    # --- Merchandising sophistication (filtering on collection pages) ---
    merch = build_merchandising_comparison([user] + competitors)
    mrows = {r["domain"]: r for r in merch.get("rows", [])}
    u_m = mrows.get(user["domain"], {})
    u_filt = (u_m.get("collectionsWithFilters") or 0) / (u_m.get("collectionCount") or 1)
    for comp in competitors:
        c_m = mrows.get(comp["domain"], {})
        c_filt = (c_m.get("collectionsWithFilters") or 0) / (c_m.get("collectionCount") or 1)
        if c_filt >= u_filt + 0.3 and (c_m.get("collectionCount") or 0) >= 3:
            items.append(make_insight(
                "merchandising", "medium",
                f"{comp['domain']} offers filtering on more of its collections ({round(c_filt * 100)}% vs your {round(u_filt * 100)}%)",
                "Filtering/sorting on collection pages helps shoppers narrow choices and usually lifts conversion. Consider adding facets to your key collections.",
                60, {"competitorFilterRate": round(c_filt, 2), "userFilterRate": round(u_filt, 2)}))

    # --- On-page SEO hygiene (your own quick wins) ---
    seo_cmp = build_seo_comparison([user] + competitors)
    srows = {r["domain"]: r for r in seo_cmp.get("rows", [])}
    u_seo = srows.get(user["domain"], {})
    if (u_seo.get("pagesAnalyzed") or 0) > 0:
        miss_meta = u_seo.get("pagesWithMissingMetaDescription") or 0
        miss_h1 = u_seo.get("pagesWithMissingH1") or 0
        dup = u_seo.get("duplicateTitlePages") or 0
        parts = []
        if miss_meta: parts.append(f"{miss_meta} missing meta description{'s' if miss_meta != 1 else ''}")
        if miss_h1: parts.append(f"{miss_h1} missing H1{'s' if miss_h1 != 1 else ''}")
        if dup: parts.append(f"{dup} duplicate title{'s' if dup != 1 else ''}")
        if parts:
            items.append(make_insight(
                "seo", "low",
                "On-page SEO gaps on your analyzed pages: " + ", ".join(parts),
                "Unique titles, present H1s and meta descriptions are quick on-page SEO wins that improve click-through and ranking. Fix these on your key pages first.",
                58, {"missingMeta": miss_meta, "missingH1": miss_h1, "duplicateTitles": dup}))

    # --- SaaS plan pricing (structured pricing pages) ---
    for block in (pricing_pages or {}).get("competitors", []):
        ppc = block.get("planPriceComparison")
        if not ppc or not ppc.get("sameCurrency"):
            continue
        comp_domain = block.get("competitorDomain")
        u_entry, c_entry = ppc.get("userEntryPrice"), ppc.get("competitorEntryPrice")
        if u_entry == 0 and (c_entry or 0) > 0:
            items.append(make_insight(
                "saas_pricing", "medium",
                f"You offer a free tier; {comp_domain} starts at {c_entry}",
                "A free entry point is a strong acquisition advantage - make it prominent in positioning and SEO.",
                75, {"userEntryPrice": u_entry, "competitorEntryPrice": c_entry}))
        elif u_entry is not None and c_entry is not None and c_entry > 0 and u_entry > 0:
            gap = round((c_entry - u_entry) / u_entry * 100)
            if abs(gap) >= 20:
                if gap >= 100:
                    title = f"{comp_domain}'s entry plan costs {round(c_entry / u_entry, 1)}x yours ({c_entry} vs {u_entry})"
                elif gap <= -50:
                    title = f"Your entry plan costs {round(u_entry / c_entry, 1)}x {comp_domain}'s ({u_entry} vs {c_entry})"
                else:
                    direction = "below" if gap > 0 else "above"
                    title = f"Your entry plan is priced ~{abs(gap)}% {direction} {comp_domain}"
                items.append(make_insight(
                    "saas_pricing", "high", title,
                    f"Entry price: you {u_entry} vs competitor {c_entry}. Entry pricing anchors plan perception and trial conversion.",
                    82, {"userEntryPrice": u_entry, "competitorEntryPrice": c_entry, "gapPercent": gap}))
        u_top, c_top = ppc.get("userTopPrice"), ppc.get("competitorTopPrice")
        if u_top is not None and c_top is not None and u_top > 0 and c_top > u_top * 1.5:
            items.append(make_insight(
                "saas_pricing", "low",
                f"{comp_domain} monetizes a much higher top tier ({c_top} vs your {u_top})",
                "A higher top tier can indicate an upmarket/enterprise motion you may be leaving unaddressed.",
                60, {"userTopPrice": u_top, "competitorTopPrice": c_top}))

    # --- Catalog breadth ---
    comp_best_product_count = max((c["catalog"]["totalUniqueProducts"] for c in competitors), default=0)
    if user["catalog"]["totalUniqueProducts"] < comp_best_product_count:
        items.append(make_insight("catalog_depth", "medium", "Competitor has broader detected catalog coverage", "A competitor has more unique products in the analyzed snapshot. Note this reflects analyzed pages, not necessarily the full store.", 65, {"userProducts": user["catalog"]["totalUniqueProducts"], "bestCompetitorProducts": comp_best_product_count}))

    # --- Trust signals ---
    comp_trust = any(c["homepage"].get("features", {}).get("hasTrustSignals") for c in competitors)
    if comp_trust and not user["homepage"].get("features", {}).get("hasTrustSignals"):
        items.append(make_insight("trust", "medium", "Competitor shows stronger homepage trust signals", "Trust signals influence conversion confidence and should be visible in high-priority homepage sections.", 78, {"userHasTrustSignals": False}))

    # --- SEO ---
    if user["seo"]["pagesWithMissingMetaDescription"] > 0:
        items.append(make_insight("seo", "medium", "Some analyzed user pages are missing meta descriptions", "Missing meta descriptions can reduce CTR control in search results.", 76, {"missingCount": user["seo"]["pagesWithMissingMetaDescription"]}))

    # --- Price data quality ---
    if user["catalog"]["totalUniqueProducts"] > 0 and user["catalog"]["priceCoverageRate"] < 1:
        items.append(make_insight("pricing", "high", "Some user products have missing prices", "Missing pricing weakens competitive price comparison and AI interpretation.", 86, {"priceCoverageRate": user["catalog"]["priceCoverageRate"]}))

    # --- Stock availability: only when BOTH sides have reliable availability data ---
    user_avail_cov = availability_coverage(user)
    if user_avail_cov >= 0.5:
        for comp in competitors:
            if availability_coverage(comp) < 0.5:
                continue
            user_in_stock = aggregate_in_stock_rate(user)
            comp_stock = aggregate_in_stock_rate(comp)
            if comp_stock > user_in_stock + 0.15:
                items.append(make_insight("inventory", "medium", f"{comp['domain']} has better stock availability in analyzed collections", "Stock availability can directly affect conversion and merchandising strength.", 73, {"userInStockRate": user_in_stock, "competitorInStockRate": comp_stock}))

    # --- Homepage structure ---
    user_high_sections = [s for s in user.get("sections", []) if s.get("importanceLevel") == "high"]
    if not user_high_sections:
        items.append(make_insight("homepage_structure", "medium", "No high-importance homepage sections detected", "The analyzed homepage may not have strong above-the-fold, trust, promo, or merchandising sections detected.", 67, {}))

    if not same_currency:
        items.append(make_insight("data", "low", "Sites use different currencies", "Cross-currency absolute price comparisons were suppressed. Use relative signals (bands, promo rates, assortment) instead.", 50, {}))

    return {"displayType": "ranked_insights", "items": rank_items(items)}


def make_insight(type_: str, severity: str, title: str, detail: str, importance: int, evidence: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "type": type_,
        "severity": severity,
        "title": title,
        "detail": detail,
        "importanceScore": importance,
        "recommendedDisplayRank": None,
        "workspacePriority": "P1" if importance >= 80 else "P2" if importance >= 65 else "P3",
        "evidence": evidence,
    }


def rank_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    severity_weight = {"high": 30, "medium": 18, "low": 8}
    ranked = sorted(items, key=lambda x: (x.get("importanceScore", 0) + severity_weight.get(x.get("severity"), 0)), reverse=True)
    for idx, item in enumerate(ranked, start=1):
        item["recommendedDisplayRank"] = idx
    return ranked


def build_recommendations(user: Dict[str, Any], competitors: List[Dict[str, Any]]) -> Dict[str, Any]:
    recs = []
    if user["seo"]["pagesWithMissingMetaDescription"]:
        recs.append({"area": "SEO", "priority": "P1", "importanceScore": 88, "recommendation": "Add unique meta descriptions to analyzed pages where missing.", "successMetric": "pagesWithMissingMetaDescription = 0"})
    if not user["homepage"].get("features", {}).get("hasTrustSignals"):
        recs.append({"area": "Trust/Conversion", "priority": "P2", "importanceScore": 78, "recommendation": "Add visible homepage trust signals such as shipping, returns, authenticity, payment security, reviews, or support badges.", "successMetric": "homepage.features.hasTrustSignals = true"})
    if user["catalog"]["priceCoverageRate"] < 1:
        recs.append({"area": "Pricing Data", "priority": "P1", "importanceScore": 86, "recommendation": "Improve product price extraction or product page coverage for products missing price data.", "successMetric": "priceCoverageRate = 1.0"})
    if aggregate_in_stock_rate(user) < 0.8:
        recs.append({"area": "Inventory", "priority": "P2", "importanceScore": 74, "recommendation": "Prioritize restocking or merchandising available products in analyzed collections.", "successMetric": "inStockRate >= 0.8"})
    recs = sorted(recs, key=lambda r: r.get("importanceScore", 0), reverse=True)
    for idx, rec in enumerate(recs, start=1):
        rec["recommendedDisplayRank"] = idx
    return {"displayType": "recommendations", "items": recs}


def build_workspace_layout_hints(user: Dict[str, Any], competitors: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "displayType": "workspace_layout_hints",
        "recommendedDefaultOrder": [
            {"rank": 1, "sectionKey": "rankedInsights", "reason": "Highest action value for users"},
            {"rank": 2, "sectionKey": "homepageComparison", "reason": "Homepage is the front face and should always be reviewed"},
            {"rank": 3, "sectionKey": "navigationComparison", "reason": "Navigation reveals priority categories, services, and SaaS pages"},
            {"rank": 4, "sectionKey": "pageMatchComparison", "reason": "Like-for-like homepage, pricing, service, product, collection, and content page matching"},
            {"rank": 5, "sectionKey": "collectionGapAnalysis", "reason": "Shows missing collections, services, SaaS concepts, and market coverage gaps"},
            {"rank": 6, "sectionKey": "oneToOneComparison", "reason": "Like-for-like collection and product matching"},
            {"rank": 7, "sectionKey": "pricingPageComparison", "reason": "Core SaaS packaging and pricing intelligence"},
            {"rank": 8, "sectionKey": "servicesComparison", "reason": "Core service business coverage and CTA intelligence"},
            {"rank": 9, "sectionKey": "priceComparison", "reason": "Core ecommerce intelligence"},
            {"rank": 10, "sectionKey": "inventoryComparison", "reason": "Availability and merchandising opportunity"},
            {"rank": 11, "sectionKey": "sectionComparison", "reason": "Homepage/page structure and content positioning"},
            {"rank": 12, "sectionKey": "productDetailComparison", "reason": "Detailed evidence layer, expandable in UI"},
            {"rank": 13, "sectionKey": "pageContentComparison", "reason": "AI evidence and copy/SEO context"},
            {"rank": 14, "sectionKey": "dataQuality", "reason": "Transparency and debugging"},
        ]
    }


# Token budget for the raw-text recovery net fed to the AI. The homepage carries
# the most qualitative signal (promos, positioning, trust), so it gets the largest
# slice; other pages contribute just their top zone (announcements/promos) plus a
# short excerpt. Kept small on purpose — this is a safety net, not the main input.
_RAW_EVIDENCE_HOMEPAGE_FULLTEXT = 3500
_RAW_EVIDENCE_OTHER_EXCERPT = 800


def _budget_raw_evidence(page: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    rte = page.get("rawTextEvidence") or {}
    if not isinstance(rte, dict) or not rte:
        return None
    is_home = page.get("pageType") == "homepage"
    out: Dict[str, Any] = {}
    if rte.get("top"):
        out["top"] = rte["top"]
    if rte.get("headings"):
        out["headings"] = rte["headings"][:20]
    if is_home:
        if rte.get("hero"):
            out["hero"] = rte["hero"]
        if rte.get("footer"):
            out["footer"] = rte["footer"]
        ft = (rte.get("fullText") or "")[:_RAW_EVIDENCE_HOMEPAGE_FULLTEXT]
        if ft:
            out["fullText"] = ft
    else:
        ex = (rte.get("fullText") or "")[:_RAW_EVIDENCE_OTHER_EXCERPT]
        if ex:
            out["excerpt"] = ex
    return out or None


def build_openai_evidence_pack(user: Dict[str, Any], competitors: List[Dict[str, Any]], shared_modules: Dict[str, Any] | None = None) -> Dict[str, Any]:
    all_sites = [user] + competitors
    modules = shared_modules or {}
    return {
        "purpose": "Use this detailed evidence pack for narrative explanation, alerts, strategic analysis, and insight generation. Numeric facts are computed deterministically by the comparison engine.",
        "instructionHint": "Do not invent products, prices, plans, services, or page facts. Use homepage, navigation, page matches, pricing pages, service pages, products, sections, importance ranks, and oneToOneComparison matchups as evidence.",
        "pageMatchComparison": modules.get("pageMatchComparison") or build_page_match_comparison(user, competitors),
        "navigationComparison": modules.get("navigationComparison") or build_navigation_comparison(user, competitors),
        "collectionGapAnalysis": modules.get("collectionGapAnalysis") or build_collection_gap_analysis(user, competitors),
        "pricingPageComparison": modules.get("pricingPageComparison") or build_pricing_page_comparison(user, competitors),
        "servicesComparison": modules.get("servicesComparison") or build_services_comparison(user, competitors),
        "oneToOneComparison": modules.get("oneToOneComparison") or build_one_to_one_comparison(user, competitors),
        "categoryCoverageComparison": modules.get("categoryCoverageComparison"),
        "saleAndDiscountComparison": modules.get("saleAndDiscountComparison"),
        "shippingPaymentComparison": _safe_shipping_payment(all_sites),
        "sites": [
            {
                "key": site["key"],
                "domain": site["domain"],
                "platform": site.get("displayPlatform") or site.get("platform"),
                "summary": site_overview(site),
                "catalog": site["catalog"],
                "topProductsForAI": sorted(site["products"], key=lambda p: score_product_ai_usefulness(p)["score"], reverse=True)[:40],
                "allProductCount": len(site["products"]),
                "pages": [
                    {
                        "url": p.get("url"),
                        "pageType": p.get("pageType"),
                        "title": p.get("seo", {}).get("title"),
                        "h1": p.get("seo", {}).get("h1"),
                        "metaDescription": p.get("seo", {}).get("metaDescription"),
                        "textEvidence": p.get("textEvidence"),
                        # Raw visible-text recovery net (budgeted): catches promos,
                        # announcements and messaging structured extraction dropped.
                        "rawEvidence": _budget_raw_evidence(p),
                        "sections": p.get("sections", [])[:20],
                    }
                    for p in site["pages"]
                ],
                "topSectionsByImportance": sorted(site.get("sections", []), key=lambda s: s.get("importanceScore") or 0, reverse=True)[:30],
                "seo": site["seo"],
                "collections": site["collections"],
                "quality": site["quality"],
            }
            for site in all_sites
        ]
    }


def aggregate_in_stock_rate(site: Dict[str, Any]) -> float:
    # In-stock rate over UNIQUE products that live in collections, using each
    # product's own availability — same basis as the "Catalog & stock" table, so
    # insights and the table agree (not the old per-collection double-counted sum).
    col_urls = {_norm_col_url(c.get("url")) for c in site.get("collections", []) if c.get("url")}
    in_col = [
        p for p in site.get("products", [])
        if col_urls and any(_norm_col_url(sp.get("url")) in col_urls for sp in (p.get("sourcePages") or []))
    ]
    known = [p for p in in_col if _avail_in_stock(p) is not None]
    in_stock = sum(1 for p in known if _avail_in_stock(p) is True)
    return pct(in_stock, len(known))
