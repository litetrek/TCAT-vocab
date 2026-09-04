import logging

from db import supabase

logger = logging.getLogger(__name__)


def _v(row, key):
    val = row.get(key)
    return val if val is not None else ""


def _to_pg(val):
    return val if val not in ("", None) else None


def _row_to_response(row):
    """row must have the embedded `terms(...)` relation from a select() with that join."""
    term = row.get("terms") or {}
    return {
        "id":                 row.get("id"),                 # internal bigint — used in /api/trans/glossary/<id>
        "display_id":         _v(row, "display_id"),          # G000001
        "book_id":            row.get("book_id"),
        "term_id":            term.get("display_id", ""),     # the TERM's display_id, e.g. T000123
        "term_chinese":       term.get("chinese", ""),
        "term_pinyin":        term.get("pinyin", ""),
        "explanation":        _v(row, "explanation"),
        "explanation_source": _v(row, "explanation_source") or "ai",
        "status":             _v(row, "status") or "draft",
        "added_by":           _v(row, "added_by"),
        "added_at":           row.get("added_at"),
        "last_modified_by":   _v(row, "last_modified_by"),
        "last_modified_at":   row.get("last_modified_at"),
    }


def list_for_book(book_id):
    """book_id is trans_books' internal bigint id. Sorted alphabetically by the term's pinyin."""
    result = (
        supabase.table("book_glossary_terms")
        .select("*, terms(display_id, chinese, pinyin, romanization_plain)")
        .eq("book_id", book_id)
        .execute()
    )
    rows = result.data or []
    rows.sort(key=lambda r: ((r.get("terms") or {}).get("romanization_plain") or ""))
    return [_row_to_response(r) for r in rows]


def add_term(book_id, term_display_id, modifier, now_str):
    """
    Add a term (by its display_id, e.g. T000123) to a book's glossary.
    Returns the new row's internal id, or None if the term doesn't exist or is
    already in this book's glossary (caller gives the friendly message either way).
    """
    term_res = (
        supabase.table("terms").select("id").eq("display_id", term_display_id).limit(1).execute()
    )
    if not term_res.data:
        return None
    term_internal_id = term_res.data[0]["id"]

    existing = (
        supabase.table("book_glossary_terms")
        .select("id")
        .eq("book_id", book_id).eq("term_id", term_internal_id)
        .limit(1).execute()
    )
    if existing.data:
        return None

    display_id = supabase.rpc(
        "next_display_id", {"p_prefix": "G", "p_seq_name": "seq_glossary_display"}
    ).execute().data

    result = supabase.table("book_glossary_terms").insert({
        "display_id": display_id,
        "book_id":    book_id,
        "term_id":    term_internal_id,
        "status":     "draft",
        "added_by":   modifier,
        "added_at":   _to_pg(now_str),
    }).execute()
    return result.data[0]["id"] if result.data else None


def remove_term(book_id, glossary_id):
    """Delete a glossary row by its internal id, scoped to book_id so one book can't remove
    another's entry by guessing an id. Returns True if a row was deleted."""
    result = (
        supabase.table("book_glossary_terms")
        .delete()
        .eq("id", glossary_id).eq("book_id", book_id)
        .execute()
    )
    return bool(result.data)


def get_one(glossary_id):
    """Return the raw row (with embedded term + book fields) for the generate/patch endpoints,
    or None if not found."""
    result = (
        supabase.table("book_glossary_terms")
        .select("*, terms(display_id, chinese, pinyin, pali, sanskrit, translation_known), trans_books(title)")
        .eq("id", glossary_id)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def get_response(glossary_id):
    """get_one() + _row_to_response() — the response-shaped row a route can jsonify directly."""
    row = get_one(glossary_id)
    return _row_to_response(row) if row else None


def update_entry(glossary_id, explanation=None, explanation_source=None, status=None,
                  modifier=None, now_str=None):
    """
    Partial update — pass only the fields being changed. Setting `explanation` without an
    explicit `explanation_source` defaults to 'manual' (human edit); the AI-generate endpoint
    passes explanation_source='ai' explicitly. Returns True if a row was updated.
    """
    updates = {"last_modified_by": modifier, "last_modified_at": _to_pg(now_str)}
    if explanation is not None:
        updates["explanation"] = explanation
        updates["explanation_source"] = explanation_source or "manual"
    if status is not None:
        updates["status"] = status
    result = supabase.table("book_glossary_terms").update(updates).eq("id", glossary_id).execute()
    return bool(result.data)
