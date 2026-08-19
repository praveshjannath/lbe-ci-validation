from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from lbe_guard_inspector.memory.completion_evidence import TaskCompletionEvidencePersistence
from lbe_guard_inspector.runtime.completion_gate import (
    CompletionVerdict,
    evaluate_completion,
)
from lbe_guard_inspector.runtime.completion_evidence_producers import (
    CompletionEvidenceProducers,
)
from lbe_guard_inspector.runtime.completion_runtime import CodingCompletionRuntime
from lbe_guard_inspector.runtime.task_completion_policy import (
    DEFAULT_TASK_COMPLETION_POLICY_CATALOG,
)
from lbe_guard_inspector.session_memory_runtime import SessionMemoryRuntimeBridge


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
    (root / "tracked.txt").write_text("before\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.txt"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "initial"], cwd=root, check=True)
    return root


def _runtime(tmp_path: Path, root: Path) -> SessionMemoryRuntimeBridge:
    runtime = SessionMemoryRuntimeBridge(
        database_path=tmp_path / "memory.sqlite",
        project_workspace_id="project-1",
        workspace_root=root,
        session_id="session-1",
        mode="coding",
        permission="write_allowed",
        runtime_policy="permissive",
    )
    policy = DEFAULT_TASK_COMPLETION_POLICY_CATALOG.find(
        operation_id="reasoning.inspect",
        task_class="coding_fix",
        mode="coding",
    )
    assert policy is not None
    CodingCompletionRuntime(runtime=runtime).persist_contract(
        task_id="task-1",
        contract=policy.contract(),
    )
    return runtime


def _producers(runtime: SessionMemoryRuntimeBridge) -> CompletionEvidenceProducers:
    return CompletionEvidenceProducers(runtime=runtime)


def _passing_validation_run(command: tuple[str, ...], **_: object) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(command, 0, stdout="3 passed\n", stderr="")


def test_source_change_passes_only_for_live_changed_task_workspace(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    runtime = _runtime(tmp_path, root)
    producers = _producers(runtime)
    baseline = producers.capture_workspace_snapshot()
    (root / "tracked.txt").write_text("after\n", encoding="utf-8")

    evidence = producers.produce_source_change(
        task_id="task-1", operation_id="reasoning.inspect", baseline=baseline
    )

    assert evidence.kind == "source_change"
    assert evidence.status == "PASS"
    assert evidence.producer_id == "lbe.completion.source_change.v1"
    assert evidence.operation_id == "reasoning.inspect"
    assert evidence.session_id == "session-1"
    assert evidence.project_workspace_id == "project-1"
    assert evidence.details["task_changed_paths"] == ["tracked.txt"]


def test_missing_live_change_does_not_pass_even_with_provider_claim(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path, _repo(tmp_path))
    producers = _producers(runtime)

    evidence = producers.produce_source_change(
        task_id="task-1",
        operation_id="reasoning.inspect",
        baseline=producers.capture_workspace_snapshot(),
    )

    assert evidence.status == "FAIL"
    assert "provider" not in evidence.details


def test_preexisting_workspace_change_is_not_credited_to_the_new_task(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "preexisting.txt").write_text("unrelated\n", encoding="utf-8")
    runtime = _runtime(tmp_path, root)
    producers = _producers(runtime)

    evidence = producers.produce_source_change(
        task_id="task-1",
        operation_id="reasoning.inspect",
        baseline=producers.capture_workspace_snapshot(),
    )

    assert evidence.status == "FAIL"
    assert evidence.details["task_status_entries"] == []


def test_source_change_becomes_stale_when_prior_live_change_disappears(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    runtime = _runtime(tmp_path, root)
    producers = _producers(runtime)
    initial_baseline = producers.capture_workspace_snapshot()
    (root / "tracked.txt").write_text("after\n", encoding="utf-8")
    producers.produce_source_change(
        task_id="task-1", operation_id="reasoning.inspect", baseline=initial_baseline
    )
    reverted_baseline = producers.capture_workspace_snapshot()
    (root / "tracked.txt").write_text("before\n", encoding="utf-8")

    evidence = producers.produce_source_change(
        task_id="task-1", operation_id="reasoning.inspect", baseline=reverted_baseline
    )

    assert evidence.status == "STALE"


def test_git_status_passes_for_expected_uncommitted_task_diff(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    runtime = _runtime(tmp_path, root)
    producers = _producers(runtime)
    baseline = producers.capture_workspace_snapshot()
    (root / "tracked.txt").write_text("after\n", encoding="utf-8")
    producers.produce_source_change(
        task_id="task-1", operation_id="reasoning.inspect", baseline=baseline
    )

    evidence = producers.produce_git_status(task_id="task-1", operation_id="reasoning.inspect")

    assert evidence.kind == "git_status"
    assert evidence.status == "PASS"
    assert evidence.details["expected_status_entries"] == evidence.details["observed_status_entries"]


def test_git_status_fails_when_live_state_has_unrelated_changes(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    runtime = _runtime(tmp_path, root)
    producers = _producers(runtime)
    baseline = producers.capture_workspace_snapshot()
    (root / "tracked.txt").write_text("after\n", encoding="utf-8")
    producers.produce_source_change(
        task_id="task-1", operation_id="reasoning.inspect", baseline=baseline
    )
    (root / "unrelated.txt").write_text("unrelated\n", encoding="utf-8")

    evidence = producers.produce_git_status(task_id="task-1", operation_id="reasoning.inspect")

    assert evidence.status == "FAIL"
    assert evidence.details["unexpected_status_entries"]


def test_focused_test_runs_only_registered_repository_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo(tmp_path)
    runtime = _runtime(tmp_path, root)
    calls: list[tuple[tuple[str, ...], Path, bool]] = []

    def run(
        *, command: tuple[str, ...], workspace_root: object, timeout_seconds: float
    ) -> subprocess.CompletedProcess[str]:
        calls.append((command, Path(str(workspace_root)), timeout_seconds == 300.0))
        return _passing_validation_run(command)

    monkeypatch.setattr(
        "lbe_guard_inspector.runtime.completion_evidence_producers._run_validation_command", run
    )
    evidence = _producers(runtime).produce_focused_test(
        task_id="task-1", operation_id="reasoning.inspect"
    )

    assert calls == [(("python", "-m", "pytest", "-q"), root, True)]
    assert evidence.kind == "focused_test"
    assert evidence.status == "PASS"
    assert evidence.producer_id == "lbe.completion.focused_test.v1"
    assert evidence.details["validation_policy_id"] == "repository.ci.pytest.v1"


def test_focused_test_failure_is_producer_classified_not_provider_claim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = _runtime(tmp_path, _repo(tmp_path))

    def run(*, command: tuple[str, ...], **_: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 1, stdout="1 failed\n", stderr="failure\n")

    monkeypatch.setattr(
        "lbe_guard_inspector.runtime.completion_evidence_producers._run_validation_command", run
    )
    evidence = _producers(runtime).produce_focused_test(
        task_id="task-1", operation_id="reasoning.inspect"
    )

    assert evidence.status == "FAIL"
    assert evidence.details["command"] == ["python", "-m", "pytest", "-q"]
    assert "provider" not in evidence.details


def test_producer_retry_is_idempotent_and_conflicting_replacement_fails_closed(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    runtime = _runtime(tmp_path, root)
    producers = _producers(runtime)
    baseline = producers.capture_workspace_snapshot()
    (root / "tracked.txt").write_text("after\n", encoding="utf-8")
    first = producers.produce_source_change(
        task_id="task-1", operation_id="reasoning.inspect", baseline=baseline
    )
    second = producers.produce_source_change(
        task_id="task-1", operation_id="reasoning.inspect", baseline=baseline
    )

    assert second == first
    with pytest.raises(ValueError, match="cannot be replaced implicitly"):
        TaskCompletionEvidencePersistence(runtime.store).save(
            session_id=runtime.session_id,
            task_id="task-1",
            project_workspace_id=runtime.project_workspace_id,
            canonical_workspace_root=str(runtime.workspace_root),
            evidence_id=first.evidence_id,
            kind=first.kind,
            status=first.status,
            source=first.source,
            producer_id=first.producer_id,
            operation_id=first.operation_id,
            details={"fabricated": True},
        )


def test_completion_remains_blocked_without_focused_test_evidence(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    runtime = _runtime(tmp_path, root)
    producers = _producers(runtime)
    baseline = producers.capture_workspace_snapshot()
    (root / "tracked.txt").write_text("after\n", encoding="utf-8")
    producers.produce_source_change(
        task_id="task-1", operation_id="reasoning.inspect", baseline=baseline
    )
    producers.produce_git_status(task_id="task-1", operation_id="reasoning.inspect")
    completion_runtime = CodingCompletionRuntime(runtime=runtime)
    contract = completion_runtime.load_contract(task_id="task-1")
    assert contract is not None

    decision = evaluate_completion(
        contract=contract,
        evidence=completion_runtime.load_evidence(task_id="task-1"),
        claimed_complete=True,
    )

    assert decision.verdict is CompletionVerdict.BLOCKED
    assert decision.missing_requirement_ids == ("focused-tests",)


def test_registered_focused_test_completes_the_existing_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo(tmp_path)
    runtime = _runtime(tmp_path, root)
    producers = _producers(runtime)
    baseline = producers.capture_workspace_snapshot()
    (root / "tracked.txt").write_text("after\n", encoding="utf-8")
    producers.produce_source_change(
        task_id="task-1", operation_id="reasoning.inspect", baseline=baseline
    )
    monkeypatch.setattr(
        "lbe_guard_inspector.runtime.completion_evidence_producers._run_validation_command",
        lambda *, command, **_: _passing_validation_run(command),
    )
    producers.produce_focused_test(task_id="task-1", operation_id="reasoning.inspect")
    producers.produce_git_status(task_id="task-1", operation_id="reasoning.inspect")
    completion_runtime = CodingCompletionRuntime(runtime=runtime)
    contract = completion_runtime.load_contract(task_id="task-1")
    assert contract is not None

    decision = evaluate_completion(
        contract=contract,
        evidence=completion_runtime.load_evidence(task_id="task-1"),
        claimed_complete=True,
    )

    assert decision.verdict is CompletionVerdict.READY
