"""Sync submission/app.py from the current, src-synced app.py.

submission/ holds the deliverable copies that live inside this repo (no
external absolute path dependency): submission/app.py (kept current here)
and submission/김관영_머신러닝프로젝트.ipynb (frozen — already matches the
report's screenshots 1:1, no generator needed).

Run scripts/sync_standalone_app.py first so app.py reflects the latest src/.

Usage:
  python scripts/sync_standalone_app.py
  python scripts/package_submission.py
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--app-py", default="app.py")
    parser.add_argument("--out", default="submission/app.py")
    args = parser.parse_args()

    src = Path(args.app_py)
    dest = Path(args.out)
    if not src.exists():
        print(f"ERROR: {src} not found")
        return 1
    dest.parent.mkdir(parents=True, exist_ok=True)

    shutil.copyfile(src, dest)
    print(f"Copied {src} -> {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
