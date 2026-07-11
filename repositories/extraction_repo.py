import logging

from db import supabase

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
        "SourceID":        _v(row, "source_id"),
        "ParagraphCount":  row.get("paragraph_count") or 0,
        "UploadedBy":      _v(row, "uploaded_by"),
        "UploadedAt":      _fmt_ts(row.get("uploaded_at")),
        "LastViewedIndex": row.get("last_viewed_index") or 0,
        "Status":          _v(row, "status"),
    }


def create_document(title, source_name, zh_paras, en_paras, uploaded_by, uploaded_at, source_id=None):
    """
    Insert a new document and all its paragraphs atomically via RPC.
    Returns the display_id (e.g. 'D000003').
    """
    para_count = len(zh_paras)
    display_id = supabase.rpc(
        "next_display_id",
        {"p_prefix": "D", "p_seq_name": "seq_ext_documents_display"}
    ).execute().data

    paragraphs = [{"zh": zh_paras[i], "en": en_paras[i]} for i in range(para_count)]

    supabase.rpc("create_document_with_paragraphs", {
        "p_display_id":  display_id,
        "p_title":       title or "",
        "p_source_name": source_name,
        "p_para_count":  para_count,
        "p_uploaded_by": uploaded_by or "",
        "p_uploaded_at": uploaded_at or "",
        "p_paragraphs":  paragraphs,
    }).execute()

    if source_id:
        supabase.table("ext_documents") \
            .update({"source_id": source_id}) \
            .eq("display_id", display_id) \
            .execute()

    return display_id


def list_documents():
    result = (
        supabase.table("ext_documents")
        .select("*")
        .order("source_name")
        .order("title")
        .execute()
    )
    return [_doc_to_sheets_fmt(r) for r in result.data]


def get_paragraphs(document_id):
    """
    document_id is a display_id (e.g. 'D000001').
    Returns {"paragraphs": [...], "last_viewed_index": int}, or None if not found.
    """
    doc_result = (
        supabase.table("ext_documents")
        .select("id,last_viewed_index")
        .eq("display_id", document_id)
        .limit(1)
        .execute()
    )
    if not doc_result.data:
        return None
    doc_row           = doc_result.data[0]
    doc_internal_id   = doc_row["id"]
    last_viewed_index = doc_row.get("last_viewed_index") or 0

    para_result = (
        supabase.table("ext_paragraphs")
        .select("paragraph_index,chinese_text,english_text")
        .eq("document_id", doc_internal_id)
        .order("paragraph_index")
        .execute()
    )
    paragraphs = [
        {
            "index":   r["paragraph_index"],
            "chinese": r.get("chinese_text") or "",
            "english": r.get("english_text") or "",
        }
        for r in para_result.data
    ]
    return {"paragraphs": paragraphs, "last_viewed_index": last_viewed_index}


def update_last_viewed_index(document_id, index):
    """document_id is a display_id. Returns True if found and updated, False if not found."""
    result = (
        supabase.table("ext_documents")
        .select("id")
        .eq("display_id", document_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        return False
    supabase.table("ext_documents") \
        .update({"last_viewed_index": index}) \
        .eq("display_id", document_id) \
        .execute()
    return True
