"""
scripts/run_migration.py
========================
Apply migrations/001_initial_schema.sql to the Supabase Postgres database.

Reads DATABASE_URL from .env (pgBouncer pooled connection string, port 6543).
Uses psycopg2-binary — no Supabase client library needed.

Usage:
    pip install psycopg2-binary python-dotenv
    python scripts/run_migration.py
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

MIGRATION_FILE = Path(__file__).parent.parent / "migrations" / "001_initial_schema.sql"


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

    sql = MIGRATION_FILE.read_text(encoding="utf-8")

    print(f"Connecting to Postgres via DATABASE_URL ...")
    try:
        conn = psycopg2.connect(db_url)
    except Exception as exc:
        print(f"ERROR: could not connect: {exc}")
        return 1

    try:
        conn.autocommit = False
        with conn.cursor() as cur:
            print(f"Applying {MIGRATION_FILE.name} ...")
            cur.execute(sql)
        conn.commit()
        print("Migration applied successfully.")
    except Exception as exc:
        conn.rollback()
        print(f"ERROR during migration (rolled back): {exc}")
        return 1
    finally:
        conn.close()

    # Verify: list all public tables
    print("\nVerifying — public tables now in database:")
    try:
        conn2 = psycopg2.connect(db_url)
        with conn2.cursor() as cur:
            cur.execute(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname = 'public' ORDER BY tablename;"
            )
            tables = [row[0] for row in cur.fetchall()]
        conn2.close()
        for t in tables:
            print(f"  {t}")
        print(f"\nTotal: {len(tables)} table(s)")
        if len(tables) == 11:
            print("✓ All 11 expected tables present.")
        else:
            print(f"WARNING: expected 11 tables, found {len(tables)}.")
    except Exception as exc:
        print(f"WARNING: could not verify tables: {exc}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
