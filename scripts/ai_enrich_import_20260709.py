"""
scripts/ai_enrich_import_20260709.py
=====================================
One-time batch: enrich xlsx_import_20260709 terms with AI-generated
pali / sanskrit / translation1-3.

Targets rows where:
  added_by = 'xlsx_import_20260709' AND last_modified_at IS NULL

last_modified_at IS NULL acts as the "not yet processed" flag — safe to
re-run after interruption; already-completed rows are skipped automatically.

Usage:
    python scripts/ai_enrich_import_20260709.py [--dry-run]

Flags:
    --dry-run   Print target rows (display_id + first 20 chars of chinese)
                without calling AI or writing to database.

Required env vars (in .env):
    DATABASE_URL       pgBouncer pooled connection (port 6543)
    ANTHROPIC_API_KEY  Claude API key
"""

import argparse
import logging
import os
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Allow importing ai.py from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

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
log = logging.getLogger("ai_enrich")

BATCH_MODIFIED_BY = "ai_batch_translate"
DELAY_SECONDS     = 0.4   # between API calls
PROGRESS_EVERY    = 20
FAILED_LOG        = Path(__file__).parent.parent / "failed_ids.log"


def get_target_rows(conn):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, display_id, chinese
            FROM terms
            WHERE added_by = 'xlsx_import_20260709'
              AND last_modified_at IS NULL
            ORDER BY id
        """)
        return cur.fetchall()


def update_row(conn, row_id, pali, sanskrit, t1, t2, t3):
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE terms SET
                pali            = %s,
                sanskrit        = %s,
                translation1    = %s,
                translation2    = %s,
                translation3    = %s,
                last_modified_by  = %s,
                last_modified_at  = now()
            WHERE id = %s
        """, (
            pali or None,
            sanskrit or None,
            t1 or None,
            t2 or None,
            t3 or None,
            BATCH_MODIFIED_BY,
            row_id,
        ))
    conn.commit()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Print target rows without calling AI or writing to DB")
    args = parser.parse_args()

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL is not set in .env")
        sys.exit(1)
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY is not set in .env")
        sys.exit(1)

    import psycopg2
    conn = psycopg2.connect(db_url)

    rows = get_target_rows(conn)
    total = len(rows)
    log.info("Target rows: %d", total)

    if args.dry_run:
        print(f"\n-- DRY RUN -- {total} rows would be processed --")
        for internal_id, display_id, chinese in rows:
            preview = (chinese or "")[:20]
            print(f"  {display_id}  {preview}")
        print(f"\nTotal: {total} rows. Run without --dry-run to process.")
        conn.close()
        return

    from ai import generate_term_data

    succeeded  = 0
    failed_ids = []

    for i, (internal_id, display_id, chinese) in enumerate(rows, start=1):
        try:
            _pinyin, pali, sanskrit, t1, t2, t3 = generate_term_data(chinese)
            update_row(conn, internal_id, pali, sanskrit, t1, t2, t3)
            succeeded += 1
        except Exception as exc:
            msg = f"{display_id}: {exc}"
            log.error(msg)
            failed_ids.append(display_id)
            with open(FAILED_LOG, "a", encoding="utf-8") as f:
                f.write(msg + "\n")

        if i % PROGRESS_EVERY == 0 or i == total:
            log.info("Progress: %d/%d done, %d failed", i, total, len(failed_ids))

        if i < total:
            time.sleep(DELAY_SECONDS)

    conn.close()

    print("\n-- Result --")
    print(f"  Succeeded: {succeeded}")
    print(f"  Failed:    {len(failed_ids)}")
    if failed_ids:
        print(f"  Failed IDs: {', '.join(failed_ids)}")
        print(f"  See {FAILED_LOG} for details.")
    print("Done.")


if __name__ == "__main__":
    main()
