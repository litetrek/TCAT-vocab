"""
scripts/run_migration_005.py
============================
Apply migrations/005_t1_translation_module.sql and run T1 acceptance tests.

The five translation tables are defined in this migration (idempotent — safe to
re-run).  After applying the DDL this script:
  1. Inserts one test row per table to verify display_id sequences and constraints.
  2. Tests uniqueness constraint (duplicate display_id must be rejected).
  3. Tests fractional indexing in trans_units.unit_order.
  4. Cleans up all test rows.

Usage:
    pip install psycopg2-binary python-dotenv
    python scripts/run_migration_005.py
"""

import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import psycopg2

MIGRATION_FILE = Path(__file__).parent.parent / "migrations" / "005_t1_translation_module.sql"

EXPECTED_TABLES = [
    "style_guide", "trans_books", "trans_chapters", "trans_revisions", "trans_units",
]


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
    print("\n--- T1 Acceptance Tests ---")
    passed = 0
    failed = 0

    with conn.cursor() as cur:
        try:
            # ── trans_books ──────────────────────────────────────────────────
            cur.execute("select 'B' || lpad(nextval('seq_trans_books_display')::text,6,'0')")
            book_did = cur.fetchone()[0]
            cur.execute(
                "insert into trans_books (display_id, title, created_by) "
                "values (%s, 'T1 Test Book', 'test') returning id",
                (book_did,),
            )
            book_id = cur.fetchone()[0]
            print(f"  [PASS] trans_books INSERT  display_id={book_did}")
            passed += 1

            # uniqueness constraint — use savepoint so main tx is unaffected
            cur.execute("SAVEPOINT sp_dup_test")
            try:
                cur.execute(
                    "insert into trans_books (display_id, title) values (%s, 'DUP')",
                    (book_did,),
                )
                cur.execute("ROLLBACK TO SAVEPOINT sp_dup_test")
                print("  [FAIL] trans_books uniqueness not enforced")
                failed += 1
            except psycopg2.errors.UniqueViolation:
                cur.execute("ROLLBACK TO SAVEPOINT sp_dup_test")
                print("  [PASS] trans_books unique constraint enforced")
                passed += 1

            # ── trans_chapters ───────────────────────────────────────────────
            cur.execute("select 'C' || lpad(nextval('seq_trans_chapters_display')::text,6,'0')")
            ch_did = cur.fetchone()[0]
            cur.execute(
                "insert into trans_chapters (display_id, book_id, chapter_index, title) "
                "values (%s, %s, 1, 'T1 Test Chapter') returning id",
                (ch_did, book_id),
            )
            chapter_id = cur.fetchone()[0]
            print(f"  [PASS] trans_chapters INSERT  display_id={ch_did}")
            passed += 1

            # ── trans_units — integer unit_order ─────────────────────────────
            cur.execute("select 'U' || lpad(nextval('seq_trans_units_display')::text,6,'0')")
            u_did1 = cur.fetchone()[0]
            cur.execute(
                "insert into trans_units "
                "(display_id, chapter_id, paragraph_index, unit_order, chinese_text) "
                "values (%s, %s, 0, 1, '測試句。') returning id",
                (u_did1, chapter_id),
            )
            unit_id = cur.fetchone()[0]
            print(f"  [PASS] trans_units INSERT  display_id={u_did1}")
            passed += 1

            # ── trans_units — fractional unit_order (1.5) ────────────────────
            cur.execute("select 'U' || lpad(nextval('seq_trans_units_display')::text,6,'0')")
            u_did2 = cur.fetchone()[0]
            cur.execute(
                "insert into trans_units "
                "(display_id, chapter_id, paragraph_index, unit_order, chinese_text) "
                "values (%s, %s, 0, 1.5, '分句插入測試。')",
                (u_did2, chapter_id),
            )
            print(f"  [PASS] trans_units fractional unit_order=1.5  display_id={u_did2}")
            passed += 1

            # ── trans_revisions ──────────────────────────────────────────────
            cur.execute("select 'R' || lpad(nextval('seq_trans_revisions_display')::text,6,'0')")
            r_did = cur.fetchone()[0]
            cur.execute(
                "insert into trans_revisions "
                "(display_id, unit_id, chinese_text, english_before, english_after, revision_type) "
                "values (%s, %s, '測試句。', 'before', 'after', 'other') returning id",
                (r_did, unit_id),
            )
            revision_id = cur.fetchone()[0]
            print(f"  [PASS] trans_revisions INSERT  display_id={r_did}")
            passed += 1

            # ── style_guide ──────────────────────────────────────────────────
            cur.execute("select 'S' || lpad(nextval('seq_style_guide_display')::text,6,'0')")
            s_did = cur.fetchone()[0]
            cur.execute(
                "insert into style_guide (display_id, category, rule_text) "
                "values (%s, 'tone', 'T1 test rule')",
                (s_did,),
            )
            print(f"  [PASS] style_guide INSERT  display_id={s_did}")
            passed += 1

            # ── Clean up ─────────────────────────────────────────────────────
            cur.execute("delete from style_guide   where display_id = %s", (s_did,))
            cur.execute("delete from trans_revisions where display_id = %s", (r_did,))
            cur.execute("delete from trans_units    where chapter_id = %s", (chapter_id,))
            cur.execute("delete from trans_chapters where id = %s", (chapter_id,))
            cur.execute("delete from trans_books    where id = %s", (book_id,))
            conn.commit()
            print("  [PASS] Cleanup — all test rows removed")
            passed += 1

        except Exception as exc:
            conn.rollback()
            print(f"  [ERROR] {exc}")
            failed += 1

    print(f"\nAcceptance tests: {passed} passed, {failed} failed.")
    return failed == 0


def verify_tables(conn):
    with conn.cursor() as cur:
        cur.execute(
            "select tablename from pg_tables "
            "where schemaname = 'public' order by tablename"
        )
        present = {row[0] for row in cur.fetchall()}

    missing = [t for t in EXPECTED_TABLES if t not in present]
    if missing:
        print(f"WARNING: missing tables: {missing}")
        return False

    print("\nFive translation tables confirmed present:")
    for t in EXPECTED_TABLES:
        print(f"  [OK] {t}")
    return True


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

    if not verify_tables(conn):
        conn.close()
        return 1

    ok = run_acceptance_tests(conn)
    conn.close()

    if ok:
        print("\n[PASS] T1 migration and acceptance tests all passed.")
        return 0
    else:
        print("\n[FAIL] One or more acceptance tests failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
