import hashlib
import os
import time
from typing import Any

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client


ALLOWED_TOOL_NAMES = frozenset({"detect_text", "search_knowledge"})


def _input_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


async def _call_tool(
    client: Client,
    tool_name: str,
    arguments: dict[str, Any],
    query_hash: str,
    tool_trace: list[dict[str, Any]],
) -> dict[str, Any]:
    started_at = time.perf_counter()
    try:
        result = await client.call_tool(tool_name, arguments, read_timeout_seconds=35)
        if result.is_error:
            raise RuntimeError("MCP tool returned an error")
        output = result.structured_content
        if not isinstance(output, dict):
            raise ValueError("MCP tool returned no structured object")
        tool_trace.append(
            {
                "tool": tool_name,
                "inputHash": query_hash,
                "status": "completed",
                "latencyMs": int((time.perf_counter() - started_at) * 1000),
            }
        )
        return output
    except Exception as exc:
        tool_trace.append(
            {
                "tool": tool_name,
                "inputHash": query_hash,
                "status": "failed",
                "errorCode": type(exc).__name__,
                "latencyMs": int((time.perf_counter() - started_at) * 1000),
            }
        )
        raise


async def call_readonly_tools(
    content: str,
    model: str | None = None,
    transport: httpx2.AsyncBaseTransport | None = None,
) -> dict[str, Any]:
    tool_trace: list[dict[str, Any]] = []
    query_hash = _input_hash(content)
    failed_detection = {
        "status": "failed",
        "riskScore": None,
        "riskLevel": "检测失败",
        "detail": "Agent 工具调用失败，未形成风险结论。",
        "errorCode": "MCP_UNAVAILABLE",
    }
    unavailable_search = {
        "status": "not_configured",
        "query": "",
        "results": [],
        "message": "Knowledge retrieval is unavailable; no supporting source was found.",
    }
    token = os.getenv("AGENT_SERVICE_TOKEN", "")
    base_url = os.getenv("MCP_SERVICE_URL", "http://127.0.0.1:8001").rstrip("/")
    if not token:
        tool_trace.append(
            {
                "tool": "mcp_connect",
                "inputHash": query_hash,
                "status": "failed",
                "errorCode": "MCP_AUTH_NOT_CONFIGURED",
                "latencyMs": 0,
            }
        )
        return {
            "detection": {**failed_detection, "errorCode": "MCP_AUTH_NOT_CONFIGURED"},
            "knowledgeSearch": unavailable_search,
            "toolCalls": tool_trace,
        }

    timeout = httpx2.Timeout(connect=5, read=35, write=5, pool=5)
    try:
        async with httpx2.AsyncClient(
            timeout=timeout,
            headers={"X-Agent-Service-Token": token},
            transport=transport,
        ) as http_client:
            transport = streamable_http_client(
                f"{base_url}/mcp/",
                http_client=http_client,
            )
            async with Client(transport) as client:
                advertised_tools = {tool.name for tool in (await client.list_tools()).tools}
                if advertised_tools != ALLOWED_TOOL_NAMES:
                    raise RuntimeError("MCP tool allowlist does not match the configured contract")
                try:
                    detection = await _call_tool(
                        client,
                        "detect_text",
                        {"content": content, "model": model},
                        query_hash,
                        tool_trace,
                    )
                except Exception:
                    return {
                        "detection": failed_detection,
                        "knowledgeSearch": unavailable_search,
                        "toolCalls": tool_trace,
                    }
                try:
                    knowledge_search = await _call_tool(
                        client,
                        "search_knowledge",
                        {"query": content, "top_k": 5},
                        query_hash,
                        tool_trace,
                    )
                except Exception:
                    knowledge_search = unavailable_search
    except Exception as exc:
        tool_trace.append(
            {
                "tool": "mcp_connect",
                "inputHash": query_hash,
                "status": "failed",
                "errorCode": type(exc).__name__,
                "latencyMs": 0,
            }
        )
        return {
            "detection": failed_detection,
            "knowledgeSearch": unavailable_search,
            "toolCalls": tool_trace,
        }

    return {
        "detection": detection,
        "knowledgeSearch": knowledge_search,
        "toolCalls": tool_trace,
    }
