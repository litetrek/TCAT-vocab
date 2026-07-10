"""
segmenter.py
============
Chinese-text segmentation module for the T-CAT translation pipeline.

Public API:
    decode(data: bytes) -> str | None
    split_paragraphs(text: str) -> list[str]
    detect_section_type(paragraph: str) -> str
    segment_paragraph(text: str) -> list[dict]

segment_paragraph() returns:
    [{"text": str, "is_long_sentence": bool}, ...]

Split rules:
  1. Hard boundaries: 。！？……(full-width) at quote depth == 0.
  2. Quote protection: terminators inside 「」『』"" are NOT boundaries.
     A quote-depth counter (increments on open, decrements on close) tracks nesting.
  3. Close-quote suffix (收尾規則): when a depth-0 terminator is immediately
     followed by a close-quote, the close-quote is absorbed into that sentence.
  4. Long-sentence flag: internal punctuation (，、；) count > 3 OR char count > 45.

This module is pure algorithm — no database writes (T2 scope).
"""

import re

# ── Encoding detection ────────────────────────────────────────────────────────

def decode(data: bytes) -> "str | None":
    """Try UTF-8 → GB18030 → Big5; return None if all fail."""
    for enc in ("utf-8", "gb18030", "big5"):
        try:
            return data.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return None


# ── Paragraph splitting ───────────────────────────────────────────────────────

def split_paragraphs(text: str) -> list:
    """Split on blank lines (same logic as extract.py _split_paragraphs)."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    blocks = re.split(r"\n{2,}", text)
    return [b.strip() for b in blocks if b.strip()]


# ── Section-type detection ────────────────────────────────────────────────────

_SECTION_PREFIXES = {
    "本社按": "editorial",
    "編者按": "editorial",
    "譯者序": "preface",
    "作者序": "preface",
    "序言":   "preface",
    "前言":   "preface",
    "跋":     "postscript",
    "後記":   "postscript",
}


def detect_section_type(paragraph: str) -> str:
    """Return section_type string based on paragraph-opening keywords."""
    stripped = paragraph.lstrip()
    for prefix, stype in _SECTION_PREFIXES.items():
        if stripped.startswith(prefix):
            return stype
    return "body"


# ── Sentence segmentation ─────────────────────────────────────────────────────

_TERMINATORS  = frozenset("。！？…")
_OPEN_QUOTES  = frozenset("「『“")   # 「 『 "
_CLOSE_QUOTES = frozenset("」』”")   # 」 』 "

_INTERNAL_PUNCTUATION = frozenset("，、；")
_LONG_COMMA_THRESHOLD = 3
_LONG_CHAR_THRESHOLD  = 45


def _is_long(text: str) -> bool:
    internal = sum(1 for ch in text if ch in _INTERNAL_PUNCTUATION)
    return internal > _LONG_COMMA_THRESHOLD or len(text) > _LONG_CHAR_THRESHOLD


def _flush(buf: list, sentences: list) -> None:
    text = "".join(buf).strip()
    if text:
        sentences.append({"text": text, "is_long_sentence": _is_long(text)})
    buf.clear()


def segment_paragraph(text: str) -> list:
    """
    Split a Chinese paragraph into translation units.

    Returns: [{"text": str, "is_long_sentence": bool}, ...]
    """
    sentences: list = []
    buf: list = []
    depth = 0
    i = 0
    n = len(text)

    while i < n:
        ch = text[i]

        # ── Open-quote: increase nesting depth ─────────────────────────────
        if ch in _OPEN_QUOTES:
            depth += 1
            buf.append(ch)
            i += 1
            continue

        # ── Close-quote: decrease nesting depth, append, never flush ───────
        # Terminators inside quotes are protected (depth > 0 → not split).
        # When the outermost quote closes, the depth returns to 0 and the
        # text continues accumulating until the next depth-0 terminator.
        if ch in _CLOSE_QUOTES:
            if depth > 0:
                depth -= 1
            buf.append(ch)
            i += 1
            continue

        # ── Full-width ellipsis ─────────────────────────────────────────────
        if ch == "…":
            buf.append(ch)
            # Absorb consecutive ellipsis dots (…… = two U+2026)
            while i + 1 < n and text[i + 1] == "…":
                i += 1
                buf.append(text[i])
            i += 1
            if depth == 0:
                # 收尾規則: absorb trailing close-quotes into this sentence
                while i < n and text[i] in _CLOSE_QUOTES:
                    if depth > 0:
                        depth -= 1
                    buf.append(text[i])
                    i += 1
                _flush(buf, sentences)
            continue

        # ── Standard terminators (。！？) ───────────────────────────────────
        if ch in _TERMINATORS and depth == 0:
            buf.append(ch)
            i += 1
            # 收尾規則: absorb immediately-following close-quotes
            while i < n and text[i] in _CLOSE_QUOTES:
                if depth > 0:
                    depth -= 1
                buf.append(text[i])
                i += 1
            _flush(buf, sentences)
            continue

        buf.append(ch)
        i += 1

    # Remaining text without a trailing terminator
    _flush(buf, sentences)
    return sentences
