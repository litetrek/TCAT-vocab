import logging

from db import supabase
import sheets

logger = logging.getLogger(__name__)


def _v(row, key):
    val = row.get(key)
    return val if val is not None else ""


def _row_to_sheets_fmt(row):
    return {
        "SourceID":   _v(row, "source_id"),
        "SourceName": _v(row, "source_name"),
        "SourceType": _v(row, "source_type"),
        "Notes":      _v(row, "notes"),
    }


def _next_source_id():
    result = (
        supabase.table("sources")
        .select("source_id")
        .order("source_id", desc=True)
        .limit(1)
        .execute()
    )
    if result.data:
        sid = result.data[0].get("source_id", "")
        if sid.startswith("S") and sid[1:].isdigit():
            width = len(sid) - 1          # preserve existing zero-padding width
            return f"S{int(sid[1:]) + 1:0{width}d}"
    return "S001"


def list_sources():
    result = supabase.table("sources").select("*").execute()
    return [_row_to_sheets_fmt(r) for r in result.data]


def add_source(name, source_type, notes):
    sid = _next_source_id()
    sb_row = {
        "source_id":   sid,
        "source_name": name,
        "source_type": source_type or None,
        "notes":       notes or None,
    }
    supabase.table("sources").insert(sb_row).execute()

    try:
        sheets.get_source_sheet().append_row([sid, name, source_type, notes])
    except Exception as exc:
        logger.warning("Sources Sheet mirror append failed for %s: %s", sid, exc)

    return sid
