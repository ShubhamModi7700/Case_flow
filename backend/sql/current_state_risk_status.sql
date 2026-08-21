ALTER TABLE case_ai_summaries
    ADD COLUMN IF NOT EXISTS suggested_status VARCHAR(30);

ALTER TABLE case_ai_summaries
    ADD COLUMN IF NOT EXISTS status_reason TEXT;
