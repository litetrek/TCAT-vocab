"""
scripts/run_migration_010.py
============================
Apply migrations/010_dual_embeddings.sql.

Drops the old single embedding column and adds:
  - trans_revisions.embedding_voyage  vector(1024)
  - trans_revisions.embedding_openai  vector(1536)
  - find_similar_revisions_voyage RPC
  - find_similar_revisions_openai RPC

Acceptance tests: insert a test revision, write fake vectors to both
columns, call both RPCs, verify results, then clean up.

Usage:
    python scripts/run_migration_010.py
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
from psycopg2.extras import RealDictCursor

MIGRATION_FILE = Path(__file__).parent.parent / "migrations" / "010_dual_embeddings.sql"


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
    print("\n--- T4.2 Acceptance Tests ---")
    passed = 0
    failed = 0
    test_revision_id = None

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        try:
            # ── Test 1: embedding_voyage column exists ────────────────────────
            cur.execute("""
                SELECT column_name, udt_name
                FROM information_schema.columns
                WHERE table_name = 'trans_revisions' AND column_name = 'embedding_voyage'
            """)
            row = cur.fetchone()
            assert row is not None, "embedding_voyage column missing from trans_revisions"
            print("  [PASS] trans_revisions.embedding_voyage column exists")
            passed += 1

            # ── Test 2: embedding_openai column exists ────────────────────────
            cur.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'trans_revisions' AND column_name = 'embedding_openai'
            """)
            row = cur.fetchone()
            assert row is not None, "embedding_openai column missing from trans_revisions"
            print("  [PASS] trans_revisions.embedding_openai column exists")
            passed += 1

            # ── Test 3: old embedding column is gone ─────────────────────────
            cur.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'trans_revisions' AND column_name = 'embedding'
            """)
            row = cur.fetchone()
            assert row is None, "old embedding column still present on trans_revisions"
            print("  [PASS] old trans_revisions.embedding column removed")
            passed += 1

            # ── Test 4: insert test revision with fake vectors ────────────────
            voyage_vec  = "[" + ",".join(["0.01"] * 1024) + "]"
            openai_vec  = "[" + ",".join(["0.02"] * 1536) + "]"
            cur.execute("""
                INSERT INTO trans_revisions
                  (display_id, unit_id, chinese_text, english_before, english_after,
                   revision_type, note, revised_by, embedding_voyage, embedding_openai)
                VALUES
                  ('R_TEST_010', 1, '測試句子', 'test before', 'test after',
                   'other', 'migration 010 acceptance test', 'test@example.com',
                   %s::vector, %s::vector)
                RETURNING id
            """, (voyage_vec, openai_vec))
            row = cur.fetchone()
            test_revision_id = row["id"]
            conn.commit()
            print(f"  [PASS] test revision inserted (id={test_revision_id})")
            passed += 1

            # ── Test 5: find_similar_revisions_voyage RPC ─────────────────────
            cur.execute(
                "SELECT * FROM find_similar_revisions_voyage(%s::vector, 5)",
                (voyage_vec,)
            )
            rows = cur.fetchall()
            assert any(r["id"] == test_revision_id for r in rows), \
                "test revision not returned by find_similar_revisions_voyage"
            print("  [PASS] find_similar_revisions_voyage RPC returns test revision")
            passed += 1

            # ── Test 6: find_similar_revisions_openai RPC ─────────────────────
            cur.execute(
                "SELECT * FROM find_similar_revisions_openai(%s::vector, 5)",
                (openai_vec,)
            )
            rows = cur.fetchall()
            assert any(r["id"] == test_revision_id for r in rows), \
                "test revision not returned by find_similar_revisions_openai"
            print("  [PASS] find_similar_revisions_openai RPC returns test revision")
            passed += 1

        except Exception as exc:
            conn.rollback()
            print(f"  [ERROR] {exc}")
            import traceback
            traceback.print_exc()
            failed += 1
        finally:
            # ── Cleanup test data ─────────────────────────────────────────────
            if test_revision_id is not None:
                try:
                    cur.execute("DELETE FROM trans_revisions WHERE id = %s", (test_revision_id,))
                    conn.commit()
                    print(f"  [INFO] test revision {test_revision_id} cleaned up")
                except Exception:
                    conn.rollback()

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
        print("\n[PASS] T4.2 migration and acceptance tests all passed.")
        return 0
    else:
        print("\n[FAIL] One or more acceptance tests failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
