import logging

from config import SUPER_ADMIN_EMAIL, MCOL
from db import supabase
import sheets

logger = logging.getLogger(__name__)


def _v(row, key):
    val = row.get(key)
    return val if val is not None else ""


def _row_to_sheets_fmt(row):
    return {
        "Email":     _v(row, "email"),
        "Role":      _v(row, "role"),
        "AddedBy":   _v(row, "added_by"),
        "AddedAt":   _v(row, "added_at"),
        "Name":      _v(row, "name"),
        "ShortName": _v(row, "short_name"),
    }


def list_members():
    result = supabase.table("members").select("*").execute()
    return [_row_to_sheets_fmt(r) for r in result.data]


def lookup_member(email):
    """Return role string for email, or None if not a member."""
    if email.lower() == SUPER_ADMIN_EMAIL.lower():
        return "admin"
    try:
        result = supabase.table("members").select("role").eq("email", email.lower()).execute()
        if result.data:
            return result.data[0].get("role") or "member"
    except Exception as exc:
        logger.error("lookup_member Supabase query failed for %s: %s", email, exc)
    return None


def member_exists(email):
    result = supabase.table("members").select("email").eq("email", email.lower()).execute()
    return bool(result.data)


def add_member(email, role, added_by, now_str, name, short_name):
    sb_row = {
        "email":      email.lower(),
        "role":       role,
        "added_by":   added_by or None,
        "added_at":   now_str or None,
        "name":       name or None,
        "short_name": short_name or None,
    }
    supabase.table("members").insert(sb_row).execute()

    try:
        sheets.get_members_sheet().append_row(
            [email, role, added_by, now_str, name, short_name]
        )
    except Exception as exc:
        logger.warning("Members Sheet mirror append failed for %s: %s", email, exc)


def remove_member(email):
    """Delete member by email. Returns True if found and deleted, False if not found."""
    result = supabase.table("members").select("email").eq("email", email.lower()).execute()
    if not result.data:
        return False

    supabase.table("members").delete().eq("email", email.lower()).execute()

    try:
        ms   = sheets.get_members_sheet()
        rows = ms.get_all_values()
        for i, row in enumerate(rows):
            if i == 0:
                continue
            if row[0].lower() == email.lower():
                ms.delete_rows(i + 1)
                break
    except Exception as exc:
        logger.warning("Members Sheet mirror delete failed for %s: %s", email, exc)

    return True


def update_member(email, role=None, name=None, short_name=None):
    """Update member fields. Returns True if found, False if not found."""
    result = supabase.table("members").select("email").eq("email", email.lower()).execute()
    if not result.data:
        return False

    updates = {}
    if role       is not None: updates["role"]       = role
    if name       is not None: updates["name"]       = name or None
    if short_name is not None: updates["short_name"] = short_name or None

    supabase.table("members").update(updates).eq("email", email.lower()).execute()

    try:
        ms   = sheets.get_members_sheet()
        rows = ms.get_all_values()
        for i, row in enumerate(rows):
            if i == 0:
                continue
            if row[0].lower() == email.lower():
                if role       is not None: ms.update_cell(i + 1, MCOL["role"],       role)
                if name       is not None: ms.update_cell(i + 1, MCOL["name"],       name or "")
                if short_name is not None: ms.update_cell(i + 1, MCOL["short_name"], short_name or "")
                break
    except Exception as exc:
        logger.warning("Members Sheet mirror update failed for %s: %s", email, exc)

    return True
