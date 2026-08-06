begin;

-- Add vector index for case matching
create index if not exists ix_case_embeddings_embedding
on public.case_embeddings
using hnsw (embedding vector_cosine_ops);

-- Add useful indexes for suggestions
create index if not exists ix_ai_document_suggestions_document
on public.ai_document_suggestions(document_id);

create index if not exists ix_ai_document_suggestions_current_case
on public.ai_document_suggestions(current_case_id);

create index if not exists ix_ai_document_suggestions_suggested_case
on public.ai_document_suggestions(suggested_case_id);

create index if not exists ix_ai_document_suggestions_status
on public.ai_document_suggestions(status);

create index if not exists ix_case_ai_summaries_case
on public.case_ai_summaries(case_id);

create index if not exists ix_case_ai_summaries_status
on public.case_ai_summaries(status);

-- Validate document processing status
alter table public.documents
drop constraint if exists documents_processing_status_check;

alter table public.documents
add constraint documents_processing_status_check
check (
  processing_status in (
    'Uploaded',
    'Extracting',
    'Chunking',
    'Embedding',
    'Ready',
    'Failed'
  )
);

-- Validate embedding status
alter table public.documents
drop constraint if exists documents_embedding_status_check;

alter table public.documents
add constraint documents_embedding_status_check
check (
  embedding_status in (
    'Pending',
    'Processing',
    'Ready',
    'Failed',
    'Outdated'
  )
);

-- Validate AI suggestion status
alter table public.ai_document_suggestions
drop constraint if exists ai_document_suggestions_status_check;

alter table public.ai_document_suggestions
add constraint ai_document_suggestions_status_check
check (
  status in (
    'Pending',
    'Approved',
    'EditedAndApproved',
    'Rejected',
    'Failed',
    'Outdated'
  )
);

-- Validate management summary status
alter table public.case_ai_summaries
drop constraint if exists case_ai_summaries_status_check;

alter table public.case_ai_summaries
add constraint case_ai_summaries_status_check
check (
  status in (
    'Pending',
    'Approved',
    'EditedAndApproved',
    'Rejected',
    'Failed',
    'Outdated'
  )
);

-- Validate case-match confidence
alter table public.ai_document_suggestions
drop constraint if exists ai_document_suggestions_confidence_check;

alter table public.ai_document_suggestions
add constraint ai_document_suggestions_confidence_check
check (
  case_match_confidence is null
  or case_match_confidence between 0 and 1
);

-- Automatically update updated_at
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists trg_document_chunks_updated_at
on public.document_chunks;

create trigger trg_document_chunks_updated_at
before update on public.document_chunks
for each row
execute function public.set_updated_at();

drop trigger if exists trg_case_embeddings_updated_at
on public.case_embeddings;

create trigger trg_case_embeddings_updated_at
before update on public.case_embeddings
for each row
execute function public.set_updated_at();

-- Replace document chunk search function
create or replace function public.match_document_chunks(
  query_embedding extensions.vector(1536),
  requested_case_id integer default null,
  requested_document_id integer default null,
  match_threshold float default 0.55,
  match_count integer default 12
)
returns table (
  chunk_id bigint,
  document_id integer,
  case_id integer,
  content text,
  source_type varchar,
  page_number integer,
  sheet_name varchar,
  metadata jsonb,
  similarity float
)
language sql
stable
as $$
  select
    dc.id as chunk_id,
    dc.document_id as document_id,
    dc.case_id as case_id,
    dc.content as content,
    dc.source_type as source_type,
    dc.page_number as page_number,
    dc.sheet_name as sheet_name,
    dc.metadata as metadata,
    (
      1 - (dc.embedding <=> query_embedding)
    )::float as similarity
  from public.document_chunks dc
  where dc.embedding is not null
    and (
      requested_case_id is null
      or dc.case_id = requested_case_id
    )
    and (
      requested_document_id is null
      or dc.document_id = requested_document_id
    )
    and (
      1 - (dc.embedding <=> query_embedding)
    ) >= match_threshold
  order by dc.embedding <=> query_embedding
  limit greatest(match_count, 0);
$$;

-- Replace case search function
create or replace function public.match_cases(
  query_embedding extensions.vector(1536),
  match_count integer default 5
)
returns table (
  case_id integer,
  similarity float
)
language sql
stable
as $$
  select
    ce.case_id as case_id,
    (
      1 - (ce.embedding <=> query_embedding)
    )::float as similarity
  from public.case_embeddings ce
  where ce.embedding is not null
  order by ce.embedding <=> query_embedding
  limit greatest(match_count, 0);
$$;

commit;