from flask import Blueprint, jsonify, request

from sheets import ensure_headers
from repositories import sources_repo
from auth import is_logged_in, is_admin

sources_bp = Blueprint('sources', __name__)


@sources_bp.route("/api/sources", methods=["GET"])
def api_get_sources():
    if not is_logged_in():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        return jsonify(sources_repo.list_sources())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@sources_bp.route("/api/sources", methods=["POST"])
def api_add_source():
    if not is_logged_in() or not is_admin():
        return jsonify({"error": "Admin only"}), 403
    data  = request.json or {}
    name  = data.get("name",  "").strip()
    stype = data.get("type",  "").strip()
    notes = data.get("notes", "").strip()
    if not name:
        return jsonify({"error": "Source name is required"}), 400
    try:
        sid = sources_repo.add_source(name, stype, notes)
        return jsonify({"status": "added", "id": sid})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@sources_bp.route("/api/init", methods=["POST"])
def api_init():
    if not is_logged_in() or not is_admin():
        return jsonify({"error": "Admin only"}), 403
    try:
        ensure_headers()
        return jsonify({"status": "Sheets initialized"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
