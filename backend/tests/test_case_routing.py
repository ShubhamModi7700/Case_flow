"""Consolidated regression tests; original test functions preserved.

Sources: test_background_routing.py, test_document_case_routing_safety.py, test_case_routing_evaluation.py, test_retrieval_acl_contract.py
"""


# ---- From test_background_routing.py ----

from scripts.document_worker import _auto_assignment_candidate
from app.services.document_case_routing import CaseCandidate, DocumentCaseRouteSuggestion


def _suggestion(case_id=12, confidence=.98, decision='existing_case'):
    return DocumentCaseRouteSuggestion(decision=decision, suggested_case_id=case_id,
                                       confidence=confidence, reason='Document matches case')


def _candidates(first=.94, second=.75):
    return [CaseCandidate(case_id=12, title='Flach', similarity=first),
            CaseCandidate(case_id=13, title='Stromversorgung Isenbüttel', similarity=second)]


def test_clear_existing_case_is_eligible():
    assert _auto_assignment_candidate(_suggestion(), _candidates()) == 12


def test_uncertain_and_new_cases_are_never_auto_assigned():
    assert _auto_assignment_candidate(_suggestion(decision='uncertain'), _candidates()) is None
    assert _auto_assignment_candidate(_suggestion(case_id=None, confidence=0, decision='new_case'), _candidates()) is None


def test_low_confidence_similarity_or_margin_requires_review():
    assert _auto_assignment_candidate(_suggestion(confidence=.94), _candidates()) is None
    assert _auto_assignment_candidate(_suggestion(), _candidates(first=.84)) is None
    assert _auto_assignment_candidate(_suggestion(), _candidates(first=.90, second=.86)) is None


def test_suggested_case_must_be_top_retrieval_candidate():
    assert _auto_assignment_candidate(_suggestion(case_id=13), _candidates()) is None


# ---- From test_document_case_routing_safety.py ----
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


def test_no_existing_cases_stays_unassigned_without_creating_draft(monkeypatch):
    monkeypatch.setattr(routing, "create_document_case_draft", lambda context: (_ for _ in ()).throw(AssertionError("must not draft")))
    result = routing.suggest_document_case_route(document_context="Testdokument", candidates=[])
    assert result.decision == "uncertain"
    assert result.confidence == 0.0
    assert result.new_case is None


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
    assert result.decision == "uncertain"
    assert result.suggested_case_id is None
    assert result.confidence == 0.0
    assert result.new_case is None


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


# ---- From test_case_routing_evaluation.py ----
from scripts.evaluate_case_routing import evaluate


def test_metrics_distinguish_wrong_case_and_review():
    result = evaluate([
        {"expected_case_id": 1, "decision": "existing_case", "suggested_case_id": 1},
        {"expected_case_id": 2, "decision": "existing_case", "suggested_case_id": 1},
        {"expected_case_id": 3, "decision": "uncertain", "suggested_case_id": 3},
        {"expected_case_id": 4, "decision": "new_case", "suggested_case_id": None},
        {"expected_case_id": None, "decision": "new_case", "suggested_case_id": None},
    ])
    assert result["correct_suggestions"] == 2
    assert result["wrong_existing_case_suggestions"] == 1
    assert result["missed_existing_cases"] == 1
    assert result["needs_review"] == 1
    assert result["suggestion_accuracy_excluding_review"] == 0.5


# ---- From test_retrieval_acl_contract.py ----
"""Security contract tests for ACL-before-ranking retrieval.

These tests intentionally inspect the SQL contract because the critical manager
requirement is *where* authorization happens: inaccessible chunks must be
filtered before vector ranking/LIMIT, not removed from results afterwards.
"""

import inspect

from app.services import retrieval


def test_chunk_retrieval_embeds_acl_in_vector_query():
    source = inspect.getsource(retrieval.retrieve_chunks).casefold()

    assert "public.case_access" in source
    assert "ca.user_id = :requesting_user_id" in source
    assert "ca.case_id = d.case_id" in source
    assert "partition by dc.document_id order by dc.embedding" in source
    assert "limit :match_count" in source

    assert "match_document_chunks(" not in source


def test_case_matching_embeds_acl_before_ranking():
    source = inspect.getsource(retrieval.match_cases).casefold()

    assert "public.case_access" in source
    assert "ca.user_id = :requesting_user_id" in source
    assert "ca.case_id = ce.case_id" in source
    assert "order by ce.embedding" in source
    assert "limit :match_count" in source



def test_auto_assignment_requires_case_specific_text():
    suggestion = _suggestion()
    candidates = _candidates()
    assert _auto_assignment_candidate(suggestion, candidates, "Schreiben an Flach betreffend Projekt") == 12
    assert _auto_assignment_candidate(suggestion, candidates, "Allgemeines Schreiben zu einem Projekt") is None
    assert _auto_assignment_candidate(suggestion, candidates, "Stromversorgung Isenbüttel") is None


def test_isenbuettel_title_corrobation():
    suggestion = _suggestion(case_id=13)
    candidates = [CaseCandidate(case_id=13, title="Stromversorgung Isenbüttel", similarity=.95)]
    assert _auto_assignment_candidate(suggestion, candidates, "Netzanschluss in Isenbüttel") == 13
    assert _auto_assignment_candidate(suggestion, candidates, "Stromversorgung allgemein") is None
