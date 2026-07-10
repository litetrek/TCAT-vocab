"""
scripts/migrate_extraction_only.py
===================================
Migrate ExtractionDocuments and ExtractionParagraphs from Google Sheets
into ext_documents and ext_paragraphs in Supabase Postgres.

Use when those two tables are empty but all other tables already have data.

Usage:
    python scripts/migrate_extraction_only.py [--dry-run]

Flags:
    --dry-run   Read and print counts; do NOT write to database.

Required env vars (in .env):
    SHEET_ID                       Google Sheet ID
    DATABASE_URL                   pgBouncer pooled connection (port 6543)
    GOOGLE_SERVICE_ACCOUNT_FILE    path to credentials.json (default: credentials.json)
"""

import argparse
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("migrate_extraction")

BASE_DIR = Path(__file__).parent.parent
NUMERIC_RE = re.compile(r"(\d+)$")


def _null(val):
    if val in (None, ""):
        return None
    return str(val).strip() or None


def _int_or_none(val, default=0):
    if val in (None, ""):
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _parse_ts(raw):
    if raw in (None, ""):
        return None
    raw = str(raw).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%dT%H:%M", "%m/%d/%Y %H:%M:%S", "%m/%d/%Y %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).isoformat()
        except ValueError:
            pass
    try:
        from dateutil import parser as dp
        return dp.parse(raw).isoformat()
    except Exception:
        pass
    log.warning("Could not parse timestamp: %r", raw)
    return None


def preflight():
    sheet_id = os.environ.get("SHEET_ID")
    db_url   = os.environ.get("DATABASE_URL")
    sa_file  = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE", "credentials.json")

    missing = [v for v in ["SHEET_ID", "DATABASE_URL"] if not os.environ.get(v)]
    if missing:
        print(f"ERROR: missing env var(s): {', '.join(missing)}")
        sys.exit(1)

    sa_path = Path(sa_file) if Path(sa_file).is_absolute() else BASE_DIR / sa_file
    if not sa_path.exists():
        print(f"ERROR: service account file not found: {sa_path}")
        sys.exit(1)

    return sheet_id, db_url, str(sa_path)


def read_worksheet(wb, name):
    ws = wb.worksheet(name)
    records = ws.get_all_records(numericise_ignore=["all"])
    log.info("Read %d rows from '%s'", len(records), name)
    return records


def transform_documents(records):
    rows, skipped = [], 0
    for i, r in enumerate(records, start=2):
        display_id = _null(r.get("DocumentID", ""))
        title      = _null(r.get("Title", ""))
        if not display_id or not title:
            log.warning("Row %d: missing DocumentID or Title, skipped", i)
            skipped += 1
            continue
        rows.append({
            "display_id":      display_id,
            "title":           title,
            "source_name":     _null(r.get("SourceName", "")),
            "paragraph_count": _int_or_none(r.get("ParagraphCount", ""), 0),
            "uploaded_by":     _null(r.get("UploadedBy", "")),
            "uploaded_at":     _parse_ts(r.get("UploadedAt", "")),
            "last_viewed_index": _int_or_none(r.get("LastViewedIndex", ""), 0),
            "status":          _null(r.get("Status", "")) or "active",
        })
    return rows, skipped


def transform_paragraphs(records, doc_id_map):
    rows, skipped = [], 0
    skipped_docs = set()
    for i, r in enumerate(records, start=2):
        display_doc_id = _null(r.get("DocumentID", ""))
        if not display_doc_id:
            skipped += 1
            continue
        internal_id = doc_id_map.get(display_doc_id)
        if internal_id is None:
            if display_doc_id not in skipped_docs:
                log.warning("DocumentID '%s' not in ext_documents, paragraphs skipped", display_doc_id)
                skipped_docs.add(display_doc_id)
            skipped += 1
            continue
        rows.append({
            "document_id":     internal_id,
            "paragraph_index": _int_or_none(r.get("ParagraphIndex", ""), 0),
            "chinese_text":    _null(r.get("ChineseText", "")),
            "english_text":    _null(r.get("EnglishText", "")),
        })
    return rows, skipped


def insert_documents(conn, rows, dry_run):
    if dry_run or not rows:
        return {}
    id_map = {}
    with conn.cursor() as cur:
        for row in rows:
            cur.execute(
                "INSERT INTO ext_documents "
                "(display_id, title, source_name, paragraph_count, "
                " uploaded_by, uploaded_at, last_viewed_index, status) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id, display_id",
                (row["display_id"], row["title"], row["source_name"],
                 row["paragraph_count"], row["uploaded_by"], row["uploaded_at"],
                 row["last_viewed_index"], row["status"])
            )
            result = cur.fetchone()
            id_map[result[1]] = result[0]
    conn.commit()
    return id_map


def insert_paragraphs(conn, rows, dry_run):
    if dry_run or not rows:
        return 0
    BATCH = 200
    total = 0
    with conn.cursor() as cur:
        for i in range(0, len(rows), BATCH):
            batch = rows[i:i + BATCH]
            args = [(r["document_id"], r["paragraph_index"],
                     r["chinese_text"], r["english_text"]) for r in batch]
            cur.executemany(
                "INSERT INTO ext_paragraphs "
                "(document_id, paragraph_index, chinese_text, english_text) "
                "VALUES (%s, %s, %s, %s)",
                args
            )
            total += len(batch)
    conn.commit()
    return total


def calibrate_sequence(conn, doc_rows, dry_run):
    if not doc_rows:
        return
    best = 0
    for r in doc_rows:
        m = NUMERIC_RE.search(str(r.get("display_id") or ""))
        if m:
            best = max(best, int(m.group(1)))
    log.info("Calibrating seq_ext_documents_display → %d", best)
    if not dry_run:
        with conn.cursor() as cur:
            cur.execute("SELECT setval('seq_ext_documents_display', %s, true)", (best,))
        conn.commit()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    sheet_id, db_url, sa_path = preflight()

    # ── Connect to Google Sheets ──────────────────────────────────────────────
    import gspread
    from google.oauth2.service_account import Credentials
    scopes = ["https://spreadsheets.google.com/feeds",
              "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file(sa_path, scopes=scopes)
    gc    = gspread.authorize(creds)
    wb    = gc.open_by_key(sheet_id)

    raw_docs  = read_worksheet(wb, "ExtractionDocuments")
    raw_paras = read_worksheet(wb, "ExtractionParagraphs")

    doc_rows,  doc_skipped  = transform_documents(raw_docs)
    log.info("Documents ready: %d rows (%d skipped)", len(doc_rows), doc_skipped)

    if args.dry_run:
        log.info("[DRY RUN] Would insert %d documents", len(doc_rows))
        log.info("[DRY RUN] Would insert %d paragraphs (approx)", len(raw_paras))
        return

    # ── Connect to Postgres ───────────────────────────────────────────────────
    import psycopg2
    conn = psycopg2.connect(db_url)

    # Safety check: refuse if ext_documents already has data
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM ext_documents")
        existing = cur.fetchone()[0]
    if existing > 0:
        print(f"ERROR: ext_documents already has {existing} rows. "
              "Truncate first if you want to re-migrate.")
        conn.close()
        sys.exit(1)

    doc_id_map = insert_documents(conn, doc_rows, dry_run=False)
    log.info("Inserted %d documents", len(doc_id_map))

    para_rows, para_skipped = transform_paragraphs(raw_paras, doc_id_map)
    log.info("Paragraphs ready: %d rows (%d skipped)", len(para_rows), para_skipped)

    n_para = insert_paragraphs(conn, para_rows, dry_run=False)
    log.info("Inserted %d paragraphs", n_para)

    calibrate_sequence(conn, doc_rows, dry_run=False)

    conn.close()

    print("\n── Result ───────────────────────────────────────────────────────────")
    print(f"  ext_documents:  {len(doc_id_map)} rows inserted")
    print(f"  ext_paragraphs: {n_para} rows inserted")
    print("Done.")


if __name__ == "__main__":
    main()
