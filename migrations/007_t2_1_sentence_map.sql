-- migrations/007_t2_1_sentence_map.sql
-- T2.1: Add sentence_map to trans_units; create trans_unit_drafts for the
--       human-review / AI-grouping workflow.

-- sentence_map records which original sentences are merged into this unit.
-- NULL = legacy single-sentence unit (no sentence_map).
-- Non-NULL = AI/human-grouped multi-sentence unit.
alter table trans_units
  add column if not exists sentence_map jsonb;

-- ── trans_unit_drafts ──────────────────────────────────────────────────────
-- Holds AI-suggested and human-adjusted grouping drafts before they are
-- committed to trans_units.  One row per (chapter, paragraph).
-- draft_groups format:
--   [{"sentences": [{"text": "...", "is_long_sentence": bool}, ...]}, ...]
create table if not exists trans_unit_drafts (
  id                bigint generated always as identity primary key,
  chapter_id        bigint  not null references trans_chapters(id),
  paragraph_index   int     not null,
  draft_groups      jsonb   not null,
  status            text    default 'pending'
                    check (status in ('pending','ai_suggested','human_adjusted','confirmed')),
  last_modified_by  text,
  last_modified_at  timestamptz default now(),
  unique (chapter_id, paragraph_index)
);

create index if not exists idx_drafts_chapter
  on trans_unit_drafts (chapter_id, paragraph_index);
