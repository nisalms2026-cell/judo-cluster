"""Import team departure plans (Google Form / sheet responses) into data/arrival.json."""

from __future__ import annotations

import re

import store
from org_names import canonical_org

# org label -> canonical dashboard org
ORG_ALIASES = {
    "HARYANA POLICE": "HARYANA",
    "HARYANA": "HARYANA",
    "J& K POLICE": "JAMMU & KASHMIR",
    "J&K POLICE": "JAMMU & KASHMIR",
    "MADHYAPRADESH POLICE TEAM": "MADHYA PRADESH POLICE",
    "MADHYA PRADESH POLICE": "MADHYA PRADESH POLICE",
    "SIKKIM": "SIKKIM POLICE",
    "KERALA POLICE": "KERALA POLICE",
    "KERALA पOLIS": "KERALA POLICE",
    "JHARKHAND": "JHARKHAND",
    "CHANDIGARH": "CHANDIGARH POLICE",
    "HIMACHAL PRADESH POLICE": "HIMACHAL PRADESH POLICE",
    "BIHAR POLICE": "BIHAR POLICE",
    "MAHARASHTRA STATE POLICE": "MAHARASHTRA POLICE",
    "MAHARASHTRA POLICE": "MAHARASHTRA POLICE",
    "TAMILNADU": "TAMILNADU",
    "SSB": "SSB",
    "WEST BENGAL POLICE": "WEST BENGAL POLICE",
    "PUNJAB POLICE": "PUNJAB POLICE",
    "MANIPUR POLICE": "MANIPUR POLICE",
    "ANDHRA PRADESH": "Andhra Pradesh",
    "ANDHRA PRADESH POLICE": "Andhra Pradesh",
    "RPF": "RPF",
    "MIZORAM POLICE": "MIZORAM POLICE",
    "UTTAR PRADESH POLICE": "UTTARPRADESH",
    "UP POLICE": "UTTARPRADESH",
    "UTTARPRADESH": "UTTARPRADESH",
}


def map_org(label: str) -> str:
    key = " ".join(str(label or "").split()).upper()
    if key in ORG_ALIASES:
        return ORG_ALIASES[key]
    return canonical_org(label.strip())


def leg(
    mode: str,
    station: str,
    when: str,
    details: str,
    *,
    status: str = "planned",
    team_label: str | None = None,
) -> dict:
    out = {
        "mode": mode,
        "station": station,
        "arrival": when,
        "details": details.strip(),
        "status": status,
        "direction": "departure",
    }
    if team_label:
        out["team_label"] = team_label
    return out


# Parsed from received departure sheet (Jul 2026). Dates/times normalised to dashboard format.
DEPARTURE_PLANS: dict[str, dict] = {
    "HARYANA": {
        "manager": "ASI Sunil Kumar",
        "phone": "9467130300",
        "primary": leg(
            "rail",
            "Secunderabad Jn",
            "31.07.2026/0625 hrs",
            "Telangana Exp Secunderabad → New Delhi · 8 personnel by train",
        ),
        "extra": [],
        "remarks": "",
    },
    "JAMMU & KASHMIR": {
        "manager": "Anjana (Dy. SP)",
        "phone": "9622089944",
        "primary": leg(
            "flight",
            "Rajiv Gandhi Intl Airport (Shamshabad)",
            "31.07.2026/1135 hrs",
            "Dy. SP Anjana · Flight 6E 6202 · RGIA departure",
        ),
        "extra": [
            leg(
                "rail",
                "Secunderabad Jn",
                "31.07.2026/0625 hrs",
                "Train 12723 Telangana Exp · 47 team members",
            ),
        ],
        "remarks": "Vehicle 09:00 from Senior Officers Mess (Dy. SP). Rest of players pickup from JOM — timing to be conveyed by phone.",
    },
    "MADHYA PRADESH POLICE": {
        "manager": "INSP/Exe Gopikrishna Shridharan",
        "phone": "8440809321",
        "primary": leg(
            "rail",
            "Hyderabad Rly. Station",
            "01.08.2026/2300 hrs",
            "Train 12721 Dakshin SF Ex · Hyderabad Deccan → Bhopal · 16 ORs (11 M, 4 F) + 1 team manager",
        ),
        "extra": [],
        "remarks": "",
    },
    "SIKKIM POLICE": {
        "manager": "ASI Tenzing Sherpa",
        "phone": "9593788535",
        "primary": leg(
            "flight",
            "Rajiv Gandhi Intl Airport (Shamshabad)",
            "31.07.2026/0815 hrs",
            "IndiGo 6E 6872 (A321) · 2 personnel",
        ),
        "extra": [],
        "remarks": "Request vehicle — leave for TGPA at 05:00.",
    },
    "KERALA POLICE": {
        "manager": "IV Vinod",
        "phone": "8281382896",
        "primary": leg(
            "rail",
            "Secunderabad Jn",
            "01.08.2026/2335 hrs",
            "Train 07193 Secunderabad · 35 personnel",
        ),
        "extra": [],
        "remarks": "",
    },
    "JHARKHAND": {
        "manager": "Shri Rajat Manik Baxla (DSP)",
        "phone": "8252966659",
        "primary": leg(
            "flight",
            "Rajiv Gandhi Intl Airport (Shamshabad)",
            "31.07.2026/0915 hrs",
            "Flight 6E-421 · 1 personnel",
        ),
        "extra": [
            leg(
                "rail",
                "Charlapalli Rly. Stn.",
                "31.07.2026/2100 hrs",
                "Train 03255 · 39 personnel",
            ),
        ],
        "remarks": "",
    },
    "CHANDIGARH POLICE": {
        "manager": "Sandeep Malik Wasu",
        "phone": "9988211547",
        "primary": leg(
            "rail",
            "Secunderabad Jn",
            "02.08.2026/0030 hrs",
            "Train 12214 Duronto Ex · 17 personnel (9 M, 8 F)",
        ),
        "extra": [],
        "remarks": "Form showed 22/7/26 night 12:30 — confirm date/time with team.",
    },
    "HIMACHAL PRADESH POLICE": {
        "manager": "Kamal Kishore DySP",
        "phone": "9418484672",
        "primary": leg(
            "rail",
            "Secunderabad Jn",
            "31.07.2026/0710 hrs",
            "Train 22691 Rajdhani Express · 1 DySP",
        ),
        "extra": [
            leg(
                "rail",
                "Hyderabad Rly. Station",
                "31.07.2026/2325 hrs",
                "Train 12721 Dakshin Express · 10 police personnel",
            ),
        ],
        "remarks": "",
    },
    "BIHAR POLICE": {
        "manager": "Raju Kumar",
        "phone": "9472972929",
        "primary": leg(
            "rail",
            "Charlapalli Rly. Stn.",
            "31.07.2026/2100 hrs",
            "Train 03255",
        ),
        "extra": [],
        "remarks": "",
    },
    "MAHARASHTRA POLICE": {
        "manager": "Santosh Kamble",
        "phone": "9325154416",
        "primary": leg(
            "rail",
            "Hyderabad Rly. Station",
            "31.07.2026/1455 hrs",
            "Train 12702 Hyderabad → Mumbai CSMT · arr 01.08.2026/0455 hrs",
        ),
        "extra": [],
        "remarks": "",
    },
    "TAMILNADU": {
        "manager": "Tr A Hasen Becha / AC",
        "phone": "9965445421",
        "primary": leg(
            "rail",
            "Charlapalli Rly. Stn.",
            "31.07.2026/1725 hrs",
            "Train 12604 · Charlapalli → Chennai · M 50, F 22 (incl. AC and wife)",
        ),
        "extra": [],
        "remarks": "",
    },
    "SSB": {
        "manager": "Durgesh Sharma",
        "phone": "9017409009",
        "primary": leg(
            "rail",
            "Secunderabad Jn",
            "30.07.2026/0710 hrs",
            "Train 22691 Rajdhani Express · 15 personnel",
        ),
        "extra": [
            leg(
                "rail",
                "Secunderabad Jn",
                "31.07.2026/0625 hrs",
                "Train 12723 Telangana Express · 20 personnel",
            ),
            leg(
                "flight",
                "Rajiv Gandhi Intl Airport (Shamshabad)",
                "31.07.2026/1300 hrs",
                "Flight · RGIA · 1 personnel",
            ),
            leg(
                "rail",
                "Secunderabad Jn",
                "01.08.2026/0625 hrs",
                "Train 12723 Telangana Express · 10 personnel",
            ),
            leg(
                "rail",
                "Secunderabad Jn",
                "01.08.2026/0710 hrs",
                "Train 22691 Rajdhani SF Express · 25 personnel",
            ),
            leg(
                "rail",
                "Charlapalli Rly. Stn.",
                "01.08.2026/1630 hrs",
                "Train 15645 · CHZ → Rangiya Jn · 17 personnel",
            ),
            leg(
                "rail",
                "Hyderabad Rly. Station",
                "01.08.2026/2300 hrs",
                "Train 12721 Dakshin Express · 18 personnel",
            ),
            leg(
                "rail",
                "Secunderabad Jn",
                "02.08.2026/1250 hrs",
                "Train 12285 Duronto Express · 5 personnel",
            ),
            leg(
                "rail",
                "Charlapalli Rly. Stn.",
                "03.08.2026/1630 hrs",
                "Train 17031 CHZ–AGTL Express · 7 personnel",
            ),
        ],
        "remarks": "Report at Sports Tower and Athletic Stadium 2 hrs before journey.",
    },
    "WEST BENGAL POLICE": {
        "manager": "Goutam Chakraborty",
        "phone": "9433803233",
        "primary": leg(
            "rail",
            "Sikandrabad Jn",
            "31.07.2026/0830 hrs",
            "Train 07046 Nahar Lagum Special (Summer Special) · 69 personnel",
        ),
        "extra": [],
        "remarks": "Transport required to Sikandrabad Jn. Pickup 04:30 Sports Tower Gachibowli (69 personnel); Team Manager at TGPA JOM 06:00.",
    },
    "PUNJAB POLICE": {
        "manager": "Rajwinder Kaur",
        "phone": "8146577701",
        "primary": leg(
            "rail",
            "Secunderabad Jn",
            "31.07.2026/0600 hrs",
            "Train 12723 Telangana Exp · 8 personnel",
        ),
        "extra": [],
        "remarks": "Pickup at TGPA.",
    },
    "MANIPUR POLICE": {
        "manager": "",
        "phone": "",
        "primary": leg(
            "flight",
            "Rajiv Gandhi Intl Airport (Shamshabad)",
            "04.08.2026/0520 hrs",
            "RGIA → Imphal · Batch A · 16 personnel",
        ),
        "extra": [
            leg(
                "flight",
                "Rajiv Gandhi Intl Airport (Shamshabad)",
                "04.08.2026/0815 hrs",
                "RGIA → Imphal · Batch B · 22 personnel",
            ),
            leg(
                "flight",
                "Rajiv Gandhi Intl Airport (Shamshabad)",
                "04.08.2026/1920 hrs",
                "RGIA → Imphal · Batch C · 6 personnel",
            ),
        ],
        "remarks": "All 44 personnel depart by air RGIA → Imphal on 04.08.2026.",
    },
    "Andhra Pradesh": {
        "manager": "",
        "phone": "",
        "primary": leg(
            "bus",
            "Bus Boarding Point",
            "30.07.2026/2100 hrs",
            "MGBS (Mahatma Gandhi Bus Station) · 24 personnel",
        ),
        "extra": [],
        "remarks": "",
    },
    "ITBP": {
        "manager": "",
        "phone": "",
        "primary": leg(
            "rail",
            "Secunderabad Jn",
            "30.07.2026/2325 hrs",
            "Train 12721 Dakshin SF Ex · → H Nizamuddin arr 01.08.2026/2325 hrs · 46 personnel (30 M, 16 F)",
            team_label="ITBP Judo / Pencak Silat",
        ),
        "extra": [
            leg(
                "rail",
                "Secunderabad Jn",
                "30.07.2026/2325 hrs",
                "Train 12721 Dakshin SF Ex · → H Nizamuddin arr 01.08.2026/2325 hrs · 31 personnel (17 M, 14 F)",
                team_label="ITBP Wushu",
            ),
            leg(
                "rail",
                "Secunderabad Jn",
                "30.07.2026/2325 hrs",
                "Train 12721 Dakshin SF Ex · → H Nizamuddin arr 01.08.2026/2325 hrs · 20 personnel (16 M, 4 F)",
                team_label="ITBP Taekwondo",
            ),
            leg(
                "rail",
                "Secunderabad Jn",
                "02.08.2026/1250 hrs",
                "Train 12285 Duronto Ex · 17 personnel (11 M, 6 F)",
                team_label="ITBP Karate",
            ),
        ],
        "remarks": "",
    },
    "RPF": {
        "manager": "Sanjit Sarkar",
        "phone": "9862153714",
        "primary": leg(
            "rail",
            "Charlapalli Rly. Stn.",
            "01.08.2026/0400 hrs",
            "Train 07221 CHZ → Santragachi · RPF team proceeding to Guwahati",
        ),
        "extra": [],
        "remarks": "Pickup RPF Training School, Moulali at 04:00 on 01.08.2026.",
    },
    "MIZORAM POLICE": {
        "manager": "F. Lalhmingliana MPS",
        "phone": "9436142704",
        "primary": leg(
            "rail",
            "Charlapalli Rly. Stn.",
            "01.08.2026/1625 hrs",
            "Train 15645 CHZ SCL Express · 6 personnel",
            team_label="Mizoram Team",
        ),
        "extra": [
            leg(
                "flight",
                "Rajiv Gandhi Intl Airport (Shamshabad)",
                "01.08.2026/1730 hrs",
                "Flight QP-1407 Akasa Air · Manager only · RGIA",
                team_label="Mizoram Manager",
            ),
        ],
        "remarks": "Separate transport required. Manager pickup IOM Room 124 TGPA; team pickup SOTC Mess TGPA.",
    },
    "UTTARPRADESH": {
        "manager": "Anand Kumar (DySP)",
        "phone": "9953523571",
        "primary": leg(
            "flight",
            "Rajiv Gandhi Intl Airport (Shamshabad)",
            "31.07.2026/1615 hrs",
            "IndiGo 6E-501 · DySP Anand Kumar",
        ),
        "extra": [
            leg(
                "rail",
                "Secunderabad Jn",
                "30.07.2026/2325 hrs",
                "Train 12721 · 19 personnel",
            ),
            leg(
                "rail",
                "Secunderabad Jn",
                "31.07.2026/0600 hrs",
                "Train 12723 · 25 personnel",
            ),
            leg(
                "rail",
                "Secunderabad Jn",
                "31.07.2026/0915 hrs",
                "Train 15024 · 16 personnel",
            ),
            leg(
                "rail",
                "Secunderabad Jn",
                "31.07.2026/2100 hrs",
                "Train 07075 · 50 personnel",
            ),
        ],
        "remarks": "Pickup at TGPA as per train timings. 7 personnel travel details not yet received.",
    },
}


def apply_plan(row: dict, plan: dict) -> None:
    org = row["org"]
    primary = dict(plan["primary"])
    if not primary.get("team_label"):
        primary["team_label"] = org
    if plan.get("remarks"):
        primary["details"] = (primary.get("details") or "").strip()
        if primary["details"]:
            primary["details"] += " · "
        primary["details"] += f"Remarks: {plan['remarks']}"

    row["travel_departure"] = primary
    extras = []
    for x in plan.get("extra") or []:
        e = dict(x)
        if not e.get("team_label"):
            e["team_label"] = org
        e["direction"] = "departure"
        extras.append(e)
    row["travel_departure_extra"] = extras


def main() -> None:
    doc = store._read(store.FILES["arrival"], {"rows": [], "hubs": store.DEFAULT_HUBS})
    rows = doc.get("rows") or []
    hubs = store.normalize_hubs(doc.get("hubs"))
    by_org = {r["org"]: r for r in rows}
    by_key = {store._org_key(r["org"]): r for r in rows}

    updated = 0
    missing = []
    for org, plan in DEPARTURE_PLANS.items():
        row = by_org.get(org) or by_key.get(store._org_key(org))
        if not row:
            canonical = store._resolve_org_name(org)
            row = by_org.get(canonical) or by_key.get(store._org_key(canonical))
        if not row:
            missing.append(org)
            continue
        apply_plan(row, plan)
        updated += 1

    store._write(store.FILES["arrival"], {"hubs": hubs, "rows": rows})
    store.merge_bundle()

    print(f"Departure import: {updated} teams updated")
    if missing:
        print("Missing in arrival.json:", ", ".join(missing))
    for org in sorted(DEPARTURE_PLANS):
        p = DEPARTURE_PLANS[org]
        n = 1 + len(p.get("extra") or [])
        print(f"  {org}: {n} leg(s) · {p['manager']} · {p['phone']}")


if __name__ == "__main__":
    main()
