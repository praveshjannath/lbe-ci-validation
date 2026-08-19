from pathlib import Path

from lbe_guard_inspector.memory.models import SessionState
from lbe_guard_inspector.memory.operational_history import SessionOperationalHistory, TurnStatus
from lbe_guard_inspector.memory.store import WorkspaceMemoryStore
from lbe_guard_inspector.professional_provider_events import ModelEventType, NormalizedModelEvent, ProviderProtocolFamily
from lbe_guard_inspector.provider_event_history import project_provider_events


def test_provider_events_persist_in_order_and_finalize_only_terminal_turn(tmp_path: Path) -> None:
    store = WorkspaceMemoryStore(tmp_path / "state.sqlite3")
    store.save_session_state(SessionState("s", "w", tmp_path, "coding", "read_only", "development", "openai-compatible", "m"))
    history = SessionOperationalHistory(store=store)
    turn = history.start_turn(session_id="s")
    events = (
        NormalizedModelEvent(ModelEventType.TURN_STARTED, "openai-compatible", "m", ProviderProtocolFamily.OPENAI_COMPATIBLE_CHAT, provider_request_id="req-1"),
        NormalizedModelEvent(ModelEventType.MESSAGE_COMPLETED, "openai-compatible", "m", ProviderProtocolFamily.OPENAI_COMPATIBLE_CHAT, provider_request_id="req-1", text="done"),
        NormalizedModelEvent(ModelEventType.TURN_COMPLETED, "openai-compatible", "m", ProviderProtocolFamily.OPENAI_COMPATIBLE_CHAT, provider_request_id="req-1"),
    )
    rows = project_provider_events(history=history, turn_id=turn.turn_id, events=events)
    assert [row.event_type for row in rows] == [item.event_type.value for item in events]
    assert rows[1].payload["text"] == "done"
    assert history.get_turn(turn_id=turn.turn_id).status is TurnStatus.COMPLETED


def test_provider_usage_may_follow_a_terminal_error(tmp_path: Path) -> None:
    store = WorkspaceMemoryStore(tmp_path / "state.sqlite3")
    store.save_session_state(SessionState("s", "w", tmp_path, "coding", "read_only", "development", "openai-compatible", "m"))
    history = SessionOperationalHistory(store=store)
    turn = history.start_turn(session_id="s")
    rows = project_provider_events(history=history, turn_id=turn.turn_id, events=(
        NormalizedModelEvent(ModelEventType.ERROR, "openai-compatible", "m", ProviderProtocolFamily.OPENAI_COMPATIBLE_CHAT, error_code="LBE_CALL_ID_REQUIRED"),
        NormalizedModelEvent(ModelEventType.USAGE_UPDATED, "openai-compatible", "m", ProviderProtocolFamily.OPENAI_COMPATIBLE_CHAT, usage={"total_tokens": 3}),
    ))
    assert [row.event_type for row in rows] == ["model.error", "model.usage.updated"]
    assert history.get_turn(turn_id=turn.turn_id).status is TurnStatus.FAILED
