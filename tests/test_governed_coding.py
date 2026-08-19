from __future__ import annotations

import json
from pathlib import Path

import agent

from lbe_guard_inspector.reasoning_provider import ProviderConfig
from lbe_guard_inspector.runtime.governed_coding import (
    _cline_base_url,
    build_workspace_create_candidate_text_handler,
    workspace_create_candidate_text_spec,
)
from lbe_guard_inspector.runtime.mode_controller import ModeDecision
from lbe_guard_inspector.runtime.tool_orchestration import (
    GovernedToolOrchestrator,
    ToolExecutionContext,
    ToolReceiptStatus,
    ToolRegistry,
    ToolRequest,
)


def _configure_runtime_files(
    tmp_path: Path,
    monkeypatch,
    *,
    allowed_write_paths=(".",),
    forbidden_globs=(),
    max_changed_files=1,
    max_patch_bytes=4096,
) -> Path:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    config = tmp_path / "config.json"
    governance = tmp_path / "governance.json"
    config.write_text(
        json.dumps(
            {
                "knowledge_roots": [
                    {"name": "project-1", "path": str(workspace)}
                ]
            }
        ),
        encoding="utf-8",
    )
    governance.write_text(
        json.dumps(
            {
                "allowed_read_paths": ["."],
                "allowed_write_paths": list(allowed_write_paths),
                "forbidden_globs": list(forbidden_globs),
                "max_changed_files": max_changed_files,
                "max_patch_bytes": max_patch_bytes,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(agent, "CONFIG_PATH", config)
    monkeypatch.setattr(agent, "GOVERNANCE_PATH", governance)
    return workspace


def _context(workspace: Path) -> ToolExecutionContext:
    return ToolExecutionContext(
        mode_decision=ModeDecision(
            mode="coding",
            allowed_behaviors=("development_mode_capabilities",),
            capabilities=("test_candidate",),
            rationale="test",
        ),
        workspace_id="project-1",
        workspace_root=workspace,
        configured_root_id="project-1",
    )


def _orchestrator() -> GovernedToolOrchestrator:
    registry = ToolRegistry()
    registry.register(
        workspace_create_candidate_text_spec(),
        build_workspace_create_candidate_text_handler(),
    )
    return GovernedToolOrchestrator(registry=registry)


def test_create_candidate_text_executes_once_and_is_idempotent(
    tmp_path: Path, monkeypatch
) -> None:
    workspace = _configure_runtime_files(tmp_path, monkeypatch)
    orchestrator = _orchestrator()
    request = ToolRequest(
        operation_id="op-create-1",
        tool_id="workspace.create_candidate_text",
        arguments={"path": "candidate.txt", "content": "governed\n"},
        context=_context(workspace),
    )

    first = orchestrator.invoke(request)
    second = orchestrator.invoke(request)

    assert first.status is ToolReceiptStatus.EXECUTED
    assert second is first
    assert first.authorization is not None
    assert first.authorization.verdict.value == "ALLOW"
    assert first.output["created"] is True
    assert first.output["path"] == "candidate.txt"
    assert first.output["sha256"]
    assert (workspace / "candidate.txt").read_text(encoding="utf-8") == "governed\n"


def test_create_candidate_text_never_overwrites_existing_file(
    tmp_path: Path, monkeypatch
) -> None:
    workspace = _configure_runtime_files(tmp_path, monkeypatch)
    target = workspace / "candidate.txt"
    target.write_text("original", encoding="utf-8")
    receipt = _orchestrator().invoke(
        ToolRequest(
            operation_id="op-create-existing",
            tool_id="workspace.create_candidate_text",
            arguments={"path": "candidate.txt", "content": "replacement"},
            context=_context(workspace),
        )
    )

    assert receipt.status is ToolReceiptStatus.FAILED
    assert receipt.error_code == "TOOL_EXECUTION_FAILED"
    assert "already exists" in receipt.error_message
    assert target.read_text(encoding="utf-8") == "original"


def test_create_candidate_text_respects_allowed_write_paths(
    tmp_path: Path, monkeypatch
) -> None:
    workspace = _configure_runtime_files(
        tmp_path,
        monkeypatch,
        allowed_write_paths=(),
    )
    receipt = _orchestrator().invoke(
        ToolRequest(
            operation_id="op-denied-path",
            tool_id="workspace.create_candidate_text",
            arguments={"path": "candidate.txt", "content": "blocked"},
            context=_context(workspace),
        )
    )

    assert receipt.status is ToolReceiptStatus.FAILED
    assert receipt.error_code == "TOOL_EXECUTION_FAILED"
    assert "write path is not allowed" in receipt.error_message
    assert not (workspace / "candidate.txt").exists()


def test_create_candidate_text_respects_patch_limit(
    tmp_path: Path, monkeypatch
) -> None:
    workspace = _configure_runtime_files(
        tmp_path,
        monkeypatch,
        max_patch_bytes=3,
    )
    receipt = _orchestrator().invoke(
        ToolRequest(
            operation_id="op-too-large",
            tool_id="workspace.create_candidate_text",
            arguments={"path": "candidate.txt", "content": "four"},
            context=_context(workspace),
        )
    )

    assert receipt.status is ToolReceiptStatus.FAILED
    assert receipt.error_code == "TOOL_EXECUTION_FAILED"
    assert "max_patch_bytes" in receipt.error_message
    assert not (workspace / "candidate.txt").exists()


def test_cline_base_url_reuses_openai_compatible_endpoint_root() -> None:
    config = ProviderConfig(
        endpoint="http://127.0.0.1:18777/v1/chat/completions",
        model="model-a",
        timeout_seconds=5,
    )
    assert _cline_base_url(config.endpoint) == "http://127.0.0.1:18777/v1"
