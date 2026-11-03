-- 018 (Stage G1): keep the AI's reasoning and the glossary check with each unit.
--
-- ai_reasoning:     2–4 short notes from the AI on its latest draft (term choices,
--                   restructuring, ambiguities) — shown collapsed under the English box.
-- missing_terms:    required glossary renderings the current English leaves out (F3 check);
--                   set by AI Translate, re-checked on every Save. Was only in the response.
-- ai_translated_at: when the latest AI draft was written (labels the reasoning).
-- Applied to Supabase (TCAT-vocab) 2026-11-02.

ALTER TABLE public.trans_units
  ADD COLUMN IF NOT EXISTS ai_reasoning     jsonb,
  ADD COLUMN IF NOT EXISTS missing_terms    jsonb,
  ADD COLUMN IF NOT EXISTS ai_translated_at timestamptz;
