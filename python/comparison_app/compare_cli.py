from __future__ import annotations

import argparse
import json
from pathlib import Path
from comparison_engine.comparator import compare_sites


def load_json(path: str):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(description="Compare merged website JSON snapshots.")
    parser.add_argument("--user", required=True, help="Path to user website merged JSON")
    parser.add_argument("--competitor", action="append", default=[], help="Path to competitor merged JSON. Can be repeated.")
    parser.add_argument("--out", default="comparison_output.json", help="Output JSON path")
    args = parser.parse_args()

    user = load_json(args.user)
    competitors = [load_json(path) for path in args.competitor]
    result = compare_sites(user, competitors)

    Path(args.out).write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved comparison to {args.out}")


if __name__ == "__main__":
    main()
