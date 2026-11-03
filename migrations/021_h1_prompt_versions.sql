-- 021 (Stage H1): editable AI translation instructions with version history.
--
-- prompt_versions: every saved version of an editable prompt text, never edited in place.
--   prompt_key 'translate_base' = the base instructions (system prompt) of sentence
--   translation; the output format and dynamic blocks stay in code (ai.py).
--   Exactly one active row per prompt_key (partial unique index). Save / restore go
--   through the two functions below so the switch is atomic.
-- trans_units.prompt_version: the 'translate_base' version that produced the AI draft.

create table if not exists prompt_versions (
  id          bigint generated always as identity primary key,
  prompt_key  text not null,
  version     int  not null,
  content     text not null,
  note        text,
  created_by  text,
  created_at  timestamptz not null default now(),
  is_active   boolean not null default false,
  unique (prompt_key, version)
);
create unique index if not exists uq_prompt_versions_active
  on prompt_versions (prompt_key) where is_active;

alter table prompt_versions enable row level security;

alter table trans_units add column if not exists prompt_version int;

-- New version = max + 1, made active; the previous active row is deactivated.
create or replace function save_prompt_version(p_key text, p_content text, p_note text, p_user text)
returns prompt_versions language plpgsql as $$
declare
  v_next int;
  v_row  prompt_versions;
begin
  perform pg_advisory_xact_lock(hashtext('prompt_versions:' || p_key));
  select coalesce(max(version), 0) + 1 into v_next from prompt_versions where prompt_key = p_key;
  update prompt_versions set is_active = false where prompt_key = p_key and is_active;
  insert into prompt_versions (prompt_key, version, content, note, created_by, is_active)
  values (p_key, v_next, p_content, p_note, p_user, true)
  returning * into v_row;
  return v_row;
end $$;

-- Make an existing version the active one (rollback / restore).
create or replace function activate_prompt_version(p_key text, p_version int)
returns prompt_versions language plpgsql as $$
declare
  v_row prompt_versions;
begin
  perform pg_advisory_xact_lock(hashtext('prompt_versions:' || p_key));
  if not exists (select 1 from prompt_versions where prompt_key = p_key and version = p_version) then
    return null;
  end if;
  update prompt_versions set is_active = false where prompt_key = p_key and is_active;
  update prompt_versions set is_active = true where prompt_key = p_key and version = p_version
  returning * into v_row;
  return v_row;
end $$;

-- Version 1 = the instructions hard-coded before H1 (ai.DEFAULT_TRANSLATION_INSTRUCTIONS).
insert into prompt_versions (prompt_key, version, content, note, created_by, is_active)
select 'translate_base', 1,
$txt$You are an expert translator of Chinese Buddhist texts — Vajrayana and Chinese Buddhist teaching literature — into English, writing for a scholarly but accessible readership.
- Be faithful to the meaning of the source; do not add content that is not in it.
- Write natural, readable English rather than a word-for-word rendering.
- Where it helps the English, split a long Chinese sentence into several English sentences.
- Use the REQUIRED TERMINOLOGY, adapted grammatically to the sentence as its rules allow.
- Translate only the target sentence; any surrounding text is context.$txt$,
  'Initial version — the instructions used before Stage H1', 'system', true
where not exists (select 1 from prompt_versions where prompt_key = 'translate_base');
