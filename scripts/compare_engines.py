"""
compare_engines.py
==================
Stage F4: blind comparison of the two translation engines for reviewers.

Drafts each unit with both engines (Claude and OpenAI), using exactly the same
glossary constraints, context, style rules and RAG examples as the "Translate"
button (api_translate_unit). Nothing is written to Supabase.

Outputs (in docs/):
    compare_<date>.md      Version A / Version B per sentence, order randomised — send this one
    compare_<date>_key.md  which version is which engine — keep it back until judging is done

Usage:
    python scripts/compare_engines.py                       # book 10, 入法門論 sentences 1–7
    python scripts/compare_engines.py --units 354,353       # other units
    python scripts/compare_engines.py --seed 42             # repeatable A/B order
"""

import argparse
import io
import os
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date

# Force UTF-8 output on Windows (avoids cp1252 errors with Chinese characters)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ai import translate_unit
from db import supabase
from routes.translate import (_match_constraint_terms, _get_context, _get_active_style_rules,
                              _get_similar_examples, _get_source_id_for_book)

ENGINES = ("claude", "openai")


def _missing_text(missing):
    if not missing:
        return "none"
    return "; ".join(f"{m['chinese']} → {m['english']}" + (" (gloss dropped)" if m["partial"] else "")
                     for m in missing)


def main():
    ap = argparse.ArgumentParser(description="Blind engine comparison (no DB writes)")
    ap.add_argument("--book-id", type=int, default=10)
    ap.add_argument("--units", default="354,353,352,351,348,349,350")
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args()

    unit_ids = [int(u) for u in args.units.split(",") if u.strip()]
    rng = random.Random(args.seed)

    book = supabase.table("trans_books").select("id,title").eq("id", args.book_id).execute().data
    if not book:
        sys.exit(f"Book {args.book_id} not found")
    book_title = book[0].get("title") or f"Book {args.book_id}"
    source_id = _get_source_id_for_book(args.book_id)
    style_rules = _get_active_style_rules(args.book_id)

    rows = {u["id"]: u for u in supabase.table("trans_units")
            .select("id,chapter_id,chinese_text,english_final,is_long_sentence")
            .in_("id", unit_ids).execute().data}

    results, timings = [], []
    for n, uid in enumerate(unit_ids, 1):
        u = rows.get(uid)
        if not u or not (u.get("chinese_text") or "").strip():
            print(f"unit {uid}: not found or empty — skipped", flush=True)
            continue
        zh = u["chinese_text"]
        terms = _match_constraint_terms(zh, prefer_source_id=source_id)
        before, after, para = _get_context(u["chapter_id"], uid)
        examples = _get_similar_examples(zh)

        def run(engine):
            t0 = time.time()
            r = translate_unit(zh, term_constraints=terms, context_before=before, context_after=after,
                               is_long_sentence=bool(u.get("is_long_sentence")), style_rules=style_rules,
                               similar_examples=examples, engine=engine, paragraph_text=para)
            return engine, r, time.time() - t0

        with ThreadPoolExecutor(max_workers=len(ENGINES)) as pool:
            drafts = {e: (r, secs) for e, r, secs in pool.map(run, ENGINES)}

        order = list(ENGINES)
        rng.shuffle(order)
        results.append({"n": n, "unit": u, "terms": terms, "order": order, "drafts": drafts})
        for e in ENGINES:
            r, secs = drafts[e]
            timings.append((n, uid, e, r, secs))
            print(f"[{n}] unit {uid} {e:6} {secs:5.1f}s retried={'yes' if r['retried'] else 'no'} "
                  f"missing={len(r['missing_terms'])}" + (f" ERROR {r['error']}" if r.get("error") else ""),
                  flush=True)

    today = date.today().isoformat()
    out = os.path.join(ROOT, "docs", f"compare_{today}.md")
    key = os.path.join(ROOT, "docs", f"compare_{today}_key.md")

    blind = [f"# Translation comparison — {book_title}", "",
             f"{today}. Each sentence has two English drafts, **Version A** and **Version B**, made by "
             "two different AI systems with the same glossary and instructions. The order changes from "
             "sentence to sentence. Please note which version you prefer for each sentence, and why.", ""]
    keylines = [f"# Comparison key — {book_title} ({today})", "",
                "Do not share with reviewers until they have judged.", "",
                "| # | Unit | Version A | Version B |", "|---|---|---|---|"]
    for res in results:
        blind += [f"## Sentence {res['n']}", "", res["unit"]["chinese_text"], ""]
        if res["terms"]:
            blind += ["Required glossary terms: " +
                      "; ".join(f"{t['chinese']} → {t['english']}" for t in res["terms"]), ""]
        for label, eng in zip("AB", res["order"]):
            r, _ = res["drafts"][eng]
            blind += [f"**Version {label}**", "", r["english"] or f"_(no draft: {r.get('error')})_", "",
                      f"Glossary terms not used: {_missing_text(r['missing_terms'])}", ""]
        a, b = (res["drafts"][e][0]["model"] for e in res["order"])
        keylines.append(f"| {res['n']} | {res['unit']['id']} | {res['order'][0]} ({a}) | {res['order'][1]} ({b}) |")

    keylines += ["", "## Current English in T-CAT (for reference)", ""]
    for res in results:
        keylines += [f"**{res['n']}.** {res['unit'].get('english_final') or '_(empty)_'}", ""]

    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(blind))
    with open(key, "w", encoding="utf-8") as f:
        f.write("\n".join(keylines))

    print("\n── Usage per call ─────────────────────────────────────────────")
    print(f"{'#':>2} {'unit':>5} {'engine':7} {'model':18} {'secs':>6} {'calls':>5} {'in tok':>7} {'out tok':>8}")
    tot = {e: [0, 0, 0.0] for e in ENGINES}
    for n, uid, e, r, secs in timings:
        us = r.get("usage") or {}
        print(f"{n:>2} {uid:>5} {e:7} {r['model']:18} {secs:6.1f} {us.get('calls', 0):>5} "
              f"{us.get('input_tokens', 0):>7} {us.get('output_tokens', 0):>8}")
        tot[e][0] += us.get("input_tokens", 0)
        tot[e][1] += us.get("output_tokens", 0)
        tot[e][2] += secs
    for e, (i, o, s) in tot.items():
        print(f"total {e:7} in={i} out={o} time={s:.1f}s")
    print(f"\nWrote {os.path.relpath(out, ROOT)} and {os.path.relpath(key, ROOT)}")


if __name__ == "__main__":
    main()
