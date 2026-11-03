# T-CAT Translation Fix — Claude Code Prompts (Nov 2026)

Background: Greg compared T-CAT's translations of 入法門論 sentences 1–7 against ChatGPT and found (1) ChatGPT's English was clearly better, and (2) the underlined in-page vocabulary links do not reflect the reviewed glossary. Investigation found:

- All AI calls use `claude-haiku-4-5-20251001` (smallest model), including sentence translation (`ai.translate_unit`, `routes/translate.py` `AI_MODEL_NAME`).
- Underlines (`trdHighlightKnownTerms` in `templates/index.html`, fed by `GET /api/trans/known-terms`) match **every** term in the DB (all books, unreviewed, single characters, inactive), tooltip = `trans_known || trans1` (never the reviewed Final), and on duplicates the first (older, unreviewed) entry wins.
- AI constraints (`terms_repo.get_translation_constraint_terms`) use Known **before** Final, so a reviewed Final is overridden by a Known value.
- Haiku often ignores the glossary constraints (e.g. 傳法 → "taught the Dharma" though Final = "transmit the Dharma"; dropped "(Bardo in Tibetan)" for 中陰).

Run the stages **in order**, one prompt per Claude Code session. Test each stage before starting the next.

---

## Stage F1 — Glossary links and constraint priority

```
Read PROGRESS.md, claude.md, routes/translate.py, repositories/terms_repo.py and the translation-workspace JavaScript in templates/index.html (trdFetchKnownTerms, trdHighlightKnownTerms, trdHandleTermClick) before changing anything.

Goal: the underlines and hover text in the Books translation workspace must reflect the reviewed glossary of the book being translated, and AI translation must give the reviewed Final priority over Known.

1. Constraint priority — repositories/terms_repo.py get_translation_constraint_terms():
   - Change the English chosen per term to: Final text (translation_first, when `final` is set) FIRST; only if there is no Final, fall back to translation_known.
   - When falling back to translation_known and it contains several options separated by ";" , pass the whole string but mark it as alternatives (return an extra key "alternatives": true) so the prompt can say "choose the one that fits".
   - Keep the existing inactive-term exclusion and the prefer_source_id (book's own vocabulary wins) behaviour.
   - Among duplicates linked to the book, prefer status='reviewed', then entries with a Final, then the rest.

2. Book-scoped known terms — GET /api/trans/known-terms:
   - Accept an optional ?book_id= query parameter. Add a helper that resolves a book's source id from book_id (same logic as _get_book_source_id, which works from chapter_id: trans_books.source_id, else sources.source_name == book title). Refactor so both share one function.
   - With book_id: return only active (not inactive) terms linked to that book's source via term_sources. Without book_id: keep current behaviour (backward compatible; the extraction module uses its own endpoint and must not change).
   - Deduplicate by Chinese text using the same preference order as step 1 (reviewed > has Final > other).
   - Add fields to each item: "final_text" (translation_first when final is set, else ""), "in_book": true/false.
   - Single-character terms (len(chinese) == 1) are included only if status == 'reviewed'.

3. Frontend — templates/index.html:
   - trdFetchKnownTerms() must pass the current book id (_transCurrentBookId) and re-fetch when the book changes.
   - Tooltip priority: final_text → trans_known → trans1. Prefix the tooltip so the translator knows what they see: "Final: …", "Known: …", or "AI suggestion: …".
   - Keep colour classes: reviewed (term-reviewed), has known (term-has-known).
   - Add a small checkbox in the translation workspace toolbar: "Show all vocabulary" (default OFF). When ON, fetch without book_id (old behaviour) and render non-book terms with a faint dotted underline class (term-other-book). Remember the setting in localStorage (wrap in try/catch).
   - Clicking an underlined term must open the same (deduplicated) term the tooltip came from.

4. Do not change: the extraction module (/api/extract/known-terms), the vocabulary AI functions, the database schema.

Acceptance tests (write them down in PROGRESS.md and run what you can with the Flask test client against Supabase):
   - 入法門論 (book id 10, source id 5): 輪迴 resolves to T002904 "Samsara (the cycle of rebirth)", 無始 → T002874 "without beginning", 中陰 → T003074 "intermediate state (Bardo in Tibetan)", 修行 → T002894, 成就 constraint English = "attainment" (Final), not the Known value.
   - 學佛 and 道 are NOT underlined for book 10 (not linked / single unreviewed character); 法 IS underlined (reviewed T002861).
   - get_translation_constraint_terms(prefer_source_id=5) returns "transmit the Dharma" for 傳法.
   - Toggling "Show all vocabulary" restores the old full underline set.

Finish: update PROGRESS.md (what changed, test results, anything not verified in a browser), commit with a clear message. Do not deploy.
```

**You test:** open 入法門論 → a chapter → hover 輪迴, 無始, 中陰, 傳法; confirm 學佛/道 are not underlined; toggle "Show all vocabulary".

---

## Stage F2 — Two selectable translation engines (Claude and OpenAI)

```
Read PROGRESS.md, ai.py (translate_unit), routes/translate.py (api_translate_unit, AI_MODEL_NAME), config.py, .env.example and the translation-workspace UI in templates/index.html. Stage F1 is complete.

Goal: the translator can choose the engine for sentence translation: Claude or OpenAI. Vocabulary functions (generate_term_data, generate_missing_translations, explain_term_context, generate_glossary_entry, find_known_translation, classify_term) stay on Claude Haiku — do not change them. group_sentences_by_topic also stays on Haiku.

1. Configuration (.env.example + config.py, documented with comments; never commit real keys):
   - CLAUDE_TRANSLATION_MODEL (default "claude-opus-5-5")
   - OPENAI_TRANSLATION_MODEL (default "gpt-5.6-sol")
   - DEFAULT_TRANSLATION_ENGINE (default "claude"; allowed: claude | openai)
   - OPENAI_API_KEY is already used for embeddings — reuse it.

2. ai.py:
   - Split translate_unit() into (a) a prompt builder that returns the exact same prompt text as today, and (b) a provider call.
   - Add translate_unit(..., engine="claude"). engine="claude" → anthropic messages.create with CLAUDE_TRANSLATION_MODEL. engine="openai" → the openai SDK (already in requirements.txt, openai==2.33.0) with OPENAI_TRANSLATION_MODEL. Check the installed SDK for the correct call and token-limit parameter for this model family (newer models use max_completion_tokens / the Responses API rather than max_tokens) — verify, don't guess.
   - Raise the output limit to ~2000 tokens (long sentences + split_map).
   - Return {"english", "split_map", "model"} where model is the actual model string used.
   - Keep the never-raise behaviour, but log the provider error (print with flush=True) so failures are visible in the server log instead of silently returning "".
   - If the chosen engine's API key is missing, return an error the route can show ("OpenAI key not configured").

3. routes/translate.py api_translate_unit:
   - Accept JSON body {"engine": "claude"|"openai"}; default DEFAULT_TRANSLATION_ENGINE; reject other values with 400.
   - Store the real model string in trans_units.ai_model (replace the hard-coded AI_MODEL_NAME).
   - Include "engine" and "model" in the JSON response and in the existing [translate_unit] log line.
   - Check request time: Opus/GPT top models are slower than Haiku. Look at how the app is deployed (vercel.json, api/index.py, index.cgi, DEPLOYMENT.md) and set/document a function timeout that allows ~60 s if the platform supports it.

4. UI (templates/index.html), translation workspace:
   - Engine selector next to the AI Translate button(s): "Claude" / "OpenAI". Remember choice in localStorage (try/catch). Send it with every AI Translate / regenerate request.
   - Show the model used under each unit's translation (small grey text from ai_model, e.g. "claude-opus-5-5"), so reviewers know which engine wrote a draft.
   - If the server reports a missing key, show a toast.

5. No schema changes (ai_model column already exists).

Acceptance tests: with both keys set, translate unit 354 (book 10, "一 先說大小法 又看邪與正") once with each engine through the Flask test client — both return non-empty English and ai_model reflects the engine. Note: this overwrites english_final on that unit; unit 354/353/352 are in_review — use a test unit or restore english_final afterwards, and say which you did. With OPENAI_API_KEY unset, engine=openai returns a clear error. Update PROGRESS.md and commit. Do not deploy.
```

**You test:** add the OpenAI key to `.env` (and the server env), translate one unit with each engine, check the model label.

---

## Stage F3 — Better prompt and glossary compliance check

```
Read PROGRESS.md, ai.py (translate_unit prompt builder), routes/translate.py (_match_constraint_terms, _get_context, api_translate_unit). Stages F1–F2 are complete.

Goal: drafts follow the reviewed glossary, read naturally, and any glossary term the AI missed is flagged.

1. Prompt (shared by both engines):
   - System-style instructions: expert translator of Chinese Buddhist texts (Vajrayana / Chinese Buddhist teaching literature) into English for a scholarly but accessible readership; faithful to meaning, natural English, split long Chinese sentences into several English sentences where it helps; do not add content not in the source.
   - Glossary block, clearly separated: "REQUIRED TERMINOLOGY — reviewed by the translation team. Use these renderings exactly, including any parenthetical gloss, capitalisation and diacritics." For items flagged alternatives=true: "choose the alternative that fits the context".
   - Context: instead of only the previous/next sentence, give the full paragraph the unit belongs to (all units with the same chapter_id + paragraph_index, in order), marked "context only — translate only the target sentence". Keep previous/next unit across paragraph boundaries as today.
   - Keep style-guide rules and RAG examples as they are.

2. Compliance check after each draft (both engines):
   - For each constraint term found in the Chinese, check the English output contains the required rendering (case-insensitive; ignore punctuation differences; for alternatives, any one alternative counts; for a rendering with a parenthetical, the part before the parenthesis counts as a partial match).
   - If any required term is missing, retry ONCE with an added instruction listing the missing terms. Keep the better result (fewer missing terms).
   - Return "missing_terms": [{"chinese","english"}] in the API response. No schema change: do not store it in the DB.

3. UI: after AI Translate, if missing_terms is non-empty, show amber chips under the unit: "⚠ 傳法 → transmit the Dharma not used". Clicking a chip opens that term.

Acceptance tests (Flask test client, do not overwrite in_review units — copy their Chinese into a throwaway call of translate_unit directly):
   - 傳法 sentence (unit 353 text) → output contains "transmit the Dharma" or it is reported in missing_terms.
   - 中陰 sentence (unit 351 text) → "(Bardo in Tibetan)" kept or reported.
   - Log retries in the [translate_unit] line (retried=yes/no, missing=N).
Update PROGRESS.md and commit. Do not deploy.
```

---

## Stage F4 — Blind comparison for Greg (no DB writes)

```
Read PROGRESS.md and ai.py. Stages F1–F3 are complete.

Create scripts/compare_engines.py:
   - Input: --book-id (default 10) and --units (default "354,353,352,351,348,349,350" — 入法門論 sentences 1–7 in reading order).
   - For each unit: load chinese_text and existing english_final; build the same constraints / context / style rules / RAG examples that api_translate_unit uses (reuse the functions, do not duplicate logic); call translate_unit with engine=claude and engine=openai.
   - Must NOT write anything to Supabase.
   - Output 1: docs/compare_<date>.md — per sentence: the Chinese, then "Version A" and "Version B" (random order per sentence), plus the list of required glossary terms and any missing_terms per version.
   - Output 2: docs/compare_<date>_key.md — which version is which engine/model per sentence (kept separate so the reviewers can judge blind).
   - Print token usage / elapsed time per call at the end.
Run it once, show me the summary, update PROGRESS.md, commit.
```

**You do:** send `compare_<date>.md` to Greg and Weiya (not the key file).

---

## Later (after Thrangu shares material)

If Thrangu sends his ChatGPT custom instructions, uploaded files, memory or exported chat history, a follow-up stage can: (a) fold his instructions into the shared translation prompt / style guide, and (b) import his past Chinese→English sentence pairs into `trans_revisions` with embeddings so they are used as RAG examples.
