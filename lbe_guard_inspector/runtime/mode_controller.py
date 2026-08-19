"""
Mode Controller — typed runtime policy boundary.

The controller sits between provider intent and private LBE authority. It:
1. Accepts intent + permission + runtime policy
2. Determines canonical runtime mode (coding / audit / investigation)
3. Maps that mode onto the existing public behavior-contract vocabulary
4. Returns mode + allowed_behaviors + capabilities

It does NOT:
- run guards
- know guard IDs
- modify files
- decide verdicts
- grant permissions beyond the supplied policy inputs
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from lbe_guard_inspector.behavior.contracts import (
    Mode as BehaviorMode,
    get_behaviors_for_intent,
    get_behaviors_for_mode,
    validate_mode_behavior,
)


Mode = Literal["coding", "audit", "investigation"]
Permission = Literal["read_only", "write_allowed", "audit_only", "elevated"]
RuntimePolicy = Literal["audit", "development", "strict", "permissive"]


@dataclass(frozen=True)
class ModeRequest:
    """Input to the mode controller. Provider intent is advisory; policy decides."""

    intent: str
    permission: Permission = "read_only"
    workspace_root: str = ""
    runtime_policy: RuntimePolicy = "audit"


@dataclass(frozen=True)
class ModeDecision:
    """Typed runtime mode and its bounded behavior/capability contract."""

    mode: Mode
    allowed_behaviors: tuple[str, ...]
    capabilities: tuple[str, ...]
    rationale: str


_PERMISSION_MODE: dict[Permission, Mode] = {
    "read_only": "audit",
    "audit_only": "audit",
    "write_allowed": "coding",
    "elevated": "coding",
}

# Keep existing persisted/configuration policy names backward-compatible while
# exposing the canonical runtime vocabulary at the decision boundary.
_POLICY_MODE_OVERRIDE: dict[RuntimePolicy, Mode | None] = {
    "audit": "audit",
    "development": "coding",
    "strict": "audit",
    "permissive": None,
}

_INVESTIGATION_INTENTS = frozenset(
    {
        "investigate_issue",
        "diagnose_failure",
        "trace_failure",
        "investigate_guard_failure",
    }
)

_AUDIT_INTENTS = frozenset(
    {
        "audit_workspace",
        "check_finding",
        "review_memory",
        "inspect_workspace",
        "verify_compliance",
    }
)


def _behavior_mode(mode: Mode) -> BehaviorMode:
    """Translate canonical runtime mode to the existing behavior vocabulary."""

    return "development" if mode == "coding" else "audit"


def _resolve_mode(
    intent: str,
    permission: Permission,
    runtime_policy: RuntimePolicy,
) -> tuple[Mode, str]:
    """Determine effective runtime mode from policy, intent, and permission."""

    forced = _POLICY_MODE_OVERRIDE.get(runtime_policy)
    if forced is not None:
        return forced, f"Runtime policy '{runtime_policy}' forces {forced} mode"

    base = _PERMISSION_MODE.get(permission, "audit")
    if intent in _INVESTIGATION_INTENTS:
        return "investigation", f"Intent '{intent}' requires investigation mode"
    if intent in _AUDIT_INTENTS and base == "coding":
        return "audit", f"Intent '{intent}' requires audit mode despite {permission} permission"
    return base, f"Permission '{permission}' maps to {base} mode"


def _resolve_capabilities(mode: Mode, allowed_behaviors: tuple[str, ...]) -> tuple[str, ...]:
    """Derive concrete capabilities from existing behavior contracts."""

    behavior_caps: dict[str, tuple[str, ...]] = {
        "require_current_workspace_evidence": ("inspect", "search", "compare", "verify"),
        "validation_before_acceptance": ("validate", "verify", "corroborate", "cross_check"),
        "evidence_boundary_enforcement": (
            "reference_inform",
            "workspace_prove",
            "guard_detect",
            "validation_confirm",
        ),
        "audit_mode_constraints": (
            "inspect",
            "collect_evidence",
            "report_findings",
            "register_finding",
        ),
        "development_mode_capabilities": (
            "discover",
            "propose",
            "test_candidate",
            "validate_proposal",
            "promote_after_validation",
        ),
        "finding_review_required": (
            "record_finding",
            "request_review",
            "verify_against_current",
            "categorize_finding",
        ),
        "memory_is_historical_context": (
            "read_memory",
            "use_as_context",
            "correlate_with_current",
        ),
        "use_only_approved_guards": (
            "list_approved_guards",
            "execute_approved_guard",
            "request_guard_execution",
        ),
        "proposed_rules_require_validation": (
            "propose_rule",
            "test_proposal",
            "validate_proposal",
            "submit_for_approval",
        ),
    }

    seen: set[str] = set()
    capabilities: list[str] = []
    for behavior in allowed_behaviors:
        for capability in behavior_caps.get(behavior, ()):
            if capability not in seen:
                capabilities.append(capability)
                seen.add(capability)

    if mode in {"audit", "investigation"}:
        write_capabilities = {
            "modify",
            "propose",
            "test_candidate",
            "promote_after_validation",
            "propose_rule",
            "test_proposal",
            "submit_for_approval",
        }
        capabilities = [cap for cap in capabilities if cap not in write_capabilities]

    return tuple(capabilities)


def resolve_mode(request: ModeRequest) -> ModeDecision:
    """Resolve canonical mode, allowed behaviors, and capabilities."""

    mode, rationale = _resolve_mode(request.intent, request.permission, request.runtime_policy)
    behavior_mode = _behavior_mode(mode)
    intent_behaviors = get_behaviors_for_intent(request.intent)

    if not intent_behaviors:
        mode_behaviors = get_behaviors_for_mode(behavior_mode)
        allowed_behaviors = tuple(behavior.name for behavior in mode_behaviors)
        return ModeDecision(
            mode=mode,
            allowed_behaviors=allowed_behaviors,
            capabilities=_resolve_capabilities(mode, allowed_behaviors),
            rationale=f"Unknown intent '{request.intent}': fell back to {mode} mode defaults. {rationale}",
        )

    allowed = tuple(
        behavior_name
        for behavior_name in intent_behaviors
        if validate_mode_behavior(behavior_mode, behavior_name)
    )
    capabilities = _resolve_capabilities(mode, allowed)
    return ModeDecision(
        mode=mode,
        allowed_behaviors=allowed,
        capabilities=capabilities,
        rationale=f"Intent '{request.intent}' resolved in {mode} mode. {rationale}",
    )


def get_supported_permissions() -> tuple[Permission, ...]:
    return tuple(sorted(_PERMISSION_MODE.keys()))


def get_supported_policies() -> tuple[RuntimePolicy, ...]:
    return tuple(sorted(_POLICY_MODE_OVERRIDE.keys()))
