-- 017: Drop the audit_log action_type CHECK constraint.
--
-- chk_audit_action_type only allowed 9 action names, but the app writes many more
-- (merged, deleted, marked_inactive, reviewed, ask_ai, ai_classified, ai_translate,
-- translation_saved, translation_approved, ...). write_audit() swallows errors, so those
-- audit rows were silently dropped. The app controls action names itself; no DB list.
-- Applied to Supabase (TCAT-vocab) 2026-10-27.

ALTER TABLE public.audit_log DROP CONSTRAINT IF EXISTS chk_audit_action_type;
