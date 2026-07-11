from flask import Blueprint, jsonify
from auth import is_logged_in, is_admin
from db import supabase

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/api/admin/login-log")
def api_login_log():
    if not is_logged_in():
        return jsonify({"error": "Unauthorized"}), 401
    if not is_admin():
        return jsonify({"error": "Forbidden"}), 403
    try:
        result = (
            supabase.table("login_log")
            .select("email,name,role,logged_in_at")
            .order("logged_in_at", desc=True)
            .limit(500)
            .execute()
        )
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    return jsonify(result.data)
