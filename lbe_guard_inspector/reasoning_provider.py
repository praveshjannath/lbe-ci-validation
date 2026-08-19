"""Provider-neutral OpenAI-compatible backend for bounded LBE reasoning."""
from __future__ import annotations

import json
import http.client
import socket
import threading
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any, Mapping, Protocol

from .reasoning_contracts import (
    ExplanationRequest,
    ExplanationResult,
    ReasoningPlan,
    ReasoningRequest,
)


@dataclass(frozen=True)
class ProviderConfig:
    endpoint: str
    model: str
    timeout_seconds: float
    api_key: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.endpoint, str) or not self.endpoint.strip():
            raise ValueError("provider endpoint must be a non-empty string")
        if not isinstance(self.model, str) or not self.model.strip():
            raise ValueError("provider model must be a non-empty string")
        if not isinstance(self.timeout_seconds, (int, float)) or self.timeout_seconds <= 0:
            raise ValueError("provider timeout_seconds must be greater than zero")


class ProviderError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class JsonTransport(Protocol):
    supports_cancellation: bool

    def post_json(
        self,
        *,
        endpoint: str,
        payload: Mapping[str, Any],
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> Mapping[str, Any]: ...

    def cancel(self) -> None: ...


class UrllibJsonTransport:
    supports_cancellation = False  # http.client/urlib cannot be reliably cancelled from another thread

    def __init__(self) -> None:
        pass

    def cancel(self) -> None:
        """Request cancellation - not supported by urllib transport."""
        raise ProviderError("PROVIDER_CANCELLED", "live provider cancellation is not available for this transport")

    def post_json(
        self,
        *,
        endpoint: str,
        payload: Mapping[str, Any],
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> Mapping[str, Any]:
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=dict(headers),
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else str(exc)
            raise ProviderError("PROVIDER_HTTP_ERROR", f"HTTP {exc.code}: {detail}") from exc
        except (TimeoutError, socket.timeout) as exc:
            raise ProviderError("PROVIDER_TIMEOUT", str(exc) or "provider request timed out") from exc
        except urllib.error.URLError as exc:
            reason = getattr(exc, "reason", exc)
            if isinstance(reason, (TimeoutError, socket.timeout)):
                raise ProviderError("PROVIDER_TIMEOUT", str(reason) or "provider request timed out") from exc
            raise ProviderError("PROVIDER_TRANSPORT_ERROR", str(reason)) from exc
        except OSError as exc:
            raise ProviderError("PROVIDER_TRANSPORT_ERROR", str(exc)) from exc

        if not raw:
            raise ProviderError("PROVIDER_RESPONSE_ERROR", "provider returned an empty response body")
        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProviderError("PROVIDER_RESPONSE_ERROR", "provider returned invalid JSON") from exc
        if not isinstance(decoded, Mapping):
            raise ProviderError("PROVIDER_RESPONSE_ERROR", "provider response must be a JSON object")
        return decoded


class OpenAICompatibleReasoningBackend:
    def __init__(self, *, config: ProviderConfig, transport: JsonTransport | None = None) -> None:
        self._config = config
        self._transport = transport or UrllibJsonTransport()

    def plan(self, request: ReasoningRequest) -> ReasoningPlan:
        result = self._complete(
            "planning",
            _PLANNING_SYSTEM_PROMPT,
            _PLANNING_OUTPUT_CONTRACT,
            _PLANNING_JSON_SCHEMA,
            _planning_input_payload(request),
        )
        try:
            plan = ReasoningPlan.from_mapping(result)
            _require_relative_evidence_paths(plan)
            return plan
        except (TypeError, ValueError) as exc:
            raise ProviderError("PROVIDER_SCHEMA_ERROR", f"invalid planning response: {exc}") from exc

    def explain(self, request: ExplanationRequest) -> ExplanationResult:
        result = self._complete(
            "explanation",
            _EXPLANATION_SYSTEM_PROMPT,
            _EXPLANATION_OUTPUT_CONTRACT,
            _EXPLANATION_JSON_SCHEMA,
            asdict(request),
        )
        try:
            return ExplanationResult.from_mapping(result)
        except (TypeError, ValueError) as exc:
            raise ProviderError("PROVIDER_SCHEMA_ERROR", f"invalid explanation response: {exc}") from exc

    def _complete(
        self,
        stage: str,
        system_prompt: str,
        output_contract: Mapping[str, Any],
        output_schema: Mapping[str, Any],
        input_payload: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        payload = {
            "model": self._config.model.strip(),
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "stage": stage,
                            "output_contract": output_contract,
                            "input": input_payload,
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                },
            ],
            "temperature": 0,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": f"lbe_{stage}_response",
                    "strict": True,
                    "schema": output_schema,
                },
            },
        }
        headers = {"Content-Type": "application/json"}
        if self._config.api_key:
            headers["Authorization"] = f"Bearer {self._config.api_key}"
        response = self._transport.post_json(
            endpoint=self._config.endpoint.strip(),
            payload=payload,
            headers=headers,
            timeout_seconds=float(self._config.timeout_seconds),
        )
        content = _extract_message_content(response)
        try:
            decoded = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ProviderError("PROVIDER_RESPONSE_ERROR", "provider message content is not valid JSON") from exc
        if not isinstance(decoded, Mapping):
            raise ProviderError("PROVIDER_RESPONSE_ERROR", "provider message content must decode to an object")
        return decoded


def _planning_input_payload(request: ReasoningRequest) -> Mapping[str, Any]:
    payload = asdict(request)
    identity = dict(payload.get("workspace_identity", {}))
    identity.pop("target_project_root", None)
    payload["workspace_identity"] = identity
    return payload


def _require_relative_evidence_paths(plan: ReasoningPlan) -> None:
    for item in plan.evidence_requests:
        path = item.path.strip()
        if (
            not path
            or PureWindowsPath(path).is_absolute()
            or PurePosixPath(path).is_absolute()
            or path.startswith(("/", "\\"))
            or (len(path) >= 2 and path[1] == ":")
        ):
            raise ValueError(f"evidence path must be workspace-relative: {item.path}")


def _extract_message_content(response: Mapping[str, Any]) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list) or len(choices) != 1:
        raise ProviderError("PROVIDER_RESPONSE_ERROR", "provider response must contain exactly one choice")
    choice = choices[0]
    if not isinstance(choice, Mapping):
        raise ProviderError("PROVIDER_RESPONSE_ERROR", "provider choice must be an object")
    message = choice.get("message")
    if not isinstance(message, Mapping):
        raise ProviderError("PROVIDER_RESPONSE_ERROR", "provider choice must contain a message object")
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ProviderError("PROVIDER_RESPONSE_ERROR", "provider message content must be a non-empty string")
    return content.strip()


_PLANNING_OUTPUT_CONTRACT = {
    "interpreted_problem": "non-empty string",
    "ambiguities": ["string"],
    "candidate_guard_ids": ["approved guard ID string"],
    "evidence_requests": [
        {
            "tool_id": "approved tool ID string",
            "path": "workspace-relative path without a leading slash, backslash, or drive prefix",
            "reason": "non-empty string",
        }
    ],
    "validation_requests": [],
    "explanation_focus": ["string"],
    "proposal_candidate": "optional governed rule candidate object",
}

_EXPLANATION_OUTPUT_CONTRACT = {"explanation": "non-empty string"}

_PLANNING_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "interpreted_problem": {"type": "string", "minLength": 1},
        "ambiguities": {"type": "array", "items": {"type": "string"}},
        "candidate_guard_ids": {"type": "array", "items": {"type": "string"}, "maxItems": 1},
        "evidence_requests": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "tool_id": {"type": "string", "minLength": 1},
                    "path": {
                        "type": "string",
                        "minLength": 1,
                        "pattern": "^[^/\\\\:][^:]*$",
                    },
                    "reason": {"type": "string", "minLength": 1},
                },
                "required": ["tool_id", "path", "reason"],
                "additionalProperties": False,
            },
        },
        "validation_requests": {"type": "array", "items": {"type": "string"}, "maxItems": 0},
        "explanation_focus": {"type": "array", "items": {"type": "string"}},
        "proposal_candidate": {
            "type": ["object", "null"],
            "properties": {
                "target_profile_path": {"type": "string", "minLength": 1},
                "trigger": {"type": "string", "minLength": 1},
                "rationale": {"type": "string", "minLength": 1},
                "scope": {"type": "array", "items": {"type": "string", "minLength": 1}, "minItems": 1},
                "required_action": {"type": "string", "minLength": 1},
                "severity": {"type": "string", "enum": ["info", "warning", "error", "blocking"]},
                "exceptions": {"type": "array", "items": {"type": "string"}},
                "validation_plan": {"type": "array", "items": {"type": "string", "minLength": 1}, "minItems": 1},
                "rollback_plan": {"type": "array", "items": {"type": "string", "minLength": 1}, "minItems": 1},
            },
            "required": [
                "target_profile_path", "trigger", "rationale", "scope",
                "required_action", "severity", "exceptions",
                "validation_plan", "rollback_plan",
            ],
            "additionalProperties": False,
        },
    },
    "required": [
        "interpreted_problem",
        "ambiguities",
        "candidate_guard_ids",
        "evidence_requests",
        "validation_requests",
        "explanation_focus",
    ],
    "additionalProperties": False,
}

_EXPLANATION_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "explanation": {"type": "string", "minLength": 1},
    },
    "required": ["explanation"],
    "additionalProperties": False,
}

_PLANNING_SYSTEM_PROMPT = """You are the bounded planning stage inside LBE. Return exactly one top-level JSON object with exactly these six required keys: interpreted_problem, ambiguities, candidate_guard_ids, evidence_requests, validation_requests, explanation_focus. You may optionally include a seventh key, proposal_candidate, only when the deterministic result warrants a governed workspace rule; it must be an object with exactly these keys: target_profile_path, trigger, rationale, scope, required_action, severity, exceptions, validation_plan, rollback_plan, and must be omitted otherwise. Do not wrap the object in planning_contract, result, output, data, or any other key. interpreted_problem must be a non-empty string. ambiguities, candidate_guard_ids, and explanation_focus must be JSON arrays of strings and may be empty. validation_requests must be an empty JSON array because deterministic validation is owned by LBE. evidence_requests must be a JSON array of objects with exactly tool_id, path, and reason. Every evidence path must be workspace-relative and must not begin with a slash or backslash, contain a drive prefix, use a UNC prefix, or reconstruct an absolute workspace root. Use only approved guard IDs, approved tool IDs, and workspace-relative paths supplied in the input. Do not select validation IDs. Do not return verdicts, authorization, commands, writes, repairs, mutations, policy decisions, or memory-promotion instructions. Do not include Markdown or prose outside the JSON object."""

_EXPLANATION_SYSTEM_PROMPT = """You are the bounded explanation stage inside LBE. The deterministic result is final. Return exactly one top-level JSON object with exactly one key: explanation. Do not wrap it in result, output, data, or any other key. explanation must be a non-empty string that concisely explains only the supplied result and evidence. Do not add or alter verdicts, authority, evidence, governance state, commands, writes, repairs, or policy decisions. Do not include Markdown or prose outside the JSON object."""
