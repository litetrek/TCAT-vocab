# PROGRESS — T-CAT Buddhist Vocabulary Tool

Snapshot document. Overwritten at each stage boundary to reflect current state.

---

## Project Overview

**T-CAT** is a collaborative web app for a small team translating Chinese Buddhist texts
into English. Translators add terms, Claude AI generates Pinyin / Pali / Sanskrit plus
three English translation options, and a Leader or Admin directly finalises the best option
with a single click.

- **Live URL:** https://app.cyber-tech.com
- **GitHub repo:** https://github.com/litetrek/TCAT-vocab (private)
- **Local path:** `C:\Users\vince\code-projects\buddhist-vocab`

---

## Tech Stack

| Layer    | Technology |
|----------|-----------|
| Backend  | Python 3.10 / Flask |
| Auth     | Google OAuth 2.0 (Authlib) |
| Database | **Supabase Postgres** (migrating from Google Sheets — T0 in progress) |
| AI       | Anthropic Claude (`claude-haiku-4-5-20251001`) |
| Frontend | Vanilla JS + HTML/CSS (single-page, no framework) |
| Hosting  | GreenGeeks shared hosting, Apache, CGI via `index.cgi` |
| Deploy   | GitHub Actions → FTPS → GreenGeeks |

---

## File Structure

```
buddhist-vocab/
├── app.py                      # Flask entry point, Google OAuth, route registration
├── config.py                   # Constants, sheet column maps, utility functions
├── archive/sheets.py.bak       # Google Sheets client — archived (T0-5); no longer imported by app
├── db.py                       # supabase-py client: create_client() using SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY
├── ai.py                       # Anthropic Claude AI generation (Pinyin, Pali, Sanskrit, translations)
├── auth.py                     # Session helpers: is_logged_in, is_admin, is_leader, can_access_translation_module
├── segmenter.py                # Chinese sentence segmentation — T1; decode/split_paragraphs/segment_paragraph
├── routes/
│   ├── __init__.py
│   ├── terms.py                # /api/terms/* endpoints
│   ├── members.py              # /api/members/* endpoints
│   ├── sources.py              # /api/sources + /api/init endpoints
│   ├── extract.py              # /api/extract/* endpoints — Extraction module
│   └── translate.py            # /api/trans/* endpoints — Translation module (T2); guard: _require_translation
├── repositories/               # psycopg2 data-access layer — pure Postgres, no Sheets mirror
│   ├── __init__.py
│   ├── members_repo.py
│   ├── sources_repo.py
│   ├── terms_repo.py
│   ├── extraction_repo.py
│   └── audit_repo.py
├── migrations/
│   ├── 001_initial_schema.sql  # Full Postgres DDL — 11 tables per design guide
│   ├── 002_rpc_functions.sql   # next_display_id RPC + atomic write RPCs
│   ├── 003_romanization_plain.sql  # unaccent extension, trigger, backfill, index for romanization_plain
│   ├── 004_entity_subject_classification.sql  # entity_type / subject_field columns on terms
│   ├── 005_t1_translation_module.sql  # T1: five translation-module tables (idempotent IF NOT EXISTS)
│   ├── 006_t2_import_book_rpc.sql    # T2: import_trans_book + list_trans_books RPC functions
│   ├── 007_t2_1_sentence_map.sql     # T2.1: sentence_map column + trans_unit_drafts table
│   ├── 008_login_log.sql             # login_log table — records every successful login
│   ├── 009_ext_documents_source_id.sql  # ext_documents.source_id column
│   └── 010_dual_embeddings.sql       # T4.2: trans_revisions embedding_voyage/embedding_openai + find_similar_revisions_* RPCs
├── scripts/
│   ├── run_migration.py        # Applies 001_initial_schema.sql via DATABASE_URL / psycopg2
│   ├── run_migration_005.py    # T1: applies 005 + runs acceptance tests (insert/unique/fractional/cleanup)
│   ├── run_migration_006.py    # T2: applies 006 + runs 4 acceptance tests (import/list/section_type/cleanup)
│   ├── run_migration_007.py    # T2.1: applies 007 + 5 acceptance tests + T2 test data cleanup
│   ├── run_migration_010.py    # T4.2: applies 010 + acceptance tests (dual embedding columns, both RPCs)
│   ├── migrate_from_sheets.py  # T0-2: one-shot Sheets → Postgres migration
│   ├── migrate_extraction_only.py  # T0-4: re-migrate extraction data only
│   ├── backfill_classification.py  # Backfill entity_type/subject_field for unclassified terms
│   └── compare_embedding_providers.py  # T4.2: side-by-side Voyage vs OpenAI retrieval quality comparison
├── embeddings.py                # T4.2: get_voyage_embedding / get_openai_embedding / get_embeddings — best-effort, never raises
├── test_segmenter.py           # pytest tests for segmenter.py (15 cases, all passing)
├── static/
│   ├── Tcat-logo.png           # Primary logo (yellow-gold T with sparkle and swoosh)
│   ├── favicon.ico             # Multi-size ICO (16/32/48px) generated from Tcat-logo.png
│   ├── favicon.svg             # SVG redraw of logo design (used for modern browser tab icon)
│   ├── favicon-32x32.png       # 32×32 PNG
│   ├── favicon-512x512.png     # 512×512 PNG (PWA/Android)
│   └── apple-touch-icon.png    # 180×180 PNG (iOS home screen)
├── index.cgi                   # CGI entry point (shebang: venv310/bin/python3.10)
├── templates/
│   ├── index.html              # Main app UI — three top-level tabs: Vocabulary / Extraction / Translation (admin-only)
│   ├── login.html              # Google OAuth login page
│   └── denied.html             # Access denied (user not in Members sheet)
├── requirements.txt
├── import-template.csv         # CSV template for bulk term import
├── import/import1.csv          # First batch import data
├── sample_terms.csv            # Sample terms for reference
├── .env.example                # Template listing all required env vars (no real values)
├── credentials.example.json    # Template showing shape of Google service account JSON
├── .gitignore                  # Excludes credentials.json, .env, .env.*, venv, __pycache__
├── .github/
│   └── workflows/
│       └── deploy.yml          # GitHub Actions CI/CD deploy pipeline
├── README.md                   # Project overview, setup, deployment docs
├── DEPLOYMENT.md               # Pipeline docs, secret names, rollback procedure
└── PROGRESS.md                 # This file
```

**Never committed to git (server/local only):**
- `credentials.json` — Google service account private key
- `.env` — dev environment secrets (contains DATABASE_URL, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
- `.env.production` — production environment secrets (upload as `.env` on server)
- `.htaccess` — Apache rewrite rules (exists on server, managed manually)
- `venv/`, `venv310/` — Python virtual environments

---

## Supabase Database Schema (13 tables, all live)

**Project:** `TCAT-vocab` (id: `yvkadctkigkjtjmmxrqc`, region: us-west-1)
**Connection:** supabase-py HTTPS REST (port 443), `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` env vars

All tables use `id bigint generated always as identity` as internal PK and a `display_id`
text column (T000001 / D000001 / etc.) for human-facing IDs. Sequences are created for
each display_id to eliminate the race condition from the old Sheets "scan for max ID" pattern.

| Table | display_id prefix | Notes |
|---|---|---|
| `members` | — | email UNIQUE, role check constraint |
| `sources` | S000001 | |
| `terms` | T000001 | status check: pending/finalized; idx on chinese, status; **no longer has a `source` column** — see `term_sources` (2026-09-03) |
| `term_sources` | — | many-to-many terms↔sources; PK (term_id, source_id); both FKs ON DELETE CASCADE (2026-09-03) |
| `book_glossary_terms` | G000001 | Leader-curated, per-`trans_books` glossary; term_id/book_id FKs ON DELETE CASCADE; UNIQUE (book_id, term_id); status draft/reviewed (2026-09-03) |
| `audit_log` | — | ts timestamptz; term_id is text (no FK — historical rows may ref deleted terms) |
| `ext_documents` | D000001 | |
| `ext_paragraphs` | — | FK → ext_documents(id); UNIQUE (document_id, paragraph_index) |
| `trans_books` | B000001 | FK → sources(id); status: active/archived |
| `trans_chapters` | C000001 | FK → trans_books(id); section_type + status check constraints |
| `trans_units` | U000001 | unit_order numeric (fractional indexing); `sentence_map jsonb` (original sentence list, added T2.1) |
| `trans_unit_drafts` | — | `(chapter_id, paragraph_index)` unique; `draft_groups jsonb`; status: pending/ai_suggested/human_adjusted/confirmed |
| `trans_revisions` | R000001 | `embedding_voyage vector(1024)` + `embedding_openai vector(1536)` (T4.2 — replaced the original single `embedding vector(1536)` column) |
| `style_guide` | S000001 | active boolean; source_revision_ids bigint[]; CRUD live since T4.1 |
| `login_log` | — | email/name/role/logged_in_at; records every successful login |

pgvector extension enabled. `find_similar_revisions_voyage` / `find_similar_revisions_openai` RPC functions (migration 010) do the `<=>` cosine-distance ORDER BY query — PostgREST/supabase-py can't express that operator directly.

---

## Google Sheets Structure (source of truth until T0-4 cutover)

One Google Sheet with seven worksheets:

| Sheet | Key Columns |
|-------|------------|
| **Terms** | ID, Chinese, Pinyin, Pali, Sanskrit, Context, Category, Notes, Translation1–3, Final, Status, AddedBy, Timestamp, TranslationKnown, Source, TranslationFirst/Second, TranslationOther1/2, LastModifiedBy/Time, RomanizationPlain, SourceContentChinese/English |
| **Votes** | TermID, VoterEmail, ChosenTranslation *(deprecated — worksheet preserved but unused since Stage 3)* |
| **Members** | Email, Role, AddedBy, AddedAt, Name, ShortName |
| **Sources** | SourceID, SourceName, SourceType, Notes |
| **Audit_Log** | AuditID, Timestamp, TermID, TermChinese, UserEmail, UserName, ActionType, FieldChanged, OldValue, NewValue, Details |
| **ExtractionDocuments** | DocumentID, Title, SourceName, ParagraphCount, UploadedBy, UploadedAt, LastViewedIndex, Status |
| **ExtractionParagraphs** | DocumentID, ParagraphIndex, ChineseText, EnglishText |

**Service account:** `sheets-editor@warm-composite-494900-b0.iam.gserviceaccount.com`

---

## User Roles

| Role | Capabilities |
|------|-------------|
| **Viewer** | Read-only |
| **Depositor** | Add terms |
| **Member** | Add terms, edit fields, add terms |
| **Leader** | Member + set Final (First/Second) + reset finalization |
| **Admin** | Leader + manage members/sources + Init Sheets |

`SUPER_ADMIN_EMAIL` env var always grants admin regardless of the Members sheet.

---

## Environment Variables

All loaded from `.env` (local) or `.env` on the GreenGeeks server (production).
See `.env.example` for the full list with placeholder values.

| Variable | Purpose |
|----------|---------|
| `GOOGLE_CLIENT_ID` | OAuth 2.0 client ID |
| `GOOGLE_CLIENT_SECRET` | OAuth 2.0 client secret |
| `SECRET_KEY` | Flask session signing key |
| `ANTHROPIC_API_KEY` | Claude AI access |
| `SHEET_ID` | Google Sheet ID (kept until T0-5 cutover) |
| `SUPER_ADMIN_EMAIL` | Always-admin email address |
| `GOOGLE_REDIRECT_URI` | OAuth callback URL (differs dev vs prod) |
| `FLASK_ENV` | `development` or `production` |
| `PORT` | Local dev port (unused in CGI mode) |
| `SUPABASE_URL` | **Required by Flask app** — supabase-py REST client (HTTPS port 443) |
| `SUPABASE_SERVICE_ROLE_KEY` | **Required by Flask app** — service_role JWT, bypasses RLS (server-side only) |
| `DATABASE_URL` | Local scripts only (`scripts/migrate_from_sheets.py`); NOT used by Flask app |

---

## GreenGeeks Server Details

- **Host IP:** `108.163.242.106` (no public DNS hostname available for FTP)
- **Remote app dir:** `~/public_html/app.cyber-tech.com/`
- **Python interpreter:** `/home/dorjecha/public_html/app.cyber-tech.com/venv310/bin/python3.10`
- **Both `venv/` and `venv310/` exist on server** — only `venv310` is used (active env with all packages)
- **Protocol:** FTPS (explicit TLS) on port 21
- **SSH access:** Not confirmed/enabled — deployment uses FTPS only

---

## CI/CD Pipeline (GitHub Actions)

**Workflow:** `.github/workflows/deploy.yml`

- Triggers on: every push to `main`, or manually via **Actions → Run workflow**
- Deploys via: `SamKirkland/FTP-Deploy-Action@v4.3.5` over FTPS
- Excludes from sync: `.git*`, `.github/`, `.env*`, `credentials.json`,
  `README.md`, `claude.md`, `deploy_note.md`, `project-overview`, `project-revision`,
  `__pycache__/`, `*.pyc`
- Health check: `curl -s -L` to the live URL after deploy; fails loudly if not HTTP 200
- Logging: verbose (captures FTP command/response for debugging)

**GitHub Actions secrets required** (repo → Settings → Secrets and variables → Actions):

| Secret name | Value |
|-------------|-------|
| `FTP_HOST` | `108.163.242.106` |
| `FTP_USERNAME` | GreenGeeks FTP username |
| `FTP_PASSWORD` | GreenGeeks FTP password |
| `FTP_PORT` | Optional — defaults to 21 |
| `FTP_REMOTE_DIR` | `public_html/app.cyber-tech.com/` |
| `SITE_URL` | `https://app.cyber-tech.com` |

---

## Completed Stages

### Stage 1 — Application Build (pre-June 2026)
- Flask app with Google OAuth login
- Google Sheets as database (gspread, service account auth)
- Claude AI integration for term generation (Pinyin, Pali, Sanskrit, 3 translations)
- Role-based access: viewer / depositor / member / leader / admin
- Single-page frontend (vanilla JS, no framework)
- Bulk CSV import with AI fill-in
- Audit log for all changes
- CGI deployment via `index.cgi` on GreenGeeks, manual FTP uploads via FileZilla

### Stage 2 — Git + GitHub + CI/CD Pipeline (2026-06-16)
- Audited all local files for secrets before touching git
- Created `.gitignore` excluding all secrets and build artifacts
- Created `.env.example` and `credentials.example.json` as safe reference templates
- Initialized local git repo, committed 25 tracked files (no secrets staged)
- Renamed branch to `main`, pushed to private GitHub repo `litetrek/TCAT-vocab`
- Built GitHub Actions workflow: FTPS deploy + post-deploy health check
- Resolved FTPS "FIN packet" error (verbose logging confirmed connection, IP-based host required)
- Fixed `index.cgi` shebang pointing to wrong `venv/` path — corrected to `venv310/python3.10`
- Fixed health check to follow redirects (`curl -L`) since root URL redirects to `/login`
- **Pipeline confirmed working end-to-end** — green deploy on commit `804e56e`

### Stage 3 — Voting Removal (2026-06-16)
- Removed all voting functionality: `/api/vote` and `/api/unvote` endpoints deleted
- Removed vote-tallying from `GET /api/terms` (no longer fetches Votes worksheet at all)
- Removed vote-lock guard from `PATCH /api/terms/<id>` (all fields now freely editable)
- Removed `can_vote()` from auth.py; removed `VALID_VOTES`, `FIELD_TO_VOTE_KEY`, `VOTES_HEADER` from config.py
- Removed `get_votes_sheet()`, `recalculate_auto_selections()`, `_migrate_term_ids()` from sheets.py
- Removed Votes worksheet auto-creation from `ensure_headers()` (existing sheet preserved with historical data)
- Finalization is now a direct one-click action: Leader/Admin sees a "Set Final" button on each of the six translation candidates in the edit view
- Overview panel reduced to 2 stats: Total and Finalized
- Filter list reduced to: All Terms, Pending, Finalized
- Audit Log: no new `voted`/`vote_updated` rows written; historical rows remain and still render correctly

### Extraction Stage 1 — Paragraph Viewer (2026-06-16)
- Added a top-level two-tab bar: **Extraction** (default/active) and **Vocabulary**
- All existing Vocabulary UI (sidebar, list view, edit view, modals) unchanged — wrapped in `#vocab-view` container that shows when the Vocabulary tab is active
- New `routes/extract.py` blueprint registered in `app.py`:
  - `POST /api/extract/upload` — accepts `chinese_file` + `english_file` (.txt only, ≤500 KB each)
  - Decodes bytes: UTF-8 → GB18030 → Big5; clear JSON error if all fail
  - Splits text on blank-line boundaries; trims and drops empty blocks
  - Returns 400 with both paragraph counts if Chinese/English counts don't match
  - Returns `{ "paragraphs": [{index, chinese, english}, …], "count": N }` on success
  - Requires login; no role restriction beyond that
- New Extraction tab UI: source/book selector, file inputs, two side-by-side read-only panels, top+bottom navigator bars with Prev/Next/jump

### Extraction Stage 2 — Google Sheets Persistence + Resume (2026-06-16)
- **Replaced** `POST /api/extract/upload` with `POST /api/extract/documents`:
  - Accepts `title` (chapter/part label), `source_name` (book title), plus the two text files
  - Same validation as before; writes nothing to Sheets if validation fails
  - On success: generates DocumentID (`D000001` pattern, same as Terms `T000001`), appends one row to ExtractionDocuments, batch-appends all paragraphs to ExtractionParagraphs in a single API call (`append_rows`)
  - Returns `{ "document_id": ..., "paragraphs": [...], "count": N }`
- **Added** `GET /api/extract/documents` — returns all ExtractionDocuments rows sorted by SourceName then Title
- **Added** `GET /api/extract/documents/<id>/paragraphs` — returns paragraphs in index order plus LastViewedIndex
- **Added** `PATCH /api/extract/documents/<id>` — updates LastViewedIndex only
- All four endpoints require login; no additional role restriction
- **New Google Sheets worksheets** created by `ensure_headers()` (same init pattern as existing sheets):
  - **ExtractionDocuments**: DocumentID, Title, SourceName, ParagraphCount, UploadedBy, UploadedAt, LastViewedIndex, Status
  - **ExtractionParagraphs**: DocumentID, ParagraphIndex, ChineseText, EnglishText
- **Frontend changes** to Extraction tab:
  - "Source / Book" dropdown renamed to "Book / Source title" — same dropdown + free-text toggle as before
  - New "Chapter / part label" text input (`#ext-chapter-input`) added below source row
  - Document list section ("Previously Uploaded") appears above upload form on tab load, grouped by book title, each chapter showing title, paragraph count, last-viewed position, uploader, upload date, and a "Resume" button
  - Upload now POSTs to `/api/extract/documents`; stores returned `document_id` in JS state
  - "Resume" calls GET paragraphs endpoint and renders starting at LastViewedIndex
  - Every navigation event (Prev/Next/jump-to, both nav bars) fires a fire-and-forget PATCH to save progress
  - Document list auto-refreshes after upload or resume

### Extraction Stage 2b — Picker / Working Split (2026-06-16)
- Extraction tab restructured into two sub-views: **Picker** (upload + document list) and **Working** (paragraph navigator)
- Picker view shown on tab load; Working view shown after Upload or Resume
- `extShowWorking(sourceName, title)` transitions to Working view and fetches known terms
- `extShowPicker()` / `extSwitchDocument()` allow returning to the list or switching documents

### Extraction Stage 3 — Term Highlighting + Selection Candidate Modal (2026-06-16)
- **New endpoint** `GET /api/extract/known-terms`:
  - Reuses `get_terms_sheet()`; returns lightweight array: ID, Chinese, Pinyin, Pali, Sanskrit, TranslationKnown, Translation1–3
- **Frontend — paragraph highlighting**:
  - `extHighlightKnownTerms()`: greedy longest-match-first, `Uint8Array` claimed-character tracking, wraps matches in `<span class="term-known">` with hover tooltip
  - `.term-known` styled gold background tint + underline
- **Frontend — candidate modal** (`#ext-candidate-panel`):
  - `position: fixed` overlay anchored to `<body>` (direct child, not nested in `#ext-working`)
  - CSS selector is `#ext-candidate-panel` (ID, not class — class selector was a prior bug that broke fixed positioning)
  - `mouseup` on `#ext-text-zh` → `extHandleSelection()` → `extShowCandidatePanel()`
  - Exact match branch: "Already in database" badge + read-only field grid
  - New term branch: "New term — not yet in database" badge
  - Both branches include in-modal English passage block + editable Known Translation textarea
  - Text selected inside the modal English passage auto-fills the Known Translation input (selection always wins — no "only once" guard)
  - `extEnPassageHtml()` shared helper renders English passage + textarea + Find button for both branches
  - Escape key or ✕ button hides modal and clears browser selection

### Extraction Stage 4 — AI Find Translation (2026-06-16)
- **New `ai.py` function** `find_known_translation(chinese_term, chinese_paragraph, english_paragraph)`:
  - Prompts Claude to find a **verbatim substring** of the English paragraph that translates the Chinese term
  - Validates: result must be non-empty, not `NOT_FOUND`, and actually present in `english_paragraph` — returns `""` otherwise
  - Model: `claude-haiku-4-5-20251001`, `max_tokens=200`
- **New endpoint** `POST /api/extract/lookup`:
  - Accepts `chinese_term`, `chinese_paragraph`, `english_paragraph`
  - Returns `{ "suggested_translation": "..." }` (empty string if not found)
- **Frontend "Find Translation" button** (`extFindTranslation()`):
  - POSTs to `/api/extract/lookup` with current paragraph text
  - On match: fills Known Translation textarea; on no match: shows inline "No clear match" message
  - Button shown in both "new term" and "already in database" modal branches

### Extraction Stage 5 — Generate Translations + Save (2026-06-16)
- **New endpoint** `POST /api/extract/generate`:
  - Reuses existing `generate_term_data()` from `ai.py`
  - Returns `{ pinyin, pali, sanskrit, trans1, trans2, trans3 }`
- **New endpoint** `POST /api/extract/save`:
  - Server-side existence check (scans Terms sheet fresh each call — not trusting client state)
  - **Insert path** (term not in sheet): requires `can_create_term()` (depositor+); appends full 26-column row matching `api_add_term` in `terms.py` exactly; `Status="pending"`, `Final=""`
  - **Update path** (term exists): requires `can_edit_existing()` (member+); updates only `TranslationKnown`, `LastModifiedBy`, `LastModifiedTime`
  - Both paths write to Audit_Log via `write_audit()`
- **Frontend "Generate 3 AI Translations"** (`extGenerateTranslations()`):
  - POSTs to `/api/extract/generate`; populates `extGeneratedFields` state
  - Renders read-only Pinyin, Pali, Sanskrit, Translation 1–3 fields in `#ext-gen-fields`
- **Frontend "Save" button** (`extSaveTerm()`):
  - Requires generated fields to be present before enabling save
  - On success: shows result message, then after 900 ms hides modal, re-fetches known terms, re-renders paragraph (new term immediately appears highlighted)
  - Error displayed inline in modal (never alerts)

### Extraction Bugfix — Document List Empty on Initial Load (2026-06-17)
- **Root cause**: `extLoadDocumentList()` was only called from `switchTopTab('extraction')` (tab-click handler) and `extSwitchDocument()`. Since Extraction is the default active tab, the click handler never fires on first page load.
- **Fix**: Added `extLoadDocumentList()` to the page init block (alongside `loadTerms()`).
- No other startup gap found: `extPopulateSources()` is already called by `loadTerms()` internally; `extFetchKnownTerms()` is correctly triggered only when a document is opened.

### Extraction Enhancement — Two-Tone Term Highlighting (2026-06-17)
- Terms highlighted in the Chinese panel now use two distinct colors:
  - **Blue** underline + background tint (`.term-known.term-has-known`): term already has a Known Translation recorded
  - **Gold** underline + background tint (`.term-known`): term is in the database but has no Known Translation yet
- Implemented by storing `hasKnown: !!term.trans_known` on each segment in `extHighlightKnownTerms()` and applying the extra class conditionally

### Extraction Enhancement — English Panel Highlighting (2026-06-17)
- Corresponding translation phrases are now highlighted in the English panel to match the Chinese panel
- `extHighlightKnownTerms()` refactored to return `{ html, segs }` (was plain string); `segs` carries each matched term's best translation phrase (`trans_known` → `trans1` fallback) and `hasKnown` flag
- New `extHighlightEnglishTerms(text, segs)` function: same greedy longest-match-first algorithm as Chinese; searches for each phrase verbatim in the English text; skips phrases not found (no false highlights)
- English panel switched from `textContent` to `innerHTML`
- Same color coding as Chinese: blue for `trans_known` phrases, gold for `trans1` phrases

### Extraction Enhancement — Fixed-Height Scrollable Panels (2026-06-17)
- Chinese and English panels now have a fixed default height (520px) instead of expanding with content
- Each panel scrolls vertically within its fixed height (`overflow-y: auto` on `.ext-panel-text`)
- User can drag the resize handle (bottom-right corner of each panel) to make it taller or shorter (`resize: vertical` on `.ext-panel`)
- Panel label row stays fixed at top; only the text content scrolls (`display: flex; flex-direction: column` layout)
- Minimum height 160px prevents panels from being collapsed to nothing

### T0-1 — Supabase Schema (2026-07-09)
- Created `migrations/001_initial_schema.sql` — full DDL per `docs/T-CAT翻譯模組設計指南.md` appendix
- Created `scripts/run_migration.py` — applies the migration via `DATABASE_URL` / psycopg2-binary
- Applied migration to Supabase project `TCAT-vocab` via MCP; all 11 tables verified
- Dropped interim tables from earlier exploratory migration sessions (staged 1-6):
  `extraction_documents`, `extraction_paragraphs`, `votes` — all were empty
- Rebuilt 6 existing-system tables with correct design-guide schema:
  - `id bigint generated always as identity` as internal PK (was text display_id as PK)
  - `display_id text unique` for human-facing IDs
  - `audit_log.ts` (was `timestamp`); `ext_documents`/`ext_paragraphs` (was `extraction_*`)
- Created 5 new translation-module tables: `trans_books`, `trans_chapters`, `trans_units`,
  `trans_revisions`, `style_guide`
- pgvector extension enabled; display_id sequences created for all relevant tables
- **Note:** `repositories/` and `db.py` still use old supabase-py client names — rewritten in T0-3

### T0-2 — Data Migration (2026-07-09)
- Created `scripts/migrate_from_sheets.py` — full one-shot migration: gspread → Postgres
- Pre-flight: checks env vars, credentials.json, aborts if target tables non-empty (unless `--force`)
- Migrated 6 tables in FK order: members → sources → terms → audit_log → ext_documents → ext_paragraphs
- Key transforms: email lowercase, role normalized, `translation_1/2/3` → `translation1/2/3`, FK resolution for ext_paragraphs.document_id (display_id → internal bigint via RETURNING map)
- Votes (15 rows) exported to `backup/votes_export_20260709.csv` — not migrated (deprecated)
- Sequences calibrated: `seq_terms_display → 2844`, `seq_ext_documents_display → 2`
- Verification: row counts all match (2844 terms, 6 members, 5 sources, 49 audit, 2 docs, 36 paragraphs); 20-row spot-check on terms (26 cols) passed; all spot-checks passed
- **T0-2 驗收通過 — zero errors, zero skipped rows**

### T0-3 — Data Layer Rewrite (2026-07-09)
- **Connection method switched from psycopg2 TCP to supabase-py HTTPS REST** — GreenGeeks shared hosting blocks port 5432/6543; only HTTPS (443) works
- Rewrote `db.py`: supabase-py `create_client()` using `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` (service_role bypasses RLS; all 11 tables have RLS disabled)
- Created `migrations/002_rpc_functions.sql`:
  - `seq_sources_display` sequence (next → S000006)
  - `NOT VALID` CHECK constraint on `audit_log.action_type` (skips legacy rows with non-standard action types)
  - `next_display_id(p_prefix, p_seq_name)` — generates T000001 / D000001 / S000001 style IDs atomically
  - `update_term_field_with_audit`, `set_final_with_audit`, `reset_final_with_audit` — atomic term + audit_log writes in one transaction
  - `create_document_with_paragraphs` — atomic ext_documents + all ext_paragraphs in one transaction
- Rewrote all 5 repositories to use supabase-py REST; removed all Sheets mirror code
- `list_terms()`: paginated loop with `.range()` to bypass PostgREST 1000-row default limit (2844 rows require 3 pages)
- `create_term()` / `add_source()` / `create_document()`: use `next_display_id` RPC for race-free display ID generation
- `create_document()`: uses `create_document_with_paragraphs` RPC for atomic insert
- Column mapping preserved: `routes/` layer zero changes; all function signatures and return dict shapes unchanged
- RLS status: disabled on all 11 tables — service_role key required and used

### UI Polish — Favicon, Logo, Layout, Sidebar (2026-07-10)

#### Favicon & Logo
- Added `static/` directory with 5 favicon assets: `favicon.ico` (16/32/48), `favicon.svg`, `favicon-32x32.png`, `apple-touch-icon.png` (180px), `favicon-512x512.png`
- Added `<link rel="icon">` and `<link rel="apple-touch-icon">` tags to all three templates (`index.html`, `login.html`, `denied.html`)
- Replaced the `☸` dharma-wheel emoji in the header and login page with `<img class="wheel">` pointing to the favicon SVG
- Recolored SVG favicon from blue-purple gradient (`#2E3A87 → #5B6EF5`) to warm dark palette matching site header (`#1a1208 → #3d2a14`); icon strokes changed from white to cream `#e8dcc0`; spark changed from `#FFD24C` to site gold `#c9a84c`
- Replaced all favicon files with `Tcat-logo.png` (yellow-gold T with sparkle + swoosh): used Pillow to generate ICO, 32px, 180px, and 512px sizes; SVG redrawn to match design
- Added `?v=2` cache-busting to all favicon `<link>` tags to force browser cache invalidation
- Header logo and login page logo updated to use `Tcat-logo.png` directly

#### Database — Migration 003
- Created `migrations/003_romanization_plain.sql`:
  - `CREATE EXTENSION IF NOT EXISTS unaccent`
  - `set_romanization_plain()` trigger function — fires `BEFORE INSERT OR UPDATE OF pinyin`, sets `romanization_plain = lower(unaccent(pinyin))`
  - `DROP/CREATE TRIGGER trg_set_romanization_plain ON terms`
  - Backfill: `UPDATE terms SET romanization_plain = lower(unaccent(pinyin)) WHERE pinyin IS NOT NULL`
  - `CREATE INDEX idx_terms_romanization_plain ON terms (romanization_plain)`
- Applied via psycopg2 + `DATABASE_URL`; verified: `甘露 → pinyin=gānlù, romanization_plain=ganlu`
- No frontend changes needed: `_row_to_response()` already returned `romanization_plain`; frontend search (`getFilteredSorted()`) already included it in the haystack (line 893)

#### Layout Fixes
- Sidebar width reduced from 260px to 210px (`grid-template-columns: 260px 1fr` → `210px 1fr`)
- Added `min-width: 0` to `.main` to prevent flex/grid overflow squeezing the right content area
- Set Final button (`admin-pick-btn`) on mobile: changed `flex: 1 1 30%` → `flex: 0 1 auto; max-width: 140px` to prevent button from stretching full card width

#### Tab Order
- Vocabulary tab moved to the left of Extraction and set as the default active tab on login
- `vocab-view` now visible by default; `extraction-view` starts hidden; active class on Vocabulary button

#### Resizable & Collapsible Sidebar
- Sidebar restructured: outer `<aside class="sidebar">` is the non-scrolling positioning context; inner `<div class="sidebar-inner">` is the scrollable content container
- Drag handle (`.sidebar-resize-handle`, 6px, `cursor: col-resize`) on the right edge of the sidebar — turns gold on hover/drag
- Width range: 140px – 380px; persisted in `localStorage` (`tcat_sb_width`)
- Toggle button (`.sidebar-toggle-btn`, `‹` / `›`) at top-right of sidebar — hides/shows the panel
- When collapsed: `layout.style.gridTemplateColumns = '0 1fr'` (inline style, wins over CSS class); main content expands to full width
- Fixed: CSS class approach was overridden by the inline `gridTemplateColumns` saved from resize — changed to always use inline style directly
- When collapsed: fixed PANEL pill button (`.sidebar-show-btn`, vertical writing-mode) appears on left edge to re-expand
- Collapsed state persisted in `localStorage` (`tcat_sb_hidden`)
- Mobile (≤768px): resize handle and toggle button hidden; mobile overlay/hamburger behavior unchanged

### T0-5 — Sheets Retirement + Backup Schedule (2026-07-09)
- Removed `gspread`, `google-auth`, `google-auth-oauthlib` from `requirements.txt` (production no longer needs them)
- `sheets.py` moved to `archive/sheets.py.bak` — archived for reference, no longer imported
- `routes/sources.py`: removed `from sheets import ensure_headers`; `/api/init` endpoint now returns retirement message instead of calling Sheets
- `templates/index.html`: removed "Init Sheets" admin button and `initSheets()` JS function
- `.env.example`: removed `SHEET_ID` (Sheets retired); `DATABASE_URL` noted as local scripts only
- Created `.github/workflows/weekly_backup.yml`: `pg_dump` (custom format) every Sunday 00:00 UTC; stored as Actions artifact (90-day retention); `trans_revisions` noted as priority table
- **Note on DATABASE_URL for backup**: Store in GitHub repo Secrets (not GreenGeeks .env). If pg_dump fails with pgBouncer transaction pooler (port 6543), switch secret to direct connection (port 5432): `postgresql://postgres:PASSWORD@db.yvkadctkigkjtjmmxrqc.supabase.co:5432/postgres`
- Backup workflow verified 2026-07-10: `tcat_backup_20260710_062839.dump`, 493,747 bytes, 90-day artifact retention
- `upload-artifact@v4` Node.js 20 deprecation warning — upgrade to `v5` before 2025-09-19
- **Pending manual steps** (no code changes needed): export 7 Sheets worksheets as CSV → `backup/sheets_final_export_20260709/`; SSH GreenGeeks remove `SHEET_ID` from `.env`; SSH GreenGeeks: `rm ~/public_html/app.cyber-tech.com/credentials.json`

---

### Classification Stage 1 — Entity Type / Subject Field (2026-07-10)

Two-axis structured classification added to all vocabulary terms:

- **entity_type**: 人名 / 地名 / 寺院 / 宗派 / 書名典籍 / 佛菩薩尊號 / 概念術語 / 其他
- **subject_field**: 教義 / 戒律 / 禪修 / 因明 / 儀軌法物 / 稱謂教職 / 歷史事項 / 文學藝術 / 其他

**Migration**: `migrations/004_entity_subject_classification.sql`
- 5 new columns on `terms`: `entity_type`, `subject_field`, `classification_source` (ai/manual), `classified_by`, `classified_at`
- 2 indexes: `idx_terms_entity_type`, `idx_terms_subject_field`
- Old `category` column preserved (not dropped yet)
- Applied to Supabase project via MCP; all 5 columns verified

**Backend** (`ai.py`):
- Added `ENTITY_TYPES`, `SUBJECT_FIELDS` module-level constants
- Added `classify_term(term: dict) -> dict` — calls Claude Haiku, returns validated `{entity_type, subject_field, confidence, reasoning}`; strips markdown fences from response, validates values against allowed lists

**Data layer** (`repositories/terms_repo.py`):
- `entity_type`, `subject_field` added to `_FIELD_TO_DB` and `_ALLOWED_INSERT_COLS`
- `_row_to_response()` now returns all 5 classification fields
- `update_term_field()` accepts optional `extra_updates` dict for co-writing classification metadata
- Added `update_classification()` — sets all 5 classification columns in one UPDATE
- Added `get_classification_source()` — returns `classification_source` for a single term

**Routes** (`routes/terms.py`):
- `PATCH /api/terms/<id>`: `entity_type` and `subject_field` added to `editable`; when either is patched, automatically sets `classification_source='manual'`, `classified_by`, `classified_at`; audit_log entry written
- `POST /api/terms/<id>/classify`: member+ — calls `classify_term()`, writes AI result to DB, writes audit, returns `{entity_type, subject_field, confidence, reasoning}`
- `POST /api/terms/classify_batch`: leader+ — same as above for one term at a time, skips `manual` terms; frontend drives the loop

**Frontend** (`templates/index.html`):
- CSS: `.cls-row`, `.cls-badge.cls-ai`, `.cls-badge.cls-manual`, `.cls-confidence-note`
- Sidebar: "Entity Type" and "Subject Field" filter dropdowns (including "Unclassified" option for entity type); all options bilingual (e.g. `概念術語 / Doctrinal Term`)
- Sidebar: "Batch Classify" button for leader+ (drives the batch loop with live progress counter)
- Edit view: label "Entity Type / Subject Field"; two `<select>` dropdowns with bilingual options; AI badge or manual badge; "AI Classify" button; confidence note (English) shown inline when AI confidence < 60%; Source Content Chinese/English moved to bottom (below Save to Note)
- `ENTITY_TYPES` / `SUBJECT_FIELDS` value arrays; `ENTITY_TYPE_LABELS` / `SUBJECT_FIELD_LABELS` bilingual display maps; `currentEntityType` / `currentSubjectField` filter state
- `setEntityType()`, `setSubjectField()`, `classifyTerm()`, `autoSaveClassify()`, `startBatchClassify()`
- `getFilteredSorted()` updated to apply entity_type / subject_field filters

**Backfill script** (`scripts/backfill_classification.py`):
- Fetches all terms where `entity_type IS NULL`
- Calls `classify_term()` for each, writes result to Supabase
- `--dry-run`: prints suggestions only, no writes
- `--limit N`: process only N terms
- Skips already-classified rows; safe to interrupt and resume

### CI/CD Fix — Health Check User-Agent (2026-07-10)
- `deploy.yml`: health check `curl` command now sends a browser `User-Agent` and `Accept` header
- **Root cause**: GreenGeeks WAF was returning HTTP 415 to requests with the default `curl/x.x` User-Agent, causing every deploy to fail at the post-deploy site check even though the site was up
- Fix commit: `97df9a2`

---

### T2 — Translation Module: Access Gate + Import + Browse (2026-07-10)

**Scope**: Admin-only access gate, book import pipeline, and read-only browse UI. No editing or AI translation (T3 scope).

#### 任務一 — 存取旗標（開發期 admin-only gate）

- `auth.py`: added `TRANSLATION_MODULE_MIN_ROLE = os.environ.get("TRANSLATION_MIN_ROLE", "admin")` and `can_access_translation_module(user_role)` — single centralized check using `_ROLE_ORDER` index comparison
- `.env`: `TRANSLATION_MIN_ROLE=admin` (development default)
- `.env.example`: documented new variable and its on/off semantics
- `app.py`: imports `can_access_translation_module`; passes `can_access_translation=can_access_translation_module(role)` to the template
- `templates/index.html`: Translation top tab button wrapped in `{% if can_access_translation %}` — non-admin users see no tab at all (not greyed-out; completely absent)
- `routes/translate.py`: `_require_translation` decorator on every endpoint — checks `is_logged_in()` + `can_access_translation_module(session role)` → 403 if either fails
- Result: non-admin users cannot see the Translation tab, cannot navigate to it, and any direct API call to `/api/trans/...` returns 403

**Update (2026-09-04) — released to everyone**: `TRANSLATION_MODULE_MIN_ROLE` default changed
`admin` → `viewer` in `auth.py` (and local `.env`/`.env.example`), now that the module (renamed
**Books** in the UI) is ready for general use. Per-action gating inside the module is unchanged —
translate = member+, approve/glossary = leader+, chapter upload = admin — this only opens up
visibility of the tab itself. **Not yet done**: the live GreenGeeks `.env` is never touched by the
FTPS deploy (excludes `.env*`) and, per the pattern documented in `.env.example` since T2, almost
certainly has an explicit `TRANSLATION_MIN_ROLE=admin` line overriding the new code default — someone
needs to edit that line to `viewer` (or remove it) directly on the server and restart the Python
app for this to actually take effect in production. No SSH/FTP access was available this session
to do that step directly.

#### 任務二 — Migration 006 + RPC Functions

- `migrations/006_t2_import_book_rpc.sql`:
  - `import_trans_book(p_title, p_created_by, p_chapters jsonb)` — single atomic transaction: INSERT trans_books → N×INSERT trans_chapters → all×INSERT trans_units; generates all display_ids via `next_display_id()` inside the function; returns `{book_id, display_id, chapter_count, unit_count}`
  - `list_trans_books()` — single `GROUP BY` query across trans_books/trans_chapters/trans_units; returns per-book counts for all 5 unit statuses (untranslated/ai_drafted/in_review/revised/approved)
- `scripts/run_migration_006.py` — applies migration + 4 acceptance tests: import_trans_book creates correct counts; list_trans_books finds the test book; section_type='editorial' stored correctly; cleanup removes all test rows
- Migration applied; all 4 acceptance tests passed (BK000003 / BK000004 created and cleaned up)

#### 任務二 — routes/translate.py

New blueprint registered in `app.py`:
- `_require_translation` decorator — guard for all endpoints
- `POST /api/trans/books` — file upload → `decode()` → `split_paragraphs()` → one chapter per paragraph, `detect_section_type()` for each, `segment_paragraph()` for each → `import_trans_book` RPC → 201 `{book_display_id, chapter_count, unit_count}`
- `GET /api/trans/books` — calls `list_trans_books()` RPC; returns book list with progress stats
- `GET /api/trans/books/<book_id>/chapters` — PostgREST SELECT ordered by `chapter_index`
- `GET /api/trans/chapters/<chapter_id>/units` — PostgREST SELECT ordered by `paragraph_index, unit_order`

#### 任務三 — Translation UI (index.html)

CSS added for: book card grid (`.trans-book-card`), progress bar (`.trans-progress-bar`), status dots, upload form, chapter list, unit list, status badges — all 5 status colors (grey/blue/gold/orange/green).

HTML added (`{% if can_access_translation %}` block):
- `#translation-view` (hidden div, shown by `switchTopTab('translation')`)
  - `#trans-picker` — book card grid + upload form
  - `#trans-chapter-view` — chapter list with back button
  - `#trans-unit-view` — sentence list with back button

JS added (`{% if can_access_translation %}` block):
- `transLoadBooks()` — calls `GET /api/trans/books`; renders book cards with progress bar + status dots
- `transOpenBook(bookId, title)` — calls `GET /api/trans/books/<id>/chapters`; renders chapter list
- `transOpenChapter(chapterId, title)` — calls `GET /api/trans/chapters/<id>/units`; renders sentence list (paragraph breaks, long-sentence highlight, status badges)
- `transUploadBook()` — `FormData` POST to `/api/trans/books`; shows inline success/error message; refreshes book grid
- `transShowPicker()` / `transShowChapterList()` / `transShowUnitList()` — sub-view toggle helpers
- `switchTopTab()` refactored to handle 3 tabs cleanly (vocabulary / extraction / translation)

---

### T2.1 — Sentence-Map + Draft Review Workflow (2026-07-10)

**Scope**: Per-sentence grouping workspace — segment chapter into draft groups, run AI topic grouping per paragraph, drag-and-drop human review, confirm to write `trans_units`.

#### Migration 007
- `migrations/007_t2_1_sentence_map.sql`:
  - `ALTER TABLE trans_units ADD COLUMN IF NOT EXISTS sentence_map jsonb` — stores original sentence list for split-back
  - `CREATE TABLE trans_unit_drafts` — `(chapter_id bigint FK, paragraph_index int, draft_groups jsonb, status text CHECK(pending/ai_suggested/human_adjusted/confirmed), last_modified_by, last_modified_at)`; UNIQUE `(chapter_id, paragraph_index)`; `idx_drafts_chapter` index
- `scripts/run_migration_007.py` — applies 007 + 5 acceptance tests (column, table, unique constraint, index, check constraint) + T2 test-data cleanup
- Migration applied to Supabase via MCP; all 5 acceptance tests passed

#### ai.py — `group_sentences_by_topic()`
- New function added before `classify_term`
- Input: `[{"text": str, "is_long_sentence": bool}, ...]`; output: `[[0,1], [2], [3,4,5]]` — index lists per group
- Prompts Claude Haiku in Chinese to group sentences by topic coherence; strips markdown fences; validates all indices present exactly once
- Fallback: `[[i] for i in range(len(sentences))]` on any exception — never raises

#### routes/translate.py — Full Rewrite (T2.1 endpoints)

`POST /api/trans/books` changed to **metadata-only** — JSON body `{"title": "..."}`, no file upload.

New endpoints (all guarded by `_require_translation`):

| Endpoint | Purpose |
|---|---|
| `POST /api/trans/books/<id>/chapters` | Upload `.txt` → `split_paragraphs` + `segment_paragraph` → create `trans_unit_drafts` rows (one per paragraph, `status='pending'`) |
| `GET /api/trans/chapters/<id>/drafts` | Return all paragraph drafts ordered by `paragraph_index` |
| `POST /api/trans/chapters/<id>/paragraphs/<idx>/group-preview` | Flatten current draft_groups → call `group_sentences_by_topic()` → UPDATE draft with `status='ai_suggested'` |
| `PATCH /api/trans/chapters/<id>/paragraphs/<idx>/draft` | Human adjustment — auto-save on every UI change; sets `status='human_adjusted'` |
| `POST /api/trans/chapters/<id>/paragraphs/<idx>/confirm` | DELETE existing `trans_units` for this paragraph, INSERT one row per group (`chinese_text`, `sentence_map`, `is_long_sentence`), mark draft `confirmed` |

Key design decisions:
- Chapter upload runs only pure-algorithm code (no AI calls) to avoid CGI timeout on GreenGeeks shared hosting. AI grouping is triggered per-paragraph by the frontend separately.
- Re-confirm is idempotent: `confirm` DELETEs existing `trans_units` for the paragraph before inserting, so re-running never duplicates.
- `_now_iso()` helper (`datetime.now(timezone.utc).isoformat()`) used for `last_modified_at` in PATCH/confirm — PostgREST doesn't execute SQL functions inside value strings.

#### templates/index.html — Review Workspace UI

CSS additions: paragraph card stack (`.trd-para-card`, confirmed variant), status badges (4 states: pending/ai/adjusted/confirmed), sentence/group drag-and-drop targets, "new group" drop zone, save indicator, chapter upload section.

HTML additions:
- Upload form: removed `<input type="file">` (book creation is now metadata-only); added chapter upload section `<div class="trans-ch-upload">` inside chapter list view
- `<div id="trans-review-view">` — new sub-view with title, progress line, paragraph card body
- Chapter rows: now render two buttons per row — "Review Drafts" and "Browse Units"

JS additions:
- `_transHideAll()` hides all 4 sub-views; each `transShow*` calls it then shows one
- `transOpenBook` → `transReloadChapters()` renders chapter rows with two-button layout
- `transUploadChapter()` — FormData POST, refreshes chapter list on success
- `transUploadBook()` — JSON POST (title only), refreshes book grid on success
- `transOpenReview(chapterId, title)` → `trdLoad()` → GET /drafts → `trdRenderAll()`
- `trdParaCardHtml()` / `trdGroupHtml()` — render paragraph cards with drag handles, AI button, confirm button
- Drag-drop: `trdDragStart`, `trdDropGroup`, `trdDropNew`, `_trdMoveSentence` — sentence moves between groups; re-renders card in-place; calls `trdScheduleSave()`
- `trdScheduleSave(paraIdx)` — 600ms debounce → `trdSave()` → PATCH auto-save on every UI change
- `trdRunAI(paraIdx)` — POST group-preview, re-renders paragraph card with AI grouping
- `trdConfirm(paraIdx)` — confirm dialog → POST confirm → re-renders as confirmed
- `trdUpdateProgress()` — tracks confirmed count vs total

#### E2E Validation
- Full flow tested via SQL DO block in Supabase: insert book → chapter → draft → update draft → confirm → assert 2 `trans_units` rows → cleanup — all steps passed

### T2.1 Post-Launch Fixes (2026-07-11)

Bugs and UX issues found during first live test of the review workspace:

- **RPC parameter name bug** (`routes/translate.py`): `next_display_id` RPC was called with `prefix`/`seq_name` but the function signature uses `p_prefix`/`p_seq_name`. Fixed all three call sites (book, chapter, unit creation). Commit `9a3fb74`.
- **Drag-drop enforces original sentence order**: Sentences can only be regrouped — they cannot be reordered. Added `_trdStampOrigIdx()` (stamps each sentence with its flat position on load) and `_trdRestoreOrder()` (sorts sentences within groups and groups by min index after every move). `_origIdx` is stripped from the payload before saving to DB. Also re-stamps after AI grouping response. Commit `cff1ac8`.
- **Upload Chapter hidden from non-admins**: The chapter upload form is now wrapped in `{% if is_admin %}` — only admins see it. Commit `9af7f27`.
- **Chapter title no longer defaults to filename**: Removed the `or f.filename.rsplit(".", 1)[0]` fallback in `api_upload_chapter()`; title is now empty if not supplied. Frontend falls back to the book name when chapter title is empty. Commit `9af7f27`.
- **Confirm button at bottom of card**: Added a second "確認寫入" button at the bottom of each paragraph card so users don't need to scroll back up. For paragraphs with fewer than 3 groups, the top button is hidden (only bottom shown). Commits `0548df6`, `b097af8`.

---

### T3 — AI Translation Drafting (2026-07-11)

**Scope**: `translate_unit()` AI drafting (system instruction + terminology constraints), plus save/approve endpoints that write revisions to `trans_revisions`. Per the design guide roadmap, RAG example retrieval (pgvector) and style-guide prompt injection are **T4** (now done — see below), not T3. No migration was needed — `trans_units` (`english_draft`/`english_final`/`split_map`/`status`/`ai_model`/`translated_by`/`reviewed_by`/`approved_by`) and `trans_revisions` already existed from T0-1/T1.

#### ai.py — `translate_unit()`
- New function: `translate_unit(chinese_text, term_constraints=None, context_before="", context_after="", is_long_sentence=False) -> {"english": str, "split_map": list|None}`
- Prompt assembly: translator role instruction + terminology constraints (`Fixed terminology — MUST be rendered exactly as given: …`) + adjacent-sentence context (labelled "context only — do not translate") + long-sentence split_map request
- Reply parsed as JSON (`{"english": ..., "split_map": ...}`) — same markdown-fence-stripping pattern as `classify_term()` / `group_sentences_by_topic()`
- Never raises — returns `{"english": "", "split_map": None}` on any API/parse failure

#### repositories/terms_repo.py — `get_translation_constraint_terms()`
- Returns `[{"chinese": str, "english": str}, ...]` for every term with a non-empty `TranslationKnown`, or a `translation_first` when `final` is set (i.e. Final/Known per the design doc's constraint rule)
- Paginated fetch (same `_PAGE` pattern as `list_terms()`); filtering done client-side rather than a PostgREST `.or_()` filter, to match this module's existing query style

#### routes/translate.py — new endpoints
| Endpoint | Method | Guard | Purpose |
|---|---|---|---|
| `/api/trans/units/<id>/translate` | POST | `_require_translation` + member+ | Runs AI drafting for one unit. First run writes `english_draft` (never overwritten again) + `english_final`; re-runs ("regenerate") leave `english_draft` untouched and overwrite only `english_final`, for comparison. Sets `ai_model`, `translated_by`, `status='ai_drafted'`. |
| `/api/trans/units/<id>` | PATCH | `_require_translation` + member+ (approve requires leader+) | Saves an edited translation. Body: `{"english_text", "approve"}`. `approve=true` + unchanged → `status='approved'`, no revision row. `approve=true` + changed → `status='revised'`, writes a `trans_revisions` row (`english_before`/`english_after`/`revision_type`/`note`), sets `approved_by`. `approve=false` → `status='in_review'` (work-in-progress save, no revision write). |

- `_match_constraint_terms()`: substring-matches `get_translation_constraint_terms()` against the unit's Chinese text, longest match first, capped at 15 terms to keep the prompt compact
- `_get_context()`: fetches the previous/next unit's Chinese text within the same chapter for coherence context
- Both endpoints write to the shared `audit_log` via `write_audit()` (reusing the vocabulary module's audit mechanism, per the design doc's "reusable assets" list), keyed on the unit's `display_id`
- `GET /api/trans/chapters/<id>/units` widened from a fixed column list to `select("*")` so the browse view can read `english_draft`/`english_final`/`status` etc.

#### templates/index.html — minimal working UI
- `trans-unit-row` restructured from a single-line read-only row into a card: id + status badge, Chinese text, an editable English textarea (member+), and action buttons
- New JS: `transTranslateUnit()` (calls the translate endpoint), `transSaveUnit(unitId, approve)` (calls the PATCH endpoint), `_transUnitRowHtml()` / `_transReplaceUnitRow()` (render/patch a single row in place)
- Button visibility gated client-side by `userRole`: Translate/Save require member+ (`_CAN_TRANSLATE`), Approve requires leader+ (`_CAN_APPROVE`) — mirrors the server-side checks, which remain the actual authority
- **Deferred to T4/T5** (per the design doc's own roadmap, not an oversight): the three-column review workspace (chapter tree / sentence cards / reference panel), diff highlighting between `english_draft` and `english_final`, chapter claiming — style-guide + pgvector example injection landed in T4.1/T4.2 below

#### Not yet verified
- No live end-to-end test run yet (no local server / Supabase round-trip performed this session) — see Next Steps

---

### T4.1 — Style Guide CRUD + Prompt Injection (2026-07-12)

**Scope**: CRUD for `style_guide` (already existed as a table since T1) plus injecting active rules into `translate_unit()`'s prompt. No migration needed.

#### `routes/translate.py`
- `_get_active_style_rules()` — fetches `style_guide` rows `where active=true`; returns `[]` on any error (never blocks translation)
- `GET /api/trans/styleguide` — member+; returns all rules (active and inactive) ordered by `category, created_at`, so the management screen can show the full picture
- `POST /api/trans/styleguide` — leader+ only (403 otherwise); validates `category` against the 5 allowed values and requires `rule_text`; `display_id` via `next_display_id` RPC (`S` prefix, `seq_style_guide_display`)
- `PATCH /api/trans/styleguide/<id>` — leader+ only; partial update of any of `category`/`rule_text`/`example_before`/`example_after`/`active`; deactivation only (`active=false`), no hard delete, matching the design doc's "disable, don't delete" rule
- `api_translate_unit()` now calls `_get_active_style_rules()` and passes the result into `translate_unit(..., style_rules=...)`

#### `ai.py` — `translate_unit()`
- New optional param `style_rules: list = None`; when non-empty, assembles a "Style guide — house rules to follow" block inserted before the terminology-constraints section, matching the design doc's prompt-assembly order

#### `templates/index.html`
- New "風格指南" (Style Guide) entry point from the Translation Picker view, visible to leader+
- Rule list grouped by category, visible read-only to all translation-module users; add-rule form and active/inactive toggle restricted to leader+ (both client-side hidden and server-side enforced)
- **Preset picker** (added 2026-07-13, post-launch): `SG_PRESETS` — a hardcoded JS array of style rules across all 5 categories. A dropdown above the Add New Rule form fills the category/rule/example fields on selection (does not auto-submit — leader can edit before adding). `sgPopulatePresets()` filters out any preset whose `rule` text exact-matches an already-added rule, re-run after every `sgLoadRules()` so the list stays current
- **Expanded to 54 presets** (2026-07-13): researched established Buddhist-translation style conventions — Wisdom Publications' style guide (capitalization, italics, diacritics, glossary format), Xuanzang's Five Untranslatables (五種不翻 — mantras, polysemous terms, no target-culture equivalent, established precedent, respect-inspiring terms), Fo Guang Shan ITC glossary conventions (Chinese+Pinyin+Sanskrit format), and general scholarly Buddhist-translation practice. Breakdown: 12 tone, 11 honorifics, 16 proper_nouns, 6 sentence_splitting, 9 other.
- **Bilingual rule text** (2026-07-13): every preset's `rule` string is now `中文說明 / English explanation` in one field (rather than Chinese-only), so the rule cards in the Style Guide list, the Add Rule form once a preset is picked, and the text injected into `translate_unit()`'s prompt all carry both languages. Verified via a standalone Node syntax check (parsed cleanly, 54/54 presets contain English text, no duplicate labels/rule text, all categories valid) — not yet tested by actually rendering the dropdown/card list in a browser

#### Not yet verified
- No rule has been created live yet (`style_guide` table is still empty in Supabase) — see Next Steps for live-test plan
- Preset picker not yet committed/deployed (edited directly in this session — needs `git add`/`commit`/`push` to reach the live site)

---

### T4.2 — Dual-Provider Embeddings + pgvector RAG Retrieval (2026-07-12)

**Scope**: Anthropic has no native embeddings endpoint, so this wires up **two** providers in parallel — Voyage AI and OpenAI — rather than committing to one, so retrieval quality can be compared before choosing. Superseded the original design doc's single `trans_revisions.embedding vector(1536)` column.

#### Migration 010 — `010_dual_embeddings.sql`
- Dropped the unused `trans_revisions.embedding` column
- Added `embedding_voyage vector(1024)` (Voyage `voyage-3`) and `embedding_openai vector(1536)` (OpenAI `text-embedding-3-small`)
- Added RPC functions `find_similar_revisions_voyage(query_embedding, match_limit)` and `find_similar_revisions_openai(query_embedding, match_limit)` — cosine-similarity `ORDER BY ... <=> ...` queries (PostgREST/supabase-py can't express `<=>` directly, hence the RPC wrapper)
- No index built yet (corpus far below the threshold where ivfflat/hnsw would matter, per design doc guidance)
- Applied to Supabase (`TCAT-vocab`); columns and both RPC functions verified live via direct SQL

#### `embeddings.py` (new file)
- `get_voyage_embedding(text)` / `get_openai_embedding(text)` — each returns `None` (never raises) if the text is empty, the corresponding API key env var is unset, the package isn't importable, or the API call fails
- `get_embeddings(text)` — calls both, returns `{"voyage": ..., "openai": ...}`
- `requirements.txt`: added `voyageai`, `openai` (both used defensively via `try/except ImportError`)
- `.env.example`: added `VOYAGE_API_KEY`, `OPENAI_API_KEY` (both optional), `EMBEDDING_PROVIDER` (default `voyage` — selects which column drives live RAG retrieval at translate time; writes always attempt both regardless of this setting)

#### `routes/translate.py`
- `PATCH /api/trans/units/<id>`: after an approved-and-changed save writes its `trans_revisions` row, best-effort calls `embeddings.get_embeddings(chinese_text)` and updates `embedding_voyage`/`embedding_openai` on that row — wrapped so failure never fails the parent request
- `_get_similar_examples(chinese_text, match_limit=5, threshold=0.5)` — reads `EMBEDDING_PROVIDER`, embeds via the matching provider, calls the matching RPC, filters out results below `similarity < 0.5` (cold-start guard from the design doc), returns `[]` on any failure or if nothing clears the threshold
- `api_translate_unit()` now also calls `_get_similar_examples()` and passes results into `translate_unit(..., similar_examples=...)`

#### `ai.py` — `translate_unit()`
- New optional param `similar_examples: list = None`; when non-empty, assembles a few-shot "Similar past translations (for tone/style reference only...)" block, inserted after the style-guide block and before terminology constraints

#### `scripts/compare_embedding_providers.py` (new)
- Manual A/B tool: for a set of test Chinese sentences, embeds each via both providers and prints the top-5 `find_similar_revisions_*` results for each side by side, so retrieval quality can be judged by eye before deciding whether to keep both providers or drop one

#### Not yet verified
- `trans_revisions` has zero rows with embeddings so far (no approved-and-changed edit has been made live yet) — RAG injection, the write-on-approve hook, and the comparison script all still need a real run once at least one `VOYAGE_API_KEY`/`OPENAI_API_KEY` is set in `.env`

---

### T1 — Translation Module Data Layer + Segmenter (2026-07-10)

**Scope**: Pure data layer + algorithm. No UI, no API endpoints.

#### Migration 005
- Created `migrations/005_t1_translation_module.sql` — idempotent DDL (`IF NOT EXISTS`) for all 5 translation tables and their sequences
- Created `scripts/run_migration_005.py` — applies migration + runs 8 acceptance tests:
  1. INSERT one test row per table; verify display_id format (B000001, C000001, U000001, R000001, S000001)
  2. Unique constraint on `trans_books.display_id` — duplicate rejected (savepoint-safe)
  3. Fractional `unit_order=1.5` in `trans_units` — confirms numeric type allows decimal values
  4. Clean-up: all test rows deleted; transaction committed
- Migration applied to Supabase; all 8 acceptance tests passed; no test data left in tables

#### segmenter.py
- New module `segmenter.py` at repo root — pure algorithm, no DB writes (T2 scope)
- Public API:
  - `decode(data: bytes)` — UTF-8 → GB18030 → Big5 encoding detection (same as `extract.py._decode`)
  - `split_paragraphs(text: str)` — blank-line paragraph split (same as `extract.py._split_paragraphs`)
  - `detect_section_type(paragraph: str)` — prefix matching: 本社按/編者按→editorial, 譯者序→preface, 跋→postscript, else body
  - `segment_paragraph(text: str) -> list[dict]` — returns `[{"text": str, "is_long_sentence": bool}, ...]`
- Segmentation algorithm:
  - Hard boundaries: `。！？……` (full-width) fire only at quote depth == 0
  - Quote protection: `「」『』""` — depth counter; terminators at depth > 0 are absorbed without split
  - Close-quote handler: adjusts depth, appends to buffer, **never flushes** (key fix: only depth-0 terminators split)
  - Close-quote suffix rule (收尾規則): when a depth-0 terminator fires, trailing close-quotes are consumed into that sentence before flush
  - Ellipsis (`……`): absorbs consecutive `…` chars; at depth=0 consumes trailing close-quotes then flushes
  - Long-sentence flag: internal punctuation (，、；) count > 3 **or** char count > 45
  - Remainder: text after last terminator returned as final unit (no trailing terminator required)

#### test_segmenter.py
- 15 pytest test cases, all passing (`pytest test_segmenter.py` → 15 passed, 0 failed)
- TC-1 (design doc): quote-protected `。` inside `「」` does not split; entire passage = 1 unit
- TC-2 (design doc): 5-comma parallel sentence flagged `is_long_sentence=True`
- Boundary cases: plain short sentence, 3-sentence no-quote, `！`/`？` boundaries, quote speech continues after close-quote, close-suffix rule at depth-0, nested `「『』」` no inner split, ellipsis boundary, no-terminator remainder, long-by-char-count
- Section-type detection: editorial / preface / postscript / body defaults

---

### Translation Module — Term Highlighting + Candidate Modal (2026-07-12)

**Scope**: Click-to-lookup term highlighting in the Translation module's T2.1 Review Drafts and T3 Browse Units views, plus a floating candidate modal for viewing or creating terms.

#### Backend — `GET /api/trans/known-terms`

- New endpoint in `routes/translate.py`, guarded by `_require_translation`
- Calls `terms_repo.list_terms()` and returns a lightweight array: `id, chinese, pinyin, pali, sanskrit, trans_known, trans1, trans2, trans3, status, final`
- `status` and `final` included so the frontend can show the term's current state without a second fetch

#### Frontend — Highlighting

- `trdFetchKnownTerms()` — fetches from `/api/trans/known-terms` on entering Review Drafts or Browse Units; stores result in `trdKnownTerms[]`
- `trdHighlightKnownTerms(text)` — greedy longest-match-first algorithm using `Uint8Array` for claimed-character tracking; produces `<span class="term-known">` elements (gold tint = no Known Translation; blue tint = has Known Translation)
- Applied in `trdGroupHtml()` (T2.1 sentence cards) and `_transUnitRowHtml()` (T3 Browse Units rows)
- Term span click handlers use `onclick` + `stopPropagation()` (not mousedown) so drag-and-drop is not disrupted

#### Frontend — Candidate Modal (`#trd-candidate-panel`)

- Separate panel from Extraction's `#ext-candidate-panel` (own ID, own state variables, own drag handler)
- Triggered by either term span click (`trdHandleTermClick`) or text selection (`trdHandleSelection`) in T2.1 or T3
- **Known term branch**: read-only field grid (Known Trans., Translation 1–3, Pinyin, Pali, Sanskrit)
- **New term branch**: "✨ Generate 3 AI Translations" button → `POST /api/extract/generate` → populated fields → "Add to Database" button → `POST /api/extract/save`
- Escape key or ✕ closes modal
- Draggable via `_trdMakeDraggable()` (separate from `_extMakeDraggable`, uses own `_trdPanelPos` state)

#### Edit Term

- Read-only modal has "✎ Edit Term" button → `trdShowTermEditMode()`
- Edit mode renders 7 input fields (trans_known, trans1, trans2, trans3, pinyin, pali, sanskrit) pre-filled with current values
- "Save Changes" → `trdSaveTermEdits()` — calls `PATCH /api/terms/<id>` per changed field (one call per field); updates `trdKnownTerms` cache in-place; returns to read-only view after 1 second
- "Cancel" returns to read-only view without saving

#### Status Badge + Finalize Button (added same day)

- Read-only modal now shows a status badge next to "Already in database":
  - **Pending** — amber badge
  - **Finalized — Translation N** — green badge (shows which translation was finalized)
- Edit mode adds a **Finalize** button next to trans_known, trans1, trans2, trans3 inputs that have a non-empty value
- `trdFinalizeTerm(voteKey)` — confirm dialog → `POST /api/terms/<id>/final` (requires Leader+ role) → updates `status`/`final` in `trdKnownTerms` cache → returns to read-only view with updated status badge
- Finalize is Leader/Admin only; Member clicking the button sees a "Leader or admin only" error from the server

Commits: `0d9010e` (highlighting + modal + edit term), `42feaf9` (status badge + finalize button)

---

### Translation Module — UI Polish Pass (2026-09-01 to 2026-09-03)

A run of small UX fixes/features to the Translation module, done incrementally:

- **"Approve" → "Reviewed"**: renamed the T3 unit action button and its status badge label; underlying `trans_units.status = 'approved'` DB value unchanged (display-only). Commit `bc0702e`.
- **Chapter list hides Review Drafts once fully confirmed**: `GET /api/trans/books/<id>/chapters` now also returns `draft_total`/`draft_confirmed` per chapter; frontend hides the **Review Drafts** button and relabels **Browse Units** → **Work on Units** once every paragraph draft in that chapter is confirmed. Commit `0a0ee7b`.
- **Full editable term panel replaces the old cramped modal**: clicking a highlighted term in Review Drafts or Work on Units now opens the same rich Vocabulary edit view (`buildEditView()`, AI Translate, Suggest, Ask AI, audit log, etc.) as a full-screen overlay, reusing `#edit-view` via DOM reparenting rather than a separate small panel. Header shows **← Back to Unit** (closes the overlay, blurring any focused field first so autosave fires) and **Previous/Next** that walk the *other known terms in that same unit* (not the global vocabulary list) — hidden entirely when there's only one term to navigate to. Old small-panel edit/finalize functions (`trdShowTermEditMode`, `trdSaveTermEdits`, `trdFinalizeTerm`) removed as dead code. Term highlighting gained a third color: **green** (`.term-reviewed`) when the term's status is `reviewed`, on top of the existing gold/blue (no known-translation / has known-translation) scheme. Commit `a8d8325`.
- **Fixed Previous/Next sticking on repeated terms**: when a term (e.g. 法, 相應) appears more than once in a unit, `Array.indexOf(termId)` always resolved to the first occurrence. Fixed by capturing the clicked span's actual position (`opts.navIndex`) instead of re-deriving it from the id on every navigation step. Commit `bd175bd`.
- **Chapter list staleness fix**: the "← Chapters" back button only toggled panel visibility without re-fetching, so it kept showing the button state from before a Review Drafts session — not a data bug. Added `transBackToChapters()` which re-fetches on the way back. Commit `62910b0`.
- **Vocabulary list "Go to Page"**: added a page-number jump input next to Prev/Next in the pagination bar (reuses the existing `goToPage(n)` clamp logic and the Extraction tab's `.ext-jump-input` styling). Commits `2431b52`, `2ceaab9`.

---

### Vocabulary — Multi-Source Terms (2026-09-03)

**Scope**: `terms.source` was a single text column (one SourceID per term), so the same term appearing in multiple source books had to be duplicated or arbitrarily assigned to just one book. Replaced with a proper many-to-many relationship.

#### Migration 015 — `015_term_sources_many_to_many.sql`
- New table `term_sources (term_id bigint, source_id bigint)` — composite PK, both FKs `ON DELETE CASCADE`; indexes on both columns
- Backfilled from the old `terms.source` column (1,902 of 3,654 terms had a source set — all values verified to resolve cleanly to existing `sources.display_id` before migrating, zero orphans)
- `terms.source` column dropped after backfill
- Applied directly to Supabase (`TCAT-vocab`) via MCP; backfill count (1,902 rows) verified to match pre-migration count exactly

#### `repositories/terms_repo.py`
- Removed `source` from `_FIELD_TO_DB`, `_MERGE_FIELD_TO_DB`, `_ALLOWED_INSERT_COLS`, `_row_to_response`, `_row_to_sheets_fmt`
- `_row_to_response()` now takes an optional `sources` list param → `"sources": [SourceID, ...]` in the API response (empty list default)
- `_fetch_all_term_sources_map()` — one paginated query joining `term_sources` + `sources`, returns `{term_internal_id: [SourceID, ...]}`; used by `list_terms()` to attach `sources` to every row in one shot rather than N+1 queries
- `set_term_sources(term_id, source_display_ids, modifier, now_str)` — **replaces** a term's linked sources; returns `(chinese, old_sources, new_sources)`
- `add_term_source(term_id, source_display_id, modifier, now_str)` — **additive** link (used when an already-known term is re-encountered in a different source book via Extraction — doesn't clobber its existing sources)
- `create_term()` accepts an optional `"sources": [...]` list and links them after insert
- `merge_terms()` no longer treats `source` as a per-side radio field — it now **always unions** both terms' linked sources onto `keep_id` automatically, so merging duplicates never silently drops a source book
- All three write paths (`set_term_sources`, `add_term_source`, `merge_terms` union) verified against live Supabase data this session using a real term (round-tripped and restored to its original state) and disposable throwaway terms (created, merged, hard-deleted) — zero net change to production data, confirmed via row-count check on `term_sources` (1,902 before and after)

#### `routes/terms.py`
- `POST /api/terms`: `sources` (list) replaces `source` (string) in the payload passed to `create_term()`
- `POST /api/terms/bulk` (CSV import): `source` column now accepts multiple SourceIDs separated by `|` (e.g. `S000001|S000002`)
- `PATCH /api/terms/<id>`: `field: "sources"` now accepts `value` as a list and routes to `terms_repo.set_term_sources()`; audit log records old/new as comma-joined SourceID lists

#### `routes/extract.py`
- `POST /api/extract/save` insert path: `"source": source_id` → `"sources": [source_id]`
- Update path (term already exists): now also calls `add_term_source()` so re-encountering a known term in a new document links the new book without touching its existing sources

#### `templates/index.html`
- Edit view **Sources** field: initially a `<select multiple>` (ctrl/cmd-click), saved via `autoSaveSources()` — same optimistic-update pattern as `autoSaveMeta()` but diffs arrays instead of strings. **Superseded same day**: replaced with a compact one-line dropdown button (`sourceMultiSelectHtml()` + `toggleSourceDropdown()` + `onSourceCheckboxChange()`) after user feedback that the 4-row select ate too much header space — see "Translation Module — UI Polish Pass" below. `autoSaveSources()` itself was removed; the checkbox popover posts the same `PATCH {field:'sources'}` directly.
- Add Term modal's Source field is still the native `<select multiple>` (has room to spare there); `submitSingleTerm()` sends `sources: [...]`
- Sidebar source filter, search haystack, and the list table's Source column all switched from `t.source`/`sourceName()` to `t.sources`/new `sourceNames()` helper (comma-joined)
- Merge-duplicates modal: removed the per-side Source radio row entirely; added a read-only **Sources — combined automatically** info row showing the union, since merging always keeps both terms' sources now
- `config.py` `FIELD_LABELS`: `"source"` → `"sources": "Sources"` (used in audit-log field-changed labels)

#### Not yet verified
- No live browser test of the merge-modal union display this session — backend read/write paths and the compact Sources dropdown button were both verified (dropdown confirmed working via later user screenshots this session; merge modal has not been)

---

### Book Glossary (2026-09-03)

**Scope**: Leader/Admin-curated glossary per **Translation Book** (`trans_books` — the book being
actively translated, not the vocabulary "Sources" citation tag). A term can be marked as a
glossary entry for a specific book, with an AI-drafted bilingual (EN+ZH) explanation the user can
regenerate and hand-edit — distinct from the term-scoped "Ask AI" doctrinal gloss (`ai_context`),
which is translator-facing and not book-scoped. Planned via `EnterPlanMode`/`ExitPlanMode` with
two user-confirmed decisions: "book" = `trans_books`, and only Leader/Admin can add/remove/edit/
generate (Members can view).

#### Migration 016 — `016_book_glossary.sql`
- New table `book_glossary_terms`: `book_id`/`term_id` FKs (`ON DELETE CASCADE`), `explanation`
  text, `explanation_source` (ai/manual), `status` (draft/reviewed), UNIQUE (book_id, term_id)
- Applied live via Supabase MCP; verified with `list_tables`

#### `ai.py` — `generate_glossary_entry()`
- Sibling to `explain_term_context()` (unchanged) but shorter and reader-facing: one concise
  bilingual paragraph per language ("dictionary style"), not the multi-section translator essay
  Ask AI produces. Same `── English ──` / `── 中文 ──` format for consistent rendering.
- Verified live against the Anthropic API (522-char bilingual entry for a test term)

#### `repositories/glossary_repo.py` (new)
- `list_for_book()`, `add_term()` (dedupe via UNIQUE constraint → friendly "already in glossary"),
  `remove_term()`, `get_one()`/`get_response()` (join with `terms`+`trans_books` for display
  fields), `update_entry()` (partial update; setting `explanation` without an explicit
  `explanation_source` defaults to `'manual'`, so the AI-generate endpoint must pass
  `explanation_source='ai'` explicitly to avoid mislabeling its own output)
- All functions verified directly against live Supabase with disposable book+term (created,
  full CRUD cycle, cleaned up) — zero leftover rows confirmed via row-count check

#### `routes/translate.py` — 5 new endpoints
| Endpoint | Method | Guard |
|---|---|---|
| `/api/trans/books/<book_id>/glossary` | GET | any translation-module user |
| `/api/trans/books/<book_id>/glossary` | POST | Leader+ (`{term_id}`) |
| `/api/trans/glossary/<id>/generate` | POST | Leader+ |
| `/api/trans/glossary/<id>` | PATCH | Leader+ (`{explanation}` and/or `{status}`) |
| `/api/trans/glossary/<id>` | DELETE | Leader+ |

All 5 verified end-to-end through Flask's test client (real HTTP request/response cycle, admin
session, live Supabase + live Anthropic API) this session — add → duplicate-add rejected →
generate → manual edit + mark reviewed → list → delete → list empty — then cleaned up with zero
leftover rows.

#### `templates/index.html`
- **Entry point**: "📖 Glossary" button in the Chapters view toolbar (Leader+ only, `{% if is_leader %}`) → `transOpenGlossaryList()`
- **New sub-view** `#trans-glossary-list-view`: one row per entry (Chinese + pinyin, draft/reviewed
  badge reusing the `.trans-status-*` classes, explanation preview with the bilingual header
  markers stripped) — each row opens the **same full editable term panel** built earlier this
  session (`trdOpenTermFull`), with `navList` = the book's ordered glossary term ids so Previous/
  Next walk the glossary instead of a unit's terms — zero changes needed in `buildEditView()`'s
  nav logic, it already generalized to this via `opts.navList`/`navIndex`
- **Term panel**: new Glossary section in `buildEditView()`, shown only when `opts.bookId` is set
  (i.e. opened from inside a Translation book — never from the plain Vocabulary tab). Not-yet-
  glossary shows "★ Add to Glossary — {book}"; already-glossary shows a status badge, an editable
  explanation textarea (`autoSaveGlossaryExplanation()`, blur-to-save), Generate/Regenerate, a
  Draft⇄Reviewed toggle, and Remove — all Leader+-gated client-side (server is the real authority)
- `_transCurrentBookId`/`_transCurrentBookTitle` (already-existing globals) are read directly
  into `_editViewOpts.bookId`/`bookTitle` inside `trdOpenTermFull()` — no new params needed since
  the panel is only ever opened from contexts where those globals are already set
- `trdGlossaryMap` (term_id → entry) + `trdGlossaryList` (ordered array) fetched once via
  `trdFetchGlossaryTerms()` whenever a book context opens (Review Drafts/Work on Units/Review
  Vocabularies/Glossary list), avoiding a per-term round trip; `trdCloseTermFull()` re-fetches
  both on close so edits are immediately reflected
- One bug caught and fixed before commit: the glossary row's `onclick` embedded a JSON-stringified
  navList array inside a double-quoted HTML attribute, which broke because `JSON.stringify`
  produces double-quoted strings — fixed by switching that one attribute to single-quoted

#### Out of scope this pass (documented, not built)
Exporting/printing the glossary as a book appendix; custom (non-alphabetical) sort/reorder;
copying a glossary entry to another book; a live glossary-count badge on the Book List cards.

### Stage F1 — Glossary Links + Constraint Priority (2026-11-02)

First stage of `docs/TCAT_Translation_Fix_Prompts.md` (Greg's 入法門論 comparison: underlines did
not reflect the reviewed glossary, and a Known value could override a reviewed Final).

#### `repositories/terms_repo.py`
- `get_translation_constraint_terms()`: English per term is now the Final (`translation_first`
  when `final` is set) **first**, `translation_known` only as fallback. A Known fallback containing
  ";" is passed whole with `"alternatives": True`. Duplicates linked to the book: only the best one
  is used (reviewed > has Final > other). Unlinked duplicates: all distinct renderings kept, best
  first (previous behaviour). Inactive exclusion unchanged.
- New `list_book_known_terms(source_id)`: active terms linked to the source via `term_sources`,
  deduplicated by Chinese with the same ranking; single characters only when reviewed. Adds
  `final_text` and `in_book: true`.
- Helpers `_final_text()`, `_dup_rank()`, `_source_term_ids()`.

#### `routes/translate.py`
- `_get_source_id_for_book(book_id)` (trans_books.source_id, else sources.source_name == title);
  `_get_book_source_id(chapter_id)` now delegates to it.
- `GET /api/trans/known-terms`: `?book_id=N` → book-scoped list; `?book_id=N&all=1` → full list
  (old behaviour) with `in_book` flags; no `book_id` → old behaviour. Every item has `final_text`
  and `in_book`. A book whose source cannot be resolved falls back to the full list.
  `/api/extract/known-terms` untouched.

#### `ai.py`
- `translate_unit()` term hint renders alternatives as `X → one of [a / b] (choose the one that
  fits)` so ";"-separated options no longer blur into the "; "-joined pair list. Rest of the
  prompt unchanged (F3 rewrites it).

#### `templates/index.html`
- `trdFetchKnownTerms()` sends `_transCurrentBookId` (fetched on every chapter/review open, so a
  book change re-fetches). Tooltip priority: `Final: …` → `Known: …` → `AI suggestion: …`.
- "Show all vocabulary" checkbox (default off, `localStorage` key `tcat_trd_show_all`, try/catch)
  in the Work on Units, Review Vocabularies and Review Drafts toolbars; on = full list, non-book
  terms get faint dotted `.term-other-book`.
- Click opens the same deduplicated term id the tooltip came from (span `data-term-id`).
- Select-to-add panel: if the selected text is not in the book-scoped list, it now checks the full
  term list before offering "New term", so unlinked existing terms are opened instead of duplicated.

#### Acceptance tests (Flask test client, live Supabase, admin session) — all PASS
- Book 10 (入法門論) resolves to source 5 by title (trans_books.source_id is null).
- Book-scoped list (807 terms): 輪迴 → T002904 "Samsara (the cycle of rebirth)", 無始 → T002874
  "without beginning", 中陰 → T003074 "intermediate state (Bardo in Tibetan)", 修行 → T002894,
  法 → T002861 "Dharma", 傳法 → T002899 "transmit the Dharma".
- 學佛 and 道 not in the book-scoped list; no single unreviewed characters; no inactive terms.
- `?book_id=10&all=1` returns the same 3,797 terms as the old no-book call (superset of the book list).
- `get_translation_constraint_terms(prefer_source_id=5)`: 傳法 → "transmit the Dharma",
  成就 → "attainment" (Final, not the Known value), 輪迴 → T002904 text, 修行 → T002894 text.

**Browser test (local, 127.0.0.1:5000, 入法門論 ch. 01, 2026-11-02) — PASS:** tooltips show
"Final: …" for 輪迴/無始/中陰/傳法/修行/法; 學佛, 道, 成就 occur in the chapter but are not
underlined (360 underlines); "Show all vocabulary" ON → 514 underlines, other-book terms dotted,
setting survives a reload, OFF → back to 360; clicking 輪迴 opens T002904. Show-all mode is the
old list without deduplication, so there 輪迴 again shows the older T000911 (by design).
Select-to-add fallback not exercised.

Local login note: `.env` has the production `GOOGLE_REDIRECT_URI`; for local testing run with
`GOOGLE_REDIRECT_URI=http://127.0.0.1:5000/callback` and open http://127.0.0.1:5000 (not localhost).

### Stage F2 — Selectable Translation Engine: OpenAI (default) or Claude (2026-11-02)

Sentence translation can use OpenAI or Claude. **OpenAI is the default** (Vincent's choice:
Greg's good results with ChatGPT). Vocabulary AI functions and `group_sentences_by_topic` stay on
Claude Haiku, unchanged.

- **`config.py` / `.env.example`:** `DEFAULT_TRANSLATION_ENGINE` (default `openai`; `openai|claude`),
  `OPENAI_TRANSLATION_MODEL` (default `gpt-5.6-sol`), `CLAUDE_TRANSLATION_MODEL` (default
  `claude-opus-5-5`). `OPENAI_API_KEY` is shared with embeddings. Both default models confirmed
  available on our accounts (model list API, 2026-11-02).
- **`ai.py`:** `build_translate_prompt()` returns the exact previous prompt text;
  `_translate_with_openai()` uses the Responses API with `max_output_tokens` (GPT-5.x are reasoning
  models, so `max_tokens` does not apply); `_translate_with_claude()` joins the text blocks (Opus 5.5
  returns a thinking block first, which broke `content[0].text`). Limit: 2,000 visible tokens + 6,000
  reasoning headroom; 90 s client timeout. `translate_unit(..., engine=)` returns
  `{english, split_map, model}` and `error` on failure; provider errors are printed to the server log.
- **`routes/translate.py`:** `POST /api/trans/units/<id>/translate` takes `{"engine"}` (400 on other
  values). A failed draft writes nothing (400 for a missing key, 502 for a provider error) — before,
  a failure silently wrote an empty `english_final`. `ai_model` stores the real model; the response
  adds `engine` and `model`; the `[translate_unit]` log line shows both; the audit detail adds the
  model. `AI_MODEL_NAME` removed.
- **`templates/index.html`:** "AI engine" selector (OpenAI / Claude) in the Work on Units toolbar,
  preselected from `DEFAULT_TRANSLATION_ENGINE`, viewer's choice remembered in `localStorage`
  (`tcat_trans_engine`). Each unit shows "AI draft: <model>" under its translation. Errors show as a
  toast instead of an alert. `app.py` passes `default_translation_engine` to the template.
- **Timeouts:** `vercel.json` build config `maxDuration: 60`. GreenGeeks CGI has no app-side
  setting; drafts measured at 4–8 s, well inside Apache's limit.

#### Tests (2026-11-02)
- Flask test client, unit 354 (U000354 "一 先說大小法 又看邪與正", in_review): engine=openai → 200,
  `ai_model` = `gpt-5.6-sol`; no body → default openai; engine=gemini → 400; `OPENAI_API_KEY` unset →
  400 "OpenAI key not configured" with no write. **Unit 354 was restored** to its original
  english_final / english_draft / status / ai_model / split_map / translated_by / last_modified_*
  afterwards (verified). Three `ai_translate` audit rows from `f2-test@local` remain on U000354.
- engine=claude first failed (thinking block, see above); after the fix it was verified by calling
  `translate_unit()` directly (no DB write) — both engines return English for unit 354's text.
- Browser (local): selector defaults to OpenAI, switch is remembered, model labels render
  (e.g. "AI draft: claude-haiku-4-5-20251001"). AI Translate was not clicked in the browser (it
  would overwrite a live unit).
- Glossary note: both engines rendered 小法 as "A lesser teaching" (capital A), copied from the
  glossary constraint — worth checking that term's Final.

### Stage F3 — Better Prompt + Glossary Compliance Check (2026-11-02)

- **Prompt (`ai.build_translate_prompt`, both engines):** now returns `{system, user}` — system
  instructions (expert translator of Vajrayana / Chinese Buddhist teaching literature; faithful, no
  added content; natural English; split long sentences; translate only the target). Separate
  "REQUIRED TERMINOLOGY — reviewed by the translation team…" block, one term per line; alternatives
  say "choose the alternative that fits the context"; (noun)/(verb) labels explained as not part of
  the translation. Context = the whole paragraph (all units with the same chapter + paragraph_index,
  "context only"), plus the previous/next unit when it lies outside the paragraph. Style rules and
  RAG examples unchanged. Claude gets `system=`, OpenAI `instructions=`.
- **Constraint selection (`routes/translate._match_constraint_terms`):** longest match claims its
  characters, as the workspace underlines do, so 法 is not required inside 傳法 / 小法. Constraint
  items carry `term_id` (display_id) from `terms_repo.get_translation_constraint_terms`.
- **Compliance check (`ai.check_term_compliance`):** for each required term: case-insensitive,
  punctuation ignored, simple inflections allowed (transmit → transmitted, practice → practicing,
  being → beings), a leading infinitive "to" ignored, any ";"-separated option counts, usage labels
  not required. A rendering found without its parenthetical gloss is reported as `partial`
  ("gloss dropped"). Diacritics are required (Vajrayana ≠ Vajrayāna).
- **Retry:** any missing term → one more call naming the missing renderings; the draft with the
  lower score (missing = 1, partial = 0.5) is kept. Retry errors leave the first draft in place.
- **API:** `POST /api/trans/units/<id>/translate` response adds `missing_terms`
  `[{chinese, english, term_id, partial}]` (not stored). Log line adds `retried=yes|no missing=N`.
- **UI:** amber chips under the unit after AI Translate — "⚠ 傳法 → transmit the Dharma not used" or
  "… gloss dropped"; clicking opens the term. Chips disappear on reload (not stored, by design).

#### Tests (2026-11-02) — no DB writes
- Checker unit cases (offline): case/punctuation, missing, gloss dropped → partial, gloss kept,
  (verb) label, alternatives, inflections, plurals, diacritics — all pass.
- Unit 353 text (傳法), built exactly as the route builds it: OpenAI first wrote "transmitted the
  Dharma" (reported as missing before inflections were allowed → retry); Claude kept "transmit the
  Dharma" after a retry. Unit 351 text (中陰): both engines kept "intermediate state (Bardo in
  Tibetan)". Drafts took 11–26 s including a retry (within Vercel's 60 s).
- Browser (local): chips render for unit 353 with sample data and clicking 傳法 opens T002899; no
  console errors. A live AI Translate click with chips was not done (it would overwrite a unit).

### Stage F4 — Blind Engine Comparison for Reviewers (2026-11-02)

- **`scripts/compare_engines.py`** (new): `--book-id` (default 10), `--units` (default
  354,353,352,351,348,349,350 = 入法門論 sentences 1–7), `--seed` (repeatable A/B order). Builds
  constraints / context / style rules / RAG examples with the same functions as
  `api_translate_unit`, drafts with both engines in parallel, writes nothing to Supabase.
  Outputs `docs/compare_<date>.md` (Version A/B per sentence, random order, required terms and
  missing terms per version; send to reviewers) and `docs/compare_<date>_key.md` (engine per
  version, plus current T-CAT English for reference; keep back). Prints time and tokens per call.
- **`ai.py`**: `translate_unit` now also returns `usage` {calls, input_tokens, output_tokens},
  summed over the draft and any retry (OpenAI output includes reasoning).

#### Run 2026-11-02
- All 14 drafts succeeded first time, no retries, no missing glossary terms.
- Claude opus-5-5: 48.7 s total, 6,922 in / 4,956 out tokens. OpenAI gpt-5.6-sol: 41.2 s,
  4,716 in / 3,902 out. Slowest single call 12.2 s.
- Glossary data issue seen: 小法 → "A lesser teaching" (capital A) is copied verbatim mid-sentence
  ("disparages A lesser teaching"); the term's Known/Final text should be "a lesser teaching".

### Stage G1 — AI Translation Reasoning (2026-11-02)

First of three stages giving translators more to decide with (G1 reasoning, G2 notes,
G3 notes → Style Guide rule proposed by anyone, approved only by a Lead).

- **Migration 018 — `018_g1_ai_reasoning.sql`** (applied to TCAT-vocab 2026-11-02):
  `trans_units` gains `ai_reasoning jsonb`, `missing_terms jsonb`, `ai_translated_at timestamptz`.
- **`ai.py`**: the translate prompt now asks for `"reasoning"`: 2–4 notes under 25 words (key
  term choices, restructuring/splits, ambiguities and how they were resolved).
  `_parse_translation` returns `(english, split_map, reasoning)`, accepting a list or a
  newline string, capped at 4 notes × 300 chars. A retry keeps the reasoning of the draft kept.
  `translate_unit` returns `reasoning`.
- **`routes/translate.py`**: AI Translate saves `ai_reasoning`, `missing_terms` and
  `ai_translated_at` (re-translate overwrites them). Save re-runs `check_term_compliance` on
  changed text, so the F3 ⚠ chips now persist across reloads and clear once a term is fixed.
- **`templates/index.html`**: `_transReasoningHtml(u)` — collapsed `<details>` under the English
  box, "Why this translation (n) — AI draft, model · date"; open state kept across row re-renders
  (`_transReasonOpen`). Units drafted before G1 keep the plain "AI draft: model" line.
- **Tested**: parser on list / newline-string / missing reasoning; live local AI Translate on
  U000344 (OpenAI gpt-5.6-sol) returned 3 notes, saved and shown after reload, no console errors.
  Not tested live: Save re-check of missing terms (would change a unit's status).

### Stage G2 — Translator Notes per Unit (2026-11-02)

- **Migration 019 — `019_g2_unit_notes.sql`** (applied to TCAT-vocab 2026-11-02): new
  `trans_unit_notes` (unit_id → trans_units on delete cascade, note_text, author_email,
  author_name, created_at, rule_id → style_guide on delete set null — filled in G3).
- **`routes/translate.py`**: `GET /api/trans/units/<id>/notes` (any module user),
  `POST /api/trans/units/<id>/notes` (Member+, 2000 chars max), `DELETE /api/trans/notes/<id>`
  (author or Leader+). Add/delete write audit rows `note_added` / `note_deleted`.
  `GET /api/trans/chapters/<id>/units` now adds `note_count` per unit (one extra query; 0s if it fails).
- **`templates/index.html`**: "Notes (n)" button beside History on every Translation card;
  panel lists notes (author · time · text, "used in a rule" once G3 links it), 🗑 for the
  author or Leader/Admin, add box for Member+. Counts kept client-side (`_transNoteCounts`)
  because translate/save responses don't carry note_count; an open panel reloads after Save /
  Re-translate re-renders the card.
- **Tested** (local, live Supabase): add note on U000344 → "Notes (1)", author + time shown;
  delete → "Notes", server count 0, table empty again. No console errors from G2.

### Stage G3 — Notes → Style Guide Rule (2026-11-02)

- **Migration 020 — `020_g3_rule_proposals.sql`** (applied to TCAT-vocab 2026-11-02):
  `style_guide` gains `proposed boolean default false`, `book_id` (→ trans_books, on delete
  cascade; null = all books), `approved_by`, `approved_at`. `active` stays the only switch for
  prompt injection; a proposed rule is `active=false, proposed=true`.
- **`ai.py`**: `suggest_style_rules(notes, chinese_text, english_text, existing_rules)` —
  CLAUDE_TRANSLATION_MODEL; returns 0–2 rules {category, rule_text, example_before,
  example_after}, `term_notes` (notes about one term's rendering — glossary matters, not
  rules) and a one-line `comment`. Never raises.
- **`routes/translate.py`**:
  - `POST /api/trans/units/<id>/suggest-rule` (Member+): AI drafts from the unit's unused notes
    (`rule_id` null), given the book's active rules; writes nothing.
  - `POST /api/trans/styleguide` now accepts `book_id` and `note_ids`. **Leader+ → active at
    once** (approved_by set, no extra click). **Member → saved as proposed**, allowed only with
    note_ids. Notes are linked (`rule_id`) so they are not summarised twice.
  - `PATCH …/styleguide/<id>` with `active: true` also approves a proposed rule; accepts `book_id`.
  - `DELETE /api/trans/styleguide/<id>` (Leader+): permanent; its notes become unused again.
  - `_get_active_style_rules(book_id)`: global rules + that book's rules only.
    `api_translate_unit` and `scripts/compare_engines.py` pass the book.
  - `GET /api/trans/styleguide` embeds `trans_books(title)` for the scope badge.
- **`templates/index.html`**: "✦ Suggest rule from notes" in the Notes panel (only while unused
  notes exist) → `#sg-suggest-modal` with editable category / rule / examples, "Only <book>"
  (default on), Discard, and "Add rule" (Lead) / "Submit for Lead approval" (Member); term notes
  shown separately. Style Guide view: "Waiting for Lead approval (n)" section with Approve /
  Delete, book badge on scoped rules, Delete on every rule for Leaders.
- **Tested** (local, live Supabase, as admin): 2 test notes on U000344 → Suggest (≈7 s) → 1 rule +
  1 term note → Add rule → rule active immediately, book 10, both notes linked, Suggest button
  hidden; `_get_active_style_rules(10)` includes it, book 9 and global do not; Style Guide shows
  it with the 入法門論 badge; Delete → notes freed; test notes deleted (back to rules 2 and 3,
  no notes). Proposed-rule section checked with client-side sample data only — the Member
  submit path was not run (no Member login locally).
- **Follow-up (2026-11-02)**: the AI engine selector moved from the page toolbar to each card,
  just before AI Translate / Re-translate; all card selectors stay in sync (`transSetEngine`
  updates every `.trans-engine-select`; choice still saved in localStorage `tcat_trans_engine`).
  Card action rows now wrap on narrow screens.

---

## Known Issues / Notes

- `ftp.cyber-tech.com` does not resolve in DNS — raw IP `108.163.242.106` must be used
- `.htaccess` is not tracked in git (doesn't exist locally) — managed manually on server
- `venv/` exists on server alongside `venv310/` — only `venv310` is active; `venv/` may be an old artifact
- The `SamKirkland/FTP-Deploy-Action@v4.3.5` Node.js 20 deprecation warning is harmless now but will need updating before September 16, 2026 when GitHub removes Node.js 20 from runners
- `.ftp-deploy-sync-stat.json` on the server is created by the deploy action to track file state — do not delete it
- Supabase has a few stale sequences (`documents_id_seq`, `sources_id_seq1`, `terms_id_seq1`) left from
  earlier sessions — harmless, can be cleaned up later

---

## T-CAT Translation Module Roadmap

| Stage | Status | Summary |
|---|---|---|
| **T0** | **Done** | Schema, data migration, data layer rewrite, Sheets retirement |
| **T1** | **Done** | 5 translation tables verified + sequences; `segmenter.py` + 15 pytest cases passing |
| **T2** | **Done** | Access gate (admin-only routed via env flag), import pipeline, read-only Picker + chapter + sentence browse UI |
| **T2.1** | **Done** | Sentence-map column, trans_unit_drafts table, chapter upload → segmentation → drafts, AI topic grouping per paragraph, drag-and-drop review workspace, debounced auto-save, confirm → trans_units |
| **T3** | **Done (MVP)** | `translate_unit()` AI drafting + terminology constraints; save/approve endpoints writing `trans_revisions`; minimal per-unit textarea + button UI |
| **T4.1** | **Done** | Style guide CRUD (`/api/trans/styleguide`), leader-only management UI, prompt injection into `translate_unit()` |
| **T4.2** | **Done** | Dual-provider embeddings (Voyage + OpenAI, migration 010), `find_similar_revisions_*` RPCs, RAG example injection with cold-start similarity threshold, `scripts/compare_embedding_providers.py` |
| **T4.3** | Planned | Three-column review workspace polish, diff highlighting (english_draft vs english_final) |
| **G1** | **Done** | AI reasoning notes saved per unit and shown collapsed; F3 missing-term chips persisted and re-checked on Save (migration 018) |
| **G2** | **Done** | Translator notes per unit (`trans_unit_notes`, migration 019; "Notes (n)" beside History; author/Lead delete) |
| **G3** | **Done** | "Suggest rule from notes" → AI-drafted Style Guide rule; Lead's rule active at once, Member's proposed for Lead approval; Lead deletes; optional `book_id` scope (migration 020) |
| **T5** | Planned | Chapter claiming, collaborative approval flow, annotations (per-unit notes now come from G2) |

---

## Next Steps

- **G3 Member path live test**: sign in as a Member → add notes → Suggest → "Submit for Lead
  approval" → as Lead, Approve it in Style Guide → confirm it reaches the next AI Translate.
- **Send `docs/compare_2026-11-02.md` to Greg and Weiya** (not the `_key` file); pick the
  default engine from their verdicts.
- **Fix glossary entry 小法** → "a lesser teaching" (lower-case a).
- **Book Glossary live UI test** (backend fully verified via live Supabase + a real Flask
  test-client HTTP cycle, but never clicked through in an actual browser): open a book → Chapters
  → "📖 Glossary" button (Leader+ only — confirm it's absent for Members) → open a term from
  Review Vocabularies → "Add to Glossary" → Generate → edit the textarea → Mark Reviewed → back to
  Chapters → Glossary list → confirm the entry, badge, and preview text look right → click the row
  → confirm Previous/Next walks other glossary terms (not the chapter's terms) → Remove
- **Multi-source terms live UI test** (backend verified directly against Supabase, but not clicked through in the browser): open a term's edit view and confirm the multi-select shows its linked sources correctly and ctrl/cmd-click saves via `autoSaveSources()`; add a new term with 2+ sources selected; try the merge-duplicates modal and confirm the "Sources — combined automatically" row shows the right union
- **T4.1/T4.2 live testing** (nothing has touched these live yet — `style_guide` and embedding columns are still empty in Supabase):
  - Set at least one of `VOYAGE_API_KEY` / `OPENAI_API_KEY` in `.env`
  - Add a style guide rule as leader → run AI Translate on a unit → confirm the rule's language shows up in behavior (AI compliance isn't 100%, may need a few tries)
  - Edit + Approve a unit (changed text) → confirm a `trans_revisions` row is written with `embedding_voyage`/`embedding_openai` populated for whichever key(s) are set
  - Once 2-3 revisions have embeddings, run `python scripts/compare_embedding_providers.py` and eyeball Voyage vs OpenAI retrieval quality
  - Translate a new unit with a semantically similar confirmed one already in the corpus → confirm RAG examples get injected (and confirm nothing breaks when similarity is too low / no examples exist)
- **T3 live testing**: Start Flask server locally and test: open a confirmed chapter → AI Translate a unit → verify terminology constraints/context are applied → edit + Save → edit + Approve (leader) → verify a `trans_revisions` row was written
- **T2.1 data cleanup**: T2 test data (1 book, 35 chapters, 131 units) still in DB — run `python scripts/run_migration_007.py` with `DATABASE_URL` set, or execute `DELETE FROM trans_unit_drafts; DELETE FROM trans_units; DELETE FROM trans_chapters; DELETE FROM trans_books;` via Supabase SQL editor to clear before production use
- **T2.1 live testing**: Start Flask server locally and test: create book → upload chapter → open review view → run AI grouping → drag-drop → confirm → verify trans_units content
- **T4.3**: Three-column review workspace, diff highlighting — worth prompting for once T4.1/T4.2 are confirmed working live
- **Run backfill**: `python scripts/backfill_classification.py --dry-run --limit 20` (spot-check), then full run
- **T0 manual cleanup** (no code changes needed):
  - Export 7 Sheets worksheets as CSV → `backup/sheets_final_export_20260709/` (local only, do not commit)
  - SSH GreenGeeks: remove `SHEET_ID` from `.env`
  - SSH GreenGeeks: `rm ~/public_html/app.cyber-tech.com/credentials.json`
- **Maintenance**: upgrade `upload-artifact@v4` → `v5` before 2025-09-19; upgrade deploy action to Node.js 24 before Sep 2026
