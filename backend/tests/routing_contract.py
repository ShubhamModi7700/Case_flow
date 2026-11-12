import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_manual_case_change_records_correction():
    tree = ast.parse((ROOT / 'app/routes/documents.py').read_text(encoding='utf-8'))
    fn = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == 'assign_document_to_case')
    source = ast.unparse(fn)
    assert 'previous_case_id != document.case_id' in source
    assert "event_type=" in source and "correction" in source
    assert 'previous_case_id' in source
    assert 'has_global_case_access(current_user)' in source


def test_history_endpoint_requires_document_access():
    tree = ast.parse((ROOT / 'app/routes/documents.py').read_text(encoding='utf-8'))
    fn = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == 'get_document_case_routing_history')
    source = ast.unparse(fn)
    assert 'require_case_view' in source
    assert 'has_global_case_access' in source
