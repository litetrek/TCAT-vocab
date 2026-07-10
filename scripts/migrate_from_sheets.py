"""
scripts/migrate_from_sheets.py
==============================
One-shot migration: Google Sheets → Supabase Postgres.

Reads six worksheets from the existing Google Sheet, cleans the data, and
inserts it into the 11-table schema defined in migrations/001_initial_schema.sql.
Votes worksheet is exported to CSV only (not inserted into Postgres).

Usage:
    pip install gspread psycopg2-binary python-dotenv python-dateutil
    python scripts/migrate_from_sheets.py [--force] [--dry-run]

Flags:
    --force     Override the safety guard that refuses to run if any target
                table already has rows.
    --dry-run   Read and clean Sheets data; print row counts and warnings;
                do NOT write anything to Postgres or disk.

Required env vars (all in .env):
    SHEET_ID                       Google Sheet ID
    DATABASE_URL                   pgBouncer pooled connection (port 6543)
    GOOGLE_SERVICE_ACCOUNT_FILE    path to credentials.json (default: credentials.json)
"""

import argparse
import csv
import logging
import os
import random
import re
import sys
from datetime import date, datetime
from pathlib import Path

# Force UTF-8 output on Windows so Unicode chars (checkmarks, box lines) print correctly
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── Logging setup ─────────────────────────────────────────────────────────────

BASE_DIR   = Path(__file__).parent.parent
ERROR_LOG  = BASE_DIR / "migration_errors.log"
BACKUP_DIR = BASE_DIR / "backup"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("migrate")

error_logger = logging.getLogger("errors")
error_logger.setLevel(logging.WARNING)
error_handler = logging.FileHandler(ERROR_LOG, encoding="utf-8")
error_handler.setFormatter(logging.Formatter("%(asctime)s  %(message)s"))
error_logger.addHandler(error_handler)
error_logger.propagate = False


# ── Constants ─────────────────────────────────────────────────────────────────

VALID_ROLES   = {"viewer", "depositor", "member", "leader", "admin"}
VALID_STATUSES = {"pending", "finalized"}
NUMERIC_RE    = re.compile(r"(\d+)$")
BATCH_SIZE    = 200


# ── Helpers ───────────────────────────────────────────────────────────────────

def _null(val):
    """Convert empty string → None; pass through everything else."""
    if val in (None, ""):
        return None
    return str(val).strip() or None


def _int_or_none(val, default=None):
    if val in (None, ""):
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _parse_ts(raw, context=""):
    """Parse a Sheets timestamp string to ISO 8601. Returns None on failure."""
    if raw in (None, ""):
        return None
    raw = str(raw).strip()
    if not raw:
        return None
    # Try common formats Sheets produces
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(raw, fmt).isoformat()
        except ValueError:
            pass
    # Last resort: dateutil
    try:
        from dateutil import parser as dp
        return dp.parse(raw).isoformat()
    except Exception:
        pass
    error_logger.warning("Could not parse timestamp '%s'%s", raw,
                         f" in {context}" if context else "")
    return None


def _max_numeric(rows, id_field):
    """Return the highest numeric suffix among IDs like 'T000042' → 42."""
    best = 0
    for row in rows:
        m = NUMERIC_RE.search(str(row.get(id_field) or ""))
        if m:
            best = max(best, int(m.group(1)))
    return best


def _chunked(lst, size):
    for i in range(0, len(lst), size):
        yield lst[i : i + size]


# ── Pre-flight checks ─────────────────────────────────────────────────────────

def preflight_env():
    """Return (sheet_id, db_url, sa_file) or print errors and exit."""
    sheet_id = os.environ.get("SHEET_ID")
    db_url   = os.environ.get("DATABASE_URL")
    sa_file  = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE", "credentials.json")

    missing = []
    if not sheet_id:
        missing.append("SHEET_ID")
    if not db_url:
        missing.append("DATABASE_URL")
    if missing:
        print(f"ERROR: missing required env var(s): {', '.join(missing)}")
        print("Add them to your local .env file.")
        sys.exit(1)

    sa_path = Path(sa_file) if Path(sa_file).is_absolute() else BASE_DIR / sa_file
    if not sa_path.exists():
        print(f"ERROR: Google service account file not found: {sa_path}")
        sys.exit(1)

    log.info("Env check passed. SHEET_ID=%s  SA=%s", sheet_id, sa_path.name)
    return sheet_id, db_url, str(sa_path)


def preflight_tables(conn, force):
    """Refuse to run if any existing-system table already has rows."""
    import psycopg2.extras
    target_tables = ["members", "sources", "terms", "audit_log",
                     "ext_documents", "ext_paragraphs"]
    non_empty = []
    with conn.cursor() as cur:
        for tbl in target_tables:
            cur.execute(f"SELECT count(*) FROM {tbl}")
            cnt = cur.fetchone()[0]
            if cnt > 0:
                non_empty.append((tbl, cnt))

    if non_empty:
        print("\n⚠  The following tables already contain data:")
        for tbl, cnt in non_empty:
            print(f"   {tbl}: {cnt} row(s)")
        if force:
            print("   --force flag detected. Continuing — duplicate UNIQUE values may cause errors.\n")
        else:
            print("\nAbort. Re-run with --force to override this guard.\n")
            sys.exit(1)


# ── Sheets reader ─────────────────────────────────────────────────────────────

def open_sheet(sheet_id, sa_file):
    import gspread
    from google.oauth2.service_account import Credentials
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds  = Credentials.from_service_account_file(sa_file, scopes=scopes)
    gc     = gspread.authorize(creds)
    wb     = gc.open_by_key(sheet_id)
    log.info("Opened Google Sheet: %s", wb.title)
    return wb


def read_worksheet(wb, name):
    """Return list-of-dicts for worksheet name, or [] if not found."""
    try:
        ws = wb.worksheet(name)
        records = ws.get_all_records(default_blank="")
        log.info("  %s: %d row(s) read", name, len(records))
        return records
    except Exception as exc:
        log.warning("  %s: could not read — %s", name, exc)
        return []


# ── Row transformers ──────────────────────────────────────────────────────────

def transform_members(records):
    rows, warnings = [], []
    for i, r in enumerate(records, start=2):
        email = _null(r.get("Email", ""))
        if not email:
            error_logger.warning("Members row %d: no email, skipped. Raw=%s", i, r)
            warnings.append(f"Row {i}: no email")
            continue
        role_raw = str(r.get("Role", "")).strip().lower()
        if role_raw not in VALID_ROLES:
            msg = f"Members row {i}: unknown role '{r.get('Role')}' for {email}, skipped"
            error_logger.warning(msg)
            warnings.append(msg)
            continue
        rows.append({
            "email":      email.lower(),
            "role":       role_raw,
            "name":       _null(r.get("Name")),
            "short_name": _null(r.get("ShortName")),
            "added_by":   _null(r.get("AddedBy")),
            "added_at":   _parse_ts(r.get("AddedAt"), f"Members row {i} AddedAt"),
        })
    return rows, warnings


def transform_sources(records):
    rows, warnings = [], []
    for i, r in enumerate(records, start=2):
        src_name = _null(r.get("SourceName", ""))
        if not src_name:
            error_logger.warning("Sources row %d: no SourceName, skipped. Raw=%s", i, r)
            warnings.append(f"Row {i}: no SourceName")
            continue
        rows.append({
            "display_id":  _null(r.get("SourceID")),
            "source_name": src_name,
            "source_type": _null(r.get("SourceType")),
            "notes":       _null(r.get("Notes")),
        })
    return rows, warnings


def transform_terms(records):
    rows, warnings = [], []
    for i, r in enumerate(records, start=2):
        display_id = _null(r.get("ID", ""))
        chinese    = _null(r.get("Chinese", ""))
        if not display_id or not chinese:
            error_logger.warning("Terms row %d: missing ID or Chinese, skipped. Raw=%s", i, r)
            warnings.append(f"Row {i}: missing ID or Chinese")
            continue

        status_raw = str(r.get("Status", "")).strip().lower()
        if status_raw not in VALID_STATUSES:
            # Default to pending for unexpected values; log it
            if status_raw:
                error_logger.warning(
                    "Terms row %d ID=%s: unexpected status '%s', mapped to 'pending'",
                    i, display_id, r.get("Status"))
                warnings.append(f"Row {i} {display_id}: status '{r.get('Status')}' → 'pending'")
            status_raw = "pending"

        rows.append({
            "display_id":             display_id,
            "chinese":                chinese,
            "pinyin":                 _null(r.get("Pinyin")),
            "pali":                   _null(r.get("Pali")),
            "sanskrit":               _null(r.get("Sanskrit")),
            "context":                _null(r.get("Context")),
            "category":               _null(r.get("Category")),
            "notes":                  _null(r.get("Notes")),
            "translation1":           _null(r.get("Translation1")),
            "translation2":           _null(r.get("Translation2")),
            "translation3":           _null(r.get("Translation3")),
            "final":                  _null(r.get("Final")),
            "status":                 status_raw,
            "added_by":               _null(r.get("AddedBy")),
            "added_at":               _parse_ts(r.get("Timestamp"), f"Terms row {i} Timestamp"),
            "translation_known":      _null(r.get("TranslationKnown")),
            "source":                 _null(r.get("Source")),
            "translation_first":      _null(r.get("TranslationFirst")),
            "translation_second":     _null(r.get("TranslationSecond")),
            "translation_other1":     _null(r.get("TranslationOther1")),
            "translation_other2":     _null(r.get("TranslationOther2")),
            "last_modified_by":       _null(r.get("LastModifiedBy")),
            "last_modified_at":       _parse_ts(r.get("LastModifiedTime"), f"Terms row {i} LastModifiedTime"),
            "romanization_plain":     _null(r.get("RomanizationPlain")),
            "source_content_chinese": _null(r.get("SourceContentChinese")),
            "source_content_english": _null(r.get("SourceContentEnglish")),
        })
    return rows, warnings


def transform_audit_log(records):
    rows, warnings = [], []
    for i, r in enumerate(records, start=2):
        ts = _parse_ts(r.get("Timestamp"), f"Audit_Log row {i} Timestamp")
        rows.append({
            "ts":            ts,
            "term_id":       _null(r.get("TermID")),
            "term_chinese":  _null(r.get("TermChinese")),
            "user_email":    _null(r.get("UserEmail")),
            "user_name":     _null(r.get("UserName")),
            "action_type":   _null(r.get("ActionType")),
            "field_changed": _null(r.get("FieldChanged")),
            "old_value":     _null(r.get("OldValue")),
            "new_value":     _null(r.get("NewValue")),
            "details":       _null(r.get("Details")),
        })
    return rows, warnings


def transform_ext_documents(records):
    rows, warnings = [], []
    for i, r in enumerate(records, start=2):
        display_id = _null(r.get("DocumentID", ""))
        title      = _null(r.get("Title", ""))
        if not display_id or not title:
            error_logger.warning(
                "ExtractionDocuments row %d: missing DocumentID or Title, skipped", i)
            warnings.append(f"Row {i}: missing DocumentID or Title")
            continue
        rows.append({
            "display_id":        display_id,
            "title":             title,
            "source_name":       _null(r.get("SourceName")),
            "paragraph_count":   _int_or_none(r.get("ParagraphCount"), 0),
            "uploaded_by":       _null(r.get("UploadedBy")),
            "uploaded_at":       _parse_ts(r.get("UploadedAt"), f"ExtDoc row {i} UploadedAt"),
            "last_viewed_index": _int_or_none(r.get("LastViewedIndex"), 0),
            "status":            _null(r.get("Status")) or "active",
        })
    return rows, warnings


def transform_ext_paragraphs(records, doc_display_to_id):
    """
    doc_display_to_id: dict mapping display_id (D000001) → internal bigint id.
    """
    rows, warnings, skipped_doc = [], [], set()
    for i, r in enumerate(records, start=2):
        display_doc_id = _null(r.get("DocumentID", ""))
        if not display_doc_id:
            error_logger.warning("ExtParagraphs row %d: no DocumentID, skipped", i)
            warnings.append(f"Row {i}: no DocumentID")
            continue

        internal_id = doc_display_to_id.get(display_doc_id)
        if internal_id is None:
            if display_doc_id not in skipped_doc:
                error_logger.warning(
                    "ExtParagraphs: DocumentID '%s' not found in ext_documents, "
                    "all its paragraphs skipped", display_doc_id)
                warnings.append(f"DocumentID '{display_doc_id}' not in ext_documents (paragraphs skipped)")
                skipped_doc.add(display_doc_id)
            continue

        para_index = _int_or_none(r.get("ParagraphIndex"))
        if para_index is None:
            error_logger.warning("ExtParagraphs row %d: invalid ParagraphIndex, skipped", i)
            warnings.append(f"Row {i}: invalid ParagraphIndex")
            continue

        rows.append({
            "document_id":     internal_id,
            "paragraph_index": para_index,
            "chinese_text":    _null(r.get("ChineseText")),
            "english_text":    _null(r.get("EnglishText")),
        })
    return rows, warnings


# ── Postgres inserters ────────────────────────────────────────────────────────

def _insert_batch(cur, table, columns, rows):
    """Batch INSERT using executemany. Returns count of inserted rows."""
    if not rows:
        return 0
    placeholders = ", ".join(["%s"] * len(columns))
    col_list     = ", ".join(columns)
    sql = f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})"
    data = [[row[c] for c in columns] for row in rows]
    inserted = 0
    for chunk in _chunked(data, BATCH_SIZE):
        cur.executemany(sql, chunk)
        inserted += len(chunk)
    return inserted


def insert_members(conn, rows, dry_run):
    cols = ["email", "role", "name", "short_name", "added_by", "added_at"]
    if dry_run:
        return len(rows)
    with conn.cursor() as cur:
        n = _insert_batch(cur, "members", cols, rows)
    conn.commit()
    return n


def insert_sources(conn, rows, dry_run):
    cols = ["display_id", "source_name", "source_type", "notes"]
    if dry_run:
        return len(rows)
    with conn.cursor() as cur:
        n = _insert_batch(cur, "sources", cols, rows)
    conn.commit()
    return n


def insert_terms(conn, rows, dry_run):
    cols = [
        "display_id", "chinese", "pinyin", "pali", "sanskrit",
        "context", "category", "notes",
        "translation1", "translation2", "translation3",
        "final", "status", "added_by", "added_at",
        "translation_known", "source",
        "translation_first", "translation_second",
        "translation_other1", "translation_other2",
        "last_modified_by", "last_modified_at",
        "romanization_plain", "source_content_chinese", "source_content_english",
    ]
    if dry_run:
        return len(rows)
    with conn.cursor() as cur:
        n = _insert_batch(cur, "terms", cols, rows)
    conn.commit()
    return n


def insert_audit_log(conn, rows, dry_run):
    cols = [
        "ts", "term_id", "term_chinese", "user_email", "user_name",
        "action_type", "field_changed", "old_value", "new_value", "details",
    ]
    if dry_run:
        return len(rows)
    # audit_log rows can be large; insert 500 at a time
    inserted = 0
    with conn.cursor() as cur:
        for chunk in _chunked(rows, 500):
            data = [[row[c] for c in cols] for row in chunk]
            placeholders = ", ".join(["%s"] * len(cols))
            col_list = ", ".join(cols)
            sql = f"INSERT INTO audit_log ({col_list}) VALUES ({placeholders})"
            cur.executemany(sql, data)
            inserted += len(chunk)
    conn.commit()
    return inserted


def insert_ext_documents(conn, rows, dry_run):
    """Insert and return {display_id: internal_id} mapping."""
    cols = [
        "display_id", "title", "source_name", "paragraph_count",
        "uploaded_by", "uploaded_at", "last_viewed_index", "status",
    ]
    if dry_run:
        return {r["display_id"]: -1 for r in rows}

    id_map = {}
    with conn.cursor() as cur:
        sql = (
            "INSERT INTO ext_documents "
            "(display_id, title, source_name, paragraph_count, "
            " uploaded_by, uploaded_at, last_viewed_index, status) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id, display_id"
        )
        for row in rows:
            cur.execute(sql, [row[c] for c in cols])
            internal_id, disp = cur.fetchone()
            id_map[disp] = internal_id
    conn.commit()
    return id_map


def insert_ext_paragraphs(conn, rows, dry_run):
    """Insert paragraphs; skip duplicate (document_id, paragraph_index) pairs."""
    if dry_run:
        return len(rows), 0

    cols = ["document_id", "paragraph_index", "chinese_text", "english_text"]
    inserted, dupes = 0, 0
    with conn.cursor() as cur:
        sql = (
            "INSERT INTO ext_paragraphs "
            "(document_id, paragraph_index, chinese_text, english_text) "
            "VALUES (%s, %s, %s, %s) "
            "ON CONFLICT (document_id, paragraph_index) DO NOTHING"
        )
        for chunk in _chunked(rows, BATCH_SIZE):
            data = [[row[c] for c in cols] for row in chunk]
            cur.executemany(sql, data)
            inserted += cur.rowcount if cur.rowcount >= 0 else len(chunk)
    conn.commit()
    total_attempted = len(rows)
    dupes = total_attempted - inserted
    return inserted, dupes


# ── Votes CSV export ──────────────────────────────────────────────────────────

def export_votes_csv(records, dry_run):
    if dry_run:
        log.info("  [dry-run] would export %d Votes rows to CSV", len(records))
        return None
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    filename = BACKUP_DIR / f"votes_export_{date.today().strftime('%Y%m%d')}.csv"
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["TermID", "VoterEmail", "ChosenTranslation"])
        writer.writeheader()
        writer.writerows(records)
    log.info("  Votes: %d row(s) exported to %s", len(records), filename.name)
    return filename


# ── Sequence calibration ──────────────────────────────────────────────────────

def calibrate_sequences(conn, terms_rows, ext_doc_rows, dry_run):
    """
    Set seq_terms_display and seq_ext_documents_display to max migrated
    numeric suffix so new records don't collide with existing display_ids.
    """
    seq_updates = []

    if terms_rows:
        max_t = _max_numeric(terms_rows, "display_id")
        seq_updates.append(("seq_terms_display", max_t or 0))

    if ext_doc_rows:
        max_d = _max_numeric(ext_doc_rows, "display_id")
        seq_updates.append(("seq_ext_documents_display", max_d or 0))

    print("\n── Sequence calibration ─────────────────────────────────────────")
    print(f"  {'Sequence':<35}  {'New value':>12}")
    print(f"  {'-'*35}  {'-'*12}")

    if dry_run:
        for seq_name, val in seq_updates:
            print(f"  {seq_name:<35}  {val:>12}  [dry-run]")
        return

    with conn.cursor() as cur:
        for seq_name, val in seq_updates:
            cur.execute(f"SELECT last_value FROM {seq_name}")
            old_val = cur.fetchone()[0]
            cur.execute(f"SELECT setval('{seq_name}', %s, true)", (val,))
            new_val = cur.fetchone()[0]
            print(f"  {seq_name:<35}  {old_val:>5} → {new_val:>5}")
    conn.commit()


# ── Verification ──────────────────────────────────────────────────────────────

def _ts_norm(val):
    """Normalize a timestamp value to 'YYYY-MM-DD HH:MM' for comparison."""
    if val in (None, ""):
        return ""
    s = str(val).replace("T", " ")
    for ch in ("+", "."):
        if ch in s:
            s = s[: s.index(ch)]
    return s[:16]


def _str_eq(sheets_val, pg_val):
    """Compare a Sheets string and Postgres value, both treated as stripped strings."""
    sv = str(sheets_val).strip() if sheets_val is not None else ""
    pv = str(pg_val).strip() if pg_val is not None else ""
    return sv == pv


def verify_counts(conn, sheets_counts):
    print("\n── Row count verification ───────────────────────────────────────")
    print(f"  {'Table':<22}  {'Sheets':>8}  {'Postgres':>8}  {'Match':>6}")
    print(f"  {'-'*22}  {'-'*8}  {'-'*8}  {'-'*6}")
    all_ok = True
    with conn.cursor() as cur:
        for table, sheets_n in sheets_counts:
            cur.execute(f"SELECT count(*) FROM {table}")
            pg_n = cur.fetchone()[0]
            ok   = sheets_n == pg_n
            mark = "✓" if ok else "❌"
            if not ok:
                all_ok = False
            print(f"  {table:<22}  {sheets_n:>8}  {pg_n:>8}  {mark:>6}")
    return all_ok


def verify_sample_terms(conn, sheets_records, sample_n=20):
    """Spot-check sample_n randomly chosen Terms rows against Postgres."""
    if not sheets_records:
        return True

    sample = random.sample(sheets_records, min(sample_n, len(sheets_records)))
    field_map = [
        # (Sheets header, Postgres column, is_timestamp)
        ("ID",                    "display_id",             False),
        ("Chinese",               "chinese",                False),
        ("Pinyin",                "pinyin",                 False),
        ("Pali",                  "pali",                   False),
        ("Sanskrit",              "sanskrit",               False),
        ("Context",               "context",                False),
        ("Category",              "category",               False),
        ("Notes",                 "notes",                  False),
        ("Translation1",          "translation1",           False),
        ("Translation2",          "translation2",           False),
        ("Translation3",          "translation3",           False),
        ("Final",                 "final",                  False),
        ("Status",                "status",                 False),
        ("AddedBy",               "added_by",               False),
        ("Timestamp",             "added_at",               True),
        ("TranslationKnown",      "translation_known",      False),
        ("Source",                "source",                 False),
        ("TranslationFirst",      "translation_first",      False),
        ("TranslationSecond",     "translation_second",     False),
        ("TranslationOther1",     "translation_other1",     False),
        ("TranslationOther2",     "translation_other2",     False),
        ("LastModifiedBy",        "last_modified_by",       False),
        ("LastModifiedTime",      "last_modified_at",       True),
        ("RomanizationPlain",     "romanization_plain",     False),
        ("SourceContentChinese",  "source_content_chinese", False),
        ("SourceContentEnglish",  "source_content_english", False),
    ]
    pg_cols = ", ".join(c for _, c, _ in field_map)

    mismatches = []
    with conn.cursor() as cur:
        for rec in sample:
            disp_id = str(rec.get("ID", "")).strip()
            if not disp_id:
                continue
            cur.execute(f"SELECT {pg_cols} FROM terms WHERE display_id = %s", (disp_id,))
            pg_row = cur.fetchone()
            if pg_row is None:
                mismatches.append(f"  {disp_id}: NOT FOUND in Postgres ❌")
                continue
            for col_idx, (sh_key, pg_col, is_ts) in enumerate(field_map):
                sh_val = rec.get(sh_key, "")
                pg_val = pg_row[col_idx]
                if is_ts:
                    ok = _ts_norm(sh_val) == _ts_norm(pg_val) or (
                        sh_val in ("", None) and pg_val is None)
                else:
                    ok = _str_eq(sh_val, pg_val)
                if not ok:
                    mismatches.append(
                        f"  {disp_id} [{pg_col}]: "
                        f"sheets='{sh_val}' | postgres='{pg_val}' ❌"
                    )

    print(f"\n── Terms spot-check ({min(sample_n, len(sheets_records))} rows, 26 cols each) ──")
    if mismatches:
        for m in mismatches:
            print(m)
        return False
    print("  All sampled rows match ✓")
    return True


def verify_sample_table(conn, table, pg_col_map, sheets_records, pk_sheet, pk_pg, sample_n=20):
    """
    Generic spot-check for non-Terms tables.
    pg_col_map: list of (sheets_header, pg_column, is_timestamp)
    pk_sheet / pk_pg: column names for lookup key in Sheets and Postgres
    """
    if not sheets_records:
        return True

    sample = random.sample(sheets_records, min(sample_n, len(sheets_records)))
    pg_cols = ", ".join(c for _, c, _ in pg_col_map)
    mismatches = []
    with conn.cursor() as cur:
        for rec in sample:
            key_val = str(rec.get(pk_sheet, "")).strip()
            if not key_val:
                continue
            cur.execute(f"SELECT {pg_cols} FROM {table} WHERE {pk_pg} = %s", (key_val,))
            pg_row = cur.fetchone()
            if pg_row is None:
                mismatches.append(f"  {key_val}: NOT FOUND in {table} ❌")
                continue
            for col_idx, (sh_key, pg_col, is_ts) in enumerate(pg_col_map):
                sh_val = rec.get(sh_key, "")
                pg_val = pg_row[col_idx]
                if is_ts:
                    ok = _ts_norm(sh_val) == _ts_norm(pg_val) or (
                        sh_val in ("", None) and pg_val is None)
                else:
                    ok = _str_eq(sh_val, pg_val)
                if not ok:
                    mismatches.append(
                        f"  {key_val} [{pg_col}]: "
                        f"sheets='{sh_val}' | postgres='{pg_val}' ❌"
                    )
    print(f"\n── {table} spot-check ({min(sample_n, len(sheets_records))} rows) ──")
    if mismatches:
        for m in mismatches:
            print(m)
        return False
    print(f"  All sampled rows match ✓")
    return True


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force",   action="store_true",
                        help="Run even if target tables already have data")
    parser.add_argument("--dry-run", action="store_true",
                        help="Read and transform data but write nothing")
    args = parser.parse_args()

    # 1. Pre-flight
    sheet_id, db_url, sa_file = preflight_env()

    # 2. Connect to Postgres
    import psycopg2
    log.info("Connecting to Postgres via DATABASE_URL ...")
    try:
        conn = psycopg2.connect(db_url)
    except Exception as exc:
        print(f"ERROR: cannot connect to Postgres: {exc}")
        sys.exit(1)
    conn.autocommit = False

    if not args.dry_run:
        preflight_tables(conn, args.force)

    # 3. Open Sheets
    log.info("Reading Google Sheets ...")
    wb = open_sheet(sheet_id, sa_file)

    raw_members  = read_worksheet(wb, "Members")
    raw_sources  = read_worksheet(wb, "Sources")
    raw_terms    = read_worksheet(wb, "Terms")
    raw_audit    = read_worksheet(wb, "Audit_Log")
    raw_ext_docs = read_worksheet(wb, "ExtractionDocuments")
    raw_ext_para = read_worksheet(wb, "ExtractionParagraphs")
    raw_votes    = read_worksheet(wb, "Votes")

    # 4. Transform
    log.info("Transforming data ...")
    members_rows,  members_warn  = transform_members(raw_members)
    sources_rows,  sources_warn  = transform_sources(raw_sources)
    terms_rows,    terms_warn    = transform_terms(raw_terms)
    audit_rows,    audit_warn    = transform_audit_log(raw_audit)
    ext_doc_rows,  ext_doc_warn  = transform_ext_documents(raw_ext_docs)

    all_warnings = (members_warn + sources_warn + terms_warn
                    + audit_warn + ext_doc_warn)

    # Paragraphs depend on ext_doc_rows (display_id → internal id)
    # We do a preliminary insert of ext_documents to get the map,
    # so we defer paragraph transform until after that insert.

    # 5. Insert in FK order
    print("\n── Inserting data ───────────────────────────────────────────────")

    n_members = insert_members(conn, members_rows, args.dry_run)
    log.info("  members:      %d row(s) written", n_members)

    n_sources = insert_sources(conn, sources_rows, args.dry_run)
    log.info("  sources:      %d row(s) written", n_sources)

    n_terms = insert_terms(conn, terms_rows, args.dry_run)
    log.info("  terms:        %d row(s) written", n_terms)

    n_audit = insert_audit_log(conn, audit_rows, args.dry_run)
    log.info("  audit_log:    %d row(s) written", n_audit)

    # ext_documents: insert and capture display_id → internal id map
    doc_id_map = insert_ext_documents(conn, ext_doc_rows, args.dry_run)
    log.info("  ext_documents: %d row(s) written", len(doc_id_map))

    # Now transform paragraphs (needs doc_id_map)
    ext_para_rows, ext_para_warn = transform_ext_paragraphs(raw_ext_para, doc_id_map)
    all_warnings.extend(ext_para_warn)

    n_para, n_para_dupes = insert_ext_paragraphs(conn, ext_para_rows, args.dry_run)
    log.info("  ext_paragraphs: %d row(s) written, %d duplicate(s) skipped",
             n_para, n_para_dupes)

    # Votes → CSV only
    votes_file = export_votes_csv(raw_votes, args.dry_run)

    # 6. Sequence calibration
    calibrate_sequences(conn, terms_rows, ext_doc_rows, args.dry_run)

    # 7. Warnings summary
    if all_warnings:
        print(f"\n── Warnings ({len(all_warnings)} total — see migration_errors.log) ──")
        for w in all_warnings[:20]:
            print(f"  {w}")
        if len(all_warnings) > 20:
            print(f"  ... and {len(all_warnings) - 20} more (see log)")

    # 8. Verification
    if args.dry_run:
        print("\n[dry-run] Skipping Postgres verification.")
        print("\nDry-run complete. No data was written.")
        conn.close()
        return

    sheets_counts = [
        ("members",       len(members_rows)),
        ("sources",       len(sources_rows)),
        ("terms",         len(terms_rows)),
        ("audit_log",     len(audit_rows)),
        ("ext_documents", len(ext_doc_rows)),
        ("ext_paragraphs", n_para),
    ]
    counts_ok = verify_counts(conn, sheets_counts)

    terms_ok  = verify_sample_terms(conn, raw_terms)

    members_ok = verify_sample_table(
        conn, "members",
        [("Email", "email", False), ("Role", "role", False),
         ("Name", "name", False), ("ShortName", "short_name", False)],
        raw_members, "Email", "email",
    )

    sources_ok = verify_sample_table(
        conn, "sources",
        [("SourceID", "display_id", False), ("SourceName", "source_name", False),
         ("SourceType", "source_type", False), ("Notes", "notes", False)],
        raw_sources, "SourceID", "display_id",
    )

    ext_docs_ok = verify_sample_table(
        conn, "ext_documents",
        [("DocumentID", "display_id", False), ("Title", "title", False),
         ("SourceName", "source_name", False),
         ("UploadedBy", "uploaded_by", False),
         ("UploadedAt", "uploaded_at", True)],
        raw_ext_docs, "DocumentID", "display_id",
    )

    all_checks_ok = counts_ok and terms_ok and members_ok and sources_ok and ext_docs_ok

    print("\n" + "=" * 65)
    if all_checks_ok:
        print("✓  T0-2 驗收通過")
    else:
        print("❌  T0-2 驗收未通過，需人工檢查（見上方差異）")
    print("=" * 65)

    if all_warnings:
        print(f"\n{len(all_warnings)} row(s) skipped during transform — see {ERROR_LOG.name}")

    if votes_file:
        print(f"Votes CSV: {votes_file}")

    conn.close()


if __name__ == "__main__":
    main()
