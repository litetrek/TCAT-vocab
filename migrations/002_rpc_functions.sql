-- migrations/002_rpc_functions.sql
-- T0-3 fix: supabase-py REST layer — atomic RPC functions + utility helpers
--
-- Why this file exists:
--   psycopg2 direct TCP (port 5432/6543) is blocked on GreenGeeks shared hosting.
--   All DB access now goes through supabase-py HTTPS REST (PostgREST).
--   PostgREST calls are individual HTTP requests, not transactions.
--   This file provides PL/pgSQL functions that wrap multi-table writes in a
--   single Postgres transaction, callable via .rpc() from Python.

-- ── Sequence for sources display IDs ─────────────────────────────────────────
-- sources.display_id values imported from Sheets use ad-hoc formats (S01, S002…).
-- New rows will use this sequence → S000006, S000007, …  (unique, no collision).

CREATE SEQUENCE IF NOT EXISTS seq_sources_display;

-- Advance past the highest numeric suffix currently in the table.
DO $$
DECLARE v_max bigint;
BEGIN
  SELECT MAX(CAST(SUBSTRING(display_id FROM 2) AS BIGINT))
    INTO v_max
    FROM sources
    WHERE display_id ~ '^S[0-9]+$';
  IF v_max IS NULL THEN
    PERFORM setval('seq_sources_display', 1, false); -- next nextval = 1
  ELSE
    PERFORM setval('seq_sources_display', v_max);    -- next nextval = v_max + 1
  END IF;
END;
$$;

-- ── Check constraint on audit_log ─────────────────────────────────────────────
-- NOT VALID: constraint applies only to new rows; existing test-era rows are kept.
-- This constraint enables the transaction rollback acceptance test:
--   call update_term_field_with_audit(..., p_action => 'INVALID') → audit INSERT
--   fails the check → whole transaction rolls back → terms row unchanged.

ALTER TABLE audit_log
  DROP CONSTRAINT IF EXISTS chk_audit_action_type;

ALTER TABLE audit_log
  ADD CONSTRAINT chk_audit_action_type
  CHECK (action_type IN (
    'created', 'updated',
    'finalized_first', 'finalized_second', 'reset_final',
    'ai_translated', 'login', 'logout', 'other'
  ))
  NOT VALID;

-- ── next_display_id ───────────────────────────────────────────────────────────
-- Returns the next formatted ID for any sequence:
--   next_display_id('T', 'seq_terms_display')  →  'T002845'
--   next_display_id('S', 'seq_sources_display') →  'S000006'

CREATE OR REPLACE FUNCTION next_display_id(p_prefix text, p_seq_name text)
RETURNS text
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
  RETURN p_prefix || lpad(nextval(p_seq_name)::text, 6, '0');
END;
$$;

-- ── update_term_field_with_audit ──────────────────────────────────────────────
-- Atomically: SELECT old value → UPDATE terms → INSERT audit_log.
-- Returns jsonb:  {found: bool, chinese: text, old_value: text}
-- Rollback test:  pass p_action = 'INVALID' to trigger the chk_audit_action_type
--                 constraint and verify terms row is NOT partially updated.

CREATE OR REPLACE FUNCTION update_term_field_with_audit(
  p_term_id   text,
  p_db_col    text,       -- Postgres column name, e.g. 'translation1'
  p_value     text,       -- new value (empty string stored as NULL)
  p_roman     text,       -- romanization_plain; pass NULL when not a pinyin update
  p_modifier  text,
  p_now       text,       -- timestamp string, e.g. '2026-01-01 12:00'
  p_user_name text,
  p_action    text,       -- must satisfy chk_audit_action_type
  p_field_lbl text,
  p_old_val   text,       -- pre-computed old value from caller; ignored if empty
  p_new_val   text,
  p_details   text
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_chinese text;
  v_old_val text;
BEGIN
  EXECUTE format('SELECT chinese, %I FROM terms WHERE display_id = $1', p_db_col)
    INTO v_chinese, v_old_val
    USING p_term_id;

  IF v_chinese IS NULL THEN
    RETURN jsonb_build_object('found', false);
  END IF;

  IF p_roman IS NOT NULL THEN
    EXECUTE format(
      'UPDATE terms SET %I = $1, romanization_plain = $2,
       last_modified_by = $3, last_modified_at = $4 WHERE display_id = $5',
      p_db_col
    ) USING
      NULLIF(p_value, ''),
      p_roman,
      p_modifier,
      NULLIF(p_now, '')::timestamptz,
      p_term_id;
  ELSE
    EXECUTE format(
      'UPDATE terms SET %I = $1,
       last_modified_by = $2, last_modified_at = $3 WHERE display_id = $4',
      p_db_col
    ) USING
      NULLIF(p_value, ''),
      p_modifier,
      NULLIF(p_now, '')::timestamptz,
      p_term_id;
  END IF;

  INSERT INTO audit_log (
    term_id, term_chinese, user_email, user_name,
    action_type, field_changed, old_value, new_value, details
  ) VALUES (
    p_term_id,
    v_chinese,
    NULLIF(p_modifier,  ''),
    NULLIF(p_user_name, ''),
    NULLIF(p_action,    ''),   -- constraint fires here if invalid
    NULLIF(p_field_lbl, ''),
    NULLIF(COALESCE(NULLIF(p_old_val, ''), v_old_val, ''), ''),
    NULLIF(p_new_val,   ''),
    NULLIF(p_details,   '')
  );

  RETURN jsonb_build_object(
    'found',     true,
    'chinese',   v_chinese,
    'old_value', COALESCE(v_old_val, '')
  );
END;
$$;

-- ── set_final_with_audit ──────────────────────────────────────────────────────
-- Atomically: read vote column → UPDATE terms (first or second choice) →
-- INSERT audit_log.
-- Returns jsonb: {found: bool, text: text, chinese: text}

CREATE OR REPLACE FUNCTION set_final_with_audit(
  p_term_id   text,
  p_db_col    text,      -- vote column, e.g. 'translation1'
  p_vote_key  text,      -- e.g. 'Translation1'
  p_which     text,      -- 'first' or 'second'
  p_modifier  text,
  p_now       text,
  p_user_name text,
  p_action    text,
  p_field_lbl text,
  p_new_val   text,
  p_details   text
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_chinese text;
  v_text    text;
BEGIN
  EXECUTE format('SELECT chinese, %I FROM terms WHERE display_id = $1', p_db_col)
    INTO v_chinese, v_text
    USING p_term_id;

  IF v_chinese IS NULL THEN
    RETURN jsonb_build_object('found', false);
  END IF;

  IF p_which = 'first' THEN
    UPDATE terms SET
      translation_first = v_text,
      final             = p_vote_key,
      status            = 'finalized',
      last_modified_by  = p_modifier,
      last_modified_at  = NULLIF(p_now, '')::timestamptz
    WHERE display_id = p_term_id;
  ELSE
    UPDATE terms SET
      translation_second = v_text,
      last_modified_by   = p_modifier,
      last_modified_at   = NULLIF(p_now, '')::timestamptz
    WHERE display_id = p_term_id;
  END IF;

  INSERT INTO audit_log (
    term_id, term_chinese, user_email, user_name,
    action_type, field_changed, new_value, details
  ) VALUES (
    p_term_id, v_chinese,
    NULLIF(p_modifier,  ''),
    NULLIF(p_user_name, ''),
    NULLIF(p_action,    ''),
    NULLIF(p_field_lbl, ''),
    NULLIF(p_new_val,   ''),
    NULLIF(p_details,   '')
  );

  RETURN jsonb_build_object(
    'found',   true,
    'text',    COALESCE(v_text, ''),
    'chinese', v_chinese
  );
END;
$$;

-- ── reset_final_with_audit ────────────────────────────────────────────────────
-- Atomically: read current values → clear finalization fields → INSERT audit_log.
-- Returns jsonb: {found: bool, chinese: text, old_first: text, old_second: text}

CREATE OR REPLACE FUNCTION reset_final_with_audit(
  p_term_id   text,
  p_modifier  text,
  p_now       text,
  p_user_name text,
  p_details   text
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_chinese    text;
  v_old_first  text;
  v_old_second text;
BEGIN
  SELECT chinese, translation_first, translation_second
    INTO v_chinese, v_old_first, v_old_second
    FROM terms
    WHERE display_id = p_term_id;

  IF v_chinese IS NULL THEN
    RETURN jsonb_build_object('found', false);
  END IF;

  UPDATE terms SET
    translation_first  = NULL,
    translation_second = NULL,
    final              = NULL,
    status             = 'pending',
    last_modified_by   = p_modifier,
    last_modified_at   = NULLIF(p_now, '')::timestamptz
  WHERE display_id = p_term_id;

  INSERT INTO audit_log (
    term_id, term_chinese, user_email, user_name, action_type, details
  ) VALUES (
    p_term_id, v_chinese,
    NULLIF(p_modifier,  ''),
    NULLIF(p_user_name, ''),
    'reset_final',
    NULLIF(p_details, '')
  );

  RETURN jsonb_build_object(
    'found',      true,
    'chinese',    v_chinese,
    'old_first',  COALESCE(v_old_first,  ''),
    'old_second', COALESCE(v_old_second, '')
  );
END;
$$;

-- ── create_document_with_paragraphs ──────────────────────────────────────────
-- Atomically: INSERT ext_documents + all ext_paragraphs rows.
-- If paragraph insert fails (e.g. duplicate index), the whole transaction
-- rolls back, leaving no orphaned document.
-- p_paragraphs: JSONB array of {zh: text, en: text} objects.
-- Returns the display_id on success.

CREATE OR REPLACE FUNCTION create_document_with_paragraphs(
  p_display_id  text,
  p_title       text,
  p_source_name text,
  p_para_count  int,
  p_uploaded_by text,
  p_uploaded_at text,
  p_paragraphs  jsonb
) RETURNS text
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_doc_id bigint;
  v_len    int;
  v_i      int := 0;
BEGIN
  INSERT INTO ext_documents (
    display_id, title, source_name, paragraph_count,
    uploaded_by, uploaded_at, last_viewed_index, status
  ) VALUES (
    p_display_id,
    p_title,
    p_source_name,
    p_para_count,
    NULLIF(p_uploaded_by, ''),
    CASE WHEN p_uploaded_at IS NULL OR p_uploaded_at = ''
         THEN now()
         ELSE p_uploaded_at::timestamptz
    END,
    0,
    'active'
  )
  RETURNING id INTO v_doc_id;

  v_len := jsonb_array_length(p_paragraphs);
  WHILE v_i < v_len LOOP
    INSERT INTO ext_paragraphs (document_id, paragraph_index, chinese_text, english_text)
    VALUES (
      v_doc_id,
      v_i,
      p_paragraphs->v_i->>'zh',
      p_paragraphs->v_i->>'en'
    );
    v_i := v_i + 1;
  END LOOP;

  RETURN p_display_id;
END;
$$;
