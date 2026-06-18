from flask import Blueprint, jsonify, request, session
from datetime import datetime

from config import VALID_ROLES, SUPER_ADMIN_EMAIL
from repositories import members_repo
from auth import is_logged_in, is_admin

members_bp = Blueprint('members', __name__)


@members_bp.route("/api/members", methods=["GET"])
def api_get_members():
    if not is_logged_in() or not is_admin():
        return jsonify({"error": "Admin only"}), 403
    try:
        return jsonify(members_repo.list_members())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@members_bp.route("/api/members/directory", methods=["GET"])
def api_members_directory():
    """Lightweight email→name lookup for all logged-in users."""
    if not is_logged_in():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        rows   = members_repo.list_members()
        result = [{"email": r.get("Email",""), "name": r.get("Name",""), "short_name": r.get("ShortName","")} for r in rows]
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@members_bp.route("/api/members", methods=["POST"])
def api_add_member():
    if not is_logged_in() or not is_admin():
        return jsonify({"error": "Admin only"}), 403
    data       = request.json or {}
    email      = data.get("email",      "").strip().lower()
    role       = data.get("role",       "member")
    name       = data.get("name",       "").strip()
    short_name = data.get("short_name", "").strip()
    if not email:
        return jsonify({"error": "Email is required"}), 400
    if role not in VALID_ROLES:
        return jsonify({"error": "Invalid role"}), 400
    try:
        if members_repo.member_exists(email):
            return jsonify({"error": "Email already exists"}), 409
        members_repo.add_member(email, role, session["user_email"],
                                datetime.now().strftime("%Y-%m-%d %H:%M"), name, short_name)
        return jsonify({"status": "added"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@members_bp.route("/api/members", methods=["DELETE"])
def api_remove_member():
    if not is_logged_in() or not is_admin():
        return jsonify({"error": "Admin only"}), 403
    email = (request.json or {}).get("email", "").strip().lower()
    if not email:
        return jsonify({"error": "Email is required"}), 400
    if email == SUPER_ADMIN_EMAIL.lower():
        return jsonify({"error": "Cannot remove super admin"}), 403
    try:
        if not members_repo.remove_member(email):
            return jsonify({"error": "Member not found"}), 404
        return jsonify({"status": "removed"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@members_bp.route("/api/members", methods=["PATCH"])
def api_update_member():
    if not is_logged_in() or not is_admin():
        return jsonify({"error": "Admin only"}), 403
    data       = request.json or {}
    email      = data.get("email",      "").strip().lower()
    role       = data.get("role")
    name       = data.get("name")
    short_name = data.get("short_name")
    if not email:
        return jsonify({"error": "Email is required"}), 400
    if role is not None and role not in VALID_ROLES:
        return jsonify({"error": "Invalid role"}), 400
    if email == SUPER_ADMIN_EMAIL.lower():
        return jsonify({"error": "Cannot modify super admin"}), 403
    if role is None and name is None and short_name is None:
        return jsonify({"error": "Nothing to update"}), 400
    try:
        if not members_repo.update_member(email, role=role, name=name, short_name=short_name):
            return jsonify({"error": "Member not found"}), 404
        return jsonify({"status": "updated"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
