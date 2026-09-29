"""Run this once to delete all __pycache__ directories and .pyc files.
Usage: py clear_cache.py
"""
import os, shutil
from pathlib import Path

here = Path(__file__).parent
count = 0
for pycache in list(here.rglob("__pycache__")):
    if pycache.is_dir():
        try:
            shutil.rmtree(pycache)
            count += 1
            print(f"  Removed: {pycache.relative_to(here)}")
        except Exception as e:
            print(f"  SKIP: {pycache.relative_to(here)} — {e}")

print(f"\nDone. Removed {count} __pycache__ directories.")
print("Python will recompile all source files on next run.")
