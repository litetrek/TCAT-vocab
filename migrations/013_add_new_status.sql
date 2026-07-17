-- Migration 013: add 'new' status, migrate existing 'pending' records to 'new'
ALTER TABLE terms DROP CONSTRAINT IF EXISTS terms_status_check;
ALTER TABLE terms ADD CONSTRAINT terms_status_check
  CHECK (status IN ('new', 'pending', 'reviewed', 'finalized', 'suggested'));
UPDATE terms SET status = 'new' WHERE status = 'pending';
