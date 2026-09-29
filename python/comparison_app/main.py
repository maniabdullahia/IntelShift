from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ConfigDict

from comparison_engine.comparator import compare_sites


app = FastAPI(
    title="Competitor Comparison Engine API",
    version="5.0.0",
    description="JSON-in / JSON-out API for React apps. Compares one user website snapshot against one or more competitor snapshots.",
)

# API-key auth + rate limiting (see api_security.py; env: COMPINTEL_API_KEY,
# RATE_LIMIT_PER_MINUTE, HEAVY_RATE_LIMIT_PER_MINUTE). Installed BEFORE CORS
# so 401/429 responses also carry CORS headers.
from api_security import install_security
install_security(app, service_name="comparison-api")

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


class CompareOptions(BaseModel):
    model_config = ConfigDict(extra="allow")

    includeOpenAiEvidencePack: bool = Field(default=True)
    includeProductDetails: bool = Field(default=True)
    includePageContent: bool = Field(default=True)
    includeSectionDetails: bool = Field(default=True)
    includeOneToOneComparison: bool = Field(default=True)
    maxProductsPerSite: Optional[int] = Field(default=None, description="Optional display/output limiter. None means no app-level trim.")
    maxSectionsPerSite: Optional[int] = Field(default=None, description="Optional display/output limiter. None means no app-level trim.")


class CompareRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    userWebsite: Dict[str, Any] = Field(..., description="Merged JSON snapshot of the user's website")
    competitors: List[Dict[str, Any]] = Field(default_factory=list, description="List of merged JSON competitor snapshots")
    options: CompareOptions = Field(default_factory=CompareOptions)


class QuickCompareRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    userWebsite: Dict[str, Any]
    competitorWebsite: Dict[str, Any]
    options: CompareOptions = Field(default_factory=CompareOptions)


@app.get("/")
def root() -> Dict[str, Any]:
    return {
        "name": "Competitor Comparison Engine API",
        "version": "5.0.0",
        "status": "running",
        "mode": "json_in_json_out",
        "endpoints": {
            "health": "GET /health",
            "schema": "GET /schema/example-request",
            "compare": "POST /api/compare",
            "compareOne": "POST /api/compare-one",
        },
    }


@app.get("/health")
def health() -> Dict[str, Any]:
    return {"ok": True, "service": "comparison-engine", "version": "5.0.0"}


@app.get("/schema/example-request")
def example_request() -> Dict[str, Any]:
    return {
        "userWebsite": {
            "schemaVersion": "site_snapshot_v1",
            "site": {
                "domain": "example-user.com",
                "platform": "Shopify",
                "pagesAnalyzedCount": 3,
            },
            "pagesAnalyzed": [],
            "products": [],
        },
        "competitors": [
            {
                "schemaVersion": "site_snapshot_v1",
                "site": {
                    "domain": "example-competitor.com",
                    "platform": "Shopify",
                    "pagesAnalyzedCount": 3,
                },
                "pagesAnalyzed": [],
                "products": [],
            }
        ],
        "options": {
            "includeOpenAiEvidencePack": True,
            "includeProductDetails": True,
            "includePageContent": True,
            "includeSectionDetails": True,
            "includeOneToOneComparison": True,
            "maxProductsPerSite": None,
            "maxSectionsPerSite": None,
        },
    }


@app.post("/api/compare")
def compare_json(payload: CompareRequest) -> Dict[str, Any]:
    """
    Main React endpoint.

    Input: JSON body with userWebsite + competitors[]
    Output: comparison JSON
    """
    try:
        result = compare_sites(payload.userWebsite, payload.competitors)
        return apply_output_options(result, payload.options)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/compare-one")
def compare_one_json(payload: QuickCompareRequest) -> Dict[str, Any]:
    """
    Convenience endpoint for 1 user website vs 1 competitor website.
    """
    try:
        result = compare_sites(payload.userWebsite, [payload.competitorWebsite])
        return apply_output_options(result, payload.options)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Backward-compatible alias for older tests.
@app.post("/compare")
def compare_legacy(payload: CompareRequest) -> Dict[str, Any]:
    try:
        result = compare_sites(payload.userWebsite, payload.competitors)
        return apply_output_options(result, payload.options)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def apply_output_options(result: Dict[str, Any], options: CompareOptions) -> Dict[str, Any]:
    """
    Keeps the API flexible for React.
    You can request a smaller response for dashboard views, or full response for AI processing.
    """
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
        pages = site.get("pages") or []
        for page in pages:
            sections = page.get("sections") or []
            page["sections"] = sections[:limit]
            page["sectionsTrimmed"] = len(sections) > limit
