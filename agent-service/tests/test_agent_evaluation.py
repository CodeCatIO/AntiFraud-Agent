from scripts.create_agent_eval_dataset import FIELDS, create_cases
from scripts.evaluate_agent import evaluate


def test_agent_dataset_has_fixed_dev_holdout_split_and_valid_gold_fields():
    cases = create_cases()
    assert len(cases) == 120
    assert sum(case["split"] == "dev" for case in cases) == 96
    assert sum(case["split"] == "holdout" for case in cases) == 24
    assert {case["category"] for case in cases} == {
        "complete_context",
        "missing_context",
        "negated_claims",
        "prompt_injection",
    }
    assert all(set(case["expected_missing_fields"]).issubset(FIELDS) for case in cases)


def test_development_evaluation_reports_route_and_schema_metrics():
    development_cases = [case for case in create_cases() if case["split"] == "dev"]
    results, summary = evaluate(development_cases, repeats=1)

    assert len(results) == 96
    assert summary["metrics"]["case_count"] == 96
    assert summary["metrics"]["workflow_route_accuracy"] == 1.0
    assert summary["metrics"]["draft_schema_validity"] == 1.0
