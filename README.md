# T-CAT Buddhist Vocabulary

A collaborative web app for a team translating Chinese Buddhist texts into English.
Translators add terms; Claude AI generates Pinyin, Pali, Sanskrit, and three English
translation options; team members vote; a leader or admin finalises the winning choices.

---

## Tech Stack

| Layer    | Technology |
|----------|-----------|
| Backend  | Python / Flask |
| Auth     | Google OAuth 2.0 (Authlib) |
| Database | Google Sheets (gspread + service account) |
| AI       | Anthropic Claude (claude-haiku-4-5-20251001) |
| Frontend | Vanilla JS + HTML/CSS |
| Hosting  | GreenGeeks shared hosting via CGI (`index.cgi`) |

---

## File Structure

```
buddhist-vocab/
├── app.py              # Flask entry point: OAuth, auth routes, blueprint registration
├── config.py           # Constants, COL dict, schema headers, field maps, utilities
├── sheets.py           # Sheets client, accessors, write_audit, term/member helpers
├── ai.py               # Claude AI generation functions
├── auth.py             # is_logged_in, is_admin, is_leader
├── routes/
│   ├── terms.py        # /api/terms/* + /api/vote
│   ├── members.py      # /api/members/*
│   └── sources.py      # /api/sources + /api/init
├── index.cgi           # CGI entry point for GreenGeeks production
├── .htaccess           # Apache rewrite rules
├── credentials.json    # Google service account key  ← never commit
├── .env                # Dev environment variables    ← never commit
├── .env.production     # Production variables template
├── requirements.txt
├── import-template.csv # CSV template for bulk import
└── templates/
    ├── index.html      # Main app (single-page, vanilla JS)
    ├── login.html
    └── denied.html
```

---

## First-Time Setup

### 1. Google Sheets

1. Create a new Google Sheet at sheets.google.com.
2. Copy the Sheet ID from the URL:
   `https://docs.google.com/spreadsheets/d/<SHEET_ID>/edit`
3. Share the sheet with the service account (give it **Editor** access):
   `sheets-editor@warm-composite-494900-b0.iam.gserviceaccount.com`

### 2. Environment variables

Create `.env` in the project root:

```
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
SECRET_KEY=any-random-string
ANTHROPIC_API_KEY=...
SHEET_ID=your-sheet-id
SUPER_ADMIN_EMAIL=youremail@gmail.com   # always has admin access
GOOGLE_REDIRECT_URI=http://127.0.0.1:5000/callback
```

For production, copy this file to `.env` on the server and set:
```
FLASK_ENV=production
GOOGLE_REDIRECT_URI=https://your-domain.com/callback
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run locally

```bash
python app.py
```

Open `http://127.0.0.1:5000` in your browser.

### 5. Initialise Google Sheets

Log in as the super admin, then click **⚙ Init Sheets** in the sidebar.
This creates all five worksheets with correct headers and seeds the super admin
in the Members sheet. It is safe to run again — it only adds missing columns.

### 6. Add team members and sources

- Open **☷ Team** to add members and assign roles (member / leader / admin).
- Open **⊕ Sources** to register the source texts your team is working from.

---

## Google Sheets Structure

Five worksheets inside one Google Sheet:

**Terms** (26 columns)
`ID | Chinese | Pinyin | Pali | Sanskrit | Context | Category | Notes |`
`Translation1 | Translation2 | Translation3 | Final | Status | AddedBy | Timestamp |`
`TranslationKnown | Source | TranslationFirst | TranslationSecond |`
`TranslationOther1 | TranslationOther2 | LastModifiedBy | LastModifiedTime |`
`RomanizationPlain | SourceContentChinese | SourceContentEnglish`

**Votes** (3 columns): `TermID | VoterEmail | ChosenTranslation`

**Members** (6 columns): `Email | Role | AddedBy | AddedAt | Name | ShortName`

**Sources** (4 columns): `SourceID | SourceName | SourceType | Notes`

**Audit_Log** (11 columns): `AuditID | Timestamp | TermID | TermChinese | UserEmail | UserName | ActionType | FieldChanged | OldValue | NewValue | Details`

---

## Bulk CSV Import

Upload via **+ Add Term → Bulk Import (CSV)**. Only `chinese` is required.
AI fills Pinyin, Pali, Sanskrit, and AI Translate 1–3 automatically.

| Column | Aliases | Notes |
|--------|---------|-------|
| `chinese` | `Chinese` | Required |
| `pinyin` | `Pinyin` | AI-generated if blank |
| `pali` | `Pali` | AI-generated if blank |
| `sanskrit` | `Sanskrit` | AI-generated if blank |
| `context` | `Context` | Passed to AI as hint |
| `category` | `Category` | Stored as-is |
| `notes` | `Notes` | Passed to AI as hint |
| `source` | `Source` | SourceID e.g. `S001` |
| `trans_known` | `TranslationKnown`, `known` | Known translation |
| `added_by` | `AddedBy` | Defaults to logged-in user |

See `import-template.csv` for a ready-to-use template.

Save CSV files as **UTF-8** (not UTF-16). If saved on Windows, the app
automatically strips the BOM (`utf-8-sig`).

---

## User Roles

| Role | Capabilities |
|------|-------------|
| **Member** | View terms, vote, edit unlocked fields, add terms |
| **Leader** | All member capabilities + set Final (First/Second) + reset finalization |
| **Admin** | All leader capabilities + manage team members and sources + Init Sheets |

`SUPER_ADMIN_EMAIL` always has admin access regardless of the Members sheet.

---

## Deploying to GreenGeeks (CGI)

1. Upload all files via FTP or Git (exclude `.env` and `credentials.json` from Git).
2. Upload `.env` and `credentials.json` directly via FTP — keep them outside `public_html`.
3. Set `FLASK_ENV=production` and the correct `GOOGLE_REDIRECT_URI` in `.env`.
4. Install dependencies via SSH:
   ```bash
   pip install -r requirements.txt
   ```
5. Apache serves the app via `index.cgi` using the `StripScriptName` WSGI wrapper.
   The `.htaccess` file routes all requests through it.
