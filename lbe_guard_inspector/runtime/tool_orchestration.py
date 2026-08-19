"""Governed tool orchestration for the R6E runtime slice.

The orchestrator owns lifecycle ordering only: registered lookup, deterministic
R6C authorization, bounded handler invocation, structured receipts, and
operation-id idempotency. Tool implementations remain separate services.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol
import uuid

from ..evidence_service import EvidenceService
from .authorization_resolver import (
    AuthorizationDecision,
    AuthorizationRequest,
    AuthorizationVerdict,
    resolve_authorization,
)
from .mode_controller import ModeDecision


class ToolAccessClass(StrEnum):
    READ = "read"
    WRITE = "write"


class ToolNetworkBehavior(StrEnum):
    NONE = "none"
    OPTIONAL = "optional"
    REQUIRED = "required"


class ToolRiskClass(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ToolReceiptStatus(StrEnum):
    EXECUTED = "EXECUTED"
    DENIED = "DENIED"
    ESCALATED = "ESCALATED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class ToolSpec:
    tool_id: str
    capability: str
    required_arguments: tuple[str, ...]
    optional_arguments: tuple[str, ...] = ()
    access_class: ToolAccessClass = ToolAccessClass.READ
    network_behavior: ToolNetworkBehavior = ToolNetworkBehavior.NONE
    risk_class: ToolRiskClass = ToolRiskClass.LOW
    timeout_seconds: float = 30.0
    retry_policy: str = "none"
    preconditions: tuple[str, ...] = ()
    expected_evidence: tuple[str, ...] = ()
    failure_modes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.tool_id, str) or not self.tool_id.strip():
            raise ValueError("tool_id must be a non-empty string")
        if not isinstance(self.capability, str) or not self.capability.strip():
            raise ValueError("capability must be a non-empty string")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        overlap = set(self.required_arguments) & set(self.optional_arguments)
        if overlap:
            raise ValueError(f"tool arguments cannot be both required and optional: {sorted(overlap)}")


@dataclass(frozen=True)
class ToolExecutionContext:
    mode_decision: ModeDecision
    workspace_id: str
    workspace_root: str | Path
    configured_root_id: str
    within_workspace_scope: bool = True
    explicitly_forbidden: bool = False
    destructive: bool = False
    destructive_authorized: bool = False
    persistent_policy_change: bool = False
    persistent_policy_authorized: bool = False
    intent_scope_conflict: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.mode_decision, ModeDecision):
            raise TypeError("mode_decision must be a ModeDecision")
        for name in ("workspace_id", "configured_root_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        object.__setattr__(self, "workspace_root", Path(self.workspace_root).expanduser().resolve())


@dataclass(frozen=True)
class ToolRequest:
    operation_id: str
    tool_id: str
    arguments: Mapping[str, Any]
    context: ToolExecutionContext

    def __post_init__(self) -> None:
        if not isinstance(self.operation_id, str) or not self.operation_id.strip():
            raise ValueError("operation_id must be a non-empty string")
        if not isinstance(self.tool_id, str) or not self.tool_id.strip():
            raise ValueError("tool_id must be a non-empty string")
        if not isinstance(self.arguments, Mapping):
            raise TypeError("arguments must be a mapping")
        if not isinstance(self.context, ToolExecutionContext):
            raise TypeError("context must be ToolExecutionContext")


@dataclass(frozen=True)
class ToolExecutionResult:
    output: Mapping[str, Any]
    evidence: tuple[Mapping[str, Any], ...] = ()


@dataclass(frozen=True)
class ToolReceipt:
    operation_id: str
    tool_id: str
    status: ToolReceiptStatus
    authorization: AuthorizationDecision | None
    output: Mapping[str, Any] | None = None
    evidence: tuple[Mapping[str, Any], ...] = ()
    error_code: str | None = None
    error_message: str | None = None
    receipt_id: str = field(default_factory=lambda: f"receipt-{uuid.uuid4().hex}")


class ToolHandler(Protocol):
    def __call__(self, request: ToolRequest) -> ToolExecutionResult: ...


@dataclass(frozen=True)
class RegisteredTool:
    spec: ToolSpec
    handler: ToolHandler


class ToolRegistry:
    """Explicit registry; unregistered model requests cannot execute."""

    def __init__(self) -> None:
        self._tools: dict[str, RegisteredTool] = {}

    def register(self, spec: ToolSpec, handler: ToolHandler) -> None:
        if spec.tool_id in self._tools:
            raise ValueError(f"tool already registered: {spec.tool_id}")
        self._tools[spec.tool_id] = RegisteredTool(spec=spec, handler=handler)

    def get(self, tool_id: str) -> RegisteredTool | None:
        return self._tools.get(str(tool_id).strip())

    def specs(self) -> tuple[ToolSpec, ...]:
        return tuple(self._tools[key].spec for key in sorted(self._tools))


class GovernedToolOrchestrator:
    """Run registered tools only after R6C authorization succeeds."""

    def __init__(
        self,
        *,
        registry: ToolRegistry,
        authorization_resolver: Callable[[AuthorizationRequest], AuthorizationDecision] = resolve_authorization,
    ) -> None:
        self._registry = registry
        self._authorization_resolver = authorization_resolver
        self._receipts: dict[str, ToolReceipt] = {}

    def invoke(self, request: ToolRequest) -> ToolReceipt:
        if not isinstance(request, ToolRequest):
            raise TypeError("request must be ToolRequest")
        prior = self._receipts.get(request.operation_id)
        if prior is not None:
            return prior

        registered = self._registry.get(request.tool_id)
        if registered is None:
            return self._remember(ToolReceipt(
                operation_id=request.operation_id,
                tool_id=request.tool_id,
                status=ToolReceiptStatus.FAILED,
                authorization=None,
                error_code="UNREGISTERED_TOOL",
                error_message=f"tool is not registered: {request.tool_id}",
            ))

        argument_error = _validate_arguments(registered.spec, request.arguments)
        if argument_error is not None:
            return self._remember(ToolReceipt(
                operation_id=request.operation_id,
                tool_id=request.tool_id,
                status=ToolReceiptStatus.FAILED,
                authorization=None,
                error_code="INVALID_TOOL_ARGUMENTS",
                error_message=argument_error,
            ))

        context = request.context
        authorization = self._authorization_resolver(AuthorizationRequest(
            mode_decision=context.mode_decision,
            capability=registered.spec.capability,
            within_workspace_scope=context.within_workspace_scope,
            explicitly_forbidden=context.explicitly_forbidden,
            destructive=context.destructive,
            destructive_authorized=context.destructive_authorized,
            persistent_policy_change=context.persistent_policy_change,
            persistent_policy_authorized=context.persistent_policy_authorized,
            intent_scope_conflict=context.intent_scope_conflict,
        ))
        if authorization.verdict is AuthorizationVerdict.DENY:
            return self._remember(ToolReceipt(
                operation_id=request.operation_id,
                tool_id=request.tool_id,
                status=ToolReceiptStatus.DENIED,
                authorization=authorization,
                error_code="AUTHORIZATION_DENIED",
                error_message=authorization.rationale,
            ))
        if authorization.verdict is AuthorizationVerdict.ESCALATE:
            return self._remember(ToolReceipt(
                operation_id=request.operation_id,
                tool_id=request.tool_id,
                status=ToolReceiptStatus.ESCALATED,
                authorization=authorization,
                error_code="AUTHORIZATION_REQUIRED",
                error_message=authorization.rationale,
            ))

        try:
            result = registered.handler(request)
            if not isinstance(result, ToolExecutionResult):
                raise TypeError("tool handler must return ToolExecutionResult")
        except Exception as exc:
            return self._remember(ToolReceipt(
                operation_id=request.operation_id,
                tool_id=request.tool_id,
                status=ToolReceiptStatus.FAILED,
                authorization=authorization,
                error_code="TOOL_EXECUTION_FAILED",
                error_message=f"{type(exc).__name__}: {exc}",
            ))

        return self._remember(ToolReceipt(
            operation_id=request.operation_id,
            tool_id=request.tool_id,
            status=ToolReceiptStatus.EXECUTED,
            authorization=authorization,
            output=dict(result.output),
            evidence=tuple(dict(item) for item in result.evidence),
        ))

    def receipt(self, operation_id: str) -> ToolReceipt | None:
        return self._receipts.get(operation_id)

    def _remember(self, receipt: ToolReceipt) -> ToolReceipt:
        self._receipts[receipt.operation_id] = receipt
        return receipt


def workspace_read_spec() -> ToolSpec:
    return ToolSpec(
        tool_id="workspace.read",
        capability="inspect",
        required_arguments=("path",),
        access_class=ToolAccessClass.READ,
        network_behavior=ToolNetworkBehavior.NONE,
        risk_class=ToolRiskClass.LOW,
        timeout_seconds=30.0,
        retry_policy="transient_read_failure_only",
        preconditions=("relative workspace path", "active workspace scope"),
        expected_evidence=("current workspace evidence", "content hash"),
        failure_modes=("invalid path", "missing file", "read failure", "authorization failure"),
    )


def build_workspace_read_handler(evidence_service: EvidenceService) -> ToolHandler:
    """Delegate real workspace reads to the existing EvidenceService owner."""
    if not isinstance(evidence_service, EvidenceService):
        raise TypeError("evidence_service must be EvidenceService")

    def handler(request: ToolRequest) -> ToolExecutionResult:
        raw_path = request.arguments["path"]
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise ValueError("path must be a non-empty string")
        path = raw_path.replace("\\", "/").strip()
        candidate = Path(path)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise ValueError("path must stay within the active workspace")

        context = request.context
        package = evidence_service.build_evidence_package(
            task_id=request.operation_id,
            query=path,
            workspace_id=context.workspace_id,
            workspace_root=str(context.workspace_root),
            max_results=1,
            roots=[context.configured_root_id],
            retrieval_mode="guard",
            rule_id="workspace.read",
            path_patterns=[path],
            evidence_requirements=["explicit governed workspace.read request"],
        )
        evidence = tuple(dict(item) for item in package.get("current_workspace_evidence", ()))
        return ToolExecutionResult(
            output={
                "path": path,
                "evidence_count": len(evidence),
                "missing_evidence": list(package.get("missing_evidence", ())),
            },
            evidence=evidence,
        )

    return handler


def _validate_arguments(spec: ToolSpec, arguments: Mapping[str, Any]) -> str | None:
    allowed = set(spec.required_arguments) | set(spec.optional_arguments)
    unknown = sorted(set(arguments) - allowed)
    if unknown:
        return f"unsupported arguments for {spec.tool_id}: {unknown}"
    missing = sorted(name for name in spec.required_arguments if name not in arguments)
    if missing:
        return f"missing required arguments for {spec.tool_id}: {missing}"
    return None
