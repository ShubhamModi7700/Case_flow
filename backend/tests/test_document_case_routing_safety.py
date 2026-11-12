"""Regression tests for Phase 2 routing safety decisions."""
from types import SimpleNamespace

import pytest

from app.services import document_case_routing as routing


def _candidate():
    return routing.CaseCandidate(case_id=12, title="Testfall", similarity=0.87)


def test_low_confidence_existing_match_requires_review(monkeypatch):
    monkeypatch.setattr(routing, "_parse_structured", lambda **kw: routing.DocumentCaseRouteSuggestion(
        decision="existing_case", suggested_case_id=12, confidence=0.55, reason="Ähnliche Begriffe"
    ))
    result = routing.suggest_document_case_route(document_context="Testdokument", candidates=[_candidate()])
    assert result.decision == "uncertain"
    assert result.suggested_case_id == 12


def test_high_confidence_existing_match_is_only_suggested(monkeypatch):
    monkeypatch.setattr(routing, "_parse_structured", lambda **kw: routing.DocumentCaseRouteSuggestion(
        decision="existing_case", suggested_case_id=12, confidence=0.94, reason="Gleiche Referenz"
    ))
    result = routing.suggest_document_case_route(document_context="Testdokument", candidates=[_candidate()])
    assert result.decision == "existing_case"
    assert result.suggested_case_id == 12


def test_unknown_case_id_is_rejected(monkeypatch):
    monkeypatch.setattr(routing, "_parse_structured", lambda **kw: routing.DocumentCaseRouteSuggestion(
        decision="existing_case", suggested_case_id=999, confidence=0.99, reason="Test"
    ))
    with pytest.raises(RuntimeError, match="ungültige Fall-ID"):
        routing.suggest_document_case_route(document_context="Testdokument", candidates=[_candidate()])


def test_no_existing_cases_does_not_claim_perfect_confidence(monkeypatch):
    monkeypatch.setattr(routing, "create_document_case_draft", lambda context: routing.DocumentCaseDraft(title="Neuer Fall"))
    result = routing.suggest_document_case_route(document_context="Testdokument", candidates=[])
    assert result.decision == "new_case"
    assert result.confidence == 0.0
    assert result.new_case.title == "Neuer Fall"


def test_missing_case_id_cannot_be_high_confidence(monkeypatch):
    monkeypatch.setattr(routing, "_parse_structured", lambda **kw: routing.DocumentCaseRouteSuggestion(
        decision="existing_case", suggested_case_id=None, confidence=0.99, reason="Match"
    ))
    result = routing.suggest_document_case_route(document_context="Testdokument", candidates=[_candidate()])
    assert result.decision == "uncertain"
    assert result.confidence == 0.0


def test_new_case_does_not_inherit_matching_confidence(monkeypatch):
    monkeypatch.setattr(routing, "_parse_structured", lambda **kw: routing.DocumentCaseRouteSuggestion(
        decision="new_case", suggested_case_id=12, confidence=0.97,
        reason="New", new_case=routing.DocumentCaseDraft(title="Neuer Fall")
    ))
    result = routing.suggest_document_case_route(document_context="Testdokument", candidates=[_candidate()])
    assert result.decision == "new_case"
    assert result.suggested_case_id is None
    assert result.confidence == 0.0


def test_uncertain_match_cannot_contain_new_case_draft(monkeypatch):
    monkeypatch.setattr(routing, "_parse_structured", lambda **kw: routing.DocumentCaseRouteSuggestion(
        decision="uncertain", suggested_case_id=12, confidence=0.43,
        reason="Uncertain", new_case=routing.DocumentCaseDraft(title="Unrelated draft")
    ))
    result = routing.suggest_document_case_route(document_context="Testdokument", candidates=[_candidate()])
    assert result.decision == "uncertain"
    assert result.new_case is None


def test_high_confidence_match_discards_inconsistent_new_case_draft(monkeypatch):
    monkeypatch.setattr(routing, "_parse_structured", lambda **kw: routing.DocumentCaseRouteSuggestion(
        decision="existing_case", suggested_case_id=12, confidence=0.94,
        reason="Same reference", new_case=routing.DocumentCaseDraft(title="Unrelated draft")
    ))
    result = routing.suggest_document_case_route(document_context="Testdokument", candidates=[_candidate()])
    assert result.decision == "existing_case"
    assert result.new_case is None
