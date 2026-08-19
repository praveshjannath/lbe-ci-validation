"""Typed protocol contract for the governed Cline Node stdio bridge."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping

PROTOCOL_VERSION = "lbe-cline-stdio/1"

PYTHON_TO_NODE = frozenset(
    {
        "runtime.start",
        "turn.execute",
        "tool.result",
        "control.cancel",
        "control.steer",
        "runtime.shutdown",
    }
)
NODE_TO_PYTHON = frozenset(
    {
        "runtime.ready",
        "provider.event",
        "tool.proposed",
        "turn.completed",
        "turn.failed",
        "runtime.error",
    }
)
ALL_MESSAGE_TYPES = PYTHON_TO_NODE | NODE_TO_PYTHON


class ProtocolError(ValueError):
    """Raised when a bridge frame violates the fail-closed protocol."""


@dataclass(frozen=True)
class BridgeFrame:
    protocol_version: str
    message_id: str
    message_type: str
    session_id: str
    turn_id: str
    payload: Mapping[str, Any]
    cline_tool_call_id: str | None = None
    lbe_call_id: str | None = None
    operation_id: str | None = None
    receipt_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "protocol_version": self.protocol_version,
            "message_id": self.message_id,
            "message_type": self.message_type,
            "session_id": self.session_id,
            "turn_id": self.turn_id,
            "payload": dict(self.payload),
        }
        for name in (
            "cline_tool_call_id",
            "lbe_call_id",
            "operation_id",
            "receipt_id",
        ):
            value = getattr(self, name)
            if value is not None:
                data[name] = value
        return data

    def to_json_line(self) -> str:
        return json.dumps(
            self.to_dict(), separators=(",", ":"), ensure_ascii=False
        ) + "\n"


def parse_frame(raw: str, *, expected_direction: str | None = None) -> BridgeFrame:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ProtocolError(f"malformed JSON frame: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise ProtocolError("frame must be a JSON object")

    required = (
        "protocol_version",
        "message_id",
        "message_type",
        "session_id",
        "turn_id",
    )
    for name in required:
        value = data.get(name)
        if not isinstance(value, str) or not value.strip():
            raise ProtocolError(f"{name} must be a non-empty string")

    if data["protocol_version"] != PROTOCOL_VERSION:
        raise ProtocolError(
            f"unsupported protocol_version: {data['protocol_version']}"
        )
    if data["message_type"] not in ALL_MESSAGE_TYPES:
        raise ProtocolError(f"unknown message_type: {data['message_type']}")

    if (
        expected_direction == "node_to_python"
        and data["message_type"] not in NODE_TO_PYTHON
    ):
        raise ProtocolError("unexpected Python-to-Node frame on Node output")
    if (
        expected_direction == "python_to_node"
        and data["message_type"] not in PYTHON_TO_NODE
    ):
        raise ProtocolError("unexpected Node-to-Python frame on Python input")

    payload = data.get("payload", {})
    if not isinstance(payload, dict):
        raise ProtocolError("payload must be a JSON object")

    optional_ids: dict[str, str | None] = {}
    for name in (
        "cline_tool_call_id",
        "lbe_call_id",
        "operation_id",
        "receipt_id",
    ):
        value = data.get(name)
        if value is not None and (
            not isinstance(value, str) or not value.strip()
        ):
            raise ProtocolError(
                f"{name} must be a non-empty string when present"
            )
        optional_ids[name] = value

    return BridgeFrame(
        protocol_version=data["protocol_version"],
        message_id=data["message_id"],
        message_type=data["message_type"],
        session_id=data["session_id"],
        turn_id=data["turn_id"],
        payload=payload,
        **optional_ids,
    )
