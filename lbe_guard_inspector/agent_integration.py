from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Mapping

from .memory import TaskStatus
from .reasoning_contracts import LBEResponse
from .runtime.completion_runtime import CodingCompletionRuntime
from .runtime.completion_evidence_producers import CompletionEvidenceProducers
from .runtime.mode_controller import ModeDecision, ModeRequest, resolve_mode
from .runtime.task_completion_policy import (
    DEFAULT_TASK_COMPLETION_POLICY_CATALOG,
    TaskCompletionPolicyCatalog,
)
from .runtime.tool_orchestration import ToolExecutionContext, ToolRequest
from .session_memory_runtime import ReasoningController, SessionMemoryRuntimeBridge


class AgentMode(StrEnum):
    CODING = "coding"
    AUDIT = "audit"
    INVESTIGATION = "investigation"


class AgentIntegrationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def to_dict(self) -> dict[str, str]:
        return {"error": self.code, "message": self.message}


@dataclass(frozen=True)
class AgentRequestEnvelope:
    request_id: str
    session_id: str
    task_id: str
    project_workspace_id: str
    workspace_root: str | Path
    mode: AgentMode
    operation_id: str
    arguments: Mapping[str, Any]

    def __post_init__(self) -> None:
        for name in (
            "request_id",
            "session_id",
            "task_id",
            "project_workspace_id",
            "operation_id",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise AgentIntegrationError("invalid_request", f"{name} must be a non-empty string")
        if not isinstance(self.mode, AgentMode):
            raise AgentIntegrationError("invalid_request", "mode must be an AgentMode")
        if not isinstance(self.arguments, Mapping):
            raise AgentIntegrationError("invalid_request", "arguments must be an object")
        root = Path(self.workspace_root).expanduser().resolve()
        object.__setattr__(self, "workspace_root", root)


@dataclass(frozen=True)
class AgentResultEnvelope:
    request_id: str
    session_id: str
    task_id: str
    operation_id: str
    mode: AgentMode
    mode_decision: ModeDecision
    status: TaskStatus
    outcome: str
    response: LBEResponse


class GovernedAgentGateway:
    """Session-bound entry point for external agents and future CLI/API transports.

    The gateway validates identity and routes work into existing LBE runtime
    owners. It does not grant capabilities, execute shell commands, or create a
    parallel reasoning/session authority.
    """

    _REASONING_OPERATION = "reasoning.inspect"
    _REASONING_ARGUMENTS = frozenset({"problem", "reference_context", "max_results"})
    _MODE_INTENTS = {
        AgentMode.CODING: "fix_issue",
        AgentMode.AUDIT: "inspect_workspace",
        AgentMode.INVESTIGATION: "diagnose_failure",
    }
    _CODING_TASK_CLASS = "coding_fix"

    def __init__(
        self,
        *,
        runtime: SessionMemoryRuntimeBridge,
        reasoning_controller: ReasoningController,
        completion_policy_catalog: TaskCompletionPolicyCatalog = DEFAULT_TASK_COMPLETION_POLICY_CATALOG,
    ) -> None:
        if not isinstance(completion_policy_catalog, TaskCompletionPolicyCatalog):
            raise TypeError("completion_policy_catalog must be TaskCompletionPolicyCatalog")
        self._runtime = runtime
        self._reasoning_controller = reasoning_controller
        self._completion_policy_catalog = completion_policy_catalog

    def invoke(self, request: AgentRequestEnvelope) -> AgentResultEnvelope:
        if not isinstance(request, AgentRequestEnvelope):
            raise AgentIntegrationError("invalid_request", "request must be AgentRequestEnvelope")
        mode_decision = self.resolve_runtime_mode(request)
        if request.operation_id != self._REASONING_OPERATION:
            raise AgentIntegrationError(
                "unsupported_operation",
                f"operation is not registered: {request.operation_id}",
            )
        unknown = sorted(set(request.arguments) - self._REASONING_ARGUMENTS)
        if unknown:
            raise AgentIntegrationError(
                "invalid_request",
                f"unsupported reasoning arguments: {unknown}",
            )
        problem = request.arguments.get("problem")
        if not isinstance(problem, str) or not problem.strip():
            raise AgentIntegrationError("invalid_request", "arguments.problem must be non-empty")
        reference_context = request.arguments.get("reference_context", ())
        if not isinstance(reference_context, tuple) or not all(
            isinstance(item, Mapping) for item in reference_context
        ):
            raise AgentIntegrationError(
                "invalid_request",
                "arguments.reference_context must be a tuple of objects",
            )
        max_results = request.arguments.get("max_results", 10)
        if isinstance(max_results, bool) or not isinstance(max_results, int) or max_results < 1:
            raise AgentIntegrationError(
                "invalid_request", "arguments.max_results must be a positive integer"
            )

        if request.mode is AgentMode.CODING:
            completion_runtime = CodingCompletionRuntime(runtime=self._runtime)
            self._establish_coding_contract(
                request=request,
                mode_decision=mode_decision,
                completion_runtime=completion_runtime,
            )
            producers = CompletionEvidenceProducers(runtime=self._runtime)
            task_baseline = producers.capture_workspace_snapshot()
            result = completion_runtime.run_reasoning(
                controller=self._reasoning_controller,
                problem=problem,
                task_id=request.task_id,
                reference_context=reference_context,
                max_results=max_results,
            )
            producers.produce_source_change(
                task_id=request.task_id,
                operation_id=request.operation_id,
                baseline=task_baseline,
            )
            producers.produce_focused_test(
                task_id=request.task_id,
                operation_id=request.operation_id,
            )
            producers.produce_git_status(
                task_id=request.task_id,
                operation_id=request.operation_id,
            )
            response = result.response
            state = result.task_state
        else:
            response = self._runtime.run_reasoning(
                controller=self._reasoning_controller,
                problem=problem,
                task_id=request.task_id,
                reference_context=reference_context,
                max_results=max_results,
            )
            state = self._runtime.load_task_status(task_id=request.task_id)
            if state is None:
                raise AgentIntegrationError(
                    "runtime_state_missing",
                    "reasoning completed without persisted task lifecycle state",
                )
        return AgentResultEnvelope(
            request_id=request.request_id,
            session_id=request.session_id,
            task_id=request.task_id,
            operation_id=request.operation_id,
            mode=request.mode,
            mode_decision=mode_decision,
            status=state.status,
            outcome=response.outcome,
            response=response,
        )

    def resolve_runtime_mode(self, request: AgentRequestEnvelope) -> ModeDecision:
        """Resolve R6B from persisted policy and bounded request identity.

        Request mode is checked as an identity assertion after resolution; it
        never supplies permission or runtime-policy authority.
        """
        self._validate_identity(request)
        state = self._runtime.session_state
        if state.permission is None or state.runtime_policy is None:
            raise AgentIntegrationError(
                "policy_state_missing",
                "persisted session lacks authoritative permission and runtime_policy",
            )
        decision = resolve_mode(ModeRequest(
            intent=self._MODE_INTENTS[request.mode],
            permission=state.permission,
            runtime_policy=state.runtime_policy,
            workspace_root=str(self._runtime.workspace_root),
        ))
        if decision.mode != state.mode or decision.mode != request.mode.value:
            raise AgentIntegrationError(
                "resolved_mode_mismatch",
                "R6B resolved mode contradicts persisted or request mode identity",
            )
        return decision

    def tool_execution_context(self, request: AgentRequestEnvelope) -> ToolExecutionContext:
        """Supply the R6B decision to the existing R6E context contract."""
        return ToolExecutionContext(
            mode_decision=self.resolve_runtime_mode(request),
            workspace_id=self._runtime.project_workspace_id,
            workspace_root=self._runtime.workspace_root,
            configured_root_id=self._runtime.project_workspace_id,
        )

    def _establish_coding_contract(
        self,
        *,
        request: AgentRequestEnvelope,
        mode_decision: ModeDecision,
        completion_runtime: CodingCompletionRuntime,
    ) -> None:
        existing = completion_runtime.load_contract(task_id=request.task_id)
        if existing is not None:
            return
        if self._MODE_INTENTS[request.mode] != "fix_issue":
            raise AgentIntegrationError(
                "completion_policy_missing",
                "no LBE completion policy applies to the governed coding task",
            )
        policy = self._completion_policy_catalog.find(
            operation_id=request.operation_id,
            task_class=self._CODING_TASK_CLASS,
            mode=mode_decision.mode,
        )
        if policy is None:
            raise AgentIntegrationError(
                "completion_policy_missing",
                "no LBE completion policy applies to the governed coding task",
            )
        completion_runtime.persist_contract(task_id=request.task_id, contract=policy.contract())

    def tool_request(
        self,
        *,
        request: AgentRequestEnvelope,
        tool_id: str,
        arguments: Mapping[str, Any],
    ) -> ToolRequest:
        """Create an R6E request without reconstructing policy authority."""
        return ToolRequest(
            operation_id=f"{request.operation_id}:{request.request_id}:{tool_id}",
            tool_id=tool_id,
            arguments=arguments,
            context=self.tool_execution_context(request),
        )

    def _validate_identity(self, request: AgentRequestEnvelope) -> None:
        if request.session_id != self._runtime.session_id:
            raise AgentIntegrationError("session_mismatch", "request session does not match runtime session")
        if request.project_workspace_id != self._runtime.project_workspace_id:
            raise AgentIntegrationError(
                "workspace_mismatch",
                "request project workspace does not match runtime workspace",
            )
        if Path(request.workspace_root).resolve() != self._runtime.workspace_root.resolve():
            raise AgentIntegrationError(
                "workspace_mismatch", "request workspace root does not match runtime workspace"
            )
        if request.mode.value != self._runtime.session_state.mode:
            raise AgentIntegrationError(
                "mode_mismatch",
                "request mode does not match persisted session mode",
            )
