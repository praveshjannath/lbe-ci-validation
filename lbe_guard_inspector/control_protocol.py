"""Typed P8 control vocabulary; no session, provider, or tool authority."""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

CONTROL_PROTOCOL_VERSION="1.0"
class ControlMethod(StrEnum):
    SESSION_CREATE="session.create"; SESSION_RESUME="session.resume"; SESSION_READ="session.read"; SESSION_STATUS="session.status"; SESSION_EVENTS_LIST="session.events.list"; TURN_START="turn.start"; TURN_STEER="turn.steer"; TURN_INTERRUPT="turn.interrupt"; TURN_CANCEL="turn.cancel"; PROVIDER_SELECT="provider.select"; APPROVAL_RESPOND="approval.respond"; EVIDENCE_GET="evidence.get"; VALIDATION_GET="validation.get"
class ControlNotificationType(StrEnum):
    TURN_STEERING_RECEIVED="turn.steering.received"; TURN_STEERING_APPLIED="turn.steering.applied"; TURN_STEERING_QUEUED="turn.steering.queued"; TURN_STEERING_REJECTED="turn.steering.rejected"; TURN_INTERRUPTED="turn.interrupted"; ITEM_CANCELLED="item.cancelled"; APPROVAL_REQUESTED="approval.requested"; PROVIDER_CHANGED="provider.changed"
@dataclass(frozen=True)
class ControlRequest:
    request_id:str; method:ControlMethod; params:Mapping[str,Any]=field(default_factory=dict); protocol_version:str=CONTROL_PROTOCOL_VERSION
    def __post_init__(self):
        if not isinstance(self.request_id,str) or not self.request_id.strip(): raise ValueError("request_id must be non-empty")
        if not isinstance(self.method,ControlMethod) or not isinstance(self.params,Mapping): raise TypeError("method and params must be typed")
        if self.protocol_version!=CONTROL_PROTOCOL_VERSION: raise ValueError("unsupported control protocol version")
@dataclass(frozen=True)
class ControlOutcome:
    request_id:str; accepted:bool; state:str; reason:str|None=None
    def __post_init__(self):
        if not isinstance(self.request_id,str) or not self.request_id.strip() or not isinstance(self.accepted,bool) or not isinstance(self.state,str) or not self.state.strip(): raise ValueError("invalid control outcome")
        if not self.accepted and (not isinstance(self.reason,str) or not self.reason.strip()): raise ValueError("rejected control requires reason")
