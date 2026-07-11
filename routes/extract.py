import re
from datetime import datetime
from flask import Blueprint, jsonify, request, session
from auth import is_logged_in, can_create_term, can_edit_existing
from ai import find_known_translation, generate_term_data, classify_term
from config import FIELD_LABELS, strip_tone_marks
from repositories import terms_repo, extraction_repo
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
        all_terms = terms_repo.list_terms()
        result = [
            {
                "id":          t.get("id",          ""),
                "chinese":     t.get("chinese",     ""),
                "pinyin":      t.get("pinyin",      ""),
                "pali":        t.get("pali",        ""),
                "sanskrit":    t.get("sanskrit",    ""),
                "trans_known": t.get("trans_known", ""),
                "trans1":      t.get("trans1",      ""),
                "trans2":      t.get("trans2",      ""),
                "trans3":      t.get("trans3",      ""),
            }
            for t in all_terms
        ]
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
    entity_type       = (data.get("entity_type")            or "").strip()
    subject_field     = (data.get("subject_field")          or "").strip()
    if not chinese_term:
        return jsonify({"error": "chinese_term is required"}), 400
    try:
        existing = terms_repo.find_by_chinese(chinese_term)
        now_str    = datetime.now().strftime("%Y-%m-%d %H:%M")
        user_email = session["user_email"]
        user_name  = session.get("user_name", "")

        if existing is None:
            # ── INSERT path ──
            if not can_create_term():
                return jsonify({"error": "You need Depositor access or higher to add new terms"}), 403
            term_id = terms_repo.create_term({
                "chinese":      chinese_term,
                "pinyin":       pinyin,
                "pali":         pali,
                "sanskrit":     sanskrit,
                "context":      "",
                "category":     "",
                "notes":        "",
                "translation_1": translation1,
                "translation_2": translation2,
                "translation_3": translation3,
                "final":        "",
                "status":       "pending",
                "added_by":     user_email,
                "created_at":   now_str,
                "translation_known":   known_translation,
                "source":              source_name,
                "translation_first":   "",
                "translation_second":  "",
                "translation_other_1": "",
                "translation_other_2": "",
                "last_modified_by":    user_email,
                "last_modified_at":    now_str,
                "romanization_plain":  strip_tone_marks(pinyin),
                "source_content_chinese": src_zh,
                "source_content_english": src_en,
                "entity_type":            entity_type or None,
                "subject_field":          subject_field or None,
                "classification_source":  "manual" if entity_type else None,
                "classified_by":          user_email if entity_type else None,
                "classified_at":          now_str if entity_type else None,
            })
            write_audit(term_id, chinese_term, user_email, user_name,
                        "created", details=f"Term created via Extraction (Pinyin={pinyin})")
            return jsonify({"path": "insert", "id": term_id})
        else:
            # ── UPDATE path — only TranslationKnown + LastModified ──
            if not can_edit_existing():
                return jsonify({"error": "You need Member access or higher to update an existing term"}), 403
            existing_term_id     = existing.get("ID", "")
            existing_chinese     = existing.get("Chinese", "")
            existing_trans_known = existing.get("TranslationKnown", "")
            terms_repo.update_term_field(existing_term_id, "trans_known",
                                         known_translation, user_email, now_str)
            write_audit(existing_term_id, existing_chinese, user_email, user_name,
                        "updated",
                        field_changed=FIELD_LABELS.get("trans_known", "trans_known"),
                        old_value=existing_trans_known, new_value=known_translation)
            return jsonify({"path": "update", "id": existing_term_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@extract_bp.route("/api/extract/classify-candidate", methods=["POST"])
def api_classify_candidate():
    """AI-classify a candidate term (before it is saved). Login required."""
    if not is_logged_in():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    chinese = (data.get("chinese") or "").strip()
    if not chinese:
        return jsonify({"error": "chinese is required"}), 400
    result = classify_term({
        "chinese": chinese,
        "context": data.get("context", ""),
        "notes":   "",
        "pinyin":  "",
    })
    return jsonify(result)


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

    title       = (request.form.get("title")       or "").strip()
    source_name = (request.form.get("source_name") or "").strip()
    uploaded_by = session.get("user_email", "")
    uploaded_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    try:
        doc_id = extraction_repo.create_document(
            title, source_name, zh_paras, en_paras, uploaded_by, uploaded_at
        )
    except Exception as e:
        return jsonify({"error": f"Failed to save document: {e}"}), 500

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
        return jsonify(extraction_repo.list_documents())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@extract_bp.route("/api/extract/documents/<document_id>/paragraphs", methods=["GET"])
def api_extract_paragraphs_get(document_id):
    if not is_logged_in():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        result = extraction_repo.get_paragraphs(document_id)
        if result is None:
            return jsonify({"error": "Document not found"}), 404
        return jsonify(result)
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
        if not extraction_repo.update_last_viewed_index(document_id, data["last_viewed_index"]):
            return jsonify({"error": "Document not found"}), 404
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
