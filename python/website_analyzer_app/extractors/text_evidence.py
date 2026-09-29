"""
text_evidence.py — capture the page's full visible text + key zones.

WHY
----
The rest of the analyzer is structure-first: it reads specific DOM regions by
class/selector and emits metrics. Anything a selector doesn't match is dropped —
and because the AI payload is built FROM the structured output, the AI never sees
it either (that's how Sivanna's "Free Delivery on Bank Deposit" announcement bar
went missing end-to-end).

This module adds a safety net: the cleaned full visible text and a few high-value
zones (top-of-page/announcement region, hero, footer) are captured verbatim and
stored on the page. A curated, budgeted slice is later fed to the AI so it can
recover qualitative signals (promos, positioning, trust claims) that structured
extraction missed. Numbers stay deterministic elsewhere — this text is EVIDENCE
for interpretation, not a source of counts.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

try:
    from bs4 import BeautifulSoup  # type: ignore
except Exception:  # pragma: no cover
    BeautifulSoup = None  # type: ignore


# Per-page storage caps (the snapshot keeps more than the AI payload will use).
FULL_TEXT_CAP = 12000
ZONE_CAP = 1200
_DROP_TAGS = ("script", "style", "noscript", "svg", "template", "iframe")


def _collapse(text: str) -> str:
    return re.sub(r"[ \t ]+", " ", re.sub(r"\s*\n\s*", "\n", text or "")).strip()


def _dedupe_lines(text: str, max_chars: int) -> str:
    """Collapse whitespace and drop consecutive/near-duplicate lines (nav and
    menus repeat across the page). Order-preserving."""
    seen = set()
    out: List[str] = []
    total = 0
    for raw in re.split(r"[\n\r]+", text or ""):
        line = _collapse(raw)
        if not line:
            continue
        key = line.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(line)
        total += len(line) + 1
        if total >= max_chars:
            break
    joined = "\n".join(out)
    return joined[:max_chars]


def _text_of(node) -> str:
    if node is None:
        return ""
    try:
        return _collapse(node.get_text(" ", strip=True))
    except Exception:
        return ""


def build_text_evidence(html: Optional[str], url: str = "", page_type: str = "") -> Dict[str, Any]:
    """Return a compact evidence block:
        { fullText, fullTextChars, top, hero, footer, headings, capturedFrom }
    Best-effort; never raises."""
    empty = {
        "fullText": None, "fullTextChars": 0,
        "top": None, "hero": None, "footer": None,
        "headings": [], "capturedFrom": None,
    }
    if not html or not BeautifulSoup:
        return empty
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception:
        return empty

    for tag in soup(_DROP_TAGS):
        try:
            tag.decompose()
        except Exception:
            pass

    body = soup.body or soup

    # ── Full visible text (deduped, capped) ──────────────────────────────────
    full_text = _dedupe_lines(_text_of(body), FULL_TEXT_CAP)

    # ── Top-of-page zone: the announcement bar / promo strip usually lives in
    # the first text-bearing nodes, BEFORE the main content. Grab a short slice. ─
    top_bits: List[str] = []
    seen = set()
    for el in body.find_all(True, recursive=True, limit=40):
        if el.name in ("nav", "img", "picture", "source"):
            continue
        t = _text_of(el)
        if not t or len(t) < 3 or len(t) > 200:
            continue
        low = t.lower()
        if low in seen:
            continue
        seen.add(low)
        top_bits.append(t)
        if sum(len(x) for x in top_bits) > ZONE_CAP:
            break
    top = _dedupe_lines("\n".join(top_bits), ZONE_CAP) or None

    # ── Hero zone: first header/section/main block with real text. ────────────
    hero = None
    for sel in ("header", "main section", "main", "section"):
        node = soup.select_one(sel)
        t = _text_of(node)
        if t and len(t) > 20:
            hero = t[:ZONE_CAP]
            break

    # ── Footer zone. ─────────────────────────────────────────────────────────
    footer_nodes = soup.find_all("footer")
    footer = _dedupe_lines(" ".join(_text_of(f) for f in footer_nodes), ZONE_CAP) or None

    # ── Headings (h1–h3) for structure. ──────────────────────────────────────
    headings: List[str] = []
    for h in soup.find_all(["h1", "h2", "h3"]):
        t = _text_of(h)
        if t and t.lower() not in {x.lower() for x in headings}:
            headings.append(t)
        if len(headings) >= 40:
            break

    return {
        "fullText": full_text or None,
        "fullTextChars": len(full_text or ""),
        "top": top,
        "hero": hero,
        "footer": footer,
        "headings": headings,
        "capturedFrom": url or None,
    }
