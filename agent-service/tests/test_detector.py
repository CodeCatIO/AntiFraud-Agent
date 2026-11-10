import asyncio

import httpx

from agent_service.detector import detect_text


def run(coroutine):
    return asyncio.run(coroutine)


def test_detect_text_normalizes_success_response(monkeypatch):
    monkeypatch.setenv("AI_SERVICE_URL", "http://ai.test")

    def respond(request):
        assert request.url.path == "/api/detect/text"
        assert request.read()
        return httpx.Response(
            200,
            json={"riskScore": 76, "riskLevel": "高风险", "detail": "命中风险模式"},
        )

    result = run(detect_text("测试内容", transport=httpx.MockTransport(respond)))

    assert result["status"] == "completed"
    assert result["riskScore"] == 76
    assert result["riskLevel"] == "高风险"


def test_detect_text_treats_flask_error_score_zero_as_failure(monkeypatch):
    monkeypatch.setenv("AI_SERVICE_URL", "http://ai.test")

    def respond(_request):
        return httpx.Response(
            400,
            json={
                "error": "invalid input",
                "riskScore": 0,
                "riskLevel": "检测失败",
                "detail": "invalid input",
            },
        )

    result = run(detect_text("测试内容", transport=httpx.MockTransport(respond)))

    assert result["status"] == "failed"
    assert result["riskScore"] is None
    assert result["errorCode"] == "UPSTREAM_DETECTION_ERROR"


def test_detect_text_rejects_missing_risk_fields(monkeypatch):
    monkeypatch.setenv("AI_SERVICE_URL", "http://ai.test")

    def respond(_request):
        return httpx.Response(200, json={"detail": "incomplete"})

    result = run(detect_text("测试内容", transport=httpx.MockTransport(respond)))

    assert result["status"] == "failed"
    assert result["riskScore"] is None
    assert result["errorCode"] == "UPSTREAM_INVALID_RESPONSE"


def test_detect_text_normalizes_upstream_timeout(monkeypatch):
    monkeypatch.setenv("AI_SERVICE_URL", "http://ai.test")

    def respond(request):
        raise httpx.ReadTimeout("upstream timeout", request=request)

    result = run(detect_text("测试内容", transport=httpx.MockTransport(respond)))

    assert result["status"] == "failed"
    assert result["riskScore"] is None
    assert result["errorCode"] == "UPSTREAM_TIMEOUT"
