"""One-time migration: rename org keys to standard names in data/*.json."""
from __future__ import annotations

import json
import os

from org_names import canonical_org

DATA = os.path.join(os.path.dirname(__file__), "data")


def _rename(value):
    if isinstance(value, str):
        c = canonical_org(value)
        return c if c != value else value
    if isinstance(value, list):
        return [_rename(v) for v in value]
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            nk = k
            if k in ("org", "team_org", "unit"):
                nv = canonical_org(v) if isinstance(v, str) else _rename(v)
                if nv != v:
                    out[nk] = nv
                else:
                    out[nk] = _rename(v)
            elif k == "team_label" and isinstance(v, str):
                out[k] = canonical_org(v)
            else:
                out[k] = _rename(v)
        return out
    return value


def migrate_file(path: str) -> int:
    with open(path, encoding="utf-8") as f:
        raw = f.read()
    doc = json.loads(raw)
    new_doc = _rename(doc)
    new_raw = json.dumps(new_doc, indent=2, ensure_ascii=False) + "\n"
    if new_raw == raw if raw.endswith("\n") else new_raw == raw + "\n":
        return 0
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_raw)
    return 1


def main():
    files = [
        "accommodation.json",
        "mess.json",
        "directory.json",
        "arrival.json",
        "lo.json",
        "players.json",
        "tech_committee.json",
    ]
    changed = 0
    for name in files:
        path = os.path.join(DATA, name)
        if not os.path.isfile(path):
            continue
        if migrate_file(path):
            print("updated", name)
            changed += 1
        else:
            print("unchanged", name)
    print(f"done — {changed} file(s) updated")


if __name__ == "__main__":
    main()
