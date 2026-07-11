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
│   └── 007_t2_1_sentence_map.sql     # T2.1: sentence_map column + trans_unit_drafts table
├── scripts/
│   ├── run_migration.py        # Applies 001_initial_schema.sql via DATABASE_URL / psycopg2
│   ├── run_migration_005.py    # T1: applies 005 + runs acceptance tests (insert/unique/fractional/cleanup)
│   ├── run_migration_006.py    # T2: applies 006 + runs 4 acceptance tests (import/list/section_type/cleanup)
│   ├── run_migration_007.py    # T2.1: applies 007 + 5 acceptance tests + T2 test data cleanup
│   ├── migrate_from_sheets.py  # T0-2: one-shot Sheets → Postgres migration
│   ├── migrate_extraction_only.py  # T0-4: re-migrate extraction data only
│   └── backfill_classification.py  # Backfill entity_type/subject_field for unclassified terms
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

## Supabase Database Schema (11 tables, all live)

**Project:** `TCAT-vocab` (id: `yvkadctkigkjtjmmxrqc`, region: us-west-1)
**Connection:** supabase-py HTTPS REST (port 443), `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` env vars

All tables use `id bigint generated always as identity` as internal PK and a `display_id`
text column (T000001 / D000001 / etc.) for human-facing IDs. Sequences are created for
each display_id to eliminate the race condition from the old Sheets "scan for max ID" pattern.

| Table | display_id prefix | Notes |
|---|---|---|
| `members` | — | email UNIQUE, role check constraint |
| `sources` | S000001 | |
| `terms` | T000001 | status check: pending/finalized; idx on chinese, status |
| `audit_log` | — | ts timestamptz; term_id is text (no FK — historical rows may ref deleted terms) |
| `ext_documents` | D000001 | |
| `ext_paragraphs` | — | FK → ext_documents(id); UNIQUE (document_id, paragraph_index) |
| `trans_books` | B000001 | FK → sources(id); status: active/archived |
| `trans_chapters` | C000001 | FK → trans_books(id); section_type + status check constraints |
| `trans_units` | U000001 | unit_order numeric (fractional indexing); `sentence_map jsonb` (original sentence list, added T2.1); embedding-ready |
| `trans_unit_drafts` | — | `(chapter_id, paragraph_index)` unique; `draft_groups jsonb`; status: pending/ai_suggested/human_adjusted/confirmed |
| `trans_revisions` | R000001 | embedding vector(1536) for pgvector RAG |
| `style_guide` | S000001 | active boolean; source_revision_ids bigint[] |

pgvector extension enabled for `trans_revisions.embedding`.

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
| **T3** | Planned | AI translation: draft English for each unit via Claude; write english_draft |
| **T4** | Planned | Translation UI: per-unit review, approve, revise workflow |
| **T5** | Planned | Style guide integration: RAG lookup on trans_revisions.embedding |

---

## Next Steps

- **T2.1 data cleanup**: T2 test data (1 book, 35 chapters, 131 units) still in DB — run `python scripts/run_migration_007.py` with `DATABASE_URL` set, or execute `DELETE FROM trans_unit_drafts; DELETE FROM trans_units; DELETE FROM trans_chapters; DELETE FROM trans_books;` via Supabase SQL editor to clear before production use
- **T2.1 live testing**: Start Flask server locally and test: create book → upload chapter → open review view → run AI grouping → drag-drop → confirm → verify trans_units content
- **T3**: AI translation — draft English for each unit via Claude; write `english_draft`; update status to `ai_drafted`
- **T4**: Translation UI — per-unit review, approve, revise workflow
- **Run backfill**: `python scripts/backfill_classification.py --dry-run --limit 20` (spot-check), then full run
- **T0 manual cleanup** (no code changes needed):
  - Export 7 Sheets worksheets as CSV → `backup/sheets_final_export_20260709/` (local only, do not commit)
  - SSH GreenGeeks: remove `SHEET_ID` from `.env`
  - SSH GreenGeeks: `rm ~/public_html/app.cyber-tech.com/credentials.json`
- **Maintenance**: upgrade `upload-artifact@v4` → `v5` before 2025-09-19; upgrade deploy action to Node.js 24 before Sep 2026
