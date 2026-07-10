import logging

from config import SUPER_ADMIN_EMAIL
from db import supabase

logger = logging.getLogger(__name__)


def _v(row, key):
    val = row.get(key)
    return val if val is not None else ""


def _fmt_ts(val):
    if not val:
        return ""
    if hasattr(val, 'strftime'):
        return val.strftime("%Y-%m-%d %H:%M")
    s = str(val).replace("T", " ")
    if "+" in s:
        s = s[:s.index("+")]
    if "." in s:
        s = s[:s.index(".")]
    return s[:16]


def _row_to_sheets_fmt(row):
    return {
        "Email":     _v(row, "email"),
        "Role":      _v(row, "role"),
        "AddedBy":   _v(row, "added_by"),
        "AddedAt":   _fmt_ts(row.get("added_at")),
        "Name":      _v(row, "name"),
        "ShortName": _v(row, "short_name"),
    }


def list_members():
    result = supabase.table("members").select("*").order("email").execute()
    return [_row_to_sheets_fmt(r) for r in result.data]


def lookup_member(email):
    """Return role string for email, or None if not a member."""
    if email.lower() == SUPER_ADMIN_EMAIL.lower():
        return "admin"
    try:
        result = (
            supabase.table("members")
            .select("role")
            .eq("email", email.lower())
            .limit(1)
            .execute()
        )
        if result.data:
            return result.data[0].get("role") or "member"
        return None
    except Exception as exc:
        logger.error("lookup_member query failed for %s: %s", email, exc)
        return None


def member_exists(email):
    result = (
        supabase.table("members")
        .select("email")
        .eq("email", email.lower())
        .limit(1)
        .execute()
    )
    return bool(result.data)


def add_member(email, role, added_by, now_str, name, short_name):
    supabase.table("members").insert({
        "email":      email.lower(),
        "role":       role,
        "added_by":   added_by    or None,
        "added_at":   now_str     or None,
        "name":       name        or None,
        "short_name": short_name  or None,
    }).execute()


def remove_member(email):
    """Delete member by email. Returns True if found and deleted, False if not found."""
    result = (
        supabase.table("members")
        .select("email")
        .eq("email", email.lower())
        .limit(1)
        .execute()
    )
    if not result.data:
        return False
    supabase.table("members").delete().eq("email", email.lower()).execute()
    return True


def update_member(email, role=None, name=None, short_name=None):
    """Update member fields. Returns True if found, False if not found."""
    result = (
        supabase.table("members")
        .select("email")
        .eq("email", email.lower())
        .limit(1)
        .execute()
    )
    if not result.data:
        return False
    updates = {}
    if role       is not None: updates["role"]       = role
    if name       is not None: updates["name"]       = name or None
    if short_name is not None: updates["short_name"] = short_name or None
    if updates:
        supabase.table("members").update(updates).eq("email", email.lower()).execute()
    return True
