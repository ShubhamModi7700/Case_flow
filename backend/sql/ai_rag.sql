create extension if not exists vector with schema extensions;

alter table public.documents add column if not exists processing_status varchar(40) not null default 'Uploaded';
alter table public.documents add column if not exists processing_error text;
alter table public.documents add column if not exists embedding_status varchar(40) not null default 'Pending';
alter table public.documents add column if not exists chunk_count integer not null default 0;
alter table public.documents add column if not exists processed_at timestamptz;

create table if not exists public.document_chunks (
  id bigserial primary key,
  document_id integer not null references public.documents(id) on delete cascade,
  case_id integer references public.cases(id) on delete set null,
  chunk_index integer not null,
  content text not null,
  source_type varchar(30) not null,
  page_number integer,
  sheet_name varchar(255),
  email_section varchar(100),
  metadata jsonb not null default '{}'::jsonb,
  token_count integer,
  embedding extensions.vector(1536),
  embedding_model varchar(100) not null,
  embedding_version varchar(30) not null default 'v1',
  search_vector tsvector generated always as (to_tsvector('german', coalesce(content, ''))) stored,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(document_id, chunk_index)
);
create index if not exists ix_document_chunks_document on public.document_chunks(document_id);
create index if not exists ix_document_chunks_case on public.document_chunks(case_id);
create index if not exists ix_document_chunks_search on public.document_chunks using gin(search_vector);
create index if not exists ix_document_chunks_embedding on public.document_chunks using hnsw (embedding vector_cosine_ops);

create table if not exists public.case_embeddings (
  case_id integer primary key references public.cases(id) on delete cascade,
  searchable_text text not null,
  embedding extensions.vector(1536),
  embedding_model varchar(100) not null,
  updated_at timestamptz not null default now()
);

create table if not exists public.ai_document_suggestions (
  id bigserial primary key,
  document_id integer not null references public.documents(id) on delete cascade,
  current_case_id integer references public.cases(id) on delete set null,
  suggested_case_id integer references public.cases(id) on delete set null,
  case_match_confidence numeric(5,4),
  suggested_summary text,
  suggested_latest_development text,
  suggested_deadline date,
  deadline_source text,
  suggested_next_action text,
  suggested_risk varchar(20),
  suggested_risk_reason text,
  relevant_chunk_ids jsonb not null default '[]'::jsonb,
  relevant_document_ids jsonb not null default '[]'::jsonb,
  status varchar(40) not null default 'Pending',
  model_name varchar(100),
  prompt_version varchar(50),
  raw_response jsonb,
  created_by integer references public.users(id),
  reviewed_by integer references public.users(id),
  created_at timestamptz not null default now(),
  reviewed_at timestamptz
);

create table if not exists public.case_ai_summaries (
  id bigserial primary key,
  case_id integer not null references public.cases(id) on delete cascade,
  short_case_summary text,
  latest_development text,
  next_required_action text,
  open_deadline date,
  deadline_comment text,
  suggested_risk varchar(20),
  risk_comment text,
  relevant_document_ids jsonb not null default '[]'::jsonb,
  relevant_chunk_ids jsonb not null default '[]'::jsonb,
  status varchar(30) not null default 'Pending',
  model_name varchar(100),
  prompt_version varchar(50),
  generated_by integer references public.users(id),
  reviewed_by integer references public.users(id),
  created_at timestamptz not null default now(),
  reviewed_at timestamptz
);

create or replace function public.match_document_chunks(
  query_embedding extensions.vector(1536),
  requested_case_id integer default null,
  requested_document_id integer default null,
  match_threshold float default 0.55,
  match_count integer default 12
) returns table (
  chunk_id bigint, document_id integer, case_id integer, content text,
  source_type varchar, page_number integer, sheet_name varchar,
  metadata jsonb, similarity float
) language sql stable as $$
  select dc.id, dc.document_id, dc.case_id, dc.content, dc.source_type,
         dc.page_number, dc.sheet_name, dc.metadata,
         1 - (dc.embedding <=> query_embedding) as similarity
  from public.document_chunks dc
  where dc.embedding is not null
    and (requested_case_id is null or dc.case_id = requested_case_id)
    and (requested_document_id is null or dc.document_id = requested_document_id)
    and 1 - (dc.embedding <=> query_embedding) >= match_threshold
  order by dc.embedding <=> query_embedding
  limit match_count;
$$;

create or replace function public.match_cases(
  query_embedding extensions.vector(1536), match_count integer default 5
) returns table (case_id integer, similarity float)
language sql stable as $$
  select ce.case_id, 1 - (ce.embedding <=> query_embedding) as similarity
  from public.case_embeddings ce
  where ce.embedding is not null
  order by ce.embedding <=> query_embedding
  limit match_count;
$$;
