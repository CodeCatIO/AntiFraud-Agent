import argparse
import hashlib
import json
import math
import platform
import statistics
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from agent_service.mcp_client import ALLOWED_TOOL_NAMES
from agent_service.workflow import build_draft, find_missing_information, route_after_information_check


FIELDS = ("contact_channel", "claimed_identity", "requested_action", "event_time")


def percentile(values: list[float], percentile_value: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = max(0, math.ceil(percentile_value * len(ordered)) - 1)
    return ordered[index]


def load_dataset(path: Path) -> list[dict]:
    cases = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not cases:
        raise ValueError("Agent evaluation dataset is empty")
    identifiers = set()
    for case in cases:
        if not isinstance(case.get("content"), str) or not case["content"].strip():
            raise ValueError(f"Invalid content in {case.get('case_id', '<missing id>')}")
        if not isinstance(case.get("expected_missing_fields"), list) or not set(
            case["expected_missing_fields"]
        ).issubset(FIELDS):
            raise ValueError(f"Invalid gold fields in {case.get('case_id', '<missing id>')}")
        if not case.get("case_id") or case["case_id"] in identifiers:
            raise ValueError(f"Missing or duplicate case id: {case.get('case_id')}")
        if case.get("split") not in {"dev", "holdout"}:
            raise ValueError(f"Invalid split in {case['case_id']}")
        identifiers.add(case["case_id"])
    return cases


def _evaluate_case(case: dict, repeats: int) -> tuple[dict, list[float], dict]:
    latencies = []
    missing = []
    draft = {}
    route = ""
    for _ in range(repeats):
        started_at = time.perf_counter()
        missing = find_missing_information(case["content"])
        route = route_after_information_check({"missingInformation": missing, "supplementRound": 0})
        state = {
            "caseId": 1,
            "runId": case["case_id"],
            "detection": {"status": "completed", "riskScore": 50, "riskLevel": "中风险"},
            "knowledgeSearch": {"status": "completed", "results": []},
            "missingInformation": missing,
        }
        draft = build_draft(state)["draft"]
        latencies.append((time.perf_counter() - started_at) * 1000)

    expected_missing = set(case["expected_missing_fields"])
    actual_missing = {item["field"] for item in missing}
    expected_present = set(FIELDS) - expected_missing
    actual_present = set(FIELDS) - actual_missing
    schema_valid = (
        {"caseId", "runId", "status", "summary", "detection", "citations", "missingInformation",
         "suggestedChecks", "uncertaintyNotes"}.issubset(draft)
        and isinstance(draft["summary"], str)
        and isinstance(draft["detection"], dict)
        and isinstance(draft["citations"], list)
        and isinstance(draft["missingInformation"], list)
        and isinstance(draft["suggestedChecks"], list)
        and isinstance(draft["uncertaintyNotes"], list)
    )
    expected_route = "request_information" if expected_missing else "run_tools"
    result = {
        "case_id": case["case_id"],
        "category": case["category"],
        "split": case["split"],
        "expected_missing_fields": sorted(expected_missing),
        "predicted_missing_fields": sorted(actual_missing),
        "field_true_positives": len(expected_present & actual_present),
        "field_false_positives": len(actual_present - expected_present),
        "field_false_negatives": len(expected_present - actual_present),
        "expected_route": expected_route,
        "predicted_route": route,
        "route_correct": route == expected_route,
        "draft_schema_valid": schema_valid,
        "latency_ms_median": statistics.median(latencies),
    }
    counts = {
        "tp": result["field_true_positives"],
        "fp": result["field_false_positives"],
        "fn": result["field_false_negatives"],
        "route_correct": int(result["route_correct"]),
        "schema_valid": int(schema_valid),
    }
    return result, latencies, counts


def _metrics(counts: dict, case_count: int, latencies: list[float]) -> dict:
    tp, fp, fn = counts["tp"], counts["fp"], counts["fn"]
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {
        "case_count": case_count,
        "field_precision": precision,
        "field_recall": recall,
        "field_f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
        "workflow_route_accuracy": counts["route_correct"] / case_count if case_count else 0.0,
        "draft_schema_validity": counts["schema_valid"] / case_count if case_count else 0.0,
        "latency_p50_ms": percentile(latencies, 0.50),
        "latency_p95_ms": percentile(latencies, 0.95),
    }


def evaluate(cases: list[dict], repeats: int) -> tuple[list[dict], dict]:
    results = []
    latencies_by_split = defaultdict(list)
    counts_by_split = defaultdict(lambda: defaultdict(int))
    counts_by_category = defaultdict(lambda: defaultdict(int))
    latencies_by_category = defaultdict(list)
    totals = defaultdict(int)
    all_latencies = []

    for case in cases:
        result, latencies, counts = _evaluate_case(case, repeats)
        results.append(result)
        all_latencies.extend(latencies)
        latencies_by_split[case["split"]].extend(latencies)
        latencies_by_category[case["category"]].extend(latencies)
        for key, value in counts.items():
            totals[key] += value
            counts_by_split[case["split"]][key] += value
            counts_by_category[case["category"]][key] += value

    summary = {
        "case_count": len(cases),
        "repeats_per_case": repeats,
        "metrics": _metrics(totals, len(cases), all_latencies),
        "splits": {},
        "categories": {},
        "tool_allowlist": sorted(ALLOWED_TOOL_NAMES),
    }
    for split in sorted(counts_by_split):
        count = sum(case["split"] == split for case in cases)
        summary["splits"][split] = _metrics(counts_by_split[split], count, latencies_by_split[split])
    for category in sorted(counts_by_category):
        count = sum(case["category"] == category for case in cases)
        summary["categories"][category] = _metrics(
            counts_by_category[category], count, latencies_by_category[category]
        )
    return results, summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate deterministic Agent extraction and workflow routing.")
    parser.add_argument("--dataset", type=Path, default=Path("data/agent_eval_v4.jsonl"))
    parser.add_argument("--output-dir", type=Path, default=Path("eval/agent/v4"))
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()
    if args.repeats < 1 or args.repeats > 100:
        parser.error("--repeats must be between 1 and 100")

    cases = load_dataset(args.dataset)
    results, summary = evaluate(cases, args.repeats)
    dataset_hash = hashlib.sha256(args.dataset.read_bytes()).hexdigest()
    manifest = {
        "dataset_version": "v4",
        "dataset_path": str(args.dataset),
        "dataset_sha256": dataset_hash,
        "dataset_review_status": "synthetic_templates_generated_and_script_validated; external_human_review_pending",
        "python_version": platform.python_version(),
        "run_at": datetime.now(timezone.utc).isoformat(),
        "repeats_per_case": args.repeats,
        "workflow": "deterministic missing-information rules plus fixed draft fixture",
        "tool_allowlist": sorted(ALLOWED_TOOL_NAMES),
        "external_detector_baseline": "not_run",
        "single_turn_llm_baseline": "not_run",
        "limitations": [
            "Cases are synthetic and partly templated; this is an offline engineering regression, not fraud-detection accuracy.",
            "Gold labels are generated from explicit template construction and require independent student/advisor review before thesis claims.",
            "Draft schema checks use fixed tool-result fixtures; no network, Flask detector, or external LLM call is made.",
            "Latency covers local rule routing and fixed draft construction only, not MCP, model, database, or end-to-end latency.",
        ],
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "cases.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in results),
        encoding="utf-8",
    )
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report_lines = [
        "# Agent Workflow Evaluation",
        "",
        f"- Cases: {summary['case_count']} synthetic, template-derived scenarios",
        f"- Dataset SHA-256: {dataset_hash}",
        f"- Repeats per case: {args.repeats}",
        "- External detector and single-turn LLM baselines: not run (offline fixture evaluation).",
        "- Latency covers local extraction/routing/draft fixture only; it is not end-to-end performance.",
        "",
        "| Split | Cases | Field P | Field R | Field F1 | Route accuracy | Schema validity | P50 ms | P95 ms |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for split, metrics in [("all", summary["metrics"]), *sorted(summary["splits"].items())]:
        report_lines.append(
            f"| {split} | {metrics['case_count']} | {metrics['field_precision']:.4f} | "
            f"{metrics['field_recall']:.4f} | {metrics['field_f1']:.4f} | "
            f"{metrics['workflow_route_accuracy']:.4f} | {metrics['draft_schema_validity']:.4f} | "
            f"{metrics['latency_p50_ms']:.4f} | {metrics['latency_p95_ms']:.4f} |"
        )
    report_lines.extend(("", "## Category breakdown", "", "| Category | Cases | Field F1 | Route accuracy |", "|---|---:|---:|---:|"))
    for category, metrics in sorted(summary["categories"].items()):
        report_lines.append(
            f"| {category} | {metrics['case_count']} | {metrics['field_f1']:.4f} | "
            f"{metrics['workflow_route_accuracy']:.4f} |"
        )
    report_lines.extend(("", "Results are a reproducible local workflow check, not evidence of real-world fraud accuracy."))
    (args.output_dir / "report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    print(json.dumps({"summary": summary, "output_dir": str(args.output_dir)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
