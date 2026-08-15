from __future__ import annotations

from lbe_guard_inspector.memory.models import SessionState
from lbe_guard_inspector.memory.operational_history import (
    OperationalEvent,
    SessionOperationalHistory,
    TurnStatus,
)
from lbe_guard_inspector.memory.store import WorkspaceMemoryStore
from lbe_guard_inspector.professional_control_protocol import ControlMethod, ControlRequest, ControlResponse
from lbe_guard_inspector.professional_control_runtime import ProfessionalControlRuntime


def _runtime(tmp_path):
    store = WorkspaceMemoryStore(tmp_path / "memory.sqlite3")
    store.save_session_state(SessionState(
        session_id="session-1",
        project_workspace_id="workspace-1",
        canonical_workspace_root=tmp_path,
        mode="coding",
        permission="write_allowed",
        runtime_policy="development",
        provider_id="openai-compatible",
        provider_model="model-a",
    ))
    history = SessionOperationalHistory(store=store)
    return store, history, ProfessionalControlRuntime(store=store, history=history, runtime_version="test")


def _request(request_id: str, method: ControlMethod, **params):
    return ControlRequest(request_id=request_id, method=method, params=params)


def _initialize(runtime):
    return runtime.handle(_request(
        "init-1",
        ControlMethod.INITIALIZE,
        client={
            "client_name": "test-client",
            "client_version": "1.0",
            "client_kind": "test",
            "supported_protocol_version": "1.0",
            "supported_event_capabilities": ["item.delta"],
        },
    ))


def test_initialize_advertises_only_implemented_read_only_methods(tmp_path) -> None:
    _, _, runtime = _runtime(tmp_path)
    response = _initialize(runtime)
    assert response.error is None
    assert runtime.initialized
    assert response.result["protocol_version"] == "1.0"
    assert set(response.result["supported_methods"]) == {
        "initialize",
        "session.read",
        "session.status",
        "session.events.list",
    }
    assert "turn.steer" not in response.result["supported_methods"]


def test_read_only_methods_require_successful_initialization(tmp_path) -> None:
    _, _, runtime = _runtime(tmp_path)
    response = runtime.handle(_request("read-1", ControlMethod.SESSION_READ, session_id="session-1"))
    assert response.result is None
    assert response.error.code == "NOT_INITIALIZED"


def test_unsupported_protocol_version_fails_closed(tmp_path) -> None:
    _, _, runtime = _runtime(tmp_path)
    request = ControlRequest(
        request_id="bad-version",
        method=ControlMethod.INITIALIZE,
        protocol_version="2.0",
        params={"client": {
            "client_name": "test-client",
            "client_version": "1.0",
            "client_kind": "test",
            "supported_protocol_version": "2.0",
        }},
    )
    response = runtime.handle(request)
    assert response.error.code == "INVALID_REQUEST"
    assert not runtime.initialized


def test_session_read_projects_authoritative_persisted_state(tmp_path) -> None:
    _, _, runtime = _runtime(tmp_path)
    _initialize(runtime)
    response = runtime.handle(_request("read-1", ControlMethod.SESSION_READ, session_id="session-1"))
    assert response.error is None
    session = response.result["session"]
    assert session["session_id"] == "session-1"
    assert session["project_workspace_id"] == "workspace-1"
    assert session["mode"] == "coding"
    assert session["permission"] == "write_allowed"
    assert session["provider_id"] == "openai-compatible"


def test_session_status_uses_persisted_history_without_mutating_it(tmp_path) -> None:
    _, history, runtime = _runtime(tmp_path)
    turn = history.start_turn(session_id="session-1", turn_id="turn-1")
    history.append_event(OperationalEvent(
        session_id="session-1",
        turn_id=turn.turn_id,
        event_type="model.turn.started",
        payload={},
    ))
    history.finalize_turn(turn_id=turn.turn_id, status=TurnStatus.INCOMPLETE)
    _initialize(runtime)

    response = runtime.handle(_request("status-1", ControlMethod.SESSION_STATUS, session_id="session-1"))
    assert response.error is None
    assert response.result["event_count"] == 1
    assert response.result["latest_turn"]["turn_id"] == "turn-1"
    assert response.result["latest_turn"]["status"] == "incomplete"
    assert len(history.events_for_session(session_id="session-1")) == 1


def test_session_events_list_preserves_order_and_identity(tmp_path) -> None:
    _, history, runtime = _runtime(tmp_path)
    turn = history.start_turn(session_id="session-1", turn_id="turn-1")
    history.append_event(OperationalEvent(
        session_id="session-1",
        turn_id=turn.turn_id,
        event_type="model.turn.started",
        payload={"n": 1},
        provider_id="openai-compatible",
        model_id="model-a",
    ))
    history.append_event(OperationalEvent(
        session_id="session-1",
        turn_id=turn.turn_id,
        event_type="model.turn.completed",
        payload={"n": 2},
        provider_id="openai-compatible",
        model_id="model-a",
    ))
    history.finalize_turn(turn_id=turn.turn_id, status=TurnStatus.COMPLETED)
    _initialize(runtime)

    response = runtime.handle(_request(
        "events-1",
        ControlMethod.SESSION_EVENTS_LIST,
        session_id="session-1",
        turn_id="turn-1",
    ))
    assert response.error is None
    events = response.result["events"]
    assert [event["event_type"] for event in events] == ["model.turn.started", "model.turn.completed"]
    assert [event["turn_sequence"] for event in events] == [1, 2]
    assert {event["provider_id"] for event in events} == {"openai-compatible"}


def test_unknown_session_and_turn_are_structured_errors(tmp_path) -> None:
    _, _, runtime = _runtime(tmp_path)
    _initialize(runtime)
    missing_session = runtime.handle(_request(
        "missing-session", ControlMethod.SESSION_READ, session_id="missing"
    ))
    assert missing_session.error.code == "SESSION_NOT_FOUND"

    missing_turn = runtime.handle(_request(
        "missing-turn",
        ControlMethod.SESSION_EVENTS_LIST,
        session_id="session-1",
        turn_id="missing",
    ))
    assert missing_turn.error.code == "TURN_NOT_FOUND"


def test_mutable_control_methods_are_not_falsely_advertised_or_executed(tmp_path) -> None:
    _, _, runtime = _runtime(tmp_path)
    _initialize(runtime)
    response = runtime.handle(_request(
        "steer-1",
        ControlMethod.TURN_STEER,
        session_id="session-1",
        turn_id="turn-1",
        input="change direction",
    ))
    assert response.result is None
    assert response.error.code == "METHOD_NOT_IMPLEMENTED"


def test_mutable_controls_delegate_to_existing_runtime_owner(tmp_path) -> None:
    store, history, _ = _runtime(tmp_path)
    class Owner:
        @property
        def supported_methods(self):
            return frozenset({ControlMethod.TURN_STEER})
        def handle_control(self, request):
            return ControlResponse(request_id=request.request_id, result={"accepted": request.method.value})
    runtime = ProfessionalControlRuntime(store=store, history=history, mutable_owner=Owner())
    _initialize(runtime)
    response = runtime.handle(_request("steer-1", ControlMethod.TURN_STEER, session_id="session-1", text="change direction"))
    assert response.result == {"accepted": "turn.steer"}
    assert "turn.steer" in _initialize(runtime).result["supported_methods"]
