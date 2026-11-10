import os
from typing import Any

import httpx


def _failed(code: str, detail: str) -> dict[str, Any]:
    return {
        "status": "failed",
        "riskScore": None,
        "riskLevel": "检测失败",
        "detail": detail,
        "errorCode": code,
    }


async def detect_text(
    content: str,
    model: str | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict[str, Any]:
    base_url = os.getenv("AI_SERVICE_URL", "http://ai-service:5000").rstrip("/")
    timeout = httpx.Timeout(
        connect=float(os.getenv("AI_SERVICE_CONNECT_TIMEOUT", "5")),
        read=float(os.getenv("AI_SERVICE_READ_TIMEOUT", "30")),
        write=5,
        pool=5,
    )
    payload: dict[str, str] = {"content": content}
    if model:
        payload["model"] = model

    try:
        async with httpx.AsyncClient(timeout=timeout, transport=transport) as client:
            response = await client.post(f"{base_url}/api/detect/text", json=payload)
            result = response.json()
    except httpx.TimeoutException:
        return _failed("UPSTREAM_TIMEOUT", "文本检测服务响应超时")
    except (httpx.RequestError, ValueError):
        return _failed("UPSTREAM_UNAVAILABLE", "文本检测服务不可用或返回格式无效")

    if not isinstance(result, dict):
        return _failed("UPSTREAM_INVALID_RESPONSE", "文本检测服务返回格式无效")
    if not response.is_success or result.get("error"):
        return _failed("UPSTREAM_DETECTION_ERROR", str(result.get("detail") or result.get("error") or "文本检测失败"))

    score = result.get("riskScore", result.get("risk_score"))
    level = result.get("riskLevel", result.get("risk_level"))
    if not isinstance(score, (int, float)) or isinstance(score, bool) or not isinstance(level, str):
        return _failed("UPSTREAM_INVALID_RESPONSE", "文本检测服务缺少有效风险字段")

    normalized = dict(result)
    normalized["status"] = "completed"
    normalized["riskScore"] = int(score)
    normalized["riskLevel"] = level
    return normalized
