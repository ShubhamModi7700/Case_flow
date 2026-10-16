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
    }

    assert set(TASK_PROMPTS) == expected
    assert all(value.strip() for value in TASK_PROMPTS.values())


def test_task_prompts_remain_compact():
    for task, prompt in TASK_PROMPTS.items():
        assert len(prompt.strip()) < 1000, (
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