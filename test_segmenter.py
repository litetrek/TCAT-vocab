"""
test_segmenter.py
=================
Unit tests for segmenter.segment_paragraph().

Run with:  pytest test_segmenter.py -v
"""

import pytest
from segmenter import segment_paragraph, detect_section_type


# ─────────────────────────────────────────────────────────────────────────────
# Standard test cases from the T1 design document
# ─────────────────────────────────────────────────────────────────────────────

def test_quote_protection_single_unit():
    """
    TC-1 (design doc): Terminator inside 「」 must NOT split the sentence.
    The full passage must be returned as exactly ONE translation unit.
    Failure condition: splitting at 「平等的。」 is incorrect.
    """
    text = (
        "處處都對眾生說：「我是一個普通人，是與你們一樣平等的。」"
        "帕母儘管如此態度，但是我們和高僧們認為她就是當今在世真正的佛菩薩。"
    )
    result = segment_paragraph(text)
    assert len(result) == 1, (
        f"Expected 1 unit (quote-protected), got {len(result)}: {[r['text'] for r in result]}"
    )


def test_long_sentence_flag():
    """
    TC-2 (design doc): A single-period long parallel sentence must be marked
    is_long_sentence=True.
    """
    text = (
        "自由女神像的消失是神秘的，她的缺席令人震驚，"
        "她的重要性無可替代，她的意義深遠，她的影響廣大，她的地位崇高。"
    )
    result = segment_paragraph(text)
    assert len(result) == 1, f"Expected 1 unit, got {len(result)}"
    assert result[0]["is_long_sentence"] is True, (
        "Expected is_long_sentence=True for long parallel sentence"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Additional boundary cases
# ─────────────────────────────────────────────────────────────────────────────

def test_plain_short_sentence_not_long():
    """Short sentence with no internal punctuation is not flagged as long."""
    text = "她來了。"
    result = segment_paragraph(text)
    assert len(result) == 1
    assert result[0]["text"] == "她來了。"
    assert result[0]["is_long_sentence"] is False


def test_multiple_sentences_no_quotes():
    """Three plain sentences split correctly into three units."""
    text = "第一句話。第二句話。第三句話。"
    result = segment_paragraph(text)
    assert len(result) == 3
    assert result[0]["text"] == "第一句話。"
    assert result[1]["text"] == "第二句話。"
    assert result[2]["text"] == "第三句話。"


def test_terminator_exclamation_and_question():
    """！ and ？ also act as hard boundaries."""
    text = "這是什麼？真的嗎！對啊。"
    result = segment_paragraph(text)
    assert len(result) == 3
    assert result[0]["text"] == "這是什麼？"
    assert result[1]["text"] == "真的嗎！"
    assert result[2]["text"] == "對啊。"


def test_quote_speech_continues_after_close_quote():
    """
    When 「...。」 is followed by more text, the protected 。 inside the quote
    must NOT split the sentence. The entire passage is ONE unit.
    This verifies: close-quote handler never flushes; only depth-0 terminator does.
    """
    text = "他說：「好的。」然後離去。"
    result = segment_paragraph(text)
    assert len(result) == 1, (
        f"Expected 1 unit, got {len(result)}: {[r['text'] for r in result]}"
    )
    assert result[0]["text"] == text


def test_close_suffix_rule_depth_zero():
    """
    收尾規則: when a terminator fires at depth=0 and a close-quote immediately
    follows, the close-quote is absorbed into that sentence (e.g. unbalanced
    or outermost-level close in mid-text).
    """
    # 。 fires at depth=0 here; 」 immediately follows → belongs to that sentence
    text = "她走了。」旁白結束。"
    result = segment_paragraph(text)
    assert len(result) == 2
    assert result[0]["text"] == "她走了。」"
    assert result[1]["text"] == "旁白結束。"


def test_nested_quotes_no_inner_split():
    """
    Nested 「『』」: terminators inside both quote levels are protected.
    Only the depth-0 terminator at the very end causes a split.
    """
    text = "師父說：「她叫做『普通人。』這就是答案。」大家點頭。"
    result = segment_paragraph(text)
    assert len(result) == 1, (
        f"Expected 1 unit, got {len(result)}: {[r['text'] for r in result]}"
    )
    assert result[0]["text"] == text


def test_ellipsis_as_boundary():
    """Full-width ellipsis (……) at depth=0 counts as a sentence boundary."""
    text = "她沉默了……然後說話了。"
    result = segment_paragraph(text)
    assert len(result) == 2
    assert result[0]["text"] == "她沉默了……"
    assert result[1]["text"] == "然後說話了。"


def test_no_terminator_returns_one_unit():
    """Text with no terminator returns as a single remainder unit."""
    text = "這段話沒有句號所以算一個單元"
    result = segment_paragraph(text)
    assert len(result) == 1
    assert result[0]["text"] == text


def test_long_by_char_count():
    """Sentences longer than 45 characters are flagged long regardless of commas."""
    text = "這是一個非常非常非常非常非常非常非常非常非常非常非常非常長的句子沒有逗號但是超過四十五個字。"
    result = segment_paragraph(text)
    assert len(result) == 1
    assert result[0]["is_long_sentence"] is True


# ─────────────────────────────────────────────────────────────────────────────
# Section-type detection
# ─────────────────────────────────────────────────────────────────────────────

def test_section_type_editorial():
    assert detect_section_type("本社按：本期主題……") == "editorial"
    assert detect_section_type("編者按　本書收錄……") == "editorial"


def test_section_type_preface():
    assert detect_section_type("譯者序\n本書是……") == "preface"


def test_section_type_postscript():
    assert detect_section_type("跋 本書完成之際……") == "postscript"


def test_section_type_body_default():
    assert detect_section_type("佛法是慈悲的……") == "body"
