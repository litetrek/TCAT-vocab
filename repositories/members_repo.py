import logging

from config import SUPER_ADMIN_EMAIL
from db import get_conn

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
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM members ORDER BY email")
                rows = cur.fetchall()
    finally:
        conn.close()
    return [_row_to_sheets_fmt(r) for r in rows]


def lookup_member(email):
    """Return role string for email, or None if not a member."""
    if email.lower() == SUPER_ADMIN_EMAIL.lower():
        return "admin"
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT role FROM members WHERE email = %s", (email.lower(),))
                row = cur.fetchone()
    except Exception as exc:
        logger.error("lookup_member query failed for %s: %s", email, exc)
        return None
    finally:
        conn.close()
    if row:
        return row["role"] or "member"
    return None


def member_exists(email):
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM members WHERE email = %s", (email.lower(),))
                return cur.fetchone() is not None
    finally:
        conn.close()


def add_member(email, role, added_by, now_str, name, short_name):
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO members (email, role, added_by, added_at, name, short_name)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (
                        email.lower(),
                        role,
                        added_by   or None,
                        now_str    or None,
                        name       or None,
                        short_name or None,
                    )
                )
    finally:
        conn.close()


def remove_member(email):
    """Delete member by email. Returns True if found and deleted, False if not found."""
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM members WHERE email = %s", (email.lower(),))
                if not cur.fetchone():
                    return False
                cur.execute("DELETE FROM members WHERE email = %s", (email.lower(),))
    finally:
        conn.close()
    return True


def update_member(email, role=None, name=None, short_name=None):
    """Update member fields. Returns True if found, False if not found."""
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM members WHERE email = %s", (email.lower(),))
                if not cur.fetchone():
                    return False
                updates = {}
                if role       is not None: updates["role"]       = role
                if name       is not None: updates["name"]       = name or None
                if short_name is not None: updates["short_name"] = short_name or None
                if updates:
                    set_clauses = [f"{c} = %s" for c in updates]
                    sql = f"UPDATE members SET {', '.join(set_clauses)} WHERE email = %s"
                    cur.execute(sql, list(updates.values()) + [email.lower()])
    finally:
        conn.close()
    return True
