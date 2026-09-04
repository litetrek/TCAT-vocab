-- migrations/016_book_glossary.sql
-- Per-Translation-Book curated glossary: a Leader/Admin can mark a subset of a
-- book's known terms as glossary entries with an AI-drafted, human-editable,
-- bilingual (EN+ZH) explanation. Independent of term_sources (bibliographic
-- citation tagging) — this is editorial curation scoped to one specific book.

create sequence if not exists seq_glossary_display start 1;

create table book_glossary_terms (
  id                  bigint generated always as identity primary key,
  display_id          text unique not null,          -- G000001
  book_id             bigint not null references trans_books(id) on delete cascade,
  term_id             bigint not null references terms(id) on delete cascade,
  explanation         text,                            -- bilingual EN+ZH, AI-seeded, human-editable
  explanation_source  text default 'ai' check (explanation_source in ('ai','manual')),
  status              text default 'draft' check (status in ('draft','reviewed')),
  added_by            text,
  added_at            timestamptz default now(),
  last_modified_by    text,
  last_modified_at    timestamptz,
  unique (book_id, term_id)
);
create index idx_glossary_book on book_glossary_terms(book_id);
create index idx_glossary_term on book_glossary_terms(term_id);
