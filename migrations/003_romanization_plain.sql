-- Migration 003: backfill romanization_plain + trigger to keep it in sync

CREATE EXTENSION IF NOT EXISTS unaccent;

CREATE OR REPLACE FUNCTION set_romanization_plain()
RETURNS trigger AS $$
BEGIN
  IF NEW.pinyin IS NOT NULL THEN
    NEW.romanization_plain := lower(unaccent(NEW.pinyin));
  ELSE
    NEW.romanization_plain := NULL;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_set_romanization_plain ON terms;
CREATE TRIGGER trg_set_romanization_plain
  BEFORE INSERT OR UPDATE OF pinyin ON terms
  FOR EACH ROW
  EXECUTE FUNCTION set_romanization_plain();

UPDATE terms SET romanization_plain = lower(unaccent(pinyin)) WHERE pinyin IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_terms_romanization_plain ON terms (romanization_plain);
