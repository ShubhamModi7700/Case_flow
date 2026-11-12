CREATE TABLE IF NOT EXISTS public.document_case_routing_events (
    id VARCHAR(36) PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES public.documents(id) ON DELETE CASCADE,
    actor_id INTEGER REFERENCES public.users(id) ON DELETE SET NULL,
    event_type VARCHAR(32) NOT NULL CHECK (event_type IN ('suggestion','confirmation')),
    decision VARCHAR(32) NOT NULL,
    suggested_case_id INTEGER,
    assigned_case_id INTEGER,
    confidence DOUBLE PRECISION CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
    reason TEXT,
    details TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_document_case_routing_events_document_id
    ON public.document_case_routing_events(document_id, created_at DESC);
