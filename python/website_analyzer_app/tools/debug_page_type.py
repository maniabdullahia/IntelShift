"""Debug why the page-type detector classified a URL the way it did.

Usage:
    python tools/debug_page_type.py <url> [<url> ...]
    python tools/debug_page_type.py --expected product https://example.com/product/foo

Prints the detected page type, confidence, the decision rule that fired, and
the full signal breakdown — everything needed to fix a misclassification
without guessing.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> None:
    args = [a for a in sys.argv[1:] if a]
    expected = None
    if "--expected" in args:
        i = args.index("--expected")
        expected = args[i + 1]
        del args[i:i + 2]
    urls = [a for a in args if a.startswith("http")]
    if not urls:
        print(__doc__)
        return

    from level1_detector.fetcher import fetch_html
    from level1_detector.platform_detector import detect_platform
    from level1_detector.page_type_detector import detect_page_type

    for url in urls:
        print(f"\n{'=' * 70}\nURL: {url}")
        html, final_url, headers = fetch_html(url)
        if not html:
            print("  !! no HTML returned (blocked?) — headers:", json.dumps(headers or {})[:200])
            continue
        platform = detect_platform(html=html, url=final_url, headers=headers)
        pt = detect_page_type(html=html, url=final_url, platform=platform.get("platform", ""))

        print(f"  platform      : {platform.get('platform')} ({platform.get('platformConfidence')})")
        print(f"  pageType      : {pt.get('pageType')} ({pt.get('pageTypeConfidence')})"
              + (f"  [expected {expected}]" if expected else ""))
        if pt.get("generalSubtype"):
            print(f"  generalSubtype: {pt['generalSubtype']}")
        dbg = pt.get("pageTypeDebug") or {}
        print(f"  decision rule : {dbg.get('reason')}")
        print(f"  type scores   : {json.dumps(pt.get('pageTypeSignals') or {})}")
        signals = dbg.get("signals") or {}
        for group, val in signals.items():
            print(f"  {group}:")
            print("    " + json.dumps(val, default=str)[:600])
        if expected and pt.get("pageType") != expected:
            print("  >> MISMATCH — copy this whole block into the fix request.")


if __name__ == "__main__":
    main()
