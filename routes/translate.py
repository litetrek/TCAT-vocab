from functools import wraps
from flask import Blueprint, jsonify, request, session
from auth import is_logged_in, can_access_translation_module
from db import supabase
from segmenter import decode, split_paragraphs, detect_section_type, segment_paragraph

translate_bp = Blueprint("translate", __name__)

MAX_FILE_SIZE = 2 * 1024 * 1024  # 2 MB


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


# ── POST /api/trans/books ─────────────────────────────────────────────────────

@translate_bp.route("/api/trans/books", methods=["POST"])
@_require_translation
def api_import_book():
    """Upload a .txt file → segment → INSERT trans_books/chapters/units atomically."""
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
        return jsonify({"error": "Cannot decode file — please use UTF-8, GB18030, or Big5"}), 400

    title = request.form.get("title", "").strip() or f.filename
    created_by = session.get("user_email", "")

    # ── Segment the file ─────────────────────────────────────────────────────
    paragraphs = split_paragraphs(text)
    if not paragraphs:
        return jsonify({"error": "No content found in file"}), 400

    # Build chapter list (one chapter per paragraph block).
    # Each paragraph → chapter; units are the sentences within it.
    chapters = []
    for ch_idx, para in enumerate(paragraphs):
        section_type = detect_section_type(para)
        sentences = segment_paragraph(para)
        units = [
            {
                "paragraph_index": 0,
                "unit_order": i + 1,
                "chinese_text": s["text"],
                "is_long_sentence": s["is_long_sentence"],
            }
            for i, s in enumerate(sentences)
            if s["text"]
        ]
        if not units:
            continue
        chapters.append({
            "chapter_index": ch_idx,
            "title": para[:40].split("。")[0] if para else f"段落 {ch_idx + 1}",
            "section_type": section_type,
            "units": units,
        })

    if not chapters:
        return jsonify({"error": "No translatable content found after segmentation"}), 400

    # ── Single atomic RPC ────────────────────────────────────────────────────
    try:
        result = supabase.rpc("import_trans_book", {
            "p_title": title,
            "p_created_by": created_by,
            "p_chapters": chapters,
        }).execute()
    except Exception as exc:
        return jsonify({"error": f"Database error: {exc}"}), 500

    data = result.data
    return jsonify({
        "book_display_id": data.get("display_id"),
        "chapter_count":   data.get("chapter_count"),
        "unit_count":      data.get("unit_count"),
    }), 201


# ── GET /api/trans/books ──────────────────────────────────────────────────────

@translate_bp.route("/api/trans/books", methods=["GET"])
@_require_translation
def api_list_books():
    """Return all active books with per-status unit counts (single GROUP BY query)."""
    try:
        result = supabase.rpc("list_trans_books", {}).execute()
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    return jsonify(result.data)


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
    """Return all units in a chapter ordered by paragraph_index, unit_order."""
    try:
        result = (
            supabase.table("trans_units")
            .select("id,display_id,paragraph_index,unit_order,chinese_text,status,is_long_sentence")
            .eq("chapter_id", chapter_id)
            .order("paragraph_index")
            .order("unit_order")
            .execute()
        )
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    return jsonify(result.data)
