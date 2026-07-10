"""
scripts/backfill_classification.py
===================================
Batch-classify unclassified terms in the `terms` table via AI.

- Reads SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY from .env
- Reads ANTHROPIC_API_KEY from .env
- Filters rows where entity_type IS NULL
- Calls classify_term() for each and writes back entity_type / subject_field /
  classification_source / classified_by / classified_at
- Safe to interrupt and re-run: rows already classified are skipped
- --dry-run: prints suggestions without writing to the database
- --limit N: stop after N terms (useful for spot-checks)

Usage:
    python scripts/backfill_classification.py --dry-run
    python scripts/backfill_classification.py --limit 20
    python scripts/backfill_classification.py
"""

import argparse
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ── Add repo root to path so we can import ai.py and db.py ─────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env")
except ImportError:
    pass

from ai import classify_term
from supabase import create_client


# ── Supabase client ──────────────────────────────────────────────────────────
_url = os.getenv("SUPABASE_URL", "")
_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
if not _url or not _key:
    print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env")
    sys.exit(1)

supabase = create_client(_url, _key)

_PAGE = 1000


def fetch_unclassified() -> list[dict]:
    """Return all terms where entity_type IS NULL, paginated."""
    rows = []
    offset = 0
    while True:
        chunk = (
            supabase.table("terms")
            .select("display_id, chinese, pinyin, context, notes")
            .is_("entity_type", "null")
            .order("display_id")
            .range(offset, offset + _PAGE - 1)
            .execute()
            .data
        )
        rows.extend(chunk)
        if len(chunk) < _PAGE:
            break
        offset += _PAGE
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill entity_type / subject_field for unclassified terms")
    parser.add_argument("--dry-run", action="store_true", help="Print suggestions without writing to the database")
    parser.add_argument("--limit", type=int, default=0, help="Stop after N terms (0 = no limit)")
    args = parser.parse_args()

    rows = fetch_unclassified()
    total = len(rows)
    print(f"Found {total} unclassified term(s).")

    if total == 0:
        print("Nothing to do.")
        return 0

    if args.limit:
        rows = rows[: args.limit]
        print(f"Processing first {len(rows)} term(s) (--limit {args.limit}).")

    if args.dry_run:
        print("DRY RUN — no writes will be made.\n")

    done = 0
    errors = 0
    for i, row in enumerate(rows, 1):
        term_id = row["display_id"]
        chinese = row.get("chinese", "")
        try:
            result = classify_term({
                "chinese": chinese,
                "pinyin":  row.get("pinyin",  ""),
                "context": row.get("context", ""),
                "notes":   row.get("notes",   ""),
            })
            entity  = result["entity_type"]
            subject = result["subject_field"]
            conf    = result["confidence"]
            reason  = result["reasoning"]

            flag = " ⚠ LOW CONF" if conf < 0.6 else ""
            print(f"[{i}/{len(rows)}] {term_id} {chinese[:12]:<12}  "
                  f"type={entity:<8}  field={subject:<8}  conf={conf:.2f}{flag}")
            if not args.dry_run:
                now_ts = datetime.now(tz=timezone.utc).isoformat()
                supabase.table("terms").update({
                    "entity_type":           entity,
                    "subject_field":         subject,
                    "classification_source": "ai",
                    "classified_by":         "ai:claude-haiku-4-5",
                    "classified_at":         now_ts,
                }).eq("display_id", term_id).execute()
            done += 1
        except Exception as exc:
            print(f"[{i}/{len(rows)}] {term_id} {chinese[:12]:<12}  ERROR: {exc}")
            errors += 1
        # Respect rate limits — small sleep between calls
        time.sleep(0.2)

    print(f"\nDone: {done} classified, {errors} errors.")
    if args.dry_run:
        print("(DRY RUN — no changes written)")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
