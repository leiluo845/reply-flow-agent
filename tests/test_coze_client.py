from __future__ import annotations

import json
from pathlib import Path

import pytest
import requests

from replyflow.config import AppSettings
from replyflow.coze_client import CozeClient, CozeError


class FakeResponse:
    def __init__(self, status_code: int = 200, payload=None, text: str = "", headers=None):
        self.status_code = status_code
        self._payload = payload
        self._text = text or (json.dumps(payload) if payload is not None else "")
        self.headers = headers or {}

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload

    @property
    def text(self) -> str:
        return self._text


class FakeSession:
    def __init__(self, response=None, error: Exception | None = None):
        self.response = response
        self.error = error
        self.calls: list[dict] = []

    def post(self, url, *, headers, json, timeout):
        self.calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        if self.error:
            raise self.error
        return self.response


def configured_settings() -> AppSettings:
    return AppSettings(
        coze_api_token="secret-token",
        coze_workflow_id="workflow-001",
        coze_workflow_version="v1",
        coze_timeout_seconds=7,
    )


def test_unconfigured_client_fails_without_http_call(tmp_path: Path) -> None:
    session = FakeSession()
    client = CozeClient(AppSettings(), session=session)

    with pytest.raises(CozeError) as error:
        client.analyze(subject="Hi", body="Where is my order?")

    assert error.value.code == "COZE_NOT_CONFIGURED"
    assert session.calls == []


def test_analyze_parses_common_coze_output_wrapper_and_limits_inputs() -> None:
    session = FakeSession(
        FakeResponse(
            payload={
                "code": 0,
                "request_id": "req-analyze-1",
                "data": {"output": json.dumps({"is_buyer_message": True, "intent": "shipping_status", "order_id": "ORD-1001", "missing_fields": [], "confidence": 0.94})},
            }
        )
    )
    client = CozeClient(configured_settings(), session=session)

    result = client.analyze(subject="S" * 500, body="B" * 9000, order_context_id="ORD-1001")

    assert result.intent == "shipping_status"
    assert result.confidence == 0.94
    call = session.calls[0]
    assert call["url"] == "https://api.coze.cn/v1/workflow/run"
    assert call["headers"]["Authorization"] == "Bearer secret-token"
    assert call["json"]["workflow_id"] == "workflow-001"
    parameters = json.loads(call["json"]["parameters"]["payload_json"])
    assert len(parameters["subject"]) == 300
    assert len(parameters["body"]) == 8000
    assert parameters["task_type"] == "analyze"
    assert "expected" not in json.dumps(call["json"]).lower()


def test_draft_parses_direct_output_and_does_not_add_control_actions() -> None:
    session = FakeSession(
        FakeResponse(
            payload={
                "code": 0,
                "data": {"draft_subject": "Re: Delivery", "draft_body": "Hello, we are checking the latest verified status.", "used_basis": ["basis-logistics-v1#delivery-status"], "uncertainties": []},
            }
        )
    )
    client = CozeClient(configured_settings(), session=session)

    result = client.draft(
        email_json={"subject": "Where is my order?", "body": "ORD-1001"},
        verified_facts_json={"order_id": "ORD-1001", "shipping_status": "In transit"},
        reply_basis_json={"results": [{"basis_id": "basis-logistics-v1", "section_id": "delivery-status"}]},
        risk_context_json={"risk_level": "R0", "ai_level": "L1"},
    )

    assert result.draft_subject == "Re: Delivery"
    assert "send" not in result.model_dump_json().lower()
    assert json.loads(session.calls[0]["json"]["parameters"]["payload_json"])["task_type"] == "draft"


def test_official_style_data_string_and_debug_url_are_supported() -> None:
    output = {"is_buyer_message": True, "intent": "shipping_status", "order_id": "ORD-1001", "missing_fields": [], "confidence": 0.9}
    session = FakeSession(
        FakeResponse(
            payload={
                "code": 0,
                "data": json.dumps({"output": json.dumps(output)}),
                "debug_url": "https://www.coze.cn/work_flow?execute_id=execute-123&workflow_id=workflow-001",
            }
        )
    )
    client = CozeClient(configured_settings(), session=session)

    result = client._run("analyze", {"subject": "Hi", "body": "ORD-1001"})

    assert result.request_id == "execute-123"
    assert result.output == output


@pytest.mark.parametrize(
    ("response", "expected_code"),
    [
        (FakeResponse(401, {"code": 401, "msg": "unauthorized"}), "COZE_AUTH_ERROR"),
        (FakeResponse(403, {"code": 403, "msg": "forbidden"}), "COZE_AUTH_ERROR"),
        (FakeResponse(429, {"code": 429, "msg": "too many requests"}), "COZE_RATE_LIMITED"),
        (FakeResponse(500, {"code": 500, "msg": "server error"}), "COZE_HTTP_500"),
        (FakeResponse(200, ValueError("not json"), text="not-json"), "COZE_NON_JSON"),
        (FakeResponse(200, {"code": 0, "data": {"output": "not an object"}}), "MODEL_OUTPUT_INVALID"),
    ],
)
def test_coze_failures_are_structured(response: FakeResponse, expected_code: str) -> None:
    client = CozeClient(configured_settings(), session=FakeSession(response))

    with pytest.raises(CozeError) as error:
        client.analyze(subject="Hi", body="Hello")

    assert error.value.code == expected_code


def test_timeout_is_retryable_and_token_is_not_in_error_message() -> None:
    client = CozeClient(configured_settings(), session=FakeSession(error=requests.Timeout("network timeout")))

    with pytest.raises(CozeError) as error:
        client.analyze(subject="Hi", body="Hello")

    assert error.value.code == "COZE_TIMEOUT"
    assert error.value.retryable is True
    assert "secret-token" not in str(error.value)


def test_schema_extra_fields_are_rejected() -> None:
    session = FakeSession(
        FakeResponse(
            payload={
                "code": 0,
                "data": {"output": {"is_buyer_message": True, "intent": "other_buyer_support", "confidence": 0.8, "unexpected": "x"}},
            }
        )
    )
    client = CozeClient(configured_settings(), session=session)

    with pytest.raises(CozeError) as error:
        client.analyze(subject="Hi", body="Hello")

    assert error.value.code == "MODEL_OUTPUT_INVALID"


def test_analyze_rejects_unknown_intent_enum() -> None:
    session = FakeSession(
        FakeResponse(
            payload={
                "code": 0,
                "data": {"output": {"is_buyer_message": True, "intent": "other", "confidence": 0.8}},
            }
        )
    )
    client = CozeClient(configured_settings(), session=session)

    with pytest.raises(CozeError) as error:
        client.analyze(subject="Wrong item", body="Order RF-9999")

    assert error.value.code == "MODEL_OUTPUT_INVALID"
