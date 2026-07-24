-- Migration 014: add 'inactive' status for soft-hiding duplicate or unwanted terms
ALTER TABLE terms DROP CONSTRAINT IF EXISTS terms_status_check;
ALTER TABLE terms ADD CONSTRAINT terms_status_check
  CHECK (status IN ('new', 'pending', 'reviewed', 'finalized', 'suggested', 'inactive'));
