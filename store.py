"""
Per-page JSON storage for the ops dashboard.

data/
  event.json          — event meta
  accommodation.json  — stay location + strength
  mess.json           — mess tags + TGPA dining lists
  arrival.json        — travel / arrival plans
  directory.json      — team manager contacts
  adm_staff.json      — ADM staff persons, tasks, detailments
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
}


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
    adm = _read(FILES["adm_staff"], {"persons": [], "tasks": [], "detailments": []})
    adm_staff = {
        "persons": adm.get("persons") or [],
        "tasks": adm.get("tasks") or [],
        "detailments": adm.get("detailments") or [],
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
        tr = arr_map.get(org) or {}
        unit = {
            "org": org,
            "location": a.get("location", "TGPA"),
            "manager": dir_map.get(org) or {"name": "", "rank": "", "phone": ""},
            "count_gos": a.get("count_gos") or {"male": 0, "female": 0},
            "count_sos": a.get("count_sos") or {"male": 0, "female": 0},
            "support": a.get("support") or {"male": 0, "female": 0},
            "coach_male": a.get("coach_male") or {"sos": 0, "ors": 0},
            "coach_female": a.get("coach_female") or {"gos": 0, "sos": 0, "ors": 0},
            "doctor": a.get("doctor", 0),
            "strength": a.get("strength") or {},
            "total": a.get("total", 0),
            "mess": mess_map.get(org, ""),
            "travel": tr.get("travel") or {"station": "", "arrival": "", "details": "", "status": "awaited"},
        }
        if tr.get("travel_extra"):
            unit["travel_extra"] = tr["travel_extra"]
        if tr.get("travel_departure"):
            unit["travel_departure"] = tr["travel_departure"]
        units.append(unit)

    stamps = [
        event_doc.get("updated_at"),
        acc.get("updated_at"),
        mess.get("updated_at"),
        arrival.get("updated_at"),
        directory.get("updated_at"),
        adm.get("updated_at"),
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
        "summary": build_summary(units),
        "files": {
            "accommodation": FILES["accommodation"],
            "mess": FILES["mess"],
            "arrival": FILES["arrival"],
            "directory": FILES["directory"],
            "event": FILES["event"],
            "adm_staff": FILES["adm_staff"],
        },
    }


def save_accommodation_row(org: str, patch: dict) -> dict:
    org = org.strip().upper()
    doc = _read(FILES["accommodation"], {"rows": [], "venues": list(DEFAULT_VENUES)})
    rows = doc.get("rows") or []
    found = False
    for r in rows:
        if r["org"] == org:
            found = True
            if "location" in patch:
                r["location"] = (patch["location"] or "TGPA").strip()
            strength = r.setdefault("strength", {})
            for key in ("gos_m", "sos_m", "ors_m", "gos_f", "sos_f", "ors_f"):
                if key in patch:
                    strength[key] = int(patch[key] or 0)
            r["total"] = sum(int(strength.get(k, 0) or 0) for k in ("gos_m", "sos_m", "ors_m", "gos_f", "sos_f", "ors_f"))
            break
    if not found:
        raise KeyError(org)
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
    org = org.strip().upper()
    doc = _read(FILES["mess"], {"by_unit": [], "tgpa_mess": {}})
    rows = doc.get("by_unit") or []
    found = False
    for r in rows:
        if r["org"] == org:
            r["mess"] = mess_value
            found = True
            break
    if not found:
        rows.append({"org": org, "mess": mess_value})
    _write(FILES["mess"], {"by_unit": rows, "tgpa_mess": doc.get("tgpa_mess") or {}})
    return merge_bundle()


def save_tgpa_mess(tgpa_mess: dict) -> dict:
    doc = _read(FILES["mess"], {"by_unit": [], "tgpa_mess": {}})
    _write(FILES["mess"], {"by_unit": doc.get("by_unit") or [], "tgpa_mess": tgpa_mess})
    return merge_bundle()


def save_arrival_row(org: str, travel: dict, travel_extra=None, field: str = "travel") -> dict:
    """Save arrival or departure leg. field is 'travel' or 'travel_departure'."""
    org = org.strip().upper()
    key = "travel_departure" if field == "travel_departure" else "travel"
    doc = _read(FILES["arrival"], {"rows": [], "hubs": DEFAULT_HUBS})
    rows = doc.get("rows") or []
    hubs = normalize_hubs(doc.get("hubs"))
    found = False
    for r in rows:
        if r["org"] == org:
            found = True
            cur = r.get(key) or {}
            cur.update(travel or {})
            r[key] = cur
            if travel_extra is not None and key == "travel":
                r["travel_extra"] = travel_extra
            break
    if not found:
        row = {
            "org": org,
            "travel": {"station": "", "arrival": "", "details": "", "status": "awaited"},
            "travel_extra": travel_extra or [],
        }
        row[key] = travel or {"station": "", "arrival": "", "details": "", "status": "awaited"}
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
    org = org.strip().upper()
    doc = _read(FILES["directory"], {"rows": []})
    rows = doc.get("rows") or []
    found = False
    for r in rows:
        if r["org"] == org:
            found = True
            cur = r.get("manager") or {}
            cur.update({k: manager[k] for k in ("name", "rank", "phone") if k in manager})
            r["manager"] = cur
            break
    if not found:
        rows.append({"org": org, "manager": manager})
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
    org = org.strip().upper()
    removed = False
    for key in ("accommodation", "arrival", "directory"):
        doc = _read(FILES[key], {"rows": [], "venues": list(DEFAULT_VENUES)} if key == "accommodation" else {"rows": []})
        before = len(doc.get("rows") or [])
        doc["rows"] = [r for r in (doc.get("rows") or []) if r.get("org") != org]
        if len(doc["rows"]) < before:
            removed = True
        if key == "accommodation":
            _write(FILES[key], {
                "venues": normalize_venues(doc.get("venues"), doc["rows"]),
                "rows": doc["rows"],
            })
        elif key == "arrival":
            _write(FILES[key], {
                "hubs": normalize_hubs(doc.get("hubs")),
                "rows": doc["rows"],
            })
        else:
            _write(FILES[key], {"rows": doc["rows"]})

    mess = _read(FILES["mess"], {"by_unit": [], "tgpa_mess": {}})
    before = len(mess.get("by_unit") or [])
    mess["by_unit"] = [r for r in (mess.get("by_unit") or []) if r.get("org") != org]
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
