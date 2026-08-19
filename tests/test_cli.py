from __future__ import annotations

import json
import subprocess
from pathlib import Path

from lbe_guard_inspector.cli import main
from lbe_guard_inspector.memory import TaskStatus, WorkspaceMemoryStore
from lbe_guard_inspector.memory.completion_evidence import TaskCompletionEvidencePersistence
from lbe_guard_inspector.runtime.completion_gate import CompletionRequirement, TaskCompletionContract
from lbe_guard_inspector.runtime.completion_runtime import CodingCompletionRuntime
from lbe_guard_inspector.session_memory_runtime import SessionMemoryRuntimeBridge


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
    (root / "tracked.txt").write_text("one\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.txt"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "initial"], cwd=root, check=True)
    return root


def _json_output(capsys):
    output = capsys.readouterr().out.strip()
    return json.loads(output)


def _persist_completion_contract(runtime: SessionMemoryRuntimeBridge) -> None:
    CodingCompletionRuntime(runtime=runtime).persist_contract(
        task_id="task-1",
        contract=TaskCompletionContract(
            requirements=(
                CompletionRequirement("source-change", "source_change"),
                CompletionRequirement("focused-tests", "focused_test"),
                CompletionRequirement("git-state", "git_status"),
            )
        ),
    )


def _persist_completion_evidence(runtime: SessionMemoryRuntimeBridge, *, kind: str, status: str) -> None:
    TaskCompletionEvidencePersistence(runtime.store).save(
        session_id=runtime.session_id,
        task_id="task-1",
        project_workspace_id=runtime.project_workspace_id,
        canonical_workspace_root=str(runtime.workspace_root),
        evidence_id=f"evidence-{kind}-{status}",
        kind=kind,
        status=status,
        source="lbe.test",
        producer_id="lbe.test.producer",
        operation_id="reasoning.inspect",
        details={"fixture": True},
    )


def test_session_create_persists_explicit_runtime_contract(tmp_path: Path, capsys) -> None:
    root = _repo(tmp_path)
    database = tmp_path / "memory.sqlite"

    code = main([
        "session", "create",
        "--database", str(database),
        "--workspace", str(root),
        "--project-workspace-id", "project-1",
        "--session-id", "session-1",
        "--mode", "coding",
        "--provider", "openai-compatible",
        "--model", "model-a",
        "--profile", "profile-a",
        "--permission-policy", "permissions-a",
        "--evidence-policy", "evidence-a",
    ])

    payload = _json_output(capsys)
    assert code == 0
    assert payload["ok"] is True
    assert payload["action"] == "session.create"
    assert payload["session"]["session_id"] == "session-1"
    assert payload["session"]["mode"] == "coding"
    assert payload["session"]["provider_id"] == "openai-compatible"
    assert payload["session"]["provider_model"] == "model-a"
    assert payload["session"]["permission_policy_id"] == "permissions-a"

    stored = WorkspaceMemoryStore(database).load_session_state(session_id="session-1")
    assert stored is not None
    assert stored.project_workspace_id == "project-1"
    assert Path(stored.canonical_workspace_root).resolve() == root.resolve()


def test_session_status_reads_existing_state_without_reconfiguring_it(tmp_path: Path, capsys) -> None:
    root = _repo(tmp_path)
    database = tmp_path / "memory.sqlite"
    runtime = SessionMemoryRuntimeBridge(
        database_path=database,
        project_workspace_id="project-1",
        workspace_root=root,
        session_id="session-1",
        mode="audit",
        provider_id="openai-compatible",
        provider_model="model-a",
        permission_policy_id="read-policy",
    )
    before = runtime.store.load_session_state(session_id="session-1")
    assert before is not None

    code = main([
        "session", "status",
        "--database", str(database),
        "--session-id", "session-1",
    ])

    payload = _json_output(capsys)
    assert code == 0
    assert payload == {
        "action": "session.status",
        "checkpoint_id": before.checkpoint_id,
        "mode": "audit",
        "ok": True,
        "provider_id": "openai-compatible",
        "provider_model": "model-a",
        "session_id": "session-1",
        "workspace": before.canonical_workspace_root,
    }
    after = runtime.store.load_session_state(session_id="session-1")
    assert after is not None
    assert after.permission_policy_id == "read-policy"
    assert after.mode == before.mode
    assert after.provider_id == before.provider_id


def test_session_status_can_include_canonical_task_state(tmp_path: Path, capsys) -> None:
    root = _repo(tmp_path)
    database = tmp_path / "memory.sqlite"
    runtime = SessionMemoryRuntimeBridge(
        database_path=database,
        project_workspace_id="project-1",
        workspace_root=root,
        session_id="session-1",
        mode="coding",
    )
    runtime.record_task_status(
        task_id="task-1",
        status=TaskStatus.BLOCKED,
        last_outcome="VALIDATION_REQUIRED",
    )

    code = main([
        "session", "status",
        "--database", str(database),
        "--session-id", "session-1",
        "--task-id", "task-1",
    ])

    payload = _json_output(capsys)
    assert code == 0
    assert payload["task"]["task_id"] == "task-1"
    assert payload["task"]["status"] == "blocked"
    assert payload["task"]["last_outcome"] == "VALIDATION_REQUIRED"


def test_session_inspect_returns_persisted_contract_not_model_inference(tmp_path: Path, capsys) -> None:
    root = _repo(tmp_path)
    database = tmp_path / "memory.sqlite"
    SessionMemoryRuntimeBridge(
        database_path=database,
        project_workspace_id="project-1",
        workspace_root=root,
        session_id="session-1",
        mode="investigation",
        active_profile_id="profile-a",
        evidence_policy_id="evidence-a",
    )

    code = main([
        "session", "inspect",
        "--database", str(database),
        "--session-id", "session-1",
    ])

    payload = _json_output(capsys)
    assert code == 0
    assert payload["action"] == "session.inspect"
    assert payload["session"]["mode"] == "investigation"
    assert payload["session"]["active_profile_id"] == "profile-a"
    assert payload["session"]["evidence_policy_id"] == "evidence-a"


def test_session_continue_rehydrates_existing_runtime_identity(tmp_path: Path, capsys) -> None:
    root = _repo(tmp_path)
    database = tmp_path / "memory.sqlite"
    runtime = SessionMemoryRuntimeBridge(
        database_path=database,
        project_workspace_id="project-1",
        workspace_root=root,
        session_id="session-1",
        mode="audit",
        provider_id="openai-compatible",
        provider_model="model-a",
    )
    runtime.checkpoint(
        compaction={
            "source_message_count": 1,
            "source_prefix_hash": "sha256:" + "a" * 64,
            "source_last_message_key": "id:msg-1",
            "messages": [],
        },
        active_constraints=["do not mutate"],
    )

    code = main([
        "session", "continue",
        "--database", str(database),
        "--session-id", "session-1",
    ])

    payload = _json_output(capsys)
    assert code == 0
    assert payload["action"] == "session.continue"
    assert payload["session"]["session_id"] == "session-1"
    assert payload["session"]["mode"] == "audit"
    assert payload["session"]["provider_id"] == "openai-compatible"
    assert payload["context"]["checkpoint"]["active_constraints"] == ["do not mutate"]


def test_provider_list_reads_registered_adapters_without_building_provider(capsys) -> None:
    code = main(["provider", "list"])

    payload = _json_output(capsys)
    assert code == 0
    assert payload == {
        "action": "provider.list",
        "ok": True,
        "providers": ["openai-compatible"],
    }


def test_missing_session_returns_structured_error(tmp_path: Path, capsys) -> None:
    code = main([
        "session", "status",
        "--database", str(tmp_path / "memory.sqlite"),
        "--session-id", "missing",
    ])

    payload = _json_output(capsys)
    assert code == 2
    assert payload["ok"] is False
    assert payload["error"] == "FileNotFoundError"
    assert "persistent session not found: missing" in payload["message"]


def test_session_create_rejects_missing_workspace(tmp_path: Path, capsys) -> None:
    code = main([
        "session", "create",
        "--database", str(tmp_path / "memory.sqlite"),
        "--workspace", str(tmp_path / "missing"),
        "--project-workspace-id", "project-1",
        "--session-id", "session-1",
        "--mode", "coding",
    ])

    payload = _json_output(capsys)
    assert code == 2
    assert payload["ok"] is False
    assert payload["error"] == "FileNotFoundError"


def test_text_output_is_human_readable_without_changing_state(tmp_path: Path, capsys) -> None:
    root = _repo(tmp_path)
    database = tmp_path / "memory.sqlite"
    SessionMemoryRuntimeBridge(
        database_path=database,
        project_workspace_id="project-1",
        workspace_root=root,
        session_id="session-1",
        mode="audit",
        provider_id="openai-compatible",
        provider_model="model-a",
    )

    code = main([
        "--format", "text",
        "session", "status",
        "--database", str(database),
        "--session-id", "session-1",
    ])

    output = capsys.readouterr().out
    assert code == 0
    assert "session.status" in output
    assert "session_id: session-1" in output
    assert "mode: audit" in output
    assert "provider_id: openai-compatible" in output
    assert not output.lstrip().startswith("{")


def test_provider_select_changes_only_provider_fields(tmp_path: Path, capsys) -> None:
    root = _repo(tmp_path)
    database = tmp_path / "memory.sqlite"
    runtime = SessionMemoryRuntimeBridge(
        database_path=database,
        project_workspace_id="project-1",
        workspace_root=root,
        session_id="session-1",
        mode="coding",
        provider_id="openai-compatible",
        provider_model="model-a",
        active_profile_id="profile-a",
        permission_policy_id="permissions-a",
        evidence_policy_id="evidence-a",
    )
    before = runtime.store.load_session_state(session_id="session-1")
    assert before is not None

    code = main([
        "provider", "select",
        "--database", str(database),
        "--session-id", "session-1",
        "--provider", "openai-compatible",
        "--model", "model-b",
    ])

    payload = _json_output(capsys)
    assert code == 0
    assert payload["action"] == "provider.select"
    assert payload["provider_model"] == "model-b"
    assert all(payload["policy_unchanged"].values())
    after = runtime.store.load_session_state(session_id="session-1")
    assert after is not None
    assert after.provider_model == "model-b"
    assert after.canonical_workspace_root == before.canonical_workspace_root
    assert after.mode == before.mode
    assert after.active_profile_id == before.active_profile_id
    assert after.permission_policy_id == before.permission_policy_id
    assert after.evidence_policy_id == before.evidence_policy_id


def test_session_continue_can_switch_provider_without_changing_policy(tmp_path: Path, capsys) -> None:
    root = _repo(tmp_path)
    database = tmp_path / "memory.sqlite"
    runtime = SessionMemoryRuntimeBridge(
        database_path=database,
        project_workspace_id="project-1",
        workspace_root=root,
        session_id="session-1",
        mode="audit",
        provider_id="openai-compatible",
        provider_model="model-a",
        active_profile_id="profile-a",
        permission_policy_id="permissions-a",
        evidence_policy_id="evidence-a",
    )

    code = main([
        "session", "continue",
        "--database", str(database),
        "--session-id", "session-1",
        "--provider", "openai-compatible",
        "--model", "model-b",
    ])

    payload = _json_output(capsys)
    assert code == 0
    assert payload["session"]["provider_model"] == "model-b"
    stored = runtime.store.load_session_state(session_id="session-1")
    assert stored is not None
    assert stored.mode == "audit"
    assert stored.active_profile_id == "profile-a"
    assert stored.permission_policy_id == "permissions-a"
    assert stored.evidence_policy_id == "evidence-a"


def test_unknown_provider_is_rejected_without_mutating_session(tmp_path: Path, capsys) -> None:
    root = _repo(tmp_path)
    database = tmp_path / "memory.sqlite"
    runtime = SessionMemoryRuntimeBridge(
        database_path=database,
        project_workspace_id="project-1",
        workspace_root=root,
        session_id="session-1",
        mode="coding",
        provider_id="openai-compatible",
        provider_model="model-a",
        permission_policy_id="permissions-a",
    )
    before = runtime.store.load_session_state(session_id="session-1")
    assert before is not None

    code = main([
        "provider", "select",
        "--database", str(database),
        "--session-id", "session-1",
        "--provider", "not-registered",
        "--model", "model-x",
    ])

    payload = _json_output(capsys)
    assert code == 2
    assert payload["ok"] is False
    assert payload["error"] == "ValueError"
    after = runtime.store.load_session_state(session_id="session-1")
    assert after is not None
    assert after.provider_id == before.provider_id
    assert after.provider_model == before.provider_model
    assert after.permission_policy_id == before.permission_policy_id


def test_session_evidence_delegates_to_canonical_evidence_service(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    root = _repo(tmp_path)
    database = tmp_path / "memory.sqlite"
    SessionMemoryRuntimeBridge(
        database_path=database,
        project_workspace_id="project-1",
        workspace_root=root,
        session_id="session-1",
        mode="investigation",
        evidence_policy_id="evidence-a",
    )

    calls: list[dict] = []

    class _EvidenceService:
        def build_evidence_package(self, **kwargs):
            calls.append(kwargs)
            return {
                "package_id": "ep-test",
                "task_id": kwargs["task_id"],
                "current_workspace_evidence": [{"ref": "workspace:tracked.txt"}],
                "indexed_reference_evidence": [],
                "validation_evidence": [],
                "contradictions": [],
                "gaps": [],
            }

    monkeypatch.setattr("lbe_guard_inspector.cli.EvidenceService", _EvidenceService)

    code = main([
        "session", "evidence",
        "--database", str(database),
        "--session-id", "session-1",
        "--task-id", "task-1",
        "--query", "tracked workspace fact",
        "--max-results", "7",
    ])

    payload = _json_output(capsys)
    assert code == 0
    assert payload["action"] == "session.evidence"
    assert payload["mode"] == "investigation"
    assert payload["evidence_policy_id"] == "evidence-a"
    assert payload["package"]["package_id"] == "ep-test"
    assert len(calls) == 1
    assert calls[0]["task_id"] == "task-1"
    assert calls[0]["workspace_id"] == "project-1"
    assert Path(calls[0]["workspace_root"]).resolve() == root.resolve()
    assert calls[0]["roots"] == ["project-1"]
    assert calls[0]["retrieval_mode"] == "investigation"
    assert calls[0]["max_results"] == 7


def test_session_evidence_rejects_invalid_result_limit_before_retrieval(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    root = _repo(tmp_path)
    database = tmp_path / "memory.sqlite"
    SessionMemoryRuntimeBridge(
        database_path=database,
        project_workspace_id="project-1",
        workspace_root=root,
        session_id="session-1",
        mode="audit",
    )

    constructed = False

    class _EvidenceService:
        def __init__(self):
            nonlocal constructed
            constructed = True

    monkeypatch.setattr("lbe_guard_inspector.cli.EvidenceService", _EvidenceService)

    code = main([
        "session", "evidence",
        "--database", str(database),
        "--session-id", "session-1",
        "--task-id", "task-1",
        "--query", "fact",
        "--max-results", "0",
    ])

    payload = _json_output(capsys)
    assert code == 2
    assert payload["error"] == "ValueError"
    assert constructed is False


def test_policy_and_permissions_show_only_persisted_session_references(tmp_path: Path, capsys) -> None:
    root = _repo(tmp_path)
    database = tmp_path / "memory.sqlite"
    runtime = SessionMemoryRuntimeBridge(
        database_path=database,
        project_workspace_id="project-1",
        workspace_root=root,
        session_id="session-1",
        mode="coding",
        active_profile_id="profile-a",
        permission_policy_id="permissions-a",
        evidence_policy_id="evidence-a",
    )
    before = runtime.store.load_session_state(session_id="session-1")
    assert before is not None

    policy_code = main([
        "policy", "show",
        "--database", str(database),
        "--session-id", "session-1",
    ])
    policy = _json_output(capsys)

    permissions_code = main([
        "permissions", "show",
        "--database", str(database),
        "--session-id", "session-1",
    ])
    permissions = _json_output(capsys)

    assert policy_code == 0
    assert policy == {
        "action": "policy.show",
        "active_profile_id": "profile-a",
        "evidence_policy_id": "evidence-a",
        "mode": "coding",
        "ok": True,
        "session_id": "session-1",
        "workspace": before.canonical_workspace_root,
    }
    assert permissions_code == 0
    assert permissions == {
        "action": "permissions.show",
        "mode": "coding",
        "ok": True,
        "permission_policy_id": "permissions-a",
        "session_id": "session-1",
        "workspace": before.canonical_workspace_root,
    }
    after = runtime.store.load_session_state(session_id="session-1")
    assert after is not None
    assert after.as_dict() == before.as_dict()


def test_session_validate_uses_existing_gate_for_persisted_evidence(tmp_path: Path, capsys) -> None:
    root = _repo(tmp_path)
    database = tmp_path / "memory.sqlite"
    runtime = SessionMemoryRuntimeBridge(
        database_path=database,
        project_workspace_id="project-1",
        workspace_root=root,
        session_id="session-1",
        mode="coding",
        permission="write_allowed",
        runtime_policy="permissive",
    )
    _persist_completion_contract(runtime)
    for kind in ("source_change", "focused_test", "git_status"):
        _persist_completion_evidence(runtime, kind=kind, status="PASS")

    code = main([
        "session", "validate",
        "--database", str(database),
        "--session-id", "session-1",
        "--task-id", "task-1",
    ])

    payload = _json_output(capsys)
    assert code == 0
    assert payload["action"] == "session.validate"
    assert payload["completion"]["verdict"] == "READY"
    assert payload["task"]["status"] == "completed"


def test_session_validate_exposes_existing_blocked_result_without_cli_evidence_input(
    tmp_path: Path, capsys
) -> None:
    root = _repo(tmp_path)
    database = tmp_path / "memory.sqlite"
    runtime = SessionMemoryRuntimeBridge(
        database_path=database,
        project_workspace_id="project-1",
        workspace_root=root,
        session_id="session-1",
        mode="coding",
        permission="write_allowed",
        runtime_policy="permissive",
    )
    _persist_completion_contract(runtime)
    _persist_completion_evidence(runtime, kind="source_change", status="PASS")

    code = main([
        "session", "validate",
        "--database", str(database),
        "--session-id", "session-1",
        "--task-id", "task-1",
    ])

    payload = _json_output(capsys)
    assert code == 0
    assert payload["completion"]["verdict"] == "BLOCKED"
    assert payload["completion"]["missing_requirement_ids"] == ["focused-tests", "git-state"]
    assert payload["task"]["status"] == "blocked"


def test_session_validate_rejects_task_without_persisted_contract(tmp_path: Path, capsys) -> None:
    root = _repo(tmp_path)
    database = tmp_path / "memory.sqlite"
    SessionMemoryRuntimeBridge(
        database_path=database,
        project_workspace_id="project-1",
        workspace_root=root,
        session_id="session-1",
        mode="coding",
        permission="write_allowed",
        runtime_policy="permissive",
    )

    code = main([
        "session", "validate",
        "--database", str(database),
        "--session-id", "session-1",
        "--task-id", "task-1",
    ])

    payload = _json_output(capsys)
    assert code == 2
    assert payload["error"] == "ValueError"
    assert "completion contract" in payload["message"]
