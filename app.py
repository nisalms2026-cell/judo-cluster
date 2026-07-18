"""
11th All India Police Judo Cluster 2026 — CISF Host, Hyderabad
LAN Ops Dashboard

View (read-only) and Edit run on different ports:
  View:  py app.py --mode view --port 5000
  Edit:  py app.py --mode edit --port 5001

Or use start_both.bat
"""
from __future__ import annotations

import argparse
import os
import threading
from datetime import timedelta

from flask import Flask, jsonify, redirect, request, send_from_directory, session

import authutil
import store
from import_excel import find_latest_workbook, import_workbook

BASE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(BASE, "assets")

# Set by main() / create_app()
APP_MODE = os.environ.get("DASHBOARD_MODE", "edit").lower()  # view | edit
APP_PORT = int(os.environ.get("DASHBOARD_PORT", "5000"))

app = Flask(__name__)
app.secret_key = authutil.flask_secret()
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=timedelta(days=14),
    SESSION_REFRESH_EACH_REQUEST=True,
)
LOCK = threading.Lock()

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
PUBLIC_PATHS = {
    "/login",
    "/login.html",
    "/api/login",
    "/api/auth/status",
    "/api/config",
}


def is_edit_mode() -> bool:
    return APP_MODE == "edit"


def request_bearer_token() -> str:
    auth = request.headers.get("Authorization") or ""
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return (request.headers.get("X-Dashboard-Token") or "").strip()


def is_logged_in() -> bool:
    if session.get("auth_ok"):
        return True
    # Fallback when browsers drop LAN cookies — token from login / localStorage
    return authutil.check_auth_token(request_bearer_token())


@app.before_request
def require_login():
    path = request.path or "/"
    if path.startswith("/assets/"):
        return None
    if path in PUBLIC_PATHS:
        return None
    if is_logged_in():
        return None
    if path.startswith("/api/"):
        return jsonify({"error": "Login required", "login": "/login.html"}), 401
    return redirect("/login.html")


@app.before_request
def block_writes_in_view_mode():
    if is_edit_mode():
        return None
    path = request.path or "/"
    # Login/logout must work on the View server too
    if path in ("/api/login", "/api/logout"):
        return None
    if request.method in WRITE_METHODS and path.startswith("/api/"):
        return jsonify({
            "error": "Read-only view server. Use the Edit port to make changes.",
            "mode": "view",
            "hint": f"Edit URL is usually http://<host>:5001",
        }), 403
    return None


@app.route("/")
def index():
    resp = send_from_directory(BASE, "index.html")
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return resp


@app.route("/login")
@app.route("/login.html")
def login_page():
    if is_logged_in():
        return redirect("/")
    resp = send_from_directory(BASE, "login.html")
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return resp


@app.route("/assets/<path:filename>")
def assets(filename):
    return send_from_directory(ASSETS, filename)


@app.route("/api/auth/status", methods=["GET"])
def api_auth_status():
    ok = is_logged_in()
    return jsonify({
        "ok": ok,
        "mode": APP_MODE,
        "auth": "session+token" if ok else "none",
    })


@app.route("/api/login", methods=["POST"])
def api_login():
    payload = request.get_json(silent=True) or {}
    password = str(payload.get("password") or "")
    if not authutil.check_password(password):
        return jsonify({"ok": False, "error": "Invalid password"}), 401
    session.clear()
    session["auth_ok"] = True
    session.permanent = True
    token = authutil.auth_token()
    return jsonify({"ok": True, "mode": APP_MODE, "token": token})


@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"ok": True})


@app.route("/api/config", methods=["GET"])
def api_config():
    return jsonify({
        "mode": APP_MODE,
        "port": APP_PORT,
        "editable": is_edit_mode(),
        "label": "EDIT MODE" if is_edit_mode() else "VIEW ONLY",
        "auth_required": True,
        "logged_in": is_logged_in(),
    })


@app.route("/api/data", methods=["GET"])
def get_data():
    with LOCK:
        return jsonify(store.merge_bundle())


@app.route("/api/import", methods=["POST"])
def api_import():
    payload = request.get_json(silent=True) or {}
    path = payload.get("path") or find_latest_workbook()
    with LOCK:
        try:
            data = import_workbook(path)
            return jsonify(data)
        except Exception as e:
            return jsonify({"error": str(e)}), 400


# ── Accommodation ──────────────────────────────────────────
@app.route("/api/accommodation/<org>", methods=["PUT"])
def put_accommodation(org):
    payload = request.get_json(force=True)
    with LOCK:
        try:
            return jsonify(store.save_accommodation_row(org, payload))
        except KeyError:
            return jsonify({"error": "Organisation not found"}), 404


@app.route("/api/venues", methods=["POST"])
def post_venue():
    payload = request.get_json(force=True) or {}
    with LOCK:
        try:
            return jsonify(store.add_venue(payload.get("name", "")))
        except ValueError as e:
            return jsonify({"error": str(e)}), 400


@app.route("/api/venues/<path:name>", methods=["DELETE"])
def delete_venue(name):
    with LOCK:
        try:
            return jsonify(store.delete_venue(name))
        except ValueError as e:
            return jsonify({"error": str(e)}), 400


# ── Mess ───────────────────────────────────────────────────
@app.route("/api/mess/<org>", methods=["PUT"])
def put_mess(org):
    payload = request.get_json(force=True)
    mess = payload.get("mess", "")
    with LOCK:
        return jsonify(store.save_mess_row(org, mess))


@app.route("/api/mess/tgpa", methods=["PUT"])
def put_tgpa_mess():
    payload = request.get_json(force=True)
    with LOCK:
        return jsonify(store.save_tgpa_mess(payload))


# ── Arrival ────────────────────────────────────────────────
@app.route("/api/arrival/<path:org>", methods=["PUT"])
def put_arrival(org):
    payload = request.get_json(force=True)
    travel = payload.get("travel") or payload
    extra = payload.get("travel_extra")
    field = payload.get("field") or "travel"
    if payload.get("direction") == "departure" or (isinstance(travel, dict) and travel.get("direction") == "departure"):
        field = "travel_departure"
    with LOCK:
        return jsonify(store.save_arrival_row(org, travel, extra, field=field))


@app.route("/api/hubs", methods=["PUT"])
def put_hubs():
    payload = request.get_json(force=True) or {}
    hubs = payload.get("hubs") or payload
    with LOCK:
        return jsonify(store.save_hubs(hubs))


# ── Directory ──────────────────────────────────────────────
@app.route("/api/directory/<org>", methods=["PUT"])
def put_directory(org):
    payload = request.get_json(force=True)
    mgr = {}
    for k in ("name", "rank", "phone"):
        if k in payload:
            mgr[k] = payload[k]
        elif f"manager_{k}" in payload:
            mgr[k] = payload[f"manager_{k}"]
    with LOCK:
        return jsonify(store.save_directory_row(org, mgr))


# ── ADM Staff ──────────────────────────────────────────────
@app.route("/api/adm/persons", methods=["POST"])
def post_adm_person():
    payload = request.get_json(force=True) or {}
    with LOCK:
        try:
            return jsonify(store.save_adm_person(payload))
        except ValueError as e:
            return jsonify({"error": str(e)}), 400


@app.route("/api/adm/persons/<person_id>", methods=["PUT"])
def put_adm_person(person_id):
    payload = request.get_json(force=True) or {}
    with LOCK:
        try:
            return jsonify(store.save_adm_person(payload, person_id=person_id))
        except KeyError:
            return jsonify({"error": "Person not found"}), 404
        except ValueError as e:
            return jsonify({"error": str(e)}), 400


@app.route("/api/adm/persons/<person_id>", methods=["DELETE"])
def delete_adm_person(person_id):
    with LOCK:
        try:
            return jsonify(store.delete_adm_person(person_id))
        except KeyError:
            return jsonify({"error": "Person not found"}), 404


@app.route("/api/adm/tasks", methods=["POST"])
def post_adm_task():
    payload = request.get_json(force=True) or {}
    with LOCK:
        try:
            return jsonify(store.save_adm_task(payload))
        except ValueError as e:
            return jsonify({"error": str(e)}), 400


@app.route("/api/adm/tasks/<task_id>", methods=["PUT"])
def put_adm_task(task_id):
    payload = request.get_json(force=True) or {}
    with LOCK:
        try:
            return jsonify(store.save_adm_task(payload, task_id=task_id))
        except KeyError:
            return jsonify({"error": "Task not found"}), 404
        except ValueError as e:
            return jsonify({"error": str(e)}), 400


@app.route("/api/adm/tasks/<task_id>", methods=["DELETE"])
def delete_adm_task(task_id):
    with LOCK:
        try:
            return jsonify(store.delete_adm_task(task_id))
        except KeyError:
            return jsonify({"error": "Task not found"}), 404


@app.route("/api/adm/detailments", methods=["POST"])
def post_adm_detailment():
    payload = request.get_json(force=True) or {}
    with LOCK:
        try:
            return jsonify(store.save_adm_detailment(payload))
        except ValueError as e:
            return jsonify({"error": str(e)}), 400


@app.route("/api/adm/detailments/<detailment_id>", methods=["DELETE"])
def delete_adm_detailment(detailment_id):
    with LOCK:
        try:
            return jsonify(store.delete_adm_detailment(detailment_id))
        except KeyError:
            return jsonify({"error": "Detailment not found"}), 404


# ── Units add / delete ─────────────────────────────────────
@app.route("/api/units", methods=["POST"])
def add_unit():
    payload = request.get_json(force=True)
    org = (payload.get("org") or "").strip().upper()
    if not org:
        return jsonify({"error": "Organisation name required"}), 400
    strength = {
        "gos_m": int(payload.get("gos_m", 0) or 0),
        "sos_m": int(payload.get("sos_m", 0) or 0),
        "ors_m": int(payload.get("ors_m", 0) or 0),
        "gos_f": int(payload.get("gos_f", 0) or 0),
        "sos_f": int(payload.get("sos_f", 0) or 0),
        "ors_f": int(payload.get("ors_f", 0) or 0),
    }
    unit = {
        "org": org,
        "location": payload.get("location", "TGPA"),
        "manager": {
            "name": (payload.get("manager_name") or "").strip(),
            "rank": (payload.get("manager_rank") or "").strip(),
            "phone": (payload.get("manager_phone") or "").strip(),
        },
        "count_gos": {"male": 0, "female": 0},
        "count_sos": {"male": 0, "female": 0},
        "support": {"male": 0, "female": 0},
        "coach_male": {"sos": 0, "ors": 0},
        "coach_female": {"gos": 0, "sos": 0, "ors": 0},
        "doctor": 0,
        "strength": strength,
        "total": sum(strength.values()),
        "mess": payload.get("mess", ""),
        "travel": {"station": "", "arrival": "", "details": "", "status": "awaited"},
    }
    with LOCK:
        try:
            return jsonify(store.add_unit(unit))
        except ValueError as e:
            return jsonify({"error": str(e)}), 400


@app.route("/api/units/<org>", methods=["PUT"])
def update_unit_compat(org):
    payload = request.get_json(force=True)
    with LOCK:
        try:
            data = None
            acc_keys = {"location", "gos_m", "sos_m", "ors_m", "gos_f", "sos_f", "ors_f"}
            if acc_keys & set(payload.keys()):
                data = store.save_accommodation_row(org, payload)
            if "mess" in payload:
                data = store.save_mess_row(org, payload["mess"])
            if "travel" in payload:
                data = store.save_arrival_row(org, payload["travel"], payload.get("travel_extra"))
            mgr = {}
            for k in ("manager_name", "manager_rank", "manager_phone", "name", "rank", "phone"):
                if k in payload:
                    nk = k.replace("manager_", "")
                    mgr[nk] = payload[k]
            if mgr:
                data = store.save_directory_row(org, mgr)
            return jsonify(data or store.merge_bundle())
        except KeyError:
            return jsonify({"error": "Organisation not found"}), 404


@app.route("/api/units/<org>", methods=["DELETE"])
def delete_unit(org):
    with LOCK:
        try:
            return jsonify(store.delete_unit(org))
        except KeyError:
            return jsonify({"error": "Organisation not found"}), 404


@app.route("/api/rows", methods=["GET"])
def legacy_rows():
    with LOCK:
        data = store.merge_bundle()
        rows = []
        for u in data["units"]:
            s = u["strength"]
            rows.append([
                u["org"], u["location"],
                s.get("gos_m", 0), s.get("sos_m", 0), s.get("ors_m", 0),
                s.get("gos_f", 0), s.get("sos_f", 0), s.get("ors_f", 0),
            ])
        return jsonify({"updated_at": data["updated_at"], "rows": rows})


def main():
    global APP_MODE, APP_PORT
    parser = argparse.ArgumentParser(description="Judo Cluster Ops Dashboard")
    parser.add_argument(
        "--mode", choices=("view", "edit"), default=os.environ.get("DASHBOARD_MODE", "edit"),
        help="view = read-only display; edit = full save/import",
    )
    parser.add_argument(
        "--port", type=int, default=None,
        help="Port (defaults: view=5000, edit=5001)",
    )
    args = parser.parse_args()
    APP_MODE = args.mode.lower()
    APP_PORT = args.port if args.port is not None else (5000 if APP_MODE == "view" else 5001)
    os.environ["DASHBOARD_MODE"] = APP_MODE
    os.environ["DASHBOARD_PORT"] = str(APP_PORT)

    with LOCK:
        store.merge_bundle()
    authutil.ensure_access_file()
    authutil.ensure_auth_file()
    app.secret_key = authutil.flask_secret()

    print("=" * 56)
    print("11th All India Police Judo Cluster 2026 — Ops Dashboard")
    print(f"Mode : {APP_MODE.upper()} ({'read-only' if APP_MODE == 'view' else 'editable'})")
    print(f"URL  : http://localhost:{APP_PORT}")
    print(f"LAN  : http://<this-PC-IP>:{APP_PORT}")
    print("Login: password from data/access.json (or DASHBOARD_PASSWORD)")
    if APP_MODE == "view":
        print("Tip  : Start Edit on port 5001 for changes")
    else:
        print("Tip  : Share View on port 5000 with the team")
    print("=" * 56)
    app.run(host="0.0.0.0", port=APP_PORT, debug=False)


if __name__ == "__main__":
    main()
