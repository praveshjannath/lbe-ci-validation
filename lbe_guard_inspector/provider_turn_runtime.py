"""Runtime-owned non-streaming provider turn over existing adapter and history."""
from __future__ import annotations

import threading

from .memory.operational_history import OperationalEvent, SessionOperationalHistory
from .openai_compatible_event_adapter import OpenAICompatibleEventAdapter
from .professional_provider_events import ModelEventType, NormalizedModelEvent, ProviderProtocolFamily
from .provider_event_history import project_provider_events


class NonStreamingProviderTurnRuntime:
    def __init__(self, *, history: SessionOperationalHistory, adapter: OpenAICompatibleEventAdapter, provider_id: str = "openai-compatible") -> None:
        self.history = history
        self.adapter = adapter
        self.provider_id = provider_id
        self._cancel_lock = threading.Lock()
        self._cancelled_turns: set[str] = set()

    @property
    def supports_cancellation(self) -> bool:
        transport = getattr(getattr(self.adapter, "_transport", None), "supports_cancellation", False)
        return bool(transport)

    def cancel(self, *, turn_id: str) -> None:
        with self._cancel_lock:
            self._cancelled_turns.add(turn_id)
        transport = getattr(getattr(self.adapter, "_transport", None), "cancel", None)
        if transport is not None:
            transport()

    def was_cancelled(self, *, turn_id: str) -> bool:
        with self._cancel_lock:
            return turn_id in self._cancelled_turns

    def run(self, *, turn_id: str, text: str) -> None:
        try:
            events = self.adapter.complete(messages=({"role": "user", "content": text},), provider_id=self.provider_id)
            if self.was_cancelled(turn_id=turn_id):
                return
            project_provider_events(history=self.history, turn_id=turn_id, events=events)
        except Exception as exc:
            if self.was_cancelled(turn_id=turn_id):
                return
            project_provider_events(history=self.history, turn_id=turn_id, events=(NormalizedModelEvent(
                ModelEventType.ERROR, self.provider_id, self.adapter._config.model, ProviderProtocolFamily.OPENAI_COMPATIBLE_CHAT,
                error_code="RUNTIME_PROVIDER_PROJECTION_ERROR", metadata={"error_type": type(exc).__name__},
            ),))

    def start(self, *, turn_id: str, text: str) -> None:
        self.run(turn_id=turn_id, text=text)


class BackgroundProviderTurnRuntime:
    """One non-blocking lifecycle around the existing non-streaming runtime."""

    def __init__(self, *, history: SessionOperationalHistory, foreground: NonStreamingProviderTurnRuntime) -> None:
        self.history = history
        self.foreground = foreground
        self._lock = threading.RLock()
        self._threads: dict[str, threading.Thread] = {}

    @property
    def supports_cancellation(self) -> bool:
        return getattr(self.foreground, "supports_cancellation", False)

    def cancel(self, *, turn_id: str) -> None:
        if self.is_running(turn_id=turn_id):
            self.foreground.cancel(turn_id=turn_id)

    def start(self, *, turn_id: str, text: str) -> None:
        with self._lock:
            if self.is_running(turn_id=turn_id):
                raise ValueError("provider turn is already running")
            turn = self.history.get_turn(turn_id=turn_id)
            if turn is None:
                raise ValueError("turn not found")
            self.history.append_event(OperationalEvent(session_id=turn.session_id, turn_id=turn_id, event_type="runtime.provider.queued", payload={}))
            thread = threading.Thread(target=self._run, kwargs={"turn_id": turn_id, "text": text}, daemon=True)
            self._threads[turn_id] = thread
            thread.start()

    def is_running(self, *, turn_id: str) -> bool:
        with self._lock:
            thread = self._threads.get(turn_id)
            return thread is not None and thread.is_alive()

    def _run(self, *, turn_id: str, text: str) -> None:
        try:
            turn = self.history.get_turn(turn_id=turn_id)
            if turn is not None:
                self.history.append_event(OperationalEvent(session_id=turn.session_id, turn_id=turn_id, event_type="runtime.provider.running", payload={}))
                self.foreground.run(turn_id=turn_id, text=text)
        finally:
            with self._lock:
                self._threads.pop(turn_id, None)
