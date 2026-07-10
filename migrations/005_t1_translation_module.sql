-- migrations/005_t1_translation_module.sql
-- T1: Ensure five translation-module tables exist with correct structure.
-- Idempotent: uses IF NOT EXISTS throughout (tables were defined in 001 but
-- this migration acts as the canonical T1 delivery record).

-- ============ Sequences ============

create sequence if not exists seq_trans_books_display      start 1;
create sequence if not exists seq_trans_chapters_display   start 1;
create sequence if not exists seq_trans_units_display      start 1;
create sequence if not exists seq_trans_revisions_display  start 1;
create sequence if not exists seq_style_guide_display      start 1;

-- ============ Tables ============

create table if not exists trans_books (
  id         bigint generated always as identity primary key,
  display_id text unique not null,
  title      text not null,
  source_id  bigint references sources(id),
  created_by text,
  created_at timestamptz default now(),
  status     text default 'active' check (status in ('active','archived'))
);

create table if not exists trans_chapters (
  id            bigint generated always as identity primary key,
  display_id    text unique not null,
  book_id       bigint not null references trans_books(id),
  chapter_index int not null,
  title         text,
  section_type  text default 'body'
    check (section_type in ('body','editorial','preface','postscript')),
  claimed_by    text,
  status        text default 'not_started'
    check (status in ('not_started','in_progress','in_review','completed')),
  unique (book_id, chapter_index)
);

create table if not exists trans_units (
  id               bigint generated always as identity primary key,
  display_id       text unique not null,
  chapter_id       bigint not null references trans_chapters(id),
  paragraph_index  int not null,
  unit_order       numeric not null,
  chinese_text     text not null,
  english_draft    text,
  english_final    text,
  split_map        jsonb,
  status           text default 'untranslated'
    check (status in ('untranslated','ai_drafted','in_review','revised','approved')),
  is_long_sentence boolean default false,
  ai_model         text,
  merged_into      bigint references trans_units(id),
  translated_by    text,
  reviewed_by      text,
  approved_by      text,
  last_modified_by text,
  last_modified_at timestamptz
);
create index if not exists idx_units_chapter on trans_units (chapter_id, paragraph_index, unit_order);
create index if not exists idx_units_status  on trans_units (status);

create table if not exists trans_revisions (
  id             bigint generated always as identity primary key,
  display_id     text unique not null,
  unit_id        bigint not null references trans_units(id),
  chinese_text   text not null,
  english_before text,
  english_after  text,
  revision_type  text
    check (revision_type in ('terminology','tone','grammar','split','other')),
  note           text,
  revised_by     text,
  revised_at     timestamptz default now(),
  embedding      vector(1536)
);
create index if not exists idx_revisions_unit on trans_revisions (unit_id);

create table if not exists style_guide (
  id                  bigint generated always as identity primary key,
  display_id          text unique not null,
  category            text check (category in
    ('honorifics','proper_nouns','sentence_splitting','tone','other')),
  rule_text           text not null,
  example_before      text,
  example_after       text,
  active              boolean default true,
  source_revision_ids bigint[],
  created_by          text,
  created_at          timestamptz default now()
);
