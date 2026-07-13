-- migrations/010_dual_embeddings.sql
-- T4.2: Replace single embedding column with dual-provider columns (Voyage + OpenAI)
-- and add two RPC functions for vector similarity search.

-- Drop the old single-provider embedding column (defined in 005, may be NULL for all rows)
alter table trans_revisions drop column if exists embedding;

-- Add per-provider embedding columns
alter table trans_revisions add column if not exists embedding_voyage vector(1024);
alter table trans_revisions add column if not exists embedding_openai vector(1536);

-- RPC: find similar revisions using Voyage AI embeddings (1024-dim)
create or replace function find_similar_revisions_voyage(
    query_embedding vector(1024),
    match_limit int default 5
)
returns table(id bigint, display_id text, chinese_text text, english_after text, similarity float)
language sql stable as $$
    select id, display_id, chinese_text, english_after,
           1 - (embedding_voyage <=> query_embedding) as similarity
    from trans_revisions
    where embedding_voyage is not null
    order by embedding_voyage <=> query_embedding
    limit match_limit;
$$;

-- RPC: find similar revisions using OpenAI embeddings (1536-dim)
create or replace function find_similar_revisions_openai(
    query_embedding vector(1536),
    match_limit int default 5
)
returns table(id bigint, display_id text, chinese_text text, english_after text, similarity float)
language sql stable as $$
    select id, display_id, chinese_text, english_after,
           1 - (embedding_openai <=> query_embedding) as similarity
    from trans_revisions
    where embedding_openai is not null
    order by embedding_openai <=> query_embedding
    limit match_limit;
$$;
