"""Runtime-neutral coordination of bounded reasoning and deterministic LBE tools."""
from __future__ import annotations

import uuid
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable, Mapping

from agent import Context, GovernanceError
from audit_controller import AuditError, resolve_rule

from .contracts import ContractValidationError, validate_contract
from .evidence_service import EvidenceService
from .explanation_planner import ExplanationPlanner
from .guard_catalog import evidence_contract_for_guard, select_guard_catalog
from .guard_runner import GuardRunner
from .reasoning_guard_planner import GuardCandidate, GuardPlanner
from .project_profiler import ProjectProfiler
from .proposal_planner import ProposalPlanner
from .rule_gatekeeper import RuleGatekeeper
from .reasoning_contracts import (
    EvidenceRequest,
    ExplanationResult,
    LBERequest,
    LBEResponse,
    OrchestrationError,
    ReasoningBackend,
    ReasoningPlan,
    ReasoningRequest,
)
from .reasoning_planner import ReasoningPolicy
from .runtime.context_assembly import assemble_reasoning_context
from .workspace_identity import resolve_workspace_identity, scoped_context


_APPROVED_TOOLS = frozenset({"workspace.read"})


class LBERequestController:
    """Coordinates LBE dependencies without becoming a provider or authority."""

    def __init__(
        self,
        *,
        backend: ReasoningBackend,
        context: Context | None = None,
        context_loader: Callable[[], Context] = Context.load,
        profiler: ProjectProfiler | None = None,
        evidence_service: EvidenceService | None = None,
        catalog_selector: Callable[[dict[str, Any]], dict[str, Any]] = select_guard_catalog,
        runner: GuardRunner | None = None,
        rule_resolver: Callable[[str, str], Any] = resolve_rule,
        policy: ReasoningPolicy | None = None,
        guard_planner: GuardPlanner | None = None,
        explanation_planner: ExplanationPlanner | None = None,
        proposal_planner: ProposalPlanner | None = None,
    ) -> None:
        self._backend = backend
        self._context = context
        self._context_loader = context_loader
        self._profiler = profiler or ProjectProfiler()
        self._evidence_service = evidence_service or EvidenceService()
        self._catalog_selector = catalog_selector
        self._runner = runner or GuardRunner()
        self._rule_resolver = rule_resolver
        self._policy = policy or ReasoningPolicy()
        self._guard_planner = guard_planner or GuardPlanner()
        self._explanation_planner = explanation_planner or ExplanationPlanner()
        self._proposal_planner = proposal_planner

    def run(self, request: LBERequest) -> LBEResponse:
        """Run planning, deterministic inspection, and explanation in read-only mode."""
        try:
            return self._run(request)
        except _ControllerFailure as exc:
            return self._error_response(request, exc.code, str(exc), exc.details)
        except Exception as exc:  # provider failures and defensive boundary
            return self._error_response(request, "ORCHESTRATION_ERROR", f"{type(exc).__name__}: {exc}", ())

    def _run(self, request: LBERequest) -> LBEResponse:
        problem = _text(request.problem, "problem")
        context = self._context or self._context_loader()
        identity = resolve_workspace_identity(context, request.workspace_root)
        profile = self._profiler.profile(
            identity.target_project_root, configured_root_id=identity.configured_root_id
        )
        catalog = self._catalog_selector(profile)
        approved_guards = tuple(dict.fromkeys(
            [*catalog.get("foundation_guard_ids", []), *catalog.get("optional_guard_ids", [])]
        ))
        evidence_package = self._evidence_service.build_evidence_package(
            task_id=request.task_id or f"task-{uuid.uuid4()}",
            query=problem,
            workspace_id=identity.workspace_id,
            workspace_root=str(identity.target_project_root),
            max_results=request.max_results,
            roots=[identity.configured_root_id],
        )
        validated_evidence_package = validate_contract("evidence_package", evidence_package)
        reasoning_request = ReasoningRequest(
            problem=problem,
            workspace_identity={
                "configured_root_id": identity.configured_root_id,
                "target_project_root": str(identity.target_project_root),
                "workspace_id": identity.workspace_id,
            },
            workspace_profile=profile,
            approved_guard_ids=approved_guards,
            approved_tools=tuple(sorted(_APPROVED_TOOLS)),
            reference_context=assemble_reasoning_context(
                request_context=request.reference_context,
                indexed_reference_evidence=validated_evidence_package["indexed_reference_evidence"],
            ),
        )
        plan = _coerce_plan(self._backend.plan(reasoning_request))
        plan = replace(plan, explanation_focus=self._policy.normalize_explanation_focus(plan))
        self._validate_plan(plan, identity.target_project_root, approved_guards)
        if not plan.candidate_guard_ids:
            return self._response(
                request, identity, profile, plan, None, None, "INSUFFICIENT_EVIDENCE",
                OrchestrationError("NO_GUARD_SELECTED", "Reasoning plan selected no approved guard."),
            )
        unknown_in_candidates = sorted(set(plan.candidate_guard_ids) - set(approved_guards))
        if unknown_in_candidates:
            raise _ControllerFailure(
                "UNKNOWN_GUARD",
                "Reasoning plan requested unknown guard IDs.",
                tuple(unknown_in_candidates),
            )
        candidates = []
        for candidate_guard_id in plan.candidate_guard_ids:
            candidate_contract = evidence_contract_for_guard(candidate_guard_id)
            candidate_package = self._evidence_service.build_evidence_package(
                task_id=request.task_id or f"task-{uuid.uuid4()}",
                query=next(iter(candidate_contract.get("path_patterns", ("",))), ""),
                workspace_id=identity.workspace_id,
                workspace_root=str(identity.target_project_root),
                max_results=request.max_results,
                roots=[identity.configured_root_id],
                retrieval_mode="guard",
                rule_id=candidate_guard_id,
                path_patterns=list(candidate_contract.get("path_patterns", ())),
                evidence_requirements=list(candidate_contract.get("evidence_requirements", ())),
            )
            evidence_plan = self._policy.plan_evidence(
                guard_contract=candidate_contract,
                evidence_package=candidate_package,
            )
            candidates.append(
                GuardCandidate(
                    guard_id=candidate_guard_id,
                    reason=f"backend proposed guard {candidate_guard_id}",
                    evidence_plan=evidence_plan,
                )
            )
        selection = self._guard_planner.select(
            candidates=candidates,
            approved_guard_ids=approved_guards,
            workspace_profile=profile,
        )
        if not selection.executable:
            if selection.stop_reason == "UNKNOWN_GUARD":
                raise _ControllerFailure(
                    "UNKNOWN_GUARD",
                    f"GuardPlanner rejected unknown guard(s): {selection.rejected_guard_ids}",
                    selection.rejected_guard_ids,
                )
            if selection.stop_reason in {"INSUFFICIENT_EVIDENCE", "AMBIGUOUS_GUARD_SELECTION"}:
                return self._response(
                    request,
                    identity,
                    profile,
                    plan,
                    None,
                    None,
                    "INSUFFICIENT_EVIDENCE",
                    OrchestrationError(
                        selection.stop_reason,
                        f"GuardPlanner could not select a guard: {selection.stop_reason}",
                    ),
                )
            return self._response(
                request,
                identity,
                profile,
                plan,
                None,
                None,
                "ORCHESTRATION_ERROR",
                OrchestrationError(
                    selection.stop_reason,
                    f"GuardPlanner failed: {selection.stop_reason}",
                ),
            )
        plan = replace(plan, candidate_guard_ids=(selection.selected_guard_id,))
        if not plan.candidate_guard_ids:
            return self._response(
                request, identity, profile, plan, None, None, "INSUFFICIENT_EVIDENCE",
                OrchestrationError("NO_GUARD_SELECTED", "Reasoning plan selected no approved guard."),
            )

        guard_id = next(guard for guard in approved_guards if guard in plan.candidate_guard_ids)
        pack_id = _pack_for(guard_id)
        try:
            self._rule_resolver(pack_id, guard_id)
        except (AuditError, OSError, ValueError) as exc:
            raise _ControllerFailure("UNREGISTERED_GUARD", f"Approved guard is not registered: {guard_id}: {exc}") from exc
        evidence_contract = evidence_contract_for_guard(guard_id)
        decision = self._runner.run(
            problem=problem,
            workspace_root=str(identity.target_project_root),
            workspace_id=identity.workspace_id,
            pack_id=pack_id,
            rule_id=guard_id,
            guard_id=guard_id,
            roots=[identity.configured_root_id],
            extensions=evidence_contract.get("extensions"),
            reason=f"controller-selected guard inspection: {guard_id}",
            retrieval_mode="guard",
            query=problem,
            path_patterns=list(evidence_contract["path_patterns"]),
            evidence_requirements=list(evidence_contract["evidence_requirements"]),
        )
        guard_result = decision.get("guard_result")
        package = decision.get("evidence_package")
        if not isinstance(guard_result, Mapping) or not isinstance(package, Mapping):
            raise _ControllerFailure("INVALID_DETERMINISTIC_RESULT", "GuardRunner did not return guard_result and evidence_package.")
        try:
            validated_result = validate_contract("guard_result", guard_result)
            validated_package = validate_contract("evidence_package", package)
        except ContractValidationError as exc:
            raise _ControllerFailure("INVALID_DETERMINISTIC_RESULT", str(exc), tuple(exc.errors)) from exc
        outcome = self._explanation_planner.build_request(
            guard_result=validated_result,
            current_workspace_evidence=validated_package["current_workspace_evidence"],
            validation_evidence=validated_package["validation_evidence"],
            governance_state=validated_result["governance_state"],
            explanation_focus=plan.explanation_focus,
        )
        if not outcome.executable or outcome.request is None:
            return self._response(
                request, identity, profile, plan, validated_result, None, "ORCHESTRATION_ERROR",
                OrchestrationError(
                    outcome.stop_reason or "EXPLANATION_UNAVAILABLE",
                    f"Explanation could not be built: {outcome.stop_reason}",
                ),
            )
        try:
            explanation = _coerce_explanation(self._backend.explain(outcome.request))
        except Exception as exc:
            return self._response(
                request, identity, profile, plan, validated_result, None, "ORCHESTRATION_ERROR",
                OrchestrationError("EXPLANATION_FAILED", f"{type(exc).__name__}: {exc}"),
            )
        proposal = self._maybe_propose(
            context=context,
            identity=identity,
            plan=plan,
            pack_id=pack_id,
            validated_result=validated_result,
            validated_package=validated_package,
        )
        return self._response(request, identity, profile, plan, validated_result, explanation, "COMPLETED", None, proposal=proposal)

    def _validate_plan(self, plan: ReasoningPlan, root: Path, approved_guards: tuple[str, ...]) -> None:
        unknown_guards = sorted(set(plan.candidate_guard_ids) - set(approved_guards))
        if unknown_guards:
            raise _ControllerFailure("UNKNOWN_GUARD", "Reasoning plan requested unknown guard IDs.", tuple(unknown_guards))
        if plan.validation_requests:
            raise _ControllerFailure(
                "MODEL_VALIDATION_REQUEST_FORBIDDEN",
                "Reasoning plans must not select validation IDs; deterministic validation is owned by LBE.",
                tuple(plan.validation_requests),
            )
        for evidence in plan.evidence_requests:
            if evidence.tool_id not in _APPROVED_TOOLS:
                raise _ControllerFailure("UNKNOWN_TOOL", f"Reasoning plan requested unknown tool: {evidence.tool_id}")
            _bounded_path(root, evidence.path)
        if plan.candidate_guard_ids and not plan.evidence_requests:
            raise _ControllerFailure("MISSING_EVIDENCE_REQUEST", "A selected guard requires a bounded evidence request.")

    def _maybe_propose(self, *, context, identity, plan, pack_id, validated_result, validated_package):
        candidate = plan.proposal_candidate
        if candidate is None:
            return None
        if validated_package.get("contradictions"):
            return None
        planner = self._proposal_planner or ProposalPlanner(
            RuleGatekeeper(context=context, rule_resolver=self._rule_resolver)
        )
        provenance = {
            "origin": "lbe_reasoning_controller",
            "guard_result_id": validated_result.get("result_id"),
            "workspace_id": identity.workspace_id,
        }
        contradiction_result = validated_package.get("contradictions") or "NONE"
        outcome = planner.build(
            workspace_root=identity.target_project_root,
            pack_id=pack_id,
            guard_result=validated_result,
            evidence_package=validated_package,
            governance_state=validated_result["governance_state"],
            candidate=candidate,
            provenance=provenance,
            equivalent_rule_result="NONE",
            contradiction_result=contradiction_result,
        )
        if not outcome.executable or outcome.proposal is None:
            return None
        return outcome.proposal

    @staticmethod
    def _response(request, identity, profile, plan, result, explanation, outcome, error, proposal=None) -> LBEResponse:
        return LBEResponse(
            task_id=request.task_id or f"task-{uuid.uuid4()}",
            workspace_identity={"configured_root_id": identity.configured_root_id, "target_project_root": str(identity.target_project_root), "workspace_id": identity.workspace_id},
            workspace_profile=profile, plan=plan, deterministic_result=result,
            explanation=explanation, outcome=outcome, error=error, proposal=proposal,
        )

    def _error_response(self, request: LBERequest, code: str, message: str, details: tuple[str, ...]) -> LBEResponse:
        return LBEResponse(
            task_id=request.task_id or f"task-{uuid.uuid4()}", workspace_identity={}, workspace_profile={},
            plan=None, deterministic_result=None, explanation=None, outcome="ORCHESTRATION_ERROR",
            error=OrchestrationError(code, message, details),
        )


class _ControllerFailure(ValueError):
    def __init__(self, code: str, message: str, details: tuple[str, ...] = ()) -> None:
        super().__init__(message)
        self.code, self.details = code, details


def _coerce_plan(value: ReasoningPlan | Mapping[str, Any]) -> ReasoningPlan:
    return value if isinstance(value, ReasoningPlan) else ReasoningPlan.from_mapping(value)


def _coerce_explanation(value: ExplanationResult | Mapping[str, Any]) -> ExplanationResult:
    return value if isinstance(value, ExplanationResult) else ExplanationResult.from_mapping(value)


def _bounded_path(root: Path, value: str) -> None:
    path = Path(value)
    semantic_parts = tuple(
        part.casefold()
        for part in value.replace(chr(92), "/").split("/")
        if part not in {"", "."}
    )
    root_parts = tuple(
        part.strip(chr(92) + "/").rstrip(":").casefold()
        for part in root.resolve().parts
        if part.strip(chr(92) + "/").rstrip(":")
    )
    if root_parts and semantic_parts[: len(root_parts)] == root_parts:
        raise _ControllerFailure(
            "OUT_OF_WORKSPACE_PATH",
            f"Evidence path reconstructs the workspace root: {value}",
        )
    if path.is_absolute() or ".." in path.parts:
        raise _ControllerFailure("OUT_OF_WORKSPACE_PATH", f"Evidence path escapes the workspace: {value}")
    try:
        (root / path).resolve().relative_to(root)
    except ValueError as exc:
        raise _ControllerFailure("OUT_OF_WORKSPACE_PATH", f"Evidence path escapes the workspace: {value}") from exc


def _pack_for(guard_id: str) -> str:
    prefix = guard_id.split(".", 1)[0]
    if prefix == "module_registry":
        return "module_registry"
    return prefix


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _ControllerFailure("INVALID_REQUEST", f"{field} must be a non-empty string")
    return value.strip()
