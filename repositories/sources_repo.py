import logging

from db import supabase

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


def list_sources():
    result = supabase.table("sources").select("*").order("display_id").execute()
    return [_row_to_sheets_fmt(r) for r in result.data]


def add_source(name, source_type, notes):
    sid = supabase.rpc(
        "next_display_id",
        {"p_prefix": "S", "p_seq_name": "seq_sources_display"}
    ).execute().data
    supabase.table("sources").insert({
        "display_id":  sid,
        "source_name": name,
        "source_type": source_type or None,
        "notes":       notes       or None,
    }).execute()
    return sid
