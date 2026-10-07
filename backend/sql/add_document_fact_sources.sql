ALTER TABLE public.case_ai_summaries
ADD COLUMN IF NOT EXISTS document_fact_sources JSONB NOT NULL DEFAULT '[]'::jsonb;