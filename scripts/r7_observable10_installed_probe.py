"""Installed R7 observable 10 provisional-completion authority probe."""
from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import threading
from typing import Any
from uuid import uuid4

from lbe_guard_inspector.memory import WorkspaceMemoryStore
from lbe_guard_inspector.memory.completion_contracts import TaskCompletionContractPersistence

MODEL = "r7-obs10-model"
SESSION_ID = "r7-obs10-session"
TASK_ID = "r7-obs10-task"
PROJECT_ID = "r7-obs10-project"
PROVIDER_CLAIM = "The task is complete and ready."


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def run(command: list[str], *, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(cwd),
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def json_stdout(result: subprocess.CompletedProcess[str], label: str) -> dict[str, Any]:
    if result.returncode != 0:
        raise RuntimeError(
            f"{label} exit={result.returncode}; stderr={result.stderr!r}; stdout={result.stdout!r}"
        )
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    require(bool(lines), f"{label} produced no stdout")
    value = json.loads(lines[-1])
    require(isinstance(value, dict), f"{label} JSON root is not an object")
    require(value.get("ok") is True, f"{label} ok is not true: {value}")
    return value


def git(workspace: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(workspace), *args],
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stdout}\n{result.stderr}")
    return result.stdout


def final_response() -> list[dict[str, Any]]:
    return [
        {
            "id": "chatcmpl-r7-obs10-final",
            "object": "chat.completion.chunk",
            "created": 1,
            "model": MODEL,
            "choices": [
                {
                    "index": 0,
                    "delta": {"role": "assistant", "content": PROVIDER_CLAIM},
                    "finish_reason": None,
                }
            ],
        },
        {
            "id": "chatcmpl-r7-obs10-final",
            "object": "chat.completion.chunk",
            "created": 1,
            "model": MODEL,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        },
    ]


class StubServer(ThreadingHTTPServer):
    def __init__(self) -> None:
        super().__init__(("127.0.0.1", 0), StubHandler)
        self.requests: list[dict[str, Any]] = []


class StubHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("content-length", "0"))
        raw = self.rfile.read(length)
        request = json.loads(raw.decode("utf-8")) if raw else {}
        self.server.requests.append({"path": self.path, "body": request})
        require(len(self.server.requests) == 1, "provider received unexpected continuation/tool request")
        chunks = final_response()
        body = (
            "".join(
                f"data: {json.dumps(chunk, separators=(',', ':'))}\n\n"
                for chunk in chunks
            )
            + "data: [DONE]\n\n"
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)
        self.wfile.flush()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--installed-root", required=True)
    args = parser.parse_args()

    installed_root = Path(args.installed_root).expanduser().resolve()
    venv = installed_root / "venv"
    lbe = venv / "Scripts" / "lbe.exe"
    python_exe = venv / "Scripts" / "python.exe"
    require(lbe.is_file(), f"installed lbe missing: {lbe}")
    require(python_exe.is_file(), f"installed python missing: {python_exe}")

    package_file = Path(__import__("lbe_guard_inspector").__file__).resolve()
    require("site-packages" in str(package_file).lower(), f"probe imported non-installed package: {package_file}")
    require("agents-memory-tool-v6-integration" not in str(package_file).lower(), "source checkout import leakage")
    print("R7_OBS10_PACKAGE_FILE=" + str(package_file))

    # Use a fresh disposable root on every invocation. On Windows, prior nested
    # Git object files may remain temporarily locked after a failed probe; a
    # rerun must not depend on deleting that prior repository before reaching
    # the product acceptance predicate.
    probe = installed_root / f"obs10-{uuid4().hex}"
    workspace = probe / "workspace"
    state_dir = probe / "state"
    workspace.mkdir(parents=True)
    state_dir.mkdir(parents=True)
    print("R7_OBS10_PROBE_ROOT=" + str(probe))

    (workspace / "test_smoke.py").write_text("def test_smoke():\n    assert True\n", encoding="utf-8")
    (workspace / ".gitignore").write_text("__pycache__/\n.pytest_cache/\n", encoding="utf-8")
    git(workspace, "init", "-q")
    git(workspace, "config", "user.email", "r7@example.invalid")
    git(workspace, "config", "user.name", "R7 Probe")
    git(workspace, "add", "test_smoke.py", ".gitignore")
    git(workspace, "commit", "-q", "-m", "R7 observable 10 baseline")
    baseline_status = git(workspace, "status", "--porcelain")
    require(baseline_status == "", f"baseline workspace not clean: {baseline_status!r}")

    database = probe / "memory.sqlite"
    config = probe / "config.json"
    governance = probe / "governance.json"
    provider = probe / "provider.json"
    config.write_text(
        json.dumps({"knowledge_roots": [{"name": PROJECT_ID, "path": str(workspace)}]}),
        encoding="utf-8",
    )
    governance.write_text(
        json.dumps(
            {
                "allowed_read_paths": ["."],
                "allowed_write_paths": ["."],
                "forbidden_globs": ["**/.git/**", "**/.env", "**/.env.*", "**/credentials*", "**/secrets*"],
                "required_files": [],
                "allowed_commands": [],
                "required_validation_commands": [],
                "max_changed_files": 1,
                "max_patch_bytes": 4096,
                "require_clean_base_hash": True,
                "store_only_verified_repairs": True,
            }
        ),
        encoding="utf-8",
    )

    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env["PATH"] = str(venv / "Scripts") + os.pathsep + env.get("PATH", "")
    env["LBE_GUARD_INSPECTOR_CONFIG_PATH"] = str(config)
    env["LBE_GUARD_INSPECTOR_GOVERNANCE_PATH"] = str(governance)
    env["LBE_GUARD_INSPECTOR_STATE_DIR"] = str(state_dir)

    server = StubServer()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        provider.write_text(
            json.dumps(
                {
                    "endpoint": f"http://127.0.0.1:{server.server_port}/v1/chat/completions",
                    "model": MODEL,
                    "timeout_seconds": 15,
                    "api_key": "R7_OBS10_SECRET_NEVER_ECHO",
                }
            ),
            encoding="utf-8",
        )

        json_stdout(
            run(
                [
                    str(lbe), "session", "create",
                    "--database", str(database),
                    "--workspace", str(workspace),
                    "--project-workspace-id", PROJECT_ID,
                    "--session-id", SESSION_ID,
                    "--mode", "coding",
                    "--permission", "write_allowed",
                    "--runtime-policy", "development",
                    "--provider", "openai-compatible",
                    "--model", MODEL,
                    "--profile", "r7-obs10-profile",
                    "--permission-policy", "r7-obs10-permissions",
                    "--evidence-policy", "r7-obs10-evidence",
                ],
                cwd=probe,
                env=env,
            ),
            "session create",
        )

        code = json_stdout(
            run(
                [
                    str(lbe), "code",
                    "--database", str(database),
                    "--session-id", SESSION_ID,
                    "--task-id", TASK_ID,
                    "--provider-config", str(provider),
                    "--problem", "Inspect the bounded task and report your conclusion.",
                    "--request-id", "r7-obs10-request",
                ],
                cwd=probe,
                env=env,
            ),
            "installed code",
        )

        store = WorkspaceMemoryStore(database)
        contract = TaskCompletionContractPersistence(store).load(
            session_id=SESSION_ID,
            task_id=TASK_ID,
            project_workspace_id=PROJECT_ID,
        )
        require(contract is not None, "normal coding path did not persist completion contract")
        contract_kinds = [item.evidence_kind for item in contract.requirements]
        require(
            contract_kinds == ["source_change", "focused_test", "git_status"],
            f"registered completion contract mismatch: {contract_kinds}",
        )
        print("R7_OBS10_REGISTERED_CONTRACT=PASS")

        require(len(server.requests) == 1, f"provider request count={len(server.requests)}")
        require(code.get("outcome") == "COMPLETED", f"reasoning outcome={code.get('outcome')}")
        response = code.get("response") or {}
        deterministic = response.get("deterministic_result") or {}
        require(deterministic.get("terminal_message_type") == "turn.completed", "provider turn did not complete")
        require(deterministic.get("terminal_status") == "completed", "provider terminal status not completed")
        require(PROVIDER_CLAIM in str(deterministic.get("provider_output") or ""), "provider completion claim missing")
        require(deterministic.get("lbe_completion_truth") is False, "provider completion truth was accepted")
        require(code.get("status") == "running", f"post-reasoning task status={code.get('status')}")
        print("R7_OBS10_PROVIDER_TURN_COMPLETED=PASS")
        print("R7_OBS10_PROVIDER_COMPLETION_TRUTH_FALSE=PASS")
        print("R7_OBS10_REASONING_COMPLETION_PROVISIONAL=PASS")

        status = json_stdout(
            run(
                [
                    str(lbe), "session", "status",
                    "--database", str(database),
                    "--session-id", SESSION_ID,
                    "--task-id", TASK_ID,
                ],
                cwd=probe,
                env=env,
            ),
            "session status after reasoning",
        )
        task = status.get("task") or {}
        require(task.get("status") == "running", f"persisted post-reasoning status={task.get('status')}")
        require(task.get("last_outcome") == "AWAITING_VALIDATION", f"post-reasoning last_outcome={task.get('last_outcome')}")
        print("R7_OBS10_AWAITING_VALIDATION_PERSISTED=PASS")

        validation = json_stdout(
            run(
                [
                    str(lbe), "session", "validate",
                    "--database", str(database),
                    "--session-id", SESSION_ID,
                    "--task-id", TASK_ID,
                ],
                cwd=probe,
                env=env,
            ),
            "session validate",
        )
        completion = validation.get("completion") or {}
        validated_task = validation.get("task") or {}
        require(completion.get("verdict") == "FAILED", f"completion verdict={completion.get('verdict')}")
        require(
            completion.get("satisfied_requirement_ids") == ["focused-tests"],
            f"satisfied requirements={completion.get('satisfied_requirement_ids')}",
        )
        require(
            completion.get("failed_requirement_ids") == ["source-change", "git-state"],
            f"failed requirements={completion.get('failed_requirement_ids')}",
        )
        require(validated_task.get("status") == "failed", f"validated task status={validated_task.get('status')}")
        require(validated_task.get("last_outcome") == "VALIDATION_FAILED", f"validated last_outcome={validated_task.get('last_outcome')}")
        require(validated_task.get("status") != "completed", "provider completion bypassed deterministic gate")
        require(validated_task.get("last_outcome") != "VALIDATED_COMPLETION", "provider completion produced validated completion")
        print("R7_OBS10_DETERMINISTIC_VALIDATION_REJECTED=PASS")
        print("R7_OBS10_NO_PREMATURE_VALIDATED_COMPLETION=PASS")
        print("R7_OBS10_DETERMINISTIC_COMPLETION_AUTHORITY=PASS")

        require(git(workspace, "status", "--porcelain") == baseline_status, "observable 10 changed workspace state")
        print("R7_OBS10_WORKSPACE_UNCHANGED=PASS")
        print("R7_OBS10_PROVIDER_COMPLETION_PROVISIONAL=PASS")
        print("R7_OBSERVABLE_10=PASS")
        return 0
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


if __name__ == "__main__":
    raise SystemExit(main())
