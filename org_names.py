"""Canonical organisation / team names used across the dashboard."""

from __future__ import annotations

# Standard roster names (user-defined)
JAMMU_KASHMIR = "JAMMU & KASHMIR"
GUJRAT = "Gujrat"
ANDHRA_PRADESH = "Andhra Pradesh"

# All known aliases → canonical (lookup is case-insensitive on alias)
_ALIASES: dict[str, str] = {
    "J&K POLICE": JAMMU_KASHMIR,
    "J&K": JAMMU_KASHMIR,
    "JAMMU AND KASHMIR": JAMMU_KASHMIR,
    "JAMMU & KASHMIR": JAMMU_KASHMIR,
    "Jammu & Kashmir": JAMMU_KASHMIR,
    "GUJARAT POLICE": GUJRAT,
    "GUJARAT": GUJRAT,
    "Gujarat": GUJRAT,
    "GUJRAT": GUJRAT,
    "Gujrat": GUJRAT,
    "ANDHRA POLICE": ANDHRA_PRADESH,
    "ANDHRA PRADESH POLICE": ANDHRA_PRADESH,
    "ANDHRA PRADESH": ANDHRA_PRADESH,
    "Andhra Pradesh": ANDHRA_PRADESH,
    "UTTAR PRADESH": "UTTARPRADESH",
    "UTTARPRADESH": "UTTARPRADESH",
}

_LOOKUP = {k.upper(): v for k, v in _ALIASES.items()}


def canonical_org(name: str) -> str:
    """Return the standard roster name for a team/org label."""
    if not name:
        return name
    key = str(name).strip()
    return _LOOKUP.get(key.upper(), key)


def is_known_alias(name: str) -> bool:
    return str(name or "").strip().upper() in _LOOKUP
