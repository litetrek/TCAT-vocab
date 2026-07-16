-- Migration 011: add 'suggested' to terms status check constraint
ALTER TABLE terms DROP CONSTRAINT IF EXISTS terms_status_check;
ALTER TABLE terms ADD CONSTRAINT terms_status_check
  CHECK (status IN ('pending', 'finalized', 'suggested'));
