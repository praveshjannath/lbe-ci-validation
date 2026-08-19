from pathlib import Path

from lbe_guard_inspector.control_protocol import ControlMethod, ControlRequest
from lbe_guard_inspector.memory.models import SessionState
from lbe_guard_inspector.memory.operational_history import SessionOperationalHistory, TurnStatus
from lbe_guard_inspector.memory.store import WorkspaceMemoryStore
from lbe_guard_inspector.persistent_turn_control import PersistentTurnControl


def test_persisted_turn_control_records_intent_and_finalizes_cancel(tmp_path: Path) -> None:
    store = WorkspaceMemoryStore(tmp_path / "state.sqlite3")
    store.save_session_state(SessionState("s", "w", tmp_path, "coding", "read_only", "development", "openai-compatible", "m"))
    history = SessionOperationalHistory(store=store)
    control = PersistentTurnControl(history=history)
    start = control.handle(ControlRequest("one", ControlMethod.TURN_START, {"session_id": "s", "text": "begin"}))
    assert start.accepted and start.state == "started"
    turn = history.latest_running_turn(session_id="s")
    assert turn is not None
    assert not control.handle(ControlRequest("two", ControlMethod.TURN_START, {"session_id": "s", "text": "duplicate"})).accepted
    assert control.handle(ControlRequest("three", ControlMethod.TURN_STEER, {"session_id": "s", "turn_id": turn.turn_id, "text": "focus"})).state == "queued"
    assert control.handle(ControlRequest("four", ControlMethod.TURN_INTERRUPT, {"session_id": "s", "turn_id": turn.turn_id})).state == "requested"
    assert control.handle(ControlRequest("five", ControlMethod.TURN_CANCEL, {"session_id": "s", "turn_id": turn.turn_id})).state == "cancelled"
    assert history.get_turn(turn_id=turn.turn_id).status is TurnStatus.CANCELLED
    assert [event.event_type for event in history.events_for_turn(turn_id=turn.turn_id)] == ["user.message", "turn.steering.received", "turn.interrupt.requested", "turn.cancelled"]
