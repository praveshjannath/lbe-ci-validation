from __future__ import annotations

from typing import Any, Mapping

from lbe_guard_inspector.openai_compatible_event_adapter import OpenAICompatibleEventAdapter
from lbe_guard_inspector.professional_provider_events import ModelEventType
from lbe_guard_inspector.reasoning_provider import ProviderConfig, ProviderError


class _Transport:
    def __init__(self, response: Mapping[str, Any] | Exception) -> None:
        self.response = response

    def post_json(self, **_: Any) -> Mapping[str, Any]:
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def _adapter(response: Mapping[str, Any] | Exception) -> OpenAICompatibleEventAdapter:
    return OpenAICompatibleEventAdapter(
        config=ProviderConfig(endpoint="http://provider/v1/chat/completions", model="local-model", timeout_seconds=5),
        transport=_Transport(response),
    )


def test_complete_text_response_emits_no_fabricated_delta_and_preserves_usage() -> None:
    events = _adapter({
        "id": "chatcmpl-1",
        "choices": [{"message": {"content": "complete response"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
    }).complete(messages=({"role": "user", "content": "hello"},))

    assert [event.event_type for event in events] == [
        ModelEventType.TURN_STARTED,
        ModelEventType.MESSAGE_COMPLETED,
        ModelEventType.USAGE_UPDATED,
        ModelEventType.TURN_COMPLETED,
    ]
    assert events[1].text == "complete response"
    assert events[2].usage == {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5}
    assert all(event.event_type is not ModelEventType.MESSAGE_DELTA for event in events)


def test_complete_tool_call_preserves_distinct_provider_and_lbe_identity() -> None:
    events = _adapter({
        "id": "chatcmpl-2",
        "choices": [{
            "message": {"content": None, "tool_calls": [{
                "id": "provider-call-1",
                "function": {"name": "workspace.read", "arguments": '{"path":"README.md"}'},
            }]},
            "finish_reason": "tool_calls",
        }],
    }).complete(
        messages=({"role": "user", "content": "read"},),
        lbe_call_id_for_provider_tool_call=lambda _: "lbe-call-1",
    )

    assert [event.event_type for event in events] == [
        ModelEventType.TURN_STARTED,
        ModelEventType.TOOL_CALL_STARTED,
        ModelEventType.TOOL_CALL_COMPLETED,
        ModelEventType.TURN_REQUIRES_TOOL,
    ]
    assert events[2].provider_tool_call_id == "provider-call-1"
    assert events[2].lbe_call_id == "lbe-call-1"
    assert events[2].tool_arguments == {"path": "README.md"}


def test_provider_failure_is_a_truthful_error_event() -> None:
    events = _adapter(ProviderError("PROVIDER_TIMEOUT", "timed out")).complete(
        messages=({"role": "user", "content": "hello"},),
    )

    assert len(events) == 1
    assert events[0].event_type is ModelEventType.ERROR
    assert events[0].error_code == "PROVIDER_TIMEOUT"
    assert events[0].metadata["terminal_attribution"] == "http_or_transport_error"


def test_unmapped_provider_tool_call_fails_without_fabricating_requires_tool_state() -> None:
    events = _adapter({
        "id": "chatcmpl-3",
        "choices": [{
            "message": {"tool_calls": [{
                "id": "provider-call-1",
                "function": {"name": "workspace.read", "arguments": '{"path":"README.md"}'},
            }]},
            "finish_reason": "tool_calls",
        }],
    }).complete(messages=({"role": "user", "content": "read"},))

    assert [event.event_type for event in events] == [
        ModelEventType.TURN_STARTED,
        ModelEventType.ERROR,
    ]
    assert events[-1].error_code == "LBE_CALL_ID_REQUIRED"
