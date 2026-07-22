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
