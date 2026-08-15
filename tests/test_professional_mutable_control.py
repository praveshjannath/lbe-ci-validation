from pathlib import Path

from lbe_guard_inspector.memory.models import SessionState
from lbe_guard_inspector.memory.operational_history import SessionOperationalHistory, TurnStatus
from lbe_guard_inspector.memory.store import WorkspaceMemoryStore
from lbe_guard_inspector.professional_control_protocol import ControlMethod, ControlRequest
from lbe_guard_inspector.professional_mutable_control import PersistentTurnControlOwner
from lbe_guard_inspector.textual_tui import build_transcript_app, submit_composer_text


def _owner(tmp_path: Path):
    store = WorkspaceMemoryStore(tmp_path / "state.sqlite3")
    store.save_session_state(SessionState("session-1", "workspace-1", tmp_path, "coding", "read_only", "development", "openai-compatible", "model-a"))
    history = SessionOperationalHistory(store=store)
    return history, PersistentTurnControlOwner(history=history)


def _request(method: ControlMethod, **params):
    return ControlRequest(request_id=f"request-{method.value}", method=method, params=params)


def test_turn_input_owner_persists_start_steer_and_cancel_without_fabricating_output(tmp_path: Path) -> None:
    history, owner = _owner(tmp_path)
    started = owner.handle_control(_request(ControlMethod.TURN_START, session_id="session-1", text="inspect this"))
    turn_id = started.result["turn_id"]
    assert [event.event_type for event in history.events_for_session(session_id="session-1")] == ["user.message"]

    steered = owner.handle_control(_request(ControlMethod.TURN_STEER, session_id="session-1", turn_id=turn_id, text="use safe mode"))
    assert steered.error is None
    cancelled = owner.handle_control(_request(ControlMethod.TURN_CANCEL, session_id="session-1", turn_id=turn_id))
    assert cancelled.error is None
    assert history.get_turn(turn_id=turn_id).status is TurnStatus.CANCELLED
    assert [event.event_type for event in history.events_for_session(session_id="session-1")] == ["user.message", "turn.steering.received", "turn.cancelled"]


class _ComposerTransport:
    def __init__(self) -> None:
        self.requests = []

    def call(self, request):
        self.requests.append(request)
        if request.method is ControlMethod.SESSION_STATUS:
            return type("Response", (), {"error": None, "result": {"latest_turn": {"turn_id": "turn-active", "status": "in_progress"}}})()
        return type("Response", (), {"error": None, "result": {"outcome": "accepted"}})()


def test_composer_uses_runtime_status_to_route_active_turn_as_steering() -> None:
    transport = _ComposerTransport()
    response = submit_composer_text(control=transport, session_id="session-1", text="focus tests")
    assert response.error is None
    assert [request.method for request in transport.requests] == [ControlMethod.SESSION_STATUS, ControlMethod.TURN_STEER]
    assert transport.requests[-1].params["turn_id"] == "turn-active"


def test_textual_composer_routes_through_typed_control_and_refreshes_transcript(tmp_path: Path) -> None:
    import asyncio

    history, owner = _owner(tmp_path)

    class RuntimeTransport:
        def call(self, request):
            if request.method is ControlMethod.SESSION_STATUS:
                events = history.events_for_session(session_id="session-1")
                latest = history.get_turn(turn_id=events[-1].turn_id) if events else None
                return type("Response", (), {"error": None, "result": {"latest_turn": None if latest is None else {"turn_id": latest.turn_id, "status": latest.status.value}}})()
            return owner.handle_control(request)

    async def exercise() -> None:
        app = build_transcript_app(history=history, session_id="session-1", control=RuntimeTransport())
        async with app.run_test() as pilot:
            await pilot.click("#steering")
            await pilot.press(*"check persisted controls")
            await pilot.press("enter")
            assert "check persisted controls" in str(app.query_one("#transcript").render())

    asyncio.run(exercise())
