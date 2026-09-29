"""
level1_detector/llm_extractor.py
=================================
Tier-2 LLM extraction fallback using OpenAI GPT-4o-mini.

Triggered from main.py when standard extraction leaves critical fields null.
Covers four page types:
  - product   : name, price, currency, availability, description, variants
  - collection: product list (name, price, url), currency, count
  - pricing   : plans (name, price, period, features), billing model
  - unknown   : detect page type then extract product fields

Cost estimate: ~$0.0002–0.002 per page (GPT-4o-mini pricing).
"""

import os
import re
import json
import logging

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_MODEL = "gpt-4o-mini"
_MAX_TOKENS_RESPONSE = 800
_MAX_CONTEXT_CHARS = 8000   # trimmed page snapshot sent to the LLM

_PRODUCT_SCHEMA = {
    "name":          "Product name (string, not the page title)",
    "price":         "Current selling price as a number exactly as shown on the page (e.g. 98.0 or 32500.0), null if unknown",
    "compareAtPrice":"Original / strikethrough price as a number exactly as shown, null if no sale",
    "currency":      (
        "ISO 4217 currency code that matches the price shown on the page. "
        "Look for explicit currency symbols (£=GBP, €=EUR, $=USD, ₹=INR, PKR/Rs=PKR, etc.) "
        "or currency codes in the page text. "
        "IMPORTANT: if the URL contains a locale like /en-pk/ infer PKR, /en-gb/ infer GBP, "
        "/en-us/ or no locale infer USD. Do NOT default to USD if a different currency is shown."
    ),
    "availability":  '"in_stock" or "out_of_stock"',
    "description":   "Short product description text, null if absent",
    "category":      "Broad category e.g. Clothing, Footwear, Beauty, Accessories — null if unclear",
    "productType":   "Specific type e.g. Leggings, Sneakers, Moisturizer — null if unclear",
    "vendor":        "Brand / vendor name, null if not on page",
    "imageUrl":      "Primary product image URL, null if absent",
    "variants":      (
        "List of option groups, e.g. "
        '[{"name":"Size","values":["XS","S","M","L"]},{"name":"Color","values":["Black","White"]}]'
        " — empty list [] if no variants found"
    ),
}


# ---------------------------------------------------------------------------
# OpenAI client (lazy init so the library is only imported when needed)
# ---------------------------------------------------------------------------

_client = None


def _get_client():
    global _client
    if _client is not None:
        return _client

    # Load .env file if present
    try:
        from dotenv import load_dotenv
        _env = os.path.join(os.path.dirname(__file__), "..", ".env")
        load_dotenv(dotenv_path=_env, override=False)
    except ImportError:
        pass

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY not set. Add it to the .env file in the project root."
        )

    from openai import OpenAI
    _client = OpenAI(api_key=api_key)
    return _client


# ---------------------------------------------------------------------------
# Page snapshot builder
# ---------------------------------------------------------------------------

def _build_page_snapshot(html: str, url: str, result: dict) -> str:
    """
    Build a compact text snapshot of the page for the LLM prompt.
    Strips scripts/styles, includes OG tags, JSON-LD, and visible text.
    Capped at _MAX_CONTEXT_CHARS to keep costs low.
    """
    soup = BeautifulSoup(html or "", "lxml")

    # Extract locale hint from URL (e.g. /en-pk/ → locale=en-pk, likely PKR)
    import re as _re
    _locale_match = _re.search(r'/([a-z]{2}-[a-z]{2})/', url or "")
    _locale_hint = f" (locale: {_locale_match.group(1)})" if _locale_match else ""

    lines = [f"URL: {url}{_locale_hint}"]

    # Page title
    title_tag = soup.find("title")
    if title_tag:
        lines.append(f"Title: {title_tag.get_text(strip=True)}")

    # Meta description
    desc_meta = soup.find("meta", attrs={"name": "description"})
    if desc_meta and desc_meta.get("content"):
        lines.append(f"MetaDescription: {desc_meta['content']}")

    # OG tags
    og_lines = []
    for tag in soup.find_all("meta"):
        prop = tag.get("property") or tag.get("name") or ""
        if prop.startswith("og:") and tag.get("content"):
            og_lines.append(f"  {prop}: {tag['content']}")
    if og_lines:
        lines.append("OpenGraph:")
        lines.extend(og_lines)

    # JSON-LD
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            schema_type = (
                data.get("@type") if isinstance(data, dict)
                else (data[0].get("@type") if isinstance(data, list) and data else None)
            )
            if schema_type in ("Product", "BreadcrumbList", None):
                lines.append(f"JSON-LD: {json.dumps(data, separators=(',', ':'))[:1500]}")
                break
        except Exception:
            pass

    # H1
    h1 = soup.find("h1")
    if h1:
        lines.append(f"H1: {h1.get_text(strip=True)}")

    # Visible body text (scripts/styles stripped)
    for tag in soup(["script", "style", "noscript", "svg", "iframe"]):
        tag.decompose()
    body = soup.find("body")
    if body:
        raw_text = body.get_text(separator="\n", strip=True)
        # Collapse blank lines
        clean_text = re.sub(r"\n{3,}", "\n\n", raw_text)
        lines.append("PageText:")
        lines.append(clean_text[:4000])

    snapshot = "\n".join(lines)
    return snapshot[:_MAX_CONTEXT_CHARS]


# ---------------------------------------------------------------------------
# Core extraction
# ---------------------------------------------------------------------------

# Provider-agnostic JSON extraction (routes to OpenAI or Claude via AI_PROVIDER),
# replacing the direct OpenAI client so .env controls the provider everywhere.
def _llm_available() -> bool:
    try:
        from level1_detector.ai_assist import ai_enabled  # type: ignore
        return ai_enabled()
    except Exception:
        return bool(os.environ.get("OPENAI_API_KEY"))


def _llm_json(system_prompt: str, user_prompt: str, max_tokens: int) -> dict:
    try:
        from level1_detector.ai_assist import ai_json  # type: ignore
        out = ai_json(system_prompt, user_prompt, max_tokens=max_tokens)
        return out if isinstance(out, dict) else {}
    except Exception as e:
        logger.warning(f"LLM extractor: ai_json failed — {e}")
        return {}


def extract_product_with_llm(html: str, url: str, result: dict) -> dict:
    """
    Call the configured LLM (AI_PROVIDER) to extract product fields from a snapshot.

    Returns a dict with any of the _PRODUCT_SCHEMA keys that were found.
    Returns {} on failure (never raises).
    """
    if not _llm_available():
        return {}

    snapshot = _build_page_snapshot(html, url, result)

    schema_desc = "\n".join(
        f'  "{k}": {v}' for k, v in _PRODUCT_SCHEMA.items()
    )

    system_prompt = (
        "You are a precise product data extractor. "
        "Given web page content, extract product fields and return ONLY valid JSON — "
        "no markdown, no explanation, no code block."
    )

    user_prompt = (
        f"Extract the following product fields from this page.\n\n"
        f"Required JSON schema (return ALL keys, use null for missing values):\n"
        f"{{\n{schema_desc}\n}}\n\n"
        f"Page content:\n{snapshot}"
    )

    try:
        extracted = _llm_json(system_prompt, user_prompt, _MAX_TOKENS_RESPONSE)
        if not isinstance(extracted, dict) or not extracted:
            return {}

        # --- Sanity-check the extracted name ---
        # Reject names that are clearly not product names so they don't
        # pollute the result with the wrong value.
        llm_name = extracted.get("name")
        if llm_name and isinstance(llm_name, str):
            # 1. Too long to be a product name (probably a description or page heading)
            if len(llm_name) > 120:
                logger.warning(f"LLM EXTRACTION: rejecting name (too long, {len(llm_name)} chars)")
                extracted["name"] = None

            # 2. Matches the site domain or og:site_name (LLM confused site identity with product)
            elif llm_name:
                _page_url  = (result.get("page") or {}).get("url") or url or ""
                _site_name = ""
                try:
                    from urllib.parse import urlparse as _urlparse
                    _domain = _urlparse(_page_url).netloc.lower().replace("www.", "")
                    _domain_root = _domain.split(".")[0]          # "happynails" from "happynails.pk"
                    _site_name   = _domain_root
                except Exception:
                    pass
                # Also check og:site_name from result if available
                _og_site = (result.get("seo") or {}).get("siteName") or \
                           (result.get("og") or {}).get("site_name") or ""
                _name_lower = llm_name.lower().strip()
                if (
                    (_site_name and _name_lower == _site_name.lower())
                    or (_og_site and _name_lower == _og_site.lower().strip())
                ):
                    logger.warning(f"LLM EXTRACTION: rejecting name {llm_name!r} (matches site identity)")
                    extracted["name"] = None

        print(f"LLM EXTRACTION: name={extracted.get('name')!r} price={extracted.get('price')} currency={extracted.get('currency')}")
        return extracted
    except Exception as e:
        logger.warning(f"LLM extractor: API call failed — {e}")
        return {}


# ---------------------------------------------------------------------------
# Merge helper
# ---------------------------------------------------------------------------

def merge_llm_into_result(result: dict, llm_data: dict) -> dict:
    """
    Merge LLM-extracted fields into the existing result dict.
    Only fills NULL / missing fields — never overwrites good data.
    """
    if not llm_data:
        return result

    ec = result.get("ecommerce") or {}
    prod = ec.get("product") or {}
    content = result.get("content") or {}

    def _set_if_null(d, key, value):
        if value is not None and not d.get(key):
            d[key] = value

    # Name
    _set_if_null(prod, "name", llm_data.get("name"))
    _set_if_null(content, "productName", llm_data.get("name"))

    # Category / productType
    _set_if_null(prod, "category", llm_data.get("category"))
    _set_if_null(prod, "productType", llm_data.get("productType"))
    _set_if_null(content, "category", llm_data.get("category"))
    _set_if_null(content, "productType", llm_data.get("productType"))

    # Vendor
    _set_if_null(prod, "vendor", llm_data.get("vendor"))

    # Image
    _set_if_null(prod, "imageUrl", llm_data.get("imageUrl"))

    # Description
    if llm_data.get("description") and not (prod.get("description") or {}).get("text"):
        prod["description"] = {
            "html": None,
            "text": llm_data["description"],
            "bullets": [],
            "headings": [],
            "features": [],
            "benefits": [],
            "usage": [],
            "specifications": [],
        }
        content["productDescription"] = prod["description"]

    # Price
    price = prod.get("price") or {}
    llm_price = llm_data.get("price")
    llm_compare = llm_data.get("compareAtPrice")
    llm_currency = llm_data.get("currency")

    # Hard-override currency from URL locale — LLMs often default to USD even
    # when the page shows a different currency.  Also overrides the "USD"
    # placeholder that the Shopify extractor writes when no real currency is found.
    _LOCALE_CURRENCY = {
        "en-pk": "PKR", "en-in": "INR", "en-gb": "GBP",
        "en-au": "AUD", "en-ca": "CAD", "en-ae": "AED",
        "en-sa": "SAR", "en-eu": "EUR", "de-de": "EUR",
        "fr-fr": "EUR", "it-it": "EUR", "es-es": "EUR",
        "nl-nl": "EUR", "ja-jp": "JPY", "zh-cn": "CNY",
        "ko-kr": "KRW", "en-sg": "SGD", "en-nz": "NZD",
    }
    _url_str = (result.get("page") or {}).get("url") or ""
    _locale_currency_override = None
    for _loc, _cur in _LOCALE_CURRENCY.items():
        if f"/{_loc}/" in _url_str:
            _locale_currency_override = _cur
            llm_currency = _cur
            break

    # TLD-based currency override — catches .ca, .com.au, .pk, etc.
    # Only fires if no path-locale match was found above.
    if not _locale_currency_override and _url_str:
        try:
            from urllib.parse import urlparse as _up
            _host = _up(_url_str).netloc.lower()
        except Exception:
            _host = ""
        _TLD_MAP = {
            ".com.pk": "PKR", ".pk": "PKR",
            ".co.in": "INR", ".in": "INR",
            ".co.uk": "GBP",
            ".com.au": "AUD",
            ".co.nz": "NZD", ".nz": "NZD",
            ".ca": "CAD",
            ".ae": "AED", ".sa": "SAR",
            ".de": "EUR", ".fr": "EUR", ".it": "EUR",
            ".es": "EUR", ".nl": "EUR", ".be": "EUR",
            ".jp": "JPY", ".sg": "SGD",
        }
        for _tld, _cur in _TLD_MAP.items():
            if _host.endswith(_tld):
                _locale_currency_override = _cur
                llm_currency = _cur
                break

    try:
        llm_price = float(llm_price) if llm_price is not None else None
    except (TypeError, ValueError):
        llm_price = None
    try:
        llm_compare = float(llm_compare) if llm_compare is not None else None
    except (TypeError, ValueError):
        llm_compare = None

    if llm_price and not price.get("current"):
        price["current"] = llm_price
        price["isOnSale"] = bool(llm_compare and llm_compare > llm_price)
    if llm_compare and not price.get("compareAt"):
        price["compareAt"] = llm_compare
    if llm_currency:
        # Always write locale-derived currency; only skip if currency already
        # set AND no locale override was found (i.e. LLM just guessed USD).
        if _locale_currency_override or not price.get("currency"):
            price["currency"] = llm_currency
    prod["price"] = price

    # Availability
    llm_avail = llm_data.get("availability")
    avail = prod.get("availability") or {}
    if llm_avail and not avail.get("status"):
        avail["status"] = llm_avail
        avail["inStock"] = (llm_avail == "in_stock")
        prod["availability"] = avail

    # Variants
    llm_variants = llm_data.get("variants")
    if llm_variants and isinstance(llm_variants, list) and not (prod.get("options") or prod.get("variants")):
        # Convert to options format
        options = []
        for v in llm_variants:
            if isinstance(v, dict) and v.get("name"):
                options.append({
                    "name": v["name"],
                    "values": v.get("values") or [],
                })
        if options:
            prod["options"] = options
            ec["options"] = options

    # Write back
    ec["product"] = prod
    result["ecommerce"] = ec
    result["content"] = content
    result["_llm_extraction"] = True

    return result


# ---------------------------------------------------------------------------
# Shared snapshot builder (lighter than product version — no JSON-LD detail)
# ---------------------------------------------------------------------------

def _build_general_snapshot(html: str, url: str, max_chars: int = 6000) -> str:
    """Compact page snapshot for collection / pricing / unknown pages."""
    soup = BeautifulSoup(html or "", "lxml")

    lines = [f"URL: {url}"]

    title_tag = soup.find("title")
    if title_tag:
        lines.append(f"Title: {title_tag.get_text(strip=True)}")

    h1 = soup.find("h1")
    if h1:
        lines.append(f"H1: {h1.get_text(strip=True)}")

    # JSON-LD (first block only)
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            lines.append(f"JSON-LD: {json.dumps(data, separators=(',', ':'))[:1200]}")
            break
        except Exception:
            pass

    # __NEXT_DATA__ — Next.js SSR embeds all page props as JSON in a script tag.
    # Strip scripts AFTER extracting this so we don't lose pricing data.
    _next_data_tag = soup.find("script", id="__NEXT_DATA__")
    if _next_data_tag:
        try:
            nd = json.loads(_next_data_tag.string or "")
            # Flatten to a compact string; truncate aggressively since it can be huge
            nd_str = json.dumps(nd, separators=(',', ':'))
            lines.append(f"NextData(truncated): {nd_str[:2500]}")
        except Exception:
            pass

    # Visible body text
    for tag in soup(["script", "style", "noscript", "svg", "iframe", "nav", "footer"]):
        tag.decompose()
    body = soup.find("body")
    if body:
        raw = body.get_text(separator="\n", strip=True)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        lines.append("PageText:")
        lines.append(raw[:4500])

    return "\n".join(lines)[:max_chars]


# ---------------------------------------------------------------------------
# Collection extractor
# ---------------------------------------------------------------------------

_COLLECTION_SCHEMA = """{
  "collectionName": "Name/title of this category or collection (string)",
  "currency": "ISO 4217 code e.g. USD, GBP, EUR, PKR, INR — infer from symbols if needed",
  "products": [
    {
      "name": "product name",
      "price": "price as number (e.g. 29.99), null if not shown",
      "url": "absolute product URL if visible on the page, else null",
      "imageUrl": "product image URL if visible, else null"
    }
  ],
  "totalProductCount": "integer — total products shown on this page, null if unknown"
}

Return up to 12 products. Use null for any field you cannot determine."""


def extract_collection_with_llm(html: str, url: str, result: dict) -> dict:
    """Extract collection fields (product list, currency) via the configured LLM."""
    if not _llm_available():
        return {}

    snapshot = _build_general_snapshot(html, url)

    system_prompt = (
        "You are a precise e-commerce data extractor. "
        "Given web page content from a product collection or category page, "
        "extract the structured data and return ONLY valid JSON — no markdown, no explanation."
    )
    user_prompt = (
        f"Extract collection data from this page.\n\n"
        f"Required JSON schema:\n{_COLLECTION_SCHEMA}\n\n"
        f"Page content:\n{snapshot}"
    )

    try:
        extracted = _llm_json(system_prompt, user_prompt, 1200)
        if not isinstance(extracted, dict) or not extracted:
            return {}
        n_products = len(extracted.get("products") or [])
        print(f"LLM COLLECTION: name={extracted.get('collectionName')!r} currency={extracted.get('currency')} products={n_products}")
        return extracted
    except Exception as e:
        logger.warning(f"LLM collection extractor: API call failed — {e}")
        return {}


def merge_collection_into_result(result: dict, llm_data: dict) -> dict:
    """Merge LLM collection data — only fills null / empty fields."""
    if not llm_data:
        return result

    ec = result.setdefault("ecommerce", {})
    content = result.setdefault("content", {})

    # Collection name
    llm_name = llm_data.get("collectionName")
    if llm_name and not content.get("collectionName"):
        content["collectionName"] = llm_name

    # Currency
    llm_currency = llm_data.get("currency")

    # Products — only fill when the rule-based pass produced nothing
    llm_products = llm_data.get("products") or []
    existing = result.get("products") or []
    if llm_products and not existing:
        normalized = []
        for i, p in enumerate(llm_products[:12], start=1):
            if not isinstance(p, dict):
                continue
            price_val = p.get("price")
            try:
                price_val = float(price_val) if price_val is not None else None
            except (TypeError, ValueError):
                price_val = None
            normalized.append({
                "name": p.get("name"),
                "url": p.get("url"),
                "imageUrl": p.get("imageUrl"),
                "price": {
                    "current": price_val,
                    "currency": llm_currency or "USD",
                    "compareAt": None,
                    "isOnSale": False,
                } if price_val is not None else None,
                "availability": None,
                "rank": i,
                "source": "llm",
            })
        result["products"] = normalized
        ec["products"] = normalized

        # Update productStats
        prices = [p["price"]["current"] for p in normalized if (p.get("price") or {}).get("current")]
        stats = ec.setdefault("productStats", {})
        stats["productCount"] = len(normalized)
        if prices:
            stats["priceRange"] = {"min": min(prices), "max": max(prices)}
        if llm_currency:
            stats["currency"] = llm_currency

    result["_llm_extraction"] = True
    return result


# ---------------------------------------------------------------------------
# Pricing / general page extractor
# ---------------------------------------------------------------------------

_PRICING_SCHEMA = """{
  "plans": [
    {
      "name": "plan name e.g. Basic, Pro, Enterprise",
      "price": "monthly price as number, null if custom/contact-sales",
      "pricePeriod": "monthly | annual | per year | per month | null",
      "currency": "ISO 4217 code or currency symbol",
      "description": "one-line plan description, null if not shown",
      "features": ["key feature 1", "key feature 2"]
    }
  ],
  "currency": "primary currency shown on the page (ISO 4217 code)",
  "hasFreeTrial": true or false,
  "billingModel": "monthly | annual | both | null",
  "moneyBackGuarantee": "e.g. '30-day' or null",
  "lowestPrice": "lowest plan price as number, null if custom",
  "highestPrice": "highest non-enterprise plan price as number, null if custom"
}

Extract ALL plans shown. Use null for values you cannot determine."""


def extract_pricing_with_llm(html: str, url: str, result: dict) -> dict:
    """Extract pricing plan data via the configured LLM."""
    if not _llm_available():
        return {}

    snapshot = _build_general_snapshot(html, url)

    system_prompt = (
        "You are a precise SaaS pricing data extractor. "
        "Given web page content from a pricing page, extract all plans and pricing details. "
        "Return ONLY valid JSON — no markdown, no explanation."
    )
    user_prompt = (
        f"Extract pricing data from this page.\n\n"
        f"Required JSON schema:\n{_PRICING_SCHEMA}\n\n"
        f"Page content:\n{snapshot}"
    )

    try:
        extracted = _llm_json(system_prompt, user_prompt, 1500)
        if not isinstance(extracted, dict) or not extracted:
            return {}
        n_plans = len(extracted.get("plans") or [])
        print(f"LLM PRICING: plans={n_plans} currency={extracted.get('currency')} lowest={extracted.get('lowestPrice')}")
        return extracted
    except Exception as e:
        logger.warning(f"LLM pricing extractor: API call failed — {e}")
        return {}


def merge_pricing_into_result(result: dict, llm_data: dict) -> dict:
    """Merge LLM pricing data — only fills null / empty plan data."""
    if not llm_data:
        return result

    llm_plans = llm_data.get("plans") or []
    if not llm_plans:
        return result

    # Build the pricing sub-dict in the same shape as rule-based extraction
    existing_pricing = result.get("pricing") or {}
    existing_plans = list(existing_pricing.get("plans") or [])

    # Skip LLM if rule-based found well-priced plans (at least half have prices).
    # If plans are mostly name-only (price: null), let LLM overwrite them.
    if existing_plans:
        existing_priced = sum(
            1 for p in existing_plans
            if isinstance(p, dict)
            and isinstance(p.get("price"), dict)
            and p["price"].get("amount") is not None
        )
        if existing_priced >= len(existing_plans) / 2:
            result["_llm_extraction"] = True
            return result

    # Use None rather than a bare "$" when currency is unknown — the raw price
    # text already preserves the symbol, so we never need to fabricate an ISO code.
    currency = llm_data.get("currency") or None

    plans_out = []
    for p in llm_plans:
        if not isinstance(p, dict) or not p.get("name"):
            continue
        price_val = p.get("price")
        try:
            price_val = float(price_val) if price_val is not None else None
        except (TypeError, ValueError):
            price_val = None

        period = p.get("pricePeriod") or ("monthly" if price_val is not None else None)
        _plan_currency = p.get("currency") or currency  # plan-level currency wins
        price_obj = None
        if price_val is not None:
            _raw_str = f"{_plan_currency} {price_val}" if _plan_currency else str(price_val)
            price_obj = {
                "raw": _raw_str,
                "currency": _plan_currency,
                "amountRaw": str(price_val),
                "amount": price_val,
                "period": period,
            }
        elif re.search(r'contact|custom|enterprise', p.get("name", ""), re.I):
            price_obj = {
                "raw": "Custom pricing",
                "currency": None,
                "amountRaw": None,
                "amount": None,
                "period": None,
            }

        plans_out.append({
            "name": p["name"],
            "type": (
                "enterprise"
                if any(t in p.get("name", "").lower() for t in (
                    "enterprise", "business", "team", "agency", "corporate",
                    "ultimate", "unlimited", "advanced", "professional", "pro",
                    "scale", "growth", "plus"
                ))
                else "core_plan"
            ),
            "description": p.get("description"),
            "price": price_obj,
            "priceMentions": [price_obj] if price_obj else [],
            "features": p.get("features") or [],
            "rawText": None,
            "source": "llm",
        })

    if not plans_out:
        return result

    # Build period-aware price lists so we never mix monthly and annual amounts
    # in the same min/max (e.g. $29/mo vs $290/yr would produce misleading range).
    _billing_model = llm_data.get("billingModel") or "monthly"
    _preferred_period = "annual" if _billing_model == "annual" else "monthly"

    def _plan_prices_for_period(plans, period):
        """Return amounts for plans whose period matches, falling back to all."""
        matched = [
            (p["price"] or {}).get("amount")
            for p in plans
            if (p.get("price") or {}).get("amount") is not None
            and ((p["price"] or {}).get("period") or "monthly").lower().startswith(period[:2])
        ]
        if matched:
            return matched
        # If no plans matched the preferred period, use all priced plans
        return [
            (p["price"] or {}).get("amount")
            for p in plans
            if (p.get("price") or {}).get("amount") is not None
        ]

    prices = _plan_prices_for_period(plans_out, _preferred_period)

    new_pricing = {
        **existing_pricing,
        "hasPricing": True,
        "pricingModel": "plan_based",
        "currency": currency,
        "billing": {
            "monthly": _billing_model in ("monthly", "both"),
            "annual":  _billing_model in ("annual", "both"),
            "billingModel": _billing_model,
            "mentionsAnnualDiscount": False,
            "moneyBackGuarantee": llm_data.get("moneyBackGuarantee"),
        },
        "billingModel": _billing_model,
        "planOrder": [p["name"] for p in plans_out],
        "plans": plans_out,
        "lowestMainPlanPrice": min(prices) if prices else None,
        "highestMainPlanPrice": max(prices) if prices else None,
        "pricePeriod": _preferred_period,
        "freeTrial": llm_data.get("hasFreeTrial") or False,
        "moneyBackGuarantee": llm_data.get("moneyBackGuarantee"),
    }

    result["pricing"] = new_pricing

    # Mirror into generalPage.pricing if present
    gp = result.get("generalPage")
    if isinstance(gp, dict):
        gp["pricing"] = new_pricing

    result["_llm_extraction"] = True
    return result


# ---------------------------------------------------------------------------
# Unified dispatcher
# ---------------------------------------------------------------------------

def _needs_product_llm(result: dict) -> bool:
    ec = result.get("ecommerce") or {}
    prod = ec.get("product") or {}
    price = prod.get("price") if isinstance(prod.get("price"), dict) else {}
    return not prod.get("name") or not price.get("current")


def _needs_collection_llm(result: dict) -> bool:
    return not (result.get("products") or [])


def _needs_pricing_llm(result: dict) -> bool:
    pricing = result.get("pricing") or {}
    gp_pricing = (result.get("generalPage") or {}).get("pricing") or {}
    plans = list(pricing.get("plans") or gp_pricing.get("plans") or [])
    if not plans:
        return True
    # Trigger LLM if fewer than half the plans have a numeric price amount.
    # The Unknown general analyzer often extracts plan names with price: null
    # (name-only, confidence 0.45) — LLM can fill in the missing amounts.
    priced = sum(
        1 for p in plans
        if isinstance(p, dict)
        and isinstance(p.get("price"), dict)
        and p["price"].get("amount") is not None
    )
    return priced < (len(plans) / 2)


def run_llm_fallback_if_needed(
    result: dict,
    html: str,
    url: str,
    page_type: str,
) -> dict:
    """
    Universal LLM fallback dispatcher. Called once after all rule-based
    extraction is done. Dispatches to product, collection, or pricing LLM
    extractor based on page type and whether structured data is missing.
    """
    try:
        if page_type == "product" and _needs_product_llm(result):
            llm_data = extract_product_with_llm(html, url, result)
            if llm_data:
                result = merge_llm_into_result(result, llm_data)
        elif page_type == "collection" and _needs_collection_llm(result):
            llm_data = extract_collection_with_llm(html, url, result)
            if llm_data:
                result = merge_collection_into_result(result, llm_data)
        elif page_type in ("general", "pricing", "homepage") and _needs_pricing_llm(result):
            llm_data = extract_pricing_with_llm(html, url, result)
            if llm_data:
                result = merge_pricing_into_result(result, llm_data)
    except Exception as _e:
        print(f"LLM FALLBACK DISPATCH: error — {_e}")
    return result
