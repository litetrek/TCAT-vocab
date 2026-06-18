import logging

from db import supabase
import sheets

logger = logging.getLogger(__name__)


def _v(row, key):
    val = row.get(key)
    return val if val is not None else ""


def _fmt_ts(val):
    if not val:
        return ""
    s = str(val).replace("T", " ")
    if "+" in s:
        s = s[:s.index("+")]
    if "." in s:
        s = s[:s.index(".")]
    return s[:16]


def _doc_to_sheets_fmt(row):
    return {
        "DocumentID":      _v(row, "document_id"),
        "Title":           _v(row, "title"),
        "SourceName":      _v(row, "source_name"),
        "ParagraphCount":  row.get("paragraph_count") or 0,
        "UploadedBy":      _v(row, "uploaded_by"),
        "UploadedAt":      _fmt_ts(_v(row, "uploaded_at")),
        "LastViewedIndex": row.get("last_viewed_index") or 0,
        "Status":          _v(row, "status"),
    }


def _next_doc_id():
    result = (
        supabase.table("extraction_documents")
        .select("document_id")
        .order("document_id", desc=True)
        .limit(1)
        .execute()
    )
    if result.data:
        did = result.data[0].get("document_id", "")
        if did.startswith("D") and did[1:].isdigit():
            return f"D{int(did[1:]) + 1:06d}"
    return "D000001"


def create_document(title, source_name, zh_paras, en_paras, uploaded_by, uploaded_at):
    """
    Insert a new document and all its paragraphs into Supabase, then mirror to Sheets.
    Returns doc_id.
    """
    doc_id = _next_doc_id()
    para_count = len(zh_paras)

    supabase.table("extraction_documents").insert({
        "document_id":       doc_id,
        "title":             title or None,
        "source_name":       source_name,
        "paragraph_count":   para_count,
        "uploaded_by":       uploaded_by or None,
        "uploaded_at":       uploaded_at or None,
        "last_viewed_index": 0,
        "status":            "active",
    }).execute()

    para_rows = [
        {
            "document_id":     doc_id,
            "paragraph_index": i,
            "chinese_text":    zh_paras[i],
            "english_text":    en_paras[i],
        }
        for i in range(para_count)
    ]
    for start in range(0, len(para_rows), 200):
        supabase.table("extraction_paragraphs").insert(para_rows[start:start + 200]).execute()

    try:
        sheets.get_extraction_documents_sheet().append_row(
            [doc_id, title, source_name, para_count, uploaded_by, uploaded_at, 0, "active"]
        )
    except Exception as exc:
        logger.warning("ExtractionDocuments Sheet mirror failed for %s: %s", doc_id, exc)

    try:
        sheets.get_extraction_paragraphs_sheet().append_rows(
            [[doc_id, i, zh_paras[i], en_paras[i]] for i in range(para_count)],
            value_input_option="RAW",
        )
    except Exception as exc:
        logger.warning("ExtractionParagraphs Sheet mirror failed for %s: %s", doc_id, exc)

    return doc_id


def list_documents():
    result = supabase.table("extraction_documents").select("*").execute()
    docs = [_doc_to_sheets_fmt(r) for r in result.data]
    docs.sort(key=lambda r: (r.get("SourceName", ""), r.get("Title", "")))
    return docs


def get_paragraphs(document_id):
    """
    Returns {"paragraphs": [...], "last_viewed_index": int}, or None if not found.
    """
    doc_result = (
        supabase.table("extraction_documents")
        .select("last_viewed_index")
        .eq("document_id", document_id)
        .execute()
    )
    if not doc_result.data:
        return None
    last_viewed_index = doc_result.data[0].get("last_viewed_index") or 0

    para_result = (
        supabase.table("extraction_paragraphs")
        .select("*")
        .eq("document_id", document_id)
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
    """Returns True if found and updated, False if not found."""
    result = (
        supabase.table("extraction_documents")
        .select("document_id")
        .eq("document_id", document_id)
        .execute()
    )
    if not result.data:
        return False

    supabase.table("extraction_documents").update(
        {"last_viewed_index": index}
    ).eq("document_id", document_id).execute()

    try:
        sheet    = sheets.get_extraction_documents_sheet()
        all_rows = sheet.get_all_values()
        header   = all_rows[0]
        lvi_col  = header.index("LastViewedIndex") + 1
        for row_num, row in enumerate(all_rows[1:], start=2):
            if row[0] == document_id:
                sheet.update_cell(row_num, lvi_col, index)
                break
    except Exception as exc:
        logger.warning("ExtractionDocuments Sheet mirror lvi update failed for %s: %s",
                       document_id, exc)

    return True
