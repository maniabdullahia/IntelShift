"""OpenAI Insights Request Builder (openai_insights_v1).

Turns a comparison_engine_v5 output into a COMPLETE, ready-to-send OpenAI
request for narrative competitor insights:

  - system prompt  (competitive analyst persona + hard evidence rules)
  - user message   (compact deterministic evidence payload, ai_payload_v4)
  - response_format json_schema (STRICT - OpenAI structured outputs), so the
    model can only return valid `ci_insights_v1` JSON your React dashboard
    can render directly.

Usage (CLI):
    python openai_insights.py comparison_output.json            # writes *_openai_request.json
    python openai_insights.py comparison_output.json --call     # also calls OpenAI (needs OPENAI_API_KEY)

Usage (code / API):
    from openai_insights import build_openai_insights_request, call_openai
    request = build_openai_insights_request(comparison)
    insights = call_openai(request)   # optional; or send request yourself
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from build_ai_payload import build_ai_payload

SCHEMA_VERSION = "openai_insights_v1"
DEFAULT_MODEL = "gpt-4o"          # override via options or OPENAI_MODEL env
DEFAULT_TEMPERATURE = 0.2          # low: analysis, not creativity
DEFAULT_MAX_OUTPUT_TOKENS = 4096


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a senior competitive-intelligence analyst for ecommerce, SaaS and service businesses.

You receive ONE JSON evidence payload produced by a deterministic comparison engine. It compares the USER's website against COMPETITOR websites using only pages that were actually analyzed.

HARD RULES - never break these:
1. Use ONLY facts present in the evidence payload. Never invent products, prices, categories, pages, plans, percentages or features.
2. Every insight must cite evidence: set "evidencePath" to the JSON path of the data you used (e.g. "modules.categoryCoverage.userGapCategories" or "matchEvidence.oneToOneSummary[0].collectionMatchups[0]").
3. If modules.price.sameCurrency is false, NEVER compare absolute prices across sites; only discuss relative signals (assortment, promotions, content) and mention the currency limitation in dataNotes.
4. The snapshot covers only the analyzed pages, not the whole store. Phrase findings as "in the analyzed pages" where scope matters, and never claim a competitor lacks something entirely.
5. Respect siteContext.userSiteType: for ecommerce lead with categories, products, prices, promotions and stock; for saas lead with pricing pages and plans; for business/services lead with service coverage and CTAs.
6. Do not mention schema names, JSON structure, or that you received a payload. Write for a business owner.
7. If evidence for a section is missing or empty, return an empty array for it - never pad with generic advice.
8. Write in clear, direct business English. Every insight must answer: what is true, why it matters, what to do.

VERIFY BEFORE YOU ASSERT (this is why you exist, not just to summarize):
9. Sanity-check the deterministic numbers for internal contradictions or signs of a bad fetch BEFORE building insights on them. Red flags: every product in a collection showing the exact same price, a collection reported ~100% out of stock, product counts that don't reconcile across modules, a price of 0 or a suspiciously round placeholder, or a homepage with zero CTAs/hero on a real store. When a signal looks unreliable, do NOT build a confident insight on it - instead raise a "data_quality" insight naming exactly what to re-check, and lower the impactScore of anything that depends on it.
10. COMPARE TERMINOLOGY, not just quantities. Examine the navigation labels and the collection/category names on each side. When the two sites use DIFFERENT words for the same thing (e.g. one calls a range "Luxury Pret" and the other "Elara"; one navigates by "Dresses", the other by "Pret"), surface it as a navigation / positioning / seo insight: different wording changes what shoppers search for, how they browse, and which store ranks. Recommend adopting the stronger naming for discovery where the evidence supports it.
11. ADD MEANING - connect signals across modules. Where the evidence supports it, fuse related facts (price + assortment + terminology + stock) into one sharper, action-oriented insight a business owner would act on, rather than restating each number in isolation. You are an analyst, not a table formatter.

You must respond with JSON that exactly matches the provided response schema."""


# ---------------------------------------------------------------------------
# Strict output schema (OpenAI structured outputs - response_format json_schema)
# ---------------------------------------------------------------------------

SEVERITY = {"type": "string", "enum": ["low", "medium", "high", "critical"]}
PRIORITY = {"type": "string", "enum": ["P1", "P2", "P3"]}

INSIGHT_ITEM = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "title": {"type": "string", "description": "Short, specific headline of the finding."},
        "severity": SEVERITY,
        "area": {
            "type": "string",
            "enum": ["pricing", "assortment", "promotions", "product_content", "homepage",
                     "navigation", "seo", "trust_conversion", "inventory", "positioning",
                     "saas_pricing", "services", "data_quality"],
        },
        "finding": {"type": "string", "description": "What is factually true, with the numbers from the evidence."},
        "whyItMatters": {"type": "string"},
        "recommendedAction": {"type": "string"},
        "evidencePath": {"type": "string"},
        "competitorDomain": {"type": ["string", "null"]},
        "impactScore": {"type": "integer", "minimum": 0, "maximum": 100},
    },
    "required": ["title", "severity", "area", "finding", "whyItMatters",
                 "recommendedAction", "evidencePath", "competitorDomain", "impactScore"],
}

DASHBOARD_CARD = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "moduleKey": {
            "type": "string",
            "enum": ["priceComparison", "categoryCoverageComparison", "oneToOneComparison",
                     "saleAndDiscountComparison", "contentDepthComparison", "homepageComparison",
                     "navigationComparison", "seoComparison", "inventoryComparison",
                     "trustAndConversionComparison", "pricingPageComparison", "servicesComparison"],
        },
        "title": {"type": "string"},
        "headlineMetric": {"type": "string", "description": "The single number/fact to display large, e.g. '+15% median price gap'."},
        "shortText": {"type": "string", "description": "One or two sentences for the card body."},
        "severity": SEVERITY,
        "evidencePath": {"type": "string"},
    },
    "required": ["moduleKey", "title", "headlineMetric", "shortText", "severity", "evidencePath"],
}

RECOMMENDED_ACTION = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "action": {"type": "string"},
        "priority": PRIORITY,
        "area": {"type": "string"},
        "expectedImpact": {"type": "string"},
        "successMetric": {"type": "string"},
        "evidencePath": {"type": "string"},
    },
    "required": ["action", "priority", "area", "expectedImpact", "successMetric", "evidencePath"],
}

COMPETITOR_PROFILE = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "domain": {"type": "string"},
        "overallThreatLevel": SEVERITY,
        "strengthsVsUser": {"type": "array", "items": {"type": "string"}},
        "weaknessesVsUser": {"type": "array", "items": {"type": "string"}},
        "pricePositioningVsUser": {
            "type": "string",
            "enum": ["cheaper", "similar", "more_expensive", "mixed", "not_comparable"],
        },
        "summary": {"type": "string"},
    },
    "required": ["domain", "overallThreatLevel", "strengthsVsUser", "weaknessesVsUser",
                 "pricePositioningVsUser", "summary"],
}

RESPONSE_JSON_SCHEMA: Dict[str, Any] = {
    "name": "ci_insights_v1",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "schemaVersion": {"type": "string", "enum": ["ci_insights_v1"]},
            "executiveSummary": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "overallFinding": {"type": "string", "description": "3-5 sentence plain-language verdict."},
                    "userCompetitivePosition": {
                        "type": "string",
                        "enum": ["leading", "competitive", "at_risk", "behind", "insufficient_data"],
                    },
                    "topRisks": {"type": "array", "items": {"type": "string"}, "description": "Max 3."},
                    "topOpportunities": {"type": "array", "items": {"type": "string"}, "description": "Max 3."},
                },
                "required": ["overallFinding", "userCompetitivePosition", "topRisks", "topOpportunities"],
            },
            "competitorProfiles": {"type": "array", "items": COMPETITOR_PROFILE},
            "insights": {"type": "array", "items": INSIGHT_ITEM, "description": "Ordered by impactScore desc. Max 12."},
            "dashboardCards": {"type": "array", "items": DASHBOARD_CARD, "description": "Max 8, only for modules with evidence."},
            "recommendedActions": {"type": "array", "items": RECOMMENDED_ACTION, "description": "Max 8, ordered by priority."},
            "dataNotes": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Scope/quality caveats: analyzed-pages-only, currency mismatch, low availability coverage, etc.",
            },
        },
        "required": ["schemaVersion", "executiveSummary", "competitorProfiles",
                     "insights", "dashboardCards", "recommendedActions", "dataNotes"],
    },
}


# ---------------------------------------------------------------------------
# Request builder
# ---------------------------------------------------------------------------

def build_openai_insights_request(
    comparison: Dict[str, Any],
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a complete OpenAI Chat Completions request for competitor insights.

    `comparison` is the full output of the comparison engine (v4 or v5).
    Returns a dict you can POST to https://api.openai.com/v1/chat/completions
    as-is (after adding your Authorization header), or pass to call_openai().
    """
    options = options or {}
    payload = build_ai_payload(comparison, options.get("payloadOptions"))

    model = options.get("model") or os.environ.get("OPENAI_MODEL") or DEFAULT_MODEL

    # Optional business context supplied by the app (industry + the user's chosen
    # competitor set). Frames relevance and tailors recommendations, but must not
    # override the evidence-only rules above.
    ctx = comparison.get("businessContext") or {}
    ctx_lines = []
    if ctx.get("industry"):
        ctx_lines.append(f"- Industry / sector: {ctx['industry']}")
    if ctx.get("userDomain"):
        ctx_lines.append(f"- The USER's site: {ctx['userDomain']}")
    if ctx.get("competitorDomain"):
        ctx_lines.append(f"- Competitor being compared: {ctx['competitorDomain']}")
    if ctx.get("competitorSet"):
        tracked = ", ".join(str(d) for d in ctx["competitorSet"] if d)
        if tracked:
            ctx_lines.append(f"- The user deliberately tracks this competitor set: {tracked}")
    context_block = ""
    if ctx_lines:
        context_block = (
            "BUSINESS CONTEXT (use to judge relevance and tailor recommendations to the sector; "
            "do NOT invent facts that are not in the evidence payload):\n"
            + "\n".join(ctx_lines)
            + "\n\n"
        )

    user_message = (
        "Analyze this competitor comparison evidence and produce insights.\n\n"
        + context_block
        + "EVIDENCE PAYLOAD (JSON):\n"
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    )

    request: Dict[str, Any] = {
        "model": model,
        "temperature": options.get("temperature", DEFAULT_TEMPERATURE),
        "max_tokens": options.get("maxOutputTokens", DEFAULT_MAX_OUTPUT_TOKENS),
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        "response_format": {"type": "json_schema", "json_schema": RESPONSE_JSON_SCHEMA},
    }

    return {
        "schemaVersion": SCHEMA_VERSION,
        "sourceSchemaVersion": comparison.get("schemaVersion"),
        "aiPayloadSchemaVersion": payload.get("schemaVersion"),
        "approxPayloadCharacters": len(user_message),
        "openaiRequest": request,
    }


def call_openai(insights_request: Dict[str, Any], api_key: Optional[str] = None) -> Dict[str, Any]:
    """Send the request to OpenAI and return parsed ci_insights_v1 JSON.

    Requires the `openai` package and OPENAI_API_KEY (or api_key argument).
    Kept optional so the builder works without the SDK installed.
    """
    api_key = api_key or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set. Set it or pass api_key=.")
    try:
        from openai import OpenAI  # type: ignore
    except ImportError as exc:
        raise RuntimeError("The 'openai' package is not installed. Run: pip install openai") from exc

    client = OpenAI(api_key=api_key)
    request = insights_request["openaiRequest"]
    response = client.chat.completions.create(**request)
    content = response.choices[0].message.content
    insights = json.loads(content)
    return {
        "success": True,
        "insights": insights,
        "usage": {
            "promptTokens": getattr(response.usage, "prompt_tokens", None),
            "completionTokens": getattr(response.usage, "completion_tokens", None),
            "totalTokens": getattr(response.usage, "total_tokens", None),
        },
        "model": response.model,
    }


def validate_insights(insights: Dict[str, Any]) -> Dict[str, Any]:
    """Lightweight structural validation of a ci_insights_v1 response
    (defense in depth if the caller did not use strict structured outputs)."""
    errors = []
    if insights.get("schemaVersion") != "ci_insights_v1":
        errors.append("schemaVersion must be ci_insights_v1")
    for key in ("executiveSummary", "competitorProfiles", "insights",
                "dashboardCards", "recommendedActions", "dataNotes"):
        if key not in insights:
            errors.append(f"missing key: {key}")
    for i, item in enumerate(insights.get("insights") or []):
        if not item.get("evidencePath"):
            errors.append(f"insights[{i}] has no evidencePath")
    return {"valid": not errors, "errors": errors}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    if not args:
        print("Usage: python openai_insights.py comparison_output.json [--call]")
        return

    input_path = Path(args[0])
    comparison = json.loads(input_path.read_text(encoding="utf-8"))
    result = build_openai_insights_request(comparison)

    output_path = input_path.with_name(input_path.stem + "_openai_request.json")
    output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"OpenAI request file: {output_path}")
    print(f"Model: {result['openaiRequest']['model']}")
    print(f"Evidence payload: ~{result['approxPayloadCharacters']:,} characters")

    if "--call" in flags:
        outcome = call_openai(result)
        insights_path = input_path.with_name(input_path.stem + "_insights.json")
        insights_path.write_text(json.dumps(outcome, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Insights: {insights_path} | tokens: {outcome['usage']}")


if __name__ == "__main__":
    main()
