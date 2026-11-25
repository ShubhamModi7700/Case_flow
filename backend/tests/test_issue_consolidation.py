from app.schemas import AssistantCaseIssue, AssistantEvidenceStatement
from app.services.issue_consolidation import consolidate_issues


def test_duplicate_topics_preserve_sources_and_classification():
    issues = [AssistantCaseIssue(title='Vertrag', facts=[AssistantEvidenceStatement(text='Datum belegt', source_ids=['S1'])]), AssistantCaseIssue(title=' vertrag ', facts=[AssistantEvidenceStatement(text='Datum belegt', source_ids=['S2','invalid'])], party_claims=[AssistantEvidenceStatement(text='Behauptung', source_ids=['S2'])])]
    result = consolidate_issues(issues, {'S1','S2'})
    assert len(result) == 1
    assert result[0].facts[0].source_ids == ['S1','S2']
    assert len(result[0].party_claims) == 1
