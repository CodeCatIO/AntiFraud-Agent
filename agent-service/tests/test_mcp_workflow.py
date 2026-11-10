import asyncio
import uuid

import httpx
import httpx2
from mcp import Client
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
import pytest

from agent_service import main, mcp_tools, workflow
from agent_service.mcp_client import call_readonly_tools


def test_mcp_server_exposes_only_validated_readonly_tools(monkeypatch):
    async def fake_detection(content, model):
        return {
            "status": "completed",
            "riskScore": 61,
            "riskLevel": "中风险",
            "detail": "合成测试响应",
            "model": model or "mock",
            "keywords": ["验证码"],
            "patterns": ["synthetic"],
        }

    async def scenario():
        monkeypatch.setattr(mcp_tools, "call_detection_service", fake_detection)
        async with Client(mcp_tools.mcp_server) as client:
            listed_tools = await client.list_tools()
            assert {tool.name for tool in listed_tools.tools} == {
                "detect_text",
                "search_knowledge",
            }
            detection = await client.call_tool(
                "detect_text",
                {"content": "合成测试线索", "model": "mock"},
            )
            assert detection.is_error is False
            assert detection.structured_content["riskScore"] == 61
            assert detection.structured_content["status"] == "completed"

            search = await client.call_tool(
                "search_knowledge",
                {"query": "电信诈骗预警劝阻", "top_k": 3},
            )
            assert search.structured_content["status"] == "completed"
            assert search.structured_content["results"]
            citation = search.structured_content["results"][0]
            assert citation["chunkId"]
            assert citation["sourceUrl"].startswith("https://")
            assert citation["locator"]
            assert citation["excerptType"] == "paraphrase"

    asyncio.run(scenario())


def test_mcp_tool_schema_rejects_empty_content():
    async def scenario():
        async with Client(mcp_tools.mcp_server) as client:
            result = await client.call_tool("detect_text", {"content": ""})
            assert result.is_error is True

    asyncio.run(scenario())


def test_mcp_http_endpoint_requires_shared_service_token(monkeypatch):
    async def scenario():
        monkeypatch.setenv("AGENT_SERVICE_TOKEN", "expected-token")
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=main.app),
            base_url="http://127.0.0.1:8001",
        ) as client:
            missing = await client.get("/mcp/")
            invalid = await client.get(
                "/mcp/",
                headers={"X-Agent-Service-Token": "wrong-token"},
            )
        assert missing.status_code == 401
        assert invalid.status_code == 401

    asyncio.run(scenario())


def test_readonly_tools_use_streamable_http_and_emit_trace(monkeypatch):
    async def fake_detection(content, model):
        return {
            "status": "completed",
            "riskScore": 42,
            "riskLevel": "低风险",
            "detail": "合成测试响应",
            "model": model or "mock",
        }

    async def scenario():
        monkeypatch.setenv("AGENT_SERVICE_TOKEN", "test-token")
        monkeypatch.setattr(mcp_tools, "call_detection_service", fake_detection)
        async with main.mcp_server.session_manager.run():
            return await call_readonly_tools(
                "合成测试线索",
                "mock",
                transport=httpx2.ASGITransport(app=main.app),
            )

    result = asyncio.run(scenario())
    assert result["detection"]["riskScore"] == 42
    assert [call["tool"] for call in result["toolCalls"]] == [
        "detect_text",
        "search_knowledge",
    ]
    assert all(call["status"] == "completed" for call in result["toolCalls"])
    assert result["toolCalls"][0]["inputHash"]


def test_langgraph_composes_tool_results_into_draft(monkeypatch):
    run_id = str(uuid.uuid4())
    detection = {
        "status": "completed",
        "riskScore": 55,
        "riskLevel": "中风险",
        "detail": "合成检测结果",
    }

    async def fake_tools(_content, _model):
        return {
            "detection": detection,
            "knowledgeSearch": {
                "status": "not_configured",
                "results": [],
            },
            "toolCalls": [{"tool": "detect_text", "status": "completed"}],
        }

    async def scenario():
        async with AsyncSqliteSaver.from_conn_string(":memory:") as checkpointer:
            await checkpointer.setup()
            workflow.configure_checkpointer(checkpointer)
            monkeypatch.setattr(workflow, "call_readonly_tools", fake_tools)
            result = await workflow.run_workflow(
                run_id,
                12,
                7,
                "今天通过微信，冒充客服要求转账。",
            )
            workflow.configure_checkpointer(None)
            return result

    result = asyncio.run(scenario())
    assert result["draft"]["status"] == "COMPLETED"
    assert result["draft"]["citations"] == []
    assert "没有可引用依据" in result["draft"]["uncertaintyNotes"][0]
    assert result["toolCalls"][0]["tool"] == "detect_text"
    assert workflow.pending_interrupt(result)["kind"] == "review"


def test_langgraph_fails_closed_when_detection_tool_fails(monkeypatch):
    async def failed_tools(_content, _model):
        return {
            "detection": {
                "status": "failed",
                "riskScore": None,
                "riskLevel": "检测失败",
                "errorCode": "UPSTREAM_TIMEOUT",
            },
            "knowledgeSearch": {
                "status": "not_configured",
                "results": [],
            },
            "toolCalls": [{"tool": "detect_text", "status": "failed"}],
        }

    async def scenario():
        async with AsyncSqliteSaver.from_conn_string(":memory:") as checkpointer:
            await checkpointer.setup()
            workflow.configure_checkpointer(checkpointer)
            monkeypatch.setattr(workflow, "call_readonly_tools", failed_tools)
            result = await workflow.run_workflow(
                str(uuid.uuid4()),
                12,
                7,
                "今天通过微信，冒充客服要求转账。",
            )
            workflow.configure_checkpointer(None)
            return result

    result = asyncio.run(scenario())
    assert result["draft"]["status"] == "FAILED"
    assert result["draft"]["detection"]["riskScore"] is None
    assert any("不能据此判断为低风险" in note for note in result["draft"]["uncertaintyNotes"])


def test_missing_information_interrupts_and_resumes_with_supplement(monkeypatch):
    observed_content = []

    async def fake_tools(content, _model):
        observed_content.append(content)
        return {
            "detection": {"status": "completed", "riskScore": 20, "riskLevel": "低风险"},
            "knowledgeSearch": {"status": "completed", "results": []},
            "toolCalls": [],
        }

    async def scenario():
        async with AsyncSqliteSaver.from_conn_string(":memory:") as checkpointer:
            await checkpointer.setup()
            workflow.configure_checkpointer(checkpointer)
            monkeypatch.setattr(workflow, "call_readonly_tools", fake_tools)
            run_id = str(uuid.uuid4())
            waiting = await workflow.run_workflow(run_id, 12, 7, "我遇到疑似诈骗。")
            first_interrupt = workflow.pending_interrupt(waiting)
            resumed = await workflow.resume_workflow(
                run_id,
                {
                    "answers": {
                        "contact_channel": "微信",
                        "claimed_identity": "冒充客服",
                        "requested_action": "要求转账",
                        "event_time": "今天",
                    }
                },
            )
            workflow.configure_checkpointer(None)
            return first_interrupt, resumed

    first_interrupt, resumed = asyncio.run(scenario())
    assert first_interrupt["kind"] == "supplement"
    assert {question["field"] for question in first_interrupt["questions"]} == {
        "contact_channel",
        "claimed_identity",
        "requested_action",
        "event_time",
    }
    assert "微信" in observed_content[0]
    assert resumed["missingInformation"] == []
    assert workflow.pending_interrupt(resumed)["kind"] == "review"


def test_missing_information_ignores_negated_fields_and_non_channel_app_mentions():
    missing = workflow.find_missing_information(
        "对方冒充客服，要求下载APP，事情发生在近日。"
    )
    assert {item["field"] for item in missing} == {"contact_channel"}

    negated = workflow.find_missing_information(
        "微信消息显示，对方不是客服，也没有要求转账；事情发生在今天。"
    )
    assert {item["field"] for item in negated} == {
        "claimed_identity",
        "requested_action",
    }

    negated_with_modifiers = workflow.find_missing_information(
        "电话记录里对方没有自称银行工作人员，不要求点击链接，发生在刚才。"
    )
    assert {item["field"] for item in negated_with_modifiers} == {
        "claimed_identity",
        "requested_action",
    }

    negated_without_subject = workflow.find_missing_information(
        "短信记录显示，没有人自称银行工作人员，也没有要求付款，事情发生在昨晚。"
    )
    assert {item["field"] for item in negated_without_subject} == {
        "claimed_identity",
        "requested_action",
    }

    late_evening = workflow.find_missing_information(
        "昨晚通过邮件收到消息，对方自称银行工作人员，要求点击链接。"
    )
    assert late_evening == []


def test_checkpoint_survives_saver_reopen_and_review_cannot_edit_detection(monkeypatch, tmp_path):
    async def fake_tools(_content, _model):
        return {
            "detection": {"status": "completed", "riskScore": 55, "riskLevel": "中风险"},
            "knowledgeSearch": {"status": "completed", "results": []},
            "toolCalls": [],
        }

    run_id = str(uuid.uuid4())
    checkpoint_path = tmp_path / "checkpoint.sqlite"

    async def pause_workflow():
        async with AsyncSqliteSaver.from_conn_string(str(checkpoint_path)) as checkpointer:
            await checkpointer.setup()
            workflow.configure_checkpointer(checkpointer)
            monkeypatch.setattr(workflow, "call_readonly_tools", fake_tools)
            return await workflow.run_workflow(
                run_id,
                12,
                7,
                "今天通过微信，冒充客服要求转账。",
            )

    paused = asyncio.run(pause_workflow())
    assert workflow.pending_interrupt(paused)["kind"] == "review"

    async def resume_after_reopen():
        async with AsyncSqliteSaver.from_conn_string(str(checkpoint_path)) as checkpointer:
            await checkpointer.setup()
            workflow.configure_checkpointer(checkpointer)
            snapshot = await workflow.get_workflow_state(run_id)
            assert snapshot.next == ("wait_for_review",)
            with pytest.raises(ValueError, match="non-editable fields"):
                await workflow.resume_workflow(
                    run_id,
                    {
                        "decision": "modify",
                        "reviewerId": 7,
                        "comment": "合成测试",
                        "edits": {"detection": {"riskScore": 100}},
                    },
                )
            completed = await workflow.resume_workflow(
                run_id,
                {
                    "decision": "modify",
                    "reviewerId": 7,
                    "comment": "审核通过合成修改",
                    "edits": {"summary": "复核后的说明"},
                },
            )
            assert completed["status"] == "COMPLETED"
            assert completed["draft"]["summary"] == "复核后的说明"
            assert completed["draft"]["detection"]["riskScore"] == 55
            workflow.configure_checkpointer(None)

    asyncio.run(resume_after_reopen())
