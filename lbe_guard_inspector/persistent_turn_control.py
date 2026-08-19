"""Typed persisted turn-intent dispatcher; it owns no provider or tool execution."""
from __future__ import annotations

from .control_protocol import ControlMethod, ControlOutcome, ControlRequest
from .memory.operational_history import OperationalEvent, SessionOperationalHistory, TurnStatus


class ProviderTurnRuntime:
    supports_cancellation: bool

    def start(self, *, turn_id: str, text: str) -> None: ...
    def cancel(self, *, turn_id: str) -> None: ...


class PersistentTurnControl:
    """Record user control intent through the authoritative operational history."""

    _METHODS = frozenset({ControlMethod.TURN_START, ControlMethod.TURN_STEER, ControlMethod.TURN_INTERRUPT, ControlMethod.TURN_CANCEL})

    def __init__(self, *, history: SessionOperationalHistory, provider_runtime: ProviderTurnRuntime | None = None) -> None:
        self.history = history
        self.provider_runtime = provider_runtime

    def handle(self, request: ControlRequest) -> ControlOutcome:
        if request.method not in self._METHODS:
            return ControlOutcome(request.request_id, False, "rejected", "method is not implemented by persisted turn control")
        session_id = _text(request, "session_id")
        if self.history.store.load_session_state(session_id=session_id) is None:
            return ControlOutcome(request.request_id, False, "rejected", "session not found")
        if request.method is ControlMethod.TURN_START:
            return self._start(request, session_id)
        turn_id = _text(request, "turn_id")
        turn = self.history.get_turn(turn_id=turn_id)
        if turn is None or turn.session_id != session_id or turn.status is not TurnStatus.RUNNING:
            return ControlOutcome(request.request_id, False, "rejected", "turn is not active for this session")
        if request.method is ControlMethod.TURN_STEER:
            self.history.append_event(OperationalEvent(session_id=session_id, turn_id=turn_id, event_type="turn.steering.received", payload={"text": _text(request, "text")}))
            return ControlOutcome(request.request_id, True, "queued")
        if request.method is ControlMethod.TURN_INTERRUPT:
            self.history.append_event(OperationalEvent(session_id=session_id, turn_id=turn_id, event_type="turn.interrupt.requested", payload={}))
            return ControlOutcome(request.request_id, True, "requested")
        if self.provider_runtime is not None and getattr(self.provider_runtime, "is_running", lambda **_: False)(turn_id=turn_id):
            if getattr(self.provider_runtime, "supports_cancellation", False):
                self.provider_runtime.cancel(turn_id=turn_id)
                self.history.append_event(OperationalEvent(session_id=session_id, turn_id=turn_id, event_type="turn.cancelled", payload={}))
                self.history.finalize_turn(turn_id=turn_id, status=TurnStatus.CANCELLED)
                return ControlOutcome(request.request_id, True, "cancelled")
            return ControlOutcome(request.request_id, False, "rejected", "live provider cancellation is not available for this transport")
        self.history.append_event(OperationalEvent(session_id=session_id, turn_id=turn_id, event_type="turn.cancelled", payload={}))
        self.history.finalize_turn(turn_id=turn_id, status=TurnStatus.CANCELLED)
        return ControlOutcome(request.request_id, True, "cancelled")

    def _start(self, request: ControlRequest, session_id: str) -> ControlOutcome:
        if self.history.latest_running_turn(session_id=session_id) is not None:
            return ControlOutcome(request.request_id, False, "rejected", "an active turn already exists")
        turn = self.history.start_turn(session_id=session_id)
        self.history.append_event(OperationalEvent(session_id=session_id, turn_id=turn.turn_id, event_type="user.message", payload={"text": _text(request, "text")}))
        if self.provider_runtime is not None:
            self.provider_runtime.start(turn_id=turn.turn_id, text=_text(request, "text"))
        return ControlOutcome(request.request_id, True, "started")


def _text(request: ControlRequest, name: str) -> str:
    value = request.params.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()
