from __future__ import annotations

"""
Unified CompIntel API Gateway

Purpose:
- Keep your existing tools working exactly the same for CMD/local JSON-file usage.
- Add one JSON-in / JSON-out FastAPI layer for React.

Run from inside the CompIntel folder:
    uvicorn compintel_api:app --reload --port 8000

Main endpoints:
    GET  /health
    POST /api/v1/analyze-page
    POST /api/v1/analyze-pages
    POST /api/v1/merge-site
    POST /api/v1/compare-sites
    POST /api/v1/compare-one
    POST /api/v1/build-ai-payload
    POST /api/v1/openai-insights-request
    POST /api/v1/generate-insights
    POST /api/v1/compare-sites-ai-payload
    POST /api/v1/compare-one-ai-payload
    POST /api/v1/diff-snapshots
    POST /api/v1/diff-comparisons
    POST /api/v1/full-run
"""

import importlib.util
import sys
import traceback
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field, model_validator

BASE_DIR = Path(__file__).resolve().parent
WEBSITE_ANALYZER_DIR = BASE_DIR / "website_analyzer_app"
MERGER_DIR = BASE_DIR / "competitor_merger_app"
COMPARISON_DIR = BASE_DIR / "comparison_app"
CHANGE_DETECTION_DIR = BASE_DIR / "change_detection_app"

# Make existing absolute imports work without changing your old files.
for path in [str(WEBSITE_ANALYZER_DIR), str(MERGER_DIR), str(COMPARISON_DIR)]:
    if path not in sys.path:
        sys.path.insert(0, path)


def load_module(module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module: {file_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


# Existing tool imports
website_main = load_module("compintel_website_main", WEBSITE_ANALYZER_DIR / "main.py")
ai_payload_module = load_module("compintel_build_ai_payload", COMPARISON_DIR / "build_ai_payload.py")
openai_insights_module = load_module("compintel_openai_insights", COMPARISON_DIR / "openai_insights.py")
claude_insights_module = load_module("compintel_claude_insights", COMPARISON_DIR / "claude_insights.py")
change_detector_module = load_module("compintel_change_detector", CHANGE_DETECTION_DIR / "app" / "detector.py")

from app.merger import merge_page_jsons  # type: ignore  # competitor_merger_app/app/merger.py
from comparison_engine.comparator import compare_sites  # type: ignore
from level1_detector.store_locale import detect_stores, has_currency_switcher_markup, COUNTRY_CURRENCY  # type: ignore  # regional store / currency detection
from level1_detector.fetcher import fetch_with_requests, fetch_with_cloudscraper  # type: ignore  # fast, no-Playwright fetches for the store probe
from level1_detector.site_validator import validate_site, quick_catalog  # type: ignore  # onboarding site-readiness + lean category read


app = FastAPI(
    title="Unified CompIntel API",
    version="1.0.0",
    description="One JSON-in / JSON-out API for analyzer, merger, comparison, and weekly diff gate.",
)

# API-key auth + rate limiting (see api_security.py; env: COMPINTEL_API_KEY,
# RATE_LIMIT_PER_MINUTE, HEAVY_RATE_LIMIT_PER_MINUTE). Installed BEFORE CORS
# so 401/429 responses also carry CORS headers.
# from api_security import install_security
# install_security(app, service_name="unified-compintel-api")

# CORS: comma-separated origins via CORS_ORIGINS env var.
# Default covers local React dev (CRA :3000, Vite :5173).
# Set CORS_ORIGINS=https://yourapp.com in production, or "*" for open access
# (credentials are automatically disabled for "*").
import os as _os
_cors_origins = [
    o.strip() for o in _os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173",
    ).split(",") if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials="*" not in _cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -----------------------------
# Request models
# -----------------------------

class AnalyzePageRequest(BaseModel):
    url: str


class DetectStoresRequest(BaseModel):
    url: str


class CatalogRequest(BaseModel):
    url: str
    maxProducts: int = 500


class StoreProbeRequest(BaseModel):
    url: str
    allowBrowser: bool = False


class CollectionCountRequest(BaseModel):
    url: str


class AnalyzePagesRequest(BaseModel):
    urls: List[str] = Field(..., min_length=1, max_length=50)
    continueOnError: bool = True


class MergeSiteRequest(BaseModel):
    pages: List[Dict[str, Any]] = Field(..., min_length=1)


class CompareOptions(BaseModel):
    model_config = ConfigDict(extra="allow")

    includeOpenAiEvidencePack: bool = True
    includeProductDetails: bool = True
    includePageContent: bool = True
    includeSectionDetails: bool = True
    includeOneToOneComparison: bool = True
    maxProductsPerSite: Optional[int] = None
    maxSectionsPerSite: Optional[int] = None


class CompareSitesRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    userWebsite: Dict[str, Any]
    competitors: List[Dict[str, Any]] = Field(default_factory=list)
    options: CompareOptions = Field(default_factory=CompareOptions)


class CompareOneRequest(BaseModel):
    userWebsite: Dict[str, Any]
    competitorWebsite: Dict[str, Any]
    options: CompareOptions = Field(default_factory=CompareOptions)




class BuildAiPayloadOptions(BaseModel):
    model_config = ConfigDict(extra="allow")

    includeStats: bool = True
    includeEmptyModules: bool = True
    maxNavigationLinks: int = 12
    maxCollectionMatchups: int = 8
    maxProductMatches: int = 8
    maxUnmatchedProducts: int = 12
    maxPageMatches: int = 12
    maxSections: int = 5
    maxProductsPerSite: int = 8


class BuildAiPayloadRequest(BaseModel):
    comparison: Dict[str, Any]
    options: BuildAiPayloadOptions = Field(default_factory=BuildAiPayloadOptions)

class OpenAiInsightsOptions(BaseModel):
    model_config = ConfigDict(extra="allow")

    model: Optional[str] = None
    temperature: float = 0.2
    maxOutputTokens: int = 4096
    payloadOptions: Optional[Dict[str, Any]] = None


class OpenAiInsightsRequest(BaseModel):
    comparison: Dict[str, Any]
    options: OpenAiInsightsOptions = Field(default_factory=OpenAiInsightsOptions)


class GenerateInsightsRequest(BaseModel):
    """Build the OpenAI request AND call OpenAI server-side.

    Requires OPENAI_API_KEY in the API server environment (never sent by the client).
    """

    comparison: Dict[str, Any]
    options: OpenAiInsightsOptions = Field(default_factory=OpenAiInsightsOptions)


class DiffSettings(BaseModel):
    minimumSeverityForAI: str = "medium"
    priceChangeThresholdPercent: float = 5.0
    rankChangeThreshold: int = 3
    ignoreLowChanges: bool = True


class DiffSnapshotsRequest(BaseModel):
    """Same-site change detection: two site_snapshot_v2 files of ONE site."""

    model_config = ConfigDict(extra="allow")

    previousSnapshot: Dict[str, Any]
    currentSnapshot: Dict[str, Any]
    settings: Optional[Dict[str, Any]] = None


class DiffComparisonsRequest(BaseModel):
    previousComparison: Dict[str, Any]
    currentComparison: Dict[str, Any]
    settings: DiffSettings = Field(default_factory=DiffSettings)


class FullRunRequest(BaseModel):
    """
    End-to-end testing endpoint for React.

    It analyzes page URLs, merges user pages, merges competitor pages, compares them,
    and optionally runs weekly diff if previousComparison is provided.
    """

    userPages: List[str] = Field(..., min_length=1, max_length=20)
    competitorPages: List[str] = Field(..., min_length=1, max_length=50)
    previousComparison: Optional[Dict[str, Any]] = None
    compareOptions: CompareOptions = Field(default_factory=CompareOptions)
    diffSettings: DiffSettings = Field(default_factory=DiffSettings)
    continueOnError: bool = True
    includeAiPayload: bool = False
    aiPayloadOptions: BuildAiPayloadOptions = Field(default_factory=BuildAiPayloadOptions)


class PagePair(BaseModel):
    """Explicit workspace-page -> competitor-page mapping from onboarding.

    `no_equivalent` means the user declared this workspace page has no
    counterpart on THIS competitor's site. The page stays tracked for every
    other competitor, and the gap itself is reportable competitive
    intelligence - not an error.
    """

    model_config = ConfigDict(extra="allow")

    workspaceUrl: str
    competitorUrl: Optional[str] = None
    status: Literal["matched", "no_equivalent"]

    @model_validator(mode="after")
    def _check_pairing(self) -> "PagePair":
        if self.status == "matched" and not (self.competitorUrl or "").strip():
            raise ValueError("A 'matched' pair requires a competitorUrl.")
        if self.status == "no_equivalent" and (self.competitorUrl or "").strip():
            raise ValueError("A 'no_equivalent' pair must not carry a competitorUrl.")
        return self


class CompetitorInput(BaseModel):
    """One competitor as submitted by the onboarding UI."""

    model_config = ConfigDict(extra="allow")

    name: str = Field(..., min_length=1)
    url: str = Field(..., min_length=1)
    pages: List[str] = Field(..., min_length=1, max_length=50)
    pagePairs: List[PagePair] = Field(default_factory=list)

    @model_validator(mode="after")
    def _require_a_real_match(self) -> "CompetitorInput":
        # Mirrors the frontend guarantee, re-checked server-side: a competitor
        # with zero matched pages has nothing to compare.
        if self.pagePairs and not any(p.status == "matched" for p in self.pagePairs):
            raise ValueError(
                f"Competitor '{self.name}' has no matched pages - nothing to compare."
            )
        return self


class FullRunMultiRequest(BaseModel):
    """End-to-end run for one workspace against N competitors.

    The single-competitor `/api/v1/full-run` remains for backwards
    compatibility; this is the shape onboarding actually produces.
    """

    model_config = ConfigDict(extra="allow")

    userPages: List[str] = Field(..., min_length=1, max_length=20)
    competitors: List[CompetitorInput] = Field(..., min_length=1, max_length=10)
    previousComparison: Optional[Dict[str, Any]] = None
    compareOptions: CompareOptions = Field(default_factory=CompareOptions)
    diffSettings: DiffSettings = Field(default_factory=DiffSettings)
    continueOnError: bool = True
    includeAiPayload: bool = False
    aiPayloadOptions: BuildAiPayloadOptions = Field(default_factory=BuildAiPayloadOptions)


# -----------------------------
# Helpers
# -----------------------------

SEVERITY_SCORE = {
    "low": 10,
    "medium": 35,
    "high": 70,
    "critical": 100,
}


def normalize_url(url: str) -> str:
    return website_main.normalize_url(url)


def analyze_one_url(url: str) -> Dict[str, Any]:
    normalized = normalize_url(url)
    return website_main.analyze_url(normalized)


def apply_output_options(result: Dict[str, Any], options: CompareOptions) -> Dict[str, Any]:
    output = dict(result)

    if not options.includeOpenAiEvidencePack:
        output.pop("openAiEvidencePack", None)
    if not options.includeProductDetails:
        output.pop("productDetailComparison", None)
    if not options.includePageContent:
        output.pop("pageContentComparison", None)
    if not options.includeSectionDetails:
        output.pop("sectionComparison", None)
    if not options.includeOneToOneComparison:
        output.pop("oneToOneComparison", None)

    if options.maxProductsPerSite is not None:
        trim_product_details(output, options.maxProductsPerSite)
    if options.maxSectionsPerSite is not None:
        trim_section_details(output, options.maxSectionsPerSite)

    return output


def trim_product_details(output: Dict[str, Any], limit: int) -> None:
    if limit < 0:
        return

    product_block = output.get("productDetailComparison") or {}
    for site in product_block.get("sites", []) or []:
        products = site.get("products") or []
        site["products"] = products[:limit]
        site["trimmed"] = len(products) > limit
        site["returnedProducts"] = len(site["products"])

    evidence = output.get("openAiEvidencePack") or {}
    for site in evidence.get("sites", []) or []:
        products = site.get("products") or []
        site["products"] = products[:limit]
        site["productsTrimmed"] = len(products) > limit


def trim_section_details(output: Dict[str, Any], limit: int) -> None:
    if limit < 0:
        return

    section_block = output.get("sectionComparison") or {}
    for row in section_block.get("rows", []) or []:
        sections = row.get("sectionsByPosition") or []
        important = row.get("topImportantSections") or []
        row["sectionsByPosition"] = sections[:limit]
        row["topImportantSections"] = important[:limit]
        row["trimmed"] = len(sections) > limit

    homepage_block = output.get("homepageComparison") or {}
    for row in homepage_block.get("rows", []) or []:
        sections = row.get("topSections") or []
        row["topSections"] = sections[:limit]

    evidence = output.get("openAiEvidencePack") or {}
    for site in evidence.get("sites", []) or []:
        for page in site.get("pages", []) or []:
            sections = page.get("sections") or []
            page["sections"] = sections[:limit]
            page["sectionsTrimmed"] = len(sections) > limit


def normalize_product_key(product: Dict[str, Any]) -> str:
    url = (product.get("productUrl") or "").strip().lower().rstrip("/")
    if url:
        return url
    domain = (product.get("domain") or product.get("_domain") or "").strip().lower()
    name = " ".join((product.get("name") or "").strip().lower().split())
    return f"{domain}:{name}"


def get_products_from_comparison(data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    products: Dict[str, Dict[str, Any]] = {}
    sites = data.get("productDetailComparison", {}).get("sites", []) or []

    for site in sites:
        domain = site.get("domain")
        for product in site.get("products", []) or []:
            item = dict(product)
            item["_domain"] = domain or item.get("domain")
            key = normalize_product_key(item)
            item["_key"] = key
            products[key] = item

    return products


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").lower().split())


def text_changed_significantly(old: Any, new: Any, threshold: float = 0.75) -> bool:
    old_clean = clean_text(old)
    new_clean = clean_text(new)
    if not old_clean and not new_clean:
        return False
    similarity = SequenceMatcher(None, old_clean, new_clean).ratio()
    return similarity < threshold


def severity_from_score(score: int) -> str:
    if score >= 90:
        return "critical"
    if score >= 65:
        return "high"
    if score >= 30:
        return "medium"
    return "low"


def should_send_to_ai(overall_severity: str, minimum_severity: str) -> bool:
    order = {"low": 1, "medium": 2, "high": 3, "critical": 4}
    return order.get(overall_severity, 1) >= order.get(minimum_severity, 2)


def calculate_change_score(changes: List[Dict[str, Any]]) -> int:
    if not changes:
        return 0
    score = sum(SEVERITY_SCORE.get(c.get("severity", "low"), 10) for c in changes)
    return min(100, round(score / max(1, len(changes))))


def summarize_changes(changes: List[Dict[str, Any]]) -> Dict[str, int]:
    summary = {
        "totalChanges": len(changes),
        "criticalChanges": 0,
        "highChanges": 0,
        "mediumChanges": 0,
        "lowChanges": 0,
    }
    for change in changes:
        severity = change.get("severity", "low")
        key = f"{severity}Changes"
        if key in summary:
            summary[key] += 1
    return summary


def compare_catalog(previous: Dict[str, Any], current: Dict[str, Any]) -> List[Dict[str, Any]]:
    changes: List[Dict[str, Any]] = []
    old_sites = {site.get("domain"): site for site in previous.get("sites", []) or []}
    new_sites = {site.get("domain"): site for site in current.get("sites", []) or []}

    for domain, new_site in new_sites.items():
        old_site = old_sites.get(domain)
        if not old_site:
            changes.append({
                "type": "new_site_detected",
                "severity": "critical",
                "domain": domain,
                "whyImportant": "A new monitored site appeared in the comparison.",
            })
            continue

        old_count = old_site.get("uniqueProducts")
        new_count = new_site.get("uniqueProducts")
        if old_count != new_count:
            diff = (new_count or 0) - (old_count or 0)
            changes.append({
                "type": "catalog_product_count_change",
                "severity": "high" if abs(diff) >= 5 else "medium",
                "domain": domain,
                "oldValue": old_count,
                "newValue": new_count,
                "difference": diff,
                "whyImportant": "Total detected product count changed.",
            })

        old_sections = old_site.get("sectionCount")
        new_sections = new_site.get("sectionCount")
        if old_sections != new_sections:
            changes.append({
                "type": "section_count_change",
                "severity": "medium",
                "domain": domain,
                "oldValue": old_sections,
                "newValue": new_sections,
                "whyImportant": "Page or homepage structure may have changed.",
            })

    return changes


def compare_product_fields(old_product: Dict[str, Any], new_product: Dict[str, Any], settings: DiffSettings) -> List[Dict[str, Any]]:
    changes: List[Dict[str, Any]] = []

    old_price = old_product.get("priceValue")
    new_price = new_product.get("priceValue")
    if old_price is not None and new_price is not None and old_price != 0 and old_price != new_price:
        change_percent = ((new_price - old_price) / old_price) * 100
        if abs(change_percent) >= settings.priceChangeThresholdPercent:
            changes.append({
                "type": "price_change",
                "severity": "high" if abs(change_percent) >= 15 else "medium",
                "domain": new_product.get("_domain"),
                "productName": new_product.get("name"),
                "productUrl": new_product.get("productUrl"),
                "oldValue": old_price,
                "newValue": new_price,
                "changePercent": round(change_percent, 2),
                "whyImportant": "Product price changed beyond the configured threshold.",
            })

    old_rank = old_product.get("rank")
    new_rank = new_product.get("rank")
    if old_rank is not None and new_rank is not None:
        rank_diff = old_rank - new_rank
        if abs(rank_diff) >= settings.rankChangeThreshold:
            changes.append({
                "type": "rank_change",
                "severity": "high" if abs(rank_diff) >= 10 else "medium",
                "domain": new_product.get("_domain"),
                "productName": new_product.get("name"),
                "productUrl": new_product.get("productUrl"),
                "oldRank": old_rank,
                "newRank": new_rank,
                "rankChange": rank_diff,
                "whyImportant": "Product listing position changed significantly.",
            })

    old_availability = str(old_product.get("availability"))
    new_availability = str(new_product.get("availability"))
    if old_availability != new_availability:
        changes.append({
            "type": "availability_change",
            "severity": "high",
            "domain": new_product.get("_domain"),
            "productName": new_product.get("name"),
            "productUrl": new_product.get("productUrl"),
            "oldValue": old_product.get("availability"),
            "newValue": new_product.get("availability"),
            "whyImportant": "Stock or availability changed.",
        })

    old_desc = old_product.get("shortDescription") or old_product.get("descriptionText") or ""
    new_desc = new_product.get("shortDescription") or new_product.get("descriptionText") or ""
    if text_changed_significantly(old_desc, new_desc):
        changes.append({
            "type": "description_change",
            "severity": "medium",
            "domain": new_product.get("_domain"),
            "productName": new_product.get("name"),
            "productUrl": new_product.get("productUrl"),
            "whyImportant": "Product messaging changed significantly.",
        })

    old_variants = old_product.get("variantCount")
    new_variants = new_product.get("variantCount")
    if old_variants != new_variants:
        changes.append({
            "type": "variant_count_change",
            "severity": "medium",
            "domain": new_product.get("_domain"),
            "productName": new_product.get("name"),
            "productUrl": new_product.get("productUrl"),
            "oldValue": old_variants,
            "newValue": new_variants,
            "whyImportant": "Variant count changed, possibly indicating new shades, sizes, or options.",
        })

    return changes


def diff_comparisons(previous: Dict[str, Any], current: Dict[str, Any], settings: DiffSettings) -> Dict[str, Any]:
    changes: List[Dict[str, Any]] = []
    changes.extend(compare_catalog(previous, current))

    old_products = get_products_from_comparison(previous)
    new_products = get_products_from_comparison(current)

    old_keys = set(old_products.keys())
    new_keys = set(new_products.keys())

    for key in sorted(new_keys - old_keys):
        product = new_products[key]
        changes.append({
            "type": "new_product",
            "severity": "high",
            "domain": product.get("_domain"),
            "productName": product.get("name"),
            "productUrl": product.get("productUrl"),
            "priceValue": product.get("priceValue"),
            "category": product.get("category"),
            "whyImportant": "New product detected in current comparison.",
        })

    for key in sorted(old_keys - new_keys):
        product = old_products[key]
        changes.append({
            "type": "removed_product",
            "severity": "high",
            "domain": product.get("_domain"),
            "productName": product.get("name"),
            "productUrl": product.get("productUrl"),
            "category": product.get("category"),
            "whyImportant": "Previously detected product is no longer present.",
        })

    for key in sorted(old_keys & new_keys):
        changes.extend(compare_product_fields(old_products[key], new_products[key], settings))

    if settings.ignoreLowChanges:
        changes = [change for change in changes if change.get("severity") != "low"]

    change_score = calculate_change_score(changes)
    overall_severity = severity_from_score(change_score)
    should_send = should_send_to_ai(overall_severity, settings.minimumSeverityForAI)

    return {
        "schemaVersion": "comparison_diff_v1",
        "shouldSendToAI": should_send,
        "overallSeverity": overall_severity,
        "changeScore": change_score,
        "summary": summarize_changes(changes),
        "keyChanges": changes,
        "aiPayloadRecommendation": {
            "sendFullCurrentComparison": should_send,
            "sendPreviousComparison": False,
            "sendKeyChanges": should_send,
        },
    }




def build_ai_payload_for_api(comparison: Dict[str, Any], options: BuildAiPayloadOptions) -> Dict[str, Any]:
    """Build compact OpenAI-ready payload from full comparison JSON.

    This wraps comparison_app/build_ai_payload.py so CMD/file usage stays unchanged
    while React can use pure JSON input/output through the unified API.
    """
    ai_payload = ai_payload_module.build_ai_payload(comparison, options.model_dump())

    response: Dict[str, Any] = {
        "success": True,
        "data": ai_payload,
    }

    if options.includeStats:
        original_size = len(str(comparison))
        compact_size = len(str(ai_payload))
        response["stats"] = {
            "originalApproxCharacters": original_size,
            "aiPayloadApproxCharacters": compact_size,
            "reductionPercent": round((1 - compact_size / original_size) * 100, 2) if original_size else 0,
            "sourceSchemaVersion": comparison.get("schemaVersion"),
            "aiPayloadSchemaVersion": ai_payload.get("schemaVersion"),
        }

    return response

# -----------------------------
# API endpoints
# -----------------------------

@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service": "unified-compintel-api",
        "tools": {
            "websiteAnalyzer": True,
            "siteMerger": True,
            "comparisonEngine": True,
            "aiPayloadBuilder": True,
            "openAiInsightsBuilder": True,
            "comparisonDiff": True,
            "changeDetection": True,
        },
    }


@app.post("/api/v1/analyze-page")
def analyze_page(payload: AnalyzePageRequest) -> Dict[str, Any]:
    try:
        return analyze_one_url(payload.url)
    except Exception as exc:
        # Print the FULL traceback to the server log — otherwise a crash here is an
        # opaque 500 with no line number (exactly what hid the Gymshark failure).
        tb = traceback.format_exc()
        print(f"❌ [analyze-page] {payload.url} crashed:\n{tb}", flush=True)
        raise HTTPException(status_code=500, detail={
            "success": False,
            "message": "Website analysis failed.",
            "error": str(exc),
            "errorType": type(exc).__name__,
            # Last few frames, so the cause is visible in the API response too.
            "traceback": tb.strip().splitlines()[-6:],
        })


_COUNTRY_NAMES = {
    "US": "United States", "GB": "United Kingdom", "UK": "United Kingdom",
    "CA": "Canada", "AU": "Australia", "NZ": "New Zealand", "IE": "Ireland",
    "DE": "Germany", "FR": "France", "ES": "Spain", "IT": "Italy",
    "NL": "Netherlands", "SE": "Sweden", "PL": "Poland", "PT": "Portugal",
    "CH": "Switzerland", "AT": "Austria", "BE": "Belgium", "DK": "Denmark",
    "NO": "Norway", "FI": "Finland", "GR": "Greece", "CZ": "Czechia",
    "RO": "Romania", "PK": "Pakistan", "IN": "India", "BD": "Bangladesh",
    "LK": "Sri Lanka", "AE": "UAE", "SA": "Saudi Arabia", "QA": "Qatar",
    "KW": "Kuwait", "OM": "Oman", "BH": "Bahrain", "EG": "Egypt",
    "MY": "Malaysia", "SG": "Singapore", "ID": "Indonesia", "PH": "Philippines",
    "TH": "Thailand", "VN": "Vietnam", "TR": "Turkey", "JP": "Japan",
    "CN": "China", "HK": "Hong Kong", "KR": "South Korea", "TW": "Taiwan",
    "MX": "Mexico", "BR": "Brazil", "AR": "Argentina", "CL": "Chile",
    "CO": "Colombia", "ZA": "South Africa", "NG": "Nigeria", "KE": "Kenya",
    "MA": "Morocco", "IL": "Israel", "RU": "Russia",
}


def _extract_hreflang_locales(html, base):
    """Regional storefronts from <link rel=alternate hreflang=…> — returns
    [{code, country, label, url}], deduped by country, language-only alternates
    skipped."""
    import re as _re
    from urllib.parse import urljoin as _uj
    out, seen = [], set()
    for tag in _re.findall(r"<link\b[^>]*rel=[\"']?alternate[\"']?[^>]*>", html or "", _re.I):
        hl = _re.search(r"hreflang=[\"']?([a-zA-Z\-]+)[\"']?", tag)
        hr = _re.search(r"href=[\"']([^\"']+)[\"']", tag)
        if not (hl and hr):
            continue
        code = hl.group(1).lower()
        if code == "x-default":
            continue
        parts = code.split("-")
        if len(parts) >= 2:
            cc = parts[-1].upper()
        elif len(parts[0]) == 2 and parts[0].upper() in _COUNTRY_NAMES:
            cc = parts[0].upper()
        else:
            continue  # language-only alternate (e.g. hreflang="en") — not a store
        if cc in seen:
            continue
        seen.add(cc)
        out.append({
            "code": code,
            "country": cc,
            "label": _COUNTRY_NAMES.get(cc, cc),
            "url": _uj(base, hr.group(1)),
        })
    return out[:60]


@app.post("/api/v1/detect-stores")
def detect_stores_endpoint(payload: DetectStoresRequest) -> Dict[str, Any]:
    """Detect whether a site exposes multiple regional storefronts / currencies.

    Fetches the entry URL once (no location spoofing) and returns store_locale_v1,
    so the app can ASK the user which store + currency to track rather than
    letting an IP or a geo-redirect silently pick one.
    """
    try:
        normalized = normalize_url(payload.url)
        # Store signals (hreflang alternates, currency meta, Shopify.currency)
        # live in the initial server-rendered HTML, so a plain requests fetch is
        # enough. We deliberately AVOID the full fetch_html pipeline here, which
        # can escalate to Playwright and take 30-60s+ (the probe runs inline in
        # onboarding and must stay fast). We only fall back to the heavy fetch if
        # the light one comes back empty/blocked.
        html, final_url = None, None
        try:
            html, final_url, _ = fetch_with_requests(normalized)
        except Exception:
            html = None
        # If a plain request was blocked/empty (common on Cloudflare-protected
        # stores), try cloudscraper — it clears the challenge WITHOUT a browser,
        # so it stays fast. We deliberately do NOT call the full fetch_html
        # pipeline here: it force-renders homepages/root URLs in Playwright
        # (20-60s), which is far too slow for a probe that runs inline during
        # onboarding. Playwright is reserved for the JS-switcher case below.
        if not html:
            try:
                html, final_url, _ = fetch_with_cloudscraper(normalized)
            except Exception:
                html = None

        # Last-resort escalation: a genuinely bot-protected or JS-only store returns
        # nothing usable from the fast fetchers (safe_response nulls out challenge/
        # empty shells). Render it once in a REAL browser so onboarding can tell
        # "we truly cannot load this" apart from "responded but empty". Slower
        # (Playwright), but it only runs when both fast passes already failed.
        if not html:
            try:
                html, final_url, _ = website_main.fetch_with_playwright(normalized)
            except Exception:
                html = None

        # True ONLY when we actually retrieved real, parseable HTML by SOME method.
        # The fetchers null out bot-challenge/empty shells, so a truthy `html` means
        # we have the real page. Onboarding blocks progression on this — a site we
        # can't load can't be analyzed. (Distinct from `exists`, which is lenient and
        # true even for a DNS-resolvable domain we couldn't read.)
        fetched = bool(html)

        # Existence check: the site EXISTS if we got any HTML, or (when blocked)
        # if its hostname at least resolves in DNS. Only a domain that doesn't
        # resolve / refuses all connections counts as "doesn't exist", so a
        # Cloudflare-challenged live store is never wrongly flagged as missing.
        exists = bool(html)
        if not exists:
            try:
                import socket
                from urllib.parse import urlparse as _up_exist
                host = _up_exist(normalized).hostname
                for h in filter(None, [host, f"www.{host}" if host else None]):
                    try:
                        socket.getaddrinfo(h, None)
                        exists = True
                        break
                    except Exception:
                        continue
            except Exception:
                pass

        result = detect_stores(html or "", final_url or normalized)

        # If the page HINTS at a currency switcher (the container is there) but the
        # fast pass couldn't read more than one currency from it, the options are
        # almost certainly filled by JavaScript. Render once and re-detect — this
        # is the case for stores like ayeshashoaibmalik whose switcher is JS-built.
        if not result.get("multiCurrency") and has_currency_switcher_markup(html or ""):
            try:
                r_html, r_url, _ = website_main.fetch_with_playwright(final_url or normalized)
                if r_html:
                    rendered = detect_stores(r_html, r_url or final_url or normalized)
                    if rendered.get("multiCurrency"):
                        rendered["renderedFallback"] = True
                        result = rendered
            except Exception:
                pass  # Playwright unavailable/failed — keep the fast result

        # Wix (and some other builders) render prices in JS but expose the ACTIVE
        # currency as a ?currency=XXX query param on product / switcher links. Read
        # it straight from the HTML before falling back to heavier methods.
        if not result.get("currentCurrency"):
            try:
                import re as _rw
                _valid = set(COUNTRY_CURRENCY.values())
                _codes = []
                for _m in _rw.finditer(r"[?&]currency=([A-Za-z]{3})\b", html or ""):
                    _c = _m.group(1).upper()
                    if _c in _valid and _c not in _codes:
                        _codes.append(_c)
                if _codes:
                    result["currentCurrency"] = _codes[0]
                    result["currencies"] = list(dict.fromkeys((result.get("currencies") or []) + _codes))
                    if len(_codes) > 1:
                        result["multiCurrency"] = True
            except Exception:
                pass

        # WooCommerce stores rarely put the currency in the HTML, so the picker
        # would show nothing. The Store API exposes it directly (prices carry a
        # currency_code) — read it when the HTML pass found no currency.
        if not result.get("currentCurrency"):
            try:
                import json as _j
                from urllib.parse import urlparse as _upc
                _p = _upc(final_url or normalized)
                _basehost = f"{_p.scheme}://{_p.netloc}"

                # Fetch the Store API JSON directly. NOTE: the shared HTML fetchers
                # (fetch_with_requests / fetch_with_cloudscraper) route through
                # safe_response, which flags any response WITHOUT a <body> tag as
                # "blocked" — so they null out every JSON API response. We must do a
                # raw GET + .json() here, exactly like /catalog's _fetch_json, using
                # a browser UA (+ cloudscraper's TLS fingerprint) to clear WAFs.
                _woo_headers = {
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
                    ),
                    "Accept": "application/json,text/plain,*/*",
                }
                try:
                    import cloudscraper as _cs
                    _woo_sess = _cs.create_scraper(
                        browser={"browser": "chrome", "platform": "windows", "mobile": False}
                    )
                except Exception:
                    import requests as _rq
                    _woo_sess = _rq

                def _woo_json(u):
                    try:
                        _r = _woo_sess.get(u, headers=_woo_headers, timeout=20)
                        if getattr(_r, "ok", False):
                            _d = _r.json()
                            if isinstance(_d, (list, dict)):
                                return _d
                    except Exception:
                        pass
                    return None

                for prefix in ("/wp-json/wc/store/v1", "/wp-json/wc/store"):
                    _data = _woo_json(f"{_basehost}{prefix}/products?per_page=1")
                    if isinstance(_data, list) and _data:
                        _cc = (_data[0].get("prices") or {}).get("currency_code")
                        if _cc:
                            _cc = str(_cc).upper()
                            result["currentCurrency"] = _cc
                            result["currencies"] = list(dict.fromkeys((result.get("currencies") or []) + [_cc]))
                            break
            except Exception:
                pass

        # Last resort: infer the currency from the page's DECLARED LOCALE
        # (og:locale "en_US" / <html lang="en-US">). Many single-currency stores
        # expose no machine-readable currency in the HTML and price with an
        # ambiguous "$", so without this a plain USD store forces a manual pick.
        # Only a country → currency guess, used strictly when nothing else resolved.
        if not result.get("currentCurrency"):
            try:
                import re as _rc
                mcc = (
                    _rc.search(r"og:locale[\"'][^>]*content=[\"'][a-zA-Z]{2}[_-]([A-Za-z]{2})", html or "", _rc.I)
                    or _rc.search(r"content=[\"'][a-zA-Z]{2}[_-]([A-Za-z]{2})[\"'][^>]*og:locale", html or "", _rc.I)
                    or _rc.search(r"<html[^>]*\blang=[\"'][a-zA-Z]{2}[-_]([A-Za-z]{2})", html or "", _rc.I)
                )
                if mcc:
                    _cccode = mcc.group(1).upper()
                    _cur = COUNTRY_CURRENCY.get(_cccode)
                    if _cur:
                        result["currentCurrency"] = _cur
                        result["currencies"] = list(dict.fromkeys((result.get("currencies") or []) + [_cur]))
                        result["currencyFrom"] = "locale"
            except Exception:
                pass

        result["success"] = True
        result["exists"] = exists
        result["fetched"] = fetched
        result["inputUrl"] = normalized
        result["fetchedUrl"] = result.get("fetchedUrl") or final_url or normalized
        # Regional storefronts (from <link hreflang>) so the UI can offer a
        # "which country store?" picker for geo-gated sites (zara.com, hm.com).
        result["locales"] = _extract_hreflang_locales(html or "", final_url or normalized)
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail={
            "success": False,
            "message": "Store detection failed.",
            "error": str(exc),
        })


@app.post("/api/v1/debug-fetch")
def debug_fetch_endpoint(payload: DetectStoresRequest) -> Dict[str, Any]:
    """DEBUG ONLY — show exactly what the crawler retrieves for a URL.

    Runs the same fetch chain onboarding uses (requests → cloudscraper → real
    browser) and returns the method that worked, HTTP status, final URL, page
    title, HTML length, and a text snippet — so you can see precisely what the
    analyzer 'saw'. Not used by the app; safe to remove later.
    """
    import re as _re_dbg
    normalized = normalize_url(payload.url)
    steps = []
    html, final_url, method = None, None, None

    for name, fn in (
        ("requests", lambda u: fetch_with_requests(u)),
        ("cloudscraper", lambda u: fetch_with_cloudscraper(u)),
        ("playwright", lambda u: website_main.fetch_with_playwright(u)),
    ):
        if html:
            break
        try:
            h, furl, hdrs = fn(normalized)
            status = None
            try:
                status = (hdrs or {}).get("status_code")
            except Exception:
                status = None
            steps.append({"method": name, "status": status, "gotHtml": bool(h), "len": len(h or "")})
            if h:
                html, final_url, method = h, furl, name
        except Exception as e:
            steps.append({"method": name, "error": str(e)[:200]})

    # Extract a human-readable view of what came back.
    title = None
    text_snippet = None
    if html:
        try:
            from bs4 import BeautifulSoup as _BS
            _soup = _BS(html, "lxml")
            _t = _soup.find("title")
            title = _t.get_text(strip=True) if _t else None
            for _s in _soup(["script", "style", "noscript"]):
                _s.extract()
            _txt = _re_dbg.sub(r"\s+", " ", _soup.get_text(" ", strip=True))
            text_snippet = _txt[:1500]
        except Exception:
            text_snippet = _re_dbg.sub(r"\s+", " ", _re_dbg.sub(r"<[^>]+>", " ", html))[:1500]

    return {
        "success": True,
        "inputUrl": normalized,
        "fetchedUrl": final_url or normalized,
        "workingMethod": method,          # which fetcher actually returned real HTML
        "fetched": bool(html),
        "htmlLength": len(html or ""),
        "title": title,
        "textSnippet": text_snippet,      # first ~1500 chars of visible text
        "attempts": steps,                # per-method status/length so you see WHY it failed
    }


@app.post("/api/v1/validate-site")
def validate_site_endpoint(payload: DetectStoresRequest) -> Dict[str, Any]:
    """Onboarding readiness check — confirm we can actually read the homepage, a
    collection/category listing, and a product page (rendering JS sites in a real
    browser when needed), and read the currency from the product. Platform-agnostic;
    slower than the probe (may render several pages), but onboarding tolerates it.
    Returns { ok, currency, stages:{homepage, collection, product} }.
    """
    try:
        normalized = normalize_url(payload.url)
        out = validate_site(normalized)
        out["success"] = True
        out["inputUrl"] = normalized
        return out
    except Exception as exc:
        raise HTTPException(status_code=500, detail={
            "success": False,
            "message": "Site validation failed.",
            "error": str(exc),
        })


@app.post("/api/v1/quick-catalog")
def quick_catalog_endpoint(payload: DetectStoresRequest) -> Dict[str, Any]:
    """Lean category read from a rendered homepage — a fast fallback for competitor
    suggestion when /collections.json is Cloudflare-blocked and the full catalog
    render times out. Returns { categories, currency }."""
    try:
        normalized = normalize_url(payload.url)
        out = quick_catalog(normalized)
        out["success"] = True
        return out
    except Exception as exc:
        raise HTTPException(status_code=500, detail={
            "success": False, "message": "Quick catalog failed.", "error": str(exc),
        })


class PolicyPagesRequest(BaseModel):
    url: str
    footerLinks: List[Dict[str, Any]] = Field(default_factory=list)
    navLinks: List[Dict[str, Any]] = Field(default_factory=list)
    platform: str = ""


@app.post("/api/v1/policy-pages")
def policy_pages_endpoint(payload: PolicyPagesRequest) -> Dict[str, Any]:
    """Discover an ecommerce store's shipping/returns/payment/FAQ pages so they can
    be auto-analyzed (nobody selects them, but they carry high-signal intel —
    free-ship thresholds, COD, bank-deposit offers, delivery times).

    Prefers the caller-supplied footer/nav links + platform (the competitor worker
    already has them from the homepage crawl); only fetches the homepage itself when
    no links were provided."""
    try:
        from level1_detector.policy_pages import discover_policy_pages  # type: ignore
        normalized = normalize_url(payload.url)
        footer = payload.footerLinks or []
        nav = payload.navLinks or []
        platform = payload.platform or ""

        # No links supplied → best-effort homepage read to harvest footer <a> tags.
        if not footer and not nav:
            try:
                from bs4 import BeautifulSoup  # type: ignore
                html = None
                for fetch in (fetch_with_requests, fetch_with_cloudscraper):
                    try:
                        html, _u, _h = fetch(normalized)
                    except Exception:
                        html = None
                    if html:
                        break
                if html:
                    soup = BeautifulSoup(html, "html.parser")
                    for f in soup.find_all("footer"):
                        for a in f.find_all("a", href=True):
                            footer.append({"text": a.get_text(" ", strip=True), "url": a["href"]})
            except Exception:
                pass

        pages = discover_policy_pages(
            normalized, footer_links=footer, nav_links=nav, platform=platform
        )
        return {"success": True, "pages": pages}
    except Exception as exc:
        raise HTTPException(status_code=500, detail={
            "success": False, "message": "Policy page discovery failed.", "error": str(exc),
        })


class ScaleCheckRequest(BaseModel):
    url: str
    platform: str = ""
    totalProducts: Optional[int] = None
    vendorCount: Optional[int] = None
    config: Dict[str, Any] = Field(default_factory=dict)


@app.post("/api/v1/scale-check")
def scale_check_endpoint(payload: ScaleCheckRequest) -> Dict[str, Any]:
    """Decide self-serve vs enterprise for a store. Marketplace-first: denylist +
    structural signals (fetched from robots.txt), with catalog size only as a very
    high backstop. Node computes totalProducts (via getStoreProductTotal) and passes
    it in; this endpoint fetches robots.txt cheaply for the structural signals."""
    try:
        from level1_detector.marketplace_gate import classify_scale  # type: ignore
        normalized = normalize_url(payload.url)

        # Cheap robots.txt read for marketplace structure (denylist alone catches the
        # famous ones; this catches unlisted marketplaces).
        robots = ""
        try:
            from urllib.parse import urlparse as _up
            _pp = _up(normalized)
            robots_url = f"{_pp.scheme}://{_pp.netloc}/robots.txt"
            for fetch in (fetch_with_requests, fetch_with_cloudscraper):
                try:
                    html, _u, _h = fetch(robots_url)
                except Exception:
                    html = None
                if html:
                    robots = html[:20000]
                    break
        except Exception:
            robots = ""

        result = classify_scale(
            normalized,
            platform=payload.platform or "",
            total_products=payload.totalProducts,
            robots=robots,
            vendor_count=payload.vendorCount,
            config=payload.config or {},
        )
        result["success"] = True
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail={
            "success": False, "message": "Scale check failed.", "error": str(exc),
        })


class ProAutoselectRequest(BaseModel):
    collections: List[Dict[str, Any]] = Field(default_factory=list)
    navHandles: List[str] = Field(default_factory=list)
    cap: int = 95
    competitorCollections: Optional[List[Dict[str, Any]]] = None
    useAi: bool = False


@app.post("/api/v1/pro-autoselect")
def pro_autoselect_endpoint(payload: ProAutoselectRequest) -> Dict[str, Any]:
    """Pro complete-site: rank/cap the most important collections (no manual page
    picking) and, when competitorCollections are supplied, auto-pair them across the
    two sites by canonical category. Products come from the bulk catalog, so this is
    collections-only — the heavy lifting stays off the per-page crawler."""
    try:
        from level1_detector.pro_autoselect import (  # type: ignore
            select_collections_for_complete_site, auto_pair_collections,
        )
        selected = select_collections_for_complete_site(
            payload.collections, cap=payload.cap, nav_handles=payload.navHandles, use_ai=payload.useAi
        )
        out: Dict[str, Any] = {"success": True, "selected": selected, "selectedCount": len(selected)}
        if payload.competitorCollections is not None:
            comp_selected = select_collections_for_complete_site(
                payload.competitorCollections, cap=payload.cap, nav_handles=payload.navHandles, use_ai=payload.useAi
            )
            out["competitorSelected"] = comp_selected
            out["pairing"] = auto_pair_collections(selected, comp_selected)
        return out
    except Exception as exc:
        raise HTTPException(status_code=500, detail={
            "success": False, "message": "Pro auto-select failed.", "error": str(exc),
        })


class ProductMatchRequest(BaseModel):
    userProducts: List[Dict[str, Any]] = Field(default_factory=list)
    competitorProducts: List[Dict[str, Any]] = Field(default_factory=list)
    useAi: bool = False


@app.post("/api/v1/suggest-product-matches")
def suggest_product_matches_endpoint(payload: ProductMatchRequest) -> Dict[str, Any]:
    """Suggest product-to-product matches within a chosen collection pair. Local
    similarity always runs; useAi adds a cheap-model confirmation pass (Growth+).
    Suggestion-only — the user confirms in the UI; nothing is auto-asserted."""
    try:
        from comparison_engine.product_match import suggest_matches  # type: ignore
        out = suggest_matches(
            payload.userProducts, payload.competitorProducts, use_ai=payload.useAi
        )
        out["success"] = True
        return out
    except Exception as exc:
        raise HTTPException(status_code=500, detail={
            "success": False, "message": "Product match suggestion failed.", "error": str(exc),
        })


@app.post("/api/v1/store-probe")
def store_probe_endpoint(payload: StoreProbeRequest) -> Dict[str, Any]:
    """Storefront probe for competitor-suggestion verification.

    Reads a candidate store's Shopify/Woo JSON to confirm it's a REAL priced
    ecommerce store and to collect its categories + product titles (for the
    catalog-overlap check). Fetch order per URL: cloudscraper first (fast, clears
    most Cloudflare challenges), then a real browser (Playwright) as a fallback
    for the tougher WAFs that block cloudscraper too. To keep it affordable across
    many candidates, only the PRIMARY products fetch is allowed to escalate to
    Playwright; the secondary collections fetch is cloudscraper-only (best-effort
    nicer category names). Returns reachable + hasPricing + categories/types/titles.
    """
    import json as _json
    import html as _html
    import re as _re_probe
    from urllib.parse import urlparse as _up, urljoin as _urljoin_probe

    def _clean(s):
        return _html.unescape(str(s or "")).strip()

    try:
        normalized = normalize_url(payload.url)
        parsed = _up(normalized)
        base = f"{parsed.scheme}://{parsed.netloc}"

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json,text/plain,*/*",
        }

        try:
            import cloudscraper
            session = cloudscraper.create_scraper(
                browser={"browser": "chrome", "platform": "windows", "mobile": False}
            )
        except Exception:
            import requests as session

        try:
            from level1_detector.fetcher import fetch_json_with_playwright
        except Exception:
            fetch_json_with_playwright = None

        allow_browser = bool(getattr(payload, "allowBrowser", False))

        def _get_json(u, allow_pw=False):
            # cloudscraper first — short timeout so a hanging WAF can't stall the
            # whole suggestion (each candidate hits this a couple of times).
            try:
                r = session.get(u, headers=headers, timeout=9)
                if getattr(r, "ok", False):
                    d = r.json()
                    if isinstance(d, (dict, list)):
                        return d
            except Exception:
                pass
            # Playwright fallback (real browser) — only for the primary fetch AND
            # only when the caller opted in (Node escalates a capped few), so a
            # Cloudflare-hardened store can still be read without a browser render
            # on every candidate.
            if allow_pw and allow_browser and fetch_json_with_playwright:
                try:
                    txt = fetch_json_with_playwright(u)
                    if txt:
                        d = _json.loads(txt)
                        if isinstance(d, (dict, list)):
                            return d
                except Exception:
                    pass
            return None

        categories, product_types, titles = [], [], []
        vendors = []
        products_seen = 0
        has_pricing = False
        reachable = False
        platform = None
        woo_currency = None  # WooCommerce exposes the currency directly in prices

        # ── Shopify: products.json is the primary signal (pricing + types +
        #    titles) and may escalate to Playwright; collections is best-effort. ──
        prods = _get_json(f"{base}/products.json?limit=100", allow_pw=True)
        prod_list = prods.get("products") if isinstance(prods, dict) else None
        if prod_list:
            platform = "shopify"
            reachable = True
            for p in prod_list:
                products_seen += 1
                pt = p.get("product_type")
                if pt:
                    product_types.append(pt)
                # vendor diversity distinguishes a single brand (one vendor) from
                # a multi-brand marketplace (many vendors).
                vd = _clean(p.get("vendor"))
                if vd:
                    vendors.append(vd.lower())
                t = _clean(p.get("title"))
                if t:
                    titles.append(t)
                for v in (p.get("variants") or []):
                    try:
                        if float(v.get("price") or 0) > 0:
                            has_pricing = True
                    except Exception:
                        pass

            cols = _get_json(f"{base}/collections.json?limit=250")
            col_list = cols.get("collections") if isinstance(cols, dict) else None
            for c in (col_list or []):
                if c.get("products_count") == 0:
                    continue
                t = _clean(c.get("title"))
                if t:
                    categories.append(t)

        # ── WooCommerce Store API fallback ───────────────────
        if not platform:
            for prefix in ("/wp-json/wc/store/v1", "/wp-json/wc/store"):
                wp = _get_json(f"{base}{prefix}/products?per_page=50", allow_pw=True)
                wc = _get_json(f"{base}{prefix}/products/categories?per_page=100")
                has_prods = isinstance(wp, list) and wp
                has_cats = isinstance(wc, list) and wc
                if has_prods or has_cats:
                    platform = "woocommerce"
                    reachable = True
                    for c in (wc or []):
                        if (c.get("count") or 0) == 0:
                            continue
                        t = _clean(c.get("name"))
                        if t:
                            categories.append(t)
                    for p in (wp or []):
                        t = _clean(p.get("name"))
                        if t:
                            titles.append(t)
                        for cat in (p.get("categories") or []):
                            nm = _clean(cat.get("name"))
                            if nm:
                                categories.append(nm)
                        pr = None
                        if isinstance(p.get("prices"), dict):
                            pr = p["prices"].get("price")
                            # WooCommerce Store API prices carry the currency code
                            # directly — the most reliable region signal we get.
                            if not woo_currency:
                                cc = p["prices"].get("currency_code")
                                if cc:
                                    woo_currency = str(cc).upper()
                        pr = pr if pr is not None else p.get("price")
                        try:
                            if float(pr or 0) > 0:
                                has_pricing = True
                        except Exception:
                            pass
                    break

        # ── Homepage pass: existence + currency (region check) + site name ────
        # One extra cloudscraper fetch gives us three things the competitor
        # discovery needs: proof the site EXISTS, its CURRENCY (to confirm it
        # serves the user's region), and its real NAME (no LLM to name it).
        exists = reachable
        site_currency = woo_currency  # prefer the WooCommerce currency_code
        site_name = None
        # None = homepage not read; else a count of MARKETPLACE signals (a
        # "shop by brand" directory etc. that single brands don't have).
        marketplace_signals = None
        # Whether the homepage looks like an ECOMMERCE store (cart/collections/
        # Shopify markers) — lets us keep a real store whose catalog JSON is
        # blocked, while still dropping news/service/brochure sites.
        looks_like_store = None
        # Primary content language (e.g. "de-de") — a strong region hint when the
        # currency is ambiguous (a de_DE / EUR store sells into Germany, not the US).
        site_language = None
        # Regional storefront alternates from <link hreflang> — lets the caller
        # send a geo-gated store (zara.com) to its right country store (zara.com/us).
        locales = []
        try:
            hr = session.get(base, headers={**headers, "Accept": "text/html,*/*"}, timeout=10)
            home_html = hr.text if getattr(hr, "ok", False) else ""
            if home_html:
                exists = True
                # <title> → cleaned site name (strip common suffixes).
                mt = _re_probe.search(r"<title[^>]*>(.*?)</title>", home_html, _re_probe.I | _re_probe.S)
                if mt:
                    t = _clean(_html.unescape(mt.group(1)))
                    t = _re_probe.split(r"\s[|\-–—:]\s", t)[0].strip()
                    if t:
                        site_name = t[:60]
                try:
                    if not site_currency:
                        loc = detect_stores(home_html, base)
                        site_currency = loc.get("currentCurrency") or (loc.get("currencies") or [None])[0]
                except Exception:
                    pass

                # Marketplace signals: a brand directory / "shop by brand" nav,
                # or brand-filter links — hallmarks of a multi-brand retailer.
                low = home_html.lower()
                marketplace_signals = 0
                for kw in (
                    "shop by brand", "shop-by-brand", "shopbybrand",
                    "all brands", "top brands", "featured brands", "our brands",
                    "browse brands", "brands a-z", "brands a to z",
                    "/collections/vendors", "/pages/brands", "/brands\"", "/brands/",
                    "shop brands",
                ):
                    if kw in low:
                        marketplace_signals += 1
                if low.count("?vendor=") + low.count("filter.p.vendor") >= 2:
                    marketplace_signals += 1
                if low.count("/brand/") >= 3:
                    marketplace_signals += 1

                # Ecommerce-store markers — is this a shop at all?
                store_hits = 0
                for kw in (
                    "add to cart", "add-to-cart", "addtocart", "/cart", "checkout",
                    "/collections/", "/products/", "cdn.shopify", "shopify.theme",
                    "woocommerce", "add_to_cart", "data-product-id", "buy now",
                    "shop now", "product-price", "shopping-cart", "sales-price",
                ):
                    if kw in low:
                        store_hits += 1
                looks_like_store = store_hits >= 2

                # Primary content language: og:locale ("de_DE") or <html lang="de-DE">.
                mlang = (
                    _re_probe.search(r"<meta[^>]+property=[\"']og:locale[\"'][^>]*content=[\"']([a-zA-Z_\-]+)[\"']", home_html, _re_probe.I)
                    or _re_probe.search(r"<meta[^>]+content=[\"']([a-zA-Z_\-]+)[\"'][^>]*property=[\"']og:locale[\"']", home_html, _re_probe.I)
                    or _re_probe.search(r"<html[^>]*\blang=[\"']([a-zA-Z_\-]+)[\"']", home_html, _re_probe.I)
                )
                if mlang:
                    site_language = mlang.group(1).replace("_", "-").lower()

                # Regional storefront alternates (<link rel=alternate hreflang=…>).
                seen_hl = set()
                for tag in _re_probe.findall(r"<link\b[^>]*rel=[\"']?alternate[\"']?[^>]*>", home_html, _re_probe.I):
                    hl = _re_probe.search(r"hreflang=[\"']?([a-zA-Z\-]+)[\"']?", tag)
                    hr = _re_probe.search(r"href=[\"']([^\"']+)[\"']", tag)
                    if hl and hr:
                        code = hl.group(1).lower()
                        if code in seen_hl or code == "x-default":
                            continue
                        seen_hl.add(code)
                        locales.append({"hreflang": code, "url": _urljoin_probe(base, hr.group(1))})
        except Exception:
            pass

        # If nothing resolved at all, do a last-ditch DNS check for existence.
        if not exists:
            try:
                import socket
                host = _up(base).hostname
                for h in filter(None, [host, f"www.{host}" if host else None]):
                    try:
                        socket.getaddrinfo(h, None)
                        exists = True
                        break
                    except Exception:
                        continue
            except Exception:
                pass

        return {
            "success": True,
            "reachable": reachable,
            "exists": exists,
            "platform": platform,
            "categories": list(dict.fromkeys(categories))[:120],
            "productTypes": list(dict.fromkeys(product_types))[:60],
            "titles": list(dict.fromkeys(titles))[:100],
            "hasPricing": has_pricing,
            "currency": site_currency,
            "siteName": site_name,
            # Distinct vendor count (Shopify only) → brand vs marketplace signal.
            # null when we couldn't read a vendor field (e.g. WooCommerce).
            "vendorCount": (len(set(vendors)) if vendors else (0 if platform == "shopify" else None)),
            "productsSeen": products_seen,
            # Cross-platform marketplace signal from the homepage (null if unread).
            "marketplaceSignals": marketplace_signals,
            # Homepage looks like an ecommerce store (null if homepage unread).
            "looksLikeStore": looks_like_store,
            # Primary content language ("de-de") — region hint for ambiguous currencies.
            "language": site_language,
            # Regional storefront alternates [{hreflang, url}] from the homepage.
            "locales": locales[:60],
        }
    except Exception as exc:
        return {
            "success": False,
            "reachable": False,
            "exists": False,
            "platform": None,
            "categories": [],
            "productTypes": [],
            "titles": [],
            "hasPricing": False,
            "currency": None,
            "siteName": None,
            "vendorCount": None,
            "productsSeen": 0,
            "marketplaceSignals": None,
            "looksLikeStore": None,
            "language": None,
            "locales": [],
            "error": str(exc),
        }


@app.post("/api/v1/collection-count")
def collection_count_endpoint(payload: CollectionCountRequest) -> Dict[str, Any]:
    """LIVE product count for a single collection/category — the number the
    storefront actually shows ("Showing N products"), NOT Shopify's products_count
    (which counts assigned-but-not-necessarily-visible products and overcounts).

    Primary: parse the collection PAGE. Fallback: count the collection's
    products.json (online-store-published). Returns { count } or { count: null }.
    """
    import re as _rc
    from urllib.parse import urlparse as _upc

    url = (payload.url or "").strip()
    if not url or "." not in url:
        return {"count": None}

    _headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,*/*",
    }
    try:
        import cloudscraper as _cs
        _sess = _cs.create_scraper(browser={"browser": "chrome", "platform": "windows", "mobile": False})
    except Exception:
        import requests as _sess  # type: ignore

    def _get(u, accept):
        try:
            r = _sess.get(u, headers={**_headers, "Accept": accept}, timeout=15)
            if getattr(r, "ok", False):
                return r
        except Exception:
            pass
        return None

    # 1) The collection PAGE's own "Showing N products/results/items" — exactly what
    #    a shopper sees. Anchored on "showing" so we never grab a filter-facet number.
    r = _get(url, "text/html,*/*")
    if r is not None:
        text = _rc.sub(r"\s+", " ", _rc.sub(r"<[^>]+>", " ", r.text or ""))
        m = _rc.search(
            r"showing\s+(?:all\s+)?(?:[\d,]+\s*(?:–|—|-|to)\s*[\d,]+\s+of\s+)?([\d,]+)\s+(?:products|results|items)",
            text, _rc.I,
        )
        if m:
            try:
                return {"count": int(m.group(1).replace(",", "")), "source": "page"}
            except Exception:
                pass

    # 2) Fallback (Shopify): count the collection's products.json — the online-store
    #    published products, which is what the collection page renders.
    try:
        p = _upc(url)
        base = f"{p.scheme}://{p.netloc}"
        segs = [s for s in (p.path or "").split("/") if s]
        handle = segs[-1] if segs else ""
        if handle and "collections" in segs:
            total = 0
            for page in range(1, 6):
                rr = _get(f"{base}/collections/{handle}/products.json?limit=250&page={page}", "application/json,*/*")
                if rr is None:
                    break
                try:
                    arr = (rr.json() or {}).get("products", [])
                except Exception:
                    break
                total += len(arr)
                if len(arr) < 250:
                    break
            if total:
                return {"count": total, "source": "products_json"}
    except Exception:
        pass

    return {"count": None}


def _harvest_live_nav_links(base: str, html: str):
    """Harvest every link the store surfaces in its LIVE navigation chrome —
    header, nav, mega-menu/dropdown panels, and footer — from a RENDERED page.

    This is deliberately structure-agnostic: instead of reconstructing the menu
    tree (which fails on custom SPAs whose nav is non-semantic <div>s), we just
    collect the anchors present in the nav chrome and return their normalized
    URLs + last-path slugs. The caller intersects this with the full catalog to
    decide which known collections are actually LIVE on the site ("in their
    menu"), independent of how the menu is built.

    Returns (norm_urls:set, slugs:set). `norm_urls` are lowercased, same-host,
    query/'#'/trailing-slash stripped; `slugs` are the final path segment of
    each — so a link matches a catalog collection even when host/scheme differ.
    """
    from urllib.parse import urljoin as _urljoin, urlparse as _urlparse
    try:
        from bs4 import BeautifulSoup
    except Exception:
        return set(), set()

    def _norm(u):
        return (u or "").split("?")[0].split("#")[0].rstrip("/").lower()

    def _slug(u):
        try:
            segs = _urlparse(u).path.rstrip("/").lower().split("/")
            return segs[-1] if segs and segs[-1] else ""
        except Exception:
            return ""

    try:
        base_host = (_urlparse(base).netloc or "").lower()
        if base_host.startswith("www."):
            base_host = base_host[4:]
    except Exception:
        base_host = ""

    def _same_host(u):
        try:
            h = (_urlparse(u).netloc or "").lower()
            if h.startswith("www."):
                h = h[4:]
            return (not h) or (base_host and h == base_host)
        except Exception:
            return False

    try:
        soup = BeautifulSoup(html or "", "html.parser")
    except Exception:
        return set(), set()

    # Drop hidden/sr-only nodes so their stray links don't count as "surfaced".
    for junk in soup.select(".visually-hidden, .sr-only, .visuallyhidden, .screen-reader-text, [aria-hidden=true]"):
        try:
            junk.decompose()
        except Exception:
            pass

    # Nav-chrome regions, most reliable first. Class-substring selectors catch
    # the div/SPA menus (mega/dropdown/subnav/flyout) that carry no <nav> tag.
    # Case-insensitive substring selectors (the " i" flag) so camelCase ids/classes
    # like "mainNav" / "HeaderMenu" are caught too.
    chrome_selectors = [
        "header", "nav", "footer",
        "[role=navigation]", "[role=menubar]", "[role=menu]",
        "[class*=header i]", "[class*=nav i]", "[class*=menu i]", "[class*=footer i]",
        "[class*=mega i]", "[class*=dropdown i]", "[class*=drop-down i]",
        "[class*=submenu i]", "[class*=sub-menu i]", "[class*=subnav i]",
        "[class*=flyout i]", "[class*=fly-out i]", "[class*=departments i]",
        "[id*=nav i]", "[id*=menu i]", "[id*=header i]", "[id*=footer i]",
    ]

    def _collect(nodes):
        urls, slugs = set(), set()
        for node in nodes:
            try:
                anchors = node.select("a[href]")
            except Exception:
                continue
            for a in anchors:
                href = a.get("href")
                if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                    continue
                try:
                    full = _urljoin(base, href)
                except Exception:
                    continue
                if not _same_host(full):
                    continue
                n = _norm(full)
                if not n:
                    continue
                urls.add(n)
                s = _slug(full)
                if s:
                    slugs.add(s)
        return urls, slugs

    chrome_nodes = []
    for sel in chrome_selectors:
        try:
            chrome_nodes.extend(soup.select(sel))
        except Exception:
            pass

    urls, slugs = _collect(chrome_nodes)

    # SPA fallback: if the chrome selectors barely matched (non-semantic markup),
    # harvest EVERY same-host anchor on the page. Intersection with the known
    # catalog keeps this safe — a stray "About" link matches no collection, while
    # a category tile/link in the body still counts as surfaced/live.
    if len(urls) < 5:
        all_urls, all_slugs = _collect([soup])
        urls |= all_urls
        slugs |= all_slugs

    return urls, slugs


def _extract_nav_menu(base: str, html: str, title_by_url=None, product_urls=None):
    """Parse a storefront's NAVIGATION MENU into a flat list of collection /
    category links with their menu-ancestry path.

    The menu is the merchant's curated, deduped, hierarchical view of what
    matters — unlike /collections.json (which lists every collection, including
    automated duplicates and ones hidden from the storefront).

    Handles mega-menus (multiple submenu columns per item) and prefers the
    canonical collection title (from the catalog) for leaves, falling back to the
    cleaned menu text. Returns
    ([{ "url", "title", "path": [ancestor labels] }, ...], category_link_count).
    """
    import re as _re
    import html as _htmlmod
    from urllib.parse import urljoin as _urljoin, urlparse as _urlparse
    try:
        from bs4 import BeautifulSoup
    except Exception:
        return [], 0

    title_by_url = title_by_url or {}

    def _norm(u):
        return (u or "").split("?")[0].split("#")[0].rstrip("/").lower()

    # Host of the store, for the permissive pass (same-domain check).
    try:
        _base_host = (_urlparse(base).netloc or "").lower()
        if _base_host.startswith("www."):
            _base_host = _base_host[4:]
    except Exception:
        _base_host = ""

    # Product permalinks (from the Store API), so the permissive pass can EXCLUDE
    # product links that share the root-level URL shape of categories.
    _prod_set = set()
    for _pu in (product_urls or []):
        _n = _norm(_urljoin(base, _pu))
        if _n:
            _prod_set.add(_n)

    # Utility / info pages that look like root-level links but aren't collections
    # (cart, account, legal, contact, blog, …) — EN + DE, since many WooCommerce
    # stores are localized. Only consulted in the permissive pass.
    # NOTE: deliberately EXCLUDES product-ambiguous words — "basket"/"bag" (a
    # cart, but also real product categories like /french-baskets, /bags) and bare
    # "gift" (/gifts is a collection; only "gift-card" is utility). "find" is out
    # too (matches jewelry "findings"); German "finden" stays.
    _UTILITY_RE = _re.compile(
        r"(cart|checkout|warenkorb|kasse|account|my-account|mein-konto|"
        r"login|logout|register|signin|sign-in|anmelden|konto|wishlist|wunschliste|"
        r"merkliste|search|suche|contact|kontakt|about|ueber-uns|about-us|faq|help|"
        r"hilfe|support|blog|news|press|presse|career|jobs|impressum|datenschutz|"
        r"privacy|terms|agb|widerruf|shipping|versand|lieferung|returns|retoure|"
        r"payment|zahlung|bezahlung|zahlungsweisen|cookie|sitemap|beratung|pflege|"
        r"reparatur|materialien|haendler|retail|newsletter|gift-card|gutschein|locator|"
        r"finden|accessibility|legal|mentions|disclosure|polic(y|ies)|"
        r"wholesale|affiliate|stockist|refund|imprint|subscribe)"
    )

    # Flipped on for the permissive (fallback) extraction pass; see _build() below.
    _permissive = [False]

    def _clean(s):
        # unescape entities and collapse all whitespace/newlines to single spaces
        return _re.sub(r"\s+", " ", _htmlmod.unescape(str(s or ""))).strip()

    def _is_cat(href):
        if not href:
            return False
        full = _urljoin(base, href)
        h = full.lower()
        # Strict: URLs that structurally encode a category/collection. Covers
        # Shopify (/collections/), WooCommerce (/product-category/), generic /shop/,
        # and Salesforce Commerce Cloud (/c/ category, e.g. /en-us/c/mens/ — used by
        # Under Armour, Columbia, many big brands). "/c/" is a single-letter segment
        # so it won't match inside longer words.
        if (
            "/collections/" in h
            or "/product-category/" in h
            or "/product-cat/" in h
            or "/shop/" in h
            or "/c/" in h
        ):
            return True
        if not _permissive[0]:
            return False
        # Permissive (fallback) pass — used only when the strict pass finds no
        # category links, e.g. WooCommerce stores with root-level permalinks
        # (/braut-bolero/). Treat a nav link as a collection when it's a same-site
        # ROOT-LEVEL page that isn't a product, a file, the homepage, or a known
        # utility/info page.
        try:
            pu = _urlparse(full)
        except Exception:
            return False
        if pu.scheme and pu.scheme not in ("http", "https"):
            return False
        host = (pu.netloc or "").lower()
        if host.startswith("www."):
            host = host[4:]
        if _base_host and host and host != _base_host:
            return False
        path = (pu.path or "").strip("/")
        if not path:
            return False  # homepage
        segs = path.split("/")
        if len(segs) != 1:
            return False  # only single-segment root permalinks
        seg = segs[0]
        if "." in seg:
            return False  # a file (.xml, .php, …)
        if _norm(full) in _prod_set:
            return False  # a product
        if _UTILITY_RE.search(seg):
            return False  # cart/account/legal/etc.
        return True

    try:
        soup = BeautifulSoup(html or "", "html.parser")
    except Exception:
        return [], 0

    # Strip screen-reader-only / hidden text that otherwise pollutes labels
    # (e.g. "<a>Makeup<span class=visually-hidden> collection menu</span></a>").
    for junk in soup.select(".visually-hidden, .sr-only, .visuallyhidden, .screen-reader-text, [aria-hidden=true]"):
        try:
            junk.decompose()
        except Exception:
            pass

    # Candidate nav containers, most-specific first.
    selectors = [
        "header nav", "nav[role=navigation]", "[role=navigation]",
        "#AccessibleNav", ".header__inline-menu", ".site-nav", ".main-menu",
        ".main-navigation", ".primary-menu", ".navmenu", "header ul", "nav",
    ]
    containers = []
    for sel in selectors:
        try:
            containers.extend(soup.select(sel))
        except Exception:
            pass

    # (The primary-<ul> scan lives inside _build() below so it can run under both
    # the strict and permissive passes.)

    # A mega-menu item's submenu may be SEVERAL columns (multiple <ul>s), often
    # wrapped in <div>s rather than a single nested <ul>. Collect every <ul>
    # whose NEAREST <li> ancestor is this li → all its first-level submenu lists.
    def _child_uls(li):
        res = []
        for ul in li.find_all("ul"):
            if ul.find_parent("li") is li:
                res.append(ul)
        return res

    def _own_anchor(li, subuls):
        for a in li.find_all("a", href=True):
            if any(a is su or su in a.parents for su in subuls):
                continue
            return a
        return None

    def _label(el):
        return _clean(el.get_text(" ", strip=True))[:60] if el is not None else ""

    def parse_items(lis, depth):
        items = []
        for li in lis:
            subuls = _child_uls(li)
            own = _own_anchor(li, subuls)
            title = _label(own)
            if not title:
                # Header-only item (icon or non-link label): take the first
                # heading/label NOT inside a submenu — never the whole subtree.
                for el in li.find_all(["a", "span", "button", "summary", "h2", "h3", "h4", "strong"]):
                    if any(el is su or su in el.parents for su in subuls):
                        continue
                    t = _label(el)
                    if t:
                        title = t
                        break
            href = _urljoin(base, own.get("href")) if (own and own.get("href")) else None
            # Icon-only category link (no text): derive a readable label from the
            # handle so it isn't dropped (the canonical title overrides it later).
            if not title and href and _is_cat(href):
                seg = _norm(href).rsplit("/", 1)[-1]
                title = _clean(seg.replace("-", " ")).title()
            children = []
            if depth < 3:
                for su in subuls:
                    children += parse_items(su.find_all("li", recursive=False), depth + 1)
            if title:
                items.append({"title": title, "url": href, "children": children})
        return items

    # Fallback for div/nav-based menus (React/SPA sites like Gymshark) that don't
    # use <ul>/<li>. Find the MENU ROW — the element whose direct children are the
    # several sibling blocks that each contain category links (the top-level items
    # Women/Men/Accessories) — regardless of how deeply it's wrapped. Then each
    # such block is a top-level item and its category anchors are its children.
    def _has_cat(el):
        try:
            return any(_is_cat(a.get("href")) for a in el.find_all("a", href=True))
        except Exception:
            return False

    def _div_fallback():
        from collections import deque
        # Main nav = the container with the most category links.
        root, root_cnt = None, 0
        for cont in containers:
            try:
                c = sum(1 for a in cont.find_all("a", href=True) if _is_cat(a.get("href")))
            except Exception:
                c = 0
            if c > root_cnt:
                root_cnt, root = c, cont
        if not root:
            return [], 0
        # BFS (shallowest first): the top-level menu row is the SHALLOWEST element
        # whose direct children include ≥2 sibling blocks that each carry category
        # links (Women/Men/Accessories) — not the densest deep panel link-list.
        best_row, best_depth, best_n = None, 10 ** 9, 0
        dq = deque([(root, 0)])
        scanned = 0
        while dq and scanned < 5000:
            el, depth = dq.popleft()
            scanned += 1
            if depth > best_depth:
                continue
            kids = [k for k in el.find_all(recursive=False) if getattr(k, "find_all", None)]
            blocks = [k for k in kids if _has_cat(k)]
            if len(blocks) >= 2 and (depth < best_depth or len(blocks) > best_n):
                best_depth, best_n, best_row = depth, len(blocks), el
            for k in kids:
                dq.append((k, depth + 1))
        if not best_row:
            return [], 0

        items = []
        for child in best_row.find_all(recursive=False):
            cat_anchors = [a for a in child.find_all("a", href=True) if _is_cat(a.get("href"))]
            if not cat_anchors:
                continue
            # Top-level label = first short heading/button/link text in the block.
            label = ""
            for el in child.find_all(["button", "summary", "h2", "h3", "h4", "strong", "a", "span"]):
                t = _label(el)
                if t and len(t) <= 32:
                    label = t
                    break
            kids, kseen = [], set()
            for a in cat_anchors:
                u = _urljoin(base, a.get("href"))
                k = _norm(u)
                if k in kseen:
                    continue
                kseen.add(k)
                at = _label(a) or _clean(k.rsplit("/", 1)[-1].replace("-", " ")).title()
                kids.append({"title": at, "url": u, "children": []})
            if not kids:
                continue
            # A single-link block IS that collection (no useful group label).
            if len(kids) == 1 and (not label or label == kids[0]["title"]):
                items.append({"title": kids[0]["title"], "url": kids[0]["url"], "children": []})
            elif label:
                items.append({"title": label, "url": None, "children": kids})
        total = sum(len(it["children"]) or 1 for it in items)
        return items, total

    def _nested_score(t):
        return sum(1 for n in t if n.get("children"))

    # Keep only branches that lead to category links; demote non-category parents
    # to headers (drop their url so they're group labels, not selectable leaves).
    def prune(node):
        node["children"] = [c for c in (prune(ch) for ch in node["children"]) if c]
        self_is_cat = bool(node["url"]) and _is_cat(node["url"])
        if not self_is_cat and not node["children"]:
            return None
        if node["url"] and not self_is_cat:
            node["url"] = None
        return node

    # One extraction pass under the CURRENT _permissive[0] setting, so the same
    # code serves both the strict pass and the permissive fallback. Builds BOTH
    # the <ul> tree and the div/nav tree and keeps whichever nests richer. On SPA
    # sites (Gymshark) the densest <ul> is a mega-menu PANEL while the real top
    # tier (Women/Men/Accessories) lives in <div>s — captured by the div tree.
    def _build():
        best_ul, best_count = None, 0
        seen = set()
        for cont in containers:
            for ul in cont.find_all("ul"):
                if id(ul) in seen or ul.find_parent("ul") is not None:
                    continue
                seen.add(id(ul))
                cnt = sum(1 for a in ul.find_all("a", href=True) if _is_cat(a.get("href")))
                if cnt > best_count:
                    best_count, best_ul = cnt, ul
        tree_ul = parse_items(best_ul.find_all("li", recursive=False), 0) if (best_ul and best_count > 0) else []
        tree_div, div_cnt = _div_fallback()
        if _nested_score(tree_div) > _nested_score(tree_ul):
            tree, cnt = tree_div, (div_cnt or best_count)
        elif tree_ul:
            tree, cnt = tree_ul, best_count
        else:
            tree, cnt = tree_div, (div_cnt or best_count)
        if not tree:
            return [], 0
        return [c for c in (prune(n) for n in tree) if c], cnt

    # Strict pass first — identical behaviour for the many stores whose nav uses
    # /collections/ or /product-category/ links. Only if that finds almost
    # nothing do we retry permissively for root-permalink stores (/braut-bolero/).
    pruned, best_count = _build()
    if best_count < 2:
        _permissive[0] = True
        p2, c2 = _build()
        if c2 > best_count:
            pruned, best_count = p2, c2
        else:
            _permissive[0] = False

    # Flatten to {url, title, path}. path = ancestor group labels (max 3 deep, so
    # deep menus survive as Gender › Category › Sub → an L4 leaf).
    out = []
    added = set()

    def walk(node, ancestors):
        has_children = bool(node["children"])
        child_anc = (ancestors + [node["title"]])[:3] if has_children else ancestors
        if node["url"] and _is_cat(node["url"]):
            path = (child_anc if has_children else ancestors)[:3]
            key = _norm(node["url"])
            if key not in added:
                added.add(key)
                # Prefer the canonical collection title from the catalog.
                leaf_title = title_by_url.get(key) or node["title"]
                out.append({"url": node["url"], "title": leaf_title, "path": path})
        for ch in node["children"]:
            walk(ch, child_anc)

    for n in pruned:
        walk(n, [])

    # Last resort: some builders (Wix, Squarespace, custom SPAs) wrap the menu in
    # non-semantic <div>s that none of our nav containers match, so the structured
    # passes above find nothing. When we'd otherwise return ZERO collections,
    # harvest permissive category links from the WHOLE document as a FLAT list —
    # root-level, same-site, non-product, non-utility links. Utility/legal/product
    # links are filtered out, so what remains is the storefront's real sections.
    if not out:
        _permissive[0] = True
        seen_flat = set()
        for a in soup.find_all("a", href=True):
            if not _is_cat(a.get("href")):
                continue
            full = _urljoin(base, a.get("href"))
            k = _norm(full)
            if not k or k in seen_flat:
                continue
            seen_flat.add(k)
            title = (title_by_url.get(k) or _label(a)
                     or _clean(k.rsplit("/", 1)[-1].replace("-", " ")).title())
            if title:
                out.append({"url": full, "title": title, "path": []})
        best_count = len(out)

    return out, best_count


@app.post("/api/v1/catalog")
def catalog_endpoint(payload: CatalogRequest) -> Dict[str, Any]:
    """Robustly fetch a Shopify store's collections + products (with real TITLES
    and product_type) for onboarding page discovery.

    Onboarding runs in Node, but a plain Node request gets Cloudflare-challenged
    intermittently on protected stores, so titles come and go. Here we fetch the
    JSON through the analyzer's browser-grade path: cloudscraper first (fast),
    then a real browser (Playwright) if that's blocked — the same fallback that
    reliably reads products.json elsewhere. Returns empty lists for non-Shopify
    sites so Node falls back to sitemap/nav discovery.
    """
    import json as _json
    import html as _html
    from urllib.parse import urlparse as _up

    def _clean_title(s):
        return _html.unescape(str(s or "")).strip() or None

    try:
        normalized = normalize_url(payload.url)
        parsed = _up(normalized)
        base = f"{parsed.scheme}://{parsed.netloc}"
        max_products = max(50, min(1000, int(payload.maxProducts or 500)))

        _BROWSER_HEADERS = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json,text/plain,*/*",
        }

        # Shared cloudscraper session (Cloudflare-aware); falls back to requests.
        try:
            import cloudscraper
            _session = cloudscraper.create_scraper(
                browser={"browser": "chrome", "platform": "windows", "mobile": False}
            )
        except Exception:
            import requests as _requests
            _session = _requests

        try:
            from level1_detector.fetcher import fetch_json_with_playwright, fetch_same_origin_json, fetch_shopify_graphql_catalog, fetch_with_expanded_menu
        except Exception:
            fetch_json_with_playwright = None
            fetch_same_origin_json = None
            fetch_shopify_graphql_catalog = None
            fetch_with_expanded_menu = None

        import re as _re_cat
        # Once a BROWSER JSON fetch comes back blocked/empty, stop escalating to
        # Playwright for every subsequent page — otherwise a store that disables or
        # WAF-blocks its JSON endpoints triggers ~10 browser launches (collections ×4
        # + products ×6) at ~12s each and times the whole request out at 120s. One
        # probe is enough to know the endpoint won't answer; then we use the other
        # checkers (sitemap / Storefront GraphQL / rendered nav).
        _pw_blocked = [False]

        def _fetch_json(u):
            # Returns parsed JSON (dict for Shopify, list for the WooCommerce
            # Store API) or None.
            try:
                r = _session.get(u, headers=_BROWSER_HEADERS, timeout=20)
                if getattr(r, "ok", False):
                    data = r.json()
                    if isinstance(data, (dict, list)):
                        return data
            except Exception:
                pass
            if fetch_json_with_playwright and not _pw_blocked[0]:
                try:
                    txt = fetch_json_with_playwright(u)
                    if txt:
                        data = _json.loads(txt)
                        if isinstance(data, (dict, list)):
                            return data
                    _pw_blocked[0] = True  # browser reached it but it isn't JSON → stop retrying
                except Exception:
                    _pw_blocked[0] = True
            return None

        # ── Extra collection checkers (used when the JSON endpoints are blocked) ──
        def _sitemap_collections():
            """Collection URLs from the sitemap — static XML that survives when the
            JSON endpoints are WAF-blocked or disabled."""
            out, seen = [], set()
            for sm in (f"{base}/sitemap_collections_1.xml", f"{base}/sitemap.xml", f"{base}/sitemap_index.xml"):
                try:
                    r = _session.get(sm, headers={"User-Agent": _BROWSER_HEADERS["User-Agent"]}, timeout=15)
                    xml = r.text if getattr(r, "ok", False) else ""
                except Exception:
                    xml = ""
                if not xml:
                    continue
                for m in _re_cat.finditer(r"<loc>\s*([^<\s]+/collections/[^<\s]+?)\s*</loc>", xml, _re_cat.I):
                    u = m.group(1).split("?")[0].split("#")[0]
                    handle = u.rstrip("/").rsplit("/", 1)[-1].lower()
                    if handle in ("collections", "all", "") or handle in seen:
                        continue
                    seen.add(handle)
                    out.append({"url": u, "handle": handle, "title": _clean_title(handle.replace("-", " ").title()), "products_count": None})
                if out:
                    break
            return out

        def _storefront_collections(api_url, token):
            """Shopify Storefront GraphQL — works on stores that block the REST JSON
            but expose a public Storefront token (captured during the homepage render)."""
            if not (api_url and token):
                return []
            query = "{ collections(first: 200) { edges { node { handle title } } } }"
            try:
                r = _session.post(api_url, headers={
                    "Content-Type": "application/json",
                    "X-Shopify-Storefront-Access-Token": token,
                    "User-Agent": _BROWSER_HEADERS["User-Agent"],
                }, json={"query": query}, timeout=20)
                data = r.json() if getattr(r, "ok", False) else {}
            except Exception:
                return []
            edges = (((data or {}).get("data") or {}).get("collections") or {}).get("edges") or []
            out = []
            for e in edges:
                node = (e or {}).get("node") or {}
                h = node.get("handle")
                if h and h != "all":
                    out.append({"url": f"{base}/collections/{h}", "handle": h, "title": _clean_title(node.get("title")), "products_count": None})
            return out

        # `platform` is only set when the evidence is PLATFORM-SPECIFIC (Shopify REST/
        # GraphQL, WooCommerce API). `catalog_source` records HOW we found the catalog
        # (incl. universal methods like sitemap/nav that imply no platform), so recon
        # can display the source without mistaking it for the authoritative platform.
        catalog_source = None
        collections = []
        for page in range(1, 5):
            data = _fetch_json(f"{base}/collections.json?limit=250&page={page}")
            cols = (data or {}).get("collections") or []
            if not cols:
                break
            for c in cols:
                if c.get("products_count") == 0:
                    continue
                if c.get("handle"):
                    collections.append({
                        "url": f"{base}/collections/{c.get('handle')}",
                        "handle": c.get("handle"),
                        "title": _clean_title(c.get("title")),
                        "products_count": c.get("products_count"),
                    })
            if len(cols) < 250:
                break

        products = []
        page = 1
        while len(products) < max_products and page <= 6:
            data = _fetch_json(f"{base}/products.json?limit=250&page={page}")
            prods = (data or {}).get("products") or []
            if not prods:
                break
            for p in prods:
                if len(products) >= max_products:
                    break
                if p.get("handle"):
                    products.append({
                        "url": f"{base}/products/{p.get('handle')}",
                        "handle": p.get("handle"),
                        "title": _clean_title(p.get("title")),
                        "product_type": p.get("product_type"),
                        # vendor = the brand; drives the brand-vs-category split for
                        # collections on multi-brand stores (single-vendor → ignored).
                        "vendor": p.get("vendor"),
                        # tags drive the optional Audience (Men/Women/Kids) level;
                        # products.json returns them as an array.
                        "tags": p.get("tags") or [],
                    })
            if len(prods) < 250:
                break
            page += 1

        platform = "shopify" if (collections or products) else None
        if platform:
            catalog_source = "shopify-rest"

        # ── WooCommerce fallback (Store API) ─────────────────────────────────
        # If it's not Shopify, try WooCommerce's PUBLIC Store API, which gives
        # product names + categories the same way. Category = the grouping bucket
        # (2 levels: Category › item). Returns full permalinks as `url`.
        if not platform:
            def _woo_get(path):
                for prefix in ("/wp-json/wc/store/v1", "/wp-json/wc/store"):
                    data = _fetch_json(f"{base}{prefix}{path}")
                    if isinstance(data, list) and data:
                        return data
                return []

            for c in _woo_get("/products/categories?per_page=100"):
                if (c.get("count") or 0) == 0:
                    continue
                _cu = c.get("permalink") or c.get("link")
                if _cu:
                    collections.append({
                        "url": _cu,
                        "title": _clean_title(c.get("name")),
                        "products_count": c.get("count"),
                    })

            wpage = 1
            while len(products) < max_products and wpage <= 10:
                prods = _woo_get(f"/products?per_page=100&page={wpage}")
                if not prods:
                    break
                for p in prods:
                    if len(products) >= max_products:
                        break
                    if p.get("permalink"):
                        _cats = [_clean_title(cc.get("name"))
                                 for cc in (p.get("categories") or []) if cc.get("name")]
                        _cats = [c for c in _cats if c]
                        products.append({
                            "url": p.get("permalink"),
                            "title": _clean_title(p.get("name")),
                            # Primary category is the type bucket (2-level for Woo).
                            "product_type": _cats[0] if _cats else None,
                            "tags": [],
                        })
                if len(prods) < 100:
                    break
                wpage += 1

            if collections or products:
                platform = "woocommerce"
                catalog_source = "woocommerce"

        # ── Collection recovery #0 (strongest): fetch /collections.json FROM INSIDE
        #    a Cloudflare-cleared browser session. A cold GET is challenged, but an
        #    in-page fetch after the homepage passes the challenge returns the FULL
        #    list (every collection incl. level-2 submenus) with real titles+counts —
        #    which nav-derived (level-1 only) can't. This is the key fix for JS/CF
        #    Shopify stores like stdbeauty.
        if not collections and fetch_same_origin_json:
            try:
                _col_paths = [f"/collections.json?limit=250&page={pg}" for pg in (1, 2, 3)]
                _prod_paths = [f"/products.json?limit=250&page={pg}" for pg in (1, 2, 3)] if not products else []
                _blob = fetch_same_origin_json(base, _col_paths + _prod_paths)
                for _pth in _col_paths:
                    _txt = (_blob or {}).get(_pth)
                    if not _txt:
                        continue
                    try:
                        _data = _json.loads(_txt)
                    except Exception:
                        continue
                    for c in ((_data or {}).get("collections") or []):
                        if c.get("products_count") == 0 or not c.get("handle"):
                            continue
                        collections.append({
                            "url": f"{base}/collections/{c.get('handle')}",
                            "handle": c.get("handle"),
                            "title": _clean_title(c.get("title")),
                            "products_count": c.get("products_count"),
                        })
                for _pth in _prod_paths:
                    _txt = (_blob or {}).get(_pth)
                    if not _txt:
                        continue
                    try:
                        _data = _json.loads(_txt)
                    except Exception:
                        continue
                    for p in ((_data or {}).get("products") or []):
                        if len(products) >= max_products or not p.get("handle"):
                            continue
                        products.append({
                            "url": f"{base}/products/{p.get('handle')}",
                            "handle": p.get("handle"),
                            "title": _clean_title(p.get("title")),
                            "product_type": p.get("product_type"),
                            "vendor": p.get("vendor"),
                            "tags": p.get("tags") or [],
                        })
                if collections:
                    platform = platform or "shopify"
                    catalog_source = catalog_source or "shopify-rest"
                    print(f"🧭 [catalog] recovered {len(collections)} collections + {len(products)} products via in-browser fetch")
            except Exception as _ib:
                print(f"🧭 [catalog] in-browser collections.json failed: {_ib}")

        # ── Collection recovery #0.4 (UNIVERSAL): in-browser SITEMAP crawl. Works on
        #    ANY platform — including custom SPAs that merely mimic Shopify's URL shape
        #    (e.g. stdbeauty) — because a sitemap is a platform-agnostic SEO standard.
        #    Fetched in-page to clear Cloudflare; we follow sitemap-index files and
        #    pull every /collections/ and /products/ URL.
        if not collections and fetch_same_origin_json:
            try:
                _seed_blob = fetch_same_origin_json(base, ["/sitemap.xml", "/sitemap_index.xml", "/robots.txt"])
                _xmls, _subs = [], []
                for _p, _t in (_seed_blob or {}).items():
                    if not _t:
                        continue
                    if _p.endswith("robots.txt"):
                        for _m in _re_cat.finditer(r"(?im)^\s*sitemap:\s*(\S+)", _t):
                            _subs.append(_m.group(1))
                        continue
                    if "<loc" in _t or "<urlset" in _t or "<sitemapindex" in _t:
                        _xmls.append(_t)
                        for _m in _re_cat.finditer(r"<loc>\s*([^<\s]+\.xml[^<\s]*)\s*</loc>", _t, _re_cat.I):
                            _subs.append(_m.group(1))
                # Fetch any sub-sitemaps in-browser too (as origin-relative paths).
                _sub_paths = []
                for _s in _subs:
                    if _s.startswith(base):
                        _sub_paths.append(_s[len(base):] or "/")
                    elif _s.startswith("http"):
                        from urllib.parse import urlparse as _up2
                        _pp2 = _up2(_s)
                        _sub_paths.append((_pp2.path or "/") + (("?" + _pp2.query) if _pp2.query else ""))
                    else:
                        _sub_paths.append(_s if _s.startswith("/") else "/" + _s)
                _sub_paths = list(dict.fromkeys(_sub_paths))[:15]
                if _sub_paths:
                    _sub_blob = fetch_same_origin_json(base, _sub_paths)
                    for _t in (_sub_blob or {}).values():
                        if _t and "<loc" in _t:
                            _xmls.append(_t)
                _cseen, _pseen = set(), set()
                for _xml in _xmls:
                    for _m in _re_cat.finditer(r"<loc>\s*([^<\s]+)\s*</loc>", _xml, _re_cat.I):
                        _u = _m.group(1).split("?")[0].split("#")[0]
                        _low = _u.lower()
                        if "/collections/" in _low or "/collection/" in _low or "/product-category/" in _low or "/category/" in _low:
                            _h = _low.rstrip("/").rsplit("/", 1)[-1]
                            if _h and _h not in ("collections", "collection", "all", "category", "categories") and _h not in _cseen:
                                _cseen.add(_h)
                                collections.append({"url": _u, "handle": _h, "title": _clean_title(_h.replace("-", " ").title()), "products_count": None})
                        elif "/products/" in _low or "/product/" in _low:
                            _h = _low.rstrip("/").rsplit("/", 1)[-1]
                            if _h and _h not in ("products", "product") and _h not in _pseen and len(products) < max_products:
                                _pseen.add(_h)
                                products.append({"url": _u, "handle": _h, "title": None, "product_type": None, "tags": []})
                if collections:
                    catalog_source = catalog_source or "sitemap"
                    print(f"🧭 [catalog] recovered {len(collections)} collections + {len(products)} product URLs via in-browser sitemap")
            except Exception as _sm2:
                print(f"🧭 [catalog] in-browser sitemap failed: {_sm2}")

        # ── Collection recovery #0.5: HEADLESS Shopify (Hydrogen / custom SPA). When
        #    REST returns the app shell, the real catalog is behind the Storefront
        #    GraphQL API. Render the homepage, capture the public Storefront token the
        #    SPA uses, and query GraphQL in-page for the full collections + products.
        if not collections and fetch_shopify_graphql_catalog:
            try:
                _gcat = fetch_shopify_graphql_catalog(base) or {}
                for c in (_gcat.get("collections") or []):
                    h = c.get("handle")
                    if h and h not in ("all", "frontpage"):
                        collections.append({
                            "url": f"{base}/collections/{h}", "handle": h,
                            "title": _clean_title(c.get("title")), "products_count": None,
                        })
                if not products:
                    for p in (_gcat.get("products") or []):
                        if len(products) >= max_products or not p.get("handle"):
                            continue
                        products.append({
                            "url": f"{base}/products/{p.get('handle')}", "handle": p.get("handle"),
                            "title": _clean_title(p.get("title")), "product_type": p.get("productType"),
                            "vendor": p.get("vendor"), "tags": p.get("tags") or [],
                        })
                if collections:
                    platform = platform or "shopify"
                    catalog_source = catalog_source or "shopify-graphql"
                    print(f"🧭 [catalog] recovered {len(collections)} collections + {len(products)} products via Storefront GraphQL (headless)")
            except Exception as _hg:
                print(f"🧭 [catalog] headless GraphQL failed: {_hg}")

        # ── Collection recovery #1: sitemap (cheap, static XML). Runs when the JSON
        #    endpoints returned nothing — blocked, disabled, or non-standard store.
        if not collections:
            _sm = _sitemap_collections()
            if _sm:
                collections = _sm
                catalog_source = catalog_source or "sitemap"
                print(f"🧭 [catalog] recovered {len(collections)} collections from sitemap")

        # ── Navigation menu (collections exactly as shown to shoppers) ────────
        # Fetch the homepage and parse its nav. Try cloudscraper first (fast, and
        # many themes server-render the full menu incl. hidden submenus). Escalate
        # to a real browser render when the menu looks incomplete — few links OR
        # no nesting at all, which usually means the submenu panels are JS-built
        # (mega-menus). Prefer canonical collection titles for the leaves.
        menu = []
        render_headers = {}
        rendered_html = ""
        home_html = None
        try:
            title_by_url = {}
            for c in collections:
                cu, ct = c.get("url"), c.get("title")
                if cu and ct:
                    title_by_url[cu.split("?")[0].split("#")[0].rstrip("/").lower()] = ct

            # Product permalinks — the permissive nav pass uses these to EXCLUDE
            # product links (which share the root-level shape of categories on
            # stores with custom permalinks).
            _prod_urls = [p.get("url") for p in products if p.get("url")]

            home_html = None
            try:
                r = _session.get(base, headers=_BROWSER_HEADERS, timeout=15)
                if getattr(r, "ok", False):
                    home_html = r.text
            except Exception:
                home_html = None

            menu, mcount = _extract_nav_menu(base, home_html or "", title_by_url, _prod_urls)
            nested = any(m.get("path") for m in menu)
            print(f"🧭 [menu] cloudscraper: htmlLen={len(home_html or '')} catLinks={mcount} entries={len(menu)} nested={nested}")
            # Render when the menu looks incomplete OR nesting is missing. We use the
            # EXPANDED-menu render (hovers nav items + fires mouseover) so mega-menu
            # dropdown/level-2 category links enter the DOM — a plain render captures
            # only the top level (e.g. stdbeauty showed 4 of 12).
            if mcount < 2 or not nested or (len(menu) < len(collections)):
                try:
                    rendered = fetch_with_expanded_menu(base) if fetch_with_expanded_menu else None
                    if not rendered:
                        rendered, _ru, _rh = website_main.fetch_with_playwright(base)
                        render_headers = _rh or {}
                    rendered_html = rendered or rendered_html
                    if rendered:
                        menu2, mcount2 = _extract_nav_menu(base, rendered, title_by_url, _prod_urls)
                        nested2 = any(m.get("path") for m in menu2)
                        print(f"🧭 [menu] expanded render: htmlLen={len(rendered)} catLinks={mcount2} entries={len(menu2)} nested={nested2}")
                        # Take the richer result (more links, or now-nested).
                        if len(menu2) > len(menu) or (nested2 and not nested):
                            menu, mcount = menu2, mcount2
                except Exception as _me:
                    print(f"🧭 [menu] expanded render failed: {_me}")
            print(f"🧭 [menu] final entries={len(menu)} sample={[m.get('title') for m in menu[:6]]}")
        except Exception as _menu_exc:
            print(f"🧭 [menu] error: {_menu_exc}")
            menu = []

        # ── Collection recovery #2: Shopify Storefront GraphQL, using the public
        #    token captured during the render above. Then, as a last resort, derive
        #    collections from the rendered nav menu itself.
        if not collections:
            _tok = (render_headers or {}).get("shopify_storefront_token")
            _api = (render_headers or {}).get("shopify_storefront_api_url")
            _gq = _storefront_collections(_api, _tok)
            if _gq:
                collections = _gq
                platform = platform or "shopify"
                catalog_source = catalog_source or "shopify-graphql"
                print(f"🧭 [catalog] recovered {len(collections)} collections via Storefront GraphQL")
        if not collections and menu:
            _seen = set()
            for m in menu:
                _mu = m.get("url") or m.get("href") or ""
                if "/collections/" in str(_mu).lower():
                    _h = str(_mu).split("?")[0].rstrip("/").rsplit("/", 1)[-1].lower()
                    if _h and _h not in ("collections", "all") and _h not in _seen:
                        _seen.add(_h)
                        collections.append({"url": _mu, "handle": _h, "title": m.get("title") or _clean_title(_h.replace("-", " ").title()), "products_count": None})
            if collections:
                catalog_source = catalog_source or "nav"
                print(f"🧭 [catalog] derived {len(collections)} collections from rendered nav")

        # ── Liveness pass: which catalog collections are LIVE on the site ──────
        # "In their menu" must mean categories actually surfaced in the store's
        # live navigation — NOT every collection in the backend (which includes
        # discontinued / test / hidden ones). The structured menu parse above
        # nests them where it can, but it misses custom SPAs whose nav is
        # non-semantic markup. So we ALSO harvest the rendered nav-chrome links
        # and mark any known collection linked there as live — a structure-
        # agnostic signal that works even when the menu tree can't be rebuilt.
        try:
            _menu_norm = set()
            for _m in menu:
                _mu = _m.get("url")
                if _mu:
                    _menu_norm.add(_mu.split("?")[0].split("#")[0].rstrip("/").lower())

            # Prefer the expanded/rendered HTML; fall back to the cloudscraper
            # homepage. On an SPA the cloudscraper HTML has no nav, so if the menu
            # parse never rendered AND many collections are still unlinked, do one
            # expanded render now purely for the harvest.
            _harvest_html = rendered_html or home_html or ""
            _unlinked = [c for c in collections if c.get("url") and
                         c["url"].split("?")[0].split("#")[0].rstrip("/").lower() not in _menu_norm]
            if (not rendered_html) and _unlinked and len(_unlinked) > max(3, len(collections) // 2):
                try:
                    _r = fetch_with_expanded_menu(base) if fetch_with_expanded_menu else None
                    if not _r:
                        _r, _ru, _rh = website_main.fetch_with_playwright(base)
                    if _r:
                        _harvest_html = _r
                        print(f"🧭 [live] rendered homepage for liveness harvest (htmlLen={len(_r)})")
                except Exception as _re2:
                    print(f"🧭 [live] harvest render failed: {_re2}")

            live_urls, live_slugs = _harvest_live_nav_links(base, _harvest_html)
            print(f"🧭 [live] nav-chrome links: urls={len(live_urls)} slugs={len(live_slugs)}")

            def _cslug(u):
                try:
                    segs = (u or "").split("?")[0].split("#")[0].rstrip("/").lower().split("/")
                    return segs[-1] if segs and segs[-1] else ""
                except Exception:
                    return ""

            _added = 0
            for c in collections:
                cu = c.get("url")
                if not cu:
                    continue
                n = cu.split("?")[0].split("#")[0].rstrip("/").lower()
                if n in _menu_norm:
                    continue  # already surfaced via the structured menu parse
                handle = str(c.get("handle") or "").lower()
                # Live = linked anywhere in the nav chrome (by URL or slug)…
                is_live = (n in live_urls) or (handle and handle in live_slugs) or (_cslug(cu) in live_slugs)
                if not is_live:
                    continue
                # …and not an empty/discontinued category (cheap "non-empty" check;
                # products_count is already known, so no extra fetch). Unknown
                # counts (None) are kept — we only drop confirmed-empty ones.
                if c.get("products_count") == 0:
                    continue
                title = c.get("title") or _clean_title(handle.replace("-", " ").title()) or handle
                menu.append({"url": cu, "title": title, "path": [title], "liveSource": "chrome"})
                _menu_norm.add(n)
                _added += 1
            if _added:
                print(f"🧭 [live] marked {_added} extra catalog collections as live via nav-chrome harvest")
            print(f"🧭 [live] total live/in-menu entries={len(menu)} of {len(collections)} catalog collections")
        except Exception as _live_exc:
            print(f"🧭 [live] liveness pass error: {_live_exc}")

        return {
            "success": True,
            "base": base,
            "platform": platform,
            "catalogSource": catalog_source,
            "isShopify": platform == "shopify",
            "collections": collections,
            "products": products,
            "menu": menu,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail={
            "success": False,
            "message": "Catalog fetch failed.",
            "error": str(exc),
        })


@app.post("/api/v1/analyze-pages")
def analyze_pages(payload: AnalyzePagesRequest) -> Dict[str, Any]:
    results = []

    for url in payload.urls:
        try:
            results.append({
                "url": normalize_url(url),
                "success": True,
                "data": analyze_one_url(url),
            })
        except Exception as exc:
            item = {"url": url, "success": False, "error": str(exc)}
            if not payload.continueOnError:
                raise HTTPException(status_code=500, detail={
                    "success": False,
                    "message": "Batch analysis stopped because one URL failed.",
                    "failed": item,
                    "results": results,
                })
            results.append(item)

    return {
        "success": True,
        "count": len(results),
        "results": results,
    }


@app.post("/api/v1/merge-site")
def merge_site(payload: MergeSiteRequest) -> Dict[str, Any]:
    try:
        return merge_page_jsons(payload.pages)
    except Exception as exc:
        raise HTTPException(status_code=500, detail={
            "success": False,
            "message": "Site merge failed.",
            "error": str(exc),
        })


@app.post("/api/v1/compare-sites")
def compare_sites_endpoint(payload: CompareSitesRequest) -> Dict[str, Any]:
    try:
        result = compare_sites(payload.userWebsite, payload.competitors)
        return apply_output_options(result, payload.options)
    except Exception as exc:
        raise HTTPException(status_code=500, detail={
            "success": False,
            "message": "Comparison failed.",
            "error": str(exc),
        })


@app.post("/api/v1/compare-one")
def compare_one_endpoint(payload: CompareOneRequest) -> Dict[str, Any]:
    try:
        result = compare_sites(payload.userWebsite, [payload.competitorWebsite])
        return apply_output_options(result, payload.options)
    except Exception as exc:
        raise HTTPException(status_code=500, detail={
            "success": False,
            "message": "Comparison failed.",
            "error": str(exc),
        })




@app.post("/api/v1/build-ai-payload")
def build_ai_payload_endpoint(payload: BuildAiPayloadRequest) -> Dict[str, Any]:
    """Convert full comparison JSON into compact AI-ready JSON.

    React should call this after /api/v1/compare-sites if it wants to send
    a smaller, safer payload to OpenAI.
    """
    try:
        return build_ai_payload_for_api(payload.comparison, payload.options)
    except Exception as exc:
        raise HTTPException(status_code=500, detail={
            "success": False,
            "message": "AI payload build failed.",
            "error": str(exc),
        })


@app.post("/api/v1/openai-insights-request")
def openai_insights_request_endpoint(payload: OpenAiInsightsRequest) -> Dict[str, Any]:
    """Build a COMPLETE OpenAI chat request (system prompt + evidence payload +
    strict json_schema response format) from a comparison JSON.

    React/backend can POST the returned `openaiRequest` object directly to
    OpenAI with its own API key, or call /api/v1/generate-insights instead.
    """
    try:
        return openai_insights_module.build_openai_insights_request(
            payload.comparison, payload.options.model_dump()
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail={
            "success": False,
            "message": "OpenAI insights request build failed.",
            "error": str(exc),
        })


@app.post("/api/v1/generate-insights")
def generate_insights_endpoint(payload: GenerateInsightsRequest) -> Dict[str, Any]:
    """Build the AI request and call the configured provider server-side.

    Provider is chosen by (in order): request option `provider`, then the
    AI_PROVIDER env var, defaulting to "openai". "claude" uses ANTHROPIC_API_KEY;
    "openai" uses OPENAI_API_KEY. Returns ci_insights_v1 JSON plus token usage —
    identical shape for both providers so the dashboard is unaffected.
    """
    try:
        _opts = payload.options.model_dump()
        _provider = (
            _opts.get("provider")
            or _os.environ.get("AI_PROVIDER")
            or "openai"
        ).strip().lower()

        if _provider == "claude":
            request = claude_insights_module.build_claude_insights_request(
                payload.comparison, _opts
            )
            outcome = claude_insights_module.call_claude(request)
        else:
            request = openai_insights_module.build_openai_insights_request(
                payload.comparison, _opts
            )
            outcome = openai_insights_module.call_openai(request)

        outcome.setdefault("provider", _provider)
        validation = openai_insights_module.validate_insights(outcome["insights"])
        outcome["validation"] = validation
        print(f"🧠 [insights] provider={_provider} model={outcome.get('model')} tokens={outcome.get('usage')}")
        return outcome
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail={
            "success": False,
            "message": str(exc),
        })
    except Exception as exc:
        raise HTTPException(status_code=500, detail={
            "success": False,
            "message": "Insight generation failed.",
            "error": str(exc),
        })


@app.post("/api/v1/compare-sites-ai-payload")
def compare_sites_ai_payload_endpoint(payload: CompareSitesRequest) -> Dict[str, Any]:
    """Compare websites and return compact AI payload in one call.

    Use this when React does not need the full comparison JSON first.
    """
    try:
        comparison = apply_output_options(
            compare_sites(payload.userWebsite, payload.competitors),
            payload.options,
        )
        ai_payload_response = build_ai_payload_for_api(
            comparison,
            BuildAiPayloadOptions(includeStats=True),
        )
        return {
            "success": True,
            "comparison": comparison,
            "aiPayload": ai_payload_response["data"],
            "stats": ai_payload_response.get("stats"),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail={
            "success": False,
            "message": "Comparison AI payload failed.",
            "error": str(exc),
        })


@app.post("/api/v1/compare-one-ai-payload")
def compare_one_ai_payload_endpoint(payload: CompareOneRequest) -> Dict[str, Any]:
    """Compare one competitor against user site and return compact AI payload."""
    try:
        comparison = apply_output_options(
            compare_sites(payload.userWebsite, [payload.competitorWebsite]),
            payload.options,
        )
        ai_payload_response = build_ai_payload_for_api(
            comparison,
            BuildAiPayloadOptions(includeStats=True),
        )
        return {
            "success": True,
            "comparison": comparison,
            "aiPayload": ai_payload_response["data"],
            "stats": ai_payload_response.get("stats"),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail={
            "success": False,
            "message": "Single competitor AI payload failed.",
            "error": str(exc),
        })


@app.post("/api/v1/diff-snapshots")
def diff_snapshots_endpoint(payload: DiffSnapshotsRequest) -> Dict[str, Any]:
    """Same-site change detection (change_detection_app).

    Compares two merged snapshots of the SAME site over time: products added/
    removed, price and sale changes, stock, rank, collections, SaaS pricing
    plans, navigation, homepage messaging. Returns changeScore + shouldSendToAI.
    """
    try:
        return change_detector_module.detect_changes(
            payload.previousSnapshot, payload.currentSnapshot, payload.settings
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail={
            "success": False,
            "message": "Snapshot change detection failed.",
            "error": str(exc),
        })


@app.post("/api/v1/diff-comparisons")
def diff_comparisons_endpoint(payload: DiffComparisonsRequest) -> Dict[str, Any]:
    try:
        return diff_comparisons(payload.previousComparison, payload.currentComparison, payload.settings)
    except Exception as exc:
        raise HTTPException(status_code=500, detail={
            "success": False,
            "message": "Comparison diff failed.",
            "error": str(exc),
        })


@app.post("/api/v1/full-run")
def full_run(payload: FullRunRequest) -> Dict[str, Any]:
    """
    End-to-end testing endpoint.

    React sends URLs only. API returns analyzed pages, merged snapshots,
    comparison output, and optional weekly diff gate.
    """
    user_analysis = analyze_pages(AnalyzePagesRequest(
        urls=payload.userPages,
        continueOnError=payload.continueOnError,
    ))
    competitor_analysis = analyze_pages(AnalyzePagesRequest(
        urls=payload.competitorPages,
        continueOnError=payload.continueOnError,
    ))

    user_pages_json = [item["data"] for item in user_analysis["results"] if item.get("success")]
    competitor_pages_json = [item["data"] for item in competitor_analysis["results"] if item.get("success")]

    if not user_pages_json:
        raise HTTPException(status_code=400, detail="No user pages were successfully analyzed.")
    if not competitor_pages_json:
        raise HTTPException(status_code=400, detail="No competitor pages were successfully analyzed.")

    user_snapshot = merge_page_jsons(user_pages_json)
    competitor_snapshot = merge_page_jsons(competitor_pages_json)

    comparison = apply_output_options(
        compare_sites(user_snapshot, [competitor_snapshot]),
        payload.compareOptions,
    )

    diff_result = None
    if payload.previousComparison:
        diff_result = diff_comparisons(payload.previousComparison, comparison, payload.diffSettings)

    ai_payload_response = None
    if payload.includeAiPayload:
        ai_payload_response = build_ai_payload_for_api(comparison, payload.aiPayloadOptions)

    response = {
        "success": True,
        "userAnalysis": user_analysis,
        "competitorAnalysis": competitor_analysis,
        "userWebsite": user_snapshot,
        "competitorWebsite": competitor_snapshot,
        "comparison": comparison,
        "weeklyDiff": diff_result,
    }

    if ai_payload_response:
        response["aiPayload"] = ai_payload_response["data"]
        response["aiPayloadStats"] = ai_payload_response.get("stats")

    return response


@app.post("/api/v1/full-run-multi")
def full_run_multi(payload: FullRunMultiRequest) -> Dict[str, Any]:
    """
    End-to-end run for one workspace against N competitors.

    Analyses the workspace pages ONCE and reuses that snapshot for every
    competitor, then compares them together so the output carries a real
    multi-competitor landscape rather than N disconnected one-to-one runs.

    A competitor that fails to analyse does not abort the run when
    continueOnError is set - it is reported in `failedCompetitors` and the
    remaining competitors still produce a comparison. Partial results beat a
    spinner that never resolves.
    """
    user_analysis = analyze_pages(AnalyzePagesRequest(
        urls=payload.userPages,
        continueOnError=payload.continueOnError,
    ))

    user_pages_json = [item["data"] for item in user_analysis["results"] if item.get("success")]
    if not user_pages_json:
        raise HTTPException(status_code=400, detail="No user pages were successfully analyzed.")

    user_snapshot = merge_page_jsons(user_pages_json)

    competitor_snapshots: List[Dict[str, Any]] = []
    competitor_details: List[Dict[str, Any]] = []
    failed_competitors: List[Dict[str, Any]] = []

    for competitor in payload.competitors:
        try:
            analysis = analyze_pages(AnalyzePagesRequest(
                urls=competitor.pages,
                continueOnError=payload.continueOnError,
            ))
            pages_json = [item["data"] for item in analysis["results"] if item.get("success")]

            if not pages_json:
                raise ValueError("No pages for this competitor were successfully analyzed.")

            snapshot = merge_page_jsons(pages_json)

            # Carry identity through the merge so downstream comparison and
            # reporting can tell the competitors apart.
            snapshot.setdefault("siteName", competitor.name)
            snapshot.setdefault("siteUrl", competitor.url)

            competitor_snapshots.append(snapshot)

            # Pages the user explicitly declared this competitor does not have.
            # A reportable gap, not an omission.
            gaps = [
                pair.workspaceUrl
                for pair in competitor.pagePairs
                if pair.status == "no_equivalent"
            ]

            competitor_details.append({
                "name": competitor.name,
                "url": competitor.url,
                "analysis": analysis,
                "snapshot": snapshot,
                "pagePairs": [pair.model_dump() for pair in competitor.pagePairs],
                "missingPages": gaps,
                "pagesAnalyzed": len(pages_json),
                "pagesRequested": len(competitor.pages),
            })

        except Exception as exc:  # noqa: BLE001 - reported, not swallowed
            failure = {
                "name": competitor.name,
                "url": competitor.url,
                "error": str(exc),
            }
            if not payload.continueOnError:
                raise HTTPException(status_code=502, detail={
                    "success": False,
                    "message": f"Competitor '{competitor.name}' failed to analyze.",
                    **failure,
                })
            failed_competitors.append(failure)

    if not competitor_snapshots:
        raise HTTPException(status_code=400, detail={
            "success": False,
            "message": "No competitors were successfully analyzed.",
            "failedCompetitors": failed_competitors,
        })

    comparison = apply_output_options(
        compare_sites(user_snapshot, competitor_snapshots),
        payload.compareOptions,
    )

    diff_result = None
    if payload.previousComparison:
        diff_result = diff_comparisons(payload.previousComparison, comparison, payload.diffSettings)

    ai_payload_response = None
    if payload.includeAiPayload:
        ai_payload_response = build_ai_payload_for_api(comparison, payload.aiPayloadOptions)

    response = {
        "success": True,
        "userAnalysis": user_analysis,
        "userWebsite": user_snapshot,
        "competitors": competitor_details,
        "competitorWebsites": competitor_snapshots,
        "comparison": comparison,
        "weeklyDiff": diff_result,
        "failedCompetitors": failed_competitors,
        "stats": {
            "competitorsRequested": len(payload.competitors),
            "competitorsAnalyzed": len(competitor_snapshots),
            "competitorsFailed": len(failed_competitors),
        },
    }

    if ai_payload_response:
        response["aiPayload"] = ai_payload_response["data"]
        response["aiPayloadStats"] = ai_payload_response.get("stats")

    return response
