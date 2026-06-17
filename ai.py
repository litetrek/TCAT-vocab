import os
import anthropic


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
