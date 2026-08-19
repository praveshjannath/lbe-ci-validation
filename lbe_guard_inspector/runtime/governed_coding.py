"""Governed coding composition over existing Cline and R6E authorities.

This module is intentionally a composition layer, not a new authority. Provider
mechanics remain in the existing Cline worker, authorization/execution remain in
R6C/R6E, session/task persistence remains in SessionMemoryRuntimeBridge, and
completion truth remains in CodingCompletionRuntime.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Mapping
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

from agent import Context, GovernanceError, matches_any, path_allowed

from ..evidence_service import EvidenceService
from ..reasoning_contracts import LBERequest, LBEResponse, OrchestrationError
from ..reasoning_provider import ProviderConfig
from ..session_memory_runtime import SessionMemoryRuntimeBridge
from .cline_stdio_bridge import GovernedClineWorker
from .cline_stdio_protocol import PROTOCOL_VERSION, BridgeFrame
from .mode_controller import ModeRequest, resolve_mode
from .tool_orchestration import (
    GovernedToolOrchestrator,
    ToolAccessClass,
    ToolExecutionContext,
    ToolExecutionResult,
    ToolNetworkBehavior,
    ToolReceipt,
    ToolReceiptStatus,
    ToolRegistry,
    ToolRiskClass,
    ToolSpec,
    build_workspace_read_handler,
    workspace_read_spec,
)

_MAX_CREATE_BYTES = 1_000_000


def workspace_create_candidate_text_spec() -> ToolSpec:
    """Declare one deliberately small production mutation capability.

    The tool is create-only: it cannot overwrite an existing file, create parent
    directories, execute commands, or leave the active workspace. The existing
    coding capability ``test_candidate`` is reused so no new permission vocabulary
    or authorization owner is introduced by this repair slice.
    """

    return ToolSpec(
        tool_id="workspace.create_candidate_text",
        capability="test_candidate",
        required_arguments=("path", "content"),
        access_class=ToolAccessClass.WRITE,
        network_behavior=ToolNetworkBehavior.NONE,
        risk_class=ToolRiskClass.MEDIUM,
        timeout_seconds=30.0,
        retry_policy="none",
        preconditions=(
            "relative workspace path",
            "target does not already exist",
            "parent directory already exists",
            "active governance allows the write path",
            "active governance allows at least one changed file and the patch size",
        ),
        expected_evidence=("created workspace file", "sha256"),
        failure_modes=(
            "invalid path",
            "forbidden path",
            "write path not allowed",
            "target already exists",
            "patch limit exceeded",
            "write failure",
            "authorization failure",
        ),
    )


def build_workspace_create_candidate_text_handler() -> object:
    """Build the create-only handler using existing workspace governance helpers."""

    def handler(request) -> ToolExecutionResult:
        raw_path = request.arguments["path"]
        content = request.arguments["content"]
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise ValueError("path must be a non-empty string")
        if not isinstance(content, str):
            raise ValueError("content must be a string")

        relative_text = raw_path.replace("\\", "/").strip()
        relative = Path(relative_text)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("path must stay within the active workspace")

        root = Path(request.context.workspace_root).resolve()
        candidate = (root / relative).resolve()
        try:
            relative_to_root = candidate.relative_to(root).as_posix()
        except ValueError as exc:
            raise ValueError("path escapes the active workspace") from exc

        ctx = Context.load()
        configured_root = next(
            (item for item in ctx.roots if item.path.resolve() == root),
            None,
        )
        if configured_root is None:
            raise GovernanceError("active workspace is not a configured knowledge root")

        governance = ctx.governance
        forbidden = list(governance.get("forbidden_globs", []))
        virtual = f"{configured_root.name}/{relative_to_root}"
        if matches_any(virtual, forbidden) or matches_any(relative_to_root, forbidden):
            raise GovernanceError(f"write path is explicitly forbidden: {relative_to_root}")

        allowed_write_paths = list(governance.get("allowed_write_paths", []))
        if not path_allowed(relative_to_root, allowed_write_paths):
            raise GovernanceError(f"write path is not allowed: {relative_to_root}")

        raw = content.encode("utf-8")
        if len(raw) > _MAX_CREATE_BYTES:
            raise ValueError(
                f"content exceeds bounded create limit of {_MAX_CREATE_BYTES} bytes"
            )

        max_changed_files = int(governance.get("max_changed_files", 0))
        if max_changed_files < 1:
            raise GovernanceError("active governance allows zero changed files")
        max_patch_bytes = int(governance.get("max_patch_bytes", 0))
        if max_patch_bytes < len(raw):
            raise GovernanceError(
                f"content exceeds active max_patch_bytes ({max_patch_bytes})"
            )

        if not candidate.parent.is_dir():
            raise FileNotFoundError(
                f"parent directory does not exist: {candidate.parent}"
            )
        if candidate.exists():
            raise FileExistsError(
                f"create-only target already exists: {relative_to_root}"
            )

        with candidate.open("xb") as handle:
            handle.write(raw)
            handle.flush()

        digest = hashlib.sha256(raw).hexdigest()
        return ToolExecutionResult(
            output={
                "path": relative_to_root,
                "created": True,
                "bytes": len(raw),
                "sha256": digest,
            },
            evidence=(
                {
                    "ref": f"workspace:{request.context.workspace_id}:{relative_to_root}",
                    "source_type": "workspace",
                    "workspace_id": request.context.workspace_id,
                    "path": str(candidate),
                    "hash": digest,
                    "verified": True,
                    "classification": "current_workspace_mutation",
                    "metadata": {
                        "relative_path": relative_to_root,
                        "operation_id": request.operation_id,
                        "tool_id": request.tool_id,
                    },
                },
            ),
        )

    return handler


class _ReceiptTrackingOrchestrator(GovernedToolOrchestrator):
    """Observe R6E receipts without changing dispatch or authorization semantics."""

    def __init__(self, *, registry: ToolRegistry) -> None:
        super().__init__(registry=registry)
        self._observed_receipts: list[ToolReceipt] = []
        self._observed_receipt_ids: set[str] = set()

    @property
    def observed_receipts(self) -> tuple[ToolReceipt, ...]:
        return tuple(self._observed_receipts)

    def invoke(self, request):
        receipt = super().invoke(request)
        if receipt.receipt_id not in self._observed_receipt_ids:
            self._observed_receipt_ids.add(receipt.receipt_id)
            self._observed_receipts.append(receipt)
        return receipt


class GovernedClineReasoningController:
    """ReasoningController adapter that composes existing governed coding owners."""

    def __init__(
        self,
        *,
        runtime: SessionMemoryRuntimeBridge,
        provider_id: str,
        provider_config: ProviderConfig,
    ) -> None:
        if not isinstance(runtime, SessionMemoryRuntimeBridge):
            raise TypeError("runtime must be SessionMemoryRuntimeBridge")
        if not isinstance(provider_config, ProviderConfig):
            raise TypeError("provider_config must be ProviderConfig")
        clean_provider = str(provider_id).strip()
        if not clean_provider:
            raise ValueError("provider_id must be non-empty")
        if runtime.session_state.provider_id != clean_provider:
            raise ValueError("provider identity does not match persisted session")
        if runtime.session_state.provider_model != provider_config.model.strip():
            raise ValueError("provider model does not match persisted session")

        state = runtime.session_state
        decision = resolve_mode(
            ModeRequest(
                intent="fix_issue",
                permission=state.permission or "read_only",
                runtime_policy=state.runtime_policy or "audit",
                workspace_root=str(runtime.workspace_root),
            )
        )
        if decision.mode != "coding":
            raise ValueError("governed coding controller requires resolved coding mode")

        self._runtime = runtime
        self._provider_id = clean_provider
        self._provider_config = provider_config
        self._context = ToolExecutionContext(
            mode_decision=decision,
            workspace_id=runtime.project_workspace_id,
            workspace_root=runtime.workspace_root,
            configured_root_id=runtime.project_workspace_id,
        )
        registry = ToolRegistry()
        registry.register(
            workspace_read_spec(),
            build_workspace_read_handler(EvidenceService()),
        )
        registry.register(
            workspace_create_candidate_text_spec(),
            build_workspace_create_candidate_text_handler(),
        )
        self._registry = registry
        self._orchestrator = _ReceiptTrackingOrchestrator(registry=registry)

    def run(self, request: LBERequest) -> LBEResponse:
        task_id = str(request.task_id or "").strip()
        if not task_id:
            raise ValueError("governed coding requires a task_id")

        turn_id = f"turn-{uuid4().hex}"
        worker = GovernedClineWorker()
        provider = {
            "provider_id": self._provider_id,
            "model_id": self._provider_config.model.strip(),
            "base_url": _cline_base_url(self._provider_config.endpoint),
        }
        if self._provider_config.api_key:
            provider["api_key"] = self._provider_config.api_key

        start = BridgeFrame(
            protocol_version=PROTOCOL_VERSION,
            message_id=f"py-start-{uuid4().hex}",
            message_type="runtime.start",
            session_id=self._runtime.session_id,
            turn_id=turn_id,
            payload={
                "provider": provider,
                "allowed_tools": [
                    _worker_tool_definition(spec) for spec in self._registry.specs()
                ],
                "system_prompt": (
                    "Operate only through the exposed LBE governed tools. "
                    "Do not claim LBE completion truth. For a requested new text "
                    "artifact, use workspace.create_candidate_text; it is create-only."
                ),
                "max_iterations": 8,
            },
        )
        execute = BridgeFrame(
            protocol_version=PROTOCOL_VERSION,
            message_id=f"py-turn-{uuid4().hex}",
            message_type="turn.execute",
            session_id=self._runtime.session_id,
            turn_id=turn_id,
            payload={"text": request.problem.strip()},
        )

        terminal: BridgeFrame | None = None
        bridge_error: Exception | None = None
        try:
            worker.start(start)
            terminal = worker.execute_turn(
                execute,
                orchestrator=self._orchestrator,
                context=self._context,
                timeout_seconds=max(30.0, float(self._provider_config.timeout_seconds) * 4),
            )
        except Exception as exc:  # fail closed at the bridge boundary
            bridge_error = exc
        finally:
            if worker.is_running:
                try:
                    worker.shutdown(
                        BridgeFrame(
                            protocol_version=PROTOCOL_VERSION,
                            message_id=f"py-shutdown-{uuid4().hex}",
                            message_type="runtime.shutdown",
                            session_id=self._runtime.session_id,
                            turn_id=turn_id,
                            payload={},
                        )
                    )
                except Exception:
                    worker.terminate()

        receipts = self._orchestrator.observed_receipts
        receipt_payload = [_receipt_payload(receipt) for receipt in receipts]
        mutated = any(
            receipt.status is ToolReceiptStatus.EXECUTED
            and receipt.tool_id == "workspace.create_candidate_text"
            for receipt in receipts
        )
        deterministic_result = {
            "runtime": "governed_cline",
            "turn_id": turn_id,
            "provider_id": self._provider_id,
            "provider_model": self._provider_config.model.strip(),
            "governed_tool_receipts": receipt_payload,
        }

        if bridge_error is not None:
            return self._response(
                task_id=task_id,
                deterministic_result=deterministic_result,
                outcome="ORCHESTRATION_ERROR",
                read_only=not mutated,
                error=OrchestrationError(
                    code="GOVERNED_CLINE_BRIDGE_ERROR",
                    message=f"{type(bridge_error).__name__}: {bridge_error}",
                ),
            )
        assert terminal is not None
        deterministic_result = {
            **deterministic_result,
            "terminal_message_type": terminal.message_type,
            "terminal_status": terminal.payload.get("status"),
            "provider_output": terminal.payload.get("output_text", ""),
            "lbe_completion_truth": terminal.payload.get("lbe_completion_truth"),
        }
        if terminal.message_type != "turn.completed":
            return self._response(
                task_id=task_id,
                deterministic_result=deterministic_result,
                outcome="ORCHESTRATION_ERROR",
                read_only=not mutated,
                error=OrchestrationError(
                    code=str(terminal.payload.get("code") or "CLINE_TURN_FAILED"),
                    message=str(
                        terminal.payload.get("message")
                        or "governed Cline turn did not complete"
                    ),
                ),
            )
        if terminal.payload.get("status") != "completed":
            return self._response(
                task_id=task_id,
                deterministic_result=deterministic_result,
                outcome="ORCHESTRATION_ERROR",
                read_only=not mutated,
                error=OrchestrationError(
                    code="CLINE_TURN_NOT_COMPLETED",
                    message=f"Cline terminal status was {terminal.payload.get('status')!r}",
                ),
            )
        if terminal.payload.get("lbe_completion_truth") is not False:
            return self._response(
                task_id=task_id,
                deterministic_result=deterministic_result,
                outcome="ORCHESTRATION_ERROR",
                read_only=not mutated,
                error=OrchestrationError(
                    code="INVALID_COMPLETION_AUTHORITY",
                    message="provider runtime attempted to assert LBE completion truth",
                ),
            )
        return self._response(
            task_id=task_id,
            deterministic_result=deterministic_result,
            outcome="COMPLETED",
            read_only=not mutated,
            error=None,
        )

    def _response(
        self,
        *,
        task_id: str,
        deterministic_result: Mapping[str, object],
        outcome: str,
        read_only: bool,
        error: OrchestrationError | None,
    ) -> LBEResponse:
        return LBEResponse(
            task_id=task_id,
            workspace_identity={
                "workspace_id": self._runtime.project_workspace_id,
                "configured_root_id": self._runtime.project_workspace_id,
                "target_project_root": str(self._runtime.workspace_root),
            },
            workspace_profile={
                "mode": "coding",
                "provider_id": self._provider_id,
                "governed_tools": [spec.tool_id for spec in self._registry.specs()],
            },
            plan=None,
            deterministic_result=dict(deterministic_result),
            explanation=None,
            outcome=outcome,
            proposal=None,
            error=error,
            read_only=read_only,
        )


def _worker_tool_definition(spec: ToolSpec) -> dict[str, object]:
    properties = {
        name: {"type": "string"}
        for name in (*spec.required_arguments, *spec.optional_arguments)
    }
    descriptions = {
        "workspace.read": "Read current workspace evidence through the LBE evidence owner.",
        "workspace.create_candidate_text": (
            "Create one new UTF-8 text file inside an existing allowed workspace "
            "directory. Fails if the file already exists."
        ),
    }
    return {
        "tool_id": spec.tool_id,
        "description": descriptions.get(spec.tool_id, f"LBE governed tool {spec.tool_id}"),
        "input_schema": {
            "type": "object",
            "properties": properties,
            "required": list(spec.required_arguments),
            "additionalProperties": False,
        },
        "timeout_ms": max(1, int(spec.timeout_seconds * 1000)),
    }


def _receipt_payload(receipt: ToolReceipt) -> dict[str, object]:
    authorization = receipt.authorization
    return {
        "receipt_id": receipt.receipt_id,
        "operation_id": receipt.operation_id,
        "tool_id": receipt.tool_id,
        "status": receipt.status.value,
        "authorization": None
        if authorization is None
        else {
            "verdict": authorization.verdict.value,
            "rationale": authorization.rationale,
        },
        "output": dict(receipt.output or {}),
        "evidence": [dict(item) for item in receipt.evidence],
        "error_code": receipt.error_code,
        "error_message": receipt.error_message,
    }


def _cline_base_url(endpoint: str) -> str:
    clean = str(endpoint).strip()
    parsed = urlsplit(clean)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("provider endpoint must be an absolute http(s) URL")
    if parsed.query or parsed.fragment:
        raise ValueError("provider endpoint query/fragment is not supported for Cline runtime")
    path = parsed.path.rstrip("/")
    suffix = "/chat/completions"
    if path.endswith(suffix):
        path = path[: -len(suffix)]
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))
