"""
scripts/run_migration_006.py
============================
Apply migrations/006_t2_import_book_rpc.sql.

Creates two RPC functions used by the T2 translation module:
  - import_trans_book(p_title, p_created_by, p_chapters)
  - list_trans_books()

After applying the SQL this script calls both functions via Supabase RPC
to verify they were registered correctly.

Usage:
    pip install psycopg2-binary python-dotenv supabase
    python scripts/run_migration_006.py
"""

import os
import sys
import json
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import psycopg2

MIGRATION_FILE = Path(__file__).parent.parent / "migrations" / "006_t2_import_book_rpc.sql"


def _connect(db_url):
    return psycopg2.connect(db_url)


def apply_migration(conn):
    sql = MIGRATION_FILE.read_text(encoding="utf-8")
    conn.autocommit = False
    with conn.cursor() as cur:
        print(f"Applying {MIGRATION_FILE.name} ...")
        cur.execute(sql)
    conn.commit()
    print("Migration applied successfully.")


def run_acceptance_tests(conn):
    print("\n--- T2 RPC Acceptance Tests ---")
    passed = 0
    failed = 0

    with conn.cursor() as cur:
        try:
            # ── Test import_trans_book ────────────────────────────────────────
            test_chapters = json.dumps([
                {
                    "chapter_index": 0,
                    "title": "T2 Test Chapter",
                    "section_type": "body",
                    "units": [
                        {"paragraph_index": 0, "unit_order": 1, "chinese_text": "測試第一句。", "is_long_sentence": False},
                        {"paragraph_index": 0, "unit_order": 2, "chinese_text": "測試第二句。", "is_long_sentence": False},
                        {"paragraph_index": 1, "unit_order": 1, "chinese_text": "第二段第一句。", "is_long_sentence": False},
                    ]
                }
            ])
            cur.execute(
                "SELECT import_trans_book(%s, %s, %s::jsonb)",
                ("T2 Test Book", "test@example.com", test_chapters),
            )
            result = cur.fetchone()[0]
            book_id = result["book_id"]
            display_id = result["display_id"]
            chapter_count = result["chapter_count"]
            unit_count = result["unit_count"]
            assert chapter_count == 1, f"Expected 1 chapter, got {chapter_count}"
            assert unit_count == 3, f"Expected 3 units, got {unit_count}"
            print(f"  [PASS] import_trans_book: {display_id}, {chapter_count} chapters, {unit_count} units")
            passed += 1

            # ── Test list_trans_books ─────────────────────────────────────────
            cur.execute("SELECT * FROM list_trans_books()")
            rows = cur.fetchall()
            colnames = [desc[0] for desc in cur.description]
            books = [dict(zip(colnames, row)) for row in rows]
            test_book = next((b for b in books if b["id"] == book_id), None)
            assert test_book is not None, "Test book not found in list_trans_books()"
            assert test_book["unit_count"] == 3
            assert test_book["cnt_untranslated"] == 3
            print("  [PASS] list_trans_books: found test book, unit_count=3, cnt_untranslated=3")
            passed += 1

            # ── section_type detection test (editorial prefix) ────────────────
            editorial_chapters = json.dumps([
                {
                    "chapter_index": 0,
                    "title": "本社按",
                    "section_type": "editorial",
                    "units": [
                        {"paragraph_index": 0, "unit_order": 1, "chinese_text": "本社按：測試。", "is_long_sentence": False},
                    ]
                }
            ])
            cur.execute(
                "SELECT import_trans_book(%s, %s, %s::jsonb)",
                ("T2 Test Book 2 (editorial)", "test@example.com", editorial_chapters),
            )
            result2 = cur.fetchone()[0]
            book_id2 = result2["book_id"]

            cur.execute("SELECT section_type FROM trans_chapters WHERE book_id = %s", (book_id2,))
            stype = cur.fetchone()[0]
            assert stype == "editorial", f"Expected 'editorial', got '{stype}'"
            print(f"  [PASS] section_type='editorial' correctly stored")
            passed += 1

            # ── Clean up ─────────────────────────────────────────────────────
            for bid in (book_id, book_id2):
                cur.execute("DELETE FROM trans_units WHERE chapter_id IN (SELECT id FROM trans_chapters WHERE book_id = %s)", (bid,))
                cur.execute("DELETE FROM trans_chapters WHERE book_id = %s", (bid,))
                cur.execute("DELETE FROM trans_books WHERE id = %s", (bid,))
            conn.commit()
            print("  [PASS] Cleanup — all test rows removed")
            passed += 1

        except Exception as exc:
            conn.rollback()
            print(f"  [ERROR] {exc}")
            import traceback
            traceback.print_exc()
            failed += 1

    print(f"\nAcceptance tests: {passed} passed, {failed} failed.")
    return failed == 0


def main() -> int:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print(
            "ERROR: DATABASE_URL is not set.\n"
            "Add the pgBouncer pooled connection string (port 6543) to your .env:\n"
            "  DATABASE_URL=postgresql://postgres.XXXX:[PASSWORD]"
            "@aws-0-REGION.pooler.supabase.com:6543/postgres"
        )
        return 1

    if not MIGRATION_FILE.exists():
        print(f"ERROR: migration file not found: {MIGRATION_FILE}")
        return 1

    print("Connecting to Postgres via DATABASE_URL ...")
    try:
        conn = _connect(db_url)
    except Exception as exc:
        print(f"ERROR: could not connect: {exc}")
        return 1

    try:
        apply_migration(conn)
    except Exception as exc:
        conn.rollback()
        print(f"ERROR during migration (rolled back): {exc}")
        conn.close()
        return 1

    ok = run_acceptance_tests(conn)
    conn.close()

    if ok:
        print("\n[PASS] T2 migration and acceptance tests all passed.")
        return 0
    else:
        print("\n[FAIL] One or more acceptance tests failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
