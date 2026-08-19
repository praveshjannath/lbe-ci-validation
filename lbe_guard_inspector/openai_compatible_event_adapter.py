"""Native, non-streaming OpenAI-compatible response normalization for P3.

The adapter is provider I/O only. Tool execution, durable LBE call identity,
session persistence, and continuation remain outside this slice.
"""
from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Mapping

from .professional_provider_events import (
    ModelEventType,
    NormalizedModelEvent,
    ProviderProtocolFamily,
)
from .reasoning_provider import JsonTransport, ProviderConfig, ProviderError, UrllibJsonTransport


class OpenAICompatibleEventAdapter:
    """Translate one complete OpenAI-compatible response without inventing deltas."""

    def __init__(self, *, config: ProviderConfig, transport: JsonTransport | None = None) -> None:
        self._config = config
        self._transport = transport or UrllibJsonTransport()

    def complete(
        self,
        *,
        messages: tuple[Mapping[str, Any], ...],
        provider_id: str = "openai-compatible",
        lbe_call_id_for_provider_tool_call: Callable[[str], str] | None = None,
    ) -> tuple[NormalizedModelEvent, ...]:
        """Return truthful normalized events for one non-streaming provider call."""

        if not isinstance(messages, tuple) or not messages or not all(isinstance(item, Mapping) for item in messages):
            raise ValueError("messages must be a non-empty tuple of mappings")
        _required(provider_id, "provider_id")
        payload = {"model": self._config.model.strip(), "messages": [dict(item) for item in messages]}
        headers = {"Content-Type": "application/json"}
        if self._config.api_key:
            headers["Authorization"] = f"Bearer {self._config.api_key}"
        try:
            response = self._transport.post_json(
                endpoint=self._config.endpoint.strip(),
                payload=payload,
                headers=headers,
                timeout_seconds=float(self._config.timeout_seconds),
            )
        except ProviderError as exc:
            return (self._event(
                event_type=ModelEventType.ERROR,
                provider_id=provider_id,
                error_code=exc.code,
                metadata={"terminal_attribution": "http_or_transport_error"},
            ),)

        request_id = _optional_text(response.get("id"), "response id")
        events: list[NormalizedModelEvent] = [self._event(
            event_type=ModelEventType.TURN_STARTED,
            provider_id=provider_id,
            provider_request_id=request_id,
        )]
        choice = _single_choice(response)
        message = choice.get("message")
        if not isinstance(message, Mapping):
            return tuple(events + [self._event(
                event_type=ModelEventType.ERROR,
                provider_id=provider_id,
                provider_request_id=request_id,
                error_code="PROVIDER_RESPONSE_ERROR",
                metadata={"terminal_attribution": "provider_native"},
            )])
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            events.append(self._event(
                event_type=ModelEventType.MESSAGE_COMPLETED,
                provider_id=provider_id,
                provider_request_id=request_id,
                text=content,
            ))
        tool_events = self._tool_events(
            message=message,
            provider_id=provider_id,
            provider_request_id=request_id,
            lbe_call_id_for_provider_tool_call=lbe_call_id_for_provider_tool_call,
        )
        events.extend(tool_events)
        tool_error = any(event.event_type is ModelEventType.ERROR for event in tool_events)
        usage = _usage(response.get("usage"))
        if usage is not None:
            events.append(self._event(
                event_type=ModelEventType.USAGE_UPDATED,
                provider_id=provider_id,
                provider_request_id=request_id,
                usage=usage,
            ))
        finish_reason = _optional_text(choice.get("finish_reason"), "finish_reason")
        if tool_error:
            return tuple(events)
        if tool_events or finish_reason == "tool_calls":
            events.append(self._event(
                event_type=ModelEventType.TURN_REQUIRES_TOOL,
                provider_id=provider_id,
                provider_request_id=request_id,
            ))
        elif finish_reason == "length":
            events.append(self._event(
                event_type=ModelEventType.TURN_INCOMPLETE,
                provider_id=provider_id,
                provider_request_id=request_id,
                metadata={"terminal_attribution": "provider_native", "finish_reason": finish_reason},
            ))
        elif finish_reason in {"content_filter", "refusal"}:
            events.append(self._event(
                event_type=ModelEventType.TURN_REFUSED,
                provider_id=provider_id,
                provider_request_id=request_id,
                metadata={"terminal_attribution": "provider_native", "finish_reason": finish_reason},
            ))
        else:
            events.append(self._event(
                event_type=ModelEventType.TURN_COMPLETED,
                provider_id=provider_id,
                provider_request_id=request_id,
                metadata={"finish_reason": finish_reason} if finish_reason else {},
            ))
        return tuple(events)

    def _tool_events(
        self,
        *,
        message: Mapping[str, Any],
        provider_id: str,
        provider_request_id: str | None,
        lbe_call_id_for_provider_tool_call: Callable[[str], str] | None,
    ) -> tuple[NormalizedModelEvent, ...]:
        raw_calls = message.get("tool_calls")
        if raw_calls is None:
            return ()
        if not isinstance(raw_calls, list):
            return (self._event(
                event_type=ModelEventType.ERROR,
                provider_id=provider_id,
                provider_request_id=provider_request_id,
                error_code="PROVIDER_RESPONSE_ERROR",
                metadata={"terminal_attribution": "provider_native"},
            ),)
        if lbe_call_id_for_provider_tool_call is None:
            return (self._event(
                event_type=ModelEventType.ERROR,
                provider_id=provider_id,
                provider_request_id=provider_request_id,
                error_code="LBE_CALL_ID_REQUIRED",
                metadata={"terminal_attribution": "runtime_policy"},
            ),)
        events: list[NormalizedModelEvent] = []
        for raw_call in raw_calls:
            if not isinstance(raw_call, Mapping):
                return (self._event(
                    event_type=ModelEventType.ERROR,
                    provider_id=provider_id,
                    provider_request_id=provider_request_id,
                    error_code="PROVIDER_RESPONSE_ERROR",
                    metadata={"terminal_attribution": "provider_native"},
                ),)
            provider_tool_call_id = _required(raw_call.get("id"), "provider tool call id")
            function = raw_call.get("function")
            if not isinstance(function, Mapping):
                return (self._event(
                    event_type=ModelEventType.ERROR,
                    provider_id=provider_id,
                    provider_request_id=provider_request_id,
                    error_code="PROVIDER_RESPONSE_ERROR",
                    metadata={"terminal_attribution": "provider_native"},
                ),)
            tool_name = _required(function.get("name"), "tool name")
            arguments = _tool_arguments(function.get("arguments"))
            lbe_call_id = _required(lbe_call_id_for_provider_tool_call(provider_tool_call_id), "lbe_call_id")
            events.extend((
                self._event(
                    event_type=ModelEventType.TOOL_CALL_STARTED,
                    provider_id=provider_id,
                    provider_request_id=provider_request_id,
                    provider_tool_call_id=provider_tool_call_id,
                    lbe_call_id=lbe_call_id,
                ),
                self._event(
                    event_type=ModelEventType.TOOL_CALL_COMPLETED,
                    provider_id=provider_id,
                    provider_request_id=provider_request_id,
                    provider_tool_call_id=provider_tool_call_id,
                    lbe_call_id=lbe_call_id,
                    tool_name=tool_name,
                    tool_arguments=arguments,
                ),
            ))
        return tuple(events)

    def _event(self, *, event_type: ModelEventType, provider_id: str, **values: Any) -> NormalizedModelEvent:
        return NormalizedModelEvent(
            event_type=event_type,
            provider_id=provider_id,
            model_id=self._config.model.strip(),
            protocol_family=ProviderProtocolFamily.OPENAI_COMPATIBLE_CHAT,
            **values,
        )


def _single_choice(response: Mapping[str, Any]) -> Mapping[str, Any]:
    choices = response.get("choices")
    if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], Mapping):
        return {}
    return choices[0]


def _usage(value: Any) -> Mapping[str, int] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        return None
    normalized = {str(key): item for key, item in value.items() if isinstance(item, int) and not isinstance(item, bool) and item >= 0}
    return normalized or None


def _tool_arguments(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, str):
        raise ValueError("provider tool arguments must be JSON text")
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError("provider tool arguments must be valid JSON") from exc
    if not isinstance(decoded, Mapping):
        raise ValueError("provider tool arguments must decode to an object")
    return decoded


def _required(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def _optional_text(value: Any, name: str) -> str | None:
    if value is None:
        return None
    return _required(value, name)
