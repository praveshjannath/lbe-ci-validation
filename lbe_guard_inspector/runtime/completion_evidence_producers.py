"""Trusted live-repository completion-evidence producers for C2.

The producers observe current Git state and persist their own classifications.
They run a validation command only when fixed LBE policy selects it. They do
not accept provider claims or evaluate task completion.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from typing import Any

from ..memory.completion_evidence import (
    StoredCompletionEvidence,
    TaskCompletionEvidencePersistence,
)
from ..memory.context import inspect_git_state
from ..session_memory_runtime import SessionMemoryRuntimeBridge
from .completion_runtime import CodingCompletionRuntime
from .validation_command_policy import (
    DEFAULT_VALIDATION_COMMAND_POLICY_CATALOG,
    ValidationCommandPolicyCatalog,
)


SOURCE_CHANGE_PRODUCER_ID = "lbe.completion.source_change.v1"
GIT_STATUS_PRODUCER_ID = "lbe.completion.git_status.v1"
FOCUSED_TEST_PRODUCER_ID = "lbe.completion.focused_test.v1"
_SOURCE_CHANGE_KIND = "source_change"
_GIT_STATUS_KIND = "git_status"
_FOCUSED_TEST_KIND = "focused_test"
_SUPPORTED_OPERATION_ID = "reasoning.inspect"


@dataclass(frozen=True)
class LiveRepositorySnapshot:
    """Trusted repository observation made at the governed task boundary."""

    branch: str
    head: str
    status_entries: tuple[str, ...]


class CompletionEvidenceProducers:
    """Emit only C2-A evidence from current bounded workspace state."""

    def __init__(
        self,
        *,
        runtime: SessionMemoryRuntimeBridge,
        validation_command_catalog: ValidationCommandPolicyCatalog = DEFAULT_VALIDATION_COMMAND_POLICY_CATALOG,
    ) -> None:
        if not isinstance(runtime, SessionMemoryRuntimeBridge):
            raise TypeError("runtime must be SessionMemoryRuntimeBridge")
        if not isinstance(validation_command_catalog, ValidationCommandPolicyCatalog):
            raise TypeError("validation_command_catalog must be ValidationCommandPolicyCatalog")
        self._runtime = runtime
        self._persistence = TaskCompletionEvidencePersistence(runtime.store)
        self._validation_command_catalog = validation_command_catalog

    def capture_workspace_snapshot(self) -> LiveRepositorySnapshot:
        """Capture the bounded workspace state before governed task execution."""
        state = _live_git_state(self._runtime.workspace_root)
        return LiveRepositorySnapshot(
            branch=state["branch"],
            head=state["head"],
            status_entries=tuple(state["status_entries"]),
        )

    def produce_source_change(
        self,
        *,
        task_id: str,
        operation_id: str,
        baseline: LiveRepositorySnapshot,
    ) -> StoredCompletionEvidence:
        self._require_declared_requirement(
            task_id=task_id,
            operation_id=operation_id,
            evidence_kind=_SOURCE_CHANGE_KIND,
        )
        _require_snapshot(baseline)
        state = _live_git_state(self._runtime.workspace_root)
        task_status_entries = tuple(
            sorted(set(state["status_entries"]) - set(baseline.status_entries))
        )
        prior_pass = self._latest_source_change_pass(task_id=task_id, operation_id=operation_id)
        if task_status_entries:
            status = "PASS"
            reason = "Current live repository state contains task-bound changed paths."
        elif prior_pass is not None:
            status = "STALE"
            reason = "Previously observed task change is no longer present in live repository state."
        else:
            status = "FAIL"
            reason = "No current repository or source change exists for the governed task."
        details = {
            **state,
            "baseline": {
                "branch": baseline.branch,
                "head": baseline.head,
                "status_entries": list(baseline.status_entries),
            },
            "task_status_entries": list(task_status_entries),
            "task_changed_paths": [_changed_path(entry) for entry in task_status_entries],
            "classification_reason": reason,
        }
        return self._persist(
            task_id=task_id,
            operation_id=operation_id,
            kind=_SOURCE_CHANGE_KIND,
            status=status,
            producer_id=SOURCE_CHANGE_PRODUCER_ID,
            details=details,
        )

    def produce_git_status(
        self,
        *,
        task_id: str,
        operation_id: str,
    ) -> StoredCompletionEvidence:
        self._require_declared_requirement(
            task_id=task_id,
            operation_id=operation_id,
            evidence_kind=_GIT_STATUS_KIND,
        )
        state = _live_git_state(self._runtime.workspace_root)
        source_change = self._latest_source_change_pass(
            task_id=task_id,
            operation_id=operation_id,
        )
        if source_change is None:
            status = "FAIL"
            reason = "No passing task-bound source_change evidence exists to reconcile."
            expected_entries: tuple[str, ...] = ()
            unexpected_entries = state["status_entries"]
        else:
            expected_entries = tuple(source_change.details.get("task_status_entries", ()))
            observed_entries = state["status_entries"]
            unexpected_entries = tuple(sorted(set(observed_entries) - set(expected_entries)))
            missing_entries = tuple(sorted(set(expected_entries) - set(observed_entries)))
            if unexpected_entries:
                status = "FAIL"
                reason = "Current live repository state contains unaccounted-for changes."
            elif missing_entries or state["head"] != source_change.details.get("head"):
                status = "STALE"
                reason = "Current live repository state no longer matches the task-bound source snapshot."
            else:
                status = "PASS"
                reason = "Current live Git state matches the task-bound source snapshot."
        details = {
            **state,
            "expected_source_evidence_id": source_change.evidence_id if source_change else None,
            "expected_status_entries": list(expected_entries),
            "observed_status_entries": list(state["status_entries"]),
            "unexpected_status_entries": list(unexpected_entries),
            "classification_reason": reason,
        }
        return self._persist(
            task_id=task_id,
            operation_id=operation_id,
            kind=_GIT_STATUS_KIND,
            status=status,
            producer_id=GIT_STATUS_PRODUCER_ID,
            details=details,
        )

    def produce_focused_test(
        self,
        *,
        task_id: str,
        operation_id: str,
    ) -> StoredCompletionEvidence:
        """Run only the policy-selected validation command for this contract."""
        self._require_declared_requirement(
            task_id=task_id,
            operation_id=operation_id,
            evidence_kind=_FOCUSED_TEST_KIND,
        )
        policy = self._validation_command_catalog.find(
            operation_id=operation_id,
            mode=self._runtime.session_state.mode,
            evidence_kind=_FOCUSED_TEST_KIND,
        )
        if policy is None:
            raise ValueError("no LBE validation command policy applies to focused_test")
        state_before = _live_git_state(self._runtime.workspace_root)
        try:
            completed = _run_validation_command(
                command=policy.command,
                workspace_root=self._runtime.workspace_root,
                timeout_seconds=policy.timeout_seconds,
            )
        except subprocess.TimeoutExpired as error:
            status = "FAIL"
            exit_code: int | None = None
            stdout = _text(error.stdout)
            stderr = _text(error.stderr)
            reason = "The registered focused validation command exceeded its policy timeout."
        else:
            status = "PASS" if completed.returncode == 0 else "FAIL"
            exit_code = completed.returncode
            stdout = completed.stdout
            stderr = completed.stderr
            reason = (
                "The registered focused validation command completed successfully."
                if status == "PASS"
                else "The registered focused validation command failed."
            )
        details = {
            "validation_policy_id": policy.policy_id,
            "command": list(policy.command),
            "timeout_seconds": policy.timeout_seconds,
            "workspace_state_before": state_before,
            "workspace_state_after": _live_git_state(self._runtime.workspace_root),
            "exit_code": exit_code,
            "stdout_sha256": _sha256_text(stdout),
            "stderr_sha256": _sha256_text(stderr),
            "classification_reason": reason,
        }
        return self._persist(
            task_id=task_id,
            operation_id=operation_id,
            kind=_FOCUSED_TEST_KIND,
            status=status,
            producer_id=FOCUSED_TEST_PRODUCER_ID,
            details=details,
        )

    def _require_declared_requirement(
        self,
        *,
        task_id: str,
        operation_id: str,
        evidence_kind: str,
    ) -> None:
        if operation_id != _SUPPORTED_OPERATION_ID:
            raise ValueError("completion evidence producer operation is not supported")
        contract = CodingCompletionRuntime(runtime=self._runtime).load_contract(task_id=task_id)
        if contract is None or evidence_kind not in {
            item.evidence_kind for item in contract.requirements
        }:
            raise ValueError("completion evidence kind is not declared by the persisted task contract")

    def _latest_source_change_pass(
        self,
        *,
        task_id: str,
        operation_id: str,
    ) -> StoredCompletionEvidence | None:
        records = self._persistence.load(
            session_id=self._runtime.session_id,
            task_id=task_id,
            project_workspace_id=self._runtime.project_workspace_id,
        )
        for record in reversed(records):
            if (
                record.kind == _SOURCE_CHANGE_KIND
                and record.status == "PASS"
                and record.producer_id == SOURCE_CHANGE_PRODUCER_ID
                and record.operation_id == operation_id
            ):
                return record
        return None

    def _persist(
        self,
        *,
        task_id: str,
        operation_id: str,
        kind: str,
        status: str,
        producer_id: str,
        details: dict[str, Any],
    ) -> StoredCompletionEvidence:
        evidence_id = _evidence_id(
            task_id=task_id,
            operation_id=operation_id,
            kind=kind,
            status=status,
            producer_id=producer_id,
            details=details,
        )
        return self._persistence.save(
            session_id=self._runtime.session_id,
            task_id=task_id,
            project_workspace_id=self._runtime.project_workspace_id,
            canonical_workspace_root=str(self._runtime.workspace_root),
            evidence_id=evidence_id,
            kind=kind,
            status=status,
            source="lbe.live_repository",
            producer_id=producer_id,
            operation_id=operation_id,
            details=details,
        )


def _live_git_state(workspace_root: object) -> dict[str, Any]:
    state = inspect_git_state(workspace_root)
    entries = tuple(sorted(str(item) for item in state.get("status_short", ())))
    return {
        "branch": str(state.get("branch") or ""),
        "head": str(state.get("head") or ""),
        "status_entries": list(entries),
        "changed_paths": [_changed_path(entry) for entry in entries],
    }


def _changed_path(entry: str) -> str:
    if len(entry) > 2 and entry[1] == " ":
        value = entry[2:].strip()
    elif len(entry) > 3 and entry[2] == " ":
        value = entry[3:].strip()
    else:
        value = entry.strip()
    return value.rsplit(" -> ", 1)[-1].strip()


def _require_snapshot(value: object) -> None:
    if not isinstance(value, LiveRepositorySnapshot):
        raise TypeError("baseline must be a LiveRepositorySnapshot")


def _evidence_id(
    *,
    task_id: str,
    operation_id: str,
    kind: str,
    status: str,
    producer_id: str,
    details: dict[str, Any],
) -> str:
    payload = json.dumps(
        {
            "task_id": task_id,
            "operation_id": operation_id,
            "kind": kind,
            "status": status,
            "producer_id": producer_id,
            "details": details,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"evidence-{kind}-{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:24]}"


def _text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _run_validation_command(
    *,
    command: tuple[str, ...],
    workspace_root: object,
    timeout_seconds: float,
) -> subprocess.CompletedProcess[str]:
    """Execute a command already selected by fixed LBE validation policy."""
    return subprocess.run(
        command,
        cwd=workspace_root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_seconds,
    )
