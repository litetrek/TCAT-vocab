-- 020 (Stage G3): Style Guide rules drafted from translator notes.
--
-- proposed:    true while a Member's rule waits for a Leader (active stays false, so it is
--              never sent to the AI). A rule a Leader adds is active at once.
-- book_id:     null = applies to every book (as before); set = only that book's translations.
-- approved_by / approved_at: the Leader who made the rule active.
-- Notes summarised into a rule point at it via trans_unit_notes.rule_id (migration 019).
-- Applied to Supabase (TCAT-vocab) 2026-11-02.

ALTER TABLE public.style_guide
  ADD COLUMN IF NOT EXISTS proposed    boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS book_id     bigint REFERENCES trans_books(id) ON DELETE CASCADE,
  ADD COLUMN IF NOT EXISTS approved_by text,
  ADD COLUMN IF NOT EXISTS approved_at timestamptz;
