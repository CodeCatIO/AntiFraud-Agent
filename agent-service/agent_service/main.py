import asyncio
import hashlib
import hmac
import logging
import os
from pathlib import Path
from typing import Literal
from datetime import datetime, timezone
from typing import Any
from contextlib import asynccontextmanager

import httpx
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import BaseModel, ConfigDict, Field, field_validator

from agent_service.mcp_tools import mcp_server
from agent_service import workflow

mcp_http_app = mcp_server.streamable_http_app(
    streamable_http_path="/",
    stateless_http=True,
    transport_security=TransportSecuritySettings(
        allowed_hosts=["127.0.0.1:*", "localhost:*", "agent-service:*"],
    ),
)


@asynccontextmanager
async def lifespan(_app):
    checkpoint_path = Path(os.getenv("CHECKPOINT_DB_PATH", "data/agent-checkpoints.sqlite"))
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    async with AsyncSqliteSaver.from_conn_string(str(checkpoint_path)) as checkpointer:
        await checkpointer.setup()
        workflow.configure_checkpointer(checkpointer)
        try:
            async with mcp_server.session_manager.run():
                yield
        finally:
            workflow.configure_checkpointer(None)


app = FastAPI(title="Anti-Fraud Agent Service", version="0.1.0", lifespan=lifespan)
run_states: dict[str, dict[str, Any]] = {}
run_locks: dict[str, asyncio.Lock] = {}
logger = logging.getLogger(__name__)


class RunRequest(BaseModel):
    runId: str = Field(min_length=36, max_length=36)
    caseId: int = Field(gt=0)
    ownerId: int = Field(gt=0)
    content: str = Field(min_length=1, max_length=10000)
    model: str | None = Field(default=None, max_length=32)


class SupplementRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    round: int = Field(ge=1, le=2)
    answers: dict[str, str] = Field(min_length=1, max_length=4)

    @field_validator("answers")
    @classmethod
    def validate_answers(cls, answers: dict[str, str]) -> dict[str, str]:
        allowed = {"contact_channel", "claimed_identity", "requested_action", "event_time"}
        if not set(answers).issubset(allowed) or any(
            not value.strip() or len(value) > 500 for value in answers.values()
        ):
            raise ValueError("Answers must contain requested fields with up to 500 characters each")
        return answers


class ReviewEdits(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str | None = Field(default=None, max_length=2000)
    missingInformation: list[str] | None = Field(default=None, max_length=20)
    suggestedChecks: list[str] | None = Field(default=None, max_length=20)
    uncertaintyNotes: list[str] | None = Field(default=None, max_length=20)


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["approve", "modify", "return"]
    reviewerId: int = Field(gt=0)
    comment: str = Field(default="", max_length=2000)
    edits: ReviewEdits | None = None


@app.middleware("http")
async def protect_mcp_endpoint(request, call_next):
    if request.url.path == "/mcp" or request.url.path.startswith("/mcp/"):
        try:
            verify_service_key(request.headers.get("X-Agent-Service-Token"))
        except HTTPException as exc:
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    return await call_next(request)


app.mount("/mcp", mcp_http_app)


def verify_service_key(provided: str | None) -> None:
    expected = os.getenv("AGENT_SERVICE_TOKEN", "")
    if not expected or not provided or not hmac.compare_digest(expected, provided):
        raise HTTPException(status_code=401, detail="Invalid service credentials")


async def publish_event(
    run_id: str,
    event_seq: int,
    event_type: str,
    status: str,
    payload: dict[str, Any],
    transport: httpx.AsyncBaseTransport | None = None,
) -> None:
    callback_base = os.getenv(
        "BACKEND_EVENT_URL",
        "http://backend:9090/internal/agent/v1/runs",
    ).rstrip("/")
    token = os.getenv("AGENT_SERVICE_TOKEN", "")
    event = {
        "eventSeq": event_seq,
        "eventType": event_type,
        "status": status,
        "payload": payload,
        "occurredAt": datetime.now(timezone.utc).isoformat(),
    }
    timeout = httpx.Timeout(connect=5, read=10, write=5, pool=5)
    last_error: Exception | None = None
    for delay in (0, 0.2, 0.6):
        if delay:
            await asyncio.sleep(delay)
        try:
            async with httpx.AsyncClient(timeout=timeout, transport=transport) as client:
                response = await client.post(
                    f"{callback_base}/{run_id}/events",
                    json=event,
                    headers={"X-Agent-Service-Token": token},
                )
                response.raise_for_status()
                body = response.json()
                if not isinstance(body, dict) or str(body.get("code")) != "200":
                    raise httpx.HTTPStatusError(
                        "Backend rejected the event",
                        request=response.request,
                        response=response,
                    )
                return
        except (httpx.HTTPError, ValueError) as exc:
            last_error = exc
    raise RuntimeError("Backend event callback failed") from last_error


async def publish_checkpointed_event(
    run_id: str,
    event_type: str,
    status: str,
    payload: dict[str, Any],
) -> int:
    snapshot = await workflow.get_workflow_state(run_id)
    supplement_round = int(snapshot.values.get("supplementRound", 0))
    if event_type in {"run.waiting_for_info", "step.completed"}:
        event_seq = 2 + supplement_round
    elif event_type == "run.waiting_for_review":
        event_seq = 3 + supplement_round
    elif event_type == "run.finished":
        event_seq = 4 + supplement_round
    else:
        raise ValueError("Unsupported checkpointed event type")
    await publish_event(run_id, event_seq, event_type, status, payload)
    current = run_states.setdefault(run_id, {"runId": run_id})
    current.update({"status": status, "lastEventSeq": event_seq})
    return event_seq


def _interrupt_from_snapshot(snapshot) -> dict[str, Any] | None:
    for task in getattr(snapshot, "tasks", ()):
        for pending in getattr(task, "interrupts", ()):
            value = getattr(pending, "value", None)
            if isinstance(value, dict):
                return value
    return None


def _restore_run_status(state: dict[str, Any], pending: dict[str, Any] | None) -> None:
    if pending and pending.get("kind") == "supplement":
        state["status"] = "WAITING_FOR_INFO"
        state["lastEventSeq"] = 2 + int(state.get("supplementRound", 0))
    elif pending and pending.get("kind") == "review":
        state["status"] = "WAITING_FOR_REVIEW"
        state["lastEventSeq"] = 3 + int(state.get("supplementRound", 0))


async def _report_workflow_result(
    run_id: str,
    result: dict[str, Any],
    resumed_from: str | None = None,
) -> dict[str, Any]:
    state = run_states.setdefault(run_id, {"runId": run_id})
    pending = workflow.pending_interrupt(result)
    if pending and pending.get("kind") == "supplement":
        await publish_checkpointed_event(
            run_id,
            "run.waiting_for_info",
            "WAITING_FOR_INFO",
            {"round": pending.get("round"), "questions": pending.get("questions", [])},
        )
        state["pendingKind"] = "supplement"
        return {"runId": run_id, "status": "WAITING_FOR_INFO"}

    detection = result.get("detection")
    if detection is not None and resumed_from != "review":
        await publish_checkpointed_event(
            run_id,
            "step.completed",
            "RUNNING",
            {
                "step": "readonly_tools",
                "detection": detection,
                "toolCalls": result.get("toolCalls", []),
            },
        )
        state.update({"detection": detection, "toolCalls": result.get("toolCalls", [])})

    if pending and pending.get("kind") == "review":
        await publish_checkpointed_event(
            run_id,
            "run.waiting_for_review",
            "WAITING_FOR_REVIEW",
            {
                "draft": result.get("draft", {}),
                "allowedDecisions": pending.get("allowedDecisions", []),
                "editableFields": pending.get("editableFields", []),
            },
        )
        state.update({"draft": result.get("draft"), "pendingKind": "review"})
        return {"runId": run_id, "status": "WAITING_FOR_REVIEW"}

    final_status = result.get("status")
    if final_status not in {"COMPLETED", "PARTIAL", "RETURNED", "FAILED", "CANCELLED"}:
        raise RuntimeError("Workflow ended without a supported final status")
    payload = {"draft": result.get("draft", {}), "review": result.get("review", {})}
    if final_status == "FAILED":
        payload["errorCode"] = result.get("detection", {}).get("errorCode", "WORKFLOW_FAILED")
    await publish_checkpointed_event(run_id, "run.finished", final_status, payload)
    state.update(
        {
            "status": final_status,
            "draft": result.get("draft"),
            "review": result.get("review"),
            "pendingKind": None,
        }
    )
    try:
        await workflow.delete_workflow_state(run_id)
    except Exception:
        logger.warning("Finalized workflow checkpoint cleanup failed for %s", run_id, exc_info=True)
    return {"runId": run_id, "status": final_status}


async def _resume_suspended_run(
    run_id: str,
    expected_kind: str,
    resume_value: dict[str, Any],
    expected_round: int | None = None,
) -> dict[str, Any]:
    lock = run_locks.setdefault(run_id, asyncio.Lock())
    async with lock:
        try:
            snapshot = await workflow.get_workflow_state(run_id)
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail="Workflow checkpoint is unavailable") from exc
        if not snapshot.values:
            current = run_states.get(run_id)
            if current and current.get("status") in {
                "COMPLETED", "PARTIAL", "RETURNED", "FAILED", "CANCELLED",
            }:
                return {"runId": run_id, "status": current["status"], "idempotent": True}
            raise HTTPException(status_code=404, detail="Run checkpoint not found")
        pending = _interrupt_from_snapshot(snapshot)
        if pending is None:
            state = snapshot.values
            if state.get("status") in {"COMPLETED", "PARTIAL", "RETURNED", "FAILED", "CANCELLED"}:
                return {"runId": run_id, "status": state["status"], "idempotent": True}
            raise HTTPException(status_code=409, detail="Run is not paused for input")
        if pending.get("kind") != expected_kind:
            raise HTTPException(status_code=409, detail="Run is paused at a different workflow step")
        if expected_round is not None and pending.get("round") != expected_round:
            raise HTTPException(status_code=409, detail="Supplement round does not match current checkpoint")
        resumed = await workflow.resume_workflow(run_id, resume_value)
        return await _report_workflow_result(run_id, resumed, expected_kind)


async def execute_run(request: RunRequest) -> None:
    run_id = request.runId
    state = run_states[run_id]
    state.update({"status": "RUNNING", "lastEventSeq": 0})
    try:
        await publish_event(
            run_id,
            1,
            "run.started",
            "RUNNING",
            {"step": "validate_input"},
        )
        state.update({"lastEventSeq": 1})

        workflow_result = await workflow.run_workflow(
            run_id,
            request.caseId,
            request.ownerId,
            request.content,
            request.model,
        )
        await _report_workflow_result(run_id, workflow_result)
    except Exception as exc:
        state.update(
            {
                "status": "CALLBACK_FAILED",
                "errorCode": "EVENT_DELIVERY_FAILED",
                "lastErrorType": type(exc).__name__,
            }
        )
        logger.exception("Agent run event delivery failed for %s", run_id)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/internal/v1/runs", status_code=202)
async def start_run(
    request: RunRequest,
    background_tasks: BackgroundTasks,
    x_agent_service_token: str | None = Header(default=None),
) -> dict[str, str]:
    verify_service_key(x_agent_service_token)
    current = run_states.get(request.runId)
    if current is None:
        try:
            snapshot = await workflow.get_workflow_state(request.runId)
            if snapshot.values:
                current = dict(snapshot.values)
                current["runId"] = request.runId
                _restore_run_status(current, _interrupt_from_snapshot(snapshot))
                run_states[request.runId] = current
        except RuntimeError:
            current = None
    input_hash = hashlib.sha256(request.content.encode("utf-8")).hexdigest()
    if current is not None and (
        current.get("caseId") != request.caseId
        or current.get("ownerId") != request.ownerId
        or current.get("inputHash") != input_hash
    ):
        raise HTTPException(status_code=409, detail="Run id conflicts with existing input")
    if current is None:
        run_states[request.runId] = {
            "runId": request.runId,
            "caseId": request.caseId,
            "ownerId": request.ownerId,
            "inputHash": input_hash,
            "status": "QUEUED",
            "lastEventSeq": 0,
        }
        background_tasks.add_task(execute_run, request)
        current_status = "QUEUED"
    else:
        current_status = str(current["status"])
    return {"runId": request.runId, "status": current_status}


@app.post("/internal/v1/runs/{run_id}/supplement", status_code=202)
async def supplement_run(
    run_id: str,
    request: SupplementRequest,
    x_agent_service_token: str | None = Header(default=None),
) -> dict[str, Any]:
    verify_service_key(x_agent_service_token)
    return await _resume_suspended_run(
        run_id,
        "supplement",
        {"answers": request.answers},
        request.round,
    )


@app.post("/internal/v1/runs/{run_id}/review", status_code=202)
async def review_run(
    run_id: str,
    request: ReviewRequest,
    x_agent_service_token: str | None = Header(default=None),
) -> dict[str, Any]:
    verify_service_key(x_agent_service_token)
    return await _resume_suspended_run(
        run_id,
        "review",
        {
            "decision": request.decision,
            "reviewerId": request.reviewerId,
            "comment": request.comment,
            "edits": (
                request.edits.model_dump(exclude_unset=True, exclude_none=True)
                if request.edits is not None
                else {}
            ),
        },
    )


@app.get("/internal/v1/runs/{run_id}")
async def get_run(
    run_id: str,
    x_agent_service_token: str | None = Header(default=None),
) -> dict[str, Any]:
    verify_service_key(x_agent_service_token)
    state = run_states.get(run_id)
    if state is None:
        try:
            snapshot = await workflow.get_workflow_state(run_id)
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail="Workflow checkpoint is unavailable") from exc
        if not snapshot.values:
            raise HTTPException(status_code=404, detail="Run not found")
        state = dict(snapshot.values)
        state["runId"] = run_id
        _restore_run_status(state, _interrupt_from_snapshot(snapshot))
        run_states[run_id] = state
    return dict(state)
