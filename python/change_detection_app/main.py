"""Change Detection CLI.

Usage:
    python main.py previous_snapshot.json current_snapshot.json
    python main.py previous_snapshot.json current_snapshot.json -o changes.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.detector import detect_changes


def main() -> None:
    parser = argparse.ArgumentParser(description="Detect changes between two site snapshots of the same site.")
    parser.add_argument("previous", help="Previous site_snapshot JSON file")
    parser.add_argument("current", help="Current site_snapshot JSON file")
    parser.add_argument("-o", "--output", default=None, help="Output JSON path (default: <domain>_changes.json)")
    parser.add_argument("--min-severity-ai", default="medium", choices=["low", "medium", "high", "critical"])
    parser.add_argument("--price-threshold", type=float, default=5.0, help="Price change %% threshold")
    args = parser.parse_args()

    previous = json.loads(Path(args.previous).read_text(encoding="utf-8"))
    current = json.loads(Path(args.current).read_text(encoding="utf-8"))

    result = detect_changes(previous, current, {
        "minimumSeverityForAI": args.min_severity_ai,
        "priceChangeThresholdPercent": args.price_threshold,
    })

    out = args.output or f"{(result.get('domain') or 'site').replace('.', '-')}_changes.json"
    Path(out).write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    s = result["summary"]
    print(f"Domain          : {result['domain']}")
    print(f"Overall severity: {result['overallSeverity']}  (score {result['changeScore']}/100)")
    print(f"Send to AI      : {result['shouldSendToAI']}")
    print(f"Changes         : {s['totalChanges']}  "
          f"(critical {s['criticalChanges']}, high {s['highChanges']}, "
          f"medium {s['mediumChanges']}, low {s['lowChanges']})")
    for t, n in list(s.get("changesByType", {}).items())[:8]:
        print(f"    {t}: {n}")
    for w in result["warnings"]:
        print(f"  ! {w}")
    print(f"Output: {out}")


if __name__ == "__main__":
    main()
