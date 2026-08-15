"""Textual projection over LBE's persisted transcript; never a runtime owner."""
from __future__ import annotations

from typing import Protocol
from uuid import uuid4

from .memory.operational_history import SessionOperationalHistory
from .professional_control_protocol import ControlMethod, ControlRequest, ControlResponse
from .professional_transcript import replay_session_transcript


class TypedControlTransport(Protocol):
    def call(self, request: ControlRequest) -> ControlResponse: ...


def submit_composer_text(*, control: TypedControlTransport, session_id: str, text: str) -> ControlResponse:
    """Route input by authoritative session status, never UI-maintained state."""
    clean_text = text.strip()
    if not clean_text:
        raise ValueError("composer text must be non-empty")
    status = control.call(ControlRequest(
        request_id=f"tui-status-{uuid4()}",
        method=ControlMethod.SESSION_STATUS,
        params={"session_id": session_id},
    ))
    if status.error is not None:
        return status
    latest = status.result.get("latest_turn") if status.result is not None else None
    active_turn_id = latest.get("turn_id") if isinstance(latest, dict) and latest.get("status") == "in_progress" else None
    method = ControlMethod.TURN_STEER if isinstance(active_turn_id, str) else ControlMethod.TURN_START
    params = {"session_id": session_id, "text": clean_text}
    if active_turn_id is not None:
        params["turn_id"] = active_turn_id
    return control.call(ControlRequest(request_id=f"tui-input-{uuid4()}", method=method, params=params))


def build_transcript_app(*, history: SessionOperationalHistory, session_id: str, control: TypedControlTransport | None = None):
    """Create the interactive projection for terminals and integration tests."""
    try:
        from textual.app import App, ComposeResult
        from textual.widgets import Footer, Header, Input, Static
    except ImportError as exc:
        raise RuntimeError("Textual UI is unavailable; install lbe-guard-inspector[tui]") from exc

    class TranscriptApp(App[None]):
        TITLE = "LBE Agent Runtime"
        def compose(self) -> ComposeResult:
            yield Header()
            yield Static(_transcript_text(history, session_id), id="transcript")
            yield Input(
                placeholder="Steering requires a mutable control runtime" if control is None else "Send steering…",
                disabled=control is None,
                id="steering",
            )
            yield Footer()

        def on_input_submitted(self, event: Input.Submitted) -> None:
            if control is None or not event.value.strip():
                return
            response = submit_composer_text(control=control, session_id=session_id, text=event.value)
            self.query_one("#transcript", Static).update(_transcript_text(history, session_id))
            event.input.value = ""
            self.notify(response.error.message if response.error else "Input accepted")
    return TranscriptApp()


def run_transcript_tui(*, history: SessionOperationalHistory, session_id: str, control: TypedControlTransport | None = None) -> None:
    build_transcript_app(history=history, session_id=session_id, control=control).run()


def _transcript_text(history: SessionOperationalHistory, session_id: str) -> str:
    rows = replay_session_transcript(history=history, session_id=session_id)
    if not rows:
        return "No persisted runtime events for this session."
    return "\n\n".join(f"[{item.sequence}] {item.kind}\n{item.text}" for item in rows)
