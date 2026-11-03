"""Editable AI prompt texts with version history (Stage H1, table prompt_versions).

Versions are never edited: saving inserts a new version and makes it active;
restoring an older version makes that one active again.
"""
import time

from db import supabase

_CACHE_TTL_S = 60
_cache = {}   # prompt_key -> (fetched_at, row or None)

_COLUMNS = "prompt_key,version,content,note,created_by,created_at,is_active"


def _clear(prompt_key):
    _cache.pop(prompt_key, None)


def get_active(prompt_key):
    """The active row {"version", "content", ...} or None. Cached for 60 s.
    Raises on a database error (the caller decides the fallback)."""
    hit = _cache.get(prompt_key)
    if hit and time.time() - hit[0] < _CACHE_TTL_S:
        return hit[1]
    rows = (supabase.table("prompt_versions").select(_COLUMNS)
            .eq("prompt_key", prompt_key).eq("is_active", True).limit(1).execute().data)
    row = rows[0] if rows else None
    _cache[prompt_key] = (time.time(), row)
    return row


def list_versions(prompt_key):
    """All versions, newest first."""
    return (supabase.table("prompt_versions").select(_COLUMNS)
            .eq("prompt_key", prompt_key).order("version", desc=True).execute().data or [])


def _row(data):
    row = data[0] if isinstance(data, list) else data
    return row if row and row.get("version") is not None else None


def save_new_version(prompt_key, content, note, user):
    """Insert version max+1 as the active version; returns the new row."""
    data = supabase.rpc("save_prompt_version", {
        "p_key": prompt_key, "p_content": content, "p_note": note, "p_user": user,
    }).execute().data
    _clear(prompt_key)
    return _row(data)


def activate_version(prompt_key, version):
    """Make an existing version active; returns its row, or None if it does not exist."""
    data = supabase.rpc("activate_prompt_version", {
        "p_key": prompt_key, "p_version": int(version),
    }).execute().data
    _clear(prompt_key)
    return _row(data)
