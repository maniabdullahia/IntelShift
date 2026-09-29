"""Golden Fixture Harness - verifies extracted VALUES are correct.

The accuracy scorecard verifies structure (a price exists, a name is present).
This harness verifies TRUTH: it replays extraction against FROZEN page HTML
and compares the result to human-confirmed expected values, field by field.
Deterministic, offline, free - no network, no drift.

Workflow:
  1. RECORD a fixture (on your PC, needs network):
         python tools/golden_check.py record https://shop.pk/products/serum
     This fetches the page, freezes its HTML, runs extraction, and writes
     tools/golden_fixtures/<name>/{page.html, meta.json, expected.json}.
     expected.json is PRE-FILLED from the extraction - open it, verify every
     value against the real page in your browser, correct anything wrong,
     and delete fields you don't want checked. That human pass is what makes
     it ground truth.

  2. VERIFY all fixtures (offline, deterministic, CI-safe):
         python tools/golden_check.py verify
     Replays every fixture's frozen HTML through the CURRENT extraction code
     and fails if any expected value no longer matches. Exit code 1 on
     mismatch - wire it next to accuracy_check in your release gate.

expected.json format:
    {"fields": {"products[0].name": "Serum",
                "products[0].price.current": 2750,
                "products[0].price.currency": "PKR",
                "collectionSummary.productCount": 10}}
Paths are dotted, with [n] for list indices. Values compare exactly
(numbers compare numerically: 2750 == 2750.0).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
FIXTURES = Path(__file__).resolve().parent / "golden_fixtures"


# ---------------------------------------------------------------------------
# Offline replay: frozen HTML -> full extraction result (no fetch, no LLM)
# ---------------------------------------------------------------------------

def replay_extraction(html: str, url: str) -> dict:
    """Run the analyzer's extraction stack on frozen HTML (mirrors main.py's
    direct path, minus fetching / retries / LLM fallback)."""
    import os
    os.environ.setdefault("URL_HISTORY", "off")
    from level1_detector.platform_detector import detect_platform
    from level1_detector.page_type_detector import detect_page_type
    from main import choose_analyzer
    from post_processors.competitive_schema import normalize_for_competitive_analysis

    headers = {"status_code": 200, "fetch_method": "golden_replay"}
    platform_result = detect_platform(html=html, url=url, headers=headers)
    page_type_result = detect_page_type(html=html, url=url, platform=platform_result.get("platform", ""))
    analyzer = choose_analyzer(platform_result.get("platform"), platform_result.get("platformConfidence", 1.0))
    result = analyzer.analyze(
        url=url, html=html, headers=headers,
        page_type=page_type_result.get("pageType", "general"),
        level1={**platform_result, **page_type_result},
    )
    result["level1"] = {**platform_result, **page_type_result, **(result.get("level1") or {})}
    result["success"] = True
    result["crawl"] = {"success": True, "blocked": False, "crawlBlocked": False, "statusCode": 200}
    return normalize_for_competitive_analysis(result)


# ---------------------------------------------------------------------------
# Dotted-path lookup + comparison
# ---------------------------------------------------------------------------

_PATH_TOKEN = re.compile(r"([^.\[\]]+)|\[(\d+)\]")


def lookup(data, path: str):
    current = data
    for m in _PATH_TOKEN.finditer(path):
        key, idx = m.group(1), m.group(2)
        try:
            if idx is not None:
                current = current[int(idx)]
            else:
                current = current.get(key) if isinstance(current, dict) else None
        except (IndexError, TypeError, AttributeError):
            return None
        if current is None:
            return None
    return current


def values_equal(expected, actual) -> bool:
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return abs(float(expected) - float(actual)) < 1e-9
    if isinstance(expected, str) and isinstance(actual, str):
        return " ".join(expected.split()).lower() == " ".join(actual.split()).lower()
    return expected == actual


# ---------------------------------------------------------------------------
# Default expected-field templates per page type (pre-fill for human review)
# ---------------------------------------------------------------------------

def suggest_expected(result: dict) -> dict:
    page_type = (result.get("page") or {}).get("pageType")
    fields = {}

    def put(path):
        value = lookup(result, path)
        if value is not None and value != [] and value != {}:
            fields[path] = value

    put("page.pageType")
    put("platform")
    if page_type == "product":
        for path in ["products[0].name", "products[0].handle", "products[0].price.current",
                     "products[0].price.currency", "products[0].price.compareAt",
                     "products[0].vendor", "products[0].productType"]:
            put(path)
        variants = lookup(result, "products[0].variants")
        if isinstance(variants, list) and variants:
            fields["products[0].variants.__len__"] = len(variants)
    elif page_type == "collection":
        for path in ["collectionSummary.name", "collectionSummary.productCount",
                     "products[0].name", "products[0].price.current", "products[0].price.currency",
                     "products[1].name", "products[1].price.current", "products[1].price.currency",
                     "products[0].price.compareAt"]:
            put(path)
        products = result.get("products") or []
        if products:
            fields["products.__len__"] = len(products)
    elif page_type == "homepage":
        for path in ["content.siteName", "homepage.siteName"]:
            put(path)
        sections = lookup(result, "content.sections")
        if isinstance(sections, list) and sections:
            fields["content.sections.__len__"] = len(sections)
    else:
        put("pricing.currency")
        put("pricing.pricingModel")
        plans = lookup(result, "pricing.plans")
        if isinstance(plans, list) and plans:
            fields["pricing.plans.__len__"] = len(plans)
            for i in range(min(6, len(plans))):
                put(f"pricing.plans[{i}].name")
                put(f"pricing.plans[{i}].price.amount")
                put(f"pricing.plans[{i}].price.currency")
                put(f"pricing.plans[{i}].price.raw")
                put(f"pricing.plans[{i}].price.period")
    return fields


def lookup_with_len(result, path):
    if path.endswith(".__len__"):
        target = lookup(result, path[: -len(".__len__")])
        return len(target) if isinstance(target, list) else None
    return lookup(result, path)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_record(url: str) -> None:
    from main import normalize_url
    from level1_detector.fetcher import fetch_html
    input_url = normalize_url(url)
    print(f"Fetching {input_url} ...")
    html, final_url, headers = fetch_html(input_url)
    if not html:
        print("Fetch failed - cannot record fixture.")
        sys.exit(1)

    result = replay_extraction(html, final_url)
    name = re.sub(r"[^a-z0-9]+", "-", final_url.split("//", 1)[1].lower()).strip("-")[:70]
    fixture_dir = FIXTURES / name
    fixture_dir.mkdir(parents=True, exist_ok=True)
    (fixture_dir / "page.html").write_text(html, encoding="utf-8")
    (fixture_dir / "meta.json").write_text(json.dumps({
        "url": final_url, "recordedAt": __import__("time").strftime("%Y-%m-%dT%H:%M:%S"),
        "pageType": (result.get("page") or {}).get("pageType"),
        "platform": result.get("platform"),
    }, indent=2), encoding="utf-8")
    expected = {"_instructions": "VERIFY each value against the real page in your browser. "
                                 "Fix wrong values, delete fields you don't want checked.",
                "fields": suggest_expected(result)}
    (fixture_dir / "expected.json").write_text(json.dumps(expected, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Fixture recorded: {fixture_dir}")
    print("NOW: open expected.json and confirm every value against the live page.")
    for k, v in expected["fields"].items():
        print(f"    {k} = {v!r}")


def cmd_verify() -> None:
    fixtures = sorted(d for d in FIXTURES.iterdir() if d.is_dir()) if FIXTURES.exists() else []
    if not fixtures:
        print("No fixtures found. Record one first: python tools/golden_check.py record <url>")
        return

    total_fields = failed_fields = 0
    failures = []
    for fixture_dir in fixtures:
        html_path, expected_path = fixture_dir / "page.html", fixture_dir / "expected.json"
        if not html_path.exists() or not expected_path.exists():
            continue
        meta = json.loads((fixture_dir / "meta.json").read_text(encoding="utf-8")) if (fixture_dir / "meta.json").exists() else {}
        expected = json.loads(expected_path.read_text(encoding="utf-8")).get("fields") or {}
        print(f"[{fixture_dir.name}] {meta.get('url', '')}")
        try:
            result = replay_extraction(html_path.read_text(encoding="utf-8"), meta.get("url") or "https://fixture.local/")
        except Exception as exc:
            import traceback
            print(f"    CRASH during replay: {exc}")
            traceback.print_exc()
            failures.append({"fixture": fixture_dir.name, "field": "<replay>", "error": str(exc)})
            failed_fields += len(expected)
            total_fields += len(expected)
            continue
        for path, want in expected.items():
            total_fields += 1
            got = lookup_with_len(result, path)
            if values_equal(want, got):
                print(f"    ok   {path} = {want!r}")
            else:
                failed_fields += 1
                failures.append({"fixture": fixture_dir.name, "field": path, "expected": want, "got": got})
                print(f"    FAIL {path}: expected {want!r}, got {got!r}")

    print("\n" + "=" * 60)
    print(f"Fixtures: {len(fixtures)}  |  Fields checked: {total_fields}  |  Failed: {failed_fields}")
    report = {"generatedAt": __import__("time").strftime("%Y-%m-%dT%H:%M:%S"),
              "fixtures": len(fixtures), "fieldsChecked": total_fields,
              "fieldsFailed": failed_fields, "failures": failures}
    (FIXTURES / "golden_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    sys.exit(1 if failed_fields else 0)


def main() -> None:
    if len(sys.argv) >= 3 and sys.argv[1] == "record":
        cmd_record(sys.argv[2])
    elif len(sys.argv) >= 2 and sys.argv[1] == "verify":
        cmd_verify()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
