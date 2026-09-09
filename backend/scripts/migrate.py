from app import models  
from app.database import Base, engine
from app.migrations import (
    migrate_case_company_fields,
    migrate_case_title,
    migrate_case_management_fields,
    migrate_document_storage_fields,
    migrate_documents_independent,
    migrate_legacy_admin_roles,
    migrate_task_assignment_fields,
    migrate_ai_summary_status_fields,
    migrate_management_action_fields,
    migrate_ai_audit_fields,
)


def main() -> None:
    print("Starting database migration...")

    Base.metadata.create_all(bind=engine)

    migrate_case_company_fields(engine)
    migrate_case_title(engine)
    migrate_case_management_fields(engine)
    migrate_document_storage_fields(engine)
    migrate_documents_independent(engine)
    migrate_legacy_admin_roles(engine)
    migrate_task_assignment_fields(engine)
    migrate_ai_summary_status_fields(engine)
    migrate_management_action_fields(engine)
    migrate_ai_audit_fields(engine)

    print("Database migration completed successfully.")


if __name__ == "__main__":
    main()