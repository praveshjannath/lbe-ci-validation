from pathlib import Path

from lbe_guard_inspector.memory.models import SessionState
from lbe_guard_inspector.memory.operational_history import OperationalEvent, SessionOperationalHistory
from lbe_guard_inspector.memory.store import WorkspaceMemoryStore
from lbe_guard_inspector.professional_transcript import replay_session_transcript


def test_transcript_replays_authoritative_order_without_fabrication(tmp_path: Path) -> None:
    store = WorkspaceMemoryStore(tmp_path / "state.sqlite3")
    store.save_session_state(SessionState("s", "w", tmp_path, "coding", "read_only", "development", "openai-compatible", "m"))
    history = SessionOperationalHistory(store=store)
    turn = history.start_turn(session_id="s")
    item = history.start_item(turn_id=turn.turn_id, kind="model.exchange")
    history.append_event(OperationalEvent(session_id="s", turn_id=turn.turn_id, item_id=item.item_id, event_type="model.message.delta", payload={"text": "hello"}))
    rows = replay_session_transcript(history=history, session_id="s")
    assert [(row.sequence, row.kind, row.text) for row in rows] == [(1, "model.message.delta", "hello")]
