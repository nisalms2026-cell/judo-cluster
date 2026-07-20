"""
Per-page JSON storage for the ops dashboard.

data/
  event.json          — event meta
  accommodation.json  — stay location + strength
  mess.json           — mess tags + TGPA dining lists
  arrival.json        — travel / arrival plans
  directory.json      — team manager contacts
  adm_staff.json      — ADM staff persons, tasks, detailments
  lo.json             — liaison officers + team assignments
  tech_committee.json — technical committee members by game
  players.json        — athlete roster by sport (AIPSCB MIS import)
"""
from __future__ import annotations

import datetime
import json
import os
import re
import uuid

from import_excel import build_summary

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, "data")
LEGACY_FILE = os.path.join(BASE, "event_data.json")

FILES = {
    "event": os.path.join(DATA_DIR, "event.json"),
    "accommodation": os.path.join(DATA_DIR, "accommodation.json"),
    "mess": os.path.join(DATA_DIR, "mess.json"),
    "arrival": os.path.join(DATA_DIR, "arrival.json"),
    "directory": os.path.join(DATA_DIR, "directory.json"),
    "adm_staff": os.path.join(DATA_DIR, "adm_staff.json"),
    "lo": os.path.join(DATA_DIR, "lo.json"),
    "tech_committee": os.path.join(DATA_DIR, "tech_committee.json"),
    "players": os.path.join(DATA_DIR, "players.json"),
}

TC_GAMES = ["Pencak Silat", "Judo", "Wushu", "Taekwondo", "Karate"]
PLAYER_SPORTS = ["Judo", "Karate", "Taekwondo", "Wushu", "Pencak Silat", "Taolu"]


def _now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def _read(path, default):
    if not os.path.isfile(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write(path, payload):
    ensure_data_dir()
    payload["updated_at"] = _now()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def _org_key(org: str) -> str:
    return (org or "").strip().upper()


def _find_row_by_org(rows, org: str):
    key = _org_key(org)
    if not key:
        return None
    for r in rows or []:
        if _org_key(r.get("org")) == key:
            return r
    return None


def _resolve_org_name(org: str) -> str:
    """Return canonical org label (accommodation spelling when available)."""
    raw = (org or "").strip()
    key = _org_key(raw)
    if not key:
        return raw
    acc = _read(FILES["accommodation"], {"rows": []})
    hit = _find_row_by_org(acc.get("rows") or [], raw)
    if hit:
        return hit["org"]
    for path in (FILES["arrival"], FILES["mess"], FILES["directory"]):
        doc = _read(path, {"rows": []})
        hit = _find_row_by_org(doc.get("rows") or [], raw)
        if hit:
            return hit["org"]
    return raw


def _lookup_by_org(mapping: dict, org: str):
    if org in mapping:
        return mapping[org]
    key = _org_key(org)
    for k, v in mapping.items():
        if _org_key(k) == key:
            return v
    return None


DEFAULT_VENUES = ["TGPA", "Sport Tower", "NITHM", "Own Location"]

DEFAULT_HUBS = {
    "rail": [
        {"id": "secunderabad", "label": "Secunderabad Jn"},
        {"id": "hyderabad", "label": "Hyderabad Rly. Station"},
        {"id": "charlapalli", "label": "Charlapalli Rly. Stn."},
        {"id": "kacheguda", "label": "Kacheguda Station"},
    ],
    "flight": [
        {"id": "rgia", "label": "Rajiv Gandhi Intl Airport (Shamshabad)"},
    ],
    "bus": [
        {"id": "alighting", "label": "Bus Alighting Point", "role": "arrival"},
        {"id": "boarding", "label": "Bus Boarding Point", "role": "departure"},
    ],
}


def normalize_hubs(hubs):
    """Merge saved hubs with defaults so new keys always exist."""
    src = hubs or {}
    out = {}
    for mode, defaults in DEFAULT_HUBS.items():
        saved = src.get(mode)
        if isinstance(saved, list) and saved:
            out[mode] = saved
        else:
            out[mode] = [dict(x) for x in defaults]
    return out


def normalize_venues(venues, rows=None):
    """Keep known venues + any locations already used on rows."""
    seen = []
    for v in (venues or []) + list(DEFAULT_VENUES):
        name = (v or "").strip()
        if name and name not in seen:
            seen.append(name)
    if rows:
        for r in rows:
            loc = (r.get("location") or "").strip()
            if loc and loc not in seen:
                seen.append(loc)
    return seen


def empty_bundle():
    return {
        "updated_at": _now(),
        "source_file": "",
        "event": {
            "title": "11th All India Police Judo Cluster 2026",
            "host": "CISF",
            "city": "Hyderabad",
            "mascot": "Vira",
        },
        "units": [],
        "venues": list(DEFAULT_VENUES),
        "hubs": normalize_hubs(None),
        "tgpa_mess": {"dining_tgpa": [], "own_mess": [], "note": ""},
        "adm_staff": {"persons": [], "tasks": [], "detailments": []},
        "lo": {"officers": [], "assignments": []},
        "tech_committee": {"games": list(TC_GAMES), "members": []},
        "players": {"sports": list(PLAYER_SPORTS), "players": []},
        "summary": build_summary([]),
    }


def split_from_bundle(data: dict):
    """Write all per-page JSON files from a merged bundle."""
    ensure_data_dir()
    units = data.get("units") or []
    venues = normalize_venues(data.get("venues"), [
        {"location": u.get("location")} for u in units
    ])

    _write(FILES["event"], {
        "source_file": data.get("source_file", ""),
        "event": data.get("event") or empty_bundle()["event"],
    })

    _write(FILES["accommodation"], {
        "venues": venues,
        "rows": [
            {
                "org": u["org"],
                "location": u.get("location", "TGPA"),
                "strength": u.get("strength") or {},
                "total": u.get("total", 0),
                "count_gos": u.get("count_gos") or {"male": 0, "female": 0},
                "count_sos": u.get("count_sos") or {"male": 0, "female": 0},
                "support": u.get("support") or {"male": 0, "female": 0},
                "coach_male": u.get("coach_male") or {"sos": 0, "ors": 0},
                "coach_female": u.get("coach_female") or {"gos": 0, "sos": 0, "ors": 0},
                "doctor": u.get("doctor", 0),
            }
            for u in units
        ]
    })

    _write(FILES["mess"], {
        "by_unit": [{"org": u["org"], "mess": u.get("mess", "")} for u in units],
        "tgpa_mess": data.get("tgpa_mess") or {"dining_tgpa": [], "own_mess": [], "note": ""},
    })

    _write(FILES["arrival"], {
        "hubs": normalize_hubs((data.get("hubs") if isinstance(data, dict) else None)
                              or (_read(FILES["arrival"], {}).get("hubs"))),
        "rows": [
            {
                "org": u["org"],
                "travel": u.get("travel") or {"station": "", "arrival": "", "details": "", "status": "awaited"},
                "travel_extra": u.get("travel_extra") or [],
                **({"travel_departure": u["travel_departure"]} if u.get("travel_departure") else {}),
                **({"travel_departure_extra": u["travel_departure_extra"]} if u.get("travel_departure_extra") else {}),
            }
            for u in units
        ]
    })

    _write(FILES["directory"], {
        "rows": [
            {
                "org": u["org"],
                "manager": u.get("manager") or {"name": "", "rank": "", "phone": ""},
            }
            for u in units
        ]
    })


def merge_bundle() -> dict:
    """Load and merge all page JSON files into one API payload."""
    ensure_data_dir()

    # Migrate once from legacy event_data.json
    if not os.path.isfile(FILES["accommodation"]) and os.path.isfile(LEGACY_FILE):
        with open(LEGACY_FILE, "r", encoding="utf-8") as f:
            legacy = json.load(f)
        split_from_bundle(legacy)

    if not os.path.isfile(FILES["accommodation"]):
        return empty_bundle()

    event_doc = _read(FILES["event"], {"event": empty_bundle()["event"], "source_file": ""})
    acc = _read(FILES["accommodation"], {"rows": []})
    mess = _read(FILES["mess"], {"by_unit": [], "tgpa_mess": {"dining_tgpa": [], "own_mess": [], "note": ""}})
    arrival = _read(FILES["arrival"], {"rows": []})
    directory = _read(FILES["directory"], {"rows": []})
    _migrate_lo_from_adm()
    adm = _read(FILES["adm_staff"], {"persons": [], "tasks": [], "detailments": []})
    adm_staff = {
        "persons": adm.get("persons") or [],
        "tasks": adm.get("tasks") or [],
        "detailments": adm.get("detailments") or [],
    }
    lo = _read(FILES["lo"], {"officers": [], "assignments": []})
    lo_data = {
        "officers": lo.get("officers") or [],
        "assignments": lo.get("assignments") or [],
    }
    tc = _read(FILES["tech_committee"], {"games": list(TC_GAMES), "members": []})
    tc_data = {
        "games": tc.get("games") or list(TC_GAMES),
        "members": tc.get("members") or [],
    }
    pl = _read(FILES["players"], {"sports": list(PLAYER_SPORTS), "players": []})
    players_data = {
        "source_file": pl.get("source_file", ""),
        "sports": pl.get("sports") or list(PLAYER_SPORTS),
        "players": pl.get("players") or [],
    }

    mess_map = {r["org"]: r.get("mess", "") for r in mess.get("by_unit") or []}
    arr_map = {r["org"]: r for r in arrival.get("rows") or []}
    dir_map = {r["org"]: r.get("manager") or {} for r in directory.get("rows") or []}

    # Union of orgs across files (accommodation is primary order)
    orgs = [r["org"] for r in acc.get("rows") or []]
    for src in (mess_map, arr_map, dir_map):
        for org in src:
            if org not in orgs:
                orgs.append(org)

    acc_map = {r["org"]: r for r in acc.get("rows") or []}
    units = []
    for org in orgs:
        a = acc_map.get(org) or {
            "org": org,
            "location": "TGPA",
            "strength": {"gos_m": 0, "sos_m": 0, "ors_m": 0, "gos_f": 0, "sos_f": 0, "ors_f": 0},
            "total": 0,
            "count_gos": {"male": 0, "female": 0},
            "count_sos": {"male": 0, "female": 0},
            "support": {"male": 0, "female": 0},
            "coach_male": {"sos": 0, "ors": 0},
            "coach_female": {"gos": 0, "sos": 0, "ors": 0},
            "doctor": 0,
        }
        tr = _lookup_by_org(arr_map, org) or {}
        unit = {
            "org": org,
            "location": a.get("location", "TGPA"),
            "manager": _lookup_by_org(dir_map, org) or {"name": "", "rank": "", "phone": ""},
            "count_gos": a.get("count_gos") or {"male": 0, "female": 0},
            "count_sos": a.get("count_sos") or {"male": 0, "female": 0},
            "support": a.get("support") or {"male": 0, "female": 0},
            "coach_male": a.get("coach_male") or {"sos": 0, "ors": 0},
            "coach_female": a.get("coach_female") or {"gos": 0, "sos": 0, "ors": 0},
            "doctor": a.get("doctor", 0),
            "strength": a.get("strength") or {},
            "total": a.get("total", 0),
            "mess": _lookup_by_org(mess_map, org) or "",
            "travel": tr.get("travel") or {"station": "", "arrival": "", "details": "", "status": "awaited"},
        }
        if tr.get("travel_extra"):
            unit["travel_extra"] = tr["travel_extra"]
        if tr.get("travel_departure"):
            unit["travel_departure"] = tr["travel_departure"]
        if tr.get("travel_departure_extra"):
            unit["travel_departure_extra"] = tr["travel_departure_extra"]
        units.append(unit)

    stamps = [
        event_doc.get("updated_at"),
        acc.get("updated_at"),
        mess.get("updated_at"),
        arrival.get("updated_at"),
        directory.get("updated_at"),
        adm.get("updated_at"),
        lo.get("updated_at"),
        tc.get("updated_at"),
        pl.get("updated_at"),
    ]
    stamps = [s for s in stamps if s]
    updated_at = max(stamps) if stamps else _now()

    venues = normalize_venues(acc.get("venues"), acc.get("rows") or [])
    # Persist venues if file was missing them
    if acc.get("venues") != venues:
        _write(FILES["accommodation"], {
            "venues": venues,
            "rows": acc.get("rows") or [],
        })

    hubs = normalize_hubs(arrival.get("hubs"))
    if arrival.get("hubs") != hubs:
        _write(FILES["arrival"], {
            "hubs": hubs,
            "rows": arrival.get("rows") or [],
        })

    return {
        "updated_at": updated_at,
        "source_file": event_doc.get("source_file", ""),
        "event": event_doc.get("event") or empty_bundle()["event"],
        "units": units,
        "venues": venues,
        "hubs": hubs,
        "tgpa_mess": mess.get("tgpa_mess") or {"dining_tgpa": [], "own_mess": [], "note": ""},
        "adm_staff": adm_staff,
        "lo": lo_data,
        "tech_committee": tc_data,
        "players": players_data,
        "summary": build_summary(units),
        "files": {
            "accommodation": FILES["accommodation"],
            "mess": FILES["mess"],
            "arrival": FILES["arrival"],
            "directory": FILES["directory"],
            "event": FILES["event"],
            "adm_staff": FILES["adm_staff"],
            "lo": FILES["lo"],
            "tech_committee": FILES["tech_committee"],
            "players": FILES["players"],
        },
    }


def save_accommodation_row(org: str, patch: dict) -> dict:
    doc = _read(FILES["accommodation"], {"rows": [], "venues": list(DEFAULT_VENUES)})
    rows = doc.get("rows") or []
    r = _find_row_by_org(rows, org)
    if not r:
        raise KeyError(org)
    if "location" in patch:
        r["location"] = (patch["location"] or "TGPA").strip()
    strength = r.setdefault("strength", {})
    for key in ("gos_m", "sos_m", "ors_m", "gos_f", "sos_f", "ors_f"):
        if key in patch:
            strength[key] = int(patch[key] or 0)
    if "doctor" in patch:
        r["doctor"] = int(patch["doctor"] or 0)
    dr = int(r.get("doctor") or 0)
    r["total"] = sum(int(strength.get(k, 0) or 0) for k in ("gos_m", "sos_m", "ors_m", "gos_f", "sos_f", "ors_f")) + dr
    venues = normalize_venues(doc.get("venues"), rows)
    _write(FILES["accommodation"], {"venues": venues, "rows": rows})
    return merge_bundle()


def add_venue(name: str) -> dict:
    name = (name or "").strip()
    if not name:
        raise ValueError("Venue name required")
    doc = _read(FILES["accommodation"], {"rows": [], "venues": list(DEFAULT_VENUES)})
    venues = normalize_venues(doc.get("venues"), doc.get("rows") or [])
    # case-insensitive duplicate check
    if any(v.lower() == name.lower() for v in venues):
        raise ValueError("Venue already exists")
    venues.append(name)
    _write(FILES["accommodation"], {"venues": venues, "rows": doc.get("rows") or []})
    return merge_bundle()


def delete_venue(name: str) -> dict:
    name = (name or "").strip()
    doc = _read(FILES["accommodation"], {"rows": [], "venues": list(DEFAULT_VENUES)})
    rows = doc.get("rows") or []
    in_use = [r["org"] for r in rows if (r.get("location") or "").strip().lower() == name.lower()]
    if in_use:
        raise ValueError(f"Venue in use by {len(in_use)} unit(s)")
    venues = [v for v in normalize_venues(doc.get("venues"), rows) if v.lower() != name.lower()]
    if not venues:
        venues = list(DEFAULT_VENUES)
    _write(FILES["accommodation"], {"venues": venues, "rows": rows})
    return merge_bundle()

def save_mess_row(org: str, mess_value: str) -> dict:
    doc = _read(FILES["mess"], {"by_unit": [], "tgpa_mess": {}})
    rows = doc.get("by_unit") or []
    row = _find_row_by_org(rows, org)
    if row:
        row["mess"] = mess_value
    else:
        rows.append({"org": _resolve_org_name(org), "mess": mess_value})
    _write(FILES["mess"], {"by_unit": rows, "tgpa_mess": doc.get("tgpa_mess") or {}})
    return merge_bundle()


def save_tgpa_mess(tgpa_mess: dict) -> dict:
    doc = _read(FILES["mess"], {"by_unit": [], "tgpa_mess": {}})
    _write(FILES["mess"], {"by_unit": doc.get("by_unit") or [], "tgpa_mess": tgpa_mess})
    return merge_bundle()


def save_arrival_row(
    org: str,
    travel: dict,
    travel_extra=None,
    field: str = "travel",
    leg_index: int = 0,
) -> dict:
    """Save arrival or departure leg. field is 'travel' or 'travel_departure'.

    leg_index 0 updates primary travel / travel_departure;
    1+ updates travel_extra or travel_departure_extra[leg_index - 1].
    """
    key = "travel_departure" if field == "travel_departure" else "travel"
    extra_key = "travel_departure_extra" if key == "travel_departure" else "travel_extra"
    leg_index = int(leg_index or 0)
    doc = _read(FILES["arrival"], {"rows": [], "hubs": DEFAULT_HUBS})
    rows = doc.get("rows") or []
    hubs = normalize_hubs(doc.get("hubs"))
    row = _find_row_by_org(rows, org)
    blank = {"station": "", "arrival": "", "details": "", "status": "awaited"}
    if row:
        if leg_index <= 0:
            cur = row.get(key) or {}
            cur.update(travel or {})
            row[key] = cur
            if travel_extra is not None and key == "travel":
                row["travel_extra"] = travel_extra
        else:
            extras = list(row.get(extra_key) or [])
            idx = leg_index - 1
            while len(extras) <= idx:
                extras.append(dict(blank))
            cur = dict(extras[idx] or {})
            cur.update(travel or {})
            extras[idx] = cur
            row[extra_key] = extras
    else:
        canonical = _resolve_org_name(org)
        row = {
            "org": canonical,
            "travel": dict(blank),
            "travel_extra": travel_extra or [],
        }
        if leg_index <= 0:
            row[key] = {**blank, **(travel or {})}
        else:
            extras = []
            idx = leg_index - 1
            while len(extras) <= idx:
                extras.append(dict(blank))
            extras[idx] = {**blank, **(travel or {})}
            row[extra_key] = extras
        rows.append(row)
    # Preserve hubs + any other keys on write
    out = {"hubs": hubs, "rows": rows}
    _write(FILES["arrival"], out)
    return merge_bundle()


def save_hubs(hubs: dict) -> dict:
    doc = _read(FILES["arrival"], {"rows": [], "hubs": DEFAULT_HUBS})
    _write(FILES["arrival"], {
        "hubs": normalize_hubs(hubs),
        "rows": doc.get("rows") or [],
    })
    return merge_bundle()


def save_directory_row(org: str, manager: dict) -> dict:
    doc = _read(FILES["directory"], {"rows": []})
    rows = doc.get("rows") or []
    row = _find_row_by_org(rows, org)
    if row:
        cur = row.get("manager") or {}
        cur.update({k: manager[k] for k in ("name", "rank", "phone") if k in manager})
        row["manager"] = cur
    else:
        rows.append({"org": _resolve_org_name(org), "manager": manager})
    _write(FILES["directory"], {"rows": rows})
    return merge_bundle()


def add_unit(unit: dict) -> dict:
    org = unit["org"]
    # Accommodation
    acc = _read(FILES["accommodation"], {"rows": [], "venues": list(DEFAULT_VENUES)})
    if any(r["org"] == org for r in acc.get("rows") or []):
        raise ValueError("Organisation already exists")
    loc = unit.get("location", "TGPA")
    acc.setdefault("rows", []).append({
        "org": org,
        "location": loc,
        "strength": unit.get("strength") or {},
        "total": unit.get("total", 0),
        "count_gos": unit.get("count_gos") or {"male": 0, "female": 0},
        "count_sos": unit.get("count_sos") or {"male": 0, "female": 0},
        "support": unit.get("support") or {"male": 0, "female": 0},
        "coach_male": unit.get("coach_male") or {"sos": 0, "ors": 0},
        "coach_female": unit.get("coach_female") or {"gos": 0, "sos": 0, "ors": 0},
        "doctor": unit.get("doctor", 0),
    })
    venues = normalize_venues(acc.get("venues"), acc["rows"])
    _write(FILES["accommodation"], {"venues": venues, "rows": acc["rows"]})

    mess = _read(FILES["mess"], {"by_unit": [], "tgpa_mess": {}})
    mess.setdefault("by_unit", []).append({"org": org, "mess": unit.get("mess", "")})
    _write(FILES["mess"], {"by_unit": mess["by_unit"], "tgpa_mess": mess.get("tgpa_mess") or {}})

    arr = _read(FILES["arrival"], {"rows": [], "hubs": DEFAULT_HUBS})
    arr.setdefault("rows", []).append({
        "org": org,
        "travel": unit.get("travel") or {"station": "", "arrival": "", "details": "", "status": "awaited"},
        "travel_extra": unit.get("travel_extra") or [],
    })
    _write(FILES["arrival"], {"hubs": normalize_hubs(arr.get("hubs")), "rows": arr["rows"]})

    directory = _read(FILES["directory"], {"rows": []})
    directory.setdefault("rows", []).append({
        "org": org,
        "manager": unit.get("manager") or {"name": "", "rank": "", "phone": ""},
    })
    _write(FILES["directory"], {"rows": directory["rows"]})

    return merge_bundle()


def delete_unit(org: str) -> dict:
    key = _org_key(org)
    if not key:
        raise KeyError(org)
    removed = False
    for file_key in ("accommodation", "arrival", "directory"):
        doc = _read(FILES[file_key], {"rows": [], "venues": list(DEFAULT_VENUES)} if file_key == "accommodation" else {"rows": []})
        before = len(doc.get("rows") or [])
        doc["rows"] = [r for r in (doc.get("rows") or []) if _org_key(r.get("org")) != key]
        if len(doc["rows"]) < before:
            removed = True
        if file_key == "accommodation":
            _write(FILES[file_key], {
                "venues": normalize_venues(doc.get("venues"), doc["rows"]),
                "rows": doc["rows"],
            })
        elif file_key == "arrival":
            _write(FILES[file_key], {
                "hubs": normalize_hubs(doc.get("hubs")),
                "rows": doc["rows"],
            })
        else:
            _write(FILES[file_key], {"rows": doc["rows"]})

    mess = _read(FILES["mess"], {"by_unit": [], "tgpa_mess": {}})
    before = len(mess.get("by_unit") or [])
    mess["by_unit"] = [r for r in (mess.get("by_unit") or []) if _org_key(r.get("org")) != key]
    if len(mess["by_unit"]) < before:
        removed = True
    _write(FILES["mess"], {"by_unit": mess["by_unit"], "tgpa_mess": mess.get("tgpa_mess") or {}})

    if not removed:
        raise KeyError(org)
    return merge_bundle()


def save_imported_bundle(data: dict) -> dict:
    """Persist Excel import across all page files (+ legacy mirror)."""
    split_from_bundle(data)
    # Keep legacy mirror for backup / older tools
    ensure_data_dir()
    mirror = {
        "updated_at": _now(),
        "source_file": data.get("source_file", ""),
        "event": data.get("event"),
        "units": data.get("units"),
        "tgpa_mess": data.get("tgpa_mess"),
        "summary": build_summary(data.get("units") or []),
    }
    with open(LEGACY_FILE, "w", encoding="utf-8") as f:
        json.dump(mirror, f, indent=2, ensure_ascii=False)
    return merge_bundle()


# ── ADM Staff (persons / tasks / detailments) ───────────────

def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def _adm_doc() -> dict:
    return _read(FILES["adm_staff"], {"persons": [], "tasks": [], "detailments": []})


def _write_adm(doc: dict) -> dict:
    _write(FILES["adm_staff"], {
        "persons": doc.get("persons") or [],
        "tasks": doc.get("tasks") or [],
        "detailments": doc.get("detailments") or [],
    })
    return merge_bundle()


def _digits_only(value: str) -> str:
    return re.sub(r"\D", "", str(value or ""))


def validate_person_fields(payload: dict, *, require_all: bool = True) -> dict:
    """Return cleaned person fields or raise ValueError."""
    cisf_no = _digits_only(payload.get("cisf_no", ""))
    mobile = _digits_only(payload.get("mobile", ""))
    name = (payload.get("name") or "").strip()
    rank = (payload.get("rank") or "").strip()
    unit = (payload.get("unit") or "").strip()
    stay = (payload.get("stay") or payload.get("location") or "").strip()
    room = (payload.get("room") or "").strip()

    if require_all or "cisf_no" in payload:
        if cisf_no and len(cisf_no) != 9:
            raise ValueError("CISF No must be exactly 9 digits")
        # Blank CISF allowed when not yet known; uniqueness only among non-blank
    if require_all or "mobile" in payload:
        if mobile and len(mobile) != 10:
            raise ValueError("Mobile No must be exactly 10 digits")
        if require_all and not mobile:
            # Allow blank on bulk onboard; ops can fill later
            mobile = ""
    if require_all and not name:
        raise ValueError("Name is required")
    if require_all and not rank:
        raise ValueError("Rank is required")
    if require_all and not unit:
        raise ValueError("Unit is required")
    # Stay is optional at onboard — blank means not allotted yet

    out = {}
    if require_all or "cisf_no" in payload:
        out["cisf_no"] = cisf_no
    if require_all or "name" in payload:
        out["name"] = name
    if require_all or "rank" in payload:
        out["rank"] = rank
    if require_all or "unit" in payload:
        out["unit"] = unit
    if require_all or "mobile" in payload:
        out["mobile"] = mobile
    if require_all or "stay" in payload or "location" in payload:
        out["stay"] = stay
    if require_all or "room" in payload:
        out["room"] = room
    return out


def save_adm_person(payload: dict, person_id: str | None = None) -> dict:
    doc = _adm_doc()
    persons = doc.get("persons") or []
    fields = validate_person_fields(payload, require_all=not person_id)

    if person_id:
        found = None
        for p in persons:
            if p.get("id") == person_id:
                found = p
                break
        if not found:
            raise KeyError(person_id)
        # Merge then re-validate full record
        merged = {**found, **fields}
        fields = validate_person_fields(merged, require_all=True)
        if fields.get("cisf_no"):
            for p in persons:
                if p.get("id") != person_id and p.get("cisf_no") == fields["cisf_no"]:
                    raise ValueError(f"CISF No {fields['cisf_no']} already onboarded")
        found.update(fields)
    else:
        if fields.get("cisf_no"):
            for p in persons:
                if p.get("cisf_no") == fields["cisf_no"]:
                    raise ValueError(f"CISF No {fields['cisf_no']} already onboarded")
        persons.append({"id": _new_id("p"), **fields})

    doc["persons"] = persons
    return _write_adm(doc)


def delete_adm_person(person_id: str) -> dict:
    doc = _adm_doc()
    persons = doc.get("persons") or []
    before = len(persons)
    doc["persons"] = [p for p in persons if p.get("id") != person_id]
    if len(doc["persons"]) == before:
        raise KeyError(person_id)
    # Drop detailments for this person
    doc["detailments"] = [
        d for d in (doc.get("detailments") or []) if d.get("person_id") != person_id
    ]
    return _write_adm(doc)


def save_adm_task(payload: dict, task_id: str | None = None) -> dict:
    doc = _adm_doc()
    tasks = doc.get("tasks") or []
    title = (payload.get("title") or "").strip()
    if not title:
        raise ValueError("Task title is required")
    fields = {
        "title": title,
        "location": (payload.get("location") or "").strip(),
        "from_date": (payload.get("from_date") or "").strip(),
        "to_date": (payload.get("to_date") or "").strip(),
        "notes": (payload.get("notes") or "").strip(),
        "status": (payload.get("status") or "open").strip().lower() or "open",
    }
    if fields["status"] not in ("open", "closed"):
        fields["status"] = "open"

    if task_id:
        found = None
        for t in tasks:
            if t.get("id") == task_id:
                found = t
                break
        if not found:
            raise KeyError(task_id)
        found.update(fields)
    else:
        tasks.append({"id": _new_id("t"), **fields})

    doc["tasks"] = tasks
    return _write_adm(doc)


def delete_adm_task(task_id: str) -> dict:
    doc = _adm_doc()
    tasks = doc.get("tasks") or []
    before = len(tasks)
    doc["tasks"] = [t for t in tasks if t.get("id") != task_id]
    if len(doc["tasks"]) == before:
        raise KeyError(task_id)
    doc["detailments"] = [
        d for d in (doc.get("detailments") or []) if d.get("task_id") != task_id
    ]
    return _write_adm(doc)


def save_adm_detailment(payload: dict, detailment_id: str | None = None) -> dict:
    doc = _adm_doc()
    persons = {p["id"]: p for p in (doc.get("persons") or []) if p.get("id")}
    tasks = {t["id"]: t for t in (doc.get("tasks") or []) if t.get("id")}
    detailments = doc.get("detailments") or []

    task_id = (payload.get("task_id") or "").strip()
    person_id = (payload.get("person_id") or "").strip()
    if not task_id or task_id not in tasks:
        raise ValueError("Valid task is required")
    if not person_id or person_id not in persons:
        raise ValueError("Valid person is required")

    fields = {
        "task_id": task_id,
        "person_id": person_id,
        "role": (payload.get("role") or "").strip(),
        "from_date": (payload.get("from_date") or "").strip(),
        "to_date": (payload.get("to_date") or "").strip(),
        "notes": (payload.get("notes") or "").strip(),
    }

    if detailment_id:
        found = None
        for d in detailments:
            if d.get("id") == detailment_id:
                found = d
                break
        if not found:
            raise KeyError(detailment_id)
        for d in detailments:
            if (
                d.get("id") != detailment_id
                and d.get("task_id") == fields["task_id"]
                and d.get("person_id") == fields["person_id"]
            ):
                raise ValueError("This person is already detailed on that task")
        found.update(fields)
    else:
        for d in detailments:
            if d.get("task_id") == fields["task_id"] and d.get("person_id") == fields["person_id"]:
                raise ValueError("This person is already detailed on that task")
        detailments.append({"id": _new_id("d"), **fields})

    doc["detailments"] = detailments
    return _write_adm(doc)


def delete_adm_detailment(detailment_id: str) -> dict:
    doc = _adm_doc()
    detailments = doc.get("detailments") or []
    before = len(detailments)
    doc["detailments"] = [d for d in detailments if d.get("id") != detailment_id]
    if len(doc["detailments"]) == before:
        raise KeyError(detailment_id)
    return _write_adm(doc)


# ── Liaison Officers (LO) ─────────────────────────────────────

def _is_liaison_task(title: str) -> bool:
    return "liaison" in (title or "").lower() or "liaision" in (title or "").lower()


def _lo_doc() -> dict:
    return _read(FILES["lo"], {"officers": [], "assignments": []})


def _write_lo(doc: dict) -> dict:
    _write(FILES["lo"], {
        "officers": doc.get("officers") or [],
        "assignments": doc.get("assignments") or [],
    })
    return merge_bundle()


def _migrate_lo_from_adm() -> None:
    """Move Liaison officer task from ADM Staff into lo.json (once)."""
    lo = _lo_doc()
    if lo.get("officers"):
        return
    adm = _adm_doc()
    tasks = adm.get("tasks") or []
    liaison_ids = {t["id"] for t in tasks if _is_liaison_task(t.get("title", ""))}
    if not liaison_ids:
        return
    detailments = adm.get("detailments") or []
    lo_person_ids = {d["person_id"] for d in detailments if d.get("task_id") in liaison_ids}
    if not lo_person_ids:
        return
    persons = {p["id"]: p for p in (adm.get("persons") or []) if p.get("id")}
    id_map: dict[str, str] = {}
    officers = []
    for pid in lo_person_ids:
        p = persons.get(pid)
        if not p:
            continue
        new_id = _new_id("lo")
        id_map[pid] = new_id
        officers.append({
            "id": new_id,
            "cisf_no": p.get("cisf_no") or "",
            "name": p.get("name") or "",
            "rank": p.get("rank") or "",
            "unit": p.get("unit") or "",
            "mobile": p.get("mobile") or "",
        })
    officers.sort(key=lambda x: (x.get("name") or "").lower())
    _write(FILES["lo"], {"officers": officers, "assignments": []})
    remaining_dets = [d for d in detailments if d.get("task_id") not in liaison_ids]
    remaining_tasks = [t for t in tasks if t.get("id") not in liaison_ids]
    other_det_persons = {d["person_id"] for d in remaining_dets}
    remaining_persons = [
        p for p in (adm.get("persons") or [])
        if p.get("id") not in lo_person_ids or p.get("id") in other_det_persons
    ]
    _write(FILES["adm_staff"], {
        "persons": remaining_persons,
        "tasks": remaining_tasks,
        "detailments": remaining_dets,
    })


def validate_lo_officer_fields(payload: dict, *, require_all: bool = True) -> dict:
    cisf_no = _digits_only(payload.get("cisf_no", ""))
    mobile = _digits_only(payload.get("mobile", ""))
    name = (payload.get("name") or "").strip()
    rank = (payload.get("rank") or "").strip()
    unit = (payload.get("unit") or "").strip()
    if require_all or "cisf_no" in payload:
        if cisf_no and len(cisf_no) != 9:
            raise ValueError("CISF No must be exactly 9 digits")
    if require_all or "mobile" in payload:
        if mobile and len(mobile) != 10:
            raise ValueError("Mobile No must be exactly 10 digits")
    if require_all and not name:
        raise ValueError("Name is required")
    if require_all and not rank:
        raise ValueError("Rank is required")
    if require_all and not unit:
        raise ValueError("Unit is required")
    out = {}
    if require_all or "cisf_no" in payload:
        out["cisf_no"] = cisf_no
    if require_all or "name" in payload:
        out["name"] = name
    if require_all or "rank" in payload:
        out["rank"] = rank
    if require_all or "unit" in payload:
        out["unit"] = unit
    if require_all or "mobile" in payload:
        out["mobile"] = mobile
    return out


def save_lo_officer(payload: dict, officer_id: str | None = None) -> dict:
    doc = _lo_doc()
    officers = doc.get("officers") or []
    fields = validate_lo_officer_fields(payload, require_all=not officer_id)
    if officer_id:
        found = None
        for o in officers:
            if o.get("id") == officer_id:
                found = o
                break
        if not found:
            raise KeyError(officer_id)
        merged = {**found, **fields}
        fields = validate_lo_officer_fields(merged, require_all=True)
        if fields.get("cisf_no"):
            for o in officers:
                if o.get("id") != officer_id and o.get("cisf_no") == fields["cisf_no"]:
                    raise ValueError(f"CISF No {fields['cisf_no']} already onboarded")
        found.update(fields)
    else:
        if fields.get("cisf_no"):
            for o in officers:
                if o.get("cisf_no") == fields["cisf_no"]:
                    raise ValueError(f"CISF No {fields['cisf_no']} already onboarded")
        officers.append({"id": _new_id("lo"), **fields})
    doc["officers"] = officers
    return _write_lo(doc)


def delete_lo_officer(officer_id: str) -> dict:
    doc = _lo_doc()
    officers = doc.get("officers") or []
    before = len(officers)
    doc["officers"] = [o for o in officers if o.get("id") != officer_id]
    if len(doc["officers"]) == before:
        raise KeyError(officer_id)
    doc["assignments"] = [
        a for a in (doc.get("assignments") or []) if a.get("officer_id") != officer_id
    ]
    return _write_lo(doc)


def save_lo_assignment(payload: dict, assignment_id: str | None = None) -> dict:
    doc = _lo_doc()
    officers = {o["id"]: o for o in (doc.get("officers") or []) if o.get("id")}
    assignments = doc.get("assignments") or []
    team_org = (payload.get("team_org") or payload.get("org") or "").strip().upper()
    officer_id = (payload.get("officer_id") or "").strip()
    notes = (payload.get("notes") or "").strip()
    doa = (payload.get("doa") or "").strip()
    location = (payload.get("location") or "").strip()
    if location.upper() == "TOWER":
        location = "Sport Tower"
    elif location.upper() == "OWN":
        location = "Own Location"
    if not team_org:
        raise ValueError("Team is required")
    if officer_id and officer_id not in officers:
        raise ValueError("Valid liaison officer is required")
    fields = {
        "team_org": team_org,
        "officer_id": officer_id,
        "doa": doa,
        "location": location,
        "notes": notes,
    }
    if assignment_id:
        found = None
        for a in assignments:
            if a.get("id") == assignment_id:
                found = a
                break
        if not found:
            raise KeyError(assignment_id)
        for a in assignments:
            if (
                a.get("id") != assignment_id
                and a.get("team_org") == team_org
                and officer_id
                and a.get("officer_id") == officer_id
            ):
                raise ValueError("This officer is already assigned to that team")
        found.update(fields)
    else:
        existing = next((a for a in assignments if a.get("team_org") == team_org), None)
        if existing:
            existing.update(fields)
        else:
            assignments.append({"id": _new_id("la"), **fields})
    doc["assignments"] = assignments
    return _write_lo(doc)


def delete_lo_assignment(assignment_id: str) -> dict:
    doc = _lo_doc()
    assignments = doc.get("assignments") or []
    before = len(assignments)
    doc["assignments"] = [a for a in assignments if a.get("id") != assignment_id]
    if len(doc["assignments"]) == before:
        raise KeyError(assignment_id)
    return _write_lo(doc)


# ── Technical Committee ───────────────────────────────────────

def _normalize_tc_game(game: str) -> str:
    g = (game or "").strip()
    if not g:
        raise ValueError("Game is required")
    for known in TC_GAMES:
        if known.lower() == g.lower():
            return known
    raise ValueError(f"Game must be one of: {', '.join(TC_GAMES)}")


def _tc_doc() -> dict:
    doc = _read(FILES["tech_committee"], {"games": list(TC_GAMES), "members": []})
    games = doc.get("games") or list(TC_GAMES)
    out_games = []
    for g in games + list(TC_GAMES):
        name = (g or "").strip()
        if name and name not in out_games:
            out_games.append(name)
    doc["games"] = out_games or list(TC_GAMES)
    doc["members"] = doc.get("members") or []
    return doc


def _write_tc(doc: dict) -> dict:
    _write(FILES["tech_committee"], {
        "games": doc.get("games") or list(TC_GAMES),
        "members": doc.get("members") or [],
    })
    return merge_bundle()


def validate_tc_member_fields(payload: dict, *, require_all: bool = True) -> dict:
    mobile = _digits_only(payload.get("mobile", ""))
    name = (payload.get("name") or "").strip()
    rank = (payload.get("rank") or "").strip()
    unit = (payload.get("unit") or "").strip()
    role = (payload.get("role") or "").strip()
    email = (payload.get("email") or "").strip()
    arrival = (payload.get("arrival") or "").strip()
    departure = (payload.get("departure") or "").strip()
    sno_raw = payload.get("sno", "")
    sno = int(sno_raw) if str(sno_raw).strip().isdigit() else 0
    gender = (payload.get("gender") or "").strip().upper()
    if gender and gender not in ("M", "F"):
        raise ValueError("Gender must be M or F")
    if require_all or "mobile" in payload:
        if mobile and len(mobile) != 10:
            raise ValueError("Mobile No must be exactly 10 digits")
    if require_all and not name:
        raise ValueError("Name is required")
    if email and "@" not in email:
        raise ValueError("Email address looks invalid")
    out = {}
    if "game" in payload or require_all:
        out["game"] = _normalize_tc_game(payload.get("game", ""))
    if require_all or "name" in payload:
        out["name"] = name
    if require_all or "rank" in payload:
        out["rank"] = rank
    if require_all or "unit" in payload:
        out["unit"] = unit
    if require_all or "role" in payload:
        out["role"] = role
    if require_all or "mobile" in payload:
        out["mobile"] = mobile
    if require_all or "email" in payload:
        out["email"] = email
    if require_all or "arrival" in payload:
        out["arrival"] = arrival
    if require_all or "departure" in payload:
        out["departure"] = departure
    if require_all or "sno" in payload:
        out["sno"] = sno
    if require_all or "gender" in payload:
        out["gender"] = gender
    return out


def save_tc_member(payload: dict, member_id: str | None = None) -> dict:
    doc = _tc_doc()
    members = doc.get("members") or []
    fields = validate_tc_member_fields(payload, require_all=not member_id)
    if member_id:
        found = None
        for m in members:
            if m.get("id") == member_id:
                found = m
                break
        if not found:
            raise KeyError(member_id)
        merged = {**found, **fields}
        fields = validate_tc_member_fields(merged, require_all=True)
        found.update(fields)
    else:
        members.append({"id": _new_id("tc"), **fields})
    doc["members"] = members
    return _write_tc(doc)


def delete_tc_member(member_id: str) -> dict:
    doc = _tc_doc()
    members = doc.get("members") or []
    before = len(members)
    doc["members"] = [m for m in members if m.get("id") != member_id]
    if len(doc["members"]) == before:
        raise KeyError(member_id)
    return _write_tc(doc)


# ── Players (AIPSCB MIS roster) ───────────────────────────────

def save_players_import(data: dict) -> dict:
    """Replace player roster from Excel import."""
    _write(FILES["players"], {
        "source_file": data.get("source_file", ""),
        "sports": data.get("sports") or list(PLAYER_SPORTS),
        "players": data.get("players") or [],
    })
    return merge_bundle()


def _players_doc() -> dict:
    doc = _read(FILES["players"], {"sports": list(PLAYER_SPORTS), "players": []})
    doc["sports"] = doc.get("sports") or list(PLAYER_SPORTS)
    doc["players"] = doc.get("players") or []
    return doc


def _write_players(doc: dict) -> dict:
    _write(FILES["players"], {
        "source_file": doc.get("source_file", ""),
        "sports": doc.get("sports") or list(PLAYER_SPORTS),
        "players": doc.get("players") or [],
    })
    return merge_bundle()


def _normalize_player_sport(sport: str) -> str:
    s = (sport or "").strip()
    if not s:
        raise ValueError("Sport is required")
    for known in PLAYER_SPORTS:
        if known.lower() == s.lower():
            return known
    raise ValueError(f"Sport must be one of: {', '.join(PLAYER_SPORTS)}")


def validate_player_fields(payload: dict, *, require_all: bool = True) -> dict:
    mobile = _digits_only(payload.get("mobile", ""))
    name = (payload.get("name") or "").strip()
    org = (payload.get("org") or "").strip().upper()
    org_raw = (payload.get("org_raw") or org).strip()
    gender = (payload.get("gender") or "").strip()
    email = (payload.get("email") or "").strip()
    events = payload.get("events")
    if events is None and require_all:
        label = (payload.get("event_label") or "").strip()
        sport = payload.get("sport") or payload.get("game") or ""
        if label:
            events = [{"sport": _normalize_player_sport(sport), "label": label}]
        else:
            events = []
    elif isinstance(events, list):
        cleaned = []
        for ev in events:
            if not isinstance(ev, dict):
                continue
            label = (ev.get("label") or "").strip()
            if not label:
                continue
            sport_raw = (ev.get("sport") or "").strip()
            if not sport_raw:
                t = label.lower()
                for known in PLAYER_SPORTS:
                    if known.lower() in t:
                        sport_raw = known
                        break
            cleaned.append({
                "sport": _normalize_player_sport(sport_raw or "Judo"),
                "label": label,
            })
        events = cleaned
    else:
        events = []

    if require_all or "mobile" in payload:
        if mobile and len(mobile) != 10:
            raise ValueError("Mobile No must be exactly 10 digits")
    if require_all and not name:
        raise ValueError("Name is required")
    if require_all and not org:
        raise ValueError("Team / organisation is required")
    if email and "@" not in email:
        raise ValueError("Email address looks invalid")

    out = {}
    if require_all or "name" in payload:
        out["name"] = name
    if require_all or "org" in payload:
        out["org"] = org
    if require_all or "org_raw" in payload:
        out["org_raw"] = org_raw
    if require_all or "gender" in payload:
        out["gender"] = gender
    if require_all or "mobile" in payload:
        out["mobile"] = mobile
    if require_all or "email" in payload:
        out["email"] = email
    if require_all or "events" in payload or "event_label" in payload or "sport" in payload:
        out["events"] = events
    if "sno" in payload:
        sno_raw = payload.get("sno", "")
        out["sno"] = int(sno_raw) if str(sno_raw).strip().isdigit() else 0
    return out


def save_player(payload: dict, player_id: str | None = None) -> dict:
    doc = _players_doc()
    players = doc.get("players") or []
    fields = validate_player_fields(payload, require_all=not player_id)
    if player_id:
        found = None
        for p in players:
            if p.get("id") == player_id:
                found = p
                break
        if not found:
            raise KeyError(player_id)
        merged = {**found, **fields}
        fields = validate_player_fields(merged, require_all=True)
        found.update(fields)
    else:
        mobile = fields.get("mobile") or ""
        new_id = f"pl_{mobile}" if len(mobile) == 10 else _new_id("pl")
        if any(p.get("id") == new_id for p in players):
            new_id = _new_id("pl")
        players.append({"id": new_id, **fields})
    doc["players"] = players
    return _write_players(doc)


def delete_player(player_id: str) -> dict:
    doc = _players_doc()
    players = doc.get("players") or []
    before = len(players)
    doc["players"] = [p for p in players if p.get("id") != player_id]
    if len(doc["players"]) == before:
        raise KeyError(player_id)
    return _write_players(doc)
