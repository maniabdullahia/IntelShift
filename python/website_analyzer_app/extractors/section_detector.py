"""
section_detector.py
===================
Shared utility that maps raw section/accordion titles to canonical section
types (ingredients, benefits, usage, features, specifications, faqs).

Used by all platform-specific product analyzers.
"""

import re


# ---------------------------------------------------------------------------
# Canonical section type → keyword patterns
# ---------------------------------------------------------------------------

SECTION_MAP = {
    "ingredients": [
        "ingredient",
        "key ingredient",
        "active ingredient",
        "full ingredient",
        "ingredient list",
        "inci",
        "composition",
        "formula",
        "contains",
        "what's inside",
        "what is inside",
        "inside the bottle",
        "formulated with",
    ],
    "benefits": [
        "benefit",
        "key benefit",
        "why you",
        "why you'll love",
        "why you will love",
        "why choose",
        "advantage",
        "result",
        "why it works",
        "what it does",
        "skin benefit",
        "hair benefit",
        "product benefit",
        "the benefits",
        "love it because",
    ],
    "usage": [
        "how to use",
        "how to apply",
        "how to wear",
        "directions",
        "direction for use",
        "direction of use",
        "usage",
        "instruction",
        "application",
        "how it works",
        "steps",
        "apply",
        "for best result",
        "to use",
        "usage guide",
        "user guide",
        "application method",
        "apply this",
    ],
    "features": [
        "feature",
        "key feature",
        "product feature",
        "highlight",
        "product highlight",
        "product detail",
        "detail",
        "what's included",
        "what is included",
        "about this product",
        "about the product",
        "product info",
        "product information",
        "overview",
        "why this product",
        "why it performs",
        "how it performs",
    ],
    "specifications": [
        "specification",
        "spec",
        "product spec",
        "technical detail",
        "technical spec",
        "size",
        "weight",
        "volume",
        "net weight",
        "net content",
        "net volume",
        "dimensions",
        "dimension",
        "capacity",
        "shade",
        "color",
        "colour",
        "sku",
        "model",
        "material",
        "package content",
        "in the box",
        "what's in the box",
    ],
    "faqs": [
        "faq",
        "frequently asked",
        "question",
        "q&a",
        "q & a",
        "questions & answers",
        "questions and answers",
        "people also ask",
    ],
}

# ---------------------------------------------------------------------------
# Pre-compiled regex per section type for efficiency
# ---------------------------------------------------------------------------

# Short generic words in specs that could falsely match substrings like
# "lightweight" → "weight", "oversize" → "size", so require word boundaries.
_SPEC_WORD_BOUNDARY_KEYWORDS = {
    "weight", "size", "volume", "shade", "color", "colour", "model", "sku",
}

_COMPILED = {}
for _section_type, _keywords in SECTION_MAP.items():
    # Sort longest first so more specific patterns match first
    _sorted_kws = sorted(_keywords, key=len, reverse=True)
    if _section_type == "specifications":
        parts = []
        for kw in _sorted_kws:
            escaped = re.escape(kw)
            if kw in _SPEC_WORD_BOUNDARY_KEYWORDS:
                parts.append(r"\b" + escaped + r"\b")
            else:
                parts.append(escaped)
        _pattern = "|".join(parts)
    else:
        _pattern = "|".join(re.escape(kw) for kw in _sorted_kws)
    _COMPILED[_section_type] = re.compile(_pattern, re.IGNORECASE)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_section_type(title):
    """
    Map a section/accordion title string to a canonical section type.

    Returns one of: "ingredients", "benefits", "usage", "features",
    "specifications", "faqs", or None if no match.
    """
    if not title:
        return None

    title = re.sub(r"\s+", " ", title).strip()

    for section_type, pattern in _COMPILED.items():
        if pattern.search(title):
            return section_type

    return None


def map_accordion_entries(accordion_entries: list) -> dict:
    """
    Given a list of accordion entries (from accordion_extractor.extract_accordions),
    return a dict of section_type → {content, items} keeping the richest entry
    per section type.

    Parameters
    ----------
    accordion_entries : list of dict
        Each dict has: {"title": str, "content": str|None, "items": list[str]}

    Returns
    -------
    dict
        {
            "ingredients":    {"title": str, "content": str, "items": [...]} | None,
            "benefits":       ...,
            "usage":          ...,
            "features":       ...,
            "specifications": ...,
            "faqs":           ...,
        }
    """
    result = {
        "ingredients": None,
        "benefits": None,
        "usage": None,
        "features": None,
        "specifications": None,
        "faqs": None,
    }

    for entry in accordion_entries:
        section_type = detect_section_type(entry.get("title", ""))
        if not section_type:
            continue

        # Keep the entry with the most content (prefer list items, then text)
        existing = result[section_type]
        if existing is None:
            result[section_type] = entry
        else:
            existing_score = len(existing.get("items") or []) * 2 + len(existing.get("content") or "")
            new_score = len(entry.get("items") or []) * 2 + len(entry.get("content") or "")
            if new_score > existing_score:
                result[section_type] = entry

    return result


def build_description_sections(mapped: dict) -> dict:
    """
    Convert a mapped accordion dict into the standard description sections
    format used across all product analyzers.

    Returns
    -------
    dict with keys: ingredients, benefits, usage, features, specifications, faqs
    Each value is a list of strings (deduplicated).
    """
    sections = {
        "ingredients": [],
        "benefits": [],
        "usage": [],
        "features": [],
        "specifications": [],
        "faqs": [],
    }

    for section_type, entry in mapped.items():
        if not entry:
            continue

        items = entry.get("items") or []
        content = entry.get("content") or ""

        if items:
            # Prefer structured list items
            sections[section_type] = _dedupe(items)
        elif content:
            # Fall back to splitting content into sentences / clauses
            parts = _split_into_parts(content)
            sections[section_type] = _dedupe(parts)

    return sections


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dedupe(items: list) -> list:
    seen = set()
    out = []
    for item in items:
        if not item:
            continue
        key = re.sub(r"\s+", " ", item).strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(re.sub(r"\s+", " ", item).strip())
    return out


def _split_into_parts(text: str) -> list:
    """Split a content block into meaningful parts (sentences or semi-colon items)."""
    if not text:
        return []

    # First try semicolons and bullet separators
    if ";" in text or "•" in text:
        parts = re.split(r"[;•]", text)
        cleaned = [p.strip() for p in parts if p.strip() and len(p.strip()) >= 5]
        if len(cleaned) >= 2:
            return cleaned

    # Fall back to sentences
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in sentences if s.strip() and len(s.strip()) >= 10]
