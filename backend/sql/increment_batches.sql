CREATE TABLE IF NOT EXISTS document_upload_batches (
    id VARCHAR(36) PRIMARY KEY,
    owner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    case_id INTEGER REFERENCES cases(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_document_upload_batches_owner_id ON document_upload_batches(owner_id);
CREATE TABLE IF NOT EXISTS document_upload_batch_items (
    id VARCHAR(36) PRIMARY KEY,
    batch_id VARCHAR(36) NOT NULL REFERENCES document_upload_batches(id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    document_id INTEGER UNIQUE REFERENCES documents(id) ON DELETE SET NULL,
    upload_status VARCHAR(20) NOT NULL DEFAULT 'Pending',
    upload_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_document_upload_batch_items_batch_id ON document_upload_batch_items(batch_id);
