import pytest

from lbe_guard_inspector.professional_provider_events import (
    ModelEventType,
    NormalizedModelEvent,
    ProviderProtocolFamily,
)


def _event(**values):
    defaults = {
        "event_type": ModelEventType.MESSAGE_DELTA,
        "provider_id": "openai-compatible",
        "model_id": "model-a",
        "protocol_family": ProviderProtocolFamily.OPENAI_COMPATIBLE_CHAT,
        "text": "hello",
        "provider_request_id": "provider-request-1",
    }
    defaults.update(values)
    return NormalizedModelEvent(**defaults)


def test_p0_event_and_protocol_vocabularies_are_exact() -> None:
    assert {item.value for item in ModelEventType} == {
        "model.turn.started",
        "model.message.delta",
        "model.message.completed",
        "model.reasoning_summary.delta",
        "model.reasoning_summary.completed",
        "model.tool_call.started",
        "model.tool_call.arguments.delta",
        "model.tool_call.completed",
        "model.usage.updated",
        "model.turn.requires_tool",
        "model.turn.requires_continuation",
        "model.turn.completed",
        "model.turn.incomplete",
        "model.turn.refused",
        "model.cancelled",
        "model.error",
    }
    assert {item.value for item in ProviderProtocolFamily} == {
        "openai_responses",
        "anthropic_messages",
        "gemini_interactions",
        "gemini_generate_content",
        "openai_compatible_chat",
        "unknown",
    }
    assert "model.tool_call.result" not in {item.value for item in ModelEventType}
    assert ModelEventType.TURN_REQUIRES_TOOL is not ModelEventType.TURN_REQUIRES_CONTINUATION


def test_message_delta_preserves_provider_identity_without_runtime_receipt_identity() -> None:
    event = _event()
    assert event.provider_request_id == "provider-request-1"
    assert event.provider_tool_call_id is None
    assert event.lbe_call_id is None
    assert not hasattr(event, "runtime_operation_id")
    assert not hasattr(event, "tool_receipt_id")


def test_tool_completion_requires_distinct_provider_and_lbe_call_identity() -> None:
    event = _event(
        event_type=ModelEventType.TOOL_CALL_COMPLETED,
        text=None,
        provider_tool_call_id="provider-tool-1",
        lbe_call_id="lbe-call-1",
        tool_name="workspace.read",
        tool_arguments={"path": "README.md"},
    )
    assert event.provider_tool_call_id == "provider-tool-1"
    assert event.lbe_call_id == "lbe-call-1"


def test_invalid_normalized_event_fails_closed() -> None:
    with pytest.raises(ValueError, match="text"):
        _event(event_type=ModelEventType.REASONING_SUMMARY_DELTA, text="")
    with pytest.raises(ValueError, match="provider_tool_call_id"):
        _event(event_type=ModelEventType.TOOL_CALL_STARTED, text=None, lbe_call_id="lbe-call-1")
    with pytest.raises(ValueError, match="error_code"):
        _event(event_type=ModelEventType.ERROR, text=None)
    with pytest.raises(ValueError, match="usage"):
        _event(event_type=ModelEventType.USAGE_UPDATED, text=None)
