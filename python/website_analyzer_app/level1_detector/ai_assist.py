"""
ai_assist.py — tiny, best-effort AI helper for lightweight JSON tasks.

Provider-agnostic: reads AI_PROVIDER from the environment (openai | claude) and
routes to the matching SDK + API key, so switching providers is a pure .env change
(same as the main insights call). Used for the cheap, high-frequency AI touches
(Pro collection prioritisation, Growth product-match confirmation) — NOT the big
insights call. Always degrades gracefully: no key, no SDK, or any error → returns
None so callers fall back to their deterministic heuristic.

Env:
  AI_PROVIDER            "openai" (default) | "claude"
  OPENAI_API_KEY / ANTHROPIC_API_KEY
  OPENAI_MINI_MODEL      cheap OpenAI model (default "gpt-4o-mini"; avoid the
                         gpt-5 family unless your OpenAI org is verified)
  ANTHROPIC_MINI_MODEL   cheap Claude model (default "claude-haiku-4-5-20251001")
  AI_ASSIST_ENABLED      "0" to disable entirely
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, Optional


def _provider() -> str:
    return (os.environ.get("AI_PROVIDER") or "openai").strip().lower()


def ai_enabled() -> bool:
    if os.environ.get("AI_ASSIST_ENABLED", "1").strip().lower() in ("0", "false", "no"):
        return False
    key = "ANTHROPIC_API_KEY" if _provider() == "claude" else "OPENAI_API_KEY"
    return bool(os.environ.get(key))


def _strip_json_fence(txt: str) -> str:
    t = (txt or "").strip()
    t = re.sub(r"^```(?:json)?\s*", "", t, flags=re.I)
    t = re.sub(r"\s*```$", "", t)
    return t.strip()


def _openai_json(system: str, user: str, max_tokens: int) -> Optional[Dict[str, Any]]:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        return None
    try:
        from openai import OpenAI  # type: ignore
    except Exception:
        return None
    # Default to gpt-4o-mini, NOT gpt-5-mini: the gpt-5 family is gated to
    # OpenAI-verified orgs, so an unverified account 404s on every mini call and
    # silently loses all AI. gpt-4o-mini is cheap and needs no verification.
    model = os.environ.get("OPENAI_MINI_MODEL") or "gpt-4o-mini"
    try:
        client = OpenAI(api_key=key)
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
            max_tokens=max_tokens,
        )
        txt = (resp.choices[0].message.content or "").strip()
        return json.loads(txt) if txt else None
    except Exception as exc:  # pragma: no cover - network/SDK dependent
        print(f"[ai_assist:openai] fallback ({type(exc).__name__}: {exc})")
        return None


def _claude_json(system: str, user: str, max_tokens: int) -> Optional[Dict[str, Any]]:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    try:
        from anthropic import Anthropic  # type: ignore
    except Exception:
        return None
    model = os.environ.get("ANTHROPIC_MINI_MODEL") or "claude-haiku-4-5-20251001"
    try:
        client = Anthropic(api_key=key)
        msg = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            # Claude has no JSON response_format; instruct it to emit only JSON.
            system=system + " Respond with ONLY valid JSON — no prose, no code fences.",
            messages=[{"role": "user", "content": user}],
        )
        txt = "".join(getattr(b, "text", "") or "" for b in (msg.content or [])).strip()
        txt = _strip_json_fence(txt)
        return json.loads(txt) if txt else None
    except Exception as exc:  # pragma: no cover - network/SDK dependent
        print(f"[ai_assist:claude] fallback ({type(exc).__name__}: {exc})")
        return None


def ai_json(system: str, user: str, model: Optional[str] = None, max_tokens: int = 900) -> Optional[Dict[str, Any]]:
    """Run a small JSON completion via the configured provider (AI_PROVIDER).
    Returns parsed JSON dict, or None on any failure so the caller can fall back."""
    if not ai_enabled():
        return None
    if _provider() == "claude":
        return _claude_json(system, user, max_tokens)
    return _openai_json(system, user, max_tokens)


# ── Vision (image → JSON) ─────────────────────────────────────────────────────
def _openai_vision(system: str, user: str, image_url: str, max_tokens: int) -> Optional[Dict[str, Any]]:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        return None
    try:
        from openai import OpenAI  # type: ignore
    except Exception:
        return None
    model = os.environ.get("OPENAI_VISION_MODEL") or "gpt-4o-mini"
    try:
        client = OpenAI(api_key=key)
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": [
                    {"type": "text", "text": user},
                    {"type": "image_url", "image_url": {"url": image_url, "detail": "low"}},
                ]},
            ],
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        txt = (resp.choices[0].message.content or "").strip()
        return json.loads(txt) if txt else None
    except Exception as exc:  # pragma: no cover
        print(f"[ai_assist:openai-vision] fallback ({type(exc).__name__}: {exc})")
        return None


def _claude_vision(system: str, user: str, image_url: str, max_tokens: int) -> Optional[Dict[str, Any]]:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    try:
        from anthropic import Anthropic  # type: ignore
    except Exception:
        return None
    model = os.environ.get("ANTHROPIC_VISION_MODEL") or os.environ.get("ANTHROPIC_MINI_MODEL") or "claude-haiku-4-5-20251001"
    try:
        client = Anthropic(api_key=key)
        msg = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system + " Respond with ONLY valid JSON — no prose, no code fences.",
            messages=[{"role": "user", "content": [
                {"type": "text", "text": user},
                {"type": "image", "source": {"type": "url", "url": image_url}},
            ]}],
        )
        txt = "".join(getattr(b, "text", "") or "" for b in (msg.content or [])).strip()
        txt = _strip_json_fence(txt)
        return json.loads(txt) if txt else None
    except Exception as exc:  # pragma: no cover
        print(f"[ai_assist:claude-vision] fallback ({type(exc).__name__}: {exc})")
        return None


def ai_vision_json(system: str, user: str, image_url: str, max_tokens: int = 500) -> Optional[Dict[str, Any]]:
    """Read an image and return parsed JSON via the configured provider (AI_PROVIDER).
    Returns None on any failure so callers can skip enrichment gracefully."""
    if not ai_enabled() or not image_url:
        return None
    if _provider() == "claude":
        return _claude_vision(system, user, image_url, max_tokens)
    return _openai_vision(system, user, image_url, max_tokens)
