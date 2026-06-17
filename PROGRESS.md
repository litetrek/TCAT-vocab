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
| Database | Google Sheets via gspread + service account |
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
├── sheets.py                   # Google Sheets client, all read/write helpers
├── ai.py                       # Anthropic Claude AI generation (Pinyin, Pali, Sanskrit, translations)
├── auth.py                     # Session helpers: is_logged_in, is_admin, is_leader
├── routes/
│   ├── __init__.py
│   ├── terms.py                # /api/terms/* endpoints
│   ├── members.py              # /api/members/* endpoints
│   ├── sources.py              # /api/sources + /api/init endpoints
│   └── extract.py              # /api/extract/* endpoints — Extraction module
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
- `.env` — dev environment secrets
- `.env.production` — production environment secrets (upload as `.env` on server)
- `.htaccess` — Apache rewrite rules (exists on server, managed manually)
- `venv/`, `venv310/` — Python virtual environments

---

## Google Sheets Structure

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
(must have Editor access on the Google Sheet)

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
| `SHEET_ID` | Google Sheet ID from URL |
| `SUPER_ADMIN_EMAIL` | Always-admin email address |
| `GOOGLE_REDIRECT_URI` | OAuth callback URL (differs dev vs prod) |
| `FLASK_ENV` | `development` or `production` |
| `PORT` | Local dev port (unused in CGI mode) |

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

---

## Known Issues / Notes

- `ftp.cyber-tech.com` does not resolve in DNS — raw IP `108.163.242.106` must be used
- `.htaccess` is not tracked in git (doesn't exist locally) — managed manually on server
- `venv/` exists on server alongside `venv310/` — only `venv310` is active; `venv/` may be an old artifact
- The `SamKirkland/FTP-Deploy-Action@v4.3.5` Node.js 20 deprecation warning is harmless now but will need updating before September 16, 2026 when GitHub removes Node.js 20 from runners
- `.ftp-deploy-sync-stat.json` on the server is created by the deploy action to track file state — do not delete it

---

## Next Steps

- Update actions to Node.js 24 before Sep 2026 deprecation deadline
- Confirm whether `venv/` on server can be removed (old virtual environment)
- Consider adding SSH access to GreenGeeks for future pipeline improvements
