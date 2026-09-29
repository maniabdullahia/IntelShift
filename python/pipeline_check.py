"""Downstream Pipeline Robustness Check (merger -> comparison -> change detection -> AI payload).

The accuracy_check equivalent for the three apps AFTER the analyzer: feed it a
folder of real analyzer output JSONs and it exercises the full pipeline,
catching crashes and validating invariants at every stage.

Usage (from the project root):
    python pipeline_check.py <folder-with-analyzer-outputs> [more folders/files...]
    python pipeline_check.py --fuzz-only

Stages:
    1. MERGE      group pages by domain -> merge_page_jsons -> snapshot invariants
    2. COMPARE    first domain vs every other -> compare_sites -> invariants
    3. DIFF       self-diff every snapshot (must be 0 changes, score 0)
    4. AI PAYLOAD build_ai_payload + OpenAI request on one comparison
    5. FUZZ       malformed/hostile inputs must not crash any stage

Output: console + pipeline_check_report.json. Exit code 1 on any failure.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import time
import traceback
from pathlib import Path

BASE = Path(__file__).resolve().parent


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# merger + change detector are single-file modules -> load by path
merger = load_module("pc_merger", BASE / "competitor_merger_app" / "app" / "merger.py")
detector = load_module("pc_detector", BASE / "change_detection_app" / "app" / "detector.py")

# comparison engine uses package-relative imports -> import via sys.path
sys.path.insert(0, str(BASE / "comparison_app"))
from comparison_engine.comparator import compare_sites  # noqa: E402
ai_payload_mod = load_module("pc_ai_payload", BASE / "comparison_app" / "build_ai_payload.py")
openai_mod = load_module("pc_openai", BASE / "comparison_app" / "openai_insights.py")


FAILURES: list[dict] = []
CHECKS = {"passed": 0, "failed": 0}


def check(stage: str, name: str, condition: bool, detail: str = "") -> None:
    if condition:
        CHECKS["passed"] += 1
    else:
        CHECKS["failed"] += 1
        FAILURES.append({"stage": stage, "check": name, "detail": detail})
        print(f"  FAIL [{stage}] {name} {('- ' + detail) if detail else ''}")


def crash(stage: str, name: str, exc: Exception) -> None:
    CHECKS["failed"] += 1
    tb = traceback.format_exc().splitlines()[-6:]
    FAILURES.append({"stage": stage, "check": name, "detail": f"CRASH: {exc}", "traceback": tb})
    print(f"  CRASH [{stage}] {name}: {exc}")


# ---------------------------------------------------------------------------
# Invariant validators
# ---------------------------------------------------------------------------

def validate_snapshot(snap: dict, label: str) -> None:
    stage = "merge"
    check(stage, f"{label}: schemaVersion", snap.get("schemaVersion") == "site_snapshot_v2")
    site = snap.get("site") or {}
    check(stage, f"{label}: site.domain", bool(site.get("domain")) or not snap.get("pagesAnalyzed"))
    pages = snap.get("pagesAnalyzed") or []
    check(stage, f"{label}: pagesAnalyzedCount", site.get("pagesAnalyzedCount") == len(pages),
          f"{site.get('pagesAnalyzedCount')} != {len(pages)}")
    products = snap.get("products") or []
    check(stage, f"{label}: totalUniqueProducts", site.get("totalUniqueProducts") == len(products))
    check(stage, f"{label}: products are dicts", all(isinstance(p, dict) for p in products))
    for p in products[:200]:
        price = p.get("price")
        if price is not None:
            check(stage, f"{label}: price shape", isinstance(price, dict),
                  f"{p.get('name')}: {type(price).__name__}")
            if isinstance(price, dict) and "current" in price:
                check(stage, f"{label}: price.current numeric",
                      isinstance(price["current"], (int, float)), str(price)[:80])
        check(stage, f"{label}: sourcePages", isinstance(p.get("sourcePages"), list) and len(p["sourcePages"]) > 0,
              str(p.get("name"))[:40])
    raw = json.dumps(snap)
    check(stage, f"{label}: no _html leakage", "_html" not in raw and "_raw_product" not in raw)
    check(stage, f"{label}: no responseHeaders leakage", "responseHeaders" not in raw)


def validate_comparison(cmp_result: dict, label: str) -> None:
    stage = "compare"
    check(stage, f"{label}: schemaVersion", cmp_result.get("schemaVersion") == "comparison_engine_v5")
    check(stage, f"{label}: sites list", isinstance(cmp_result.get("sites"), list) and len(cmp_result["sites"]) >= 2)
    pc = cmp_result.get("priceComparison") or {}
    check(stage, f"{label}: sameCurrency bool", isinstance(pc.get("sameCurrency"), bool))
    ri = (cmp_result.get("rankedInsights") or {}).get("items")
    check(stage, f"{label}: rankedInsights list", isinstance(ri, list))
    # every matched product pair must be same inferred type (the category gate)
    for block in (cmp_result.get("oneToOneComparison") or {}).get("competitors", []):
        cw = block.get("catalogWideProductMatching") or {}
        for m in cw.get("topMatches") or []:
            ut = (m.get("userProduct") or {}).get("inferredType")
            ct = (m.get("competitorProduct") or {}).get("inferredType")
            if ut and ct:
                check(stage, f"{label}: category gate", ut == ct, f"{ut} vs {ct}")
    json.dumps(cmp_result)


def validate_self_diff(diff: dict, label: str) -> None:
    stage = "diff"
    check(stage, f"{label}: self-diff zero changes", diff.get("summary", {}).get("totalChanges") == 0,
          str(diff.get("summary", {}).get("changesByType")))
    check(stage, f"{label}: self-diff score 0", diff.get("changeScore") == 0)
    check(stage, f"{label}: self-diff no AI send", diff.get("shouldSendToAI") is False)


# ---------------------------------------------------------------------------
# Corpus loading
# ---------------------------------------------------------------------------

def load_corpus(paths: list[str]) -> dict[str, list[dict]]:
    """Group analyzer outputs by domain."""
    by_domain: dict[str, list[dict]] = {}
    files: list[Path] = []
    for a in paths:
        p = Path(a)
        if p.is_dir():
            files.extend(sorted(p.glob("*.json")))
        elif p.is_file():
            files.append(p)
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            print(f"  skip unreadable: {f.name}")
            continue
        if not isinstance(data, dict) or ("page" not in data and "inputUrl" not in data):
            continue  # not an analyzer output (report files etc.)
        url = ((data.get("page") or {}).get("url")) or data.get("inputUrl") or ""
        domain = url.split("/")[2].replace("www.", "") if "//" in url else f"unknown-{f.stem}"
        by_domain.setdefault(domain, []).append(data)
    return by_domain


# ---------------------------------------------------------------------------
# Fuzz cases (must never crash any stage)
# ---------------------------------------------------------------------------

def fuzz_cases() -> list:
    return [
        ("minimal page", [{"page": {"url": "https://x.com/", "pageType": "homepage"}}]),
        ("no page key", [{"inputUrl": "https://x.com/"}]),
        ("string products", [{"page": {"url": "https://x.com/c", "pageType": "collection"},
                              "products": ["junk", 42, None, {"name": "P"}]}]),
        ("string prices", [{"page": {"url": "https://x.com/c", "pageType": "collection"},
                            "products": [{"name": "P", "price": "$9.99"}, {"name": "Q", "price": 12}]}]),
        ("none values", [{"page": {"url": "https://x.com/", "pageType": "homepage"},
                          "seo": None, "content": None, "navigation": None, "products": None}]),
        ("blocked page", [{"status": "website_blocked", "success": False, "blockedReason": "bot_protection",
                           "userMessage": "blocked", "page": {"url": "https://x.com/", "pageType": "blocked"}}]),
        ("huge strings", [{"page": {"url": "https://x.com/", "pageType": "homepage"},
                           "content": {"mainText": "x" * 100000}}]),
        ("unicode junk", [{"page": {"url": "https://x.com/", "pageType": "general"},
                           "seo": {"title": " \U0001F600 café ☃"},
                           "products": [{"name": "❤️" * 50, "price": {"current": 1}}]}]),
        ("pricing no plans", [{"page": {"url": "https://x.com/pricing", "pageType": "general"},
                               "pricing": {"hasPricing": True, "plans": None}}]),
        ("weird price dicts", [{"page": {"url": "https://x.com/c", "pageType": "collection"},
                                "products": [{"name": "A", "price": {"current": "abc"}},
                                              {"name": "B", "price": {"current": [1, 2]}},
                                              {"name": "C", "price": {"compareAt": True}}]}]),
    ]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    fuzz_only = "--fuzz-only" in sys.argv

    snapshots: dict = {}

    if not fuzz_only and args:
        corpus = load_corpus(args)
        print(f"Corpus: {sum(len(v) for v in corpus.values())} analyzer outputs across {len(corpus)} domains\n")

        print("== STAGE 1: MERGE ==")
        for domain, pages in sorted(corpus.items()):
            try:
                snap = merger.merge_page_jsons(pages)
                snapshots[domain] = snap
                validate_snapshot(snap, domain)
                site = snap.get("site") or {}
                print(f"  ok {domain}: {len(pages)} pages -> {site.get('siteType')} "
                      f"{site.get('totalUniqueProducts')}p/{site.get('productsWithPrice')}priced"
                      + (f" [{snap.get('status')}]" if snap.get("status") else ""))
            except Exception as exc:
                crash("merge", domain, exc)

        print("\n== STAGE 2: COMPARE ==")
        domains = [d for d in snapshots if snapshots[d].get("status") != "website_blocked"]
        comparison = None
        if len(domains) >= 2:
            user = snapshots[domains[0]]
            for comp_domain in domains[1:]:
                try:
                    result = compare_sites(user, [snapshots[comp_domain]])
                    validate_comparison(result, f"{domains[0]} vs {comp_domain}")
                    if comparison is None:
                        comparison = result
                    print(f"  ok {domains[0]} vs {comp_domain}")
                except Exception as exc:
                    crash("compare", f"{domains[0]} vs {comp_domain}", exc)

        print("\n== STAGE 3: SELF-DIFF ==")
        for domain, snap in snapshots.items():
            try:
                diff = detector.detect_changes(snap, json.loads(json.dumps(snap)))
                validate_self_diff(diff, domain)
            except Exception as exc:
                crash("diff", domain, exc)
        print(f"  self-diffed {len(snapshots)} snapshots")

        print("\n== STAGE 4: AI PAYLOAD ==")
        if comparison is not None:
            try:
                payload = ai_payload_mod.build_ai_payload(comparison)
                check("ai", "payload schema", payload.get("schemaVersion") == "ai_payload_v4")
                request = openai_mod.build_openai_insights_request(comparison)
                req = request.get("openaiRequest") or {}
                check("ai", "openai request messages", len(req.get("messages") or []) == 2)
                check("ai", "strict schema", (req.get("response_format") or {}).get("json_schema", {}).get("strict") is True)
                reduction = 1 - request["approxPayloadCharacters"] / max(1, len(json.dumps(comparison)))
                print(f"  ok payload built (reduction {reduction:.0%})")
            except Exception as exc:
                crash("ai", "payload build", exc)

    print("\n== STAGE 5: FUZZ ==")
    for name, pages in fuzz_cases():
        try:
            snap = merger.merge_page_jsons(pages)
            json.dumps(snap)
            # snapshots must also survive comparison (vs a plain snapshot) and self-diff
            other = merger.merge_page_jsons([{"page": {"url": "https://other.com/", "pageType": "homepage"},
                                              "seo": {"title": "Other"}}])
            cmp_r = compare_sites(snap, [other])
            json.dumps(cmp_r)
            diff = detector.detect_changes(snap, json.loads(json.dumps(snap)))
            check("fuzz", f"{name}: self-diff clean", diff.get("summary", {}).get("totalChanges") == 0)
            ai_payload_mod.build_ai_payload(cmp_r)
            print(f"  ok fuzz: {name}")
        except Exception as exc:
            crash("fuzz", name, exc)

    print("\n" + "=" * 60)
    print(f"Checks passed: {CHECKS['passed']}  |  failed: {CHECKS['failed']}")
    report = {
        "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "checksPassed": CHECKS["passed"],
        "checksFailed": CHECKS["failed"],
        "failures": FAILURES,
    }
    Path("pipeline_check_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print("Report: pipeline_check_report.json")
    sys.exit(1 if CHECKS["failed"] else 0)


if __name__ == "__main__":
    main()
