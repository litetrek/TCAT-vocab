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
│   └── sources.py              # /api/sources + /api/init endpoints
├── index.cgi                   # CGI entry point (shebang: venv310/bin/python3.10)
├── templates/
│   ├── index.html              # Main app UI (single-page, vanilla JS)
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

One Google Sheet with five worksheets:

| Sheet | Key Columns |
|-------|------------|
| **Terms** | ID, Chinese, Pinyin, Pali, Sanskrit, Context, Category, Notes, Translation1–3, Final, Status, AddedBy, Timestamp, TranslationKnown, Source, TranslationFirst/Second, TranslationOther1/2, LastModifiedBy/Time, RomanizationPlain, SourceContentChinese/English |
| **Votes** | TermID, VoterEmail, ChosenTranslation *(deprecated — worksheet preserved but unused since Stage 3)* |
| **Members** | Email, Role, AddedBy, AddedAt, Name, ShortName |
| **Sources** | SourceID, SourceName, SourceType, Notes |
| **Audit_Log** | AuditID, Timestamp, TermID, TermChinese, UserEmail, UserName, ActionType, FieldChanged, OldValue, NewValue, Details |

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

---

## Known Issues / Notes

- `ftp.cyber-tech.com` does not resolve in DNS — raw IP `108.163.242.106` must be used
- `.htaccess` is not tracked in git (doesn't exist locally) — managed manually on server
- `venv/` exists on server alongside `venv310/` — only `venv310` is active; `venv/` may be an old artifact
- The `SamKirkland/FTP-Deploy-Action@v4.3.5` Node.js 20 deprecation warning is harmless now but will need updating before September 16, 2026 when GitHub removes Node.js 20 from runners
- `.ftp-deploy-sync-stat.json` on the server is created by the deploy action to track file state — do not delete it

---

## Next Steps (not yet started)

- Update actions to Node.js 24 before Sep 2026 deprecation deadline
- Confirm whether `venv/` on server can be removed (old virtual environment)
- Consider adding SSH access to GreenGeeks for future pipeline improvements
