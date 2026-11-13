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
