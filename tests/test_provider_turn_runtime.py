from pathlib import Path

from lbe_guard_inspector.control_protocol import ControlMethod, ControlRequest
from lbe_guard_inspector.memory.models import SessionState
from lbe_guard_inspector.memory.operational_history import SessionOperationalHistory, TurnStatus
from lbe_guard_inspector.memory.store import WorkspaceMemoryStore
from lbe_guard_inspector.openai_compatible_event_adapter import OpenAICompatibleEventAdapter
from lbe_guard_inspector.persistent_turn_control import PersistentTurnControl
from lbe_guard_inspector.provider_turn_runtime import NonStreamingProviderTurnRuntime
from lbe_guard_inspector.reasoning_provider import ProviderConfig


class _Transport:
    def post_json(self, **_: object) -> dict[str, object]:
        return {"id": "req-1", "choices": [{"message": {"content": "answer"}, "finish_reason": "stop"}], "usage": {"total_tokens": 3}}


def test_typed_start_runs_provider_through_control_owner_and_persists_result(tmp_path: Path) -> None:
    store = WorkspaceMemoryStore(tmp_path / "state.sqlite3")
    store.save_session_state(SessionState("s", "w", tmp_path, "coding", "read_only", "development", "openai-compatible", "m"))
    history = SessionOperationalHistory(store=store)
    adapter = OpenAICompatibleEventAdapter(config=ProviderConfig("http://provider.invalid/v1/chat/completions", "m", 1), transport=_Transport())
    control = PersistentTurnControl(history=history, provider_runtime=NonStreamingProviderTurnRuntime(history=history, adapter=adapter))
    assert control.handle(ControlRequest("r", ControlMethod.TURN_START, {"session_id": "s", "text": "hello"})).accepted
    turn = history.events_for_session(session_id="s")
    assert [event.event_type for event in turn] == ["user.message", "model.turn.started", "model.message.completed", "model.usage.updated", "model.turn.completed"]
    assert history.get_turn(turn_id=turn[-1].turn_id).status is TurnStatus.COMPLETED
