from flask import Blueprint, jsonify, request, session
from datetime import datetime
import csv, io

from config import (
    FIELD_LABELS, VOTE_LABELS, VOTE_KEY_TO_COL_KEY,
    normalize_translation, strip_tone_marks,
)
from repositories.audit_repo import write_audit, get_term_audit
from repositories import terms_repo
from ai import generate_term_data, generate_missing_translations, classify_term, explain_term_context
from auth import is_logged_in, is_leader, can_create_term, can_edit_existing

terms_bp = Blueprint('terms', __name__)


@terms_bp.route("/api/terms", methods=["GET"])
def api_get_terms():
    if not is_logged_in():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        return jsonify(terms_repo.list_terms())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@terms_bp.route("/api/terms", methods=["POST"])
def api_add_term():
    if not is_logged_in():
        return jsonify({"error": "Unauthorized"}), 401
    if not can_create_term():
        return jsonify({"error": "Viewers cannot add new terms"}), 403
    data    = request.json
    chinese = data.get("chinese", "").strip()
    if not chinese:
        return jsonify({"error": "Chinese term is required"}), 400
    try:
        source_content_chinese = data.get("source_content_chinese", "").strip()
        source_content_english = data.get("source_content_english", "").strip()
        notes       = data.get("notes",       "").strip()
        context     = data.get("context",     "").strip()
        trans_known = data.get("trans_known", "").strip()
        pinyin, pali, sanskrit, t1, t2, t3 = generate_term_data(
            chinese, context, notes, source_content_chinese, source_content_english, trans_known,
        )
        now_str    = datetime.now().strftime("%Y-%m-%d %H:%M")
        user_email = session["user_email"]
        term_id = terms_repo.create_term({
            "chinese":      chinese,
            "pinyin":       pinyin,
            "pali":         pali,
            "sanskrit":     sanskrit,
            "context":      context,
            "category":     "",
            "notes":        notes,
            "translation_1": t1,
            "translation_2": t2,
            "translation_3": t3,
            "final":        "",
            "status":       "pending",
            "added_by":     user_email,
            "created_at":   now_str,
            "translation_known":   trans_known,
            "source":              data.get("source", ""),
            "translation_first":   "",
            "translation_second":  "",
            "translation_other_1": "",
            "translation_other_2": "",
            "last_modified_by":    user_email,
            "last_modified_at":    now_str,
            "romanization_plain":  strip_tone_marks(pinyin),
            "source_content_chinese": source_content_chinese,
            "source_content_english": source_content_english,
        })
        write_audit(term_id, chinese, user_email, session.get("user_name", ""),
                    "created", details=f"Term created with Pinyin={pinyin}")
        return jsonify({"status": "success", "id": term_id,
                        "trans1": t1, "trans2": t2, "trans3": t3,
                        "pinyin": pinyin, "pali": pali, "sanskrit": sanskrit})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@terms_bp.route("/api/terms/bulk", methods=["POST"])
def api_bulk_import():
    if not is_logged_in():
        return jsonify({"error": "Unauthorized"}), 401
    if not can_create_term():
        return jsonify({"error": "Viewers cannot import terms"}), 403
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    f       = request.files["file"]
    content = f.read().decode("utf-8-sig")
    reader  = csv.DictReader(io.StringIO(content))
    added   = 0
    errors  = []
    for i, row in enumerate(reader):
        chinese = row.get("chinese", row.get("Chinese", "")).strip()
        if not chinese:
            continue
        try:
            context     = row.get("context",     row.get("Context",     ""))
            notes       = row.get("notes",       row.get("Notes",       ""))
            source      = row.get("source",      row.get("Source",      "")).strip()
            trans_known = row.get("trans_known",
                          row.get("TranslationKnown",
                          row.get("known", row.get("Known", "")))).strip()
            added_by    = row.get("added_by", row.get("AddedBy", "")).strip() or session["user_email"]
            ai_pinyin, ai_pali, ai_sanskrit, t1, t2, t3 = generate_term_data(chinese, context, notes)
            pinyin   = row.get("pinyin",   row.get("Pinyin",   "")).strip() or ai_pinyin
            pali     = row.get("pali",     row.get("Pali",     "")).strip() or ai_pali
            sanskrit = row.get("sanskrit", row.get("Sanskrit", "")).strip() or ai_sanskrit
            now_str  = datetime.now().strftime("%Y-%m-%d %H:%M")
            terms_repo.create_term({
                "chinese":      chinese,
                "pinyin":       pinyin,
                "pali":         pali,
                "sanskrit":     sanskrit,
                "context":      context,
                "category":     row.get("category", row.get("Category", "")),
                "notes":        notes,
                "translation_1": t1,
                "translation_2": t2,
                "translation_3": t3,
                "final":        "",
                "status":       "pending",
                "added_by":     added_by,
                "created_at":   now_str,
                "translation_known":   trans_known,
                "source":              source,
                "translation_first":   "",
                "translation_second":  "",
                "translation_other_1": "",
                "translation_other_2": "",
                "last_modified_by":    "",
                "last_modified_at":    "",
                "romanization_plain":  strip_tone_marks(pinyin),
                "source_content_chinese": "",
                "source_content_english": "",
            })
            added += 1
        except Exception as e:
            errors.append(f"Row {i+2}: {str(e)}")
    return jsonify({"status": "success", "added": added, "errors": errors})


@terms_bp.route("/api/terms/<term_id>", methods=["PATCH"])
def api_update_term(term_id):
    if not is_logged_in():
        return jsonify({"error": "Unauthorized"}), 401
    if not can_edit_existing():
        return jsonify({"error": "Your role does not allow editing existing terms"}), 403
    data  = request.json or {}
    field = data.get("field")
    value = (data.get("value") or "").strip()
    editable = {
        "chinese",
        "pinyin", "trans1", "trans2", "trans3", "trans_known",
        "trans_other1", "trans_other2", "source", "context", "category", "notes",
        "source_content_chinese", "source_content_english",
        "entity_type", "subject_field",
    }
    if field not in editable:
        return jsonify({"error": "Invalid field"}), 400
    if field == "chinese" and not is_leader():
        return jsonify({"error": "Leader or admin only"}), 403
    if field == "notes" and not is_leader():
        return jsonify({"error": "Only leaders and admins can edit the full Notes text. Use Add to Note to append."}), 403
    if field == "chinese" and not (data.get("value") or "").strip():
        return jsonify({"error": "Chinese term cannot be empty"}), 400
    try:
        now_str  = datetime.now().strftime("%Y-%m-%d %H:%M")
        modifier = session["user_email"]

        extra = None
        if field in ("entity_type", "subject_field"):
            extra = {
                "classification_source": "manual",
                "classified_by":         modifier,
                "classified_at":         now_str,
            }

        chinese, old_value = terms_repo.update_term_field(
            term_id, field, value, modifier, now_str, extra_updates=extra
        )
        if chinese is None:
            return jsonify({"error": "Term not found"}), 404
        write_audit(term_id, chinese, modifier, session.get("user_name", ""),
                    "updated",
                    field_changed=FIELD_LABELS.get(field, field),
                    old_value=old_value, new_value=value)
        result = {"status": "updated",
                  "last_modified_by":   modifier,
                  "last_modified_time": now_str}
        if field == "pinyin":
            result["romanization_plain"] = strip_tone_marks(value)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@terms_bp.route("/api/terms/<term_id>/notes/append", methods=["POST"])
def api_append_note(term_id):
    """Member+: append a stamped note line. Full notes rewrite is leader-only via PATCH."""
    if not is_logged_in():
        return jsonify({"error": "Unauthorized"}), 401
    if not can_edit_existing():
        return jsonify({"error": "Your role does not allow editing existing terms"}), 403
    data = request.json or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "Note text is required"}), 400
    try:
        now_str  = datetime.now().strftime("%Y-%m-%d %H:%M")
        modifier = session["user_email"]
        name     = (session.get("user_name") or "").strip() or modifier
        stamp_line = f"{now_str} - [{name}]: {text}"

        term = terms_repo.get_term_record(term_id)
        if not term:
            return jsonify({"error": "Term not found"}), 404
        prev = (term.get("Notes") or "").strip()
        combined = f"{prev}\n{stamp_line}" if prev else stamp_line

        chinese, old_value = terms_repo.update_term_field(
            term_id, "notes", combined, modifier, now_str
        )
        if chinese is None:
            return jsonify({"error": "Term not found"}), 404
        write_audit(term_id, chinese, modifier, session.get("user_name", ""),
                    "updated",
                    field_changed=FIELD_LABELS.get("notes", "Notes"),
                    old_value=old_value, new_value=combined,
                    details="Appended note")
        return jsonify({
            "status": "updated",
            "notes": combined,
            "last_modified_by": modifier,
            "last_modified_time": now_str,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@terms_bp.route("/api/terms/<term_id>/final", methods=["POST"])
def api_set_final(term_id):
    if not is_logged_in():
        return jsonify({"error": "Unauthorized"}), 401
    if not is_leader():
        return jsonify({"error": "Leader or admin only"}), 403
    data     = request.json
    vote_key = data.get("final")
    which    = data.get("which", "first")

    if vote_key not in VOTE_KEY_TO_COL_KEY:
        return jsonify({"error": "Invalid choice"}), 400
    if which not in ("first", "second"):
        return jsonify({"error": "Invalid 'which' parameter"}), 400
    try:
        now_str  = datetime.now().strftime("%Y-%m-%d %H:%M")
        modifier = session["user_email"]
        text, chinese = terms_repo.set_final(term_id, vote_key, which, modifier, now_str)
        if text is None:
            return jsonify({"error": "Term not found"}), 404
        label = VOTE_LABELS.get(vote_key, vote_key)
        if which == "first":
            write_audit(term_id, chinese, modifier, session.get("user_name", ""),
                        "finalized_first", field_changed="TranslationFirst",
                        new_value=text,
                        details=f"Set Final 1st = {label}: \"{text}\"")
        else:
            write_audit(term_id, chinese, modifier, session.get("user_name", ""),
                        "finalized_second", field_changed="TranslationSecond",
                        new_value=text,
                        details=f"Set Final 2nd = {label}: \"{text}\"")
        return jsonify({"status":             "success",
                        "which":              which,
                        "text":               text,
                        "last_modified_by":   modifier,
                        "last_modified_time": now_str})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@terms_bp.route("/api/terms/<term_id>/final/reset", methods=["POST"])
def api_reset_final(term_id):
    if not is_logged_in():
        return jsonify({"error": "Unauthorized"}), 401
    if not is_leader():
        return jsonify({"error": "Leader or admin only"}), 403
    try:
        now_str  = datetime.now().strftime("%Y-%m-%d %H:%M")
        modifier = session["user_email"]
        old_first, old_second, chinese = terms_repo.reset_final(term_id, modifier, now_str)
        if chinese is None:
            return jsonify({"error": "Term not found"}), 404
        write_audit(term_id, chinese, modifier, session.get("user_name", ""),
                    "reset_final",
                    details=f"Reset finalization. Was: 1st=\"{old_first}\" 2nd=\"{old_second}\"")
        return jsonify({"status":             "reset",
                        "last_modified_by":   modifier,
                        "last_modified_time": now_str})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@terms_bp.route("/api/terms/<term_id>/pending", methods=["POST"])
def api_mark_pending(term_id):
    if not is_logged_in():
        return jsonify({"error": "Unauthorized"}), 401
    if not is_leader():
        return jsonify({"error": "Leader or admin only"}), 403
    try:
        now_str  = datetime.now().strftime("%Y-%m-%d %H:%M")
        modifier = session["user_email"]
        chinese  = terms_repo.mark_pending(term_id, modifier, now_str)
        if chinese is None:
            return jsonify({"error": "Term not found"}), 404
        write_audit(term_id, chinese, modifier, session.get("user_name", ""),
                    "marked_pending", details="Marked as Pending")
        return jsonify({"status": "pending", "last_modified_by": modifier, "last_modified_time": now_str})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@terms_bp.route("/api/terms/<term_id>/review", methods=["POST"])
def api_mark_reviewed(term_id):
    if not is_logged_in():
        return jsonify({"error": "Unauthorized"}), 401
    if not is_leader():
        return jsonify({"error": "Leader or admin only"}), 403
    try:
        now_str  = datetime.now().strftime("%Y-%m-%d %H:%M")
        modifier = session["user_email"]
        chinese  = terms_repo.mark_reviewed(term_id, modifier, now_str)
        if chinese is None:
            return jsonify({"error": "Term not found"}), 404
        write_audit(term_id, chinese, modifier, session.get("user_name", ""),
                    "reviewed", details="Marked as Reviewed")
        return jsonify({"status": "reviewed", "last_modified_by": modifier, "last_modified_time": now_str})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@terms_bp.route("/api/terms/<term_id>/ask-ai", methods=["POST"])
def api_ask_ai(term_id):
    """Logged-in: ephemeral Buddhist doctrinal gloss in English (not saved on the term)."""
    if not is_logged_in():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        term = terms_repo.get_term_record(term_id)
        if not term:
            return jsonify({"error": "Term not found"}), 404

        explanation = explain_term_context(
            chinese     = term.get("Chinese", ""),
            pinyin      = term.get("Pinyin", ""),
            pali        = term.get("Pali", ""),
            sanskrit    = term.get("Sanskrit", ""),
            context     = term.get("Context", ""),
            notes       = term.get("Notes", ""),
            source_zh   = term.get("SourceContentChinese", ""),
            source_en   = term.get("SourceContentEnglish", ""),
            known_trans = term.get("TranslationKnown", "") or term.get("TranslationFirst", ""),
        )
        if not explanation:
            return jsonify({"error": "AI returned an empty response"}), 502

        preview = explanation.replace("\n", " ")
        if len(preview) > 160:
            preview = preview[:157] + "…"
        write_audit(
            term_id, term.get("Chinese", ""),
            session["user_email"], session.get("user_name", ""),
            "ask_ai", details=preview,
        )
        return jsonify({"explanation": explanation})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@terms_bp.route("/api/terms/<term_id>/translate", methods=["POST"])
def api_translate_term(term_id):
    if not is_logged_in():
        return jsonify({"error": "Unauthorized"}), 401
    if not can_edit_existing():
        return jsonify({"error": "Your role does not allow editing existing terms"}), 403
    try:
        term = terms_repo.get_term_record(term_id)
        if not term:
            return jsonify({"error": "Term not found"}), 404

        to_fill = []
        for vote_key, col_key in [("Translation1","trans1"),("Translation2","trans2"),("Translation3","trans3")]:
            if not term.get(vote_key):
                to_fill.append((vote_key, col_key))

        if not to_fill:
            return jsonify({"error": "No empty unlocked options to fill"}), 400

        existing_texts = [
            term.get("TranslationKnown",  ""),
            term.get("TranslationOther1", ""),
            term.get("TranslationOther2", ""),
            term.get("Translation1",      ""),
            term.get("Translation2",      ""),
            term.get("Translation3",      ""),
            term.get("TranslationFirst",  ""),
            term.get("TranslationSecond", ""),
        ]
        existing_texts = [t for t in existing_texts if t and t.strip()]
        existing_norms = {normalize_translation(t) for t in existing_texts}

        src_zh  = term.get("SourceContentChinese", "")
        src_en  = term.get("SourceContentEnglish", "")
        ctx_str = term.get("Context", "")
        if src_zh or src_en:
            parts = []
            if src_zh:  parts.append(f"Source passage (Chinese): {src_zh}")
            if src_en:  parts.append(f"Source passage (English): {src_en}")
            if ctx_str: parts.append(f"Additional context: {ctx_str}")
            ctx_str = "\n".join(parts)

        generated = generate_missing_translations(
            chinese               = term.get("Chinese", ""),
            pinyin                = term.get("Pinyin", ""),
            context               = ctx_str,
            notes                 = term.get("Notes", ""),
            trans_known           = term.get("TranslationKnown", ""),
            trans_other1          = term.get("TranslationOther1", ""),
            trans_other2          = term.get("TranslationOther2", ""),
            count                 = len(to_fill),
            existing_translations = existing_texts,
        )

        now_str  = datetime.now().strftime("%Y-%m-%d %H:%M")
        modifier = session["user_email"]
        result   = {}
        skipped  = []

        for j, (vote_key, col_key) in enumerate(to_fill):
            text = (generated[j] if j < len(generated) else "").strip()
            if not text:
                skipped.append(vote_key)
                continue
            norm = normalize_translation(text)
            if norm in existing_norms:
                skipped.append(vote_key)
                continue
            result[vote_key] = text
            existing_norms.add(norm)

        if result:
            terms_repo.update_translations(term_id, result, modifier, now_str)
            _col_key_map = {"Translation1":"trans1","Translation2":"trans2","Translation3":"trans3"}
            for vk, vt in result.items():
                ck = _col_key_map.get(vk, vk.lower())
                write_audit(term_id, term.get("Chinese",""), modifier, session.get("user_name",""),
                            "ai_translated",
                            field_changed=FIELD_LABELS.get(ck, vk),
                            new_value=vt,
                            details=f"AI generated {VOTE_LABELS.get(vk, vk)}: \"{vt}\"")

        return jsonify({
            "status":             "success" if result else "no_unique",
            "translations":       result,
            "skipped":            skipped,
            "last_modified_by":   modifier if result else "",
            "last_modified_time": now_str  if result else "",
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@terms_bp.route("/api/terms/classify_batch", methods=["POST"])
def api_classify_batch():
    """Leader-only single-term classify step, called repeatedly by the frontend batch loop."""
    if not is_logged_in():
        return jsonify({"error": "Unauthorized"}), 401
    if not is_leader():
        return jsonify({"error": "Leader or admin only"}), 403
    data    = request.json or {}
    term_id = data.get("id", "").strip()
    if not term_id:
        return jsonify({"error": "id is required"}), 400
    try:
        term = terms_repo.get_term_record(term_id)
        if not term:
            return jsonify({"error": "Term not found"}), 404

        # Skip if already manually classified
        if terms_repo.get_classification_source(term_id) == "manual":
            return jsonify({"skipped": True, "reason": "already manual"}), 200

        result = classify_term({
            "chinese": term.get("Chinese", ""),
            "pinyin":  term.get("Pinyin",  ""),
            "context": term.get("Context", ""),
            "notes":   term.get("Notes",   ""),
        })
        now_str = datetime.now().isoformat()
        terms_repo.update_classification(
            term_id,
            entity_type=result["entity_type"],
            subject_field=result["subject_field"],
            source="ai",
            classified_by="ai:claude-haiku-4-5",
            now_ts=now_str,
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@terms_bp.route("/api/terms/<term_id>/classify", methods=["POST"])
def api_classify_term(term_id):
    """Member+ — call AI to classify one term and write the result to the database."""
    if not is_logged_in():
        return jsonify({"error": "Unauthorized"}), 401
    if not can_edit_existing():
        return jsonify({"error": "member+ required"}), 403
    try:
        term = terms_repo.get_term_record(term_id)
        if not term:
            return jsonify({"error": "Term not found"}), 404

        result = classify_term({
            "chinese": term.get("Chinese", ""),
            "pinyin":  term.get("Pinyin",  ""),
            "context": term.get("Context", ""),
            "notes":   term.get("Notes",   ""),
        })
        now_str = datetime.now().isoformat()
        terms_repo.update_classification(
            term_id,
            entity_type=result["entity_type"],
            subject_field=result["subject_field"],
            source="ai",
            classified_by="ai:claude-haiku-4-5",
            now_ts=now_str,
        )
        write_audit(term_id, term.get("Chinese", ""),
                    session["user_email"], session.get("user_name", ""),
                    "ai_classified",
                    details=f"AI: entity_type={result['entity_type']}, subject_field={result['subject_field']}, confidence={result['confidence']:.2f}")
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@terms_bp.route("/api/terms/merge", methods=["POST"])
def api_merge_terms():
    """Leader/admin: merge two terms — apply chosen fields to keep_id, deactivate drop_id."""
    if not is_logged_in():
        return jsonify({"error": "Unauthorized"}), 401
    if not is_leader():
        return jsonify({"error": "Leader or admin only"}), 403
    data = request.json or {}
    keep_id = (data.get("keep_id") or "").strip()
    drop_id = (data.get("drop_id") or "").strip()
    fields  = data.get("fields") or {}
    if not keep_id or not drop_id:
        return jsonify({"error": "keep_id and drop_id are required"}), 400
    if keep_id == drop_id:
        return jsonify({"error": "Cannot merge a term with itself"}), 400
    if not isinstance(fields, dict):
        return jsonify({"error": "fields must be an object"}), 400
    try:
        now_str  = datetime.now().strftime("%Y-%m-%d %H:%M")
        modifier = session["user_email"]
        result   = terms_repo.merge_terms(keep_id, drop_id, fields, modifier, now_str)
        if result is None:
            return jsonify({"error": "One or both terms not found"}), 404
        summary = ", ".join(fields.keys()) or "(no field overrides)"
        write_audit(keep_id, result["keep_chinese"], modifier, session.get("user_name", ""),
                    "merged", details=f"Merged from {drop_id}. Fields: {summary}")
        write_audit(drop_id, result["drop_chinese"], modifier, session.get("user_name", ""),
                    "merged_into", details=f"Merged into {keep_id}")
        return jsonify({
            "keep":    result["keep"],
            "drop_id": drop_id,
            "status":  "merged",
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@terms_bp.route("/api/terms/<term_id>/inactive", methods=["POST"])
def api_mark_inactive(term_id):
    if not is_logged_in():
        return jsonify({"error": "Unauthorized"}), 401
    if not is_leader():
        return jsonify({"error": "Leader or admin only"}), 403
    try:
        now_str  = datetime.now().strftime("%Y-%m-%d %H:%M")
        modifier = session["user_email"]
        chinese  = terms_repo.deactivate_term(term_id, modifier, now_str)
        if chinese is None:
            return jsonify({"error": "Term not found"}), 404
        write_audit(term_id, chinese, modifier, session.get("user_name", ""),
                    "marked_inactive", details="Marked as Inactive")
        return jsonify({"status": "inactive", "last_modified_by": modifier, "last_modified_time": now_str})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@terms_bp.route("/api/terms/<term_id>/reactivate", methods=["POST"])
def api_reactivate_term(term_id):
    if not is_logged_in():
        return jsonify({"error": "Unauthorized"}), 401
    if not is_leader():
        return jsonify({"error": "Leader or admin only"}), 403
    try:
        now_str  = datetime.now().strftime("%Y-%m-%d %H:%M")
        modifier = session["user_email"]
        chinese  = terms_repo.reactivate_term(term_id, modifier, now_str)
        if chinese is None:
            return jsonify({"error": "Term not found"}), 404
        write_audit(term_id, chinese, modifier, session.get("user_name", ""),
                    "reactivated", details="Restored to New status")
        return jsonify({"status": "new", "last_modified_by": modifier, "last_modified_time": now_str})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@terms_bp.route("/api/terms/<term_id>", methods=["DELETE"])
def api_delete_term(term_id):
    if not is_logged_in():
        return jsonify({"error": "Unauthorized"}), 401
    if not is_leader():
        return jsonify({"error": "Leader or admin only"}), 403
    try:
        modifier = session["user_email"]
        chinese, blocked = terms_repo.delete_term(term_id)
        if chinese is None:
            return jsonify({"error": "Term not found"}), 404
        if blocked:
            return jsonify({"error": "Cannot delete a term that has finalized translations. Reset suggestions first."}), 409
        write_audit(term_id, chinese, modifier, session.get("user_name", ""),
                    "deleted", details=f"Term permanently deleted by {modifier}")
        return jsonify({"status": "deleted"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@terms_bp.route("/api/terms/<term_id>/audit", methods=["GET"])
def api_get_audit(term_id):
    if not is_logged_in():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        return jsonify(get_term_audit(term_id))
    except Exception as e:
        return jsonify({"error": str(e)}), 500
