import logging

from db import get_conn

logger = logging.getLogger(__name__)


def _v(row, key):
    val = row.get(key)
    return val if val is not None else ""


def _row_to_sheets_fmt(row):
    return {
        "SourceID":   _v(row, "display_id"),
        "SourceName": _v(row, "source_name"),
        "SourceType": _v(row, "source_type"),
        "Notes":      _v(row, "notes"),
    }


def _next_source_id():
    """Scan existing display_ids and return the next S-prefixed ID."""
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT display_id FROM sources "
                    "WHERE display_id ~ '^S[0-9]+$' "
                    "ORDER BY length(display_id) DESC, display_id DESC LIMIT 1"
                )
                row = cur.fetchone()
    finally:
        conn.close()
    if row:
        sid   = row["display_id"]
        width = len(sid) - 1
        return f"S{int(sid[1:]) + 1:0{width}d}"
    return "S000001"


def list_sources():
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM sources ORDER BY display_id")
                rows = cur.fetchall()
    finally:
        conn.close()
    return [_row_to_sheets_fmt(r) for r in rows]


def add_source(name, source_type, notes):
    sid = _next_source_id()
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO sources (display_id, source_name, source_type, notes) "
                    "VALUES (%s, %s, %s, %s)",
                    (sid, name, source_type or None, notes or None)
                )
    finally:
        conn.close()
    return sid
