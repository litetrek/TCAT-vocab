import logging

from config import strip_tone_marks
from db import get_conn, generate_display_id

logger = logging.getLogger(__name__)

# Frontend field key → Postgres column name (new schema)
_FIELD_TO_DB = {
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
}

# Vote key → Postgres column name (new schema)
_VOTE_TO_DB = {
    "Translation1":      "translation1",
    "Translation2":      "translation2",
    "Translation3":      "translation3",
    "TranslationKnown":  "translation_known",
    "TranslationOther1": "translation_other1",
    "TranslationOther2": "translation_other2",
}

# Legacy key names sent by routes layer → current Postgres column names
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
}


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
    """Translate a DB row to the frontend API response shape (lowercase keys)."""
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
        "status":             _v(row, "status") or "pending",
        "added_by":           _v(row, "added_by"),
        "last_modified_by":   _v(row, "last_modified_by"),
        "last_modified_time": _fmt_ts(_v(row, "last_modified_at")),
        "romanization_plain": _v(row, "romanization_plain"),
        "source_content_chinese": _v(row, "source_content_chinese"),
        "source_content_english": _v(row, "source_content_english"),
    }


def _row_to_sheets_fmt(row):
    """CamelCase dict consumed by routes/terms.py api_translate_term and find_by_chinese."""
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
    """Return term in CamelCase format matching the Chinese text, or None."""
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM terms WHERE chinese = %s LIMIT 1", (chinese_text,))
                row = cur.fetchone()
    finally:
        conn.close()
    return _row_to_sheets_fmt(row) if row else None


def list_terms():
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM terms ORDER BY display_id")
                rows = cur.fetchall()
    finally:
        conn.close()
    return [_row_to_response(r) for r in rows]


def get_term_record(term_id):
    """Return the term in CamelCase format, or None if not found."""
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM terms WHERE display_id = %s", (term_id,))
                row = cur.fetchone()
    finally:
        conn.close()
    return _row_to_sheets_fmt(row) if row else None


def create_term(data):
    """
    Insert a new term. data uses legacy key names as sent by routes layer.
    Returns the generated display_id (e.g. 'T000001').
    """
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                display_id = generate_display_id(cur, 'T', 'seq_terms_display')
                mapped = {"display_id": display_id}
                for k, v in data.items():
                    col = _CREATE_KEY_MAP.get(k, k)
                    if col in _ALLOWED_INSERT_COLS:
                        mapped[col] = _to_pg(v)
                if not mapped.get("status"):
                    mapped["status"] = "pending"
                cols = list(mapped.keys())
                sql = (
                    f"INSERT INTO terms ({', '.join(cols)}) "
                    f"VALUES ({', '.join(['%s'] * len(cols))})"
                )
                cur.execute(sql, [mapped[c] for c in cols])
    finally:
        conn.close()
    return display_id


def update_term_field(term_id, field, value, modifier, now_str):
    """
    Update one editable field.
    Returns (chinese, old_value), or (None, None) if the term does not exist.
    """
    db_col = _FIELD_TO_DB.get(field)
    if not db_col:
        raise ValueError(f"Unknown field: {field!r}")

    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT chinese, {db_col} FROM terms WHERE display_id = %s",
                    (term_id,)
                )
                row = cur.fetchone()
                if not row:
                    return None, None
                old_value = row[db_col] or ""
                chinese   = row["chinese"] or ""

                updates = {
                    db_col: _to_pg(value),
                    "last_modified_by": modifier,
                    "last_modified_at": _to_pg(now_str),
                }
                if field == "pinyin":
                    updates["romanization_plain"] = strip_tone_marks(value)

                set_clauses = [f"{c} = %s" for c in updates]
                sql = f"UPDATE terms SET {', '.join(set_clauses)} WHERE display_id = %s"
                cur.execute(sql, list(updates.values()) + [term_id])
    finally:
        conn.close()
    return chinese, old_value


def set_final(term_id, vote_key, which, modifier, now_str):
    """
    Record first or second final translation choice.
    Returns (text, chinese), or (None, None) if the term does not exist.
    """
    db_col = _VOTE_TO_DB.get(vote_key)
    if not db_col:
        raise ValueError(f"Unknown vote key: {vote_key!r}")

    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT chinese, {db_col} FROM terms WHERE display_id = %s",
                    (term_id,)
                )
                row = cur.fetchone()
                if not row:
                    return None, None
                text    = row[db_col] or ""
                chinese = row["chinese"] or ""

                updates = {
                    "last_modified_by": modifier,
                    "last_modified_at": _to_pg(now_str),
                }
                if which == "first":
                    updates["translation_first"] = text
                    updates["final"]             = vote_key
                    updates["status"]            = "finalized"
                else:
                    updates["translation_second"] = text

                set_clauses = [f"{c} = %s" for c in updates]
                sql = f"UPDATE terms SET {', '.join(set_clauses)} WHERE display_id = %s"
                cur.execute(sql, list(updates.values()) + [term_id])
    finally:
        conn.close()
    return text, chinese


def reset_final(term_id, modifier, now_str):
    """
    Clear final/translation_first/translation_second and reset status to 'pending'.
    Returns (old_first, old_second, chinese), or (None, None, None) if not found.
    """
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT chinese, translation_first, translation_second "
                    "FROM terms WHERE display_id = %s",
                    (term_id,)
                )
                row = cur.fetchone()
                if not row:
                    return None, None, None
                old_first  = row["translation_first"]  or ""
                old_second = row["translation_second"] or ""
                chinese    = row["chinese"]            or ""

                cur.execute(
                    """UPDATE terms SET
                        translation_first  = NULL,
                        translation_second = NULL,
                        final              = NULL,
                        status             = 'pending',
                        last_modified_by   = %s,
                        last_modified_at   = %s
                    WHERE display_id = %s""",
                    (modifier, _to_pg(now_str), term_id)
                )
    finally:
        conn.close()
    return old_first, old_second, chinese


def update_translations(term_id, translation_updates, modifier, now_str):
    """
    Save AI-generated translations.
    translation_updates: dict like {"Translation1": "text", "Translation3": "text"}
    """
    _vk_to_db = {
        "Translation1": "translation1",
        "Translation2": "translation2",
        "Translation3": "translation3",
    }
    updates = {_vk_to_db[k]: v for k, v in translation_updates.items() if k in _vk_to_db}
    updates["last_modified_by"] = modifier
    updates["last_modified_at"] = _to_pg(now_str)

    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                set_clauses = [f"{c} = %s" for c in updates]
                sql = f"UPDATE terms SET {', '.join(set_clauses)} WHERE display_id = %s"
                cur.execute(sql, list(updates.values()) + [term_id])
    finally:
        conn.close()
