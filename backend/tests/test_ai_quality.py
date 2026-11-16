from __future__ import annotations
"""Consolidated regression tests; original test functions preserved.

Sources: test_ai_provider.py, test_prompt_quality.py, test_reasoning_rules.py, test_natural_chat_style.py, test_final_refinements.py
"""


# ---- From test_ai_provider.py ----


from unittest.mock import patch

import pytest

from app.services.ai_provider import OpenAIProvider, configured_provider_name, get_ai_provider


def _reset() -> None:
    get_ai_provider.cache_clear()


def test_openai_is_default_provider() -> None:
    _reset()
    with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}, clear=False):
        with patch("app.services.ai_provider.OpenAI"):
            provider = get_ai_provider()
            assert provider.name == "openai"
            assert configured_provider_name() == "openai"
    _reset()


def test_unknown_provider_fails_closed() -> None:
    _reset()
    with patch.dict("os.environ", {"AI_PROVIDER": "unknown-provider"}, clear=False):
        with pytest.raises(RuntimeError, match="Unsupported AI_PROVIDER"):
            get_ai_provider()
    _reset()


def test_provider_requires_server_side_api_key() -> None:
    with patch.dict(
        "os.environ",
        {"AI_EXTERNAL_PROCESSING_ENABLED": "true", "OPENAI_API_KEY": ""},
        clear=False,
    ):
        with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
            OpenAIProvider()


def test_external_processing_can_be_disabled() -> None:
    with patch.dict(
        "os.environ",
        {"AI_EXTERNAL_PROCESSING_ENABLED": "false", "OPENAI_API_KEY": "test-key"},
        clear=False,
    ):
        with pytest.raises(RuntimeError, match="disabled"):
            OpenAIProvider()


# ---- From test_prompt_quality.py ----
from app.prompts.case_assistant import (
    BASE_SYSTEM_PROMPT,
    CASE_ASSISTANT_PROMPT_VERSION,
    TASK_PROMPTS,
)
from app.prompts.common import CORE_RULES
from app.prompts.document_analysis import DOCUMENT_ANALYSIS_PROMPT_VERSION
from app.prompts.document_routing import DOCUMENT_ROUTING_PROMPT_VERSION
from app.prompts.extraction import EXTRACTION_PROMPT_VERSION
from app.prompts.management import MANAGEMENT_PROMPT_VERSION


def test_case_assistant_uses_compact_shared_contract():
    assert CORE_RULES in BASE_SYSTEM_PROMPT

    assert "erfinde nichts" in CORE_RULES.casefold()
    assert "Nutzerangaben" in CORE_RULES
    assert "bereitgestellte" in CORE_RULES


def test_all_case_assistant_tasks_keep_specialized_instructions():
    expected = {
        "question",
        "chronology",
        "evidence",
        "entities",
        "brief_evidence",
        "brief_outline",
        "brief_draft",
        "brief_review",
        "intelligence",
        "report",
    }

    assert set(TASK_PROMPTS) == expected
    assert all(value.strip() for value in TASK_PROMPTS.values())


def test_task_prompts_remain_compact():
    for task, prompt in TASK_PROMPTS.items():
        assert len(prompt.strip()) < (10000 if task == "report" else 1200), (
            f"{task} prompt became unexpectedly large"
        )


def test_prompt_versions_are_explicit_and_nonempty():
    versions = [
        CASE_ASSISTANT_PROMPT_VERSION,
        DOCUMENT_ANALYSIS_PROMPT_VERSION,
        DOCUMENT_ROUTING_PROMPT_VERSION,
        MANAGEMENT_PROMPT_VERSION,
        EXTRACTION_PROMPT_VERSION,
    ]

    assert all(version and "v" in version for version in versions)
    assert len(set(versions)) == len(versions)


def test_extraction_prompt_version_is_separate_from_reasoning_prompts():
    assert "extraction" in EXTRACTION_PROMPT_VERSION.casefold()
    assert "verbatim" in EXTRACTION_PROMPT_VERSION.casefold()

# ---- From test_reasoning_rules.py ----
import unittest
from app.prompts.case_assistant import CHAT_CONVERSATIONAL_PROMPT


class Phase2ReasoningRulesTests(unittest.TestCase):
    def test_distinguishes_revisions_conflicts_and_missing_evidence(self):
        prompt = CHAT_CONVERSATIONAL_PROMPT
        for phrase in ("KOMPAKTE FALLLOGIK", "echter Widerspruch", "aufeinanderfolgende Stände", "fehlende Bestätigung", "technischer Vorfall"):
            self.assertIn(phrase, prompt)


if __name__ == "__main__":
    unittest.main()


# ---- From test_natural_chat_style.py ----
import unittest
from app.prompts.case_assistant import CHAT_CONVERSATIONAL_PROMPT

class Phase2NaturalChatStyleTests(unittest.TestCase):
    def test_no_fixed_heading_template(self):
        self.assertIn("Verwende keine routinemäßigen Abschnittsüberschriften", CHAT_CONVERSATIONAL_PROMPT)
        self.assertIn("fließendem, professionellem Deutsch", CHAT_CONVERSATIONAL_PROMPT)
        self.assertNotIn("Verwende für wenige zentrale Abschnitte kurze fett markierte Bezeichnungen", CHAT_CONVERSATIONAL_PROMPT)

    def test_depth_and_evidence_are_preserved(self):
        self.assertIn("punktuelle Faktenfragen direkt und knapp", CHAT_CONVERSATIONAL_PROMPT)
        self.assertIn("alternative Erklärungen, Gegenargumente", CHAT_CONVERSATIONAL_PROMPT)
        self.assertIn("im gesamten Fall nicht vorhanden", CHAT_CONVERSATIONAL_PROMPT)


# ---- From test_final_refinements.py ----
import unittest
from app.prompts.case_assistant import CHAT_CONVERSATIONAL_PROMPT

class Phase34FinalRefinementsTests(unittest.TestCase):
    def test_natural_paragraphs_not_repeated_numbering(self):
        self.assertIn("nicht als nummerierte Chronologie", CHAT_CONVERSATIONAL_PROMPT)
        self.assertIn("Nummerierung dann einheitlich und fortlaufend", CHAT_CONVERSATIONAL_PROMPT)

    def test_arithmetic_pattern_not_documented_cause(self):
        self.assertIn("beweist weder die Kalkulationsmethode", CHAT_CONVERSATIONAL_PROMPT)
        self.assertIn("keine unbelegten Ursachen", CHAT_CONVERSATIONAL_PROMPT)

    def test_financial_comparability_and_payment_proof(self):
        self.assertIn("Netto-/Bruttobasis", CHAT_CONVERSATIONAL_PROMPT)
        self.assertIn("Eine Rechnung oder rechnerisch passende Differenz ist kein Zahlungs-, Buchungs- oder Verrechnungsnachweis", CHAT_CONVERSATIONAL_PROMPT)

    def test_adaptive_depth_preserved(self):
        self.assertIn("ADAPTIVE ANTWORTTIEFE", CHAT_CONVERSATIONAL_PROMPT)
        self.assertIn("punktuelle Faktenfragen direkt und knapp", CHAT_CONVERSATIONAL_PROMPT)

