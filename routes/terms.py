from flask import Blueprint, jsonify, request, session
from datetime import datetime
import csv, io

from config import (
    COL, VALID_VOTES, FIELD_LABELS, FIELD_TO_VOTE_KEY, VOTE_LABELS,
    VOTE_KEY_TO_COL_KEY, normalize_translation, strip_tone_marks,
)
from sheets import (
    get_terms_sheet, get_votes_sheet, get_audit_sheet,
    write_audit, next_term_id, recalculate_auto_selections,
)
from ai import generate_term_data, generate_missing_translations
from auth import is_logged_in, is_leader, can_create_term, can_vote, can_edit_existing

terms_bp = Blueprint('terms', __name__)


@terms_bp.route("/api/terms", methods=["GET"])
def api_get_terms():
    if not is_logged_in():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        ts         = get_terms_sheet()
        vs         = get_votes_sheet()
        rows       = ts.get_all_records()
        votes_rows = vs.get_all_records()
        user_email = session["user_email"]

        vote_tallies = {}
        user_votes   = {}
        for v in votes_rows:
            tid   = v.get("TermID", "")
            trans = v.get("ChosenTranslation", "")
            voter = v.get("VoterEmail", "")
            if tid not in vote_tallies:
                vote_tallies[tid] = {k: 0 for k in VALID_VOTES}
            if trans in vote_tallies[tid]:
                vote_tallies[tid][trans] += 1
            if voter == user_email:
                user_votes[tid] = trans

        result = []
        for r in rows:
            tid     = r.get("ID", "")
            tallies = vote_tallies.get(tid, {k: 0 for k in VALID_VOTES})
            result.append({
                "id":       tid,
                "chinese":  r.get("Chinese",  ""),
                "pinyin":   r.get("Pinyin",   ""),
                "pali":     r.get("Pali",     ""),
                "sanskrit": r.get("Sanskrit", ""),
                "context":  r.get("Context",  ""),
                "category": r.get("Category", ""),
                "notes":    r.get("Notes",    ""),
                "trans1":   r.get("Translation1", ""),
                "trans2":   r.get("Translation2", ""),
                "trans3":   r.get("Translation3", ""),
                "trans_known":   r.get("TranslationKnown",   ""),
                "source":        r.get("Source",             ""),
                "trans_first":   r.get("TranslationFirst",   ""),
                "trans_second":  r.get("TranslationSecond",  ""),
                "trans_other1":  r.get("TranslationOther1",  ""),
                "trans_other2":  r.get("TranslationOther2",  ""),
                "timestamp":          r.get("Timestamp",         ""),
                "final":              r.get("Final",             ""),
                "status":             r.get("Status",            "pending"),
                "added_by":           r.get("AddedBy",           ""),
                "last_modified_by":   r.get("LastModifiedBy",    ""),
                "last_modified_time": r.get("LastModifiedTime",  "") or r.get("LastModifiedDate", ""),
                "romanization_plain": r.get("RomanizationPlain", ""),
                "source_content_chinese": r.get("SourceContentChinese", ""),
                "source_content_english": r.get("SourceContentEnglish", ""),
                "votes":   tallies,
                "my_vote": user_votes.get(tid, ""),
            })
        return jsonify(result)
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
        ts                     = get_terms_sheet()
        term_id                = next_term_id(ts)
        source_content_chinese = data.get("source_content_chinese", "").strip()
        source_content_english = data.get("source_content_english", "").strip()
        notes                  = data.get("notes",      "").strip()
        context                = data.get("context",    "").strip()
        trans_known            = data.get("trans_known","").strip()
        pinyin, pali, sanskrit, t1, t2, t3 = generate_term_data(
            chinese, context, notes, source_content_chinese, source_content_english, trans_known,
        )
        now_str    = datetime.now().strftime("%Y-%m-%d %H:%M")
        user_email = session["user_email"]
        row = [
            term_id, chinese,
            pinyin, pali, sanskrit,
            context, "",          # Context, Category
            notes,
            t1, t2, t3,
            "", "pending",        # Final, Status
            user_email, now_str,  # AddedBy, Timestamp
            trans_known,          # TranslationKnown
            data.get("source", ""),
            "", "", "", "",       # TranslationFirst/Second, Other1/2
            user_email, now_str,  # LastModifiedBy, LastModifiedTime
            strip_tone_marks(pinyin),
            source_content_chinese,
            source_content_english,
        ]
        ts.append_row(row)
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
    ts      = get_terms_sheet()
    added   = 0
    errors  = []
    for i, row in enumerate(reader):
        chinese = row.get("chinese", row.get("Chinese", "")).strip()
        if not chinese:
            continue
        try:
            term_id     = next_term_id(ts)
            context     = row.get("context",     row.get("Context",          ""))
            notes       = row.get("notes",       row.get("Notes",            ""))
            source      = row.get("source",      row.get("Source",           "")).strip()
            trans_known = row.get("trans_known",
                          row.get("TranslationKnown",
                          row.get("known", row.get("Known", "")))).strip()
            added_by    = row.get("added_by", row.get("AddedBy", "")).strip() or session["user_email"]
            ai_pinyin, ai_pali, ai_sanskrit, t1, t2, t3 = generate_term_data(chinese, context, notes)
            pinyin   = row.get("pinyin",   row.get("Pinyin",   "")).strip() or ai_pinyin
            pali     = row.get("pali",     row.get("Pali",     "")).strip() or ai_pali
            sanskrit = row.get("sanskrit", row.get("Sanskrit", "")).strip() or ai_sanskrit
            ts.append_row([
                term_id, chinese,
                pinyin, pali, sanskrit,
                context,
                row.get("category", row.get("Category", "")),
                notes,
                t1, t2, t3, "", "pending",
                added_by,
                datetime.now().strftime("%Y-%m-%d %H:%M"),
                trans_known, source, "", "", "", "",
                "", "",
                strip_tone_marks(pinyin),
            ])
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
        "pinyin":      COL["pinyin"],
        "trans1":      COL["trans1"],
        "trans2":      COL["trans2"],
        "trans3":      COL["trans3"],
        "trans_known": COL["trans_known"],
        "trans_other1":COL["trans_other1"],
        "trans_other2":COL["trans_other2"],
        "source":      COL["source"],
        "context":     COL["context"],
        "category":    COL["category"],
        "notes":       COL["notes"],
        "source_content_chinese": COL["source_content_chinese"],
        "source_content_english": COL["source_content_english"],
    }
    if field not in editable:
        return jsonify({"error": "Invalid field"}), 400
    vote_key = FIELD_TO_VOTE_KEY.get(field)
    if vote_key:
        vs    = get_votes_sheet()
        votes = vs.get_all_records()
        if any(v.get("TermID") == term_id and v.get("ChosenTranslation") == vote_key for v in votes):
            return jsonify({"error": "locked", "message": "Cannot edit — this translation has votes"}), 409
    try:
        now_str  = datetime.now().strftime("%Y-%m-%d %H:%M")
        modifier = session["user_email"]
        ts   = get_terms_sheet()
        rows = ts.get_all_values()
        for i, row in enumerate(rows):
            if i == 0:
                continue
            if row[0] == term_id:
                old_value = row[editable[field] - 1] if len(row) >= editable[field] else ""
                chinese   = row[COL["chinese"] - 1]  if len(row) >= COL["chinese"]  else ""
                ts.update_cell(i + 1, editable[field], value)
                if field == "pinyin":
                    ts.update_cell(i + 1, COL["romanization_plain"], strip_tone_marks(value))
                ts.update_cell(i + 1, COL["last_modified_by"],   modifier)
                ts.update_cell(i + 1, COL["last_modified_time"], now_str)
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
        return jsonify({"error": "Term not found"}), 404
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

    VOTE_TO_COL = {k: COL[v] for k, v in VOTE_KEY_TO_COL_KEY.items()}
    if vote_key not in VOTE_TO_COL:
        return jsonify({"error": "Invalid choice"}), 400
    if which not in ("first", "second"):
        return jsonify({"error": "Invalid 'which' parameter"}), 400
    try:
        now_str  = datetime.now().strftime("%Y-%m-%d %H:%M")
        modifier = session["user_email"]
        ts   = get_terms_sheet()
        rows = ts.get_all_values()
        for i, row in enumerate(rows):
            if row[0] == term_id:
                text_col = VOTE_TO_COL[vote_key]
                text    = row[text_col - 1]           if len(row) >= text_col        else ""
                chinese = row[COL["chinese"] - 1]     if len(row) >= COL["chinese"] else ""
                if which == "first":
                    ts.update_cell(i + 1, COL["trans_first"], text)
                    ts.update_cell(i + 1, COL["final"],       vote_key)
                    ts.update_cell(i + 1, COL["status"],      "finalized")
                else:
                    ts.update_cell(i + 1, COL["trans_second"], text)
                ts.update_cell(i + 1, COL["last_modified_by"],   modifier)
                ts.update_cell(i + 1, COL["last_modified_time"], now_str)
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
        return jsonify({"error": "Term not found"}), 404
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
        ts   = get_terms_sheet()
        rows = ts.get_all_values()
        for i, row in enumerate(rows):
            if row[0] == term_id:
                old_first  = row[COL["trans_first"]  - 1] if len(row) >= COL["trans_first"]  else ""
                old_second = row[COL["trans_second"] - 1] if len(row) >= COL["trans_second"] else ""
                chinese    = row[COL["chinese"] - 1]      if len(row) >= COL["chinese"]      else ""
                ts.update_cell(i + 1, COL["trans_first"],        "")
                ts.update_cell(i + 1, COL["trans_second"],       "")
                ts.update_cell(i + 1, COL["final"],              "")
                ts.update_cell(i + 1, COL["status"],             "pending")
                ts.update_cell(i + 1, COL["last_modified_by"],   modifier)
                ts.update_cell(i + 1, COL["last_modified_time"], now_str)
                write_audit(term_id, chinese, modifier, session.get("user_name", ""),
                            "reset_final",
                            details=f"Reset finalization. Was: 1st=\"{old_first}\" 2nd=\"{old_second}\"")
                return jsonify({"status":             "reset",
                                "last_modified_by":   modifier,
                                "last_modified_time": now_str})
        return jsonify({"error": "Term not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@terms_bp.route("/api/terms/<term_id>/translate", methods=["POST"])
def api_translate_term(term_id):
    if not is_logged_in():
        return jsonify({"error": "Unauthorized"}), 401
    if not can_edit_existing():
        return jsonify({"error": "Your role does not allow editing existing terms"}), 403
    try:
        ts      = get_terms_sheet()
        vs      = get_votes_sheet()
        records = ts.get_all_records()
        term    = next((r for r in records if r.get("ID") == term_id), None)
        if not term:
            return jsonify({"error": "Term not found"}), 404

        votes  = vs.get_all_records()
        locked = {v.get("ChosenTranslation") for v in votes if v.get("TermID") == term_id}

        to_fill = []
        for vote_key, col_key in [("Translation1","trans1"),("Translation2","trans2"),("Translation3","trans3")]:
            if not term.get(vote_key) and vote_key not in locked:
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

        all_rows = ts.get_all_values()
        for i, row in enumerate(all_rows):
            if row[0] == term_id:
                result  = {}
                skipped = []
                for j, (vote_key, col_key) in enumerate(to_fill):
                    text = (generated[j] if j < len(generated) else "").strip()
                    if not text:
                        skipped.append(vote_key)
                        continue
                    norm = normalize_translation(text)
                    if norm in existing_norms:
                        skipped.append(vote_key)
                        continue
                    ts.update_cell(i + 1, COL[col_key], text)
                    result[vote_key] = text
                    existing_norms.add(norm)

                if result:
                    ts.update_cell(i + 1, COL["last_modified_by"],   modifier)
                    ts.update_cell(i + 1, COL["last_modified_time"], now_str)
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
        return jsonify({"error": "Term not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@terms_bp.route("/api/terms/<term_id>/audit", methods=["GET"])
def api_get_audit(term_id):
    if not is_logged_in():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        rows    = get_audit_sheet().get_all_records()
        entries = [r for r in rows if r.get("TermID") == term_id]
        entries.sort(key=lambda x: x.get("Timestamp", ""), reverse=True)
        return jsonify(entries)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@terms_bp.route("/api/vote", methods=["POST"])
def api_vote():
    if not is_logged_in():
        return jsonify({"error": "Unauthorized"}), 401
    if not can_vote():
        return jsonify({"error": "Your role does not allow voting"}), 403
    data    = request.json
    term_id = data.get("term_id")
    chosen  = data.get("chosen")
    if not term_id or chosen not in VALID_VOTES:
        return jsonify({"error": "Invalid vote"}), 400
    try:
        vs         = get_votes_sheet()
        ts         = get_terms_sheet()
        votes      = vs.get_all_records()
        user_email = session["user_email"]
        status     = "voted"

        existing_row = None
        old_vote     = ""
        for i, v in enumerate(votes):
            if v.get("TermID") == term_id and v.get("VoterEmail") == user_email:
                existing_row = i
                old_vote     = v.get("ChosenTranslation", "")
                break

        if existing_row is not None:
            vs.update_cell(existing_row + 2, 3, chosen)
            status = "updated"
        else:
            vs.append_row([term_id, user_email, chosen])

        updated_votes = vs.get_all_records()
        first, second = recalculate_auto_selections(term_id, updated_votes, ts)

        term_rows    = ts.get_all_values()
        term_chinese = next(
            (r[COL["chinese"] - 1] for r in term_rows[1:] if r and r[0] == term_id), ""
        )
        action = "vote_updated" if old_vote else "voted"
        detail = f"Voted for {VOTE_LABELS.get(chosen, chosen)}"
        if old_vote:
            detail = (f"Changed vote from {VOTE_LABELS.get(old_vote, old_vote)}"
                      f" to {VOTE_LABELS.get(chosen, chosen)}")
        write_audit(term_id, term_chinese, user_email, session.get("user_name", ""),
                    action, field_changed="vote", old_value=old_vote, new_value=chosen,
                    details=detail)

        return jsonify({"status": status, "trans_first": first, "trans_second": second})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@terms_bp.route("/api/unvote", methods=["POST"])
def api_unvote():
    if not is_logged_in():
        return jsonify({"error": "Unauthorized"}), 401
    if not can_vote():
        return jsonify({"error": "Your role does not allow voting"}), 403
    data    = request.json
    term_id = data.get("term_id")
    chosen  = data.get("chosen")
    if not term_id or chosen not in VALID_VOTES:
        return jsonify({"error": "Invalid request"}), 400
    try:
        vs         = get_votes_sheet()
        ts         = get_terms_sheet()
        user_email = session["user_email"]
        vote_rows  = vs.get_all_values()

        target_row = None
        for i, row in enumerate(vote_rows):
            if i == 0:
                continue
            if len(row) >= 3 and row[0] == term_id and row[1] == user_email and row[2] == chosen:
                target_row = i + 1  # 1-indexed for gspread
                break

        if target_row is None:
            return jsonify({"error": "Vote not found"}), 404

        vs.delete_rows(target_row)

        updated_votes = vs.get_all_records()
        first, second = recalculate_auto_selections(term_id, updated_votes, ts)

        # Remove the most recent matching audit entry for this user's vote
        try:
            audit_sheet = get_audit_sheet()
            audit_rows  = audit_sheet.get_all_values()
            match_row   = None
            for i, row in enumerate(audit_rows):
                if i == 0:
                    continue
                # Columns: AuditID, Timestamp, TermID, TermChinese, UserEmail, UserName,
                #          ActionType, FieldChanged, OldValue, NewValue, Details
                if (len(row) >= 10
                        and row[2] == term_id
                        and row[4] == user_email
                        and row[6] in ("voted", "vote_updated")
                        and row[9] == chosen):
                    match_row = i + 1
            if match_row is not None:
                audit_sheet.delete_rows(match_row)
        except Exception:
            pass

        return jsonify({"status": "removed", "trans_first": first, "trans_second": second})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
