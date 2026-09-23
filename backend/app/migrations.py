from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def _column_map(
    engine: Engine,
    table_name: str,
) -> dict[str, dict]:
    inspector = inspect(engine)

    if table_name not in inspector.get_table_names():
        return {}

    return {
        column["name"]: column
        for column in inspector.get_columns(table_name)
    }


def migrate_case_company_fields(engine: Engine) -> None:
    """Add company and department fields and backfill old case data."""
    columns = _column_map(engine, "cases")

    if not columns:
        return

    with engine.begin() as connection:
        if "company" not in columns:
            connection.execute(
                text(
                    "ALTER TABLE cases "
                    "ADD COLUMN company VARCHAR(200)"
                )
            )
            columns["company"] = {
                "name": "company",
                "nullable": True,
            }

        if "department" not in columns:
            connection.execute(
                text(
                    "ALTER TABLE cases "
                    "ADD COLUMN department VARCHAR(200)"
                )
            )
            columns["department"] = {
                "name": "department",
                "nullable": True,
            }

        if "company_department" in columns:
            connection.execute(
                text(
                    """
                    UPDATE cases
                    SET company = COALESCE(
                        NULLIF(TRIM(company), ''),
                        NULLIF(TRIM(company_department), '')
                    )
                    WHERE company IS NULL
                       OR TRIM(company) = ''
                    """
                )
            )

        if "title" in columns:
            connection.execute(
                text(
                    """
                    UPDATE cases
                    SET company = COALESCE(
                        NULLIF(TRIM(company), ''),
                        NULLIF(TRIM(title), ''),
                        'Unknown company'
                    )
                    WHERE company IS NULL
                       OR TRIM(company) = ''
                    """
                )
            )

        connection.execute(
            text(
                """
                UPDATE cases
                SET company = 'Unknown company'
                WHERE company IS NULL
                   OR TRIM(company) = ''
                """
            )
        )

        company_column = columns.get("company")

        if company_column and company_column.get("nullable", True):
            connection.execute(
                text(
                    "ALTER TABLE cases "
                    "ALTER COLUMN company SET NOT NULL"
                )
            )


def migrate_case_title(engine: Engine) -> None:
    """Add a required case title and backfill existing records."""
    columns = _column_map(engine, "cases")

    if not columns:
        return

    with engine.begin() as connection:
        if "title" not in columns:
            connection.execute(
                text(
                    "ALTER TABLE cases "
                    "ADD COLUMN title VARCHAR(255)"
                )
            )
            columns["title"] = {
                "name": "title",
                "nullable": True,
            }

        connection.execute(
            text(
                """
                UPDATE cases
                SET title = COALESCE(
                    NULLIF(TRIM(title), ''),
                    NULLIF(TRIM(company), ''),
                    'Untitled case ' || id::text
                )
                WHERE title IS NULL
                   OR TRIM(title) = ''
                """
            )
        )

        title_column = columns.get("title")

        if title_column and title_column.get("nullable", True):
            connection.execute(
                text(
                    "ALTER TABLE cases "
                    "ALTER COLUMN title SET NOT NULL"
                )
            )


def migrate_document_storage_fields(engine: Engine) -> None:
    """Add and repair Supabase Storage metadata fields."""
    columns = _column_map(engine, "documents")

    if not columns:
        return

    with engine.begin() as connection:
        if "storage_path" not in columns:
            connection.execute(
                text(
                    "ALTER TABLE documents "
                    "ADD COLUMN storage_path VARCHAR(500)"
                )
            )
            columns["storage_path"] = {
                "name": "storage_path",
                "nullable": True,
            }

        if "content_type" not in columns:
            connection.execute(
                text(
                    "ALTER TABLE documents "
                    "ADD COLUMN content_type VARCHAR(255)"
                )
            )
            columns["content_type"] = {
                "name": "content_type",
                "nullable": True,
            }

        if "file_size" not in columns:
            connection.execute(
                text(
                    "ALTER TABLE documents "
                    "ADD COLUMN file_size INTEGER"
                )
            )
            columns["file_size"] = {
                "name": "file_size",
                "nullable": True,
            }

        if "file_path" in columns:
            connection.execute(
                text(
                    """
                    UPDATE documents
                    SET storage_path = file_path
                    WHERE (
                        storage_path IS NULL
                        OR TRIM(storage_path) = ''
                    )
                    AND file_path IS NOT NULL
                    AND TRIM(file_path) != ''
                    """
                )
            )

        connection.execute(
            text(
                """
                UPDATE documents
                SET content_type = 'application/octet-stream'
                WHERE content_type IS NULL
                   OR TRIM(content_type) = ''
                """
            )
        )

        connection.execute(
            text(
                """
                UPDATE documents
                SET file_size = 0
                WHERE file_size IS NULL
                   OR file_size < 0
                """
            )
        )

        missing_storage_count = connection.execute(
            text(
                """
                SELECT COUNT(*)
                FROM documents
                WHERE storage_path IS NULL
                   OR TRIM(storage_path) = ''
                """
            )
        ).scalar_one()

        storage_column = columns.get("storage_path")

        if (
            storage_column
            and storage_column.get("nullable", True)
            and missing_storage_count == 0
        ):
            connection.execute(
                text(
                    "ALTER TABLE documents "
                    "ALTER COLUMN storage_path SET NOT NULL"
                )
            )

        content_type_column = columns.get("content_type")

        if (
            content_type_column
            and content_type_column.get("nullable", True)
        ):
            connection.execute(
                text(
                    "ALTER TABLE documents "
                    "ALTER COLUMN content_type SET NOT NULL"
                )
            )

        file_size_column = columns.get("file_size")

        if (
            file_size_column
            and file_size_column.get("nullable", True)
        ):
            connection.execute(
                text(
                    "ALTER TABLE documents "
                    "ALTER COLUMN file_size SET NOT NULL"
                )
            )

        file_path_column = columns.get("file_path")

        if (
            file_path_column
            and not file_path_column.get("nullable", True)
        ):
            connection.execute(
                text(
                    "ALTER TABLE documents "
                    "ALTER COLUMN file_path DROP NOT NULL"
                )
            )


def migrate_documents_independent(engine: Engine) -> None:
    """Allow documents without cases and preserve them after case deletion."""
    columns = _column_map(engine, "documents")

    if not columns:
        return

    inspector = inspect(engine)
    foreign_keys = inspector.get_foreign_keys("documents")

    with engine.begin() as connection:
        case_column = columns.get("case_id")

        if case_column and not case_column.get("nullable", True):
            connection.execute(
                text(
                    "ALTER TABLE documents "
                    "ALTER COLUMN case_id DROP NOT NULL"
                )
            )

        matching_foreign_key = None

        for foreign_key in foreign_keys:
            if (
                foreign_key.get("referred_table") == "cases"
                and foreign_key.get("constrained_columns")
                == ["case_id"]
            ):
                matching_foreign_key = foreign_key
                break

        if matching_foreign_key:
            constraint_name = matching_foreign_key.get("name")
            options = matching_foreign_key.get("options") or {}
            ondelete = str(options.get("ondelete") or "").upper()

            if constraint_name and ondelete != "SET NULL":
                safe_name = constraint_name.replace('"', '""')

                connection.execute(
                    text(
                        f'ALTER TABLE documents '
                        f'DROP CONSTRAINT "{safe_name}"'
                    )
                )

                connection.execute(
                    text(
                        """
                        ALTER TABLE documents
                        ADD CONSTRAINT fk_documents_case_id
                        FOREIGN KEY (case_id)
                        REFERENCES cases(id)
                        ON DELETE SET NULL
                        """
                    )
                )

        connection.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_documents_case_id
                ON documents (case_id)
                """
            )
        )

def migrate_case_management_fields(engine: Engine) -> None:
    """Add transparent risk and management-summary fields."""
    columns = _column_map(engine, "cases")

    if not columns:
        return

    statements = {
        "risk_reason": "ALTER TABLE cases ADD COLUMN risk_reason TEXT",
        "suggested_risk": (
            "ALTER TABLE cases ADD COLUMN suggested_risk VARCHAR(20)"
        ),
        "suggested_risk_reason": (
            "ALTER TABLE cases ADD COLUMN suggested_risk_reason TEXT"
        ),
        "risk_is_manual": (
            "ALTER TABLE cases ADD COLUMN risk_is_manual BOOLEAN "
            "NOT NULL DEFAULT FALSE"
        ),
        "management_summary": (
            "ALTER TABLE cases ADD COLUMN management_summary TEXT"
        ),
        "financial_amount": (
            "ALTER TABLE cases ADD COLUMN financial_amount NUMERIC(14, 2)"
        ),
    }

    with engine.begin() as connection:
        for column_name, statement in statements.items():
            if column_name not in columns:
                connection.execute(text(statement))


def migrate_legacy_admin_roles(engine) -> None:
    from sqlalchemy import text

    with engine.begin() as connection:
        connection.execute(
            text("UPDATE users SET role = 'Manager' WHERE role = 'Admin'")
        )


def migrate_ai_summary_status_fields(engine: Engine) -> None:
    """Add AI-proposed status fields to case_ai_summaries."""
    columns = _column_map(engine, "case_ai_summaries")
    if not columns:
        return

    statements = {
        "suggested_status": (
            "ALTER TABLE case_ai_summaries ADD COLUMN suggested_status VARCHAR(30)"
        ),
        "status_reason": (
            "ALTER TABLE case_ai_summaries ADD COLUMN status_reason TEXT"
        ),
    }

    with engine.begin() as connection:
        for column_name, statement in statements.items():
            if column_name not in columns:
                connection.execute(text(statement))


def migrate_task_assignment_fields(engine: Engine) -> None:
    """Add task category and enlarge the assignee field for multi-person assignments."""
    columns = _column_map(engine, "tasks")
    if not columns:
        return
    with engine.begin() as connection:
        if "category" not in columns:
            connection.execute(text("ALTER TABLE tasks ADD COLUMN category VARCHAR(120)"))
        # PostgreSQL safely widens existing VARCHAR columns.
        if "responsible_person" in columns:
            connection.execute(text("ALTER TABLE tasks ALTER COLUMN responsible_person TYPE VARCHAR(500)"))


def migrate_management_action_fields(engine: Engine) -> None:
    """Add Phase 2 evidence-separated recommended-action fields."""
    columns = _column_map(engine, "case_ai_summaries")
    if not columns:
        return
    statements = {
        "document_facts": "ALTER TABLE case_ai_summaries ADD COLUMN document_facts JSONB NOT NULL DEFAULT '[]'::jsonb",
        "interpretation": "ALTER TABLE case_ai_summaries ADD COLUMN interpretation TEXT",
        "responsible_role": "ALTER TABLE case_ai_summaries ADD COLUMN responsible_role VARCHAR(200)",
        "action_justification": "ALTER TABLE case_ai_summaries ADD COLUMN action_justification TEXT",
        "uncertainty_notes": "ALTER TABLE case_ai_summaries ADD COLUMN uncertainty_notes JSONB NOT NULL DEFAULT '[]'::jsonb",
    }
    with engine.begin() as connection:
        for column_name, statement in statements.items():
            if column_name not in columns:
                connection.execute(text(statement))


def migrate_ai_audit_fields(engine: Engine) -> None:
    """Backfill Step 6 audit columns if an earlier audit table already exists."""
    query_columns = _column_map(engine, "ai_queries")
    if query_columns:
        statements = {
            "provider": "ALTER TABLE ai_queries ADD COLUMN provider VARCHAR(40) NOT NULL DEFAULT 'openai'",
            "output_json": "ALTER TABLE ai_queries ADD COLUMN output_json JSONB",
        }
        with engine.begin() as connection:
            for column_name, statement in statements.items():
                if column_name not in query_columns:
                    connection.execute(text(statement))

    source_columns = _column_map(engine, "ai_query_sources")
    if source_columns and "used_in_output" not in source_columns:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE ai_query_sources "
                    "ADD COLUMN used_in_output BOOLEAN NOT NULL DEFAULT FALSE"
                )
            )


def migrate_case_intelligence_snapshot_fields(engine: Engine) -> None:
    """Step 14: repair snapshot columns if the table was created by an older build."""
    columns = _column_map(engine, "case_intelligence_snapshots")
    if not columns:
        return
    statements = {
        "generated_by": "ALTER TABLE case_intelligence_snapshots ADD COLUMN generated_by INTEGER REFERENCES users(id) ON DELETE SET NULL",
        "ai_query_id": "ALTER TABLE case_intelligence_snapshots ADD COLUMN ai_query_id INTEGER REFERENCES ai_queries(id) ON DELETE SET NULL",
        "input_fingerprint": "ALTER TABLE case_intelligence_snapshots ADD COLUMN input_fingerprint VARCHAR(64)",
        "intelligence_json": "ALTER TABLE case_intelligence_snapshots ADD COLUMN intelligence_json JSONB",
        "work_status_json": "ALTER TABLE case_intelligence_snapshots ADD COLUMN work_status_json JSONB",
        "sources_json": "ALTER TABLE case_intelligence_snapshots ADD COLUMN sources_json JSONB NOT NULL DEFAULT '[]'::jsonb",
        "source_document_ids": "ALTER TABLE case_intelligence_snapshots ADD COLUMN source_document_ids JSONB NOT NULL DEFAULT '[]'::jsonb",
        "generated_at": "ALTER TABLE case_intelligence_snapshots ADD COLUMN generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()",
    }
    with engine.begin() as connection:
        for column_name, statement in statements.items():
            if column_name not in columns:
                connection.execute(text(statement))
