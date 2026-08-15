"""Authoritative persisted turn-input controls; provider execution stays external.

This owner only records user intent through the authoritative operational
history.  It deliberately does not synthesize a provider response, execute a
tool, or claim to interrupt a provider process it does not own.
"""
from __future__ import annotations

from .memory.operational_history import OperationalEvent, SessionOperationalHistory, TurnStatus
from .professional_control_protocol import ControlError, ControlMethod, ControlRequest, ControlResponse


class PersistentTurnControlOwner:
    def __init__(self, *, history: SessionOperationalHistory) -> None:
        self.history = history

    @property
    def supported_methods(self) -> frozenset[ControlMethod]:
        return frozenset({
            ControlMethod.TURN_START,
            ControlMethod.TURN_STEER,
            ControlMethod.TURN_INTERRUPT,
            ControlMethod.TURN_CANCEL,
        })

    def handle_control(self, request: ControlRequest) -> ControlResponse:
        if request.method not in self.supported_methods:
            return ControlResponse(request_id=request.request_id, error=ControlError(code="METHOD_NOT_IMPLEMENTED", message=request.method.value))
        session_id = _text(request, "session_id")
        text = _text(request, "text") if request.method in {ControlMethod.TURN_START, ControlMethod.TURN_STEER} else ""
        if request.method is ControlMethod.TURN_START:
            active = _active_turn(self.history, session_id)
            if active is not None:
                return ControlResponse(
                    request_id=request.request_id,
                    error=ControlError(code="TURN_ALREADY_ACTIVE", message="steer, interrupt, or cancel the active turn before starting another"),
                )
            turn = self.history.start_turn(session_id=session_id)
            self.history.append_event(OperationalEvent(session_id=session_id, turn_id=turn.turn_id, event_type="user.message", payload={"text": text}))
            return ControlResponse(request_id=request.request_id, result={"turn_id": turn.turn_id, "outcome": "accepted"})
        turn_id = _text(request, "turn_id")
        turn = self.history.get_turn(turn_id=turn_id)
        if turn is None or turn.session_id != session_id or turn.status is not TurnStatus.IN_PROGRESS:
            return ControlResponse(request_id=request.request_id, error=ControlError(code="TURN_NOT_ACTIVE", message="turn is not active"))
        event_type = {
            ControlMethod.TURN_STEER: "turn.steering.received",
            ControlMethod.TURN_INTERRUPT: "turn.interrupt.requested",
            ControlMethod.TURN_CANCEL: "turn.cancelled",
        }[request.method]
        self.history.append_event(OperationalEvent(session_id=session_id, turn_id=turn_id, event_type=event_type, payload={"text": text}))
        if request.method is ControlMethod.TURN_CANCEL:
            self.history.finalize_turn(turn_id=turn_id, status=TurnStatus.CANCELLED)
        return ControlResponse(request_id=request.request_id, result={"turn_id": turn_id, "outcome": "accepted"})


def _text(request: ControlRequest, name: str) -> str:
    value = request.params.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def _active_turn(history: SessionOperationalHistory, session_id: str):
    events = history.events_for_session(session_id=session_id)
    if not events:
        return None
    turn = history.get_turn(turn_id=events[-1].turn_id)
    return turn if turn is not None and turn.status is TurnStatus.IN_PROGRESS else None
