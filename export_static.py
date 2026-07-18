"""
Build data/bundle.json for GitHub Pages (static View).

Run on the ops PC before push (push_updates.bat does this):
  py export_static.py
"""
from __future__ import annotations

import json
import os
import sys

import store

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "data", "bundle.json")


def main() -> int:
    store.ensure_data_dir()
    bundle = store.merge_bundle()
    # Do not publish local filesystem paths
    bundle.pop("files", None)
    bundle["static"] = True
    bundle["mode"] = "view"

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(bundle, f, indent=2, ensure_ascii=False)
        f.write("\n")

    units = len(bundle.get("units") or [])
    print(f"Wrote {OUT} ({units} units)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
