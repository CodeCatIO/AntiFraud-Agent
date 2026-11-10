import json
from pathlib import Path

import pytest

from agent_service.retrieval import build_index, rollback_index, search_knowledge
from scripts.evaluate_retrieval import evaluate


SOURCE_PATH = Path(__file__).resolve().parents[1] / "data" / "knowledge_sources.jsonl"


def test_versioned_index_rebuild_and_search_all_strategies(tmp_path):
    first_manifest = build_index(SOURCE_PATH, tmp_path)
    second_manifest = build_index(SOURCE_PATH, tmp_path)

    assert first_manifest == second_manifest
    assert first_manifest["source_count"] == 20
    assert first_manifest["chunk_count"] == 20
    for strategy in ("bm25", "tfidf", "hybrid"):
        response = search_knowledge("个人信息隐私保护", 5, strategy, tmp_path)
        assert response["status"] == "completed"
        assert response["indexVersion"] == first_manifest["index_version"]
        assert response["results"]
        assert response["results"][0]["chunkId"]
        assert response["results"][0]["sourceUrl"].startswith("https://")
        assert response["results"][0]["locator"]
        assert response["results"][0]["excerptType"] == "paraphrase"


def test_no_match_returns_empty_citations_instead_of_fabricating(tmp_path):
    build_index(SOURCE_PATH, tmp_path)

    response = search_knowledge("quartz submarine zebra", 5, "hybrid", tmp_path)

    assert response["status"] == "completed"
    assert response["results"] == []
    assert response["message"]


def test_index_versions_can_be_rolled_back(tmp_path):
    source_path = tmp_path / "source.jsonl"
    source = {
        "source_id": "test-source",
        "document_id": "test-document",
        "version": "v1",
        "title": "测试标题",
        "source_title": "测试来源",
        "publisher": "测试发布者",
        "source_url": "https://example.org/source",
        "published_at": "2026-01-01",
        "retrieved_at": "2026-10-26",
        "locator": "第1段",
        "license_status": "test-only",
        "content": "个人信息保护需要最小化收集。",
        "retrieval_keywords": ["个人信息", "最小化收集"],
    }
    source_path.write_text(json.dumps(source, ensure_ascii=False) + "\n", encoding="utf-8")
    first = build_index(source_path, tmp_path / "indexes")["index_version"]
    source["version"] = "v2"
    source["content"] = "隐私信息应当采取访问控制。"
    source_path.write_text(json.dumps(source, ensure_ascii=False) + "\n", encoding="utf-8")
    second = build_index(source_path, tmp_path / "indexes")["index_version"]

    assert first != second
    assert rollback_index(tmp_path / "indexes") == {"current": first, "previous": second}
    response = search_knowledge("个人信息最小化", 1, "bm25", tmp_path / "indexes")
    assert response["indexVersion"] == first


def test_source_import_rejects_duplicate_document_ids(tmp_path):
    rows = SOURCE_PATH.read_text(encoding="utf-8").splitlines()
    duplicate_source = tmp_path / "duplicate.jsonl"
    duplicate_source.write_text(rows[0] + "\n" + rows[0] + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Duplicate document_id"):
        build_index(duplicate_source, tmp_path / "indexes")


def test_evaluation_reports_development_and_holdout_splits(tmp_path):
    build_index(SOURCE_PATH, tmp_path)
    cases = [
        {
            "query_id": "dev-query",
            "query": "个人信息隐私保护",
            "gold_document_ids": ["law_article_5_privacy"],
            "split": "dev",
        },
        {
            "query_id": "holdout-query",
            "query": "反诈风险提示",
            "gold_document_ids": ["law_article_30_user_warning"],
            "split": "holdout",
        },
    ]

    per_case, summary = evaluate(cases, tmp_path, 1)

    assert len(per_case) == 2
    assert summary["splits"]["dev"]["case_count"] == 1
    assert summary["splits"]["holdout"]["case_count"] == 1
    assert summary["splits"]["dev"]["metrics"]["hybrid"]["recall_at_5"] == 1.0
