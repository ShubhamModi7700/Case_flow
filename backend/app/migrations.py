from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def migrate_case_company_fields(engine: Engine) -> None:
    """Add separate company/department fields and keep existing data usable."""
    inspector = inspect(engine)
    if "cases" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("cases")}

    with engine.begin() as connection:
        if "company" not in columns:
            connection.execute(text("ALTER TABLE cases ADD COLUMN company VARCHAR(200)"))
        if "department" not in columns:
            connection.execute(text("ALTER TABLE cases ADD COLUMN department VARCHAR(200)"))

        # Preserve existing values. Old combined values become the company value;
        # users can refine the department later in the edit form.
        if "company_department" in columns:
            connection.execute(text("""
                UPDATE cases
                SET company = COALESCE(NULLIF(TRIM(company), ''), NULLIF(TRIM(company_department), ''))
                WHERE company IS NULL OR TRIM(company) = ''
            """))
        if "title" in columns:
            connection.execute(text("""
                UPDATE cases
                SET company = COALESCE(NULLIF(TRIM(company), ''), NULLIF(TRIM(title), ''), 'Unknown company')
                WHERE company IS NULL OR TRIM(company) = ''
            """))
            connection.execute(text("ALTER TABLE cases ALTER COLUMN title DROP NOT NULL"))

        connection.execute(text("UPDATE cases SET company = 'Unknown company' WHERE company IS NULL OR TRIM(company) = ''"))
        connection.execute(text("ALTER TABLE cases ALTER COLUMN company SET NOT NULL"))


def migrate_document_storage_fields(engine: Engine) -> None:
    """Add Supabase Storage metadata fields to existing document rows."""
    inspector = inspect(engine)
    if "documents" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("documents")}

    with engine.begin() as connection:
        if "storage_path" not in columns:
            connection.execute(text("ALTER TABLE documents ADD COLUMN storage_path VARCHAR(500)"))
            if "file_path" in columns:
                connection.execute(text("UPDATE documents SET storage_path = file_path WHERE storage_path IS NULL"))

        if "content_type" not in columns:
            connection.execute(text("ALTER TABLE documents ADD COLUMN content_type VARCHAR(255)"))
            connection.execute(text("UPDATE documents SET content_type = 'application/octet-stream' WHERE content_type IS NULL"))

        if "file_size" not in columns:
            connection.execute(text("ALTER TABLE documents ADD COLUMN file_size INTEGER"))
            connection.execute(text("UPDATE documents SET file_size = 0 WHERE file_size IS NULL"))

        connection.execute(text("ALTER TABLE documents ALTER COLUMN storage_path SET NOT NULL"))
        connection.execute(text("ALTER TABLE documents ALTER COLUMN content_type SET NOT NULL"))
        connection.execute(text("ALTER TABLE documents ALTER COLUMN file_size SET NOT NULL"))
        if "file_path" in columns:
            connection.execute(text("ALTER TABLE documents ALTER COLUMN file_path DROP NOT NULL"))


def migrate_documents_independent(engine: Engine) -> None:
    """Allow documents without cases and preserve them when a case is removed."""
    inspector = inspect(engine)
    if "documents" not in inspector.get_table_names():
        return

    columns = {column["name"]: column for column in inspector.get_columns("documents")}
    foreign_keys = inspector.get_foreign_keys("documents")

    with engine.begin() as connection:
        case_column = columns.get("case_id")
        if case_column and not case_column.get("nullable", True):
            connection.execute(text("ALTER TABLE documents ALTER COLUMN case_id DROP NOT NULL"))

        # PostgreSQL cannot alter ON DELETE in place. Recreate only the FK that
        # points documents.case_id to cases.id. Constraint names come from the
        # inspector and are quoted before execution.
        for foreign_key in foreign_keys:
            if (
                foreign_key.get("referred_table") == "cases"
                and foreign_key.get("constrained_columns") == ["case_id"]
            ):
                name = foreign_key.get("name")
                ondelete = (foreign_key.get("options") or {}).get("ondelete")
                if name and str(ondelete).upper() != "SET NULL":
                    safe_name = name.replace('\"', '\"\"')
                    connection.execute(text(f'ALTER TABLE documents DROP CONSTRAINT "{safe_name}"'))
                    connection.execute(text(
                        'ALTER TABLE documents '
                        'ADD CONSTRAINT fk_documents_case_id '
                        'FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE SET NULL'
                    ))
                break

        connection.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_documents_case_id ON documents (case_id)"
        ))


def migrate_case_title(engine: Engine) -> None:
    """Add a required case title and backfill existing records safely."""
    inspector = inspect(engine)
    if "cases" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("cases")}

    with engine.begin() as connection:
        if "title" not in columns:
            connection.execute(text("ALTER TABLE cases ADD COLUMN title VARCHAR(255)"))

        connection.execute(text("""
            UPDATE cases
            SET title = COALESCE(
                NULLIF(TRIM(title), ''),
                NULLIF(TRIM(company), ''),
                'Untitled case ' || id::text
            )
            WHERE title IS NULL OR TRIM(title) = ''
        """))
        connection.execute(text("ALTER TABLE cases ALTER COLUMN title SET NOT NULL"))
