from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


def arr(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def obj(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def short_text(value: Any, limit: int = 300) -> Optional[str]:
    if value is None or value == "":
        return None
    text = str(value).replace("\n", " ").replace("\r", " ").strip()
    text = " ".join(text.split())
    if not text:
        return None
    return text[:limit] + "..." if len(text) > limit else text


def clean_obj(value: Any) -> Any:
    """Remove None, empty lists and empty dicts recursively, but keep false/0 values."""
    if isinstance(value, dict):
        cleaned = {k: clean_obj(v) for k, v in value.items()}
        return {k: v for k, v in cleaned.items() if v is not None and v != [] and v != {}}
    if isinstance(value, list):
        cleaned = [clean_obj(v) for v in value]
        return [v for v in cleaned if v is not None and v != [] and v != {}]
    return value


def safe_len(value: Any) -> int:
    return len(value) if isinstance(value, list) else 0


def first_non_empty(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, (list, dict)) and len(value) == 0:
            continue
        if value == "":
            continue
        return value
    return None


def domain_role(sites: List[Dict[str, Any]], role: str) -> Optional[str]:
    for site in sites:
        if site.get("key") == role or site.get("role") == role:
            return site.get("domain")
    if role == "user" and sites:
        return sites[0].get("domain")
    if role != "user" and len(sites) > 1:
        return sites[1].get("domain")
    return None


def product_summary(product: Optional[Dict[str, Any]], desc_limit: int = 220) -> Optional[Dict[str, Any]]:
    if not product:
        return None
    return clean_obj({
        "name": product.get("name"),
        "url": product.get("productUrl") or product.get("url"),
        "category": product.get("category"),
        "vendor": product.get("vendor"),
        "price": product.get("priceValue") if product.get("priceValue") is not None else product.get("price"),
        "currency": product.get("currency"),
        "availability": product.get("availability"),
        "variantCount": product.get("variantCount"),
        "variantOptions": (product.get("variantOptions") or [])[:12],
        "swatches": (product.get("swatches") or [])[:16],
        "imageCount": product.get("imageCount"),
        "productType": product.get("productType") or product.get("inferredType"),
        "priceBand": product.get("priceBand"),
        "isOnSale": product.get("isOnSale") or None,
        "discountPercent": product.get("discountPercent"),
        "compareAtPrice": product.get("priceCompareAt"),
        "descriptionPreview": short_text(product.get("shortDescription") or product.get("descriptionText"), desc_limit),
    })


def collection_summary(collection: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not collection:
        return None
    return clean_obj({
        "url": collection.get("url"),
        "title": collection.get("title"),
        "productCount": collection.get("productCount"),
        "currency": collection.get("currency"),
        "priceMin": collection.get("priceMin"),
        "priceMax": collection.get("priceMax"),
        "averagePrice": collection.get("averagePrice"),
        "inStockCount": collection.get("inStockCount"),
        "outOfStockCount": collection.get("outOfStockCount"),
        "inStockRate": collection.get("inStockRate"),
        "hasFilters": collection.get("hasFilters"),
        "hasSort": collection.get("hasSort"),
    })


def section_summary(section: Optional[Dict[str, Any]], text_limit: int = 220) -> Optional[Dict[str, Any]]:
    if not section:
        return None
    return clean_obj({
        "rank": section.get("rank"),
        "type": section.get("type"),
        "heading": section.get("heading"),
        "textPreview": short_text(section.get("textPreview") or section.get("text"), text_limit),
        "importanceScore": section.get("importanceScore"),
        "importanceLevel": section.get("importanceLevel"),
        "recommendedWorkspacePriority": section.get("recommendedWorkspacePriority"),
    })


def summarize_nav_link(link: Dict[str, Any]) -> Dict[str, Any]:
    return clean_obj({
        "text": short_text(link.get("text"), 90),
        "url": link.get("url"),
        "inferredIntent": link.get("inferredIntent"),
        "detectedConcepts": link.get("detectedConcepts"),
    })


def summarize_navigation(nav: Dict[str, Any], max_links: int) -> Dict[str, Any]:
    competitors = []
    for comp in arr(nav.get("competitors")):
        user_links = arr(comp.get("userNavigationLinks"))
        competitor_links = arr(comp.get("competitorNavigationLinks"))
        competitors.append(clean_obj({
            "competitorDomain": comp.get("competitorDomain"),
            "userNavLinkCount": comp.get("userNavLinkCount"),
            "competitorNavLinkCount": comp.get("competitorNavLinkCount"),
            "sharedConcepts": comp.get("sharedConcepts"),
            "userOnlyConcepts": comp.get("userOnlyConcepts"),
            "competitorOnlyConcepts": comp.get("competitorOnlyConcepts"),
            "sharedPageIntents": comp.get("sharedPageIntents"),
            "missingUserPageIntents": comp.get("missingUserPageIntents"),
            "sampleUserNavigationLinks": [summarize_nav_link(x) for x in user_links[:max_links]],
            "sampleCompetitorNavigationLinks": [summarize_nav_link(x) for x in competitor_links[:max_links]],
            "note": comp.get("aiPromptHint"),
        }))
    return clean_obj({
        "displayType": nav.get("displayType"),
        "userDomain": nav.get("userDomain"),
        "competitors": competitors,
    })


def summarize_market_coverage(block: Dict[str, Any]) -> Dict[str, Any]:
    return clean_obj({
        "displayType": block.get("displayType"),
        "rows": arr(block.get("rows")),
    })


def summarize_table_block(block: Dict[str, Any], max_rows: int = 20) -> Dict[str, Any]:
    if not block:
        return {}
    rows = arr(block.get("rows"))
    return clean_obj({
        "displayType": block.get("displayType"),
        "rows": rows[:max_rows],
        "rowCount": len(rows),
        "trimmed": len(rows) > max_rows,
    })


def summarize_collection_gaps(block: Dict[str, Any]) -> Dict[str, Any]:
    competitors = []
    for comp in arr(block.get("competitors")):
        competitors.append(clean_obj({
            "competitorDomain": comp.get("competitorDomain"),
            "sharedConcepts": comp.get("sharedConcepts"),
            "competitorOnlyConcepts": comp.get("competitorOnlyConcepts"),
            "userOnlyConcepts": comp.get("userOnlyConcepts"),
            "potentialUserGaps": comp.get("potentialUserGaps"),
            "note": comp.get("aiPromptHint"),
        }))
    return clean_obj({"displayType": block.get("displayType"), "competitors": competitors})


def summarize_pricing_services(block: Dict[str, Any]) -> Dict[str, Any]:
    competitors = []
    for comp in arr(block.get("competitors")):
        competitors.append(clean_obj({
            "competitorDomain": comp.get("competitorDomain"),
            **{k: v for k, v in comp.items() if k not in {"aiPromptHint"}},
            "note": comp.get("aiPromptHint"),
        }))
    return clean_obj({"displayType": block.get("displayType"), "competitors": competitors})


def summarize_price_block(block: Dict[str, Any], max_rows: int = 20) -> Dict[str, Any]:
    """Price comparison summary that PRESERVES the currency guard."""
    if not block:
        return {}
    rows = arr(block.get("rows"))
    return clean_obj({
        "displayType": block.get("displayType"),
        "sameCurrency": block.get("sameCurrency"),
        "currencyWarning": block.get("currencyWarning"),
        "rows": rows[:max_rows],
    })


def summarize_category_coverage(block: Dict[str, Any], max_examples: int = 2) -> Dict[str, Any]:
    if not block:
        return {}
    rows = []
    for row in arr(block.get("rows")):
        sites = {}
        for domain, cell in obj(row.get("sites")).items():
            sites[domain] = clean_obj({
                "productCount": cell.get("productCount"),
                "priceStats": cell.get("priceStats"),
                "onSaleCount": cell.get("onSaleCount"),
                "exampleProducts": arr(cell.get("exampleProducts"))[:max_examples],
            })
        rows.append(clean_obj({
            "category": row.get("category"),
            "coverageStatus": row.get("coverageStatus"),
            "userProductCount": row.get("userProductCount"),
            "bestCompetitorProductCount": row.get("bestCompetitorProductCount"),
            "sites": sites,
        }))
    return clean_obj({
        "displayType": block.get("displayType"),
        "userGapCategories": block.get("userGapCategories"),
        "userExclusiveCategories": block.get("userExclusiveCategories"),
        "rows": rows,
    })


def summarize_sale_discount(block: Dict[str, Any], max_discounts: int = 5) -> Dict[str, Any]:
    if not block:
        return {}
    rows = []
    for row in arr(block.get("rows")):
        rows.append(clean_obj({
            "domain": row.get("domain"),
            "productsAnalyzed": row.get("productsAnalyzed"),
            "onSaleCount": row.get("onSaleCount"),
            "onSaleRate": row.get("onSaleRate"),
            "averageDiscountPercent": row.get("averageDiscountPercent"),
            "maxDiscountPercent": row.get("maxDiscountPercent"),
            "deepestDiscounts": arr(row.get("deepestDiscounts"))[:max_discounts],
            "discountMessagingOnHomepage": row.get("discountMessagingOnHomepage"),
        }))
    return clean_obj({"displayType": block.get("displayType"), "rows": rows})


def summarize_catalog_wide_matching(competitor: Dict[str, Any], max_matches: int) -> Dict[str, Any]:
    cw = obj(competitor.get("catalogWideProductMatching"))
    if not cw:
        return {}
    return clean_obj({
        "matchedProductCount": cw.get("matchedProductCount"),
        "medianPriceGapPercentVsUser": cw.get("medianPriceGapPercentVsUser"),
        "userUnmatchedCount": cw.get("userUnmatchedCount"),
        "competitorUnmatchedCount": cw.get("competitorUnmatchedCount"),
        "topMatches": [clean_obj({
            "confidence": m.get("confidence"),
            "matchTier": m.get("matchTier"),
            "userProduct": product_summary(m.get("userProduct"), 120),
            "competitorProduct": product_summary(m.get("competitorProduct"), 120),
            "priceGap": m.get("priceGap"),
        }) for m in arr(cw.get("topMatches"))[:max_matches]],
    })


def build_one_to_one_summary(comparison: Dict[str, Any], max_matchups: int, max_product_matches: int, max_unmatched: int) -> List[Dict[str, Any]]:
    output: List[Dict[str, Any]] = []
    for competitor in arr(obj(comparison.get("oneToOneComparison")).get("competitors")):
        comp_block = {
            "competitorDomain": competitor.get("competitorDomain"),
            "matchedCollectionCount": competitor.get("matchedCollectionCount"),
            "collectionMatchups": [],
        }
        for matchup in arr(competitor.get("collectionMatchups"))[:max_matchups]:
            product_matching = obj(matchup.get("productMatching"))
            matches = arr(product_matching.get("matches"))
            competitor_unmatched = arr(product_matching.get("competitorUnmatchedProducts"))
            user_unmatched = arr(product_matching.get("userUnmatchedProducts"))
            match_block = {
                "category": matchup.get("category"),
                "confidence": matchup.get("confidence"),
                "matchReasons": matchup.get("matchReasons"),
                "userCollection": collection_summary(matchup.get("userCollection")),
                "competitorCollection": collection_summary(matchup.get("competitorCollection")),
                "userCollectionProductCount": matchup.get("userCollectionProductCount"),
                "competitorCollectionProductCount": matchup.get("competitorCollectionProductCount"),
                "priceStats": matchup.get("priceStats"),
                "assortmentGap": matchup.get("assortmentGap"),
                "matchedProductCount": product_matching.get("matchedProductCount"),
                "userUnmatchedCount": product_matching.get("userUnmatchedCount"),
                "competitorUnmatchedCount": product_matching.get("competitorUnmatchedCount"),
                "topProductMatches": [],
                "competitorUnmatchedProducts": [],
                "userUnmatchedProducts": [],
            }
            # Sort examples by confidence and material price gap where present.
            sorted_matches = sorted(
                matches,
                key=lambda m: (
                    abs(obj(m.get("priceGap")).get("percentVsUser") or 0),
                    m.get("confidence") or 0,
                ),
                reverse=True,
            )
            for match in sorted_matches[:max_product_matches]:
                match_block["topProductMatches"].append(clean_obj({
                    "confidence": match.get("confidence"),
                    "matchReasons": match.get("matchReasons"),
                    "userProduct": product_summary(match.get("userProduct")),
                    "competitorProduct": product_summary(match.get("competitorProduct")),
                    "priceGap": match.get("priceGap"),
                    "positioningComparisonSignals": match.get("positioningComparisonSignals"),
                }))
            for product in competitor_unmatched[:max_unmatched]:
                match_block["competitorUnmatchedProducts"].append(product_summary(product, 120))
            for product in user_unmatched[:max_unmatched]:
                match_block["userUnmatchedProducts"].append(product_summary(product, 120))
            comp_block["collectionMatchups"].append(clean_obj(match_block))
        comp_block["catalogWideProductMatching"] = summarize_catalog_wide_matching(competitor, max_product_matches)
        output.append(clean_obj(comp_block))
    return output


def build_page_match_summary(comparison: Dict[str, Any], max_matches: int, max_sections: int) -> List[Dict[str, Any]]:
    output: List[Dict[str, Any]] = []
    for competitor in arr(obj(comparison.get("pageMatchComparison")).get("competitors")):
        comp_block = {
            "competitorDomain": competitor.get("competitorDomain"),
            "matchedPageCount": competitor.get("matchedPageCount"),
            "matches": [],
        }
        for match in arr(competitor.get("matches"))[:max_matches]:
            user_page = obj(match.get("userPage"))
            competitor_page = obj(match.get("competitorPage"))
            comp_block["matches"].append(clean_obj({
                "pageIntent": match.get("pageIntent"),
                "confidence": match.get("confidence"),
                "matchReasons": match.get("matchReasons"),
                "userPage": {
                    "url": user_page.get("url"),
                    "title": user_page.get("title"),
                    "summary": short_text(user_page.get("summary"), 250),
                    "sectionCount": user_page.get("sectionCount"),
                    "topSections": [section_summary(s) for s in arr(user_page.get("topSections"))[:max_sections]],
                },
                "competitorPage": {
                    "url": competitor_page.get("url"),
                    "title": competitor_page.get("title"),
                    "summary": short_text(competitor_page.get("summary"), 250),
                    "sectionCount": competitor_page.get("sectionCount"),
                    "topSections": [section_summary(s) for s in arr(competitor_page.get("topSections"))[:max_sections]],
                },
            }))
        output.append(clean_obj(comp_block))
    return output


def build_top_products(comparison: Dict[str, Any], max_products_per_site: int) -> List[Dict[str, Any]]:
    blocks = []
    for site in arr(obj(comparison.get("productDetailComparison")).get("sites")):
        products = arr(site.get("products"))
        high_quality = sorted(
            products,
            key=lambda p: (
                obj(p.get("aiUsefulness")).get("score") or 0,
                p.get("rank") or 9999,
            ),
            reverse=True,
        )[:max_products_per_site]
        blocks.append(clean_obj({
            "domain": site.get("domain"),
            "productCount": site.get("productCount") or len(products),
            "representativeProducts": [product_summary(p, 120) for p in high_quality],
        }))
    return blocks


def build_ai_payload(comparison: Dict[str, Any], options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Build a compact, AI-ready, dashboard-aware payload from comparison_engine_v5 (also accepts v4).

    The goal is not to preserve every raw field. The goal is to pass enough structured
    evidence for OpenAI to produce useful analysis without context overflow.
    """
    options = options or {}
    max_nav_links = int(options.get("maxNavigationLinks", 12))
    max_matchups = int(options.get("maxCollectionMatchups", 8))
    max_product_matches = int(options.get("maxProductMatches", 8))
    max_unmatched = int(options.get("maxUnmatchedProducts", 12))
    max_page_matches = int(options.get("maxPageMatches", 12))
    max_sections = int(options.get("maxSections", 5))
    max_products_per_site = int(options.get("maxProductsPerSite", 8))
    include_empty_modules = bool(options.get("includeEmptyModules", False))

    sites = arr(comparison.get("sites"))
    summary = obj(comparison.get("summary"))
    user_domain = summary.get("userDomain") or domain_role(sites, "user")
    competitor_domains = summary.get("competitorDomains") or [s.get("domain") for s in sites if s.get("key") != "user"]

    payload = {
        "schemaVersion": "ai_payload_v4",
        "sourceSchemaVersion": comparison.get("schemaVersion"),
        "mode": summary.get("mode") or "competitive_comparison",
        "siteContext": clean_obj({
            "userSiteName": summary.get("userSiteName"),
            "userSiteType": summary.get("userSiteType"),
            "userBusinessCategory": summary.get("userBusinessCategory"),
            "recommendedFocusModules": summary.get("recommendedFocusModules"),
        }),
        "domains": {
            "user": user_domain,
            "competitors": competitor_domains,
        },
        "snapshotScope": {
            "sitesCompared": summary.get("sitesCompared") or len(sites),
            "sites": sites,
            "dataQuality": comparison.get("dataQuality"),
        },
        "analysisInstructions": {
            "useOnlyEvidence": True,
            "doNotInventMissingData": True,
            "emptyModuleRule": "Do not create dashboard cards, recommendations, risks or sections for modules that are empty, unavailable, not detected, or not included in this payload.",
            "dashboardGoal": "Return concise evidence-backed JSON suitable for visual cards, charts, comparison tables, recommendations, and drill-down views.",
            "uiRule": "Do not mention schema names. Do not output empty sections. For ecommerce, prefer collections/products terminology over generic pages.",
            "verifyFirst": "Sanity-check numbers for contradictions or bad-fetch artifacts (identical prices across a whole collection, ~100% out of stock, counts that don't reconcile, 0/placeholder prices). Flag these as data_quality insights and lower the impactScore of anything that depends on them instead of asserting them confidently.",
            "compareTerminology": "Compare navigation labels and collection/category names on each side (see modules.navigation sampleUserNavigationLinks vs sampleCompetitorNavigationLinks, and the collection titles in matchEvidence). When the two sites use different words for the same thing, surface it as a navigation/positioning/seo insight with an action.",
        },
        "deterministicSignals": {
            "catalogComparison": summarize_table_block(obj(comparison.get("catalogComparison")), 20),
            "rankedInsights": comparison.get("rankedInsights"),
            "recommendations": comparison.get("recommendations"),
            "workspaceLayoutHints": comparison.get("workspaceLayoutHints"),
            "appIntegrationContract": comparison.get("appIntegrationContract"),
        },
        "modules": {
            "navigation": summarize_navigation(obj(comparison.get("navigationComparison")), max_nav_links),
            "collectionGapAnalysis": summarize_collection_gaps(obj(comparison.get("collectionGapAnalysis"))),
            "marketCoverage": summarize_market_coverage(obj(comparison.get("marketCoverageComparison"))),
            "categoryCoverage": summarize_category_coverage(obj(comparison.get("categoryCoverageComparison"))),
            "saleAndDiscount": summarize_sale_discount(obj(comparison.get("saleAndDiscountComparison"))),
            "contentDepth": summarize_table_block(obj(comparison.get("contentDepthComparison")), 20),
            "price": summarize_price_block(obj(comparison.get("priceComparison")), 20),
            "inventory": summarize_table_block(obj(comparison.get("inventoryComparison")), 20),
            "homepage": summarize_table_block(obj(comparison.get("homepageComparison")), 20),
            "seo": summarize_table_block(obj(comparison.get("seoComparison")), 20),
            "merchandising": summarize_table_block(obj(comparison.get("merchandisingComparison")), 20),
            "trustAndConversion": summarize_table_block(obj(comparison.get("trustAndConversionComparison")), 20),
        },
        "matchEvidence": {
            "oneToOneSummary": build_one_to_one_summary(comparison, max_matchups, max_product_matches, max_unmatched),
            "pageMatchSummary": build_page_match_summary(comparison, max_page_matches, max_sections),
        },
        "representativeProducts": build_top_products(comparison, max_products_per_site),
        "uiRenderingRules": {
            "hideEmptySections": True,
            "doNotMentionSchema": True,
            "preferVisualSections": ["summary_cards", "comparison_tables", "price_charts", "inventory_charts", "matched_products", "recommendations"],
            "showPricingPagesOnlyWhenDetected": True,
            "showServicePagesOnlyWhenDetected": True,
            "showHomepageOnlyWhenCaptured": True,
        },
        "requiredAiOutputShape": {
            "schemaVersion": "ci_analysis_v3",
            "executiveSummary": {
                "overallFinding": "string",
                "whoWinsWhere": "object",
                "topRisksForUser": "array",
                "topOpportunitiesForUser": "array",
            },
            "dashboardCards": "array of cards with title,type,severity,shortText,evidencePath,recommendedAction",
            "comparisonTables": "array of app-friendly tables",
            "evidenceBackedFindings": "object grouped by homepage,navigation,pricing,services,collections,products,seo,trust,conversion",
            "recommendedActions": "array with priority,impact,evidencePath,successMetric",
            "dataQualityAndScopeNotes": "object",
        },
    }

    # Remove modules that would create empty dashboard sections.
    if not include_empty_modules:
        modules = payload.get("modules", {})
        filtered_modules = {}
        for key, value in modules.items():
            rows = arr(obj(value).get("rows"))
            competitors = arr(obj(value).get("competitors"))
            if key == "homepage":
                if any(r.get("homepageDetected") or r.get("sectionCount") or arr(r.get("topSections")) for r in rows):
                    filtered_modules[key] = value
            elif key == "trustAndConversion":
                if any(r.get("hasHomepageTrustSignals") or r.get("trustSectionCount") or r.get("newsletterDetected") or r.get("discountMessagingDetected") or arr(r.get("trustSections")) for r in rows):
                    filtered_modules[key] = value
            elif key == "pricingPages":
                if any(c.get("userPricingPageDetected") or c.get("competitorPricingPageDetected") or arr(c.get("userPricingSignals")) or arr(c.get("competitorPricingSignals")) for c in competitors):
                    filtered_modules[key] = value
            elif key == "services":
                if any((c.get("userServicePageCount") or 0) > 0 or (c.get("competitorServicePageCount") or 0) > 0 or arr(c.get("userServiceSignals")) or arr(c.get("competitorServiceSignals")) for c in competitors):
                    filtered_modules[key] = value
            elif rows or competitors or obj(value):
                filtered_modules[key] = value
        payload["modules"] = filtered_modules
        payload = clean_obj(payload)

    return payload


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python build_ai_payload.py comparison_output.json")
        return

    input_path = Path(sys.argv[1])
    output_path = input_path.with_name(input_path.stem + "_ai_payload.json")

    with open(input_path, "r", encoding="utf-8") as f:
        comparison = json.load(f)

    ai_payload = build_ai_payload(comparison)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(ai_payload, f, indent=2, ensure_ascii=False)

    full_size = len(json.dumps(comparison, ensure_ascii=False))
    compact_size = len(json.dumps(ai_payload, ensure_ascii=False))

    print("AI payload created successfully")
    print(f"Output file: {output_path}")
    print(f"Original size: {full_size:,} characters")
    print(f"AI payload size: {compact_size:,} characters")
    print(f"Reduced by: {round((1 - compact_size / full_size) * 100, 2)}%" if full_size else "Reduced by: 0%")


if __name__ == "__main__":
    main()
