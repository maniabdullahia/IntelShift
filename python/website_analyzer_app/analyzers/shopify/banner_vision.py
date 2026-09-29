"""
analyzers/shopify/banner_vision.py
===================================
Vision reading of image-only homepage banners / heroes.

Many stores bake their live promotion straight into a hero IMAGE with no
accompanying HTML text — e.g. IRONGEAR's "Flat 25% on activewear & flat 15%
off on accessories from 11th Aug - 16th August" locked inside the hero graphic.
The DOM extractor can see the image but finds no heading/text, so it flags the
slide as `media_no_text`. Those slides are exactly the ones this module reads.

We send each text-less banner image to a vision-capable LLM (GPT-4o-mini) and
ask it for two things:
  1. the verbatim text visible in the image (so the promo stops being invisible), and
  2. a STRUCTURED interpretation — what kind of offer, how much, on what, until
     when — plus a one-line "meaning": what the store is trying to get the
     shopper to do right now.

This is the "what it means, not just what's there" layer for the front page.

Design notes
------------
* Reuses the same lazy OpenAI client + .env loading pattern as llm_extractor.py.
* Image URLs are passed by reference (the API fetches public Shopify CDN URLs) —
  no local download, no extra deps.
* Strictly cost-capped (MAX_VISION_CALLS) and only ever fired on image-only
  slides, so a normal text hero costs nothing.
* Fails soft: any error returns {} / 0 and never breaks the homepage pipeline.
"""

import os
import re
import json
import logging

logger = logging.getLogger(__name__)

# Hero slides are often VIDEOS (cdn.shopify.com/videos/…​.mp4). The vision model
# only accepts still images, so we must never send a video URL to it.
_VIDEO_EXT_RE = re.compile(r"\.(mp4|webm|mov|m4v|ogg|ogv|avi|mkv)(\?|#|$)", re.I)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_MODEL = "gpt-4o-mini"          # vision-capable, cheap (~$0.001–0.003 / image)
_MAX_TOKENS_RESPONSE = 500
MAX_VISION_CALLS = 4            # hard cap on images read per homepage
_MIN_URL_LEN = 12               # ignore obviously broken image refs

_client = None


def _get_client():
    """Lazy OpenAI client, mirroring level1_detector/llm_extractor.py."""
    global _client
    if _client is not None:
        return _client

    try:
        from dotenv import load_dotenv
        # .env lives at the website_analyzer_app root (two levels up from
        # analyzers/shopify/). Load without override so real env wins.
        _env = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
        load_dotenv(dotenv_path=_env, override=False)
    except ImportError:
        pass

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")

    from openai import OpenAI
    _client = OpenAI(api_key=api_key)
    return _client


def vision_available() -> bool:
    """True when the configured AI provider (AI_PROVIDER) has a key, so callers can
    skip work entirely offline."""
    try:
        from dotenv import load_dotenv
        _env = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
        load_dotenv(dotenv_path=_env, override=False)
    except ImportError:
        pass
    try:
        from level1_detector.ai_assist import ai_enabled  # type: ignore
        return ai_enabled()
    except Exception:
        return bool(os.environ.get("OPENAI_API_KEY"))


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

_VISION_SCHEMA = """{
  "textInImage": "EVERY word of text visible in the image, verbatim, in reading order. null if the image has no text at all.",
  "isPromotional": true or false,
  "offer": {
    "type": "one of: percent_off | amount_off | bogo | free_shipping | free_gift | new_arrival | new_collection | seasonal_sale | clearance | bundle | loyalty | brand_message | null",
    "discountPercent": "the headline discount as a number e.g. 25, null if none or not a percentage",
    "appliesTo": ["product categories or ranges the offer covers, e.g. activewear, accessories — [] if it applies storewide or is unclear"],
    "startDate": "raw start date text exactly as written e.g. '11th Aug', null",
    "endDate": "raw end date text exactly as written e.g. '16th August', null",
    "code": "discount / coupon code if shown, null"
  },
  "headline": "the single main marketing line, null if none",
  "callToAction": "the button / CTA wording e.g. 'Shop Now', null",
  "meaning": "ONE plain sentence: what this banner is trying to get the shopper to do and what it signals about the store's CURRENT strategy (e.g. running a time-boxed activewear push to clear seasonal stock). Interpret, do not just restate the text."
}"""

_SYSTEM = (
    "You read marketing banner images from e-commerce homepages and return "
    "structured data about the offer or message shown. Read text precisely, "
    "including small print like dates and discount percentages. "
    "Return ONLY valid JSON, no markdown, no explanation."
)


# ---------------------------------------------------------------------------
# Core: read a single banner image
# ---------------------------------------------------------------------------

def read_banner_image(image_url: str) -> dict:
    """
    Send one banner image to the vision model and return the parsed intel dict
    (keys from _VISION_SCHEMA), or {} on any failure.
    """
    if not image_url or len(image_url) < _MIN_URL_LEN:
        return {}
    # Provider-agnostic vision read (routes to OpenAI or Claude via AI_PROVIDER).
    try:
        from level1_detector.ai_assist import ai_vision_json  # type: ignore
    except Exception as e:
        logger.warning(f"banner_vision: ai_assist unavailable — {e}")
        return {}
    user_prompt = (
        "Read this homepage banner image and return JSON in exactly this schema:\n"
        f"{_VISION_SCHEMA}"
    )
    data = ai_vision_json(_SYSTEM, user_prompt, image_url, max_tokens=_MAX_TOKENS_RESPONSE)
    return data if isinstance(data, dict) else {}


# ---------------------------------------------------------------------------
# Selection: which slides actually need vision
# ---------------------------------------------------------------------------

def _image_of(item: dict) -> str:
    """The banner's still-image URL across the hero / collection-banner shapes.
    Skips video URLs (.mp4 etc.) and prefers a poster image, so a video hero with
    a poster is still readable and one without a poster yields nothing."""
    for key in ("url", "imageUrl", "posterImage"):
        v = item.get(key)
        if v and not _VIDEO_EXT_RE.search(v):
            return v
    return ""


def _has_text(item: dict) -> bool:
    """True when the DOM already gave us usable text — no vision needed."""
    return bool(
        (item.get("heading") or "").strip()
        or (item.get("textPreview") or "").strip()
    )


def _needs_vision(item: dict) -> bool:
    # _image_of already excludes video URLs, so a video hero with no poster
    # returns "" here and is skipped.
    img = _image_of(item)
    return bool(img) and len(img) >= _MIN_URL_LEN and not _has_text(item)


# ---------------------------------------------------------------------------
# Enrichment: mutate hero/banner items in place, attach `vision`
# ---------------------------------------------------------------------------

def enrich_media_with_vision(*media_lists, max_calls: int = MAX_VISION_CALLS) -> int:
    """
    For every image-only slide across the given media lists (heroMedia,
    collectionBanners, …), read the image with the vision model and attach the
    result as item["vision"]. De-duplicates by image URL so the same graphic is
    never paid for twice. Returns the number of images actually read.

    Items are mutated IN PLACE, so callers that already reference these lists in
    the result payload get the enrichment for free.
    """
    if not vision_available():
        print("🖼️  [banner-vision] skipped — no OPENAI_API_KEY")
        return 0

    # Collect candidate items in priority order (hero first, then banners).
    candidates = []
    for lst in media_lists:
        if not isinstance(lst, list):
            continue
        for item in lst:
            if isinstance(item, dict) and _needs_vision(item):
                candidates.append(item)

    if not candidates:
        return 0

    read_count = 0
    seen_urls: dict = {}
    for item in candidates:
        if read_count >= max_calls:
            break
        img = _image_of(item)
        # Reuse an already-read result for a duplicate image (cost control).
        if img in seen_urls:
            item["vision"] = seen_urls[img]
            continue
        intel = read_banner_image(img)
        if not intel:
            continue
        item["vision"] = intel
        seen_urls[img] = intel
        read_count += 1
        _txt = (intel.get("textInImage") or "")[:70]
        print(
            f"🖼️  [banner-vision] read image-only slide → "
            f"promo={intel.get('isPromotional')} "
            f"type={(intel.get('offer') or {}).get('type')} "
            f"text={_txt!r}"
        )

    print(f"🖼️  [banner-vision] read {read_count} image-only banner(s) via vision")
    return read_count
