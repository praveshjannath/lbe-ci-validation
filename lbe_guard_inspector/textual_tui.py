"""Textual client over persisted LBE history and typed control requests."""
from __future__ import annotations

from uuid import uuid4

from .control_protocol import ControlMethod, ControlOutcome, ControlRequest
from .memory.operational_history import SessionOperationalHistory
from .persistent_turn_control import PersistentTurnControl
from .professional_transcript import replay_session_transcript


def build_textual_tui(*, history: SessionOperationalHistory, session_id: str, control: PersistentTurnControl):
    """Build a client that projects runtime state; it owns no runtime state itself."""
    try:
        from textual.app import App, ComposeResult
        from textual.binding import Binding
        from textual.widgets import Footer, Header, Input, Static
    except ImportError as exc:
        raise RuntimeError("Textual UI is unavailable; install lbe-guard-inspector[tui]") from exc

    state = history.store.load_session_state(session_id=session_id)
    if state is None:
        raise ValueError(f"session not found: {session_id}")

    class LbeTextualApp(App[None]):
        TITLE = "LBE Runtime"
        CSS = "#session {height: 3;} #transcript {height: 1fr; overflow-y: auto;} #composer {dock: bottom;}"
        BINDINGS = [Binding("ctrl+i", "interrupt", "Interrupt", priority=True), Binding("ctrl+x", "cancel", "Cancel", priority=True)]

        def compose(self) -> ComposeResult:
            yield Header()
            yield Static(_session_text(), id="session")
            yield Static(_transcript_text(), id="transcript")
            yield Input(placeholder="Start a task or steer the active turn", id="composer")
            yield Footer()

        def on_input_submitted(self, event: Input.Submitted) -> None:
            text = event.value.strip()
            if not text:
                return
            active = history.latest_running_turn(session_id=session_id)
            method = ControlMethod.TURN_STEER if active is not None else ControlMethod.TURN_START
            params = {"session_id": session_id, "text": text}
            if active is not None:
                params["turn_id"] = active.turn_id
            self._handle(ControlRequest(f"tui-{uuid4()}", method, params))
            event.input.value = ""

        def action_interrupt(self) -> None:
            active = history.latest_running_turn(session_id=session_id)
            if active is None:
                self.notify("No active turn to interrupt", severity="warning")
                return
            self._handle(ControlRequest(f"tui-{uuid4()}", ControlMethod.TURN_INTERRUPT, {"session_id": session_id, "turn_id": active.turn_id}))

        def action_cancel(self) -> None:
            active = history.latest_running_turn(session_id=session_id)
            if active is None:
                self.notify("No active turn to cancel", severity="warning")
                return
            self._handle(ControlRequest(f"tui-{uuid4()}", ControlMethod.TURN_CANCEL, {"session_id": session_id, "turn_id": active.turn_id}))

        def _handle(self, request: ControlRequest) -> None:
            outcome: ControlOutcome = control.handle(request)
            self.query_one("#transcript", Static).update(_transcript_text())
            self.notify(outcome.reason if not outcome.accepted else f"Control {outcome.state}", severity="error" if not outcome.accepted else "information")

    def _session_text() -> str:
        return f"Session {state.session_id}  |  {state.canonical_workspace_root}  |  {state.mode}  |  {state.provider_id or 'provider unknown'}/{state.provider_model or 'model unknown'}  |  {state.permission or 'permission unknown'}"

    def _transcript_text() -> str:
        rows = replay_session_transcript(history=history, session_id=session_id)
        return "No persisted runtime events." if not rows else "\n\n".join(f"[{row.sequence}] {row.kind}\n{row.text}" for row in rows)

    return LbeTextualApp()


def run_textual_tui(*, history: SessionOperationalHistory, session_id: str, control: PersistentTurnControl) -> None:
    build_textual_tui(history=history, session_id=session_id, control=control).run()
