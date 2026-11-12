"""Static regression checks for the Phase 2 audit/assignment contract."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_manual_correction_updates_indexed_chunk_case_ids():
    source = (ROOT / "app/routes/documents.py").read_text()
    section = source.split("def assign_document_to_case(", 1)[1].split("@router.post", 1)[0]
    assert 'DocumentChunk' in section
    assert '.update({"case_id": document.case_id}' in section
    assert 'event_type="correction"' in section

def test_sql_accepts_manual_correction_event():
    for filename in ("case_routing_events.sql", "phase2_routing_correction_fix.sql"):
        source = (ROOT / "sql" / filename).read_text()
        assert "'correction'" in source
