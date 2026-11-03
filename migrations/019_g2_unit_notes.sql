-- 019 (Stage G2): translator notes on a translation unit.
--
-- Append-only list per unit; each note keeps its author. The author or a Leader+
-- can delete a note. rule_id is filled in G3 when a note has been summarised into a
-- Style Guide rule, so the same notes are not summarised twice.
-- Applied to Supabase (TCAT-vocab) 2026-11-02.

create table if not exists trans_unit_notes (
  id           bigint generated always as identity primary key,
  unit_id      bigint not null references trans_units(id) on delete cascade,
  note_text    text not null,
  author_email text,
  author_name  text,
  created_at   timestamptz default now(),
  rule_id      bigint references style_guide(id) on delete set null
);
create index if not exists idx_unit_notes_unit on trans_unit_notes (unit_id);
