import re
from flask import Blueprint, jsonify, request
from auth import is_logged_in

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


@extract_bp.route("/api/extract/upload", methods=["POST"])
def api_extract_upload():
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

    paragraphs = [
        {"index": i, "chinese": zh_paras[i], "english": en_paras[i]}
        for i in range(len(zh_paras))
    ]

    return jsonify({"paragraphs": paragraphs, "count": len(paragraphs)})
