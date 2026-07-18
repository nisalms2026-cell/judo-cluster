"""
Shared password for dashboard login (Flask + static Pages hash).

Reads (first match):
  1. env DASHBOARD_PASSWORD
  2. data/access.json  { "password": "..." }   — gitignored
  3. default JudoCluster2026 (change via access.json)
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, "data")
ACCESS_FILE = os.path.join(DATA_DIR, "access.json")
AUTH_FILE = os.path.join(DATA_DIR, "auth.json")
EXAMPLE_FILE = os.path.join(DATA_DIR, "access.example.json")
DEFAULT_PASSWORD = "JudoCluster2026"


def ensure_access_file() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    if os.path.isfile(ACCESS_FILE):
        return
    password = DEFAULT_PASSWORD
    if os.path.isfile(EXAMPLE_FILE):
        try:
            with open(EXAMPLE_FILE, "r", encoding="utf-8") as f:
                password = (json.load(f).get("password") or DEFAULT_PASSWORD).strip() or DEFAULT_PASSWORD
        except Exception:
            password = DEFAULT_PASSWORD
    with open(ACCESS_FILE, "w", encoding="utf-8") as f:
        json.dump({"password": password}, f, indent=2)
        f.write("\n")


def get_password() -> str:
    env = (os.environ.get("DASHBOARD_PASSWORD") or "").strip()
    if env:
        return env
    ensure_access_file()
    try:
        with open(ACCESS_FILE, "r", encoding="utf-8") as f:
            pw = (json.load(f).get("password") or "").strip()
            if pw:
                return pw
    except Exception:
        pass
    return DEFAULT_PASSWORD


def password_sha256(password: str | None = None) -> str:
    raw = password if password is not None else get_password()
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def check_password(candidate: str) -> bool:
    if not candidate:
        return False
    return secrets.compare_digest(
        password_sha256(candidate),
        password_sha256(),
    )


def flask_secret() -> str:
    env = (os.environ.get("DASHBOARD_SECRET") or "").strip()
    if env:
        return env
    # Stable per-machine secret derived from password (good enough for LAN ops)
    return password_sha256("flask-secret:" + get_password())


def auth_bundle() -> dict:
    """Hash + client token (same scheme as export_static.py / GitHub Pages)."""
    pwhash = password_sha256()
    token = hashlib.sha256(("judo-token:" + pwhash).encode("utf-8")).hexdigest()
    return {
        "pwhash": pwhash,
        "token": token,
        "hint": "Set password in data/access.json (gitignored) or DASHBOARD_PASSWORD",
    }


def ensure_auth_file() -> dict:
    """Keep data/auth.json in sync with the active password (for Pages + Bearer login)."""
    bundle = auth_bundle()
    try:
        if os.path.isfile(AUTH_FILE):
            with open(AUTH_FILE, "r", encoding="utf-8") as f:
                cur = json.load(f)
            if cur.get("pwhash") == bundle["pwhash"] and cur.get("token") == bundle["token"]:
                return bundle
    except Exception:
        pass
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(AUTH_FILE, "w", encoding="utf-8") as f:
        json.dump(bundle, f, indent=2)
        f.write("\n")
    return bundle


def auth_token() -> str:
    return ensure_auth_file()["token"]


def check_auth_token(candidate: str) -> bool:
    if not candidate:
        return False
    return secrets.compare_digest(candidate.strip(), auth_token())
