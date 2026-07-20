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
from import_players import find_mis_workbook, import_and_save as import_players_workbook

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
    import importlib
    global store
    store = importlib.reload(store)
    with LOCK:
        bundle = store.merge_bundle()
        players = bundle.get("players") or {}
        tc = bundle.get("tech_committee") or {}
        resp = jsonify(bundle)
        resp.headers["X-Players-Count"] = str(len(players.get("players") or []))
        resp.headers["X-TC-Count"] = str(len(tc.get("members") or []))
        return resp


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
    leg_index = int(payload.get("leg_index") or 0)
    with LOCK:
        return jsonify(store.save_arrival_row(org, travel, extra, field=field, leg_index=leg_index))


@app.route("/api/arrival/<path:org>/legs", methods=["POST"])
def post_arrival_leg(org):
    payload = request.get_json(force=True) or {}
    field = payload.get("field") or "travel"
    if payload.get("direction") == "departure" or field == "travel_departure":
        field = "travel_departure"
    with LOCK:
        try:
            return jsonify(store.add_arrival_leg(org, field=field))
        except KeyError as e:
            return jsonify({"error": str(e)}), 404


@app.route("/api/arrival/<path:org>/legs/<int:leg_index>", methods=["DELETE"])
def delete_arrival_leg(org, leg_index):
    field = request.args.get("field") or "travel"
    if request.args.get("direction") == "departure" or field == "travel_departure":
        field = "travel_departure"
    with LOCK:
        try:
            return jsonify(store.remove_arrival_leg(org, leg_index, field=field))
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except KeyError as e:
            return jsonify({"error": str(e)}), 404


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


# ── Liaison Officers ───────────────────────────────────────
@app.route("/api/lo/officers", methods=["POST"])
def post_lo_officer():
    payload = request.get_json(force=True) or {}
    with LOCK:
        try:
            return jsonify(store.save_lo_officer(payload))
        except ValueError as e:
            return jsonify({"error": str(e)}), 400


@app.route("/api/lo/officers/<officer_id>", methods=["PUT"])
def put_lo_officer(officer_id):
    payload = request.get_json(force=True) or {}
    with LOCK:
        try:
            return jsonify(store.save_lo_officer(payload, officer_id=officer_id))
        except KeyError:
            return jsonify({"error": "Officer not found"}), 404
        except ValueError as e:
            return jsonify({"error": str(e)}), 400


@app.route("/api/lo/officers/<officer_id>", methods=["DELETE"])
def delete_lo_officer(officer_id):
    with LOCK:
        try:
            return jsonify(store.delete_lo_officer(officer_id))
        except KeyError:
            return jsonify({"error": "Officer not found"}), 404


@app.route("/api/lo/assignments", methods=["POST"])
def post_lo_assignment():
    payload = request.get_json(force=True) or {}
    with LOCK:
        try:
            return jsonify(store.save_lo_assignment(payload))
        except ValueError as e:
            return jsonify({"error": str(e)}), 400


@app.route("/api/lo/assignments/<assignment_id>", methods=["PUT"])
def put_lo_assignment(assignment_id):
    payload = request.get_json(force=True) or {}
    with LOCK:
        try:
            return jsonify(store.save_lo_assignment(payload, assignment_id=assignment_id))
        except KeyError:
            return jsonify({"error": "Assignment not found"}), 404
        except ValueError as e:
            return jsonify({"error": str(e)}), 400


@app.route("/api/lo/assignments/<assignment_id>", methods=["DELETE"])
def delete_lo_assignment(assignment_id):
    with LOCK:
        try:
            return jsonify(store.delete_lo_assignment(assignment_id))
        except KeyError:
            return jsonify({"error": "Assignment not found"}), 404


@app.route("/api/fleet/vehicles", methods=["POST"])
def post_fleet_vehicle():
    payload = request.get_json(force=True) or {}
    with LOCK:
        try:
            return jsonify(store.save_fleet_vehicle(payload))
        except ValueError as e:
            return jsonify({"error": str(e)}), 400


@app.route("/api/fleet/vehicles/<vehicle_id>", methods=["PUT"])
def put_fleet_vehicle(vehicle_id):
    payload = request.get_json(force=True) or {}
    with LOCK:
        try:
            return jsonify(store.save_fleet_vehicle(payload, vehicle_id=vehicle_id))
        except KeyError:
            return jsonify({"error": "Vehicle not found"}), 404
        except ValueError as e:
            return jsonify({"error": str(e)}), 400


@app.route("/api/fleet/vehicles/<vehicle_id>", methods=["DELETE"])
def delete_fleet_vehicle(vehicle_id):
    with LOCK:
        try:
            return jsonify(store.delete_fleet_vehicle(vehicle_id))
        except KeyError:
            return jsonify({"error": "Vehicle not found"}), 404


# ── Senior Officials ───────────────────────────────────────
@app.route("/api/so/officials/<official_id>/driver", methods=["PUT"])
def put_so_driver_assign(official_id):
    payload = request.get_json(force=True) or {}
    person_id = payload.get("person_id") or payload.get("adm_person_id") or payload.get("driver_adm_person_id") or ""
    with LOCK:
        try:
            return jsonify(store.assign_so_driver(official_id, person_id))
        except KeyError:
            return jsonify({"error": "Official or ADM driver not found"}), 404
        except ValueError as e:
            return jsonify({"error": str(e)}), 400


@app.route("/api/so/officials/<official_id>/sync-driver", methods=["PUT"])
def put_so_driver_sync(official_id):
    with LOCK:
        try:
            return jsonify(store.sync_so_driver_from_adm(official_id))
        except KeyError:
            return jsonify({"error": "Official not found"}), 404
        except ValueError as e:
            return jsonify({"error": str(e)}), 400


@app.route("/api/so/officials", methods=["POST"])
def post_so_official():
    payload = request.get_json(force=True) or {}
    with LOCK:
        try:
            return jsonify(store.save_so_official(payload))
        except ValueError as e:
            return jsonify({"error": str(e)}), 400


@app.route("/api/so/officials/<official_id>", methods=["PUT"])
def put_so_official(official_id):
    payload = request.get_json(force=True) or {}
    with LOCK:
        try:
            return jsonify(store.save_so_official(payload, official_id=official_id))
        except KeyError:
            return jsonify({"error": "Official not found"}), 404
        except ValueError as e:
            return jsonify({"error": str(e)}), 400


@app.route("/api/so/officials/<official_id>", methods=["DELETE"])
def delete_so_official(official_id):
    with LOCK:
        try:
            return jsonify(store.delete_so_official(official_id))
        except KeyError:
            return jsonify({"error": "Official not found"}), 404


@app.route("/api/so/officials/<official_id>/vehicle", methods=["PUT"])
def put_so_vehicle_assign(official_id):
    payload = request.get_json(force=True) or {}
    vehicle_id = payload.get("vehicle_id", "")
    with LOCK:
        try:
            return jsonify(store.assign_so_vehicle(official_id, vehicle_id))
        except KeyError:
            return jsonify({"error": "Official or vehicle not found"}), 404


@app.route("/api/so/officials/<official_id>/lo", methods=["PUT"])
def put_so_lo_assign(official_id):
    payload = request.get_json(force=True) or {}
    officer_id = payload.get("officer_id") or payload.get("lo_officer_id") or ""
    with LOCK:
        try:
            return jsonify(store.assign_so_lo_officer(official_id, officer_id))
        except KeyError:
            return jsonify({"error": "Official or Liaison Officer not found"}), 404
        except ValueError as e:
            return jsonify({"error": str(e)}), 400


@app.route("/api/so/vehicles", methods=["POST"])
def post_so_vehicle():
    payload = request.get_json(force=True) or {}
    with LOCK:
        try:
            return jsonify(store.save_fleet_vehicle(payload))
        except ValueError as e:
            return jsonify({"error": str(e)}), 400


@app.route("/api/so/vehicles/<vehicle_id>", methods=["PUT"])
def put_so_vehicle(vehicle_id):
    payload = request.get_json(force=True) or {}
    with LOCK:
        try:
            return jsonify(store.save_fleet_vehicle(payload, vehicle_id=vehicle_id))
        except KeyError:
            return jsonify({"error": "Vehicle not found"}), 404
        except ValueError as e:
            return jsonify({"error": str(e)}), 400


@app.route("/api/so/vehicles/<vehicle_id>", methods=["DELETE"])
def delete_so_vehicle(vehicle_id):
    with LOCK:
        try:
            return jsonify(store.delete_fleet_vehicle(vehicle_id))
        except KeyError:
            return jsonify({"error": "Vehicle not found"}), 404


@app.route("/api/so/assignments", methods=["POST"])
def post_so_assignment():
    payload = request.get_json(force=True) or {}
    with LOCK:
        try:
            return jsonify(store.save_so_lo_assignment(payload))
        except ValueError as e:
            return jsonify({"error": str(e)}), 400


@app.route("/api/so/assignments/<assignment_id>", methods=["PUT"])
def put_so_assignment(assignment_id):
    payload = request.get_json(force=True) or {}
    with LOCK:
        try:
            return jsonify(store.save_so_lo_assignment(payload, assignment_id=assignment_id))
        except KeyError:
            return jsonify({"error": "Assignment not found"}), 404
        except ValueError as e:
            return jsonify({"error": str(e)}), 400


@app.route("/api/so/assignments/<assignment_id>", methods=["DELETE"])
def delete_so_assignment(assignment_id):
    with LOCK:
        try:
            return jsonify(store.delete_so_lo_assignment(assignment_id))
        except KeyError:
            return jsonify({"error": "Assignment not found"}), 404


# ── Technical Committee ────────────────────────────────────
@app.route("/api/tc/members", methods=["POST"])
def post_tc_member():
    payload = request.get_json(force=True) or {}
    with LOCK:
        try:
            return jsonify(store.save_tc_member(payload))
        except ValueError as e:
            return jsonify({"error": str(e)}), 400


@app.route("/api/tc/members/<member_id>", methods=["PUT"])
def put_tc_member(member_id):
    payload = request.get_json(force=True) or {}
    with LOCK:
        try:
            return jsonify(store.save_tc_member(payload, member_id=member_id))
        except KeyError:
            return jsonify({"error": "Member not found"}), 404
        except ValueError as e:
            return jsonify({"error": str(e)}), 400


@app.route("/api/tc/members/<member_id>/travel", methods=["PUT"])
def put_tc_travel(member_id):
    payload = request.get_json(force=True) or {}
    travel = payload.get("travel") or payload
    field = payload.get("field") or "travel"
    if payload.get("direction") == "departure" or (
        isinstance(travel, dict) and travel.get("direction") == "departure"
    ):
        field = "travel_departure"
    leg_index = int(payload.get("leg_index") or 0)
    with LOCK:
        try:
            return jsonify(store.save_tc_travel(member_id, travel, field=field, leg_index=leg_index))
        except KeyError:
            return jsonify({"error": "Member not found"}), 404


@app.route("/api/tc/members/<member_id>/legs", methods=["POST"])
def post_tc_leg(member_id):
    payload = request.get_json(force=True) or {}
    field = payload.get("field") or "travel"
    if payload.get("direction") == "departure" or field == "travel_departure":
        field = "travel_departure"
    with LOCK:
        try:
            return jsonify(store.add_tc_leg(member_id, field=field))
        except KeyError:
            return jsonify({"error": "Member not found"}), 404


@app.route("/api/tc/members/<member_id>/legs/<int:leg_index>", methods=["DELETE"])
def delete_tc_leg(member_id, leg_index):
    field = request.args.get("field") or "travel"
    if request.args.get("direction") == "departure" or field == "travel_departure":
        field = "travel_departure"
    with LOCK:
        try:
            return jsonify(store.remove_tc_leg(member_id, leg_index, field=field))
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except KeyError:
            return jsonify({"error": "Member or leg not found"}), 404


@app.route("/api/tc/members/<member_id>", methods=["DELETE"])
def delete_tc_member(member_id):
    with LOCK:
        try:
            return jsonify(store.delete_tc_member(member_id))
        except KeyError:
            return jsonify({"error": "Member not found"}), 404


# ── Players (AIPSCB MIS roster) ────────────────────────────
@app.route("/api/players/import", methods=["POST"])
def api_players_import():
    payload = request.get_json(silent=True) or {}
    path = payload.get("path") or find_mis_workbook()
    with LOCK:
        try:
            return jsonify(import_players_workbook(path))
        except Exception as e:
            return jsonify({"error": str(e)}), 400


@app.route("/api/players/members", methods=["POST"])
def post_player():
    payload = request.get_json(force=True) or {}
    with LOCK:
        try:
            return jsonify(store.save_player(payload))
        except ValueError as e:
            return jsonify({"error": str(e)}), 400


@app.route("/api/players/members/<player_id>", methods=["PUT"])
def put_player(player_id):
    payload = request.get_json(force=True) or {}
    with LOCK:
        try:
            return jsonify(store.save_player(payload, player_id=player_id))
        except KeyError:
            return jsonify({"error": "Player not found"}), 404
        except ValueError as e:
            return jsonify({"error": str(e)}), 400


@app.route("/api/players/members/<player_id>", methods=["DELETE"])
def delete_player(player_id):
    with LOCK:
        try:
            return jsonify(store.delete_player(player_id))
        except KeyError:
            return jsonify({"error": "Player not found"}), 404


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
        "doctor": int(payload.get("doctor", 0) or 0),
        "strength": strength,
        "total": sum(strength.values()) + int(payload.get("doctor", 0) or 0),
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
            acc_keys = {"location", "gos_m", "sos_m", "ors_m", "gos_f", "sos_f", "ors_f", "doctor"}
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
