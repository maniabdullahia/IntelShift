"""
Claude (Anthropic) insights provider — a drop-in sibling of openai_insights.py.

It reuses the SAME system prompt, evidence payload and ci_insights_v1 schema as
the OpenAI path (single source of truth), and only differs in HOW structured
JSON is enforced:

  - OpenAI: response_format = json_schema (strict)
  - Claude: forced tool-use — the schema becomes a tool's input_schema and we
    force the model to call that tool, so its tool input IS the structured JSON.

This keeps the two providers behaviourally identical so you can A/B test on the
same comparison by flipping AI_PROVIDER between "openai" and "claude".

Usage:
    python claude_insights.py comparison_output.json           # writes *_claude_request.json
    python claude_insights.py comparison_output.json --call     # also calls Claude (needs ANTHROPIC_API_KEY)
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Make sibling modules (openai_insights, build_ai_payload) importable regardless
# of how the gateway loads this file.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from openai_insights import (  # noqa: E402  (path set above)
    RESPONSE_JSON_SCHEMA,
    DEFAULT_TEMPERATURE,
    DEFAULT_MAX_OUTPUT_TOKENS,
    build_openai_insights_request,
    validate_insights,
)

SCHEMA_VERSION = "claude_insights_v1"
# Sonnet 5 is the GPT-4o-equivalent tier; override via options or ANTHROPIC_MODEL.
DEFAULT_CLAUDE_MODEL = "claude-sonnet-5"

_TOOL_NAME = "emit_ci_insights"


# ---------------------------------------------------------------------------
# Request builder
# ---------------------------------------------------------------------------

def build_claude_insights_request(
    comparison: Dict[str, Any],
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build an Anthropic Messages request for competitor insights.

    Reuses the OpenAI builder to construct the identical evidence payload,
    business-context block and system prompt, then repackages it for Claude with
    a forced tool call that enforces the ci_insights_v1 schema.
    """
    options = options or {}

    # Reuse the exact payload + system prompt + user message the OpenAI path uses.
    base = build_openai_insights_request(comparison, options)
    oai = base["openaiRequest"]
    system_prompt = oai["messages"][0]["content"]
    user_message = oai["messages"][1]["content"]

    model = options.get("model") or os.environ.get("ANTHROPIC_MODEL") or DEFAULT_CLAUDE_MODEL
    # Claude temperature is 0..1 (OpenAI allows up to 2) — clamp defensively.
    temperature = min(1.0, float(options.get("temperature", DEFAULT_TEMPERATURE)))

    tool = {
        "name": _TOOL_NAME,
        "description": "Return the competitive-intelligence analysis as structured ci_insights_v1 JSON. Call this exactly once with the full result.",
        "input_schema": RESPONSE_JSON_SCHEMA["schema"],
    }

    request: Dict[str, Any] = {
        "model": model,
        "max_tokens": int(options.get("maxOutputTokens", DEFAULT_MAX_OUTPUT_TOKENS)),
        "temperature": temperature,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_message}],
        "tools": [tool],
        "tool_choice": {"type": "tool", "name": _TOOL_NAME},
    }

    return {
        "schemaVersion": SCHEMA_VERSION,
        "sourceSchemaVersion": comparison.get("schemaVersion"),
        "aiPayloadSchemaVersion": base.get("aiPayloadSchemaVersion"),
        "approxPayloadCharacters": len(user_message),
        "claudeRequest": request,
    }


def call_claude(insights_request: Dict[str, Any], api_key: Optional[str] = None) -> Dict[str, Any]:
    """Send the request to Anthropic and return parsed ci_insights_v1 JSON.

    Requires the `anthropic` package and ANTHROPIC_API_KEY (or api_key argument).
    """
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set. Set it or pass api_key=.")
    try:
        import anthropic  # type: ignore
    except ImportError as exc:
        raise RuntimeError("The 'anthropic' package is not installed. Run: pip install anthropic") from exc

    client = anthropic.Anthropic(api_key=api_key)
    request = insights_request["claudeRequest"]
    response = client.messages.create(**request)

    # With forced tool_choice the model returns a tool_use block whose `input`
    # is the structured JSON we asked for.
    insights = None
    for block in response.content:
        if getattr(block, "type", None) == "tool_use" and getattr(block, "name", None) == _TOOL_NAME:
            insights = block.input
            break
    if insights is None:
        raise RuntimeError("Claude did not return the expected tool_use output.")

    _in = getattr(response.usage, "input_tokens", None)
    _out = getattr(response.usage, "output_tokens", None)
    return {
        "success": True,
        "insights": insights,
        "usage": {
            "promptTokens": _in,
            "completionTokens": _out,
            "totalTokens": (_in or 0) + (_out or 0),
        },
        "model": getattr(response, "model", request.get("model")),
        "provider": "claude",
    }


# Re-export so callers can validate identically regardless of provider.
__all__ = ["build_claude_insights_request", "call_claude", "validate_insights"]


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python claude_insights.py comparison_output.json [--call]")
        raise SystemExit(1)
    input_path = Path(sys.argv[1])
    comparison = json.loads(input_path.read_text(encoding="utf-8"))
    result = build_claude_insights_request(comparison)
    output_path = input_path.with_name(input_path.stem + "_claude_request.json")
    output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {output_path}")
    print(f"Evidence payload: ~{result['approxPayloadCharacters']:,} characters")
    if "--call" in sys.argv:
        outcome = call_claude(result)
        insights_path = input_path.with_name(input_path.stem + "_claude_insights.json")
        insights_path.write_text(json.dumps(outcome, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Wrote {insights_path} (model={outcome.get('model')}, tokens={outcome['usage']})")


if __name__ == "__main__":
    main()
