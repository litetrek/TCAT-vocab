import re
from datetime import datetime
from flask import Blueprint, jsonify, request, session
from auth import is_logged_in, can_create_term, can_edit_existing
from ai import find_known_translation, generate_term_data
from config import COL, FIELD_LABELS, strip_tone_marks
from sheets import (
    get_terms_sheet,
    get_extraction_documents_sheet,
    get_extraction_paragraphs_sheet,
    next_doc_id, next_term_id,
)
from repositories.audit_repo import write_audit

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


@extract_bp.route("/api/extract/known-terms", methods=["GET"])
def api_extract_known_terms():
    if not is_logged_in():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        rows = get_terms_sheet().get_all_records()
        result = []
        for r in rows:
            result.append({
                "id":          r.get("ID",               ""),
                "chinese":     r.get("Chinese",          ""),
                "pinyin":      r.get("Pinyin",           ""),
                "pali":        r.get("Pali",             ""),
                "sanskrit":    r.get("Sanskrit",         ""),
                "trans_known": r.get("TranslationKnown", ""),
                "trans1":      r.get("Translation1",     ""),
                "trans2":      r.get("Translation2",     ""),
                "trans3":      r.get("Translation3",     ""),
            })
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@extract_bp.route("/api/extract/lookup", methods=["POST"])
def api_extract_lookup():
    if not is_logged_in():
        return jsonify({"error": "Unauthorized"}), 401
    data              = request.get_json(silent=True) or {}
    chinese_term      = (data.get("chinese_term")      or "").strip()
    chinese_paragraph = (data.get("chinese_paragraph") or "").strip()
    english_paragraph = (data.get("english_paragraph") or "").strip()
    if not chinese_term or not english_paragraph:
        return jsonify({"error": "chinese_term and english_paragraph are required"}), 400
    try:
        result = find_known_translation(chinese_term, chinese_paragraph, english_paragraph)
        return jsonify({"suggested_translation": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@extract_bp.route("/api/extract/generate", methods=["POST"])
def api_extract_generate():
    if not is_logged_in():
        return jsonify({"error": "Unauthorized"}), 401
    data         = request.get_json(silent=True) or {}
    chinese_term = (data.get("chinese_term")           or "").strip()
    src_zh       = (data.get("source_content_chinese") or "").strip()
    src_en       = (data.get("source_content_english") or "").strip()
    trans_known  = (data.get("known_translation")      or "").strip()
    if not chinese_term:
        return jsonify({"error": "chinese_term is required"}), 400
    try:
        pinyin, pali, sanskrit, t1, t2, t3 = generate_term_data(
            chinese_term, "", "", src_zh, src_en, trans_known
        )
        return jsonify({"pinyin": pinyin, "pali": pali, "sanskrit": sanskrit,
                        "trans1": t1, "trans2": t2, "trans3": t3})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@extract_bp.route("/api/extract/save", methods=["POST"])
def api_extract_save():
    if not is_logged_in():
        return jsonify({"error": "Unauthorized"}), 401
    data              = request.get_json(silent=True) or {}
    chinese_term      = (data.get("chinese_term")           or "").strip()
    known_translation = (data.get("known_translation")      or "").strip()
    translation1      = (data.get("translation1")           or "").strip()
    translation2      = (data.get("translation2")           or "").strip()
    translation3      = (data.get("translation3")           or "").strip()
    pinyin            = (data.get("pinyin")                 or "").strip()
    pali              = (data.get("pali")                   or "").strip()
    sanskrit          = (data.get("sanskrit")               or "").strip()
    source_name       = (data.get("source_name")            or "").strip()
    src_zh            = (data.get("source_content_chinese") or "").strip()
    src_en            = (data.get("source_content_english") or "").strip()
    if not chinese_term:
        return jsonify({"error": "chinese_term is required"}), 400
    try:
        ts       = get_terms_sheet()
        all_rows = ts.get_all_values()
        # Server-side existence check — find by Chinese column (col 2, index 1)
        existing_row_num     = None
        existing_term_id     = ""
        existing_trans_known = ""
        existing_chinese     = ""
        for i, row in enumerate(all_rows):
            if i == 0:
                continue
            if len(row) >= 2 and row[1].strip() == chinese_term:
                existing_row_num     = i + 1   # 1-based for gspread
                existing_term_id     = row[0]
                existing_chinese     = row[COL["chinese"] - 1]
                existing_trans_known = row[COL["trans_known"] - 1] if len(row) >= COL["trans_known"] else ""
                break

        now_str    = datetime.now().strftime("%Y-%m-%d %H:%M")
        user_email = session["user_email"]
        user_name  = session.get("user_name", "")

        if existing_row_num is None:
            # ── INSERT path ──
            if not can_create_term():
                return jsonify({"error": "You need Depositor access or higher to add new terms"}), 403
            term_id = next_term_id(ts)
            ts.append_row([
                term_id, chinese_term,
                pinyin, pali, sanskrit,
                "", "",                  # Context, Category
                "",                      # Notes
                translation1, translation2, translation3,
                "", "pending",           # Final, Status
                user_email, now_str,     # AddedBy, Timestamp
                known_translation,       # TranslationKnown
                source_name,             # Source
                "", "", "", "",          # TranslationFirst/Second, Other1/2
                user_email, now_str,     # LastModifiedBy, LastModifiedTime
                strip_tone_marks(pinyin),
                src_zh,
                src_en,
            ])
            write_audit(term_id, chinese_term, user_email, user_name,
                        "created", details=f"Term created via Extraction (Pinyin={pinyin})")
            return jsonify({"path": "insert", "id": term_id})
        else:
            # ── UPDATE path — only TranslationKnown + LastModified ──
            if not can_edit_existing():
                return jsonify({"error": "You need Member access or higher to update an existing term"}), 403
            ts.update_cell(existing_row_num, COL["trans_known"],        known_translation)
            ts.update_cell(existing_row_num, COL["last_modified_by"],   user_email)
            ts.update_cell(existing_row_num, COL["last_modified_time"], now_str)
            write_audit(existing_term_id, existing_chinese, user_email, user_name,
                        "updated",
                        field_changed=FIELD_LABELS.get("trans_known", "trans_known"),
                        old_value=existing_trans_known, new_value=known_translation)
            return jsonify({"path": "update", "id": existing_term_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


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
