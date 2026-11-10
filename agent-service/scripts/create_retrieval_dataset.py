import argparse
import hashlib
import json
from pathlib import Path

from agent_service.retrieval import _read_sources


def make_queries(source_rows: list[dict]) -> list[dict[str, str]]:
    cases = []
    for row in source_rows:
        keywords = row["retrieval_keywords"]
        first_keyword = keywords[0]
        second_keyword = keywords[1] if len(keywords) > 1 else first_keyword
        templates = (
            f"{first_keyword}相关要求是什么？",
            f"请查询{second_keyword}的官方参考依据。",
            f"{row['title']}有哪些相关说明？",
            f"{first_keyword}与{second_keyword}分别应关注什么？",
            f"{row['source_title']} {row['locator']} {first_keyword}",
        )
        for ordinal, query in enumerate(templates, start=1):
            cases.append(
                {
                    "query_id": f"{row['document_id']}-{ordinal:02d}",
                    "query": query,
                    "gold_document_ids": [row["document_id"]],
                    "split": "holdout" if ordinal == 5 else "dev",
                }
            )
    return cases


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a deterministic synthetic retrieval dataset.")
    parser.add_argument("--source", type=Path, default=Path("data/knowledge_sources.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("data/retrieval_eval.jsonl"))
    args = parser.parse_args()
    cases = make_queries(_read_sources(args.source))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    content = "".join(json.dumps(case, ensure_ascii=False, sort_keys=True) + "\n" for case in cases)
    args.output.write_text(content, encoding="utf-8")
    digest = hashlib.sha256(args.output.read_bytes()).hexdigest()
    print(json.dumps({"cases": len(cases), "sha256": digest, "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
