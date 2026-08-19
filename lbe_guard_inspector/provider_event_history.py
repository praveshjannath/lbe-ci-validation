"""Projection of normalized provider observations into authoritative history."""
from __future__ import annotations

from typing import Any, Iterable

from .memory.operational_history import OperationalEvent, SessionOperationalHistory, TurnStatus
from .professional_provider_events import ModelEventType, NormalizedModelEvent


_TERMINAL_STATUS = {
    ModelEventType.TURN_COMPLETED: TurnStatus.COMPLETED,
    ModelEventType.TURN_INCOMPLETE: TurnStatus.INCOMPLETE,
    ModelEventType.TURN_REFUSED: TurnStatus.REFUSED,
    ModelEventType.CANCELLED: TurnStatus.CANCELLED,
    ModelEventType.ERROR: TurnStatus.FAILED,
}


def project_provider_events(*, history: SessionOperationalHistory, turn_id: str, events: Iterable[NormalizedModelEvent]) -> tuple[OperationalEvent, ...]:
    """Persist provider observations in order; this function never invokes tools."""
    turn = history.get_turn(turn_id=turn_id)
    if turn is None or turn.status is not TurnStatus.RUNNING:
        raise ValueError("turn must exist and be running")
    persisted: list[OperationalEvent] = []
    terminal: TurnStatus | None = None
    for event in events:
        if not isinstance(event, NormalizedModelEvent):
            raise TypeError("events must contain NormalizedModelEvent")
        if terminal is not None and event.event_type is not ModelEventType.USAGE_UPDATED:
            raise ValueError("provider events cannot follow a terminal event")
        payload = _payload(event)
        persisted.append(history.append_event(OperationalEvent(
            session_id=turn.session_id, turn_id=turn.turn_id, event_type=event.event_type.value,
            payload=payload, provider_id=event.provider_id, model_id=event.model_id,
            provider_request_id=event.provider_request_id, provider_item_id=event.provider_item_id,
            provider_tool_call_id=event.provider_tool_call_id, lbe_call_id=event.lbe_call_id,
        )))
        terminal = _TERMINAL_STATUS.get(event.event_type) or terminal
    if terminal is not None:
        history.finalize_turn(turn_id=turn.turn_id, status=terminal)
    return tuple(persisted)


def _payload(event: NormalizedModelEvent) -> dict[str, Any]:
    payload: dict[str, Any] = {"protocol_family": event.protocol_family.value, "metadata": dict(event.metadata)}
    for name in ("text", "tool_name", "error_code"):
        value = getattr(event, name)
        if value is not None:
            payload[name] = value
    if event.tool_arguments is not None:
        payload["tool_arguments"] = dict(event.tool_arguments)
    if event.usage is not None:
        payload["usage"] = dict(event.usage)
    return payload
