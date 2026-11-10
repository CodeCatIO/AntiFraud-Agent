import argparse
import hashlib
import json
import math
import platform
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

from agent_service.retrieval import _load_current_index, search_knowledge


STRATEGIES = ("bm25", "tfidf", "hybrid")


def percentile(values: list[float], percentile_value: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = max(0, math.ceil(percentile_value * len(ordered)) - 1)
    return ordered[index]


def load_dataset(path: Path) -> list[dict]:
    cases = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not cases:
        raise ValueError("Retrieval evaluation dataset is empty")
    for case in cases:
        if not isinstance(case.get("query"), str) or not case.get("gold_document_ids"):
            raise ValueError(f"Invalid retrieval case: {case.get('query_id', '<missing id>')}")
    return cases


def evaluate(cases: list[dict], index_dir: Path, repeats: int) -> tuple[list[dict], dict]:
    per_case: list[dict] = []
    latencies: dict[str, list[float]] = {strategy: [] for strategy in STRATEGIES}
    reciprocal_ranks: dict[str, list[float]] = {strategy: [] for strategy in STRATEGIES}
    recall_hits: dict[str, dict[int, int]] = {
        strategy: {1: 0, 3: 0, 5: 0} for strategy in STRATEGIES
    }
    split_stats: dict[str, dict[str, dict]] = {}
    index_version = _load_current_index(index_dir)["manifest"]["index_version"]

    for case in cases:
        split = case.get("split", "unspecified")
        split_stats.setdefault(
            split,
            {
                strategy: {
                    "latencies": [],
                    "reciprocal_ranks": [],
                    "recall_hits": {1: 0, 3: 0, 5: 0},
                }
                for strategy in STRATEGIES
            },
        )
        case_result = {
            "query_id": case["query_id"],
            "query": case["query"],
            "split": split,
            "gold_document_ids": case["gold_document_ids"],
            "strategies": {},
        }
        gold_ids = set(case["gold_document_ids"])
        for strategy in STRATEGIES:
            response = None
            for _ in range(repeats):
                started_at = time.perf_counter()
                response = search_knowledge(case["query"], 5, strategy, index_dir)
                latency = (time.perf_counter() - started_at) * 1000
                latencies[strategy].append(latency)
                split_stats[split][strategy]["latencies"].append(latency)
            assert response is not None
            result_ids = [item["documentId"] for item in response["results"]]
            hit_rank = next(
                (rank for rank, document_id in enumerate(result_ids, start=1) if document_id in gold_ids),
                None,
            )
            reciprocal_ranks[strategy].append(1 / hit_rank if hit_rank else 0.0)
            split_stats[split][strategy]["reciprocal_ranks"].append(1 / hit_rank if hit_rank else 0.0)
            for cutoff in (1, 3, 5):
                if any(document_id in gold_ids for document_id in result_ids[:cutoff]):
                    recall_hits[strategy][cutoff] += 1
                    split_stats[split][strategy]["recall_hits"][cutoff] += 1
            case_result["strategies"][strategy] = {
                "ranked_document_ids": result_ids,
                "gold_rank": hit_rank,
                "index_version": response["indexVersion"],
            }
        per_case.append(case_result)

    summary = {
        "case_count": len(cases),
        "repeats_per_query": repeats,
        "index_version": index_version,
        "metrics": {},
        "splits": {},
    }
    for strategy in STRATEGIES:
        summary["metrics"][strategy] = {
            "recall_at_1": recall_hits[strategy][1] / len(cases),
            "recall_at_3": recall_hits[strategy][3] / len(cases),
            "recall_at_5": recall_hits[strategy][5] / len(cases),
            "mrr": statistics.mean(reciprocal_ranks[strategy]),
            "latency_p50_ms": percentile(latencies[strategy], 0.50),
            "latency_p95_ms": percentile(latencies[strategy], 0.95),
        }
    for split, strategies in split_stats.items():
        split_case_count = sum(1 for case in cases if case.get("split", "unspecified") == split)
        summary["splits"][split] = {"case_count": split_case_count, "metrics": {}}
        for strategy in STRATEGIES:
            values = strategies[strategy]
            summary["splits"][split]["metrics"][strategy] = {
                "recall_at_1": values["recall_hits"][1] / split_case_count,
                "recall_at_3": values["recall_hits"][3] / split_case_count,
                "recall_at_5": values["recall_hits"][5] / split_case_count,
                "mrr": statistics.mean(values["reciprocal_ranks"]),
                "latency_p50_ms": percentile(values["latencies"], 0.50),
                "latency_p95_ms": percentile(values["latencies"], 0.95),
            }
    return per_case, summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate BM25, TF-IDF and hybrid retrieval.")
    parser.add_argument("--dataset", type=Path, default=Path("data/retrieval_eval.jsonl"))
    parser.add_argument("--index-dir", type=Path, default=Path("data/indexes"))
    parser.add_argument("--output-dir", type=Path, default=Path("eval/results/latest"))
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    if args.repeats < 1 or args.repeats > 20:
        parser.error("--repeats must be between 1 and 20")

    cases = load_dataset(args.dataset)
    per_case, summary = evaluate(cases, args.index_dir, args.repeats)
    dataset_hash = hashlib.sha256(args.dataset.read_bytes()).hexdigest()
    index_data = _load_current_index(args.index_dir)
    manifest = {
        "dataset_path": str(args.dataset),
        "dataset_sha256": dataset_hash,
        "dataset_review_status": "synthetic_template_generated_not_human_reviewed",
        "index_version": summary["index_version"],
        "index_manifest": index_data["manifest"],
        "python_version": platform.python_version(),
        "run_at": datetime.now(timezone.utc).isoformat(),
        "repeats_per_query": args.repeats,
        "strategies": list(STRATEGIES),
        "limitations": [
            "Dataset queries are deterministic synthetic templates; gold labels are source-card ids, not human-judged semantic relevance.",
            "TF-IDF is a sparse lexical vector baseline, not a neural embedding model.",
            "Latency is measured locally and includes pointer lookup and retrieval; immutable snapshots are process-cached, so timing is environment-specific.",
        ],
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "results.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in per_case),
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
        "# Retrieval Evaluation",
        "",
        f"- Dataset cases: {summary['case_count']} (synthetic templates; not human-reviewed)",
        f"- Dataset SHA-256: {dataset_hash}",
        f"- Index version: {summary['index_version']}",
        f"- Repeats per query: {args.repeats}",
        "- TF-IDF is a sparse lexical vector baseline; no neural embeddings are used.",
        "",
        "| Strategy | Recall@1 | Recall@3 | Recall@5 | MRR | P50 ms | P95 ms |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for strategy in STRATEGIES:
        metrics = summary["metrics"][strategy]
        report_lines.append(
            "| {strategy} | {recall_at_1:.4f} | {recall_at_3:.4f} | {recall_at_5:.4f} | "
            "{mrr:.4f} | {latency_p50_ms:.3f} | {latency_p95_ms:.3f} |".format(
                strategy=strategy, **metrics
            )
        )
    for split, split_summary in summary["splits"].items():
        report_lines.extend(
            (
                "",
                f"## {split} ({split_summary['case_count']} cases)",
                "",
                "| Strategy | Recall@1 | Recall@3 | Recall@5 | MRR | P50 ms | P95 ms |",
                "|---|---:|---:|---:|---:|---:|---:|",
            )
        )
        for strategy in STRATEGIES:
            metrics = split_summary["metrics"][strategy]
            report_lines.append(
                "| {strategy} | {recall_at_1:.4f} | {recall_at_3:.4f} | {recall_at_5:.4f} | "
                "{mrr:.4f} | {latency_p50_ms:.3f} | {latency_p95_ms:.3f} |".format(
                    strategy=strategy, **metrics
                )
            )
    report_lines.extend(("", "Results are offline retrieval measurements, not claims about real-world fraud accuracy."))
    (args.output_dir / "report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    print(json.dumps({"summary": summary, "output_dir": str(args.output_dir)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
