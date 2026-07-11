import os
import re
import json
import anthropic

ENTITY_TYPES   = ['人名', '地名', '寺院', '宗派', '書名典籍', '佛菩薩尊號', '概念術語', '其他']
SUBJECT_FIELDS = ['教義', '戒律', '禪修', '因明', '儀軌法物', '稱謂教職', '歷史事項', '文學藝術', '其他']


def generate_term_data(chinese_term, context="", notes="",
                       source_content_chinese="", source_content_english="", trans_known=""):
    """Return (pinyin, pali, sanskrit, t1, t2, t3) via a single Claude call."""
    ai = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    ctx_parts = []
    if source_content_chinese: ctx_parts.append(f"Source passage (Chinese): {source_content_chinese}")
    if source_content_english: ctx_parts.append(f"Source passage (English): {source_content_english}")
    if context:                ctx_parts.append(f"Additional context: {context}")
    if trans_known:            ctx_parts.append(f"Known translation: {trans_known}")
    context_hint = ("\n" + "\n".join(ctx_parts)) if ctx_parts else ""
    notes_hint   = f"\nTranslator notes: {notes}" if notes else ""
    known_hint   = (
        f"\nNote: \"{trans_known}\" is already recorded as a known translation. "
        "Generate 3 distinct alternatives that differ meaningfully from it."
        if trans_known else ""
    )
    response = ai.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=800,
        messages=[{
            "role": "user",
            "content": f"""You are an expert in Buddhist studies and Chinese Buddhist terminology.
For the Chinese Buddhist term below, provide exactly the following fields.
Reply in this exact format with no extra text or explanation:

PINYIN: [Mandarin romanization with tone marks]
PALI: [Pali equivalent, or blank if none exists]
SANSKRIT: [Sanskrit equivalent, or blank if none exists]
TRANSLATION1: [English translation option 1]
TRANSLATION2: [English translation option 2]
TRANSLATION3: [English translation option 3]

Term: {chinese_term}{context_hint}{notes_hint}{known_hint}"""
        }]
    )
    parsed = {}
    for line in response.content[0].text.strip().splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            parsed[key.strip()] = val.strip()
    return (
        parsed.get("PINYIN", ""),
        parsed.get("PALI", ""),
        parsed.get("SANSKRIT", ""),
        parsed.get("TRANSLATION1", ""),
        parsed.get("TRANSLATION2", ""),
        parsed.get("TRANSLATION3", ""),
    )


def generate_missing_translations(chinese, pinyin, context, notes,
                                   trans_known, trans_other1, trans_other2,
                                   count, existing_translations=None):
    """Generate 1–3 distinct English translation options for empty/unlocked slots."""
    ai = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    ctx_parts = []
    if pinyin:       ctx_parts.append(f"Romanization (Pinyin): {pinyin}")
    if trans_known:  ctx_parts.append(f"Known translation: {trans_known}")
    if trans_other1: ctx_parts.append(f"Member suggestion 1: {trans_other1}")
    if trans_other2: ctx_parts.append(f"Member suggestion 2: {trans_other2}")
    if context:      ctx_parts.append(f"Source context: {context}")
    if notes:        ctx_parts.append(f"Translator notes: {notes}")
    ctx_str = "\n".join(ctx_parts)
    labels  = "\n".join(
        f"TRANSLATION{i+1}: [distinct English translation option {i+1}]"
        for i in range(count)
    )

    exclusion_line = ""
    if existing_translations:
        non_empty = [t for t in existing_translations if t and t.strip()]
        if non_empty:
            quoted = "; ".join(f'"{t}"' for t in non_empty)
            exclusion_line = (
                f"\nDo not use any of these existing translations: {quoted}. "
                "Provide only new, distinct alternatives that are meaningfully different.\n"
            )

    response = ai.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=400,
        messages=[{"role": "user", "content": f"""You are an expert in Buddhist studies and Chinese Buddhist terminology.
Provide {count} distinct English translation option(s) for the Chinese Buddhist term below.{exclusion_line}
Reply ONLY in this exact format with no extra text:

{labels}

Term: {chinese}
{ctx_str}"""}]
    )
    parsed = {}
    for line in response.content[0].text.strip().splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            parsed[key.strip()] = val.strip()
    return [parsed.get(f"TRANSLATION{i+1}", "") for i in range(count)]


def find_known_translation(chinese_term, chinese_paragraph, english_paragraph):
    """Return the verbatim English phrase in english_paragraph that translates chinese_term.
    Validates the result is an actual substring; returns "" if not found or not verifiable."""
    ai = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    response = ai.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        messages=[{
            "role": "user",
            "content": f"""You are an expert in Buddhist studies and Chinese Buddhist terminology.
A translator is reviewing a Chinese Buddhist text and needs to locate how a specific term is rendered in the existing English translation.

Chinese term: {chinese_term}
Chinese paragraph (context for how the term is used): {chinese_paragraph}
English paragraph (the translation of the above): {english_paragraph}

Find the English phrase in the English paragraph that translates the Chinese term "{chinese_term}".
The phrase MUST be copied verbatim from the English paragraph — do not paraphrase, summarise, or invent.
If you cannot identify a confident verbatim match, reply with NOT_FOUND.

Reply in this exact format with no other text:
TRANSLATION: [verbatim phrase copied from the English paragraph, or NOT_FOUND]"""
        }]
    )
    for line in response.content[0].text.strip().splitlines():
        if line.startswith("TRANSLATION:"):
            _, _, val = line.partition(":")
            val = val.strip()
            if val and val != "NOT_FOUND" and val in english_paragraph:
                return val
            return ""
    return ""


def group_sentences_by_topic(sentences: list) -> list:
    """Group sentences by topic for translation coherence.

    Input:  [{"text": str, "is_long_sentence": bool}, ...]
    Output: [[0,1], [2], [3,4,5]]  — index lists per group.

    On any failure returns each sentence as its own group (safe fallback).
    """
    if not sentences:
        return []
    fallback = [[i] for i in range(len(sentences))]
    if len(sentences) == 1:
        return fallback
    try:
        ai = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        numbered = "\n".join(f"[{i}] {s['text']}" for i, s in enumerate(sentences))
        response = ai.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            messages=[{
                "role": "user",
                "content": f"""你是一位佛學翻譯助理。以下是從同一段落拆分出的句子，請根據主題相關性將它們分組，使每組合併後成為一個連貫的翻譯單元。

每組理想長度為 1–4 句。語意緊密、敘述同一主題的句子應歸為同一組。

句子清單：
{numbered}

請只以 JSON 陣列格式回覆，不要有任何其他文字或 markdown 標記。格式：[[索引,...],...]
例：[[0,1],[2],[3,4,5]]"""
            }]
        )
        raw = response.content[0].text.strip()
        raw = re.sub(r'^```[a-z]*\n?', '', raw).rstrip('`').strip()
        groups = json.loads(raw)
        # Validate all indices present exactly once
        seen = set()
        for g in groups:
            for idx in g:
                if not isinstance(idx, int) or idx < 0 or idx >= len(sentences):
                    return fallback
                if idx in seen:
                    return fallback
                seen.add(idx)
        if seen != set(range(len(sentences))):
            return fallback
        return groups
    except Exception:
        return fallback


def classify_term(term: dict) -> dict:
    """Classify a Buddhist term into entity_type and subject_field.

    Returns {"entity_type": str, "subject_field": str,
             "confidence": float 0-1, "reasoning": str}.
    Values are guaranteed to be within the allowed candidate lists.
    """
    ai = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    chinese = term.get("chinese", "")
    pinyin  = term.get("pinyin",  "")
    context = term.get("context", "")
    notes   = term.get("notes",   "")

    entity_list  = "、".join(ENTITY_TYPES)
    subject_list = "、".join(SUBJECT_FIELDS)

    ctx_parts = []
    if pinyin:  ctx_parts.append(f"拼音：{pinyin}")
    if context: ctx_parts.append(f"語境：{context}")
    if notes:   ctx_parts.append(f"備注：{notes}")
    ctx_str = ("\n" + "\n".join(ctx_parts)) if ctx_parts else ""

    response = ai.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        messages=[{
            "role": "user",
            "content": f"""你是一位佛學術語分類助手。請根據以下佛學詞彙資訊，為其分配 entity_type 和 subject_field。

詞彙：{chinese}{ctx_str}

entity_type 候選值（只能選其中一個，不得自創）：{entity_list}
說明：「概念術語」是預設大類（教義概念、修行方法等）；其餘為專有名詞細分。

subject_field 候選值（只能選其中一個，不得自創）：{subject_list}
說明：若 entity_type 為專有名詞類（人名、地名、寺院、宗派、書名典籍、佛菩薩尊號），subject_field 可填「其他」。

請只以 JSON 格式回覆，不要有任何其他文字或 markdown 標記：
{{"entity_type": "...", "subject_field": "...", "confidence": 0到1之間的小數, "reasoning": "一句話說明分類理由"}}"""
        }]
    )

    raw = response.content[0].text.strip()
    # Strip markdown code fences if present
    raw = re.sub(r'^```[a-z]*\n?', '', raw).rstrip('`').strip()

    result = json.loads(raw)

    if result.get("entity_type") not in ENTITY_TYPES:
        result["entity_type"] = "其他"
    if result.get("subject_field") not in SUBJECT_FIELDS:
        result["subject_field"] = "其他"
    result["confidence"] = float(result.get("confidence", 0.5))
    result["reasoning"]  = str(result.get("reasoning", ""))
    return result
