-- 011: Persist "Ask AI" doctrinal context on terms so it survives page
-- reloads and can be toggled back into view without re-calling the AI.
ALTER TABLE terms ADD COLUMN IF NOT EXISTS ai_context text;
ALTER TABLE terms ADD COLUMN IF NOT EXISTS ai_context_generated_at timestamptz;
