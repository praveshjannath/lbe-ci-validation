"""Deterministic read-only projection of authoritative operational events."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .memory.operational_history import OperationalEvent, SessionOperationalHistory


@dataclass(frozen=True)
class TranscriptItem:
    sequence: int
    kind: str
    status: str
    text: str
    event_id: str
    item_id: str | None


def replay_session_transcript(*, history: SessionOperationalHistory, session_id: str) -> tuple[TranscriptItem, ...]:
    """Project stored events in session order without inventing UI activity."""
    return tuple(_project(event) for event in history.events_for_session(session_id=session_id))


def _project(event: OperationalEvent) -> TranscriptItem:
    payload: dict[str, Any] = dict(event.payload)
    text = payload.get("text")
    if not isinstance(text, str) or not text:
        if event.event_type == "tool.started":
            text = f"{payload.get('tool_name', 'tool')} {payload.get('arguments', {})}"
        elif event.event_type.startswith("tool."):
            text = str(payload.get("error_message") or payload.get("output") or payload.get("status") or event.event_type)
        else:
            text = event.event_type
    status = event.event_type.rsplit(".", 1)[-1]
    return TranscriptItem(event.session_sequence, event.event_type, status, text, event.event_id, event.item_id)
