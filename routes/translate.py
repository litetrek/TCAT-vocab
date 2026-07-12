import json
from datetime import datetime, timezone
from functools import wraps
from flask import Blueprint, jsonify, request, session
from auth import is_logged_in, can_access_translation_module, can_edit_existing, is_leader
from db import supabase
from segmenter import decode, split_paragraphs, detect_section_type, segment_paragraph
from ai import group_sentences_by_topic, translate_unit
from repositories import terms_repo
from repositories.audit_repo import write_audit

translate_bp = Blueprint("translate", __name__)

MAX_FILE_SIZE = 2 * 1024 * 1024  # 2 MB
AI_MODEL_NAME = "claude-haiku-4-5-20251001"


# ── Access guard ──────────────────────────────────────────────────────────────

def _require_translation(f):
    """Decorator: must be logged in AND have translation-module access."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not is_logged_in():
            return jsonify({"error": "Unauthorized"}), 401
        if not can_access_translation_module(session.get("user_role", "")):
            return jsonify({"error": "Forbidden"}), 403
        return f(*args, **kwargs)
    return wrapper


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


# ── T3 helpers ─────────────────────────────────────────────────────────────

def _match_constraint_terms(chinese_text, limit=15):
    """Find Final/Known terms that appear in chinese_text (longest match first)."""
    try:
        all_terms = terms_repo.get_translation_constraint_terms()
    except Exception:
        return []
    hits = [t for t in all_terms if t["chinese"] and t["chinese"] in chinese_text]
    hits.sort(key=lambda t: len(t["chinese"]), reverse=True)
    return hits[:limit]


def _get_context(chapter_id, unit_id):
    """Return (prev_chinese, next_chinese) — adjacent confirmed units in the same chapter."""
    try:
        result = (
            supabase.table("trans_units")
            .select("id,chinese_text")
            .eq("chapter_id", chapter_id)
            .order("paragraph_index")
            .order("unit_order")
            .execute()
        )
    except Exception:
        return "", ""
    rows = result.data or []
    idx = next((i for i, r in enumerate(rows) if r["id"] == unit_id), None)
    if idx is None:
        return "", ""
    prev_text = rows[idx - 1]["chinese_text"] if idx > 0 else ""
    next_text = rows[idx + 1]["chinese_text"] if idx < len(rows) - 1 else ""
    return prev_text or "", next_text or ""


# ── GET /api/trans/known-terms ───────────────────────────────────────────────

@translate_bp.route("/api/trans/known-terms", methods=["GET"])
@_require_translation
def api_trans_known_terms():
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
                "status":      t.get("status",      "pending"),
                "final":       t.get("final",       ""),
            }
            for t in all_terms
        ]
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── POST /api/trans/books ─────────────────────────────────────────────────────
# T2.1: create book metadata only (no file upload).

@translate_bp.route("/api/trans/books", methods=["POST"])
@_require_translation
def api_create_book():
    """Create a new book record with title only — no content."""
    if request.is_json:
        body = request.get_json() or {}
        title = body.get("title", "").strip()
    else:
        title = request.form.get("title", "").strip()

    if not title:
        return jsonify({"error": "title is required"}), 400

    created_by = session.get("user_email", "")

    try:
        did = supabase.rpc("next_display_id", {
            "p_prefix": "BK", "p_seq_name": "seq_trans_books_display"
        }).execute().data

        result = supabase.table("trans_books").insert({
            "display_id": did,
            "title": title,
            "created_by": created_by,
        }).execute()

        book = result.data[0]
        return jsonify({
            "book_id":    book["id"],
            "display_id": book["display_id"],
            "title":      book["title"],
        }), 201

    except Exception as exc:
        return jsonify({"error": f"Database error: {exc}"}), 500


# ── GET /api/trans/books ──────────────────────────────────────────────────────

@translate_bp.route("/api/trans/books", methods=["GET"])
@_require_translation
def api_list_books():
    """Return all active books with per-status unit counts."""
    try:
        result = supabase.rpc("list_trans_books", {}).execute()
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    return jsonify(result.data)


# ── POST /api/trans/books/<id>/chapters ──────────────────────────────────────

@translate_bp.route("/api/trans/books/<int:book_id>/chapters", methods=["POST"])
@_require_translation
def api_upload_chapter(book_id):
    """Upload one chapter .txt file → segment → create trans_unit_drafts."""
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "Empty filename"}), 400

    raw = f.read(MAX_FILE_SIZE + 1)
    if len(raw) > MAX_FILE_SIZE:
        return jsonify({"error": "File too large (max 2 MB)"}), 400

    text = decode(raw)
    if text is None:
        return jsonify({"error": "Cannot decode file — use UTF-8, GB18030, or Big5"}), 400

    title = request.form.get("title", "").strip()
    section_type_override = request.form.get("section_type", "").strip()

    # Segment file: paragraphs → sentences
    paragraphs = split_paragraphs(text)
    if not paragraphs:
        return jsonify({"error": "No content found in file"}), 400

    section_type = section_type_override or detect_section_type(paragraphs[0])

    # Auto-assign chapter_index as next available for this book
    try:
        ci_str = request.form.get("chapter_index", "").strip()
        if ci_str:
            chapter_index = int(ci_str)
        else:
            existing = (
                supabase.table("trans_chapters")
                .select("chapter_index")
                .eq("book_id", book_id)
                .order("chapter_index", desc=True)
                .limit(1)
                .execute()
            )
            chapter_index = (existing.data[0]["chapter_index"] + 1) if existing.data else 0
    except (ValueError, Exception) as exc:
        return jsonify({"error": f"Could not determine chapter_index: {exc}"}), 400

    created_by = session.get("user_email", "")

    try:
        # Create the chapter
        ch_did = supabase.rpc("next_display_id", {
            "p_prefix": "CH", "p_seq_name": "seq_trans_chapters_display"
        }).execute().data

        ch_result = supabase.table("trans_chapters").insert({
            "display_id":    ch_did,
            "book_id":       book_id,
            "chapter_index": chapter_index,
            "title":         title,
            "section_type":  section_type,
        }).execute()
        chapter_id = ch_result.data[0]["id"]

        # Build draft rows — one per non-empty paragraph
        drafts = []
        for para_idx, para in enumerate(paragraphs):
            sentences = segment_paragraph(para)
            if not sentences:
                continue
            # Initial grouping: each sentence is its own group
            draft_groups = [{"sentences": [s]} for s in sentences]
            drafts.append({
                "chapter_id":      chapter_id,
                "paragraph_index": para_idx,
                "draft_groups":    draft_groups,
                "status":          "pending",
                "last_modified_by": created_by,
            })

        if drafts:
            supabase.table("trans_unit_drafts").insert(drafts).execute()

        return jsonify({
            "chapter_id":      chapter_id,
            "display_id":      ch_did,
            "paragraph_count": len(drafts),
        }), 201

    except Exception as exc:
        return jsonify({"error": f"Database error: {exc}"}), 500


# ── GET /api/trans/books/<book_id>/chapters ───────────────────────────────────

@translate_bp.route("/api/trans/books/<int:book_id>/chapters", methods=["GET"])
@_require_translation
def api_list_chapters(book_id):
    """Return chapters of a book ordered by chapter_index."""
    try:
        result = (
            supabase.table("trans_chapters")
            .select("id,display_id,chapter_index,title,section_type,status")
            .eq("book_id", book_id)
            .order("chapter_index")
            .execute()
        )
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    return jsonify(result.data)


# ── GET /api/trans/chapters/<chapter_id>/units ────────────────────────────────

@translate_bp.route("/api/trans/chapters/<int:chapter_id>/units", methods=["GET"])
@_require_translation
def api_list_units(chapter_id):
    """Return all confirmed units in a chapter ordered by paragraph_index, unit_order."""
    try:
        result = (
            supabase.table("trans_units")
            .select("*")
            .eq("chapter_id", chapter_id)
            .order("paragraph_index")
            .order("unit_order")
            .execute()
        )
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    return jsonify(result.data)


# ── GET /api/trans/chapters/<chapter_id>/drafts ───────────────────────────────

@translate_bp.route("/api/trans/chapters/<int:chapter_id>/drafts", methods=["GET"])
@_require_translation
def api_get_drafts(chapter_id):
    """Return all paragraph drafts for a chapter (ordered by paragraph_index)."""
    try:
        result = (
            supabase.table("trans_unit_drafts")
            .select("*")
            .eq("chapter_id", chapter_id)
            .order("paragraph_index")
            .execute()
        )
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    return jsonify(result.data)


# ── POST /api/trans/chapters/<id>/paragraphs/<idx>/group-preview ──────────────

@translate_bp.route(
    "/api/trans/chapters/<int:chapter_id>/paragraphs/<int:para_idx>/group-preview",
    methods=["POST"],
)
@_require_translation
def api_group_preview(chapter_id, para_idx):
    """Run AI topic grouping on a paragraph; update draft; return result."""
    try:
        draft_res = (
            supabase.table("trans_unit_drafts")
            .select("*")
            .eq("chapter_id", chapter_id)
            .eq("paragraph_index", para_idx)
            .execute()
        )
        if not draft_res.data:
            return jsonify({"error": "Draft not found"}), 404
        draft = draft_res.data[0]
    except Exception as exc:
        return jsonify({"error": f"Database error: {exc}"}), 500

    # Flatten current draft_groups to get flat sentence list
    groups = draft.get("draft_groups") or []
    sentences = [s for g in groups for s in g.get("sentences", [])]

    if not sentences:
        return jsonify({"error": "No sentences in draft"}), 400

    # AI grouping — never raises (returns fallback on failure)
    index_groups = group_sentences_by_topic(sentences)

    new_draft_groups = [
        {"sentences": [sentences[i] for i in grp]}
        for grp in index_groups
    ]

    modified_by = session.get("user_email", "")
    try:
        upd = (
            supabase.table("trans_unit_drafts")
            .update({
                "draft_groups":    new_draft_groups,
                "status":          "ai_suggested",
                "last_modified_by": modified_by,
                "last_modified_at": _now_iso(),
            })
            .eq("chapter_id", chapter_id)
            .eq("paragraph_index", para_idx)
            .execute()
        )
        return jsonify(upd.data[0])
    except Exception as exc:
        return jsonify({"error": f"Database error: {exc}"}), 500


# ── PATCH /api/trans/chapters/<id>/paragraphs/<idx>/draft ────────────────────

@translate_bp.route(
    "/api/trans/chapters/<int:chapter_id>/paragraphs/<int:para_idx>/draft",
    methods=["PATCH"],
)
@_require_translation
def api_patch_draft(chapter_id, para_idx):
    """Human adjustment: update draft_groups and status; auto-saved on every change."""
    data = request.get_json()
    if not data or "draft_groups" not in data:
        return jsonify({"error": "draft_groups required"}), 400

    modified_by = session.get("user_email", "")
    try:
        result = (
            supabase.table("trans_unit_drafts")
            .update({
                "draft_groups":    data["draft_groups"],
                "status":          "human_adjusted",
                "last_modified_by": modified_by,
                "last_modified_at": _now_iso(),
            })
            .eq("chapter_id", chapter_id)
            .eq("paragraph_index", para_idx)
            .execute()
        )
        if not result.data:
            return jsonify({"error": "Draft not found"}), 404
        return jsonify(result.data[0])
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


# ── POST /api/trans/chapters/<id>/paragraphs/<idx>/confirm ───────────────────

@translate_bp.route(
    "/api/trans/chapters/<int:chapter_id>/paragraphs/<int:para_idx>/confirm",
    methods=["POST"],
)
@_require_translation
def api_confirm_paragraph(chapter_id, para_idx):
    """Write confirmed draft groups into trans_units; mark draft confirmed."""
    try:
        draft_res = (
            supabase.table("trans_unit_drafts")
            .select("*")
            .eq("chapter_id", chapter_id)
            .eq("paragraph_index", para_idx)
            .execute()
        )
        if not draft_res.data:
            return jsonify({"error": "Draft not found"}), 404
        draft = draft_res.data[0]
    except Exception as exc:
        return jsonify({"error": f"Database error: {exc}"}), 500

    draft_groups = draft.get("draft_groups") or []
    if not draft_groups:
        return jsonify({"error": "No groups to confirm"}), 400

    # Re-confirm is allowed: delete any existing units for this paragraph first
    try:
        supabase.table("trans_units").delete() \
            .eq("chapter_id", chapter_id) \
            .eq("paragraph_index", para_idx) \
            .execute()
    except Exception:
        pass

    unit_count = 0
    try:
        for unit_order, group in enumerate(draft_groups, start=1):
            sentences = group.get("sentences", [])
            if not sentences:
                continue
            chinese_text = "".join(s["text"] for s in sentences)
            is_long = any(s.get("is_long_sentence", False) for s in sentences)

            u_did = supabase.rpc("next_display_id", {
                "p_prefix": "U", "p_seq_name": "seq_trans_units_display"
            }).execute().data

            supabase.table("trans_units").insert({
                "display_id":      u_did,
                "chapter_id":      chapter_id,
                "paragraph_index": para_idx,
                "unit_order":      unit_order,
                "chinese_text":    chinese_text,
                "is_long_sentence": is_long,
                "sentence_map":    sentences,
            }).execute()
            unit_count += 1

        # Mark draft as confirmed (keep the row for AI-quality tracking)
        supabase.table("trans_unit_drafts").update({
            "status":          "confirmed",
            "last_modified_at": _now_iso(),
        }).eq("chapter_id", chapter_id).eq("paragraph_index", para_idx).execute()

        return jsonify({"status": "confirmed", "unit_count": unit_count})

    except Exception as exc:
        return jsonify({"error": f"Database error: {exc}"}), 500


# ── T3 — AI Translation Drafting ──────────────────────────────────────────────

# ── POST /api/trans/units/<id>/translate ──────────────────────────────────────

@translate_bp.route("/api/trans/units/<int:unit_id>/translate", methods=["POST"])
@_require_translation
def api_translate_unit(unit_id):
    """Trigger (or re-trigger) AI translation for one unit. Member+.

    First run: writes english_draft (never overwritten again) and english_final.
    Re-run ("regenerate"): english_draft is preserved; the new attempt is written
    to english_final only, for side-by-side comparison against the current text.
    """
    if not can_edit_existing():
        return jsonify({"error": "Member role or higher required"}), 403

    try:
        result = supabase.table("trans_units").select("*").eq("id", unit_id).execute()
        if not result.data:
            return jsonify({"error": "Unit not found"}), 404
        unit = result.data[0]
    except Exception as exc:
        return jsonify({"error": f"Database error: {exc}"}), 500

    chinese_text = unit.get("chinese_text") or ""
    if not chinese_text.strip():
        return jsonify({"error": "Unit has no Chinese text"}), 400

    term_hits          = _match_constraint_terms(chinese_text)
    ctx_before, ctx_after = _get_context(unit["chapter_id"], unit_id)

    ai_result = translate_unit(
        chinese_text,
        term_constraints=term_hits,
        context_before=ctx_before,
        context_after=ctx_after,
        is_long_sentence=bool(unit.get("is_long_sentence")),
    )

    is_first_draft = not (unit.get("english_draft") or "").strip()
    modifier = session.get("user_email", "")

    updates = {
        "english_final":     ai_result["english"],
        "ai_model":          AI_MODEL_NAME,
        "translated_by":     modifier,
        "status":            "ai_drafted",
        "last_modified_by":  modifier,
        "last_modified_at":  _now_iso(),
    }
    if is_first_draft:
        updates["english_draft"] = ai_result["english"]
    if ai_result.get("split_map"):
        updates["split_map"] = ai_result["split_map"]

    try:
        upd = supabase.table("trans_units").update(updates).eq("id", unit_id).execute()
        if not upd.data:
            return jsonify({"error": "Unit not found"}), 404
    except Exception as exc:
        return jsonify({"error": f"Database error: {exc}"}), 500

    write_audit(
        unit.get("display_id", ""), chinese_text, modifier, session.get("user_name", ""),
        "ai_translate", field_changed="english_final",
        old_value=unit.get("english_final") or "", new_value=ai_result["english"],
        details="initial draft" if is_first_draft else "regenerate",
    )

    return jsonify(upd.data[0])


# ── PATCH /api/trans/units/<id> ───────────────────────────────────────────────

@translate_bp.route("/api/trans/units/<int:unit_id>", methods=["PATCH"])
@_require_translation
def api_patch_unit(unit_id):
    """Save an edited translation. Member+ to save; Leader+ required to approve.

    Body: {"english_text": str, "approve": bool (optional), "revision_type": str (optional), "note": str (optional)}
    - approve=true,  text unchanged from baseline → status=approved, no revision written
    - approve=true,  text changed from baseline   → status=revised,  revision written, approved_by set
    - approve=false (default)                     → status=in_review, work-in-progress save
    """
    if not can_edit_existing():
        return jsonify({"error": "Member role or higher required"}), 403

    data = request.get_json() or {}
    if "english_text" not in data:
        return jsonify({"error": "english_text is required"}), 400
    new_text = (data.get("english_text") or "").strip()
    approve  = bool(data.get("approve"))

    if approve and not is_leader():
        return jsonify({"error": "Leader role or higher required to approve"}), 403

    try:
        result = supabase.table("trans_units").select("*").eq("id", unit_id).execute()
        if not result.data:
            return jsonify({"error": "Unit not found"}), 404
        unit = result.data[0]
    except Exception as exc:
        return jsonify({"error": f"Database error: {exc}"}), 500

    baseline = (unit.get("english_final") or unit.get("english_draft") or "").strip()
    changed  = new_text != baseline
    modifier = session.get("user_email", "")

    updates = {
        "english_final":    new_text,
        "reviewed_by":      modifier,
        "last_modified_by": modifier,
        "last_modified_at": _now_iso(),
    }
    if approve:
        updates["status"]      = "revised" if changed else "approved"
        updates["approved_by"] = modifier
    else:
        updates["status"] = "in_review"

    if changed and approve:
        try:
            r_did = supabase.rpc("next_display_id", {
                "p_prefix": "R", "p_seq_name": "seq_trans_revisions_display"
            }).execute().data
            supabase.table("trans_revisions").insert({
                "display_id":     r_did,
                "unit_id":        unit_id,
                "chinese_text":   unit.get("chinese_text") or "",
                "english_before": baseline,
                "english_after":  new_text,
                "revision_type":  data.get("revision_type") or "other",
                "note":           data.get("note") or "",
                "revised_by":     modifier,
            }).execute()
        except Exception as exc:
            return jsonify({"error": f"Database error writing revision: {exc}"}), 500

    try:
        upd = supabase.table("trans_units").update(updates).eq("id", unit_id).execute()
        if not upd.data:
            return jsonify({"error": "Unit not found"}), 404
    except Exception as exc:
        return jsonify({"error": f"Database error: {exc}"}), 500

    if changed:
        write_audit(
            unit.get("display_id", ""), unit.get("chinese_text") or "", modifier, session.get("user_name", ""),
            "translation_approved" if approve else "translation_saved",
            field_changed="english_final", old_value=baseline, new_value=new_text,
        )

    return jsonify(upd.data[0])
