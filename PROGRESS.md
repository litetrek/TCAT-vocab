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
├── sheets.py                   # Google Sheets client (to be retired in T0-5)
├── db.py                       # psycopg2 connection helpers: get_conn(), generate_display_id()
├── ai.py                       # Anthropic Claude AI generation (Pinyin, Pali, Sanskrit, translations)
├── auth.py                     # Session helpers: is_logged_in, is_admin, is_leader
├── routes/
│   ├── __init__.py
│   ├── terms.py                # /api/terms/* endpoints
│   ├── members.py              # /api/members/* endpoints
│   ├── sources.py              # /api/sources + /api/init endpoints
│   └── extract.py              # /api/extract/* endpoints — Extraction module
├── repositories/               # psycopg2 data-access layer — pure Postgres, no Sheets mirror
│   ├── __init__.py
│   ├── members_repo.py
│   ├── sources_repo.py
│   ├── terms_repo.py
│   ├── extraction_repo.py
│   └── audit_repo.py
├── migrations/
│   └── 001_initial_schema.sql  # Full Postgres DDL — 11 tables per design guide
├── scripts/
│   └── run_migration.py        # Applies 001_initial_schema.sql via DATABASE_URL / psycopg2
├── index.cgi                   # CGI entry point (shebang: venv310/bin/python3.10)
├── templates/
│   ├── index.html              # Main app UI — two top-level tabs: Extraction and Vocabulary
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

## Supabase Database Schema (T0 target — 11 tables)

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
| `trans_units` | U000001 | unit_order numeric (fractional indexing); split_map jsonb; embedding-ready |
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

---

## Known Issues / Notes

- `ftp.cyber-tech.com` does not resolve in DNS — raw IP `108.163.242.106` must be used
- `.htaccess` is not tracked in git (doesn't exist locally) — managed manually on server
- `venv/` exists on server alongside `venv310/` — only `venv310` is active; `venv/` may be an old artifact
- The `SamKirkland/FTP-Deploy-Action@v4.3.5` Node.js 20 deprecation warning is harmless now but will need updating before September 16, 2026 when GitHub removes Node.js 20 from runners
- `.ftp-deploy-sync-stat.json` on the server is created by the deploy action to track file state — do not delete it
- Supabase has a few stale sequences (`documents_id_seq`, `sources_id_seq1`, `terms_id_seq1`) left from
  earlier sessions — harmless, can be cleaned up in T0-5

---

## T0 Migration Roadmap

| Sub-stage | Status | Summary |
|---|---|---|
| **T0-1 Schema** | **Done** | 11 tables built in Supabase per design guide DDL |
| **T0-2 Migration script** | **Done** | gspread → Postgres; 2844 terms + 5 other tables; Votes → CSV; sequences calibrated |
| **T0-3 Data layer rewrite** | **Done** | db.py + all repositories rewritten to supabase-py HTTPS REST; routes/ untouched; RPC functions for atomicity |
| **T0-4 Cutover** | **In Progress** | Code ready; pending: clean data migration → server pip install → production env vars → deploy → verify |
| **T0-5 Cleanup** | Pending | Retire Sheets, weekly pg_dump backup, remove gspread from requirements |

## Next Steps

- **T0-4**: Server steps remaining:
  1. Step 0 — TRUNCATE all data tables + re-run `scripts/migrate_from_sheets.py --force`; verify row counts match Sheets; confirm no test IDs
  2. Step 1 — Freeze Sheets writes (coordinate with team)
  3. Step 2 — SSH to GreenGeeks → `venv310/bin/pip install -r requirements.txt` (installs `supabase`; psycopg2-binary removed from requirements)
  4. Step 3 — Add `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` to production `.env` (no `DATABASE_URL` needed in production)
  5. Step 4 — Push to `main` to trigger Actions deploy; record rollback commit hash
  6. Step 5 — Online verification checklist at https://app.cyber-tech.com
- Update deploy action to Node.js 24 before Sep 2026 deprecation deadline
- Confirm whether `venv/` on server can be removed (old virtual environment)
