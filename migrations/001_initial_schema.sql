-- migrations/001_initial_schema.sql
-- T0-1: Initial Supabase schema for T-CAT Buddhist Vocabulary Tool
-- Strictly follows the DDL in docs/T-CAT翻譯模組設計指南.md appendix.
--
-- Safe to run on a fresh project or one with the interim tables from
-- migration stages 1-6 (all interim tables were empty, so DROP is safe).

-- ============ Cleanup: drop interim tables from earlier exploration ============

drop table if exists extraction_paragraphs cascade;
drop table if exists extraction_documents  cascade;
drop table if exists votes                 cascade;

-- These may already exist with a different PK structure; drop and recreate.
drop table if exists audit_log cascade;
drop table if exists terms     cascade;
drop table if exists sources   cascade;
drop table if exists members   cascade;

-- ============ Extension ============

create extension if not exists vector;

-- ============ Six existing-system tables ============

create table members (
  id         bigint generated always as identity primary key,
  email      text not null unique,
  role       text not null check (role in ('viewer','depositor','member','leader','admin')),
  name       text,
  short_name text,
  added_by   text,
  added_at   timestamptz default now()
);

create table sources (
  id          bigint generated always as identity primary key,
  display_id  text unique,          -- original SourceID (S000001 style)
  source_name text not null,
  source_type text,
  notes       text
);

create sequence if not exists seq_terms_display start 1;

create table terms (
  id                     bigint generated always as identity primary key,
  display_id             text unique not null, -- T000001
  chinese                text not null,
  pinyin                 text,
  pali                   text,
  sanskrit               text,
  context                text,
  category               text,
  notes                  text,
  translation1           text,
  translation2           text,
  translation3           text,
  translation_first      text,
  translation_second     text,
  translation_other1     text,
  translation_other2     text,
  translation_known      text,
  final                  text,
  status                 text default 'pending' check (status in ('pending','finalized')),
  source                 text,
  romanization_plain     text,
  source_content_chinese text,
  source_content_english text,
  added_by               text,
  added_at               timestamptz default now(),
  last_modified_by       text,
  last_modified_at       timestamptz
);
create index idx_terms_chinese on terms (chinese);
create index idx_terms_status  on terms (status);

create table audit_log (
  id            bigint generated always as identity primary key,
  ts            timestamptz default now(),
  term_id       text,                    -- string type; no FK (historical rows may ref deleted terms)
  term_chinese  text,
  user_email    text,
  user_name     text,
  action_type   text,
  field_changed text,
  old_value     text,
  new_value     text,
  details       text
);
create index idx_audit_ts on audit_log (ts desc);

create sequence if not exists seq_ext_documents_display start 1;

create table ext_documents (
  id                bigint generated always as identity primary key,
  display_id        text unique not null, -- D000001
  title             text not null,
  source_name       text,
  paragraph_count   int,
  uploaded_by       text,
  uploaded_at       timestamptz default now(),
  last_viewed_index int default 0,
  status            text default 'active'
);

create table ext_paragraphs (
  id              bigint generated always as identity primary key,
  document_id     bigint not null references ext_documents(id),
  paragraph_index int not null,
  chinese_text    text,
  english_text    text,
  unique (document_id, paragraph_index)
);

-- ============ Five translation-module tables ============

create sequence if not exists seq_trans_books_display    start 1;
create sequence if not exists seq_trans_chapters_display start 1;
create sequence if not exists seq_trans_units_display    start 1;
create sequence if not exists seq_trans_revisions_display start 1;
create sequence if not exists seq_style_guide_display    start 1;

create table trans_books (
  id         bigint generated always as identity primary key,
  display_id text unique not null, -- B000001
  title      text not null,
  source_id  bigint references sources(id),
  created_by text,
  created_at timestamptz default now(),
  status     text default 'active' check (status in ('active','archived'))
);

create table trans_chapters (
  id            bigint generated always as identity primary key,
  display_id    text unique not null, -- C000001
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

create table trans_units (
  id               bigint generated always as identity primary key,
  display_id       text unique not null, -- U000001
  chapter_id       bigint not null references trans_chapters(id),
  paragraph_index  int not null,
  unit_order       numeric not null,     -- fractional indexing for split-insert
  chinese_text     text not null,
  english_draft    text,                 -- AI initial translation, never overwritten
  english_final    text,                 -- current approved translation
  split_map        jsonb,                -- [{zh, en}] for long-sentence split mapping
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
create index idx_units_chapter on trans_units (chapter_id, paragraph_index, unit_order);
create index idx_units_status  on trans_units (status);

create table trans_revisions (
  id            bigint generated always as identity primary key,
  display_id    text unique not null, -- R000001
  unit_id       bigint not null references trans_units(id),
  chinese_text  text not null,        -- redundant snapshot in case source unit is later split/merged
  english_before text,
  english_after  text,
  revision_type text
    check (revision_type in ('terminology','tone','grammar','split','other')),
  note          text,
  revised_by    text,
  revised_at    timestamptz default now(),
  embedding     vector(1536)
);
create index idx_revisions_unit on trans_revisions (unit_id);

create table style_guide (
  id                  bigint generated always as identity primary key,
  display_id          text unique not null, -- S000001
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
