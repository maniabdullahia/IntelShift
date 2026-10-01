"""
marketplace_gate.py — kept for backward compatibility.

The self-serve vs enterprise decision now lives in business_type.py, which
classifies a store into the five business types (marketplace, multinational
brand, general marketplace, niche marketplace, single brand). classify_scale()
delegates to it and keeps its old return keys (scaleTier, isMarketplace,
totalProducts, reason), adding businessType / businessTypeLabel / confidence.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from .business_type import (  # noqa: F401  (re-exported for old imports)
    MARKETPLACE_DENYLIST,
    DEFAULT_SIZE_BACKSTOP,
    classify_business_type,
    registrable_label as _registrable_domain,
)


def classify_scale(
    url: str,
    platform: str = "",
    total_products: Optional[int] = None,
    html: str = "",
    robots: str = "",
    vendor_count: Optional[int] = None,
    config: Optional[Dict[str, Any]] = None,
    **signals: Any,
) -> Dict[str, Any]:
    out = classify_business_type(
        url,
        html=html,
        robots=robots,
        total_products=total_products,
        vendor_count=vendor_count,
        config=config,
        **signals,
    )
    out["totalProducts"] = total_products
    return out
