import logging

from config import COL, strip_tone_marks
from db import supabase
import sheets

logger = logging.getLogger(__name__)

# Frontend field key → Supabase column name
_FIELD_TO_DB = {
    "pinyin":       "pinyin",
    "trans1":       "translation_1",
    "trans2":       "translation_2",
    "trans3":       "translation_3",
    "trans_known":  "translation_known",
    "trans_other1": "translation_other_1",
    "trans_other2": "translation_other_2",
    "source":       "source",
    "context":      "context",
    "category":     "category",
    "notes":        "notes",
    "source_content_chinese": "source_content_chinese",
    "source_content_english": "source_content_english",
}

# Vote key → Supabase column
_VOTE_TO_DB = {
    "Translation1":      "translation_1",
    "Translation2":      "translation_2",
    "Translation3":      "translation_3",
    "TranslationKnown":  "translation_known",
    "TranslationOther1": "translation_other_1",
    "TranslationOther2": "translation_other_2",
}


def _v(row, key):
    val = row.get(key)
    return val if val is not None else ""


def _fmt_ts(val):
    """Normalise a Supabase TIMESTAMPTZ string to 'YYYY-MM-DD HH:MM' for display."""
    if not val:
        return ""
    s = str(val).replace("T", " ")
    if "+" in s:
        s = s[:s.index("+")]
    if "." in s:
        s = s[:s.index(".")]
    return s[:16]


def _row_to_response(row):
    """Translate a Supabase terms row to the current frontend API response shape."""
    return {
        "id":       _v(row, "term_id"),
        "chinese":  _v(row, "chinese"),
        "pinyin":   _v(row, "pinyin"),
        "pali":     _v(row, "pali"),
        "sanskrit": _v(row, "sanskrit"),
        "context":  _v(row, "context"),
        "category": _v(row, "category"),
        "notes":    _v(row, "notes"),
        "trans1":        _v(row, "translation_1"),
        "trans2":        _v(row, "translation_2"),
        "trans3":        _v(row, "translation_3"),
        "trans_known":   _v(row, "translation_known"),
        "source":        _v(row, "source"),
        "trans_first":   _v(row, "translation_first"),
        "trans_second":  _v(row, "translation_second"),
        "trans_other1":  _v(row, "translation_other_1"),
        "trans_other2":  _v(row, "translation_other_2"),
        "timestamp":          _fmt_ts(_v(row, "created_at")),
        "final":              _v(row, "final"),
        "status":             _v(row, "status") or "pending",
        "added_by":           _v(row, "added_by"),
        "last_modified_by":   _v(row, "last_modified_by"),
        "last_modified_time": _fmt_ts(_v(row, "last_modified_at")),
        "romanization_plain": _v(row, "romanization_plain"),
        "source_content_chinese": _v(row, "source_content_chinese"),
        "source_content_english": _v(row, "source_content_english"),
    }


def _row_to_sheets_fmt(row):
    """Translate a Supabase row to Sheets CamelCase dict (for internal route logic)."""
    return {
        "ID":       _v(row, "term_id"),
        "Chinese":  _v(row, "chinese"),
        "Pinyin":   _v(row, "pinyin"),
        "Pali":     _v(row, "pali"),
        "Sanskrit": _v(row, "sanskrit"),
        "Context":  _v(row, "context"),
        "Category": _v(row, "category"),
        "Notes":    _v(row, "notes"),
        "Translation1":      _v(row, "translation_1"),
        "Translation2":      _v(row, "translation_2"),
        "Translation3":      _v(row, "translation_3"),
        "TranslationKnown":  _v(row, "translation_known"),
        "Source":            _v(row, "source"),
        "TranslationFirst":  _v(row, "translation_first"),
        "TranslationSecond": _v(row, "translation_second"),
        "TranslationOther1": _v(row, "translation_other_1"),
        "TranslationOther2": _v(row, "translation_other_2"),
        "Timestamp":         _fmt_ts(_v(row, "created_at")),
        "Final":             _v(row, "final"),
        "Status":            _v(row, "status") or "pending",
        "AddedBy":           _v(row, "added_by"),
        "LastModifiedBy":    _v(row, "last_modified_by"),
        "LastModifiedTime":  _fmt_ts(_v(row, "last_modified_at")),
        "RomanizationPlain": _v(row, "romanization_plain"),
        "SourceContentChinese": _v(row, "source_content_chinese"),
        "SourceContentEnglish": _v(row, "source_content_english"),
    }


def _to_sb(val):
    """Convert empty string to None for Supabase."""
    return val if val != "" else None


def _sb_to_sheets_row(sb):
    """Build the positional list matching TERMS_HEADER order for a Sheets append."""
    def v(k): return sb.get(k) or ""
    return [
        v("term_id"), v("chinese"), v("pinyin"), v("pali"), v("sanskrit"),
        v("context"), v("category"), v("notes"),
        v("translation_1"), v("translation_2"), v("translation_3"),
        v("final"), v("status"), v("added_by"), v("created_at"),
        v("translation_known"), v("source"),
        v("translation_first"), v("translation_second"),
        v("translation_other_1"), v("translation_other_2"),
        v("last_modified_by"), v("last_modified_at"),
        v("romanization_plain"), v("source_content_chinese"), v("source_content_english"),
    ]


def _next_id():
    """Generate next term ID using max existing ID in Supabase terms table."""
    # Use order + limit instead of fetching all rows.
    result = supabase.table("terms").select("term_id").order("term_id", desc=True).limit(1).execute()
    if result.data:
        tid = result.data[0].get("term_id", "")
        if tid.startswith("T") and tid[1:].isdigit():
            return f"T{int(tid[1:]) + 1:06d}"
    return "T000001"


# ── Public API ────────────────────────────────────────────────────────────────

def list_terms():
    # Supabase paginates at 1000 rows by default; fetch all pages.
    all_rows = []
    page_size = 1000
    offset = 0
    while True:
        result = supabase.table("terms").select("*").range(offset, offset + page_size - 1).execute()
        all_rows.extend(result.data)
        if len(result.data) < page_size:
            break
        offset += page_size
    return [_row_to_response(r) for r in all_rows]


def get_term_record(term_id):
    """Return the term in Sheets CamelCase format, or None if not found."""
    result = supabase.table("terms").select("*").eq("term_id", term_id).execute()
    if not result.data:
        return None
    return _row_to_sheets_fmt(result.data[0])


def create_term(data):
    """
    Insert a new term. data uses Supabase snake_case column names (no term_id).
    Returns the generated term_id.
    """
    term_id = _next_id()
    sb_row = {"term_id": term_id}
    for k, v in data.items():
        sb_row[k] = _to_sb(v)
    if not sb_row.get("status"):
        sb_row["status"] = "pending"

    supabase.table("terms").insert(sb_row).execute()

    try:
        sheets.get_terms_sheet().append_row(_sb_to_sheets_row(sb_row))
    except Exception as exc:
        logger.warning("Terms Sheet mirror append failed for %s: %s", term_id, exc)

    return term_id


def update_term_field(term_id, field, value, modifier, now_str):
    """
    Update one editable field in Supabase, then mirror to Sheets.
    Returns (chinese, old_value) so the caller can write the audit entry.
    Returns (None, None) if the term does not exist.
    """
    db_col = _FIELD_TO_DB.get(field)
    if not db_col:
        raise ValueError(f"Unknown field: {field}")

    current = supabase.table("terms").select("*").eq("term_id", term_id).execute()
    if not current.data:
        return None, None
    row = current.data[0]
    old_value = row.get(db_col) or ""
    chinese   = row.get("chinese") or ""

    updates = {
        db_col: _to_sb(value),
        "last_modified_by": modifier,
        "last_modified_at": now_str,
    }
    if field == "pinyin":
        updates["romanization_plain"] = strip_tone_marks(value)

    supabase.table("terms").update(updates).eq("term_id", term_id).execute()

    try:
        ts = sheets.get_terms_sheet()
        all_rows = ts.get_all_values()
        for i, r in enumerate(all_rows):
            if i == 0:
                continue
            if r[0] == term_id:
                ts.update_cell(i + 1, COL[field], value)
                if field == "pinyin":
                    ts.update_cell(i + 1, COL["romanization_plain"], strip_tone_marks(value))
                ts.update_cell(i + 1, COL["last_modified_by"], modifier)
                ts.update_cell(i + 1, COL["last_modified_time"], now_str)
                break
    except Exception as exc:
        logger.warning("Terms Sheet mirror update failed for %s/%s: %s", term_id, field, exc)

    return chinese, old_value


def set_final(term_id, vote_key, which, modifier, now_str):
    """
    Record first or second final translation choice.
    Returns (text, chinese) so the caller can write the audit entry.
    Returns (None, None) if the term does not exist.
    """
    db_col = _VOTE_TO_DB.get(vote_key)
    if not db_col:
        raise ValueError(f"Unknown vote key: {vote_key}")

    current = supabase.table("terms").select("*").eq("term_id", term_id).execute()
    if not current.data:
        return None, None
    row     = current.data[0]
    text    = row.get(db_col) or ""
    chinese = row.get("chinese") or ""

    updates = {"last_modified_by": modifier, "last_modified_at": now_str}
    if which == "first":
        updates["translation_first"] = text
        updates["final"]             = vote_key
        updates["status"]            = "finalized"
    else:
        updates["translation_second"] = text

    supabase.table("terms").update(updates).eq("term_id", term_id).execute()

    try:
        ts = sheets.get_terms_sheet()
        all_rows = ts.get_all_values()
        for i, r in enumerate(all_rows):
            if r[0] == term_id:
                if which == "first":
                    ts.update_cell(i + 1, COL["trans_first"], text)
                    ts.update_cell(i + 1, COL["final"],       vote_key)
                    ts.update_cell(i + 1, COL["status"],      "finalized")
                else:
                    ts.update_cell(i + 1, COL["trans_second"], text)
                ts.update_cell(i + 1, COL["last_modified_by"],   modifier)
                ts.update_cell(i + 1, COL["last_modified_time"], now_str)
                break
    except Exception as exc:
        logger.warning("Terms Sheet mirror set_final failed for %s: %s", term_id, exc)

    return text, chinese


def reset_final(term_id, modifier, now_str):
    """
    Clear final/translation_first/translation_second and reset status to 'pending'.
    Returns (old_first, old_second, chinese) for the audit entry.
    Returns (None, None, None) if the term does not exist.
    """
    current = supabase.table("terms").select("*").eq("term_id", term_id).execute()
    if not current.data:
        return None, None, None
    row        = current.data[0]
    old_first  = row.get("translation_first")  or ""
    old_second = row.get("translation_second") or ""
    chinese    = row.get("chinese")            or ""

    supabase.table("terms").update({
        "translation_first":  None,
        "translation_second": None,
        "final":              None,
        "status":             "pending",
        "last_modified_by":   modifier,
        "last_modified_at":   now_str,
    }).eq("term_id", term_id).execute()

    try:
        ts = sheets.get_terms_sheet()
        all_rows = ts.get_all_values()
        for i, r in enumerate(all_rows):
            if r[0] == term_id:
                ts.update_cell(i + 1, COL["trans_first"],        "")
                ts.update_cell(i + 1, COL["trans_second"],       "")
                ts.update_cell(i + 1, COL["final"],              "")
                ts.update_cell(i + 1, COL["status"],             "pending")
                ts.update_cell(i + 1, COL["last_modified_by"],   modifier)
                ts.update_cell(i + 1, COL["last_modified_time"], now_str)
                break
    except Exception as exc:
        logger.warning("Terms Sheet mirror reset_final failed for %s: %s", term_id, exc)

    return old_first, old_second, chinese


def update_translations(term_id, translation_updates, modifier, now_str):
    """
    Save AI-generated translations.
    translation_updates: dict like {"Translation1": "text", "Translation3": "text"}
    """
    _vk_to_db = {
        "Translation1": "translation_1",
        "Translation2": "translation_2",
        "Translation3": "translation_3",
    }
    updates = {_vk_to_db[k]: v for k, v in translation_updates.items() if k in _vk_to_db}
    updates["last_modified_by"] = modifier
    updates["last_modified_at"] = now_str

    supabase.table("terms").update(updates).eq("term_id", term_id).execute()

    try:
        _vk_to_col = {
            "Translation1": COL["trans1"],
            "Translation2": COL["trans2"],
            "Translation3": COL["trans3"],
        }
        ts = sheets.get_terms_sheet()
        all_rows = ts.get_all_values()
        for i, r in enumerate(all_rows):
            if i == 0:
                continue
            if r[0] == term_id:
                for vk, text in translation_updates.items():
                    if vk in _vk_to_col:
                        ts.update_cell(i + 1, _vk_to_col[vk], text)
                ts.update_cell(i + 1, COL["last_modified_by"],   modifier)
                ts.update_cell(i + 1, COL["last_modified_time"], now_str)
                break
    except Exception as exc:
        logger.warning("Terms Sheet mirror update_translations failed for %s: %s", term_id, exc)
