import logging

from db import get_conn, generate_display_id

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


def _doc_to_sheets_fmt(row):
    return {
        "DocumentID":      _v(row, "display_id"),
        "Title":           _v(row, "title"),
        "SourceName":      _v(row, "source_name"),
        "ParagraphCount":  row.get("paragraph_count") or 0,
        "UploadedBy":      _v(row, "uploaded_by"),
        "UploadedAt":      _fmt_ts(row.get("uploaded_at")),
        "LastViewedIndex": row.get("last_viewed_index") or 0,
        "Status":          _v(row, "status"),
    }


def create_document(title, source_name, zh_paras, en_paras, uploaded_by, uploaded_at):
    """
    Insert a new document and all its paragraphs in one transaction.
    Returns the display_id (e.g. 'D000001').
    """
    para_count = len(zh_paras)
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                display_id = generate_display_id(cur, 'D', 'seq_ext_documents_display')
                cur.execute(
                    """INSERT INTO ext_documents
                       (display_id, title, source_name, paragraph_count,
                        uploaded_by, uploaded_at, last_viewed_index, status)
                       VALUES (%s, %s, %s, %s, %s, %s, 0, 'active')
                       RETURNING id""",
                    (display_id, title or None, source_name,
                     para_count, uploaded_by or None, uploaded_at or None)
                )
                doc_internal_id = cur.fetchone()["id"]

                if para_count:
                    para_rows = [
                        (doc_internal_id, i, zh_paras[i], en_paras[i])
                        for i in range(para_count)
                    ]
                    # psycopg2.extras.execute_values would be faster but executemany is clear
                    cur.executemany(
                        """INSERT INTO ext_paragraphs
                           (document_id, paragraph_index, chinese_text, english_text)
                           VALUES (%s, %s, %s, %s)""",
                        para_rows
                    )
    finally:
        conn.close()
    return display_id


def list_documents():
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM ext_documents ORDER BY source_name, title")
                rows = cur.fetchall()
    finally:
        conn.close()
    return [_doc_to_sheets_fmt(r) for r in rows]


def get_paragraphs(document_id):
    """
    document_id is a display_id (e.g. 'D000001').
    Returns {"paragraphs": [...], "last_viewed_index": int}, or None if not found.
    """
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, last_viewed_index FROM ext_documents WHERE display_id = %s",
                    (document_id,)
                )
                doc_row = cur.fetchone()
                if not doc_row:
                    return None
                doc_internal_id   = doc_row["id"]
                last_viewed_index = doc_row["last_viewed_index"] or 0

                cur.execute(
                    """SELECT paragraph_index, chinese_text, english_text
                       FROM ext_paragraphs
                       WHERE document_id = %s
                       ORDER BY paragraph_index""",
                    (doc_internal_id,)
                )
                para_rows = cur.fetchall()
    finally:
        conn.close()

    paragraphs = [
        {
            "index":   r["paragraph_index"],
            "chinese": r.get("chinese_text") or "",
            "english": r.get("english_text") or "",
        }
        for r in para_rows
    ]
    return {"paragraphs": paragraphs, "last_viewed_index": last_viewed_index}


def update_last_viewed_index(document_id, index):
    """document_id is a display_id. Returns True if found and updated, False if not found."""
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM ext_documents WHERE display_id = %s",
                    (document_id,)
                )
                if not cur.fetchone():
                    return False
                cur.execute(
                    "UPDATE ext_documents SET last_viewed_index = %s WHERE display_id = %s",
                    (index, document_id)
                )
    finally:
        conn.close()
    return True
