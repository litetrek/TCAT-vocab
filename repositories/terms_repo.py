import logging

from config import strip_tone_marks
from db import supabase

logger = logging.getLogger(__name__)

# Frontend field key → Postgres column name
_FIELD_TO_DB = {
    "chinese":      "chinese",
    "pinyin":       "pinyin",
    "trans1":       "translation1",
    "trans2":       "translation2",
    "trans3":       "translation3",
    "trans_known":  "translation_known",
    "trans_other1": "translation_other1",
    "trans_other2": "translation_other2",
    "source":       "source",
    "context":      "context",
    "category":     "category",
    "notes":        "notes",
    "source_content_chinese": "source_content_chinese",
    "source_content_english": "source_content_english",
    "entity_type":   "entity_type",
    "subject_field": "subject_field",
}

# Fields allowed when merging two terms (response keys → DB columns)
_MERGE_FIELD_TO_DB = {
    "chinese":                "chinese",
    "pinyin":                 "pinyin",
    "pali":                   "pali",
    "sanskrit":               "sanskrit",
    "trans1":                 "translation1",
    "trans2":                 "translation2",
    "trans3":                 "translation3",
    "trans_known":            "translation_known",
    "trans_other1":           "translation_other1",
    "trans_other2":           "translation_other2",
    "trans_first":            "translation_first",
    "trans_second":           "translation_second",
    "final":                  "final",
    "status":                 "status",
    "source":                 "source",
    "context":                "context",
    "notes":                  "notes",
    "category":               "category",
    "entity_type":            "entity_type",
    "subject_field":          "subject_field",
    "source_content_chinese": "source_content_chinese",
    "source_content_english": "source_content_english",
}

# Vote key → Postgres column name
_VOTE_TO_DB = {
    "Translation1":      "translation1",
    "Translation2":      "translation2",
    "Translation3":      "translation3",
    "TranslationKnown":  "translation_known",
    "TranslationOther1": "translation_other1",
    "TranslationOther2": "translation_other2",
}

# Legacy key names from routes → Postgres column names
_CREATE_KEY_MAP = {
    "translation_1":       "translation1",
    "translation_2":       "translation2",
    "translation_3":       "translation3",
    "translation_other_1": "translation_other1",
    "translation_other_2": "translation_other2",
    "created_at":          "added_at",
}

_ALLOWED_INSERT_COLS = {
    "display_id", "chinese", "pinyin", "pali", "sanskrit", "context", "category", "notes",
    "translation1", "translation2", "translation3", "translation_first", "translation_second",
    "translation_other1", "translation_other2", "translation_known", "final", "status",
    "source", "romanization_plain", "source_content_chinese", "source_content_english",
    "added_by", "added_at", "last_modified_by", "last_modified_at",
    "entity_type", "subject_field", "classification_source", "classified_by", "classified_at",
}

_PAGE = 1000  # PostgREST default max rows per request


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


def _to_pg(val):
    return val if val != "" else None


def _row_to_response(row):
    return {
        "id":       _v(row, "display_id"),
        "chinese":  _v(row, "chinese"),
        "pinyin":   _v(row, "pinyin"),
        "pali":     _v(row, "pali"),
        "sanskrit": _v(row, "sanskrit"),
        "context":  _v(row, "context"),
        "category": _v(row, "category"),
        "notes":    _v(row, "notes"),
        "trans1":        _v(row, "translation1"),
        "trans2":        _v(row, "translation2"),
        "trans3":        _v(row, "translation3"),
        "trans_known":   _v(row, "translation_known"),
        "source":        _v(row, "source"),
        "trans_first":   _v(row, "translation_first"),
        "trans_second":  _v(row, "translation_second"),
        "trans_other1":  _v(row, "translation_other1"),
        "trans_other2":  _v(row, "translation_other2"),
        "timestamp":          _fmt_ts(_v(row, "added_at")),
        "final":              _v(row, "final"),
        "status":             _v(row, "status") or "new",
        "added_by":           _v(row, "added_by"),
        "last_modified_by":   _v(row, "last_modified_by"),
        "last_modified_time": _fmt_ts(_v(row, "last_modified_at")),
        "romanization_plain": _v(row, "romanization_plain"),
        "source_content_chinese": _v(row, "source_content_chinese"),
        "source_content_english": _v(row, "source_content_english"),
        "entity_type":           _v(row, "entity_type"),
        "subject_field":         _v(row, "subject_field"),
        "classification_source": _v(row, "classification_source"),
        "classified_by":         _v(row, "classified_by"),
        "classified_at":         _fmt_ts(_v(row, "classified_at")),
    }


def _row_to_sheets_fmt(row):
    return {
        "ID":       _v(row, "display_id"),
        "Chinese":  _v(row, "chinese"),
        "Pinyin":   _v(row, "pinyin"),
        "Pali":     _v(row, "pali"),
        "Sanskrit": _v(row, "sanskrit"),
        "Context":  _v(row, "context"),
        "Category": _v(row, "category"),
        "Notes":    _v(row, "notes"),
        "Translation1":      _v(row, "translation1"),
        "Translation2":      _v(row, "translation2"),
        "Translation3":      _v(row, "translation3"),
        "TranslationKnown":  _v(row, "translation_known"),
        "Source":            _v(row, "source"),
        "TranslationFirst":  _v(row, "translation_first"),
        "TranslationSecond": _v(row, "translation_second"),
        "TranslationOther1": _v(row, "translation_other1"),
        "TranslationOther2": _v(row, "translation_other2"),
        "Timestamp":         _fmt_ts(_v(row, "added_at")),
        "Final":             _v(row, "final"),
        "Status":            _v(row, "status") or "pending",
        "AddedBy":           _v(row, "added_by"),
        "LastModifiedBy":    _v(row, "last_modified_by"),
        "LastModifiedTime":  _fmt_ts(_v(row, "last_modified_at")),
        "RomanizationPlain": _v(row, "romanization_plain"),
        "SourceContentChinese": _v(row, "source_content_chinese"),
        "SourceContentEnglish": _v(row, "source_content_english"),
    }


# ── Public API ────────────────────────────────────────────────────────────────

def find_by_chinese(chinese_text):
    """Prefer an active (non-inactive) row so merged duplicates do not win lookups."""
    result = (
        supabase.table("terms")
        .select("*")
        .eq("chinese", chinese_text)
        .neq("status", "inactive")
        .limit(1)
        .execute()
    )
    if not result.data:
        return None
    return _row_to_sheets_fmt(result.data[0])


def list_terms():
    """Fetch all terms using paginated requests to bypass PostgREST's 1000-row limit."""
    rows = []
    offset = 0
    while True:
        chunk = (
            supabase.table("terms")
            .select("*")
            .order("display_id")
            .range(offset, offset + _PAGE - 1)
            .execute()
            .data
        )
        rows.extend(chunk)
        if len(chunk) < _PAGE:
            break
        offset += _PAGE
    logger.info("list_terms: fetched %d rows total", len(rows))
    return [_row_to_response(r) for r in rows]


def get_term_record(term_id):
    result = supabase.table("terms").select("*").eq("display_id", term_id).limit(1).execute()
    if not result.data:
        return None
    return _row_to_sheets_fmt(result.data[0])


def create_term(data):
    """
    Insert a new term. data uses legacy key names as sent by routes layer.
    Returns the generated display_id (e.g. 'T002845').
    """
    display_id = supabase.rpc(
        "next_display_id",
        {"p_prefix": "T", "p_seq_name": "seq_terms_display"}
    ).execute().data

    mapped = {"display_id": display_id}
    for k, v in data.items():
        col = _CREATE_KEY_MAP.get(k, k)
        if col in _ALLOWED_INSERT_COLS:
            mapped[col] = _to_pg(v)
    if not mapped.get("status"):
        mapped["status"] = "new"

    supabase.table("terms").insert(mapped).execute()
    return display_id


def update_term_field(term_id, field, value, modifier, now_str, extra_updates=None):
    """
    Update one editable field.
    Returns (chinese, old_value), or (None, None) if the term does not exist.
    extra_updates: optional dict of additional columns to set in the same UPDATE.
    """
    db_col = _FIELD_TO_DB.get(field)
    if not db_col:
        raise ValueError(f"Unknown field: {field!r}")

    result = supabase.table("terms").select(f"chinese,{db_col}").eq("display_id", term_id).execute()
    if not result.data:
        return None, None
    row       = result.data[0]
    old_value = row.get(db_col) or ""
    chinese   = row.get("chinese") or ""

    updates = {
        db_col: _to_pg(value),
        "last_modified_by": modifier,
        "last_modified_at": _to_pg(now_str),
    }
    if field == "pinyin":
        updates["romanization_plain"] = strip_tone_marks(value)

    if extra_updates:
        updates.update(extra_updates)

    supabase.table("terms").update(updates).eq("display_id", term_id).execute()
    return chinese, old_value


def set_final(term_id, vote_key, which, modifier, now_str):
    """
    Record first or second final translation choice.
    Returns (text, chinese), or (None, None) if the term does not exist.
    """
    db_col = _VOTE_TO_DB.get(vote_key)
    if not db_col:
        raise ValueError(f"Unknown vote key: {vote_key!r}")

    result = supabase.table("terms").select(f"chinese,{db_col}").eq("display_id", term_id).execute()
    if not result.data:
        return None, None
    row     = result.data[0]
    text    = row.get(db_col) or ""
    chinese = row.get("chinese") or ""

    updates = {
        "last_modified_by": modifier,
        "last_modified_at": _to_pg(now_str),
    }
    if which == "first":
        updates["translation_first"] = text
        updates["final"]             = vote_key
        updates["status"]            = "reviewed"
    else:
        updates["translation_second"] = text

    supabase.table("terms").update(updates).eq("display_id", term_id).execute()
    return text, chinese


def reset_final(term_id, modifier, now_str):
    """
    Clear final/translation_first/translation_second and reset status to 'pending'.
    Returns (old_first, old_second, chinese), or (None, None, None) if not found.
    """
    result = supabase.table("terms") \
        .select("chinese,translation_first,translation_second") \
        .eq("display_id", term_id) \
        .execute()
    if not result.data:
        return None, None, None
    row        = result.data[0]
    old_first  = row.get("translation_first")  or ""
    old_second = row.get("translation_second") or ""
    chinese    = row.get("chinese")            or ""

    supabase.table("terms").update({
        "translation_first":  None,
        "translation_second": None,
        "final":              None,
        "status":             "new",
        "last_modified_by":   modifier,
        "last_modified_at":   _to_pg(now_str),
    }).eq("display_id", term_id).execute()
    return old_first, old_second, chinese


def mark_pending(term_id, modifier, now_str):
    result = supabase.table("terms").select("chinese").eq("display_id", term_id).execute()
    if not result.data:
        return None
    chinese = result.data[0].get("chinese") or ""
    supabase.table("terms").update({
        "status":           "pending",
        "last_modified_by": modifier,
        "last_modified_at": _to_pg(now_str),
    }).eq("display_id", term_id).execute()
    return chinese


def mark_reviewed(term_id, modifier, now_str):
    result = supabase.table("terms").select("chinese").eq("display_id", term_id).execute()
    if not result.data:
        return None
    chinese = result.data[0].get("chinese") or ""
    supabase.table("terms").update({
        "status":           "reviewed",
        "last_modified_by": modifier,
        "last_modified_at": _to_pg(now_str),
    }).eq("display_id", term_id).execute()
    return chinese


def update_classification(term_id, entity_type, subject_field, source, classified_by, now_ts):
    """Write entity_type / subject_field and classification metadata.
    Skips terms where classification_source is already 'manual', unless called explicitly.
    """
    supabase.table("terms").update({
        "entity_type":           _to_pg(entity_type),
        "subject_field":         _to_pg(subject_field),
        "classification_source": source,
        "classified_by":         classified_by,
        "classified_at":         now_ts,
    }).eq("display_id", term_id).execute()


def get_classification_source(term_id):
    """Return classification_source for a single term, or None if term not found."""
    result = (
        supabase.table("terms")
        .select("classification_source")
        .eq("display_id", term_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        return None
    return result.data[0].get("classification_source")


def get_translation_constraint_terms():
    """Return terms usable as AI translation constraints (T3): those with a
    non-empty Final selection or a TranslationKnown value.

    Each item: {"chinese": str, "english": str}. Filtered client-side (rather
    than a PostgREST .or_() filter) to keep the query shape identical to the
    rest of this module's paginated fetches.
    """
    rows = []
    offset = 0
    while True:
        chunk = (
            supabase.table("terms")
            .select("chinese,translation_known,translation_first,final")
            .range(offset, offset + _PAGE - 1)
            .execute()
            .data
        )
        rows.extend(chunk)
        if len(chunk) < _PAGE:
            break
        offset += _PAGE

    out = []
    for r in rows:
        chinese = (r.get("chinese") or "").strip()
        if not chinese:
            continue
        english = (r.get("translation_known") or "").strip()
        if not english and r.get("final"):
            english = (r.get("translation_first") or "").strip()
        if english:
            out.append({"chinese": chinese, "english": english})
    return out


def merge_terms(keep_id, drop_id, field_values, modifier, now_str):
    """
    Apply chosen field values onto keep_id, then mark drop_id inactive.
    field_values uses frontend response keys (see _MERGE_FIELD_TO_DB).
    Returns dict with keep response row + chinese strings, or None if either term missing.
    Raises ValueError for unknown field keys.
    """
    if keep_id == drop_id:
        raise ValueError("keep_id and drop_id must differ")

    keep_res = supabase.table("terms").select("*").eq("display_id", keep_id).limit(1).execute()
    drop_res = supabase.table("terms").select("*").eq("display_id", drop_id).limit(1).execute()
    if not keep_res.data or not drop_res.data:
        return None

    keep_row = keep_res.data[0]
    drop_row = drop_res.data[0]
    updates = {}
    for key, val in (field_values or {}).items():
        col = _MERGE_FIELD_TO_DB.get(key)
        if not col:
            raise ValueError(f"Unknown merge field: {key!r}")
        updates[col] = _to_pg(val if val is not None else "")

    if "pinyin" in (field_values or {}):
        updates["romanization_plain"] = strip_tone_marks(field_values.get("pinyin") or "") or None

    if "entity_type" in (field_values or {}) or "subject_field" in (field_values or {}):
        updates["classification_source"] = "manual"
        updates["classified_by"] = modifier
        updates["classified_at"] = _to_pg(now_str)

    updates["last_modified_by"] = modifier
    updates["last_modified_at"] = _to_pg(now_str)

    supabase.table("terms").update(updates).eq("display_id", keep_id).execute()
    supabase.table("terms").update({
        "status":           "inactive",
        "last_modified_by": modifier,
        "last_modified_at": _to_pg(now_str),
    }).eq("display_id", drop_id).execute()

    refreshed = supabase.table("terms").select("*").eq("display_id", keep_id).limit(1).execute()
    keep_out = _row_to_response(refreshed.data[0] if refreshed.data else {**keep_row, **updates, "display_id": keep_id})
    return {
        "keep":         keep_out,
        "keep_id":      keep_id,
        "drop_id":      drop_id,
        "keep_chinese": keep_out.get("chinese") or _v(keep_row, "chinese"),
        "drop_chinese": _v(drop_row, "chinese"),
    }


def deactivate_term(term_id, modifier, now_str):
    result = supabase.table("terms").select("chinese").eq("display_id", term_id).execute()
    if not result.data:
        return None
    chinese = result.data[0].get("chinese") or ""
    supabase.table("terms").update({
        "status":           "inactive",
        "last_modified_by": modifier,
        "last_modified_at": _to_pg(now_str),
    }).eq("display_id", term_id).execute()
    return chinese


def reactivate_term(term_id, modifier, now_str):
    result = supabase.table("terms").select("chinese").eq("display_id", term_id).execute()
    if not result.data:
        return None
    chinese = result.data[0].get("chinese") or ""
    supabase.table("terms").update({
        "status":           "new",
        "last_modified_by": modifier,
        "last_modified_at": _to_pg(now_str),
    }).eq("display_id", term_id).execute()
    return chinese


def delete_term(term_id):
    """Hard delete a term. Returns (chinese, blocked) where blocked=True if term has finalized translations."""
    result = supabase.table("terms").select("chinese,translation_first").eq("display_id", term_id).execute()
    if not result.data:
        return None, False
    row = result.data[0]
    chinese = row.get("chinese") or ""
    if row.get("translation_first"):
        return chinese, True
    supabase.table("terms").delete().eq("display_id", term_id).execute()
    return chinese, False


def update_translations(term_id, translation_updates, modifier, now_str):
    """Save AI-generated translations. translation_updates: {vote_key: text, ...}"""
    _vk_to_db = {
        "Translation1": "translation1",
        "Translation2": "translation2",
        "Translation3": "translation3",
    }
    updates = {_vk_to_db[k]: v for k, v in translation_updates.items() if k in _vk_to_db}
    updates["last_modified_by"] = modifier
    updates["last_modified_at"] = _to_pg(now_str)
    supabase.table("terms").update(updates).eq("display_id", term_id).execute()
