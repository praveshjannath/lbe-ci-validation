import asyncio
from pathlib import Path

from lbe_guard_inspector.memory.models import SessionState
from lbe_guard_inspector.memory.operational_history import SessionOperationalHistory
from lbe_guard_inspector.memory.store import WorkspaceMemoryStore
from lbe_guard_inspector.persistent_turn_control import PersistentTurnControl
from lbe_guard_inspector.textual_tui import build_textual_tui


def test_textual_composer_and_control_keys_route_to_persisted_owner(tmp_path: Path) -> None:
    store = WorkspaceMemoryStore(tmp_path / "state.sqlite3")
    store.save_session_state(SessionState("s", "w", tmp_path, "coding", "read_only", "development", "openai-compatible", "m"))
    history = SessionOperationalHistory(store=store)
    app = build_textual_tui(history=history, session_id="s", control=PersistentTurnControl(history=history))

    async def exercise() -> None:
        async with app.run_test() as pilot:
            await pilot.click("#composer")
            await pilot.press("b", "e", "g", "i", "n", "enter")
            await pilot.press("ctrl+i", "ctrl+x")

    asyncio.run(exercise())
    turn = history.events_for_session(session_id="s")
    assert [event.event_type for event in turn] == ["user.message", "turn.interrupt.requested", "turn.cancelled"]
