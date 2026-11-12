ALTER TABLE public.document_case_routing_events
  DROP CONSTRAINT IF EXISTS document_case_routing_events_event_type_check;
ALTER TABLE public.document_case_routing_events
  ADD CONSTRAINT document_case_routing_events_event_type_check
  CHECK (event_type IN ('suggestion', 'confirmation', 'correction'));
