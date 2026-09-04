-- migrations/015_term_sources_many_to_many.sql
-- Replace terms.source (single text SourceID) with a many-to-many join table,
-- so one term can be linked to several source books without duplicating the term.

create table if not exists term_sources (
  term_id   bigint not null references terms(id) on delete cascade,
  source_id bigint not null references sources(id) on delete cascade,
  primary key (term_id, source_id)
);
create index if not exists idx_term_sources_term   on term_sources(term_id);
create index if not exists idx_term_sources_source on term_sources(source_id);

-- Backfill from the old single-valued terms.source column
insert into term_sources (term_id, source_id)
select t.id, s.id
from terms t
join sources s on s.display_id = t.source
where t.source is not null and t.source <> ''
on conflict do nothing;

alter table terms drop column if exists source;
