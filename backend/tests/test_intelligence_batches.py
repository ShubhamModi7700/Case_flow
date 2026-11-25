from types import SimpleNamespace
from app import schemas
from app.services.intelligence_batches import analyze_batches, batches
from app.services.ai_audit import referenced_source_ids


def test_large_case_preserves_global_citations():
    sources = [dict(source_id=f'S{i}', document_id=i, content='Beleg') for i in range(1,121)]
    docs = [SimpleNamespace(id=i, file_name=f'{i}.pdf') for i in range(1,122)]
    calls = []
    def analyze(**kwargs):
        batch = kwargs['sources']
        calls.extend(s['source_id'] for s in batch)
        return schemas.CaseAssistantModelAnswer(answer='Test', intelligence=schemas.AssistantCaseIntelligence(issues=[schemas.AssistantCaseIssue(title='Thema', facts=[schemas.AssistantEvidenceStatement(text='Beleg', source_ids=[s['source_id'] for s in batch]+['S999'])])]))
    result = analyze_batches('Test', sources, docs, analyze=analyze)
    assert calls == [s['source_id'] for s in sources]
    assert referenced_source_ids(result) == set(calls)
    assert len(result.intelligence.issues) == 1
    assert '120 von 121' in result.intelligence.information_gaps[0]
    assert '121.pdf' in result.intelligence.information_gaps[1]


def test_long_chunk_not_truncated():
    source = dict(source_id='S1', content='abcdefghijk')
    parts = [s for batch in batches([source], max_chars=4) for s in batch]
    assert ''.join(s['content'] for s in parts) == source['content']
    assert all(s['source_id'] == 'S1' for s in parts)
