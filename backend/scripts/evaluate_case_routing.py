from __future__ import annotations

import argparse
import json
from pathlib import Path


def evaluate(rows: list[dict]) -> dict:
    if not rows:
        raise ValueError("At least one labeled document is required")
    total = len(rows)
    correct = incorrect = reviewed = missed = 0
    for row in rows:
        if "expected_case_id" not in row:
            raise ValueError("Missing expected_case_id")
        expected = row["expected_case_id"]
        decision = row.get("decision")
        suggested = row.get("suggested_case_id")
        if decision not in {"existing_case", "new_case", "uncertain"}:
            raise ValueError(f"Invalid decision: {decision}")
        if decision == "uncertain":
            reviewed += 1
        elif decision == "existing_case":
            if suggested is None:
                raise ValueError("existing_case requires suggested_case_id")
            if suggested == expected:
                correct += 1
            else:
                incorrect += 1
        elif expected is None:
            correct += 1
        else:
            missed += 1
    automatic = correct + incorrect + missed
    return {
        "documents": total,
        "correct_suggestions": correct,
        "wrong_existing_case_suggestions": incorrect,
        "missed_existing_cases": missed,
        "needs_review": reviewed,
        "suggestion_accuracy_excluding_review": round(correct / automatic, 4) if automatic else None,
        "review_rate": round(reviewed / total, 4),
        "wrong_existing_case_rate": round(incorrect / total, 4),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("jsonl", type=Path)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.jsonl.read_text(encoding="utf-8").splitlines() if line.strip()]
    print(json.dumps(evaluate(rows), indent=2))


if __name__ == "__main__":
    main()
