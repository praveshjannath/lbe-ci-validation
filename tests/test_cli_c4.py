from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from lbe_guard_inspector.agent_integration import AgentMode
from lbe_guard_inspector.cli import main
from lbe_guard_inspector.memory import TaskStatus
from lbe_guard_inspector.provider_health import ProviderHealthResult
from lbe_guard_inspector.provider_registry import ProviderCapabilities
from lbe_guard_inspector.reasoning_contracts import LBEResponse
from lbe_guard_inspector.runtime.mode_controller import ModeDecision
from lbe_guard_inspector.session_memory_runtime import SessionMemoryRuntimeBridge


def _json_output(capsys):
    return json.loads(capsys.readouterr().out.strip())


def _provider_config(tmp_path: Path, *, model: str = "model-a") -> Path:
    path = tmp_path / "provider.json"
    path.write_text(
        json.dumps(
            {
                "endpoint": "http://provider/v1/chat/completions",
                "model": model,
                "timeout_seconds": 5,
            }
        ),
        encoding="utf-8",
    )
    return path


def _session(
    tmp_path: Path,
    *,
    mode: str,
    permission: str,
    runtime_policy: str,
) -> tuple[Path, Path]:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    database = tmp_path / "memory.sqlite"
    SessionMemoryRuntimeBridge(
        database_path=database,
        project_workspace_id="project-1",
        workspace_root=workspace,
        session_id="session-1",
        mode=mode,
        permission=permission,
        runtime_policy=runtime_policy,
        provider_id="openai-compatible",
        provider_model="model-a",
    )
    return workspace, database


def test_provider_check_delegates_to_provider_health_owner(tmp_path: Path, capsys, monkeypatch) -> None:
    config = _provider_config(tmp_path)
    calls = []

    def fake_check_provider_health(*, provider_id, provider_config):
        calls.append((provider_id, provider_config))
        return ProviderHealthResult(
            provider_id="openai-compatible",
            model_id="model-a",
            status="READY",
            capabilities=ProviderCapabilities(structured_output=True),
        )

    monkeypatch.setattr(
        "lbe_guard_inspector.cli.check_provider_health",
        fake_check_provider_health,
    )

    code = main([
        "provider",
        "check",
        "--provider",
        "openai-compatible",
        "--provider-config",
        str(config),
    ])

    payload = _json_output(capsys)
    assert code == 0
    assert payload["action"] == "provider.check"
    assert payload["status"] == "READY"
    assert payload["provider_model"] == "model-a"
    assert len(calls) == 1


@pytest.mark.parametrize(
    "command,agent_mode,session_mode,permission,runtime_policy",
    [
        ("code", AgentMode.CODING, "coding", "write_allowed", "permissive"),
        ("audit", AgentMode.AUDIT, "audit", "read_only", "audit"),
        (
            "investigate",
            AgentMode.INVESTIGATION,
            "investigation",
            "read_only",
            "permissive",
        ),
    ],
)
def test_mode_commands_route_through_existing_gateway(
    tmp_path: Path,
    capsys,
    monkeypatch,
    command,
    agent_mode,
    session_mode,
    permission,
    runtime_policy,
) -> None:
    workspace, database = _session(
        tmp_path,
        mode=session_mode,
        permission=permission,
        runtime_policy=runtime_policy,
    )
    config = _provider_config(tmp_path)
    requests = []

    handle = SimpleNamespace(
        descriptor=SimpleNamespace(
            provider_id="openai-compatible",
            model_id="model-a",
        )
    )
    monkeypatch.setattr(
        "lbe_guard_inspector.cli.build_provider_controller",
        lambda **kwargs: (object(), handle),
    )

    class FakeGateway:
        def __init__(self, *, runtime, reasoning_controller):
            assert runtime.session_id == "session-1"
            assert reasoning_controller is not None

        def invoke(self, request):
            requests.append(request)
            return SimpleNamespace(
                request_id=request.request_id,
                session_id=request.session_id,
                task_id=request.task_id,
                mode=request.mode,
                mode_decision=ModeDecision(
                    mode=request.mode.value,
                    allowed_behaviors=(),
                    capabilities=(),
                    rationale="test",
                ),
                status=TaskStatus.COMPLETED,
                outcome="COMPLETED",
                response=LBEResponse(
                    task_id=request.task_id,
                    workspace_identity={
                        "workspace_id": "project-1",
                        "target_project_root": str(workspace.resolve()),
                    },
                    workspace_profile={},
                    plan=None,
                    deterministic_result=None,
                    explanation=None,
                    outcome="COMPLETED",
                    read_only=request.mode is not AgentMode.CODING,
                ),
            )

    monkeypatch.setattr("lbe_guard_inspector.cli.GovernedAgentGateway", FakeGateway)

    code = main([
        command,
        "--database",
        str(database),
        "--session-id",
        "session-1",
        "--task-id",
        "task-1",
        "--provider-config",
        str(config),
        "--problem",
        "Inspect and act only within the governed task",
        "--request-id",
        "request-1",
    ])

    payload = _json_output(capsys)
    assert code == 0
    assert payload["action"] == command
    assert payload["mode"] == agent_mode.value
    assert payload["request_id"] == "request-1"
    assert len(requests) == 1
    request = requests[0]
    assert request.mode is agent_mode
    assert request.session_id == "session-1"
    assert request.project_workspace_id == "project-1"
    assert request.workspace_root == workspace.resolve()
    assert request.operation_id == "reasoning.inspect"


def test_mode_command_rejects_provider_config_model_mismatch_before_composition(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    _, database = _session(
        tmp_path,
        mode="audit",
        permission="read_only",
        runtime_policy="audit",
    )
    config = _provider_config(tmp_path, model="other-model")
    built = False

    def fake_build(**kwargs):
        nonlocal built
        built = True
        raise AssertionError("provider must not be composed after identity mismatch")

    monkeypatch.setattr("lbe_guard_inspector.cli.build_provider_controller", fake_build)

    code = main([
        "audit",
        "--database",
        str(database),
        "--session-id",
        "session-1",
        "--task-id",
        "task-1",
        "--provider-config",
        str(config),
        "--problem",
        "Inspect current workspace",
    ])

    payload = _json_output(capsys)
    assert code == 2
    assert "does not match persisted session provider model" in payload["message"]
    assert built is False


def test_mode_command_requires_persisted_provider_identity(tmp_path: Path, capsys) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    database = tmp_path / "memory.sqlite"
    SessionMemoryRuntimeBridge(
        database_path=database,
        project_workspace_id="project-1",
        workspace_root=workspace,
        session_id="session-1",
        mode="audit",
        permission="read_only",
        runtime_policy="audit",
    )
    config = _provider_config(tmp_path)

    code = main([
        "audit",
        "--database",
        str(database),
        "--session-id",
        "session-1",
        "--task-id",
        "task-1",
        "--provider-config",
        str(config),
        "--problem",
        "Inspect current workspace",
    ])

    payload = _json_output(capsys)
    assert code == 2
    assert "selected provider/model" in payload["message"]
