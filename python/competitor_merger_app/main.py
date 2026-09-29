from __future__ import annotations

import argparse
from pathlib import Path

from app.merger import merge_files


def collect_input_files(paths: list[str]) -> list[Path]:
    files: list[Path] = []
    for item in paths:
        path = Path(item)
        if path.is_dir():
            files.extend(sorted(path.glob("*.json")))
        elif path.is_file() and path.suffix.lower() == ".json":
            files.append(path)
    return files


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge extracted competitor page JSON files into one OpenAI-ready site snapshot.")
    parser.add_argument("inputs", nargs="+", help="JSON files or folders containing JSON files")
    parser.add_argument("-o", "--output", default="site_snapshot.json", help="Output JSON file path")
    args = parser.parse_args()

    input_files = collect_input_files(args.inputs)
    if not input_files:
        raise SystemExit("No JSON files found.")

    snapshot = merge_files(input_files, args.output)
    print(f"Merged {len(input_files)} files")
    print(f"Pages analyzed: {snapshot['site']['pagesAnalyzedCount']}")
    print(f"Unique products: {snapshot['site']['totalUniqueProducts']}")
    print(f"Output: {args.output}")


if __name__ == "__main__":
    main()
