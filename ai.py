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


def explain_term_context(chinese, pinyin="", pali="", sanskrit="", context="", notes="",
                         source_zh="", source_en="", entity_type="", known_trans=""):
    """Return a bilingual (English + Chinese) Buddhist doctrinal gloss for a Chinese term
    (ephemeral UI helper)."""
    ai = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    meta = []
    if pinyin:       meta.append(f"Pinyin: {pinyin}")
    if pali:         meta.append(f"Pali: {pali}")
    if sanskrit:     meta.append(f"Sanskrit: {sanskrit}")
    if entity_type:  meta.append(f"Entity type: {entity_type}")
    if known_trans:  meta.append(f"Known translation: {known_trans}")
    if source_zh:    meta.append(f"Source passage (Chinese): {source_zh}")
    if source_en:    meta.append(f"Source passage (English): {source_en}")
    if context:      meta.append(f"Additional context: {context}")
    if notes:        meta.append(f"Translator notes: {notes}")
    meta_block = ("\n".join(meta) + "\n") if meta else ""

    response = ai.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1500,
        messages=[{
            "role": "user",
            "content": f"""You are an expert in Buddhist studies and Chinese Buddhist terminology.
Write a short bilingual doctrinal gloss for the Chinese Buddhist term below to help translators —
one version in English, then the same content in Chinese.

Requirements:
- About 2–4 short paragraphs or short bullet sections covering: (1) core meaning / gloss, (2) doctrinal or textual usage, (3) related concepts if helpful.
- The English section must be English only (no Chinese, except when quoting the term itself once). The Chinese section must be written in Chinese (繁體中文), not a literal word-for-word translation of the English — write it naturally for a Chinese-reading translator.
- Use the metadata when provided. Do not invent specific sutra citations or page references.
- Be clear and practical for translators; avoid marketing fluff.

Term: {chinese}
{meta_block}
Reply in exactly this format, with no other preamble or title line:

── English ──
<english gloss>

── 中文 ──
<chinese gloss>"""
        }]
    )
    return (response.content[0].text or "").strip()


def generate_glossary_entry(chinese, pinyin="", pali="", sanskrit="", known_trans="", book_title=""):
    """Return a short bilingual (English + Chinese) glossary entry for a Chinese Buddhist term,
    written for a general reader of a published book's glossary appendix — not the longer,
    translator-facing doctrinal gloss produced by explain_term_context()."""
    ai = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    meta = []
    if pinyin:       meta.append(f"Pinyin: {pinyin}")
    if pali:         meta.append(f"Pali: {pali}")
    if sanskrit:     meta.append(f"Sanskrit: {sanskrit}")
    if known_trans:  meta.append(f"Known translation: {known_trans}")
    if book_title:   meta.append(f"Appears in book: {book_title}")
    meta_block = ("\n".join(meta) + "\n") if meta else ""

    response = ai.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=600,
        messages=[{
            "role": "user",
            "content": f"""You are writing a glossary entry for the appendix of a published book on
Chinese Buddhism, aimed at general readers (not translators or scholars).

Requirements:
- One concise paragraph in English (2-4 sentences), then the same entry naturally written in
  Chinese (繁體中文) — not a literal word-for-word translation.
- Dictionary/glossary style: define the term plainly and give just enough context for a reader
  to understand it when they meet it in the text. No section headers, no bullet points.
- Use the metadata when provided. Do not invent specific sutra citations or page references.

Term: {chinese}
{meta_block}
Reply in exactly this format, with no other preamble or title line:

── English ──
<english entry>

── 中文 ──
<chinese entry>"""
        }]
    )
    return (response.content[0].text or "").strip()


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


_TRANSLATE_SYSTEM = (
    "You are an expert translator of Chinese Buddhist texts — Vajrayana and Chinese Buddhist "
    "teaching literature — into English, writing for a scholarly but accessible readership.\n"
    "- Be faithful to the meaning of the source; do not add content that is not in it.\n"
    "- Write natural, readable English rather than a word-for-word rendering.\n"
    "- Where it helps the English, split a long Chinese sentence into several English sentences.\n"
    "- Use the REQUIRED TERMINOLOGY, adapted grammatically to the sentence as its rules allow.\n"
    "- Translate only the target sentence; any surrounding text is context."
)


def _rendering_options(t: dict) -> list:
    """The acceptable English options of one constraint term (";"-separated parts)."""
    parts = [p.strip() for p in (t.get("english") or "").split(";")]
    return [p for p in parts if p]


_ZH_DIGITS = {"零": 0, "〇": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
              "六": 6, "七": 7, "八": 8, "九": 9}
# "一 ", "二、", "三．", "（四）", "(五)" at the start of a unit
_HEADING_RE = re.compile(r"^\s*(?:[（(]\s*([一二三四五六七八九十〇零]{1,3})\s*[）)]\s*"
                         r"|([一二三四五六七八九十〇零]{1,3})\s*(?:[、．.]\s*|\s+))(?=\S)")


def _zh_number(numeral: str) -> int:
    """一 → 1, 十 → 10, 十二 → 12, 二十三 → 23 (up to 99)."""
    if "十" not in numeral:
        return _ZH_DIGITS.get(numeral, 0) if len(numeral) == 1 else 0
    tens, _, ones = numeral.partition("十")
    return (_ZH_DIGITS.get(tens, 0) if tens else 1) * 10 + (_ZH_DIGITS.get(ones, 0) if ones else 0)


def heading_number(chinese_text: str):
    """Section number if the unit starts with a Chinese numeral heading marker, else None."""
    m = _HEADING_RE.match(chinese_text or "")
    if not m:
        return None
    return _zh_number(m.group(1) or m.group(2)) or None


def build_translate_prompt(chinese_text: str, term_constraints: list = None,
                           context_before: str = "", context_after: str = "",
                           is_long_sentence: bool = False,
                           style_rules: list = None,
                           similar_examples: list = None,
                           paragraph_text: str = "",
                           missing_terms: list = None) -> dict:
    """The sentence-translation prompt, shared by every engine (see translate_unit).

    Returns {"system": str, "user": str}. missing_terms (retry only) lists required
    renderings the previous draft left out.
    """
    style_hint = ""
    if style_rules:
        lines = []
        for r in style_rules:
            cat = r.get("category", "")
            rule = r.get("rule_text", "")
            if not rule:
                continue
            line = f"- [{cat}] {rule}"
            ex_before = r.get("example_before", "")
            ex_after  = r.get("example_after", "")
            if ex_before and ex_after:
                line += f' (e.g. "{ex_before}" → "{ex_after}")'
            lines.append(line)
        if lines:
            style_hint = "\n\nStyle guide — house rules to follow:\n" + "\n".join(lines)

    example_hint = ""
    if similar_examples:
        lines = []
        for ex in similar_examples:
            zh = ex.get("chinese", "")
            en = ex.get("english", "")
            if zh and en:
                lines.append(f"中文: {zh} → English: {en}")
        if lines:
            example_hint = (
                "\n\nSimilar past translations (for tone/style reference only"
                " — do not copy verbatim unless the source text is identical):\n"
                + "\n".join(lines)
            )

    term_hint = ""
    if term_constraints:
        lines = []
        for t in term_constraints:
            if not (t.get("chinese") and t.get("english")):
                continue
            if t.get("alternatives"):
                opts = " / ".join(f'"{o}"' for o in _rendering_options(t))
                lines.append(f"- {t['chinese']} → one of {opts} (choose the alternative that fits the context)")
            else:
                lines.append(f'- {t["chinese"]} → "{t["english"]}"')
        if lines:
            term_hint = (
                "\n\nREQUIRED TERMINOLOGY — reviewed by the translation team. Keep each term's key "
                "words, diacritics and any parenthetical gloss, but adapt the rendering grammatically "
                "to the sentence:\n"
                "- Capitalisation follows the sentence: capitalise a term only at the start of a "
                "sentence or heading. Never carry a glossary entry's leading capital into the middle "
                "of a sentence (\"A lesser teaching\" → \"a lesser teaching\" mid-sentence). Proper "
                "nouns, \"Dharma\", \"Buddha\" and Sanskrit names keep their capitals as given.\n"
                "- Verbs take the tense and form the sentence needs (transmit → transmitted / "
                "transmitting); nouns may be singular or plural.\n"
                "- Articles (a / an / the) may be added, dropped or changed.\n"
                "- Do not bend the sentence's grammar just to fit a rendering's exact wording.\n"
                "- Where a rendering lists usages such as (noun) / (verb), use the one that fits; "
                "those labels themselves are not part of the translation.\n" + "\n".join(lines)
            )

    context_hint = ""
    if paragraph_text:
        context_hint += (
            "\n\nThe paragraph this sentence belongs to (context only — translate only the "
            f"target sentence):\n{paragraph_text}"
        )
    if context_before:
        context_hint += f"\n\nPrevious sentence (context only — do not translate this): {context_before}"
    if context_after:
        context_hint += f"\n\nNext sentence (context only — do not translate this): {context_after}"

    split_hint = ""
    if is_long_sentence:
        split_hint = (
            "\n\nThis is a long sentence. If it reads more naturally in English as two or "
            "more shorter sentences, split it. Also return split_map: a list of "
            "{\"zh\": \"...\", \"en\": \"...\"} pairs showing which portion of the original "
            "Chinese text corresponds to each English sentence (the zh portions together "
            "should cover the whole original sentence)."
        )

    heading_hint = ""
    section = heading_number(chinese_text)
    if section:
        heading_hint = (
            f"\n\nThis unit is a section heading, section number {section}: the leading Chinese "
            "numeral is the section marker. Translate the rest as a heading (concise, no final full "
            f"stop), not as a sentence, and begin the English with \"{section}. \". Do not use list "
            "numbers anywhere else."
        )

    retry_hint = ""
    if missing_terms:
        lines = "\n".join(f'- {m["chinese"]} → "{m["english"]}"' for m in missing_terms)
        retry_hint = (
            "\n\nIMPORTANT: a previous draft of this sentence did not use these required "
            "renderings (or dropped their parenthetical gloss). Use them this time, adapted "
            f"grammatically as above:\n{lines}"
        )

    user = (
        f"{style_hint}{example_hint}{term_hint}{context_hint}{split_hint}{heading_hint}{retry_hint}\n\n"
        f"TARGET SENTENCE — translate this: {chinese_text}\n\n"
        "Reply ONLY with a JSON object, no other text or markdown fences:\n"
        "{\"english\": \"the English translation\", \"reasoning\": [\"...\", ...], \"split_map\": null or "
        "[{\"zh\": \"...\", \"en\": \"...\"}, ...]}\n"
        "reasoning: 2–4 short notes (each under 25 words) for the human translator — the key "
        "term choices, any restructuring or sentence split, and any ambiguity in the Chinese and "
        "how you resolved it. Do not restate the translation."
    ).lstrip()
    return {"system": _TRANSLATE_SYSTEM, "user": user}


# Parentheticals that label a usage rather than gloss the term: not required in the output.
_USAGE_LABELS = {"noun", "verb", "adj", "adjective", "adverb", "n", "v"}


def _norm(text: str) -> str:
    """Lower-case, punctuation removed, whitespace collapsed (diacritics kept)."""
    text = re.sub(r"[^\w\s]", " ", (text or "").lower())
    return re.sub(r"\s+", " ", text).strip()


_ARTICLES = {"a", "an", "the"}

# Irregular forms: any word in a group matches any other in the same group.
_IRREGULAR_GROUPS = [
    "be is are was were been being am", "have has had having", "do does did done doing",
    "teach teaches taught teaching", "give gives gave given giving", "take takes took taken taking",
    "see sees saw seen seeing", "go goes went gone going", "come comes came coming",
    "become becomes became becoming", "speak speaks spoke spoken speaking",
    "arise arises arose arisen arising", "bring brings brought bringing",
    "seek seeks sought seeking", "think thinks thought thinking", "fall falls fell fallen falling",
    "know knows knew known knowing", "hold holds held holding", "make makes made making",
    "say says said saying", "hear hears heard hearing", "leave leaves left leaving",
    "lead leads led leading", "write writes wrote written writing", "bear bears bore borne born bearing",
    "abide abides abode abiding", "understand understands understood understanding",
    "child children", "man men", "woman women", "person people",
]
_IRREGULAR = {w: set(g.split()) for g in _IRREGULAR_GROUPS for w in g.split()}


def _word_forms(w: str) -> set:
    """w plus its regular plural / verb forms and any irregular forms."""
    forms = {w} | _IRREGULAR.get(w, set())
    if not w.isalpha() or len(w) < 2:
        return forms
    forms |= {w + "s", w + "es", w + "ed", w + "ing"}
    if w.endswith("e"):
        forms |= {w + "d", w[:-1] + "ing"}
    if w.endswith("y") and len(w) > 2 and w[-2] not in "aeiou":
        forms |= {w[:-1] + "ies", w[:-1] + "ied"}
    if len(w) >= 3 and w[-1] not in "aeiouwxy" and w[-2] in "aeiou" and w[-3] not in "aeiou":
        forms |= {w + w[-1] + "ed", w + w[-1] + "ing"}           # transmit → transmitted
    # a glossary entry that is already inflected also matches its base form
    for suf in ("ies", "es", "s", "ed", "ing"):
        if w.endswith(suf) and len(w) > len(suf) + 2:
            forms.add(w[:-len(suf)])
    return forms


def _phrase_in(phrase: str, hay: str) -> bool:
    """Whether normalized phrase occurs in normalized hay as whole words, allowing
    inflections (transmit → transmitted, being → beings, teach → taught) and
    articles added, dropped or changed (transmit the Dharma → transmit Dharma)."""
    words = [w for w in phrase.split() if w not in _ARTICLES]   # articles never required
    if not words:
        return False
    article = r"(?:(?:a|an|the)\s+)?"
    parts = ["(?:" + "|".join(re.escape(f) for f in sorted(_word_forms(w), key=len, reverse=True)) + ")"
             for w in words]
    pattern = r"(?<!\w)" + (r"\s+" + article).join(parts) + r"(?!\w)"
    return re.search(pattern, hay) is not None


def check_term_compliance(english: str, term_constraints: list) -> list:
    """Required renderings missing from english.

    Tolerant of legitimate grammatical adaptation: case, punctuation, articles
    (a / an / the added, dropped or changed), plural and verb inflections incl.
    common irregulars. Any ";"-separated option counts. Usage labels such as
    (noun) are not required. A parenthetical gloss is checked separately: main
    part present but gloss absent → "partial": True ("gloss dropped").
    Returns [{"chinese", "english", "term_id", "partial"}].
    """
    hay = _norm(english)
    missing = []
    for t in term_constraints or []:
        options = _rendering_options(t)
        if not options:
            continue
        full_hit = partial_hit = False
        for opt in options:
            glosses = [g for g in re.findall(r"\(([^)]*)\)", opt) if _norm(g) not in _USAGE_LABELS]
            main = re.sub(r"\([^)]*\)", " ", opt)
            main = re.sub(r"^\s*to\s+", "", main, flags=re.I)  # infinitive marker of a verb rendering
            if not _phrase_in(_norm(main), hay):
                continue
            if all(_phrase_in(_norm(g), hay) for g in glosses):
                full_hit = True
                break
            partial_hit = True
        if not full_hit:
            missing.append({"chinese": t["chinese"], "english": t["english"],
                            "term_id": t.get("term_id", ""), "partial": partial_hit})
    return missing


def _missing_score(missing: list) -> float:
    """Lower is better: a partial match (gloss dropped) counts half."""
    return sum(0.5 if m["partial"] else 1 for m in missing)


TRANSLATE_MAX_TOKENS = 2000  # visible output: long sentences + split_map
_REASONING_HEADROOM  = 6000  # both top models think before answering; that counts against the same limit
_TRANSLATE_TIMEOUT_S = 90


def _translate_with_claude(prompt: dict, model: str, usage: dict = None) -> str:
    ai = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"), timeout=_TRANSLATE_TIMEOUT_S)
    response = ai.messages.create(
        model=model,
        max_tokens=TRANSLATE_MAX_TOKENS + _REASONING_HEADROOM,
        system=prompt["system"],
        messages=[{"role": "user", "content": prompt["user"]}],
    )
    _add_usage(usage, response.usage.input_tokens, response.usage.output_tokens)
    # Newer models may return a thinking block before the text block.
    return "".join(b.text for b in response.content if getattr(b, "type", "") == "text")


def _translate_with_openai(prompt: dict, model: str, usage: dict = None) -> str:
    import openai
    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"), timeout=_TRANSLATE_TIMEOUT_S)
    # GPT-5.x are reasoning models: Responses API, max_output_tokens (not max_tokens)
    # covers reasoning + visible output.
    response = client.responses.create(
        model=model,
        instructions=prompt["system"],
        input=prompt["user"],
        max_output_tokens=TRANSLATE_MAX_TOKENS + _REASONING_HEADROOM,
    )
    if response.usage:
        _add_usage(usage, response.usage.input_tokens, response.usage.output_tokens)
    return response.output_text


def _add_usage(usage: dict, input_tokens: int, output_tokens: int) -> None:
    """Accumulate token counts across the draft and any retry (output includes reasoning)."""
    if usage is not None:
        usage["calls"] += 1
        usage["input_tokens"] += input_tokens or 0
        usage["output_tokens"] += output_tokens or 0


def _parse_translation(raw: str) -> tuple:
    raw = re.sub(r'^```[a-z]*\n?', '', raw.strip()).rstrip('`').strip()
    parsed = json.loads(raw)
    split_map = parsed.get("split_map")
    reasoning = parsed.get("reasoning") or []
    if isinstance(reasoning, str):
        reasoning = reasoning.splitlines()
    reasoning = [str(r).strip().lstrip("-•* ").strip()[:300] for r in reasoning if str(r).strip()][:4] \
        if isinstance(reasoning, list) else []
    return (str(parsed.get("english", "")).strip(),
            (split_map if isinstance(split_map, list) else None),
            reasoning)


def translate_unit(chinese_text: str, term_constraints: list = None,
                    context_before: str = "", context_after: str = "",
                    is_long_sentence: bool = False,
                    style_rules: list = None,
                    similar_examples: list = None,
                    engine: str = "openai",
                    paragraph_text: str = "") -> dict:
    """Draft an English translation for one trans_unit (T3; engines F2; compliance F3).

    term_constraints: [{"chinese", "english", "alternatives"?, "term_id"?}, ...] —
    reviewed glossary terms found in chinese_text; their renderings are required.
    paragraph_text: the whole paragraph the sentence belongs to (context only).
    context_before / context_after: adjacent sentences outside that paragraph.
    is_long_sentence: if True, also ask for a split_map.
    engine: "openai" (OPENAI_TRANSLATION_MODEL) or "claude" (CLAUDE_TRANSLATION_MODEL).

    After the draft, every required rendering is checked (check_term_compliance);
    if any is missing the sentence is translated once more with the missing terms
    named, and the draft with fewer missing terms is kept.

    Returns {"english", "split_map", "reasoning", "model", "missing_terms", "retried", "usage"}, plus
    "error": str when the draft failed (english is then "").
    Never raises — provider errors are logged and returned as "error".
    """
    from config import CLAUDE_TRANSLATION_MODEL, OPENAI_TRANSLATION_MODEL

    if engine == "openai":
        model, key_name, call = OPENAI_TRANSLATION_MODEL, "OPENAI_API_KEY", _translate_with_openai
    else:
        model, key_name, call = CLAUDE_TRANSLATION_MODEL, "ANTHROPIC_API_KEY", _translate_with_claude

    usage  = {"calls": 0, "input_tokens": 0, "output_tokens": 0}
    result = {"english": "", "split_map": None, "reasoning": [], "model": model, "missing_terms": [], "retried": False,
              "usage": usage}
    if not chinese_text or not chinese_text.strip():
        return result
    if not os.getenv(key_name):
        result["error"] = ("OpenAI" if engine == "openai" else "Anthropic") + " key not configured"
        return result

    args = dict(term_constraints=term_constraints, context_before=context_before,
                context_after=context_after, is_long_sentence=is_long_sentence,
                style_rules=style_rules, similar_examples=similar_examples,
                paragraph_text=paragraph_text)
    try:
        english, split_map, reasoning = _parse_translation(call(build_translate_prompt(chinese_text, **args), model, usage))
        if not english:
            result["error"] = f"{model} returned an empty translation"
            return result
        missing = check_term_compliance(english, term_constraints)
    except Exception as exc:
        print(f"[translate_unit] engine={engine} model={model} error: {type(exc).__name__}: {exc}", flush=True)
        result["error"] = f"{model} failed: {type(exc).__name__}"
        return result

    if missing:
        result["retried"] = True
        try:
            prompt2 = build_translate_prompt(chinese_text, missing_terms=missing, **args)
            english2, split_map2, reasoning2 = _parse_translation(call(prompt2, model, usage))
            missing2 = check_term_compliance(english2, term_constraints) if english2 else None
            if missing2 is not None and _missing_score(missing2) < _missing_score(missing):
                english, split_map, reasoning, missing = english2, split_map2, reasoning2, missing2
        except Exception as exc:  # the first draft still stands
            print(f"[translate_unit] engine={engine} model={model} retry error: {type(exc).__name__}: {exc}", flush=True)

    result.update(english=english, split_map=split_map, reasoning=reasoning, missing_terms=missing)
    return result


_SG_CATEGORIES = ("honorifics", "proper_nouns", "sentence_splitting", "tone", "other")


def suggest_style_rules(notes: list, chinese_text: str = "", english_text: str = "",
                        existing_rules: list = None) -> dict:
    """G3: turn translator notes on one sentence into 0–2 Style Guide rule proposals.

    notes: note texts. existing_rules: active rules, so the AI neither repeats nor contradicts them.
    Returns {"rules": [{"category", "rule_text", "example_before", "example_after"}],
             "term_notes": [str], "comment": str}, or {"error": str}. Never raises.
    Notes about how one glossary term should be rendered come back in term_notes (they
    belong in the term's entry, not in a style rule).
    """
    from config import CLAUDE_TRANSLATION_MODEL
    if not os.getenv("ANTHROPIC_API_KEY"):
        return {"error": "Anthropic key not configured"}
    existing = "\n".join(f"- [{r.get('category', '')}] {r.get('rule_text', '')}"
                         for r in (existing_rules or []) if r.get("rule_text")) or "(none)"
    note_lines = "\n".join(f"- {n}" for n in notes if n and n.strip())
    prompt = (
        "Translators of Chinese Buddhist texts into English left these notes on one sentence.\n"
        "Turn them into reusable house-style rules that a future AI translation of OTHER sentences "
        "should follow.\n\n"
        f"Chinese sentence: {chinese_text}\nCurrent English: {english_text}\n\n"
        f"Translator notes:\n{note_lines}\n\n"
        f"Existing style rules (do not repeat or contradict these):\n{existing}\n\n"
        "Guidelines:\n"
        "- Propose 0, 1 or 2 rules. Propose none if the notes only concern this one sentence.\n"
        "- Each rule is one imperative sentence a translator could apply elsewhere, under 40 words.\n"
        "- example_before / example_after: a short English phrase showing the change, or empty.\n"
        f"- category: one of {', '.join(_SG_CATEGORIES)}.\n"
        "- A note that only says how one specific Chinese term should be rendered goes in "
        "term_notes instead (as 'term → rendering'), not in rules.\n"
        "- comment: one short sentence for the team on what you did (e.g. why no rule).\n\n"
        "Reply ONLY with a JSON object, no other text or markdown fences:\n"
        '{"rules": [{"category": "...", "rule_text": "...", "example_before": "", "example_after": ""}], '
        '"term_notes": [], "comment": "..."}'
    )
    try:
        ai = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"), timeout=_TRANSLATE_TIMEOUT_S)
        response = ai.messages.create(
            model=CLAUDE_TRANSLATION_MODEL,
            max_tokens=TRANSLATE_MAX_TOKENS + _REASONING_HEADROOM,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = "".join(b.text for b in response.content if getattr(b, "type", "") == "text")
        raw = re.sub(r'^```[a-z]*\n?', '', raw.strip()).rstrip('`').strip()
        parsed = json.loads(raw)
    except Exception as exc:
        print(f"[suggest_style_rules] error: {type(exc).__name__}: {exc}", flush=True)
        return {"error": f"AI suggestion failed: {type(exc).__name__}"}
    rules = []
    for r in (parsed.get("rules") or [])[:2]:
        text = str(r.get("rule_text") or "").strip()
        if not text:
            continue
        cat = str(r.get("category") or "other").strip()
        rules.append({
            "category":       cat if cat in _SG_CATEGORIES else "other",
            "rule_text":      text[:500],
            "example_before": str(r.get("example_before") or "").strip()[:300],
            "example_after":  str(r.get("example_after") or "").strip()[:300],
        })
    return {"rules": rules,
            "term_notes": [str(t).strip() for t in (parsed.get("term_notes") or []) if str(t).strip()][:5],
            "comment": str(parsed.get("comment") or "").strip()[:300]}


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
