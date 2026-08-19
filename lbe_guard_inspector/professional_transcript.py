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
    """Project persisted events in order without creating any new activity."""
    return tuple(_project(event) for event in history.events_for_session(session_id=session_id))


def _project(event: OperationalEvent) -> TranscriptItem:
    payload: dict[str, Any] = dict(event.payload)
    text = payload.get("text")
    if not isinstance(text, str) or not text:
        text = str(payload.get("error_message") or payload.get("output") or payload.get("status") or event.event_type)
    return TranscriptItem(event.session_sequence or 0, event.event_type, event.event_type.rsplit(".", 1)[-1], text, event.event_id, event.item_id)
