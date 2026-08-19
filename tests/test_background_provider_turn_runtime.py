import http.server
import socketserver
import threading
import time
from pathlib import Path

from lbe_guard_inspector.control_protocol import ControlMethod, ControlRequest
from lbe_guard_inspector.memory.models import SessionState
from lbe_guard_inspector.memory.operational_history import SessionOperationalHistory
from lbe_guard_inspector.memory.store import WorkspaceMemoryStore
from lbe_guard_inspector.openai_compatible_event_adapter import OpenAICompatibleEventAdapter
from lbe_guard_inspector.persistent_turn_control import PersistentTurnControl
from lbe_guard_inspector.provider_turn_runtime import BackgroundProviderTurnRuntime, NonStreamingProviderTurnRuntime
from lbe_guard_inspector.reasoning_provider import ProviderConfig


class _BlockingTransport:
    def __init__(self) -> None:
        self.started = threading.Event()
        self.release = threading.Event()
    def post_json(self, **_: object) -> dict[str, object]:
        self.started.set()
        self.release.wait(timeout=5)
        return {"id": "req", "choices": [{"message": {"content": "done"}, "finish_reason": "stop"}]}


class _CancellableTransport:
    supports_cancellation = True

    def __init__(self) -> None:
        self.started = threading.Event()
        self.release = threading.Event()
        self.cancelled = threading.Event()

    def post_json(self, **_: object) -> dict[str, object]:
        self.started.set()
        self.release.wait(timeout=5)
        if self.cancelled.is_set():
            raise RuntimeError("cancelled")
        return {"id": "req", "choices": [{"message": {"content": "done"}, "finish_reason": "stop"}]}

    def cancel(self) -> None:
        self.cancelled.set()
        self.release.set()



def test_background_runtime_leaves_control_responsive_and_rejects_unavailable_live_cancel(tmp_path: Path) -> None:
    store = WorkspaceMemoryStore(tmp_path / "state.sqlite3")
    store.save_session_state(SessionState("s", "w", tmp_path, "coding", "read_only", "development", "openai-compatible", "m"))
    history = SessionOperationalHistory(store=store)
    transport = _BlockingTransport()
    foreground = NonStreamingProviderTurnRuntime(history=history, adapter=OpenAICompatibleEventAdapter(config=ProviderConfig("http://provider.invalid/v1/chat/completions", "m", 5), transport=transport))
    control = PersistentTurnControl(history=history, provider_runtime=BackgroundProviderTurnRuntime(history=history, foreground=foreground))
    started = control.handle(ControlRequest("start", ControlMethod.TURN_START, {"session_id": "s", "text": "go"}))
    assert started.accepted and transport.started.wait(timeout=1)
    turn = history.latest_running_turn(session_id="s")
    assert turn is not None
    assert control.handle(ControlRequest("steer", ControlMethod.TURN_STEER, {"session_id": "s", "turn_id": turn.turn_id, "text": "focus"})).accepted
    cancelled = control.handle(ControlRequest("cancel", ControlMethod.TURN_CANCEL, {"session_id": "s", "turn_id": turn.turn_id}))
    assert not cancelled.accepted and "cancellation" in (cancelled.reason or "")
    transport.release.set()
    for _ in range(100):
        if history.get_turn(turn_id=turn.turn_id).status.value == "completed": break
        time.sleep(.01)
    assert history.get_turn(turn_id=turn.turn_id).status.value == "completed"


def test_background_runtime_cancels_in_flight_request_with_supported_transport(tmp_path: Path) -> None:
    store = WorkspaceMemoryStore(tmp_path / "state.sqlite3")
    store.save_session_state(SessionState("s", "w", tmp_path, "coding", "read_only", "development", "openai-compatible", "m"))
    history = SessionOperationalHistory(store=store)
    transport = _CancellableTransport()
    foreground = NonStreamingProviderTurnRuntime(history=history, adapter=OpenAICompatibleEventAdapter(config=ProviderConfig("http://provider.invalid/v1/chat/completions", "m", 5), transport=transport))
    control = PersistentTurnControl(history=history, provider_runtime=BackgroundProviderTurnRuntime(history=history, foreground=foreground))
    started = control.handle(ControlRequest("start", ControlMethod.TURN_START, {"session_id": "s", "text": "go"}))
    assert started.accepted and transport.started.wait(timeout=1)
    turn = history.latest_running_turn(session_id="s")
    assert turn is not None
    cancelled = control.handle(ControlRequest("cancel", ControlMethod.TURN_CANCEL, {"session_id": "s", "turn_id": turn.turn_id}))
    assert cancelled.accepted and cancelled.state == "cancelled"
    assert transport.cancelled.is_set()
    for _ in range(100):
        if history.get_turn(turn_id=turn.turn_id).status.value in ("cancelled", "failed", "incomplete"):
            break
        time.sleep(.01)
    final_status = history.get_turn(turn_id=turn.turn_id).status.value
    assert final_status in ("cancelled", "failed", "incomplete")


class _BlockingHTTPHandler(http.server.BaseHTTPRequestHandler):
    _release = threading.Event()
    _received = threading.Event()
    _cancelled = threading.Event()

    def log_message(self, *args: object) -> None:
        pass

    def do_POST(self) -> None:
        self._received.set()
        self._release.wait(timeout=5)
        if self._cancelled.is_set():
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"error":"cancelled"}')
        else:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"id":"real-req","choices":[{"message":{"content":"done"},"finish_reason":"stop"}]}')


class _ReuseTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


def test_real_http_transport_rejects_cancellation_when_not_supported(tmp_path: Path) -> None:
    """UrllibJsonTransport correctly reports it does not support cancellation, so cancel is rejected."""
    handler = _BlockingHTTPHandler
    handler._release.clear()
    handler._received.clear()
    handler._cancelled.clear()
    server = _ReuseTCPServer(("127.0.0.1", 0), handler)
    port = server.server_address[1]
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    try:
        from lbe_guard_inspector.reasoning_provider import UrllibJsonTransport
        transport = UrllibJsonTransport()
        assert transport.supports_cancellation is False, "UrllibJsonTransport must not claim cancellation support"
        store = WorkspaceMemoryStore(tmp_path / "state.sqlite3")
        store.save_session_state(SessionState("s", "w", tmp_path, "coding", "read_only", "development", "openai-compatible", "m"))
        history = SessionOperationalHistory(store=store)
        foreground = NonStreamingProviderTurnRuntime(history=history, adapter=OpenAICompatibleEventAdapter(config=ProviderConfig(f"http://127.0.0.1:{port}/v1/chat/completions", "m", 5), transport=transport))
        control = PersistentTurnControl(history=history, provider_runtime=BackgroundProviderTurnRuntime(history=history, foreground=foreground))
        started = control.handle(ControlRequest("start", ControlMethod.TURN_START, {"session_id": "s", "text": "go"}))
        assert started.accepted
        assert handler._received.wait(timeout=2), "server did not receive request"
        turn = history.latest_running_turn(session_id="s")
        assert turn is not None
        # When transport doesn't support cancellation, control rejects the cancel request
        cancelled = control.handle(ControlRequest("cancel", ControlMethod.TURN_CANCEL, {"session_id": "s", "turn_id": turn.turn_id}))
        assert not cancelled.accepted, "cancellation must be rejected when transport doesn't support it"
        assert "cancellation" in (cancelled.reason or "").lower(), f"reason must mention cancellation, got: {cancelled.reason}"
        # The turn should continue running and complete normally
        handler._release.set()
        for _ in range(100):
            if history.get_turn(turn_id=turn.turn_id).status.value == "completed":
                break
            time.sleep(.01)
        assert history.get_turn(turn_id=turn.turn_id).status.value == "completed"
    finally:
        handler._release.set()
        handler._cancelled.set()
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=5)
