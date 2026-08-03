from app.database import Base, engine
from app.migrations import (
    migrate_case_company_fields,
    migrate_case_title,
    migrate_case_management_fields,
    migrate_document_storage_fields,
    migrate_documents_independent,
)


def main() -> None:
    print("Starting database migration...")

    Base.metadata.create_all(bind=engine)

    migrate_case_company_fields(engine)
    migrate_case_title(engine)
    migrate_case_management_fields(engine)
    migrate_document_storage_fields(engine)
    migrate_documents_independent(engine)

    print("Database migration completed successfully.")


if __name__ == "__main__":
    main()