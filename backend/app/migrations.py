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
