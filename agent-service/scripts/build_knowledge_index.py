import argparse
import json
from pathlib import Path

from agent_service.retrieval import build_index, rollback_index


def main() -> None:
    parser = argparse.ArgumentParser(description="Build or roll back the versioned knowledge index.")
    parser.add_argument("--rollback", action="store_true", help="Switch to the previous index version.")
    parser.add_argument("--source", type=Path, help="JSONL source-card path.")
    parser.add_argument("--index-dir", type=Path, help="Directory for immutable index snapshots.")
    args = parser.parse_args()
    result = rollback_index(args.index_dir) if args.rollback else build_index(args.source, args.index_dir)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
