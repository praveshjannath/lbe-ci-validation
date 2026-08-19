"""Thin CLI control plane for the persistent LBE runtime.

The CLI parses operator input and delegates to existing runtime/data owners. It
must not become a second session controller, provider authority, permission
resolver, tool executor, evidence authority, or completion gate.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Sequence
from uuid import uuid4

from .agent_integration import AgentMode, AgentRequestEnvelope, GovernedAgentGateway
from .evidence_service import EvidenceService
from .memory import WorkspaceMemoryStore
from .provider_health import check_provider_health
from .provider_registry import default_provider_registry
from .reasoning_config import load_provider_config
from .reasoning_runtime import build_provider_controller
from .runtime.completion_runtime import CodingCompletionRuntime
from .session_memory_runtime import SessionMemoryRuntimeBridge


_MODES = ("coding", "audit", "investigation")
_OUTPUT_FORMATS = ("json", "text")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lbe",
        description="Persistent LBE runtime control plane",
    )
    parser.add_argument(
        "--format",
        choices=_OUTPUT_FORMATS,
        default="json",
        help="Output format for terminal users or automation",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    session = commands.add_parser("session", help="Manage persistent sessions")
    session_commands = session.add_subparsers(dest="session_command", required=True)

    create = session_commands.add_parser("create", help="Create a persistent session")
    _add_database_argument(create)
    create.add_argument("--workspace", required=True)
    create.add_argument("--project-workspace-id", required=True)
    create.add_argument("--session-id", required=True)
    create.add_argument("--mode", required=True, choices=_MODES)
    create.add_argument("--permission", choices=("read_only", "write_allowed", "audit_only", "elevated"), default="read_only")
    create.add_argument("--runtime-policy", choices=("audit", "development", "strict", "permissive"), default="audit")
    create.add_argument("--provider")
    create.add_argument("--model")
    create.add_argument("--profile")
    create.add_argument("--permission-policy")
    create.add_argument("--evidence-policy")
    create.set_defaults(handler=_session_create)

    continue_parser = session_commands.add_parser(
        "continue", help="Rehydrate an existing persistent session"
    )
    _add_database_argument(continue_parser)
    continue_parser.add_argument("--session-id", required=True)
    continue_parser.add_argument("--task-id")
    continue_parser.add_argument("--provider")
    continue_parser.add_argument("--model")
    continue_parser.set_defaults(handler=_session_continue)

    status = session_commands.add_parser("status", help="Read persisted session status")
    _add_database_argument(status)
    status.add_argument("--session-id", required=True)
    status.add_argument("--task-id")
    status.set_defaults(handler=_session_status)

    inspect_parser = session_commands.add_parser(
        "inspect", help="Inspect persisted session identity and lifecycle state"
    )
    _add_database_argument(inspect_parser)
    inspect_parser.add_argument("--session-id", required=True)
    inspect_parser.add_argument("--task-id")
    inspect_parser.set_defaults(handler=_session_inspect)

    evidence = session_commands.add_parser(
        "evidence", help="Retrieve bounded evidence for an existing session"
    )
    _add_database_argument(evidence)
    evidence.add_argument("--session-id", required=True)
    evidence.add_argument("--task-id", required=True)
    evidence.add_argument("--query", required=True)
    evidence.add_argument("--max-results", type=int, default=10)
    evidence.set_defaults(handler=_session_evidence)

    validate = session_commands.add_parser(
        "validate", help="Evaluate persisted completion evidence for an existing task"
    )
    _add_database_argument(validate)
    validate.add_argument("--session-id", required=True)
    validate.add_argument("--task-id", required=True)
    validate.set_defaults(handler=_session_validate)

    provider = commands.add_parser("provider", help="Inspect or select reasoning providers")
    provider_commands = provider.add_subparsers(dest="provider_command", required=True)
    provider_list = provider_commands.add_parser("list", help="List registered providers")
    provider_list.set_defaults(handler=_provider_list)

    provider_check = provider_commands.add_parser(
        "check", help="Check a provider against the structured reasoning contract"
    )
    provider_check.add_argument("--provider", required=True)
    provider_check.add_argument("--provider-config", required=True)
    provider_check.set_defaults(handler=_provider_check)

    provider_select = provider_commands.add_parser(
        "select", help="Select a provider/model for an existing session"
    )
    _add_database_argument(provider_select)
    provider_select.add_argument("--session-id", required=True)
    provider_select.add_argument("--provider", required=True)
    provider_select.add_argument("--model", required=True)
    provider_select.set_defaults(handler=_provider_select)

    _add_mode_command(commands, "code", AgentMode.CODING, "Run a governed coding task")
    _add_mode_command(commands, "audit", AgentMode.AUDIT, "Run a governed read-only audit task")
    _add_mode_command(
        commands,
        "investigate",
        AgentMode.INVESTIGATION,
        "Run a governed investigation task",
    )

    policy = commands.add_parser("policy", help="Inspect active session policy references")
    policy_commands = policy.add_subparsers(dest="policy_command", required=True)
    policy_show = policy_commands.add_parser("show", help="Show active workspace/evidence policy")
    _add_database_argument(policy_show)
    policy_show.add_argument("--session-id", required=True)
    policy_show.set_defaults(handler=_policy_show)

    permissions = commands.add_parser("permissions", help="Inspect active permission policy")
    permission_commands = permissions.add_subparsers(dest="permissions_command", required=True)
    permissions_show = permission_commands.add_parser("show", help="Show active permission policy")
    _add_database_argument(permissions_show)
    permissions_show.add_argument("--session-id", required=True)
    permissions_show.set_defaults(handler=_permissions_show)

    tui = commands.add_parser("tui", help="Open the persisted Textual session projection")
    _add_database_argument(tui)
    tui.add_argument("--session-id", required=True)
    tui.add_argument("--provider-config", help="Explicit provider config for non-streaming turn execution")
    tui.set_defaults(handler=_tui)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        payload = args.handler(args)
    except (ValueError, TypeError, FileNotFoundError, RuntimeError) as exc:
        _emit(
            {
                "ok": False,
                "error": type(exc).__name__,
                "message": str(exc),
            },
            args.format,
        )
        return 2
    _emit({"ok": True, **payload}, args.format)
    return 0


def _session_create(args: argparse.Namespace) -> dict[str, Any]:
    workspace = _workspace_root(args.workspace)
    _validate_provider_selection(args.provider, args.model, require_pair=False)
    runtime = SessionMemoryRuntimeBridge(
        database_path=args.database,
        project_workspace_id=args.project_workspace_id,
        workspace_root=workspace,
        session_id=args.session_id,
        mode=args.mode,
        permission=args.permission,
        runtime_policy=args.runtime_policy,
        provider_id=args.provider,
        provider_model=args.model,
        active_profile_id=args.profile,
        permission_policy_id=args.permission_policy,
        evidence_policy_id=args.evidence_policy,
    )
    return {
        "action": "session.create",
        "session": runtime.session_state.as_dict(),
    }


def _session_continue(args: argparse.Namespace) -> dict[str, Any]:
    store = WorkspaceMemoryStore(args.database)
    state = _require_session(store, args.session_id)
    runtime = _runtime_from_state(database=args.database, state=state)
    if args.provider is not None or args.model is not None:
        provider_id = state.provider_id if args.provider is None else args.provider
        provider_model = state.provider_model if args.model is None else args.model
        _validate_provider_selection(provider_id, provider_model, require_pair=True)
        runtime.configure_session(
            provider_id=provider_id,
            provider_model=provider_model,
        )
    packet = runtime.start_or_resume(task_id=args.task_id)
    return {
        "action": "session.continue",
        "session": runtime.session_state.as_dict(),
        "context": packet,
    }


def _session_status(args: argparse.Namespace) -> dict[str, Any]:
    store = WorkspaceMemoryStore(args.database)
    state = _require_session(store, args.session_id)
    payload: dict[str, Any] = {
        "action": "session.status",
        "session_id": state.session_id,
        "mode": state.mode,
        "workspace": state.canonical_workspace_root,
        "provider_id": state.provider_id,
        "provider_model": state.provider_model,
        "checkpoint_id": state.checkpoint_id,
    }
    if args.task_id:
        task = store.load_session_task(
            session_id=state.session_id,
            task_id=args.task_id,
            project_workspace_id=state.project_workspace_id,
        )
        payload["task"] = _task_payload(task)
    return payload


def _session_inspect(args: argparse.Namespace) -> dict[str, Any]:
    store = WorkspaceMemoryStore(args.database)
    state = _require_session(store, args.session_id)
    payload: dict[str, Any] = {
        "action": "session.inspect",
        "session": state.as_dict(),
    }
    if args.task_id:
        task = store.load_session_task(
            session_id=state.session_id,
            task_id=args.task_id,
            project_workspace_id=state.project_workspace_id,
        )
        payload["task"] = _task_payload(task)
    return payload


def _session_evidence(args: argparse.Namespace) -> dict[str, Any]:
    if args.max_results < 1:
        raise ValueError("max_results must be a positive integer")
    store = WorkspaceMemoryStore(args.database)
    state = _require_session(store, args.session_id)
    retrieval_mode = "investigation" if state.mode == "investigation" else "diagnostic"
    package = EvidenceService().build_evidence_package(
        task_id=args.task_id,
        query=args.query,
        workspace_id=state.project_workspace_id,
        workspace_root=state.canonical_workspace_root,
        max_results=args.max_results,
        roots=[state.project_workspace_id],
        retrieval_mode=retrieval_mode,
    )
    return {
        "action": "session.evidence",
        "session_id": state.session_id,
        "task_id": args.task_id,
        "mode": state.mode,
        "evidence_policy_id": state.evidence_policy_id,
        "package": package,
    }


def _session_validate(args: argparse.Namespace) -> dict[str, Any]:
    """Thin C3 adapter over the existing completion runtime and gate."""
    store = WorkspaceMemoryStore(args.database)
    state = _require_session(store, args.session_id)
    runtime = _runtime_from_state(database=args.database, state=state)
    completion_runtime = CodingCompletionRuntime(runtime=runtime)
    contract = completion_runtime.load_contract(task_id=args.task_id)
    if contract is None:
        raise ValueError("persisted task completion contract not found")
    decision, task = completion_runtime.finalize(
        task_id=args.task_id,
        contract=contract,
        evidence=completion_runtime.load_evidence(task_id=args.task_id),
        claimed_complete=True,
    )
    return {
        "action": "session.validate",
        "session_id": state.session_id,
        "task_id": args.task_id,
        "completion": {
            "verdict": decision.verdict.value,
            "satisfied_requirement_ids": list(decision.satisfied_requirement_ids),
            "missing_requirement_ids": list(decision.missing_requirement_ids),
            "failed_requirement_ids": list(decision.failed_requirement_ids),
            "evidence_ids": list(decision.evidence_ids),
            "rationale": decision.rationale,
        },
        "task": _task_payload(task),
    }


def _provider_list(args: argparse.Namespace) -> dict[str, Any]:
    del args
    registry = default_provider_registry()
    return {
        "action": "provider.list",
        "providers": list(registry.provider_ids()),
    }


def _provider_check(args: argparse.Namespace) -> dict[str, Any]:
    config = load_provider_config(args.provider_config)
    result = check_provider_health(
        provider_id=args.provider,
        provider_config=config,
    )
    return {
        "action": "provider.check",
        "provider_id": result.provider_id,
        "provider_model": result.model_id,
        "status": result.status,
        "capabilities": asdict(result.capabilities),
    }


def _provider_select(args: argparse.Namespace) -> dict[str, Any]:
    _validate_provider_selection(args.provider, args.model, require_pair=True)
    store = WorkspaceMemoryStore(args.database)
    state = _require_session(store, args.session_id)
    runtime = _runtime_from_state(database=args.database, state=state)
    before = runtime.session_state
    updated = runtime.configure_session(
        provider_id=args.provider,
        provider_model=args.model,
    )
    return {
        "action": "provider.select",
        "session_id": updated.session_id,
        "provider_id": updated.provider_id,
        "provider_model": updated.provider_model,
        "workspace": updated.canonical_workspace_root,
        "mode": updated.mode,
        "policy_unchanged": {
            "active_profile_id": before.active_profile_id == updated.active_profile_id,
            "permission_policy_id": before.permission_policy_id == updated.permission_policy_id,
            "evidence_policy_id": before.evidence_policy_id == updated.evidence_policy_id,
            "permission": before.permission == updated.permission,
            "runtime_policy": before.runtime_policy == updated.runtime_policy,
        },
    }


def _tui(args: argparse.Namespace) -> dict[str, Any]:
    from .memory.operational_history import SessionOperationalHistory
    from .openai_compatible_event_adapter import OpenAICompatibleEventAdapter
    from .persistent_turn_control import PersistentTurnControl
    from .provider_turn_runtime import BackgroundProviderTurnRuntime, NonStreamingProviderTurnRuntime
    from .reasoning_config import load_provider_config
    from .textual_tui import run_textual_tui

    store = WorkspaceMemoryStore(args.database)
    state = _require_session(store, args.session_id)
    history = SessionOperationalHistory(store=store)
    provider_runtime = None
    if args.provider_config is not None:
        if state.provider_id != "openai-compatible":
            raise ValueError("Textual non-streaming execution currently requires openai-compatible session provider")
        config = load_provider_config(args.provider_config)
        if config.model != state.provider_model:
            raise ValueError("provider config model must match persisted session model")
        provider_runtime = BackgroundProviderTurnRuntime(history=history, foreground=NonStreamingProviderTurnRuntime(history=history, adapter=OpenAICompatibleEventAdapter(config=config), provider_id=state.provider_id))
    run_textual_tui(
        history=history,
        session_id=state.session_id,
        control=PersistentTurnControl(history=history, provider_runtime=provider_runtime),
    )
    return {"action": "tui", "session_id": state.session_id}


def _code(args: argparse.Namespace) -> dict[str, Any]:
    return _run_mode_command(args, AgentMode.CODING, action="code")


def _audit(args: argparse.Namespace) -> dict[str, Any]:
    return _run_mode_command(args, AgentMode.AUDIT, action="audit")


def _investigate(args: argparse.Namespace) -> dict[str, Any]:
    return _run_mode_command(args, AgentMode.INVESTIGATION, action="investigate")


def _run_mode_command(
    args: argparse.Namespace,
    mode: AgentMode,
    *,
    action: str,
) -> dict[str, Any]:
    if args.max_results < 1:
        raise ValueError("max_results must be a positive integer")
    state = _require_session(WorkspaceMemoryStore(args.database), args.session_id)
    if not state.provider_id or not state.provider_model:
        raise ValueError("persisted session does not have a selected provider/model")

    provider_config = load_provider_config(args.provider_config)
    if provider_config.model.strip() != state.provider_model:
        raise ValueError("provider config model does not match persisted session provider model")

    runtime = _runtime_from_state(database=args.database, state=state)
    controller, handle = build_provider_controller(
        provider_id=state.provider_id,
        provider_config=provider_config,
    )
    if handle.descriptor.provider_id != state.provider_id:
        raise ValueError("provider adapter identity does not match persisted session provider")
    if mode is AgentMode.CODING:
        from .runtime.governed_coding import GovernedClineReasoningController

        controller = GovernedClineReasoningController(
            runtime=runtime,
            provider_id=state.provider_id,
            provider_config=provider_config,
        )

    gateway = GovernedAgentGateway(runtime=runtime, reasoning_controller=controller)
    request_id = args.request_id.strip() if args.request_id else f"request-{uuid4()}"
    result = gateway.invoke(
        AgentRequestEnvelope(
            request_id=request_id,
            session_id=state.session_id,
            task_id=args.task_id,
            project_workspace_id=state.project_workspace_id,
            workspace_root=state.canonical_workspace_root,
            mode=mode,
            operation_id="reasoning.inspect",
            arguments={
                "problem": args.problem,
                "max_results": args.max_results,
            },
        )
    )
    return {
        "action": action,
        "request_id": result.request_id,
        "session_id": result.session_id,
        "task_id": result.task_id,
        "mode": result.mode.value,
        "mode_decision": asdict(result.mode_decision),
        "status": result.status.value,
        "outcome": result.outcome,
        "response": asdict(result.response),
    }


def _policy_show(args: argparse.Namespace) -> dict[str, Any]:
    state = _require_session(WorkspaceMemoryStore(args.database), args.session_id)
    return {
        "action": "policy.show",
        "session_id": state.session_id,
        "workspace": state.canonical_workspace_root,
        "mode": state.mode,
        "active_profile_id": state.active_profile_id,
        "evidence_policy_id": state.evidence_policy_id,
    }


def _permissions_show(args: argparse.Namespace) -> dict[str, Any]:
    state = _require_session(WorkspaceMemoryStore(args.database), args.session_id)
    return {
        "action": "permissions.show",
        "session_id": state.session_id,
        "workspace": state.canonical_workspace_root,
        "mode": state.mode,
        "permission_policy_id": state.permission_policy_id,
    }


def _runtime_from_state(*, database: str | Path, state: Any) -> SessionMemoryRuntimeBridge:
    return SessionMemoryRuntimeBridge(
        database_path=database,
        project_workspace_id=state.project_workspace_id,
        workspace_root=state.canonical_workspace_root,
        session_id=state.session_id,
        mode=state.mode,
        permission=state.permission,
        runtime_policy=state.runtime_policy,
        provider_id=state.provider_id,
        provider_model=state.provider_model,
        active_profile_id=state.active_profile_id,
        permission_policy_id=state.permission_policy_id,
        evidence_policy_id=state.evidence_policy_id,
    )


def _validate_provider_selection(
    provider_id: str | None,
    provider_model: str | None,
    *,
    require_pair: bool,
) -> None:
    if provider_id is None and provider_model is None and not require_pair:
        return
    if not provider_id or not str(provider_id).strip():
        raise ValueError("provider_id must be supplied with provider model")
    if not provider_model or not str(provider_model).strip():
        raise ValueError("provider model must be supplied with provider_id")
    registry = default_provider_registry()
    clean_provider = str(provider_id).strip()
    if clean_provider not in registry.provider_ids():
        raise ValueError(f"provider is not registered: {clean_provider}")


def _require_session(store: WorkspaceMemoryStore, session_id: str):
    clean_id = str(session_id).strip()
    if not clean_id:
        raise ValueError("session_id must not be empty")
    state = store.load_session_state(session_id=clean_id)
    if state is None:
        raise FileNotFoundError(f"persistent session not found: {clean_id}")
    return state


def _workspace_root(value: str) -> Path:
    root = Path(value).expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"workspace does not exist or is not a directory: {root}")
    return root


def _task_payload(task: Any) -> dict[str, Any] | None:
    if task is None:
        return None
    return {
        "session_id": task.session_id,
        "task_id": task.task_id,
        "project_workspace_id": task.project_workspace_id,
        "canonical_workspace_root": task.canonical_workspace_root,
        "status": task.status.value,
        "last_outcome": task.last_outcome,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
    }


def _add_database_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--database",
        required=True,
        help="Path to the persistent LBE SQLite database",
    )


def _add_mode_command(
    commands: argparse._SubParsersAction,
    name: str,
    mode: AgentMode,
    help_text: str,
) -> None:
    command = commands.add_parser(name, help=help_text)
    _add_database_argument(command)
    command.add_argument("--session-id", required=True)
    command.add_argument("--task-id", required=True)
    command.add_argument("--provider-config", required=True)
    command.add_argument("--problem", required=True)
    command.add_argument("--request-id")
    command.add_argument("--max-results", type=int, default=10)
    command.set_defaults(
        handler={
            AgentMode.CODING: _code,
            AgentMode.AUDIT: _audit,
            AgentMode.INVESTIGATION: _investigate,
        }[mode]
    )


def _emit(payload: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str))
        return
    for line in _human_lines(payload):
        print(line)


def _human_lines(payload: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    action = payload.get("action")
    if action:
        lines.append(str(action))
    if payload.get("ok") is False:
        lines.append(f"error: {payload.get('error')}: {payload.get('message')}")
        return lines
    for key, value in payload.items():
        if key in {"ok", "action"}:
            continue
        _append_human_value(lines, key, value, indent=0)
    return lines or ["ok"]


def _append_human_value(lines: list[str], key: str, value: Any, *, indent: int) -> None:
    prefix = "  " * indent
    if isinstance(value, dict):
        lines.append(f"{prefix}{key}:")
        for nested_key, nested_value in value.items():
            _append_human_value(lines, str(nested_key), nested_value, indent=indent + 1)
        return
    if isinstance(value, list):
        lines.append(f"{prefix}{key}: {', '.join(str(item) for item in value)}")
        return
    lines.append(f"{prefix}{key}: {value}")


if __name__ == "__main__":
    raise SystemExit(main())