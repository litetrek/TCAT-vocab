"""
scripts/compare_embedding_providers.py
=======================================
Side-by-side comparison of Voyage AI vs OpenAI embedding retrieval quality.

For each test query, embeds with both providers, calls their respective
find_similar_revisions_* RPCs, and prints results in two columns so you
can visually judge which provider returns more relevant results.

Usage:
    python scripts/compare_embedding_providers.py
    python scripts/compare_embedding_providers.py --limit 3

Options:
    --limit N   Return top-N results per provider per query (default: 5)
"""

import argparse
import os
import sys
from pathlib import Path

# Allow running from repo root or scripts/ directory
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from embeddings import get_voyage_embedding, get_openai_embedding

try:
    from supabase import create_client
    _sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
except Exception as exc:
    print(f"ERROR: could not connect to Supabase: {exc}")
    sys.exit(1)

TEST_QUERIES = [
    "菩薩依般若波羅蜜多故，心無罣礙。",
    "爾時世尊，在舍衛國祇樹給孤獨園，與大比丘眾千二百五十人俱。",
    "若人欲了知，三世一切佛，應觀法界性，一切唯心造。",
    "戒是正順解脫之本，故名波羅提木叉。",
    "觀自在菩薩行深般若波羅蜜多時，照見五蘊皆空，度一切苦厄。",
]

COL_WIDTH = 52


def _query_rpc(rpc_name: str, embedding: list, limit: int) -> list:
    try:
        result = _sb.rpc(rpc_name, {
            "query_embedding": embedding,
            "match_limit": limit,
        }).execute()
        return result.data or []
    except Exception as exc:
        return [{"_error": str(exc)}]


def _fmt_row(row: dict) -> str:
    if "_error" in row:
        return f"  ERROR: {row['_error']}"
    sim = row.get("similarity", 0)
    zh  = (row.get("chinese_text") or "")[:30]
    en  = (row.get("english_after") or "")[:40]
    return f"  [{sim:.3f}] {zh}\n          → {en}"


def compare(limit: int):
    voyage_key = os.getenv("VOYAGE_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    if not voyage_key:
        print("  [WARN] VOYAGE_API_KEY not set — Voyage column will be skipped")
    if not openai_key:
        print("  [WARN] OPENAI_API_KEY not set — OpenAI column will be skipped")
    if not voyage_key and not openai_key:
        print("ERROR: no API keys set. Set at least one of VOYAGE_API_KEY or OPENAI_API_KEY.")
        return

    print("=" * (COL_WIDTH * 2 + 5))
    print(f"{'VOYAGE (voyage-3, 1024-dim)':<{COL_WIDTH}}  {'OPENAI (text-embedding-3-small, 1536-dim)'}")
    print("=" * (COL_WIDTH * 2 + 5))

    for query in TEST_QUERIES:
        print(f"\nQuery: {query}")
        print("-" * (COL_WIDTH * 2 + 5))

        voyage_rows = []
        openai_rows = []

        if voyage_key:
            vec = get_voyage_embedding(query)
            if vec:
                voyage_rows = _query_rpc("find_similar_revisions_voyage", vec, limit)
            else:
                voyage_rows = [{"_error": "embedding failed"}]

        if openai_key:
            vec = get_openai_embedding(query)
            if vec:
                openai_rows = _query_rpc("find_similar_revisions_openai", vec, limit)
            else:
                openai_rows = [{"_error": "embedding failed"}]

        if not voyage_rows and not openai_rows:
            print("  (no results from either provider)")
            continue

        max_rows = max(len(voyage_rows), len(openai_rows))
        if max_rows == 0:
            print("  (no results — trans_revisions may be empty or embeddings not yet written)")
            continue

        for i in range(max_rows):
            v = _fmt_row(voyage_rows[i]) if i < len(voyage_rows) else "  —"
            o = _fmt_row(openai_rows[i]) if i < len(openai_rows) else "  —"
            v_lines = v.split("\n")
            o_lines = o.split("\n")
            lines = max(len(v_lines), len(o_lines))
            for j in range(lines):
                vl = v_lines[j] if j < len(v_lines) else ""
                ol = o_lines[j] if j < len(o_lines) else ""
                print(f"{vl:<{COL_WIDTH}}  {ol}")
            print()


def main():
    parser = argparse.ArgumentParser(description="Compare Voyage vs OpenAI embedding retrieval")
    parser.add_argument("--limit", type=int, default=5, help="Top-N results per provider (default: 5)")
    args = parser.parse_args()
    compare(args.limit)


if __name__ == "__main__":
    main()
