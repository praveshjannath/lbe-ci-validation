"""Read-only P8 control handlers over existing authoritative runtime owners.

This module is deliberately not a second session/runtime controller. It only
negotiates the control protocol and exposes read-only projections from the
existing WorkspaceMemoryStore and SessionOperationalHistory owners. Mutable
turn/session/provider/permission controls are implemented in later P8 slices.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any, Mapping, Protocol

from .memory.operational_history import OperationalEvent, OperationalTurn, SessionOperationalHistory
from .memory.store import WorkspaceMemoryStore
from .professional_control_protocol import (
    CONTROL_PROTOCOL_VERSION,
    ClientKind,
    ControlClientMetadata,
    ControlError,
    ControlMethod,
    ControlRequest,
    ControlResponse,
    InitializeParams,
    InitializeResult,
    canonical_control_methods,
    canonical_control_notifications,
    require_supported_protocol_version,
)


class MutableControlOwner(Protocol):
    """Existing runtime owner for mutations; never implemented by the UI."""
    @property
    def supported_methods(self) -> frozenset[ControlMethod]: ...
    def handle_control(self, request: ControlRequest) -> ControlResponse: ...


class ProfessionalControlRuntime:
    """Bounded request dispatcher for the first read-only P8 control slice."""

    _READ_ONLY_METHODS = frozenset({
        ControlMethod.INITIALIZE,
        ControlMethod.SESSION_READ,
        ControlMethod.SESSION_STATUS,
        ControlMethod.SESSION_EVENTS_LIST,
    })

    def __init__(
        self,
        *,
        store: WorkspaceMemoryStore,
        history: SessionOperationalHistory,
        mutable_owner: MutableControlOwner | None = None,
        runtime_name: str = "lbe-professional-runtime",
        runtime_version: str = "0.1",
    ) -> None:
        if not isinstance(store, WorkspaceMemoryStore):
            raise TypeError("store must be WorkspaceMemoryStore")
        if not isinstance(history, SessionOperationalHistory):
            raise TypeError("history must be SessionOperationalHistory")
        if history.store.database_path != store.database_path:
            raise ValueError("control runtime store/history must share the authoritative database")
        if not isinstance(runtime_name, str) or not runtime_name.strip():
            raise ValueError("runtime_name must be a non-empty string")
        if not isinstance(runtime_version, str) or not runtime_version.strip():
            raise ValueError("runtime_version must be a non-empty string")
        self.store = store
        self.history = history
        self.runtime_name = runtime_name.strip()
        self.runtime_version = runtime_version.strip()
        self._client: ControlClientMetadata | None = None
        self._mutable_owner = mutable_owner

    @property
    def initialized(self) -> bool:
        return self._client is not None

    def handle(self, request: ControlRequest) -> ControlResponse:
        if not isinstance(request, ControlRequest):
            raise TypeError("request must be ControlRequest")
        try:
            require_supported_protocol_version(request.protocol_version)
            if request.method not in self._READ_ONLY_METHODS:
                if self._mutable_owner is not None:
                    response = self._mutable_owner.handle_control(request)
                    if not isinstance(response, ControlResponse) or response.request_id != request.request_id:
                        raise TypeError("mutable control owner must return matching ControlResponse")
                    return response
                return self._error(
                    request,
                    code="METHOD_NOT_IMPLEMENTED",
                    message=f"control method is not implemented in this P8 slice: {request.method.value}",
                )
            if request.method is ControlMethod.INITIALIZE:
                return self._initialize(request)
            if not self.initialized:
                return self._error(
                    request,
                    code="NOT_INITIALIZED",
                    message="initialize must succeed before runtime control methods are used",
                )
            if request.method is ControlMethod.SESSION_READ:
                return self._session_read(request)
            if request.method is ControlMethod.SESSION_STATUS:
                return self._session_status(request)
            if request.method is ControlMethod.SESSION_EVENTS_LIST:
                return self._session_events_list(request)
        except (TypeError, ValueError) as exc:
            return self._error(request, code="INVALID_REQUEST", message=str(exc))
        return self._error(request, code="METHOD_NOT_IMPLEMENTED", message=request.method.value)

    def _initialize(self, request: ControlRequest) -> ControlResponse:
        raw_client = _required_mapping(request.params, "client")
        client = ControlClientMetadata(
            client_name=_required_text(raw_client, "client_name"),
            client_version=_required_text(raw_client, "client_version"),
            client_kind=ClientKind(_required_text(raw_client, "client_kind")),
            supported_protocol_version=_required_text(raw_client, "supported_protocol_version"),
            supported_event_capabilities=tuple(raw_client.get("supported_event_capabilities", ())),
        )
        params = InitializeParams(client=client)
        require_supported_protocol_version(params.client.supported_protocol_version)
        self._client = client
        result = InitializeResult(
            protocol_version=CONTROL_PROTOCOL_VERSION,
            runtime_name=self.runtime_name,
            runtime_version=self.runtime_version,
            supported_methods=tuple(sorted(self._supported_methods(), key=lambda item: item.value)),
            supported_notifications=canonical_control_notifications(),
        )
        return ControlResponse(request_id=request.request_id, result={
            "protocol_version": result.protocol_version,
            "runtime_name": result.runtime_name,
            "runtime_version": result.runtime_version,
            "supported_methods": [item.value for item in result.supported_methods],
            "supported_notifications": [item.value for item in result.supported_notifications],
        })

    def _supported_methods(self) -> frozenset[ControlMethod]:
        if self._mutable_owner is None:
            return self._READ_ONLY_METHODS
        methods = self._mutable_owner.supported_methods
        if not isinstance(methods, frozenset) or not all(isinstance(method, ControlMethod) for method in methods):
            raise TypeError("mutable control owner supported_methods must be a frozenset of ControlMethod")
        return self._READ_ONLY_METHODS | methods

    def _session_read(self, request: ControlRequest) -> ControlResponse:
        session_id = _param_text(request.params, "session_id")
        state = self.store.load_session_state(session_id=session_id)
        if state is None:
            return self._error(request, code="SESSION_NOT_FOUND", message=f"unknown session: {session_id}")
        return ControlResponse(request_id=request.request_id, result={"session": state.as_dict()})

    def _session_status(self, request: ControlRequest) -> ControlResponse:
        session_id = _param_text(request.params, "session_id")
        state = self.store.load_session_state(session_id=session_id)
        if state is None:
            return self._error(request, code="SESSION_NOT_FOUND", message=f"unknown session: {session_id}")
        events = self.history.events_for_session(session_id=session_id)
        latest_turn = None
        if events:
            latest_turn = self.history.get_turn(turn_id=events[-1].turn_id)
        return ControlResponse(request_id=request.request_id, result={
            "session_id": session_id,
            "mode": state.mode,
            "permission": state.permission,
            "runtime_policy": state.runtime_policy,
            "provider_id": state.provider_id,
            "provider_model": state.provider_model,
            "latest_turn": _turn_dict(latest_turn),
            "event_count": len(events),
        })

    def _session_events_list(self, request: ControlRequest) -> ControlResponse:
        session_id = _param_text(request.params, "session_id")
        state = self.store.load_session_state(session_id=session_id)
        if state is None:
            return self._error(request, code="SESSION_NOT_FOUND", message=f"unknown session: {session_id}")
        turn_id = request.params.get("turn_id")
        if turn_id is not None:
            if not isinstance(turn_id, str) or not turn_id.strip():
                raise ValueError("turn_id must be a non-empty string when supplied")
            turn = self.history.get_turn(turn_id=turn_id.strip())
            if turn is None or turn.session_id != session_id:
                return self._error(request, code="TURN_NOT_FOUND", message=f"unknown turn for session: {turn_id}")
            events = self.history.events_for_turn(turn_id=turn_id.strip())
        else:
            events = self.history.events_for_session(session_id=session_id)
        return ControlResponse(request_id=request.request_id, result={
            "session_id": session_id,
            "turn_id": turn_id.strip() if isinstance(turn_id, str) else None,
            "events": [_event_dict(event) for event in events],
        })

    @staticmethod
    def _error(request: ControlRequest, *, code: str, message: str) -> ControlResponse:
        return ControlResponse(
            request_id=request.request_id,
            error=ControlError(code=code, message=message),
        )


def _param_text(params: Mapping[str, Any], name: str) -> str:
    value = params.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def _required_mapping(params: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    value = params.get(name)
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be a mapping")
    return value


def _required_text(params: Mapping[str, Any], name: str) -> str:
    return _param_text(params, name)


def _turn_dict(turn: OperationalTurn | None) -> dict[str, Any] | None:
    if turn is None:
        return None
    return {
        "turn_id": turn.turn_id,
        "session_id": turn.session_id,
        "ordinal": turn.ordinal,
        "status": turn.status.value,
        "created_at": turn.created_at,
        "finalized_at": turn.finalized_at,
    }


def _event_dict(event: OperationalEvent) -> dict[str, Any]:
    return {
        "event_id": event.event_id,
        "session_id": event.session_id,
        "turn_id": event.turn_id,
        "item_id": event.item_id,
        "session_sequence": event.session_sequence,
        "turn_sequence": event.turn_sequence,
        "event_type": event.event_type,
        "payload": dict(event.payload),
        "provider_id": event.provider_id,
        "model_id": event.model_id,
        "provider_request_id": event.provider_request_id,
        "provider_item_id": event.provider_item_id,
        "provider_tool_call_id": event.provider_tool_call_id,
        "lbe_call_id": event.lbe_call_id,
        "runtime_operation_id": event.runtime_operation_id,
        "tool_receipt_id": event.tool_receipt_id,
        "provider_state_metadata_ref": event.provider_state_metadata_ref,
        "raw_diagnostic_ref": event.raw_diagnostic_ref,
        "created_at": event.created_at,
    }
