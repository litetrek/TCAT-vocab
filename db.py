import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

_DATABASE_URL = os.getenv("DATABASE_URL", "")

if not _DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. "
        "Add the pgBouncer pooled connection string (port 6543) to your .env."
    )


def get_conn():
    """Open a new psycopg2 connection. Caller must close() it after use."""
    return psycopg2.connect(_DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)


def generate_display_id(cur, prefix, sequence_name):
    """
    Advance the named Postgres sequence and return prefix + 6-digit zero-padded number.
    Must be called inside an open transaction (within a with-conn block).
    Example: generate_display_id(cur, 'T', 'seq_terms_display') → 'T000042'
    """
    cur.execute("SELECT lpad(nextval(%s)::text, 6, '0') AS num", (sequence_name,))
    return f"{prefix}{cur.fetchone()['num']}"
