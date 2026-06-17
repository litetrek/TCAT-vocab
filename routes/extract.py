import re
from datetime import datetime
from flask import Blueprint, jsonify, request, session
from auth import is_logged_in
from sheets import (
    get_extraction_documents_sheet,
    get_extraction_paragraphs_sheet,
    next_doc_id,
)

extract_bp = Blueprint('extract', __name__)

MAX_FILE_SIZE = 500 * 1024  # 500 KB


def _decode(data):
    for enc in ('utf-8', 'gb18030', 'big5'):
        try:
            return data.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return None


def _split_paragraphs(text):
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    blocks = re.split(r'\n{2,}', text)
    return [b.strip() for b in blocks if b.strip()]


@extract_bp.route("/api/extract/documents", methods=["POST"])
def api_extract_documents_post():
    if not is_logged_in():
        return jsonify({"error": "Unauthorized"}), 401

    zh_file = request.files.get("chinese_file")
    en_file = request.files.get("english_file")

    if not zh_file or not en_file:
        return jsonify({"error": "Both chinese_file and english_file are required"}), 400

    for label, f in [("Chinese", zh_file), ("English", en_file)]:
        if not f.filename.lower().endswith('.txt'):
            return jsonify({"error": f"{label} file must be a .txt file"}), 400

    zh_bytes = zh_file.read()
    en_bytes = en_file.read()

    if len(zh_bytes) > MAX_FILE_SIZE:
        return jsonify({"error": "Chinese file exceeds the 500 KB limit"}), 400
    if len(en_bytes) > MAX_FILE_SIZE:
        return jsonify({"error": "English file exceeds the 500 KB limit"}), 400

    zh_text = _decode(zh_bytes)
    if zh_text is None:
        return jsonify({"error": "Chinese file could not be decoded as UTF-8, GB18030, or Big5. Please check the file encoding."}), 400

    en_text = _decode(en_bytes)
    if en_text is None:
        return jsonify({"error": "English file could not be decoded as UTF-8, GB18030, or Big5. Please check the file encoding."}), 400

    zh_paras = _split_paragraphs(zh_text)
    en_paras = _split_paragraphs(en_text)

    if len(zh_paras) != len(en_paras):
        return jsonify({
            "error": (
                f"Paragraph count mismatch: the Chinese file has {len(zh_paras)} paragraph(s) "
                f"and the English file has {len(en_paras)} paragraph(s). "
                "Please fix paragraph alignment in the source files."
            )
        }), 400

    title       = (request.form.get("title") or "").strip()
    source_name = (request.form.get("source_name") or "").strip()
    uploaded_by = session.get("user_email", "")
    uploaded_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    try:
        doc_sheet  = get_extraction_documents_sheet()
        para_sheet = get_extraction_paragraphs_sheet()
    except Exception:
        return jsonify({"error": "Extraction worksheets not found. An admin must click ⚙ Init Sheets to create them."}), 500

    try:
        doc_id = next_doc_id(doc_sheet)

        doc_sheet.append_row([
            doc_id, title, source_name, len(zh_paras),
            uploaded_by, uploaded_at, 0, "active",
        ])

        para_rows = [
            [doc_id, i, zh_paras[i], en_paras[i]]
            for i in range(len(zh_paras))
        ]
        para_sheet.append_rows(para_rows, value_input_option="RAW")
    except Exception as e:
        return jsonify({"error": f"Failed to save to Google Sheets: {e}"}), 500

    paragraphs = [
        {"index": i, "chinese": zh_paras[i], "english": en_paras[i]}
        for i in range(len(zh_paras))
    ]
    return jsonify({"document_id": doc_id, "paragraphs": paragraphs, "count": len(paragraphs)})


@extract_bp.route("/api/extract/documents", methods=["GET"])
def api_extract_documents_get():
    if not is_logged_in():
        return jsonify({"error": "Unauthorized"}), 401

    try:
        rows = get_extraction_documents_sheet().get_all_records()
        rows.sort(key=lambda r: (r.get("SourceName", ""), r.get("Title", "")))
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@extract_bp.route("/api/extract/documents/<document_id>/paragraphs", methods=["GET"])
def api_extract_paragraphs_get(document_id):
    if not is_logged_in():
        return jsonify({"error": "Unauthorized"}), 401

    try:
        doc_sheet  = get_extraction_documents_sheet()
        para_sheet = get_extraction_paragraphs_sheet()

        doc_rows = doc_sheet.get_all_records()
        doc = next((r for r in doc_rows if r.get("DocumentID") == document_id), None)
        if doc is None:
            return jsonify({"error": "Document not found"}), 404

        last_viewed_index = int(doc.get("LastViewedIndex", 0) or 0)

        all_paras = para_sheet.get_all_records()
        paras = [r for r in all_paras if r.get("DocumentID") == document_id]
        paras.sort(key=lambda r: int(r.get("ParagraphIndex", 0)))

        paragraphs = [
            {
                "index": int(p["ParagraphIndex"]),
                "chinese": p.get("ChineseText", ""),
                "english": p.get("EnglishText", ""),
            }
            for p in paras
        ]
        return jsonify({"paragraphs": paragraphs, "last_viewed_index": last_viewed_index})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@extract_bp.route("/api/extract/documents/<document_id>", methods=["PATCH"])
def api_extract_document_patch(document_id):
    if not is_logged_in():
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(silent=True)
    if not data or "last_viewed_index" not in data:
        return jsonify({"error": "last_viewed_index is required"}), 400

    try:
        sheet     = get_extraction_documents_sheet()
        all_rows  = sheet.get_all_values()
        if len(all_rows) <= 1:
            return jsonify({"error": "Document not found"}), 404

        header  = all_rows[0]
        lvi_col = header.index("LastViewedIndex") + 1  # 1-based for gspread

        for row_num, row in enumerate(all_rows[1:], start=2):
            if row[0] == document_id:
                sheet.update_cell(row_num, lvi_col, data["last_viewed_index"])
                return jsonify({"ok": True})

        return jsonify({"error": "Document not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500
