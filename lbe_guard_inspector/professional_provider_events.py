"""Frozen provider-event contract for the professional runtime path.

This module is a vocabulary and identity boundary only.  It performs no
provider I/O, persistence, authorization, or tool execution.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping


class ProviderProtocolFamily(StrEnum):
    OPENAI_RESPONSES = "openai_responses"
    ANTHROPIC_MESSAGES = "anthropic_messages"
    GEMINI_INTERACTIONS = "gemini_interactions"
    GEMINI_GENERATE_CONTENT = "gemini_generate_content"
    OPENAI_COMPATIBLE_CHAT = "openai_compatible_chat"
    UNKNOWN = "unknown"


class ModelEventType(StrEnum):
    TURN_STARTED = "model.turn.started"
    MESSAGE_DELTA = "model.message.delta"
    MESSAGE_COMPLETED = "model.message.completed"
    REASONING_SUMMARY_DELTA = "model.reasoning_summary.delta"
    REASONING_SUMMARY_COMPLETED = "model.reasoning_summary.completed"
    TOOL_CALL_STARTED = "model.tool_call.started"
    TOOL_CALL_ARGUMENTS_DELTA = "model.tool_call.arguments.delta"
    TOOL_CALL_COMPLETED = "model.tool_call.completed"
    USAGE_UPDATED = "model.usage.updated"
    TURN_REQUIRES_TOOL = "model.turn.requires_tool"
    TURN_REQUIRES_CONTINUATION = "model.turn.requires_continuation"
    TURN_COMPLETED = "model.turn.completed"
    TURN_INCOMPLETE = "model.turn.incomplete"
    TURN_REFUSED = "model.turn.refused"
    CANCELLED = "model.cancelled"
    ERROR = "model.error"


_DELTA_EVENTS = frozenset({
    ModelEventType.MESSAGE_DELTA,
    ModelEventType.REASONING_SUMMARY_DELTA,
    ModelEventType.TOOL_CALL_ARGUMENTS_DELTA,
})
_TOOL_EVENTS = frozenset({
    ModelEventType.TOOL_CALL_STARTED,
    ModelEventType.TOOL_CALL_ARGUMENTS_DELTA,
    ModelEventType.TOOL_CALL_COMPLETED,
})


@dataclass(frozen=True)
class NormalizedModelEvent:
    """One truthful model observation with provider and LBE identity kept distinct."""

    event_type: ModelEventType
    provider_id: str
    model_id: str
    protocol_family: ProviderProtocolFamily
    provider_request_id: str | None = None
    provider_item_id: str | None = None
    provider_tool_call_id: str | None = None
    lbe_call_id: str | None = None
    text: str | None = None
    tool_name: str | None = None
    tool_arguments: Mapping[str, Any] | None = None
    usage: Mapping[str, int] | None = None
    error_code: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.event_type, ModelEventType):
            raise TypeError("event_type must be ModelEventType")
        if not isinstance(self.protocol_family, ProviderProtocolFamily):
            raise TypeError("protocol_family must be ProviderProtocolFamily")
        _text(self.provider_id, "provider_id")
        _text(self.model_id, "model_id")
        for name in ("provider_request_id", "provider_item_id", "provider_tool_call_id", "lbe_call_id", "tool_name", "error_code"):
            value = getattr(self, name)
            if value is not None:
                _text(value, name)
        if self.event_type in _DELTA_EVENTS:
            _text(self.text, "text")
        elif self.text is not None and not isinstance(self.text, str):
            raise TypeError("text must be a string when supplied")
        if self.event_type in _TOOL_EVENTS:
            _text(self.provider_tool_call_id, "provider_tool_call_id")
            _text(self.lbe_call_id, "lbe_call_id")
        if self.event_type is ModelEventType.TOOL_CALL_COMPLETED:
            _text(self.tool_name, "tool_name")
            if not isinstance(self.tool_arguments, Mapping):
                raise ValueError("model.tool_call.completed requires tool_arguments mapping")
        if self.event_type is ModelEventType.USAGE_UPDATED:
            if not isinstance(self.usage, Mapping):
                raise ValueError("model.usage.updated requires usage mapping")
            for key, value in self.usage.items():
                _text(key, "usage key")
                if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                    raise ValueError("usage values must be non-negative integers")
        if self.event_type is ModelEventType.ERROR:
            _text(self.error_code, "error_code")
        if not isinstance(self.metadata, Mapping):
            raise TypeError("metadata must be a mapping")


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()
