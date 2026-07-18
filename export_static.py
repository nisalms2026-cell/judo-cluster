"""
Build static files for GitHub Pages (docs/).

Writes:
  data/bundle.json          — for local/Cloudflare View refresh
  docs/index.html           — Pages site
  docs/data/bundle.json
  docs/assets/*             — logos etc.

Used by push_updates.bat:
  py export_static.py
"""
from __future__ import annotations

import json
import os
import shutil
import sys

import store

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_BUNDLE = os.path.join(BASE, "data", "bundle.json")
DOCS = os.path.join(BASE, "docs")
DOCS_DATA = os.path.join(DOCS, "data")
DOCS_ASSETS = os.path.join(DOCS, "assets")
ASSETS = os.path.join(BASE, "assets")


def write_bundle(path: str, bundle: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(bundle, f, indent=2, ensure_ascii=False)
        f.write("\n")


def main() -> int:
    store.ensure_data_dir()
    bundle = store.merge_bundle()
    bundle.pop("files", None)
    bundle["static"] = True
    bundle["mode"] = "view"

    write_bundle(DATA_BUNDLE, bundle)

    os.makedirs(DOCS, exist_ok=True)
    os.makedirs(DOCS_DATA, exist_ok=True)
    os.makedirs(DOCS_ASSETS, exist_ok=True)

    # Marker so GitHub Pages skips Jekyll processing
    open(os.path.join(DOCS, ".nojekyll"), "a", encoding="utf-8").close()

    shutil.copy2(os.path.join(BASE, "index.html"), os.path.join(DOCS, "index.html"))
    write_bundle(os.path.join(DOCS_DATA, "bundle.json"), bundle)

    if os.path.isdir(ASSETS):
        for name in os.listdir(ASSETS):
            src = os.path.join(ASSETS, name)
            if os.path.isfile(src):
                shutil.copy2(src, os.path.join(DOCS_ASSETS, name))

    units = len(bundle.get("units") or [])
    print(f"Wrote {DATA_BUNDLE}")
    print(f"Wrote {DOCS}/ (Pages site, {units} units)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
