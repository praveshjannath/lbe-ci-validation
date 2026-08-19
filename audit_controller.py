from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any, Callable
from lbe_guard_inspector.project_profiler import ProjectProfiler
from lbe_guard_inspector.project_snapshots import ProjectSnapshotStore
from lbe_guard_inspector.workspace_identity import resolve_workspace_identity, scoped_context
from lbe_guard_inspector.guard_catalog import (
    FOUNDATION_GUARD_IDS,
    resolve_foundation_guards,
    select_guard_catalog,
)

# Keep one module identity when this file is executed directly.
# Rule packs may import ``audit_controller.RuleResult``; without this alias,
# running this file as a script would create a second, incompatible class.
if __name__ == "__main__":
    sys.modules.setdefault("audit_controller", sys.modules[__name__])

try:
    from agent import (
        STATE_DIR,
        Context,
        GovernanceError,
        inspect_file,
        search_workspace,
        write_json,
    )
except ImportError as exc:  # pragma: no cover - defensive
    raise RuntimeError(
        "audit_controller requires agent.py in the same directory or Python path"
    ) from exc


REPORT_PATH = STATE_DIR / "audit_report.json"
RULES_DIR = Path(__file__).resolve().parent / "rules"
RULES_DIR.mkdir(parents=True, exist_ok=True)

VALID_RULE_STATUSES = frozenset({
    "passed",
    "failed",
    "blocked",
    "not_applicable",
})
_OVERRIDABLE_FOUNDATION_GUARD_IDS = frozenset({"generic.forbidden_roots"})


class AuditError(RuntimeError):
    """Raised when an audit cannot be constructed or a rule violates its contract."""


@dataclass(frozen=True)
class RuleResult:
    rule_id: str
    status: str
    message: str
    evidence: dict[str, Any] = field(default_factory=dict)
    severity: str = "error"
    required: bool = True
    fast_fail: bool = False


@dataclass
class AuditReport:
    audit_id: str
    started_at: str
    completed_at: str
    project_type: str
    packs_evaluated: list[str]
    passed: int = 0
    failed: int = 0
    blocked: int = 0
    not_applicable: int = 0
    summary: str = ""
    results: list[RuleResult] = field(default_factory=list)
    inventory: dict[str, Any] = field(default_factory=dict)
    skipped_gates: list[dict[str, Any]] = field(default_factory=list)
    skipped_packs: list[dict[str, Any]] = field(default_factory=list)
    project_profile: dict[str, Any] = field(default_factory=dict)
    profile_snapshot: dict[str, Any] = field(default_factory=dict)
    guard_selection: list[dict[str, Any]] = field(default_factory=list)
    snapshot_comparison: dict[str, Any] = field(default_factory=dict)
    foundation_guard_execution: dict[str, Any] = field(default_factory=dict)
    optional_guard_execution: list[dict[str, Any]] = field(default_factory=list)
    audit_status: str = "completed"
    guard_catalog: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "audit_id": self.audit_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "project_type": self.project_type,
            "packs_evaluated": self.packs_evaluated,
            "passed": self.passed,
            "failed": self.failed,
            "blocked": self.blocked,
            "not_applicable": self.not_applicable,
            "summary": self.summary,
            "inventory": self.inventory,
            "skipped_gates": self.skipped_gates,
            "skipped_packs": self.skipped_packs,
            "project_profile": self.project_profile,
            "profile_snapshot": self.profile_snapshot,
            "guard_selection": self.guard_selection,
            "snapshot_comparison": self.snapshot_comparison,
            "foundation_guard_execution": self.foundation_guard_execution,
            "optional_guard_execution": self.optional_guard_execution,
            "audit_status": self.audit_status,
            "guard_catalog": self.guard_catalog,
            "results": [
                {
                    "rule_id": result.rule_id,
                    "status": result.status,
                    "message": result.message,
                    "evidence": result.evidence,
                    "severity": result.severity,
                    "required": result.required,
                    "fast_fail": result.fast_fail,
                }
                for result in self.results
            ],
        }


RuleFunction = Callable[[Context, dict[str, Any]], RuleResult]
_rule_registry: dict[str, dict[str, RuleFunction]] = {}


def register_rule(pack_id: str, rule_id: str, func: RuleFunction) -> None:
    """Register a rule programmatically, primarily for tests or built-in packs."""
    normalized_pack = pack_id.strip().lower()
    normalized_rule = rule_id.strip()
    if not normalized_pack or not normalized_rule:
        raise AuditError("pack_id and rule_id must be non-empty")
    if not callable(func):
        raise AuditError(f"Rule is not callable: {normalized_pack}.{normalized_rule}")
    _rule_registry.setdefault(normalized_pack, {})[normalized_rule] = func


def _utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _load_module(pack_id: str, pack_path: Path) -> ModuleType:
    module_name = f"lbe_rule_pack_{pack_id}_{abs(hash(pack_path))}"
    spec = importlib.util.spec_from_file_location(module_name, pack_path)
    if spec is None or spec.loader is None:
        raise AuditError(f"Unable to construct loader for rule pack: {pack_path}")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        raise AuditError(
            f"Rule pack could not be loaded: {pack_path}: {type(exc).__name__}: {exc}"
        ) from exc
    return module


def _load_rule_pack(pack_id: str) -> dict[str, RuleFunction]:
    normalized = pack_id.strip().lower()
    if not normalized:
        raise AuditError("Rule pack ID cannot be empty")
    if normalized in _rule_registry:
        return _rule_registry[normalized]

    pack_path = RULES_DIR / f"{normalized}.py"
    if not pack_path.exists():
        raise AuditError(f"Rule pack not found: {pack_path}")

    module = _load_module(normalized, pack_path)
    functions: dict[str, RuleFunction] = {}
    for name in sorted(dir(module)):
        value = getattr(module, name)
        if callable(value) and name.startswith("rule_"):
            functions[name] = value

    if not functions:
        raise AuditError(f"No rule_* functions found in {pack_path}")

    _rule_registry[normalized] = functions
    return functions
def resolve_rule(pack_id: str, rule_id: str) -> RuleFunction:
    """Resolve a single registered rule to its executable function.

    Unlike :func:`_load_rule_pack` (which keys the registry by Python function
    name), this looks a rule up by its registered ``rule_id`` so a caller can
    select and execute one specific deterministic guard without running an
    entire pack.
    """
    normalized_pack = pack_id.strip().lower()
    normalized_rule = rule_id.strip()
    if not normalized_pack or not normalized_rule:
        raise AuditError("pack_id and rule_id must be non-empty")

    pack_path = RULES_DIR / f"{normalized_pack}.py"
    if not pack_path.exists():
        raise AuditError(f"Rule pack not found: {pack_path}")

    registered = _rule_registry.get(normalized_pack, {})
    if normalized_rule not in registered:
        # (Re)load the pack module so register_rule() populates rule_id keys.
        _load_module(normalized_pack, pack_path)
        registered = _rule_registry.get(normalized_pack, {})

    if normalized_rule not in registered:
        available = sorted(registered)
        raise AuditError(
            f"Rule not found: {normalized_pack}.{normalized_rule} "
            f"(available: {available})"
        )
    return registered[normalized_rule]


def run_rule(
    pack_id: str,
    rule_id: str,
    ctx: Context,
    params: dict[str, Any] | None = None,
) -> RuleResult:
    """Resolve and execute a single registered deterministic rule.

    Mirrors the per-rule execution and exception handling of :func:`run_audit`
    but runs only the requested rule.  Governance or audit errors are reported
    as ``blocked``; unexpected errors as ``failed``.
    """
    function = resolve_rule(pack_id, rule_id)
    resolved_params: dict[str, Any] = {
        "roots": [],
        "project_type": "generic",
        "inventory": {},
    }
    if params:
        resolved_params.update(params)

    try:
        result = function(ctx, resolved_params)
    except (GovernanceError, AuditError) as exc:
        return RuleResult(
            rule_id=rule_id,
            status="blocked",
            message=str(exc),
        )
    except Exception as exc:  # pragma: no cover - defensive
        return RuleResult(
            rule_id=rule_id,
            status="failed",
            message=f"{type(exc).__name__}: {exc}",
            evidence={"execution_error": type(exc).__name__},
        )

    if not isinstance(result, RuleResult):
        raise AuditError(
            f"Rule {pack_id}.{rule_id} must return RuleResult, "
            f"not {type(result).__name__}"
        )
    return result




def _build_file_inventory(ctx: Context, roots: list[str] | None) -> dict[str, Any]:
    files: list[str] = []
    unreadable_directories: list[str] = []
    skipped_dirs = {
        ".git",
        ".lbe",
        "node_modules",
        "dist",
        "release-public",
        "release-exec",
        "__pycache__",
    }
    selected = set(roots) if roots else None
    targets = [root for root in ctx.roots if selected is None or root.name in selected]

    for knowledge_root in targets:
        queue = [knowledge_root.path]
        while queue:
            current = queue.pop(0)
            try:
                entries = sorted(
                    current.iterdir(),
                    key=lambda path: (not path.is_dir(), path.name.lower()),
                )
            except (OSError, PermissionError):
                unreadable_directories.append(str(current))
                continue

            for entry in entries:
                try:
                    if entry.is_dir():
                        if (
                            entry.name in skipped_dirs
                            or entry.name.startswith(".")
                            or entry.name.startswith("$")
                        ):
                            continue
                        queue.append(entry)
                    elif entry.is_file():
                        files.append(str(entry))
                except (OSError, PermissionError):
                    continue

    return {
        "files_considered": len(files),
        "files": files,
        "roots": [root.name for root in targets],
        "unreadable_directories": unreadable_directories[:50],
        "unreadable_directory_count": len(unreadable_directories),
    }


def detect_project_type(ctx: Context) -> str:
    """Detect CEP from indexed manifests; otherwise return generic."""
    try:
        result = search_workspace(
            ctx,
            "manifest.json",
            max_results=50,
            extensions=[".json"],
        )
    except Exception:
        return "generic"

    if result.get("outcome") != "matches_found":
        return "generic"

    for item in result.get("results", []):
        path = item.get("path")
        if not isinstance(path, str):
            continue
        try:
            content = str(inspect_file(ctx, path).get("content", ""))
        except Exception:
            continue
        lowered = content.lower()
        if "csxs" in lowered or "cep" in lowered or "extendscript" in lowered:
            return "cep"

    return "generic"


def _record_result(report: AuditReport, result: RuleResult) -> None:
    if result.status not in VALID_RULE_STATUSES:
        raise AuditError(
            f"Rule {result.rule_id} returned invalid status: {result.status}"
        )
    report.results.append(result)
    current = getattr(report, result.status)
    setattr(report, result.status, current + 1)


def _derive_summary(report: AuditReport) -> str:
    if report.skipped_packs or report.failed > 0:
        return "fail"

    required_blocked = any(
        result.status == "blocked" and result.required
        for result in report.results
    )
    if required_blocked:
        return "incomplete"

    if report.blocked > 0:
        return "pass_with_notes"

    applicable = report.passed + report.failed + report.blocked
    if applicable == 0 and report.not_applicable > 0:
        return "not_applicable"

    return "pass"


def _evidence_refs(evidence: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    for key in ("path", "registry_path"):
        value = evidence.get(key)
        if isinstance(value, str) and value:
            refs.append(value)
    for item in evidence.get("hits", []):
        if isinstance(item, str):
            refs.append(item)
        elif isinstance(item, dict) and isinstance(item.get("path"), str):
            refs.append(item["path"])
    return list(dict.fromkeys(refs))


def _validate_foundation_overrides(
    value: Any,
    required_guard_ids: tuple[str, ...],
) -> dict[str, dict[str, Any]]:
    if value is None:
        return {}
    if not isinstance(value, list):
        raise AuditError("foundation_overrides must be a list of structured acknowledgments")
    accepted: dict[str, dict[str, Any]] = {}
    for item in value:
        if not isinstance(item, dict):
            raise AuditError("foundation override must be an object")
        guard_id = item.get("guard_id")
        if guard_id not in required_guard_ids:
            raise AuditError(f"Unknown foundation guard override: {guard_id}")
        if guard_id not in _OVERRIDABLE_FOUNDATION_GUARD_IDS:
            raise AuditError(f"Foundation guard is not overridable: {guard_id}")
        if item.get("acknowledged") is not True:
            raise AuditError(f"Foundation override requires acknowledged: true for {guard_id}")
        reason = item.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            raise AuditError(f"Foundation override requires a non-empty reason for {guard_id}")
        if item.get("requested_by") != "user":
            raise AuditError(f"Foundation override must be requested_by: user for {guard_id}")
        if guard_id in accepted:
            raise AuditError(f"Duplicate foundation override: {guard_id}")
        accepted[guard_id] = {
            "guard_id": guard_id,
            "acknowledged": True,
            "reason": reason.strip(),
            "requested_by": "user",
        }
    return accepted


def _run_foundation_gate(
    report: AuditReport,
    ctx: Context,
    params: dict[str, Any],
    foundation_overrides: Any,
) -> bool:
    resolved = resolve_foundation_guards()
    guards = resolved["guards"]
    required_guard_ids = tuple(item["guard_id"] for item in guards)
    execution = {
        "required": list(required_guard_ids),
        "resolved_applicability": resolved,
        "order": list(required_guard_ids),
        "results": [],
        "stop_reason": None,
        "gate_opened": False,
        "first_blocking_guard_id": None,
    }
    report.foundation_guard_execution = execution
    try:
        overrides = _validate_foundation_overrides(foundation_overrides, required_guard_ids)
    except AuditError as exc:
        execution["stop_reason"] = str(exc)
        execution["first_blocking_guard_id"] = (
            foundation_overrides[0].get("guard_id")
            if isinstance(foundation_overrides, list)
            and foundation_overrides
            and isinstance(foundation_overrides[0], dict)
            else None
        )
        report.audit_status = "BLOCKED"
        report.summary = "foundation_gate_failed"
        return False

    for index, guard in enumerate(guards, start=1):
        guard_id = guard["guard_id"]
        override = overrides.get(guard_id)
        if override is not None:
            execution["results"].append({
                "guard_id": guard_id,
                "execution_index": index,
                "status": "overridden",
                "evidence_refs": [],
                "evidence": {},
                "override": override,
            })
            continue
        try:
            result = run_rule(guard["pack_id"], guard_id, ctx, params)
        except AuditError as exc:
            result = RuleResult(guard_id, "blocked", str(exc))
        if result.status == "not_applicable" or result.evidence.get("execution_error"):
            result = RuleResult(
                guard_id,
                "blocked",
                f"Foundation guard could not execute reliably: {result.message}",
                result.evidence,
                severity=result.severity,
                required=result.required,
                fast_fail=result.fast_fail,
            )
        record = {
            "guard_id": guard_id,
            "execution_index": index,
            "status": result.status,
            "evidence_refs": _evidence_refs(result.evidence),
            "evidence": result.evidence,
            "message": result.message,
        }
        execution["results"].append(record)
        _record_result(report, result)
        if result.status != "passed":
            execution["stop_reason"] = f"FOUNDATION_GATE_FAILED: {guard_id}: {result.message}"
            execution["first_blocking_guard_id"] = guard_id
            report.audit_status = "BLOCKED"
            report.summary = "foundation_gate_failed"
            return False

    if overrides:
        report.audit_status = "completed_with_overrides"
        report.summary = "completed_with_overrides"
    execution["gate_opened"] = True
    return True


def run_audit(
    *,
    pack_ids: list[str] | None = None,
    project_type: str | None = None,
    roots: list[str] | None = None,
    workspace_root: str | Path | None = None,
    foundation_overrides: list[dict[str, Any]] | None = None,
    ctx: Context | None = None,
) -> AuditReport:
    resolved_ctx = ctx or Context.load()
    target_identity = None
    if workspace_root is not None:
        target_identity = resolve_workspace_identity(resolved_ctx, workspace_root)
        resolved_ctx = scoped_context(resolved_ctx, target_identity)
        roots = [target_identity.configured_root_id]
    known_roots = {root.name for root in resolved_ctx.roots}

    normalized_roots = None
    if roots:
        normalized_roots = [root.strip().lower() for root in roots if root.strip()]
        unknown = sorted(set(normalized_roots) - known_roots)
        if unknown:
            raise AuditError(f"Unknown roots: {unknown}")

    report = AuditReport(
        audit_id=uuid.uuid4().hex,
        started_at=_utc_now(),
        completed_at="",
        project_type=(project_type or "generic").strip().lower(),
        packs_evaluated=[],
    )
    report.inventory = _build_file_inventory(resolved_ctx, normalized_roots)
    base_params = {
        "roots": normalized_roots,
        "workspace_root": (
            str(target_identity.target_project_root)
            if target_identity is not None
            else None
        ),
        "workspace_id": (
            target_identity.workspace_id
            if target_identity is not None
            else None
        ),
        "project_type": report.project_type,
        "inventory": report.inventory,
    }
    if not _run_foundation_gate(report, resolved_ctx, base_params, foundation_overrides):
        report.completed_at = _utc_now()
        return report

    selected_roots = [root for root in resolved_ctx.roots if normalized_roots is None or root.name in normalized_roots]
    profiler = ProjectProfiler()
    profiles = [
        profiler.profile(
            root.path,
            configured_root_id=(
                target_identity.configured_root_id
                if target_identity is not None
                else root.name
            ),
        )
        for root in selected_roots
    ]
    confident = [profile for profile in profiles if profile["outcome"] == "profiled"]
    audit_type = (project_type or (confident[0]["project_types"][0] if len(confident) == 1 else "generic")).strip().lower()
    report.project_type = audit_type
    requested = [pack.strip().lower() for pack in pack_ids] if pack_ids else (confident[0]["guard_packs"] if len(confident) == 1 else ["generic"])
    requested = list(dict.fromkeys(pack for pack in requested if pack))
    if not requested:
        raise AuditError("At least one rule pack is required")

    report.project_profile = confident[0] if len(confident) == 1 else {"outcome": "insufficient_evidence", "profiles": profiles, "missing_evidence": ["Exactly one confident project profile is required for automatic guard selection."]}
    report.guard_catalog = select_guard_catalog(report.project_profile)
    report.guard_catalog["foundation_applicability"] = resolve_foundation_guards(report.project_profile)
    report.profile_snapshot = profiler.snapshot(confident[0]) if len(confident) == 1 else {}
    if len(confident) == 1:
        signal_references = [
            {"path": signal["path"], "sha256": signal["sha256"]}
            for signal in confident[0]["signals"]
        ]
        report.guard_selection = [
            {
                "pack_id": pack_id,
                "rationale": "Selected from approved project signals.",
                "evidence_references": signal_references,
                "rule_ids": [
                    rule_id for rule_id in report.guard_catalog["optional_guard_ids"]
                    if rule_id.startswith(pack_id + ".")
                ],
            }
            for pack_id in requested
        ]
    for pack_id in requested:
        try:
            rules = _load_rule_pack(pack_id)
        except AuditError as exc:
            reason = str(exc)
            report.skipped_packs.append({"pack_id": pack_id, "reason": reason})
            _record_result(
                report,
                RuleResult(
                    rule_id=f"{pack_id}.__load__",
                    status="failed",
                    message=reason,
                    evidence={"pack_id": pack_id, "skipped": True},
                    severity="error",
                    required=True,
                    fast_fail=True,
                ),
            )
            continue

        report.packs_evaluated.append(pack_id)
        gate_closed = False

        for function_name, function in rules.items():
            if function_name in FOUNDATION_GUARD_IDS:
                continue
            if gate_closed:
                report.skipped_gates.append({
                    "pack_id": pack_id,
                    "rule": function_name,
                    "reason": "A prior required fast-fail rule failed or was blocked.",
                })
                continue

            try:
                result = function(
                    resolved_ctx,
                    {
                        "roots": normalized_roots,
                        "workspace_root": base_params["workspace_root"],
                        "workspace_id": base_params["workspace_id"],
                        "project_type": audit_type,
                        "inventory": report.inventory,
                    },
                )
            except Exception as exc:
                result = RuleResult(
                    rule_id=f"{pack_id}.{function_name}",
                    status="failed",
                    message=f"Rule execution failed: {type(exc).__name__}: {exc}",
                    evidence={
                        "pack_id": pack_id,
                        "function": function_name,
                        "exception": type(exc).__name__,
                    },
                    severity="error",
                    required=True,
                    fast_fail=True,
                )

            if not isinstance(result, RuleResult):
                raise AuditError(
                    f"Rule {pack_id}.{function_name} must return RuleResult, "
                    f"not {type(result).__name__}"
                )

            _record_result(report, result)
            report.optional_guard_execution.append({
                "guard_id": result.rule_id,
                "execution_index": len(report.optional_guard_execution) + 1,
                "status": result.status,
                "evidence_refs": _evidence_refs(result.evidence),
                "evidence": result.evidence,
                "message": result.message,
            })
            if (
                result.fast_fail
                and result.required
                and result.status in {"failed", "blocked"}
            ):
                gate_closed = True

    report.completed_at = _utc_now()
    if report.audit_status != "completed_with_overrides":
        report.summary = _derive_summary(report)
    if len(confident) == 1:
        report.snapshot_comparison = ProjectSnapshotStore().save(
            report.profile_snapshot,
            [
                {"id": result.rule_id, "status": result.status}
                for result in report.results
            ],
        )
    return report


def audit_to_json(report: AuditReport) -> dict[str, Any]:
    payload = report.to_dict()
    payload["outcome"] = report.summary
    payload["audit_completed"] = True
    return payload


def save_report(report: AuditReport) -> Path:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    write_json(REPORT_PATH, audit_to_json(report))
    return REPORT_PATH


def _run_cli_audit(args: argparse.Namespace) -> None:
    pack_ids = [value.strip() for value in args.packs] if args.packs else None
    roots = [value.strip() for value in args.roots.split(",")] if args.roots else None
    report = run_audit(
        pack_ids=pack_ids,
        project_type=args.project_type,
        roots=roots,
        workspace_root=args.workspace_root,
    )
    path = save_report(report)
    print(json.dumps(audit_to_json(report), indent=2, ensure_ascii=False))
    print(f"\nReport: {path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Deterministic workspace audit controller"
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    audit_parser = subcommands.add_parser("audit")
    audit_parser.add_argument("--pack", action="append", dest="packs")
    audit_parser.add_argument("--project-type")
    audit_parser.add_argument("--roots")
    audit_parser.add_argument("--workspace-root")
    audit_parser.set_defaults(func=_run_cli_audit)

    packs_parser = subcommands.add_parser("packs")
    packs_parser.set_defaults(
        func=lambda _: print(
            json.dumps(
                {
                    "rules_dir": str(RULES_DIR),
                    "available_packs": sorted(
                        path.stem
                        for path in RULES_DIR.glob("*.py")
                        if path.name != "__init__.py"
                    ),
                },
                indent=2,
            )
        )
    )

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
