import re
import hashlib
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from agent_service.mcp_client import call_readonly_tools


_INFORMATION_FIELDS = {
    "contact_channel": {
        "question": "对方通过什么渠道联系你？",
        "pattern": re.compile(r"微信|QQ|短信|电话|来电|邮件|网站|网页|社交软件", re.IGNORECASE),
    },
    "claimed_identity": {
        "question": "对方自称是什么身份或机构？",
        "pattern": re.compile(r"冒充|自称|客服|公安|警察|银行|快递|平台|同事|领导|朋友|公检法|工作人员"),
    },
    "requested_action": {
        "question": "对方要求你采取什么操作？",
        "pattern": re.compile(r"转账|汇款|付款|支付|充值|验证码|点击|链接|下载|投资|刷单|贷款|转移|屏幕共享|密码|银行卡|缴费|退款|解冻|提现|扫码"),
    },
    "event_time": {
        "question": "事情大约在什么时间发生？",
        "pattern": re.compile(r"\d{4}年|\d{1,2}月\d{1,2}日|今天|昨天|前天|昨晚|近日|近期|刚才|上午|下午|晚上|凌晨|中午|\d{1,2}点"),
    },
}
_APP_CHANNEL_PATTERN = re.compile(r"(?:通过|来自|在|用)(?:某)?APP(?:联系|收到|沟通|发来)", re.IGNORECASE)
_FIELD_NEGATIONS = {
    "contact_channel": re.compile(r"(?:不是|并非)(?:通过)?$"),
    "claimed_identity": re.compile(
        r"(?:对方)?(?:不是|并非|未冒充|没有冒充|不自称|没有自称|没有人自称|并未自称|未自称)"
        r"(?:[^\s，。；！？]{0,10})$"
    ),
    "requested_action": re.compile(
        r"(?:未要求|没有要求|并未要求|不要求|无需|不需要|没有让|未让|不让|"
        r"未索要|没有索要|不索要|没有点击|未点击|不点击)"
        r"(?:[^\s，。；！？]{0,10})$"
    ),
}
_MAX_SUPPLEMENT_ROUNDS = 2
_EDITABLE_DRAFT_FIELDS = {
    "summary",
    "missingInformation",
    "suggestedChecks",
    "uncertaintyNotes",
}
_checkpointer = None


class AgentState(TypedDict, total=False):
    runId: str
    caseId: int
    ownerId: int
    content: str
    model: str | None
    detection: dict[str, Any]
    knowledgeSearch: dict[str, Any]
    toolCalls: list[dict[str, Any]]
    draft: dict[str, Any]
    missingInformation: list[dict[str, str]]
    supplementRound: int
    supplementalInformation: dict[str, str]
    review: dict[str, Any]
    status: str


async def run_readonly_tools(state: AgentState) -> dict[str, Any]:
    return await call_readonly_tools(state["content"], state.get("model"))


def find_missing_information(content: str) -> list[dict[str, str]]:
    return [
        {"field": field, "question": definition["question"]}
        for field, definition in _INFORMATION_FIELDS.items()
        if not _has_field_evidence(field, content, definition["pattern"])
    ]


def _has_field_evidence(field: str, content: str, pattern: re.Pattern[str]) -> bool:
    if field == "contact_channel" and _APP_CHANNEL_PATTERN.search(content):
        return True
    negation = _FIELD_NEGATIONS.get(field)
    for match in pattern.finditer(content):
        if negation:
            preceding = re.split(r"[，。；！？\n]", content[:match.start()])[-1][-20:]
            if negation.search(preceding + match.group(0)):
                continue
        return True
    return False


def check_missing_information(state: AgentState) -> dict[str, Any]:
    return {"missingInformation": find_missing_information(state.get("content", ""))}


def route_after_information_check(state: AgentState) -> str:
    if state.get("missingInformation") and state.get("supplementRound", 0) < _MAX_SUPPLEMENT_ROUNDS:
        return "request_information"
    return "run_tools"


def request_information(state: AgentState) -> dict[str, Any]:
    missing_information = state.get("missingInformation", [])
    response = interrupt(
        {
            "kind": "supplement",
            "round": state.get("supplementRound", 0) + 1,
            "questions": missing_information,
        }
    )
    if not isinstance(response, dict) or not isinstance(response.get("answers"), dict):
        raise ValueError("Supplement response must contain an answers object")
    answers = response["answers"]
    allowed_fields = set(_INFORMATION_FIELDS)
    if not answers or not set(answers).issubset(allowed_fields):
        raise ValueError("Supplement contains unknown fields or no answers")
    normalized_answers: dict[str, str] = {}
    for field, value in answers.items():
        if field not in {item["field"] for item in missing_information}:
            raise ValueError("Supplement field was not requested")
        if not isinstance(value, str) or not value.strip() or len(value) > 500:
            raise ValueError("Supplement values must contain 1 to 500 characters")
        normalized_answers[field] = value.strip()
    appended_information = "\n".join(
        f"{_INFORMATION_FIELDS[field]['question']}{value}"
        for field, value in normalized_answers.items()
    )
    content = state.get("content", "")
    updated_content = f"{content}\n补充信息：{appended_information}"
    all_supplements = dict(state.get("supplementalInformation", {}))
    all_supplements.update(normalized_answers)
    return {
        "content": updated_content,
        "supplementalInformation": all_supplements,
        "supplementRound": state.get("supplementRound", 0) + 1,
    }


def build_draft(state: AgentState) -> dict[str, Any]:
    detection = state["detection"]
    completed = detection.get("status") == "completed"
    knowledge_search = state.get("knowledgeSearch", {})
    citations = knowledge_search.get("results", [])
    uncertainty_notes = []
    if not completed:
        uncertainty_notes.append("检测服务调用失败，不能据此判断为低风险。")
    if knowledge_search.get("status") != "completed" or not citations:
        uncertainty_notes.append("知识检索当前不可用或未配置，因此没有可引用依据。")
    elif any(citation.get("excerptType") == "paraphrase" for citation in citations):
        uncertainty_notes.append("知识卡内容为来源摘要转述，不是来源原文引述；请审核者核对链接原文。")

    draft = {
        "caseId": state["caseId"],
        "runId": state["runId"],
        "status": "COMPLETED" if completed else "FAILED",
        "summary": (
            "文本检测已完成；当前结果只代表既有检测服务输出，不等同于完整人工研判。"
            if completed
            else "文本检测未成功，当前没有可用的风险结论。"
        ),
        "detection": detection,
        "citations": citations,
        "missingInformation": state.get("missingInformation", []),
        "suggestedChecks": [
            item["question"] for item in state.get("missingInformation", [])
        ],
        "uncertaintyNotes": uncertainty_notes,
    }
    return {"draft": draft}


def wait_for_review(state: AgentState) -> dict[str, Any]:
    review = interrupt(
        {
            "kind": "review",
            "draft": state["draft"],
            "allowedDecisions": ["approve", "modify", "return"],
            "editableFields": sorted(_EDITABLE_DRAFT_FIELDS),
        }
    )
    return {"review": review}


def validate_review_payload(review: Any) -> tuple[str, int, str, dict[str, Any]]:
    """Validate a review payload before it reaches the graph checkpoint."""
    if not isinstance(review, dict):
        raise ValueError("Review decision is missing")
    decision = review.get("decision")
    reviewer_id = review.get("reviewerId")
    comment = review.get("comment", "")
    edits = review.get("edits", {})
    if decision not in {"approve", "modify", "return"}:
        raise ValueError("Unsupported review decision")
    if not isinstance(reviewer_id, int) or reviewer_id <= 0:
        raise ValueError("reviewerId must be a positive integer")
    if not isinstance(comment, str) or len(comment) > 2000:
        raise ValueError("Review comment cannot exceed 2000 characters")
    if not isinstance(edits, dict) or not set(edits).issubset(_EDITABLE_DRAFT_FIELDS):
        raise ValueError("Review edits contain non-editable fields")
    if decision == "modify" and not edits:
        raise ValueError("Modify decision requires at least one allowed edit")
    if decision != "modify" and edits:
        raise ValueError("Edits are only accepted with a modify decision")
    for field, value in edits.items():
        if field == "summary":
            if not isinstance(value, str) or len(value) > 2000:
                raise ValueError("Edited summary cannot exceed 2000 characters")
        elif not isinstance(value, list) or len(value) > 20 or any(
            not isinstance(item, str) or not item.strip() or len(item) > 500
            for item in value
        ):
            raise ValueError(f"Edited {field} must be a list of up to 20 short strings")
    return decision, reviewer_id, comment, edits


def finalize_review(state: AgentState) -> dict[str, Any]:
    decision, reviewer_id, comment, edits = validate_review_payload(state.get("review"))

    draft = dict(state["draft"])
    draft.update(edits)
    draft["review"] = {
        "decision": decision,
        "reviewerId": reviewer_id,
        "comment": comment,
    }
    status = "RETURNED" if decision == "return" else (
        "COMPLETED" if state.get("detection", {}).get("status") == "completed" else "PARTIAL"
    )
    return {"draft": draft, "status": status}


builder = StateGraph(AgentState)
builder.add_node("check_missing_information", check_missing_information)
builder.add_node("request_information", request_information)
builder.add_node("readonly_tools", run_readonly_tools)
builder.add_node("build_draft", build_draft)
builder.add_node("wait_for_review", wait_for_review)
builder.add_node("finalize_review", finalize_review)
builder.add_edge(START, "check_missing_information")
builder.add_conditional_edges(
    "check_missing_information",
    route_after_information_check,
    {"request_information": "request_information", "run_tools": "readonly_tools"},
)
builder.add_edge("request_information", "check_missing_information")
builder.add_edge("readonly_tools", "build_draft")
builder.add_edge("build_draft", "wait_for_review")
builder.add_edge("wait_for_review", "finalize_review")
builder.add_edge("finalize_review", END)
agent_graph = builder.compile()


def configure_checkpointer(checkpointer) -> None:
    global _checkpointer, agent_graph
    _checkpointer = checkpointer
    agent_graph = builder.compile(checkpointer=checkpointer)


def _thread_config(run_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": run_id}}


async def run_workflow(
    run_id: str,
    case_id: int,
    owner_id: int,
    content: str,
    model: str | None = None,
) -> dict[str, Any]:
    if _checkpointer is None:
        raise RuntimeError("A persistent workflow checkpointer is not configured")
    return await agent_graph.ainvoke(
        {
            "runId": run_id,
            "caseId": case_id,
            "ownerId": owner_id,
            "content": content,
            "inputHash": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            "model": model,
            "supplementRound": 0,
            "supplementalInformation": {},
            "status": "RUNNING",
        },
        config=_thread_config(run_id),
    )


async def resume_workflow(run_id: str, resume_value: dict[str, Any]) -> dict[str, Any]:
    if _checkpointer is None:
        raise RuntimeError("A persistent workflow checkpointer is not configured")
    # Reject bad review payloads before LangGraph persists them into the checkpoint,
    # otherwise one malformed submission would block every later valid review.
    if isinstance(resume_value, dict) and "decision" in resume_value:
        validate_review_payload(resume_value)
    return await agent_graph.ainvoke(
        Command(resume=resume_value),
        config=_thread_config(run_id),
    )


async def get_workflow_state(run_id: str):
    if _checkpointer is None:
        raise RuntimeError("A persistent workflow checkpointer is not configured")
    return await agent_graph.aget_state(_thread_config(run_id))


async def delete_workflow_state(run_id: str) -> None:
    if _checkpointer is None:
        raise RuntimeError("A persistent workflow checkpointer is not configured")
    await _checkpointer.adelete_thread(run_id)


async def update_workflow_state(run_id: str, values: dict[str, Any]) -> None:
    if _checkpointer is None:
        raise RuntimeError("A persistent workflow checkpointer is not configured")
    await agent_graph.aupdate_state(_thread_config(run_id), values)


def pending_interrupt(result: dict[str, Any]) -> dict[str, Any] | None:
    interrupts = result.get("__interrupt__", ())
    if not interrupts:
        return None
    value = getattr(interrupts[0], "value", None)
    return value if isinstance(value, dict) else None
