-- migrations/006_t2_import_book_rpc.sql
-- T2: Two RPC functions for the translation-module import and listing.
-- All DB writes go through PostgREST HTTPS (direct TCP is blocked on GreenGeeks).

-- ── import_trans_book ──────────────────────────────────────────────────────────
-- Atomically inserts one trans_books row, N trans_chapters rows, and all their
-- trans_units rows in a single Postgres transaction.
--
-- p_chapters JSONB schema (array):
-- [
--   {
--     "chapter_index": 0,
--     "title": "第一章",
--     "section_type": "body",
--     "units": [
--       {"paragraph_index": 0, "unit_order": 1, "chinese_text": "...", "is_long_sentence": false},
--       ...
--     ]
--   },
--   ...
-- ]
--
-- Returns: {book_id, display_id, chapter_count, unit_count}

CREATE OR REPLACE FUNCTION import_trans_book(
  p_title      text,
  p_created_by text,
  p_chapters   jsonb
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_book_display_id    text;
  v_chapter_display_id text;
  v_unit_display_id    text;
  v_book_id    bigint;
  v_chapter_id bigint;
  v_ch_count   int := 0;
  v_unit_count int := 0;
  v_ch         jsonb;
  v_unit       jsonb;
  v_ch_len     int;
  v_unit_len   int;
  v_i          int;
  v_j          int;
BEGIN
  v_book_display_id := next_display_id('BK', 'seq_trans_books_display');

  INSERT INTO trans_books (display_id, title, created_by)
  VALUES (v_book_display_id, p_title, p_created_by)
  RETURNING id INTO v_book_id;

  v_ch_len := jsonb_array_length(p_chapters);
  v_i := 0;
  WHILE v_i < v_ch_len LOOP
    v_ch := p_chapters->v_i;

    v_chapter_display_id := next_display_id('CH', 'seq_trans_chapters_display');

    INSERT INTO trans_chapters (
      display_id, book_id, chapter_index, title, section_type
    ) VALUES (
      v_chapter_display_id,
      v_book_id,
      (v_ch->>'chapter_index')::int,
      v_ch->>'title',
      COALESCE(NULLIF(v_ch->>'section_type', ''), 'body')
    )
    RETURNING id INTO v_chapter_id;

    v_ch_count := v_ch_count + 1;

    v_unit_len := jsonb_array_length(v_ch->'units');
    v_j := 0;
    WHILE v_j < v_unit_len LOOP
      v_unit := (v_ch->'units')->v_j;

      v_unit_display_id := next_display_id('U', 'seq_trans_units_display');

      INSERT INTO trans_units (
        display_id, chapter_id, paragraph_index, unit_order,
        chinese_text, is_long_sentence
      ) VALUES (
        v_unit_display_id,
        v_chapter_id,
        (v_unit->>'paragraph_index')::int,
        (v_unit->>'unit_order')::numeric,
        v_unit->>'chinese_text',
        COALESCE((v_unit->>'is_long_sentence')::boolean, false)
      );

      v_unit_count := v_unit_count + 1;
      v_j := v_j + 1;
    END LOOP;

    v_i := v_i + 1;
  END LOOP;

  RETURN jsonb_build_object(
    'book_id',       v_book_id,
    'display_id',    v_book_display_id,
    'chapter_count', v_ch_count,
    'unit_count',    v_unit_count
  );
END;
$$;


-- ── list_trans_books ───────────────────────────────────────────────────────────
-- Returns all active books with per-status unit counts in a single GROUP BY query.

CREATE OR REPLACE FUNCTION list_trans_books()
RETURNS TABLE (
  id               bigint,
  display_id       text,
  title            text,
  status           text,
  created_at       timestamptz,
  chapter_count    bigint,
  unit_count       bigint,
  cnt_untranslated bigint,
  cnt_ai_drafted   bigint,
  cnt_in_review    bigint,
  cnt_revised      bigint,
  cnt_approved     bigint
)
LANGUAGE sql
SECURITY DEFINER
AS $$
  SELECT
    b.id,
    b.display_id,
    b.title,
    b.status,
    b.created_at,
    COUNT(DISTINCT c.id)                                        AS chapter_count,
    COUNT(u.id)                                                 AS unit_count,
    COUNT(CASE WHEN u.status = 'untranslated' THEN 1 END)       AS cnt_untranslated,
    COUNT(CASE WHEN u.status = 'ai_drafted'   THEN 1 END)       AS cnt_ai_drafted,
    COUNT(CASE WHEN u.status = 'in_review'    THEN 1 END)       AS cnt_in_review,
    COUNT(CASE WHEN u.status = 'revised'      THEN 1 END)       AS cnt_revised,
    COUNT(CASE WHEN u.status = 'approved'     THEN 1 END)       AS cnt_approved
  FROM trans_books b
  LEFT JOIN trans_chapters c ON c.book_id = b.id
  LEFT JOIN trans_units    u ON u.chapter_id = c.id
  WHERE b.status = 'active'
  GROUP BY b.id, b.display_id, b.title, b.status, b.created_at
  ORDER BY b.created_at DESC;
$$;
