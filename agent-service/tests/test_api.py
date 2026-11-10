import asyncio
import uuid

import pytest
import httpx
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from agent_service import main


def test_start_run_requires_service_token(monkeypatch):
    monkeypatch.setenv("AGENT_SERVICE_TOKEN", "expected")
    request = main.RunRequest(
        runId=str(uuid.uuid4()),
        caseId=1,
        ownerId=1,
        content="测试内容",
    )

    with pytest.raises(main.HTTPException) as error:
        main.verify_service_key("wrong")

    assert error.value.status_code == 401


def test_health_is_available():
    assert asyncio.run(main.health()) == {"status": "ok"}


def test_start_run_is_idempotent_after_first_accept(monkeypatch):
    async def noop(_request):
        return None

    async def scenario():
        monkeypatch.setenv("AGENT_SERVICE_TOKEN", "test-key")
        monkeypatch.setattr(main, "execute_run", noop)
        run_id = str(uuid.uuid4())
        request = main.RunRequest(
            runId=run_id,
            caseId=2,
            ownerId=3,
            content="测试线索",
        )
        background = main.BackgroundTasks()
        first = await main.start_run(request, background, "test-key")
        second = await main.start_run(request, main.BackgroundTasks(), "test-key")
        assert first["runId"] == run_id
        assert second["status"] == "QUEUED"
        assert len(background.tasks) == 1

    asyncio.run(scenario())


def test_start_run_rejects_reused_id_with_different_input(monkeypatch):
    async def scenario():
        monkeypatch.setenv("AGENT_SERVICE_TOKEN", "test-key")
        run_id = str(uuid.uuid4())
        original = main.RunRequest(
            runId=run_id,
            caseId=2,
            ownerId=3,
            content="第一段线索",
        )
        changed = main.RunRequest(
            runId=run_id,
            caseId=2,
            ownerId=3,
            content="另一段线索",
        )
        await main.start_run(original, main.BackgroundTasks(), "test-key")
        with pytest.raises(main.HTTPException) as error:
            await main.start_run(changed, main.BackgroundTasks(), "test-key")
        assert error.value.status_code == 409

    asyncio.run(scenario())


def test_publish_event_retries_and_checks_backend_result_code(monkeypatch):
    attempts = 0

    def respond(_request):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(503, json={"code": "503"})
        return httpx.Response(200, json={"code": "200"})

    async def scenario():
        await main.publish_event(
            str(uuid.uuid4()),
            1,
            "run.started",
            "RUNNING",
            {},
            transport=httpx.MockTransport(respond),
        )

    asyncio.run(scenario())
    assert attempts == 2


def test_failed_detection_is_reported_as_failed_run(monkeypatch):
    run_id = str(uuid.uuid4())
    request = main.RunRequest(
        runId=run_id,
        caseId=5,
        ownerId=7,
        content="合成测试线索",
    )
    sent_events = []

    async def failed_workflow(workflow_run_id, case_id, _owner_id, _content, _model):
        detection = {
            "status": "failed",
            "riskScore": None,
            "riskLevel": "检测失败",
            "errorCode": "UPSTREAM_TIMEOUT",
        }
        return {
            "detection": detection,
            "toolCalls": [],
            "draft": {
                "caseId": case_id,
                "runId": workflow_run_id,
                "status": "FAILED",
                "detection": detection,
            },
        }

    async def capture_event(_run_id, event_seq, event_type, status, payload):
        sent_events.append((event_seq, event_type, status, payload))

    async def capture_checkpointed_event(_run_id, event_type, status, payload):
        event_seq = len(sent_events) + 1
        sent_events.append((event_seq, event_type, status, payload))
        main.run_states[_run_id].update({"status": status, "lastEventSeq": event_seq})
        return event_seq

    async def scenario():
        main.run_states[run_id] = {"runId": run_id, "status": "QUEUED"}
        monkeypatch.setattr(main.workflow, "run_workflow", failed_workflow)
        monkeypatch.setattr(
            main.workflow,
            "pending_interrupt",
            lambda _result: {"kind": "review", "allowedDecisions": ["approve", "modify", "return"]},
        )
        monkeypatch.setattr(main, "publish_event", capture_event)
        monkeypatch.setattr(main, "publish_checkpointed_event", capture_checkpointed_event)
        await main.execute_run(request)

    asyncio.run(scenario())
    state = main.run_states.pop(run_id)
    assert state["status"] == "WAITING_FOR_REVIEW"
    assert state["draft"]["detection"]["riskScore"] is None
    assert sent_events[-1][1:3] == ("run.waiting_for_review", "WAITING_FOR_REVIEW")
    assert [event[0] for event in sent_events] == [1, 2, 3]


def test_run_waits_for_review_and_resume_finishes_with_monotonic_events(monkeypatch, tmp_path):
    run_id = str(uuid.uuid4())
    request = main.RunRequest(
        runId=run_id,
        caseId=5,
        ownerId=7,
        content="我遇到疑似诈骗。",
    )
    sent_events = []
    checkpoint_path = tmp_path / "agent.sqlite"

    async def fake_tools(_content, _model):
        return {
            "detection": {"status": "completed", "riskScore": 54, "riskLevel": "中风险"},
            "knowledgeSearch": {"status": "completed", "results": []},
            "toolCalls": [{"tool": "detect_text", "status": "completed"}],
        }

    async def capture_event(_run_id, event_seq, event_type, status, payload):
        sent_events.append((event_seq, event_type, status, payload))

    async def scenario():
        async with AsyncSqliteSaver.from_conn_string(str(checkpoint_path)) as checkpointer:
            await checkpointer.setup()
            main.workflow.configure_checkpointer(checkpointer)
            monkeypatch.setenv("AGENT_SERVICE_TOKEN", "test-token")
            monkeypatch.setattr(main.workflow, "call_readonly_tools", fake_tools)
            monkeypatch.setattr(main, "publish_event", capture_event)
            main.run_states[run_id] = {"runId": run_id, "status": "QUEUED"}

            await main.execute_run(request)
            assert main.run_states[run_id]["status"] == "WAITING_FOR_INFO"
            assert [event[0] for event in sent_events] == [1, 2]
            supplement = main.SupplementRequest(
                round=1,
                answers={
                    "contact_channel": "微信",
                    "claimed_identity": "冒充客服",
                    "requested_action": "要求转账",
                    "event_time": "今天",
                }
            )
            await main.supplement_run(run_id, supplement, "test-token")
            assert main.run_states[run_id]["status"] == "WAITING_FOR_REVIEW"
            assert [event[0] for event in sent_events] == [1, 2, 3, 4]
            main.run_states.pop(run_id)
        main.workflow.configure_checkpointer(None)

        async with AsyncSqliteSaver.from_conn_string(str(checkpoint_path)) as checkpointer:
            await checkpointer.setup()
            main.workflow.configure_checkpointer(checkpointer)
            restored = await main.get_run(run_id, "test-token")
            assert restored["status"] == "WAITING_FOR_REVIEW"
            review = main.ReviewRequest(
                decision="modify",
                reviewerId=7,
                comment="保留证据边界，补充审核意见",
                edits=main.ReviewEdits(summary="人工复核后的摘要"),
            )
            result = await main.review_run(run_id, review, "test-token")
            duplicate = await main.review_run(run_id, review, "test-token")
            snapshot = await main.workflow.get_workflow_state(run_id)
            main.workflow.configure_checkpointer(None)
            return result, duplicate, snapshot

    result, duplicate, snapshot = asyncio.run(scenario())
    assert result["status"] == "COMPLETED"
    assert duplicate["idempotent"] is True
    assert snapshot.values == {}
    assert sent_events[-1][3]["draft"]["summary"] == "人工复核后的摘要"
    assert sent_events[-1][3]["draft"]["detection"]["riskScore"] == 54
    assert [event[0] for event in sent_events] == [1, 2, 3, 4, 5]
    assert sent_events[-1][1:3] == ("run.finished", "COMPLETED")
