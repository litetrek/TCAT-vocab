# Deployment

This app deploys to GreenGeeks shared hosting automatically via GitHub Actions
whenever code is pushed to the `main` branch. It still runs exactly as before —
CGI through `index.cgi` + `.htaccess`, same Google Sheets backend, same OAuth
config. Only *how the files get onto the server* has changed.

## How it works

1. You push to `main` (or merge a PR into it).
2. The workflow at `.github/workflows/deploy.yml` runs on GitHub's servers.
3. It connects to GreenGeeks over FTPS and syncs the repository contents to
   the app's directory on the server, using
   [SamKirkland/FTP-Deploy-Action](https://github.com/SamKirkland/FTP-Deploy-Action).
4. Certain files are **never synced**, so they're never touched or wiped on
   the server: `.git*`, `.github/`, `.env`, `.env.*`, `credentials.json`,
   `README.md`, and a few local-only dev notes (`claude.md`, `deploy_note.md`,
   `project-overview`, `project-revision`).
5. After syncing, the workflow does a `curl` health check against the live
   site URL. If it doesn't get back HTTP 200, the workflow run fails loudly —
   GitHub will email/notify you.
6. You can also trigger a deploy manually any time from the **Actions** tab
   on GitHub (`workflow_dispatch`), without needing a new commit.

The live `.env` and `credentials.json` on the GreenGeeks server are managed
**only** through cPanel/SFTP by hand — they are never part of this pipeline.

## Required GitHub secrets

Set these once under **Settings → Secrets and variables → Actions** on the
repo. Names only — see the checklist message for where to find each value:

- `FTP_HOST`
- `FTP_USERNAME`
- `FTP_PASSWORD`
- `FTP_PORT` *(optional — defaults to 21 if unset)*
- `FTP_REMOTE_DIR`
- `SITE_URL` — the full live URL the health check should curl, e.g.
  `https://app.cyber-tech.com`

## Emergency manual deploy (if Actions is down)

Fall back to the original FileZilla workflow described in `deploy_note.md`:
upload `app.py`, `index.cgi` (check line 1 first), `requirements.txt` (if
changed), `templates/`, and any static files — skipping `.env*`,
`credentials.json`, and `venv/`.

## Rolling back a bad deploy

```
git log                  # find the last known-good commit
git revert <bad-commit>  # creates a new commit undoing the change
git push origin main     # triggers a fresh deploy with the revert
```

`git revert` is preferred over `git reset --hard` + force-push because it
keeps history intact and triggers the normal deploy pipeline.

## Reminder

`.env` and `credentials.json` exist **only** on the GreenGeeks server and on
your local machine for dev. They must never be committed to git or synced by
this pipeline.
