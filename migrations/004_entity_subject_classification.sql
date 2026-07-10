-- Migration 004: Entity Type / Subject Field classification columns
-- Adds structured dual-axis classification to the terms table.
-- category column is preserved (not dropped) until UI migration is confirmed stable.

alter table terms add column if not exists entity_type text
  check (entity_type in ('人名','地名','寺院','宗派','書名典籍','佛菩薩尊號','概念術語','其他'));

alter table terms add column if not exists subject_field text
  check (subject_field in ('教義','戒律','禪修','因明','儀軌法物','稱謂教職','歷史事項','文學藝術','其他'));

-- 'ai' = AI-generated; 'manual' = human override
alter table terms add column if not exists classification_source text
  check (classification_source in ('ai','manual'));

alter table terms add column if not exists classified_by text;
alter table terms add column if not exists classified_at timestamptz;

create index if not exists idx_terms_entity_type on terms (entity_type);
create index if not exists idx_terms_subject_field on terms (subject_field);
