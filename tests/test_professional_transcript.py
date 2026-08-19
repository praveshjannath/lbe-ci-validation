from pathlib import Path

from lbe_guard_inspector.memory.models import SessionState
from lbe_guard_inspector.memory.operational_history import OperationalEvent, SessionOperationalHistory
from lbe_guard_inspector.memory.store import WorkspaceMemoryStore
from lbe_guard_inspector.professional_transcript import replay_session_transcript


def test_transcript_replays_persisted_session_order_after_reopen(tmp_path: Path) -> None:
    database = tmp_path / "state.sqlite3"
    store = WorkspaceMemoryStore(database)
    store.save_session_state(SessionState("s", "w", tmp_path, "coding", "read_only", "development", "openai-compatible", "m"))
    history = SessionOperationalHistory(store=store)
    first = history.start_turn(session_id="s")
    history.append_event(OperationalEvent(session_id="s", turn_id=first.turn_id, event_type="model.message.delta", payload={"text": "first"}))
    second = history.start_turn(session_id="s")
    history.append_event(OperationalEvent(session_id="s", turn_id=second.turn_id, event_type="tool.denied", payload={"error_message": "denied"}))
    reopened = SessionOperationalHistory(store=WorkspaceMemoryStore(database))
    rows = replay_session_transcript(history=reopened, session_id="s")
    assert [(row.sequence, row.kind, row.text) for row in rows] == [(1, "model.message.delta", "first"), (2, "tool.denied", "denied")]
