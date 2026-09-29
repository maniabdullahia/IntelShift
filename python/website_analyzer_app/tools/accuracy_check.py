"""Analyzer Accuracy Scorecard.

Runs the full analyzer on a list of URLs and produces a per-page and overall
accuracy report, so you can verify extraction quality before releases and
catch regressions after changes.

Usage (from website_analyzer_app/):
    python tools/accuracy_check.py urls.txt
    python tools/accuracy_check.py training/shopify_urls.json
    python tools/accuracy_check.py output/url_history.jsonl
    python tools/accuracy_check.py https://example.com/collections/x https://example.com/

Input formats:
    - .txt   : one URL per line (# comments allowed)
    - .json  : ["url", ...]  or  {"urls": [...]}  or  [{"url": ...}, ...]
    - .json  : {"homepage": [...], "collection": [...], "product": [...], "blog": [...], "general": [...]}
               (grouped packs carry an expected page type per URL, which is
                verified against the detected page type)
    - .jsonl : URL history log written by the analyzer (output/url_history.jsonl)
    - URLs directly as arguments

Flags:
    --min-score=0.5   threshold for the failing-pages list / exit code
    --limit=20        only run the first N URLs

Output:
    - console table (one row per URL)
    - accuracy_report.json next to the input file (full details)

Exit code 1 if any page scores below --min-score, so it can run in CI or a
batch file.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


# ---------------------------------------------------------------------------
# Per-page checks (page-type aware)
# ---------------------------------------------------------------------------

# Page types that are close enough to count as a match for expected-type checks.
PAGE_TYPE_EQUIVALENTS = {
    "homepage": {"homepage", "home"},
    "collection": {"collection", "category"},
    "product": {"product"},
    "blog": {"blog", "article", "post", "blogListing", "blogPost"},
    "general": {"general", "pricing", "service", "services", "about", "contact", "unknown"},
}


def _is_brandish(name, og_site_name):
    n = (name or "").strip().lower()
    return bool(n) and bool(og_site_name) and n == (og_site_name or "").strip().lower()


# Pack filename -> expected platform family. "custom" means the pack contains
# custom-built sites where platform "Unknown" is the CORRECT answer.
PACK_PLATFORM_HINTS = {
    "shopify": {"Shopify"},
    "wordpress": {"WordPress", "WooCommerce / WordPress"},
    "wix": {"Wix"},
    "unknown": {"custom"},
}


def check_result(url: str, result: dict, expected_page_type: str | None = None,
                 expected_platform: set | None = None, expect_blocked: bool = False) -> dict:
    """Compute accuracy checks for one analyzed page.

    expected_platform: set of acceptable platform names, or {"custom"} meaning
    "Unknown" is correct (platform checks become verification instead of a
    blind detected/confident requirement).
    expect_blocked: this URL is a known-blocked regression site - a blocked
    outcome counts as PASS.
    """
    page = result.get("page") or {}
    crawl = result.get("crawl") or {}
    level1 = result.get("level1") or {}
    seo = result.get("seo") or {}
    og = result.get("openGraph") or {}
    eq = ((result.get("analysisReady") or {}).get("extractionQuality") or {})

    # Crash guard: some extractions emit non-dict entries in products
    # (this used to abort the entire row with "'str' object has no attribute 'get'").
    raw_products = result.get("products") or []
    products = [p for p in raw_products if isinstance(p, dict)]
    dropped_products = len(raw_products) - len(products)

    page_type = page.get("pageType") or "unknown"
    checks: dict[str, bool] = {}
    warnings: list[str] = []

    if dropped_products:
        warnings.append(f"{dropped_products} non-dict product entries in analyzer output (extraction bug)")

    # Universal checks
    is_blocked_outcome = result.get("status") == "website_blocked" or page_type == "blocked" or bool(crawl.get("crawlBlocked"))
    if expect_blocked:
        # Known-blocked regression site: verify the analyzer reports the
        # blocked contract instead of failing every content check.
        checks["expected_blocked_honored"] = (
            is_blocked_outcome and (result.get("status") == "website_blocked" or bool(result.get("blocked")))
        ) or bool(crawl.get("success"))  # bonus: site actually worked this run
        return {
            "url": url,
            "expectedPageType": expected_page_type,
            "pageType": page_type,
            "platform": result.get("platform"),
            "platformConfidence": level1.get("platformConfidence"),
            "pageTypeConfidence": level1.get("pageTypeConfidence"),
            "isHeadless": level1.get("isHeadless"),
            "extractionMethod": result.get("extractionMethod") or "requests",
            "expectBlocked": True,
            "checksPassed": sum(1 for v in checks.values() if v),
            "checksTotal": len(checks),
            "checkScore": round(sum(1 for v in checks.values() if v) / max(1, len(checks)), 3),
            "checks": checks,
            "warnings": warnings,
            "productCount": len(products),
        }
    checks["crawl_ok"] = bool(crawl.get("success")) and not crawl.get("crawlBlocked", False)
    if crawl.get("crawlBlocked"):
        warnings.append(f"crawler blocked (fallback: {result.get('extractionMethod') or 'unknown'})")
    detected_platform = result.get("platform")
    if expected_platform and "custom" in expected_platform:
        # Custom-platform pack: "Unknown" is the right answer, and framework
        # labels (Next.js/React/Vue) are correct too - identifying the frontend
        # framework of a custom site is useful, not a hallucination.
        _acceptable_custom = {None, "", "Unknown", "Next.js / React", "React", "Vue"}
        checks["platform_correctly_unknown"] = (
            detected_platform in _acceptable_custom or bool(level1.get("isHeadless"))
        )
        if not checks["platform_correctly_unknown"]:
            warnings.append(f"custom-site pack but detector claims platform {detected_platform!r} - verify (may belong in another pack)")
    elif expected_platform:
        checks["platform_matches_expected"] = detected_platform in expected_platform
        if not checks["platform_matches_expected"]:
            warnings.append(f"expected platform {sorted(expected_platform)} but detected {detected_platform!r} - wrong-platform pack entry or detection miss")
        checks["platform_confident"] = (level1.get("platformConfidence") or 0) >= 0.65
    else:
        checks["platform_detected"] = bool(detected_platform) and detected_platform != "Unknown"
        checks["platform_confident"] = (level1.get("platformConfidence") or 0) >= 0.65
    checks["page_type_confident"] = (level1.get("pageTypeConfidence") or 0) >= 0.65
    checks["seo_title"] = bool(seo.get("title"))
    # Missing h1 on a HOMEPAGE is usually a theme choice (logo image as h1,
    # hero without heading) — record it as an SEO observation, not an
    # extraction failure that drags checkScore down. On product/collection
    # pages a missing h1 still counts as a real check.
    if page_type == "homepage":
        if not seo.get("h1"):
            warnings.append("seo: no h1 on homepage (informational, not scored)")
    else:
        checks["seo_h1"] = bool(seo.get("h1"))

    # Expected-page-type verification (grouped packs provide ground truth).
    if expected_page_type:
        allowed = PAGE_TYPE_EQUIVALENTS.get(expected_page_type, {expected_page_type})
        checks["page_type_matches_expected"] = page_type in allowed
        if not checks["page_type_matches_expected"]:
            warnings.append(f"page type mismatch: expected {expected_page_type!r}, detected {page_type!r}")

    # Served content should relate to the requested domain (catches parked or
    # redirected domains, e.g. a .pk store URL serving a different business).
    import re as _re
    domain_core = ""
    target = page.get("url") or url
    if "//" in target:
        host = target.split("//", 1)[1].split("/", 1)[0].replace("www.", "").replace("www2.", "")
        domain_core = host.rsplit(".", 2)[0] if host.count(".") >= 2 else host.split(".")[0]
    site_text = " ".join(str(x or "") for x in [
        seo.get("title"), og.get("site_name"), (result.get("content") or {}).get("siteName"),
    ]).lower().strip()
    # Normalize "&" ↔ "and" before comparing: "blk & bold" must match
    # "blkandbold", "poly & bark" must match "polyandbark".
    # Also fold accents so "grüum" matches gruum.com (ü → u).
    import unicodedata as _ud
    site_text_folded = _ud.normalize("NFKD", site_text).encode("ascii", "ignore").decode("ascii")
    site_text_norm = site_text_folded.replace("&", " and ")
    domain_tokens = set(_re.sub(r"[^a-z0-9]+", " ", domain_core.lower()).split())
    # Skip the mismatch check when it can only produce noise:
    # - fallback extractions (Jina/Firecrawl/OpenAI) often return bare page
    #   titles without the brand ("matte lip kit" on kyliecosmetics.com)
    # - very short/generic titles ("All", "Products") carry no brand signal
    _GENERIC_TITLES = {"all", "products", "shop", "collections", "collection",
                       "home", "homepage", "new arrivals", "store"}
    _site_joined_len = len(_re.sub(r"[^a-z0-9]+", "", site_text))
    _mismatch_checkable = (
        not crawl.get("crawlBlocked")
        and _site_joined_len >= 6
        and site_text not in _GENERIC_TITLES
    )
    if domain_core and site_text and domain_tokens and _mismatch_checkable:
        joined = _re.sub(r"[^a-z0-9]+", "", site_text_norm)
        joined_no_and = joined.replace("and", "")
        domain_joined = _re.sub(r"[^a-z0-9]+", "", domain_core.lower())
        domain_joined_no_and = domain_joined.replace("and", "")
        site_words = [w for w in _re.sub(r"[^a-z0-9]+", " ", site_text_norm).split() if len(w) >= 5]
        overlap = (
            any(t in joined or t in joined_no_and for t in domain_tokens if len(t) >= 4)
            or any(t in site_text for t in domain_tokens)
            or any(w in domain_joined or w in domain_joined_no_and for w in site_words)   # "goodee" in "goodeeworld"
            or (len(domain_joined) >= 6 and (domain_joined in joined or domain_joined_no_and in joined_no_and))
        )
        if not overlap:
            warnings.append(
                f"content/domain mismatch: '{domain_core}' vs site text {site_text[:60]!r} - domain may be parked or redirected"
            )

    # Page-type specific checks
    if page_type == "collection":
        cs = result.get("collectionSummary") or {}
        checks["has_products"] = len(products) > 0
        priced = [p for p in products if isinstance(p.get("price"), dict) and p["price"].get("current") is not None]
        curr = {p["price"].get("currency") for p in priced if p["price"].get("currency")}
        if products:
            # only scored when products exist - an empty collection already
            # failed has_products; failing price/currency too triple-counts it
            checks["price_coverage_80"] = len(priced) / len(products) >= 0.8
            checks["currency_detected"] = bool(curr)
        checks["collection_name_ok"] = bool(cs.get("name")) and not _is_brandish(cs.get("name"), og.get("site_name"))
        if not checks["collection_name_ok"]:
            warnings.append(f"collection name looks wrong: {cs.get('name')!r}")
        urls_set = {p.get("productUrl") or p.get("url") for p in products} - {None, ""}
        checks["distinct_product_urls"] = len(products) <= 1 or len(urls_set) > 1
        if not checks["distinct_product_urls"]:
            warnings.append("all products share ONE url (identity collapse risk)")
        tld = (page.get("url") or url).split("/")[2].rsplit(".", 1)[-1] if "//" in (page.get("url") or url) else ""
        if "USD" in curr and tld == "pk":
            warnings.append("USD currency on a .pk domain - verify")

    elif page_type == "product":
        p0 = products[0] if products else {}
        checks["has_product"] = bool(p0)
        checks["product_name"] = bool(p0.get("name") or p0.get("title"))
        price = p0.get("price") or {}
        checks["product_price"] = isinstance(price, dict) and price.get("current") is not None
        checks["product_description"] = bool(p0.get("description") or p0.get("shortDescription"))
        checks["product_images"] = bool(p0.get("imageUrl") or p0.get("additionalImageUrls"))

    elif page_type == "homepage":
        content = result.get("content") or {}
        nav = result.get("navigation") or {}
        checks["has_sections"] = len(content.get("sections") or []) >= 3
        checks["has_nav_links"] = len(nav.get("links") or []) >= 3
        hs = result.get("homepage") or result.get("homepageSummary") or result.get("homepageStrategy") or {}
        checks["homepage_summary"] = bool(hs)
        checks["site_name"] = bool(
            (hs.get("siteName") if isinstance(hs, dict) else None)
            or content.get("siteName") or og.get("site_name")
        )

    else:  # general / pricing / blog / service
        pricing = result.get("pricing") or {}
        saas = result.get("saas") or {}
        content = result.get("content") or {}
        checks["has_main_text"] = len(str(content.get("mainText") or "")) >= 200
        if pricing.get("hasPricing") or saas.get("hasPricing") or "pricing" in url.lower() or "license" in url.lower():
            plans = pricing.get("plans") or []
            checks["pricing_plans_extracted"] = len(plans) > 0
            checks["plan_prices_extracted"] = any(
                isinstance((pl.get("price") or {}).get("amount"), (int, float)) for pl in plans if isinstance(pl, dict)
            )

    # Consistency flags from the analyzer's own scoring
    flags = ((eq.get("dataConsistency") or {}).get("flags")) or []
    for f in flags:
        warnings.append(f"consistency flag: {f}")

    passed = sum(1 for v in checks.values() if v)
    resp_headers = (result.get("technical") or {}).get("responseHeaders") or {}
    return {
        "url": url,
        "expectedPageType": expected_page_type,
        "pageType": page_type,
        "status": result.get("status"),
        "blockedReason": result.get("blockedReason"),
        "platform": result.get("platform"),
        "platformConfidence": level1.get("platformConfidence"),
        "pageTypeConfidence": level1.get("pageTypeConfidence"),
        "isHeadless": level1.get("isHeadless"),
        "extractionMethod": result.get("extractionMethod") or "requests",
        "fetchMethod": resp_headers.get("fetch_method"),
        "forcedPlaywright": bool(resp_headers.get("forced_playwright")) or None,
        "forcedPlaywrightReason": resp_headers.get("forced_playwright_reason"),
        "priceRetry": resp_headers.get("price_retry"),
        "qualityScore": eq.get("score"),
        "qualityBucket": eq.get("qualityBucket"),
        "checksPassed": passed,
        "checksTotal": len(checks),
        "checkScore": round(passed / max(1, len(checks)), 3),
        "checks": checks,
        "warnings": warnings,
        "productCount": len(products),
    }


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

GROUPED_JSON_KEYS = ("homepage", "collection", "product", "blog", "general")


def _add_url_entry(entries: list[dict], url: str, expected_page_type: str | None = None, source: str | None = None) -> None:
    """Append one URL entry in a consistent internal format."""
    url = (url or "").strip()
    if not url or not url.startswith("http"):
        return
    entries.append({
        "url": url,
        "expectedPageType": expected_page_type,
        "source": source,
        "expectedPlatform": None,
        "expectBlocked": False,
    })


def _parse_json_url_items(data, entries: list[dict], expected_page_type: str | None = None, source: str | None = None) -> None:
    """Parse common URL JSON shapes into entries.

    Supported shapes:
    - ["https://...", ...]
    - [{"url": "https://..."}, ...]
    - {"urls": [...]}
    - {"homepage": [...], "collection": [...], "product": [...], "blog": [...], "general": [...]}
    """
    if isinstance(data, str):
        _add_url_entry(entries, data, expected_page_type, source)
        return

    if isinstance(data, list):
        for item in data:
            _parse_json_url_items(item, entries, expected_page_type, source)
        return

    if isinstance(data, dict):
        if data.get("url"):
            _add_url_entry(
                entries,
                data.get("url"),
                data.get("expectedPageType") or data.get("pageType") or expected_page_type,
                data.get("source") or source,
            )
            if entries and data.get("expectBlocked"):
                entries[-1]["expectBlocked"] = True
            return

        # Existing simple format: {"urls": [...]}
        if isinstance(data.get("urls"), list):
            _parse_json_url_items(data["urls"], entries, expected_page_type, source or "urls")

        # Baseline pack format created for platform tests.
        for key in GROUPED_JSON_KEYS:
            if isinstance(data.get(key), list):
                _parse_json_url_items(data[key], entries, key, key)

        # Be forgiving with future packs that may add other list buckets such as
        # "pricing", "service", "about", or "careers".
        for key, value in data.items():
            if key in {"urls", *GROUPED_JSON_KEYS}:
                continue
            if isinstance(value, list):
                _parse_json_url_items(value, entries, key, key)


def _parse_jsonl_history(path: Path, entries: list[dict]) -> None:
    """Parse output/url_history.jsonl written by the analyzer.

    Each line: {"ts": ..., "url": ..., "pageType": ..., ...}
    The most recent entry per URL wins. The logged pageType is DETECTED (not
    ground truth), so it is carried as source info only, not as expected type.
    """
    latest: dict[str, dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict) and item.get("url"):
            latest[item["url"]] = item
    for url in latest:
        _add_url_entry(entries, url, None, path.name)


def dedupe_entries(entries: list[dict]) -> list[dict]:
    """Deduplicate URLs while preserving first-seen order and metadata."""
    seen: set[str] = set()
    unique: list[dict] = []
    for entry in entries:
        url = entry.get("url")
        if not url or url in seen:
            continue
        seen.add(url)
        unique.append(entry)
    return unique


def load_known_issues() -> list[dict]:
    """tools/known_issues.json: triaged failures that should not gate a run."""
    path = Path(__file__).resolve().parent / "known_issues.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return [i for i in (data.get("issues") or []) if isinstance(i, dict) and i.get("urlPrefix")]
    except Exception:
        return []


def match_known_issues(url: str, failed_checks: list, known: list[dict]) -> tuple[list, list, str]:
    """Split failed checks into (new, known, reason)."""
    for issue in known:
        if url.startswith(issue["urlPrefix"]):
            covered = set(issue.get("checks") or [])
            if "*" in covered:
                return [], list(failed_checks), issue.get("reason") or "accepted"
            known_f = [c for c in failed_checks if c in covered]
            new_f = [c for c in failed_checks if c not in covered]
            if known_f:
                return new_f, known_f, issue.get("reason") or "accepted"
    return list(failed_checks), [], ""


def load_url_entries(args: list[str]) -> list[dict]:
    entries: list[dict] = []
    for a in args:
        if a.startswith("http"):
            _add_url_entry(entries, a)
            continue

        path = Path(a)
        if not path.exists():
            print(f"skip (not found): {a}")
            continue

        if path.suffix.lower() == ".jsonl":
            _parse_jsonl_history(path, entries)
        elif path.suffix.lower() == ".json":
            data = json.loads(path.read_text(encoding="utf-8"))
            before = len(entries)
            _parse_json_url_items(data, entries, source=path.name)
            # Pack filename tells us the expected platform family
            # (shopify_urls.json -> Shopify, unknown_urls.json -> custom, ...)
            stem = path.stem.lower()
            hint = next((v for k, v in PACK_PLATFORM_HINTS.items() if k in stem), None)
            # Optional "expectBlocked": [urls...] bucket for the regression set
            blocked_set = set()
            if isinstance(data, dict):
                blocked_set = {u for u in (data.get("expectBlocked") or []) if isinstance(u, str)}
            for entry in entries[before:]:
                if hint:
                    entry["expectedPlatform"] = hint
                if entry["url"] in blocked_set:
                    entry["expectBlocked"] = True
        else:
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    _add_url_entry(entries, line, source=path.name)

    return dedupe_entries(entries)


def load_urls(args: list[str]) -> list[str]:
    """Backward-compatible helper returning only URL strings."""
    return [entry["url"] for entry in load_url_entries(args)]


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    min_score = 0.5
    limit: int | None = None
    for a in sys.argv[1:]:
        if a.startswith("--min-score="):
            min_score = float(a.split("=", 1)[1])
        elif a.startswith("--limit="):
            limit = int(a.split("=", 1)[1])

    entries = load_url_entries(args)
    if limit is not None:
        entries = entries[:limit]

    if not entries:
        print(__doc__)
        return

    from main import analyze_url  # heavy import, defer until needed

    known_issues = load_known_issues()
    rows = []
    for i, entry in enumerate(entries, 1):
        url = entry["url"]
        expected_page_type = entry.get("expectedPageType")
        expected_label = f" expected={expected_page_type}" if expected_page_type else ""
        print(f"[{i}/{len(entries)}] {url}{expected_label}")
        started = time.time()
        try:
            result = analyze_url(url)
            row = check_result(
                url, result,
                expected_page_type=expected_page_type,
                expected_platform=entry.get("expectedPlatform"),
                expect_blocked=bool(entry.get("expectBlocked")),
            )
        except Exception as exc:
            import traceback as _tb
            _trace = _tb.format_exc()
            print(_trace)
            row = {"url": url, "expectedPageType": expected_page_type, "pageType": "ERROR", "checkScore": 0.0,
                   "qualityScore": 0,
                   "warnings": [f"exception: {exc}", f"traceback: {_trace.strip().splitlines()[-8:]}"],
                   "checks": {}, "checksPassed": 0, "checksTotal": 0}
        row["source"] = entry.get("source")
        row["seconds"] = round(time.time() - started, 1)
        failed_all = [k for k, v in (row.get("checks") or {}).items() if not v]
        new_failed, known_failed, known_reason = match_known_issues(url, failed_all, known_issues)
        if known_failed:
            row["knownFailures"] = known_failed
            row["knownIssueReason"] = known_reason
        row["newFailures"] = new_failed
        rows.append(row)
        failed = failed_all
        print(f"    type={row.get('pageType')} expected={row.get('expectedPageType')} platform={row.get('platform')} "
              f"quality={row.get('qualityScore')} checks={row.get('checksPassed')}/{row.get('checksTotal')} "
              f"({row['seconds']}s)"
              + (f"  NEW FAILURES: {', '.join(new_failed)}" if new_failed else "")
              + (f"  [known: {', '.join(known_failed)} - {known_reason}]" if known_failed else ""))
        for w in row.get("warnings") or []:
            print(f"    ! {w}")

    # Summary
    scored = [r for r in rows if r.get("checksTotal")]
    avg_check = round(sum(r["checkScore"] for r in scored) / len(scored), 3) if scored else 0
    quality_vals = [r["qualityScore"] for r in rows if isinstance(r.get("qualityScore"), (int, float))]
    avg_quality = round(sum(quality_vals) / len(quality_vals), 3) if quality_vals else None
    weak = [r for r in rows if r.get("checkScore", 0) < min_score]
    # Gate the run on NEW failures only: a page below threshold whose failures
    # are all triaged/known does not fail the exit code.
    gating = [r for r in weak if r.get("newFailures")]
    known_only_weak = [r for r in weak if not r.get("newFailures")]

    # Aggregated diagnostics - these turn the report into a fix list.
    def _avg(vals):
        vals = [v for v in vals if isinstance(v, (int, float))]
        return round(sum(vals) / len(vals), 3) if vals else None

    by_page_type: dict = {}
    for r in scored:
        by_page_type.setdefault(r.get("pageType"), []).append(r)
    by_page_type_summary = {
        pt: {"pages": len(rs), "avgCheckScore": _avg([x["checkScore"] for x in rs]),
             "avgQuality": _avg([x.get("qualityScore") for x in rs])}
        for pt, rs in sorted(by_page_type.items(), key=lambda x: -len(x[1]))
    }

    by_method: dict = {}
    for r in rows:
        by_method.setdefault(r.get("extractionMethod") or "requests", []).append(r)
    by_method_summary = {
        m: {"pages": len(rs), "avgCheckScore": _avg([x.get("checkScore") for x in rs]),
            "avgQuality": _avg([x.get("qualityScore") for x in rs])}
        for m, rs in sorted(by_method.items(), key=lambda x: -len(x[1]))
    }

    check_fails: dict = {}
    check_totals: dict = {}
    for r in rows:
        for k, v in (r.get("checks") or {}).items():
            check_totals[k] = check_totals.get(k, 0) + 1
            if not v:
                check_fails[k] = check_fails.get(k, 0) + 1
    check_failure_rates = {
        k: {"failed": n, "of": check_totals[k], "rate": round(n / check_totals[k], 3)}
        for k, n in sorted(check_fails.items(), key=lambda x: -x[1])
    }

    flag_counts: dict = {}
    for r in rows:
        for w in r.get("warnings") or []:
            if w.startswith("consistency flag:"):
                key = w.split(":", 1)[1].strip()
                flag_counts[key] = flag_counts.get(key, 0) + 1

    price_retry_counts: dict = {}
    for r in rows:
        pr = r.get("priceRetry")
        if pr:
            price_retry_counts[pr] = price_retry_counts.get(pr, 0) + 1

    headless_sites = sorted({r["url"].split("/")[2] for r in rows if r.get("isHeadless")})
    type_mismatches = [
        {"url": r["url"], "expected": r.get("expectedPageType"), "detected": r.get("pageType")}
        for r in rows
        if r.get("checks", {}).get("page_type_matches_expected") is False
    ]

    print("\n" + "=" * 60)
    print(f"Pages analyzed : {len(rows)}")
    print(f"Avg check score: {avg_check}  |  Avg analyzer quality: {avg_quality}")
    print(f"Below {min_score}: {len(weak)}"
          + (f"  (gating: {len(gating)}, known-issue-only: {len(known_only_weak)})" if weak else ""))
    if gating:
        print("  GATING (new failures): " + ", ".join(r["url"] for r in gating))
    if known_only_weak:
        print("  known-issue-only: " + ", ".join(r["url"] for r in known_only_weak))
    print("\nBy page type:")
    for pt, info in by_page_type_summary.items():
        print(f"  {pt}: n={info['pages']} check={info['avgCheckScore']} quality={info['avgQuality']}")
    print("By extraction method:")
    for m, info in by_method_summary.items():
        print(f"  {m}: n={info['pages']} check={info['avgCheckScore']} quality={info['avgQuality']}")
    if check_failure_rates:
        print("Top failing checks:")
        for k, info in list(check_failure_rates.items())[:8]:
            print(f"  {k}: {info['failed']}/{info['of']} ({info['rate']:.0%})")
    if flag_counts:
        print("Consistency flags:", flag_counts)
    if price_retry_counts:
        print("Price-retry outcomes:", price_retry_counts)
    if headless_sites:
        print("Headless storefronts:", ", ".join(headless_sites))
    if type_mismatches:
        print("Page-type mismatches:")
        for m in type_mismatches[:10]:
            print(f"  expected {m['expected']} -> detected {m['detected']} | {m['url'][:60]}")

    out_path = Path(args[0]).with_suffix(".accuracy_report.json") if args and Path(args[0]).exists() else Path("accuracy_report.json")
    out_path.write_text(json.dumps({
        "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "averageCheckScore": avg_check,
        "averageQualityScore": avg_quality,
        "pagesBelowThreshold": [r["url"] for r in weak],
        "gatingPages": [r["url"] for r in gating],
        "knownIssueOnlyPages": [r["url"] for r in known_only_weak],
        "byPageType": by_page_type_summary,
        "byExtractionMethod": by_method_summary,
        "checkFailureRates": check_failure_rates,
        "consistencyFlagCounts": flag_counts,
        "priceRetryOutcomes": price_retry_counts,
        "headlessSites": headless_sites,
        "pageTypeMismatches": type_mismatches,
        "rows": rows,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Report: {out_path}")

    sys.exit(1 if gating else 0)


if __name__ == "__main__":
    main()
