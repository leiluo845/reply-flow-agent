from __future__ import annotations

import json
from typing import Any, Protocol

import requests
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from .config import AppSettings


class HttpResponse(Protocol):
    status_code: int

    def json(self) -> Any: ...

    @property
    def text(self) -> str: ...


class HttpSession(Protocol):
    def post(self, url: str, *, headers: dict[str, str], json: dict[str, Any], timeout: int) -> HttpResponse: ...


class InteractiveModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AnalyzeOutput(InteractiveModel):
    is_buyer_message: bool
    intent: str
    order_id: str | None = None
    missing_fields: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)


class DraftOutput(InteractiveModel):
    draft_subject: str = Field(min_length=1)
    draft_body: str = Field(min_length=1)
    used_basis: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)


class CozeError(RuntimeError):
    def __init__(self, code: str, message: str, *, status_code: int | None = None, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.retryable = retryable


class CozeRunResult(InteractiveModel):
    task_type: str
    output: dict[str, Any]
    request_id: str | None = None
    workflow_id: str
    workflow_version: str | None = None


def _safe_message(value: object, *, limit: int = 240) -> str:
    text = str(value).replace("\r", " ").replace("\n", " ").strip()
    return text[:limit]


def _parse_json_value(value: Any) -> Any:
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return value
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return value
    return value


def _extract_request_id(payload: dict[str, Any], response: HttpResponse) -> str | None:
    for key in ("request_id", "execute_id", "run_id"):
        if payload.get(key):
            return str(payload[key])
    headers = getattr(response, "headers", {}) or {}
    for key in ("x-request-id", "x-execute-id"):
        if headers.get(key):
            return str(headers[key])
    return None


def _extract_output(payload: Any) -> Any:
    """Accept common Coze response wrappers without assuming one UI-specific shape."""
    payload = _parse_json_value(payload)
    if isinstance(payload, dict):
        for key in ("output", "result", "data"):
            if key in payload:
                candidate = _parse_json_value(payload[key])
                if candidate is not payload:
                    try:
                        return _extract_output(candidate)
                    except CozeError:
                        pass
        for key in ("content", "content_str", "text"):
            if key in payload:
                candidate = _parse_json_value(payload[key])
                if isinstance(candidate, (dict, list)):
                    return candidate
        if any(key in payload for key in ("draft_subject", "draft_body", "is_buyer_message", "intent")):
            return payload
        # Some workflow APIs return a one-key output map, e.g. {"analyze_result": "{...}"}.
        if len(payload) == 1:
            return _extract_output(next(iter(payload.values())))
    if isinstance(payload, list) and len(payload) == 1:
        return _extract_output(payload[0])
    raise CozeError("MODEL_OUTPUT_INVALID", "Coze response did not contain a structured workflow output.")


class CozeClient:
    def __init__(self, settings: AppSettings, *, session: HttpSession | None = None):
        self.settings = settings
        self.session = session or requests.Session()

    @property
    def configured(self) -> bool:
        return self.settings.interactive_mode_configured

    def _run(self, task_type: str, parameters: dict[str, Any]) -> CozeRunResult:
        if not self.settings.coze_api_token or not self.settings.coze_workflow_id:
            raise CozeError(
                "COZE_NOT_CONFIGURED",
                "Interactive Mode is not configured. Add a Coze PAT and published Workflow ID, or switch to Demo Mode.",
            )
        payload: dict[str, Any] = {
            "workflow_id": self.settings.coze_workflow_id,
            "parameters": {"task_type": task_type, **parameters},
        }
        if self.settings.coze_workflow_version:
            payload["workflow_version"] = self.settings.coze_workflow_version
        headers = {
            "Authorization": f"Bearer {self.settings.coze_api_token.get_secret_value()}",
            "Content-Type": "application/json",
        }
        endpoint = f"{self.settings.coze_api_base_url}/workflow/run"
        try:
            response = self.session.post(
                endpoint,
                headers=headers,
                json=payload,
                timeout=self.settings.coze_timeout_seconds,
            )
        except requests.Timeout as exc:
            raise CozeError("COZE_TIMEOUT", "Coze Workflow timed out. Switch to Demo Mode or retry.", retryable=True) from exc
        except requests.RequestException as exc:
            raise CozeError("COZE_NETWORK_ERROR", "Coze Workflow could not be reached.", retryable=True) from exc

        status = int(response.status_code)
        if status in {401, 403}:
            raise CozeError("COZE_AUTH_ERROR", "Coze rejected the PAT or Workflow permission.", status_code=status)
        if status == 429:
            raise CozeError("COZE_RATE_LIMITED", "Coze rate-limited the request. Retry later or switch to Demo Mode.", status_code=status, retryable=True)
        if status >= 400:
            try:
                error_payload = response.json()
            except ValueError:
                error_payload = response.text
            message = error_payload.get("msg") if isinstance(error_payload, dict) else error_payload
            raise CozeError(
                f"COZE_HTTP_{status}",
                f"Coze Workflow returned HTTP {status}: {_safe_message(message)}",
                status_code=status,
            )
        try:
            response_payload = response.json()
        except ValueError as exc:
            raise CozeError("COZE_NON_JSON", "Coze returned a non-JSON response.") from exc
        if isinstance(response_payload, dict) and response_payload.get("code") not in (None, 0, "0"):
            raise CozeError(
                "COZE_API_ERROR",
                f"Coze Workflow returned an API error: {_safe_message(response_payload.get('msg', 'unknown error'))}",
            )
        output = _extract_output(response_payload)
        if not isinstance(output, dict):
            raise CozeError("MODEL_OUTPUT_INVALID", "Coze output must be a JSON object.")
        return CozeRunResult(
            task_type=task_type,
            output=output,
            request_id=_extract_request_id(response_payload if isinstance(response_payload, dict) else {}, response),
            workflow_id=self.settings.coze_workflow_id,
            workflow_version=self.settings.coze_workflow_version,
        )

    def analyze(self, *, subject: str, body: str, order_context_id: str | None = None) -> AnalyzeOutput:
        run = self._run(
            "analyze",
            {
                "subject": subject[:300],
                "body": body[:8000],
                "order_context_id": order_context_id,
            },
        )
        try:
            return AnalyzeOutput.model_validate(run.output)
        except ValidationError as exc:
            raise CozeError("MODEL_OUTPUT_INVALID", "Coze Analyze output did not match the required schema.") from exc

    def draft(
        self,
        *,
        email_json: dict[str, Any],
        verified_facts_json: dict[str, Any],
        reply_basis_json: dict[str, Any],
        risk_context_json: dict[str, Any],
    ) -> DraftOutput:
        run = self._run(
            "draft",
            {
                "email_json": email_json,
                "verified_facts_json": verified_facts_json,
                "reply_basis_json": reply_basis_json,
                "risk_context_json": risk_context_json,
            },
        )
        try:
            return DraftOutput.model_validate(run.output)
        except ValidationError as exc:
            raise CozeError("MODEL_OUTPUT_INVALID", "Coze Draft output did not match the required schema.") from exc
