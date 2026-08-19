"""Installed R7 observable 11 positive validated-completion persistence probe."""
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
from lbe_guard_inspector.memory.completion_evidence import TaskCompletionEvidencePersistence

MODEL = "r7-obs11-model"
SESSION_ID = "r7-obs11-session"
TASK_ID = "r7-obs11-task"
PROJECT_ID = "r7-obs11-project"
CALL_ID = "call_r7_obs11_create_1"
TARGET = "r7-obs11-created.txt"
CONTENT = "R7 observable 11 validated completion proof\n"


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


def tool_call_response() -> list[dict[str, Any]]:
    return [
        {
            "id": "chatcmpl-r7-obs11-tool",
            "object": "chat.completion.chunk",
            "created": 1,
            "model": MODEL,
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": CALL_ID,
                                "type": "function",
                                "function": {
                                    "name": "lbe_0_workspace_create_candidate_text",
                                    "arguments": json.dumps(
                                        {"path": TARGET, "content": CONTENT},
                                        separators=(",", ":"),
                                    ),
                                },
                            }
                        ],
                    },
                    "finish_reason": None,
                }
            ],
        },
        {
            "id": "chatcmpl-r7-obs11-tool",
            "object": "chat.completion.chunk",
            "created": 1,
            "model": MODEL,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        },
    ]


def final_response() -> list[dict[str, Any]]:
    return [
        {
            "id": "chatcmpl-r7-obs11-final",
            "object": "chat.completion.chunk",
            "created": 1,
            "model": MODEL,
            "choices": [
                {
                    "index": 0,
                    "delta": {"role": "assistant", "content": "Governed task turn complete; LBE must validate."},
                    "finish_reason": None,
                }
            ],
        },
        {
            "id": "chatcmpl-r7-obs11-final",
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
        self.responses = [tool_call_response(), final_response()]
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
        require(bool(self.server.responses), "provider received unexpected extra request")
        chunks = self.server.responses.pop(0)
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
    print("R7_OBS11_PACKAGE_FILE=" + str(package_file))

    probe = installed_root / f"obs11-{uuid4().hex}"
    workspace = probe / "workspace"
    state_dir = probe / "state"
    workspace.mkdir(parents=True)
    state_dir.mkdir(parents=True)
    print("R7_OBS11_PROBE_ROOT=" + str(probe))

    (workspace / "test_smoke.py").write_text("def test_smoke():\n    assert True\n", encoding="utf-8")
    (workspace / ".gitignore").write_text("__pycache__/\n.pytest_cache/\n", encoding="utf-8")
    git(workspace, "init", "-q")
    git(workspace, "config", "user.email", "r7@example.invalid")
    git(workspace, "config", "user.name", "R7 Probe")
    git(workspace, "add", "test_smoke.py", ".gitignore")
    git(workspace, "commit", "-q", "-m", "R7 observable 11 baseline")
    require(git(workspace, "status", "--porcelain") == "", "baseline workspace not clean")

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
                    "api_key": "R7_OBS11_SECRET_NEVER_ECHO",
                }
            ),
            encoding="utf-8",
        )

        created_session = json_stdout(
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
                    "--profile", "r7-obs11-profile",
                    "--permission-policy", "r7-obs11-permissions",
                    "--evidence-policy", "r7-obs11-evidence",
                ],
                cwd=probe,
                env=env,
            ),
            "session create",
        )
        original_session = created_session.get("session") or {}
        require(original_session.get("session_id") == SESSION_ID, "created session identity mismatch")

        code = json_stdout(
            run(
                [
                    str(lbe), "code",
                    "--database", str(database),
                    "--session-id", SESSION_ID,
                    "--task-id", TASK_ID,
                    "--provider-config", str(provider),
                    "--problem", f"Create {TARGET} with the exact requested content and then finish the turn.",
                    "--request-id", "r7-obs11-request",
                ],
                cwd=probe,
                env=env,
            ),
            "installed code",
        )
        require(len(server.requests) == 2, f"provider request count={len(server.requests)}")
        require(code.get("outcome") == "COMPLETED", f"reasoning outcome={code.get('outcome')}")
        require(code.get("status") == "running", f"post-reasoning task status={code.get('status')}")
        deterministic = (code.get("response") or {}).get("deterministic_result") or {}
        require(deterministic.get("lbe_completion_truth") is False, "provider completion truth was accepted")
        receipts = deterministic.get("governed_tool_receipts") or []
        require(len(receipts) == 1, f"expected one governed receipt, got {len(receipts)}")
        require(receipts[0].get("status") == "EXECUTED", f"governed receipt status={receipts[0].get('status')}")
        require(receipts[0].get("tool_id") == "workspace.create_candidate_text", "wrong governed tool")
        require((workspace / TARGET).read_text(encoding="utf-8") == CONTENT, "governed mutation content mismatch")
        print("R7_OBS11_GOVERNED_MUTATION=PASS")
        print("R7_OBS11_PROVIDER_COMPLETION_TRUTH_FALSE=PASS")

        store = WorkspaceMemoryStore(database)
        contract = TaskCompletionContractPersistence(store).load(
            session_id=SESSION_ID,
            task_id=TASK_ID,
            project_workspace_id=PROJECT_ID,
        )
        require(contract is not None, "registered completion contract missing")
        contract_kinds = [item.evidence_kind for item in contract.requirements]
        require(contract_kinds == ["source_change", "focused_test", "git_status"], f"contract kinds={contract_kinds}")
        evidence = TaskCompletionEvidencePersistence(store).load(
            session_id=SESSION_ID,
            task_id=TASK_ID,
            project_workspace_id=PROJECT_ID,
        )
        latest_by_kind = {item.kind: item for item in evidence}
        require(set(latest_by_kind) == {"source_change", "focused_test", "git_status"}, f"evidence kinds={sorted(latest_by_kind)}")
        require(all(latest_by_kind[kind].status == "PASS" for kind in latest_by_kind), f"evidence statuses={[(k, v.status) for k, v in latest_by_kind.items()]}")
        evidence_ids_before = sorted(item.evidence_id for item in evidence)
        print("R7_OBS11_REGISTERED_CONTRACT=PASS")
        print("R7_OBS11_ALL_COMPLETION_EVIDENCE_PASS=PASS")

        pre_validation = json_stdout(
            run(
                [str(lbe), "session", "status", "--database", str(database), "--session-id", SESSION_ID, "--task-id", TASK_ID],
                cwd=probe,
                env=env,
            ),
            "pre-validation session status",
        )
        pre_task = pre_validation.get("task") or {}
        require(pre_task.get("status") == "running", f"pre-validation status={pre_task.get('status')}")
        require(pre_task.get("last_outcome") == "AWAITING_VALIDATION", f"pre-validation outcome={pre_task.get('last_outcome')}")
        print("R7_OBS11_AWAITING_VALIDATION_PERSISTED=PASS")

        validation = json_stdout(
            run(
                [str(lbe), "session", "validate", "--database", str(database), "--session-id", SESSION_ID, "--task-id", TASK_ID],
                cwd=probe,
                env=env,
            ),
            "session validate",
        )
        completion = validation.get("completion") or {}
        validated_task = validation.get("task") or {}
        require(completion.get("verdict") == "READY", f"completion verdict={completion.get('verdict')}")
        require(completion.get("satisfied_requirement_ids") == ["source-change", "focused-tests", "git-state"], f"satisfied={completion.get('satisfied_requirement_ids')}")
        require(completion.get("missing_requirement_ids") == [], f"missing={completion.get('missing_requirement_ids')}")
        require(completion.get("failed_requirement_ids") == [], f"failed={completion.get('failed_requirement_ids')}")
        require(validated_task.get("status") == "completed", f"validated status={validated_task.get('status')}")
        require(validated_task.get("last_outcome") == "VALIDATED_COMPLETION", f"validated outcome={validated_task.get('last_outcome')}")
        print("R7_OBS11_VALIDATION_READY=PASS")
        print("R7_OBS11_VALIDATED_COMPLETION_PERSISTED=PASS")

        fresh_status = json_stdout(
            run(
                [str(lbe), "session", "status", "--database", str(database), "--session-id", SESSION_ID, "--task-id", TASK_ID],
                cwd=probe,
                env=env,
            ),
            "fresh-process session status",
        )
        fresh_task = fresh_status.get("task") or {}
        require(fresh_status.get("session_id") == SESSION_ID, "fresh session id mismatch")
        require(fresh_status.get("workspace") == str(workspace).replace("\\", "/"), f"fresh workspace={fresh_status.get('workspace')}")
        require(fresh_status.get("provider_id") == "openai-compatible", "fresh provider id mismatch")
        require(fresh_status.get("provider_model") == MODEL, "fresh provider model mismatch")
        require(fresh_task.get("task_id") == TASK_ID, "fresh task id mismatch")
        require(fresh_task.get("status") == "completed", f"fresh task status={fresh_task.get('status')}")
        require(fresh_task.get("last_outcome") == "VALIDATED_COMPLETION", f"fresh task outcome={fresh_task.get('last_outcome')}")

        fresh_continue = json_stdout(
            run(
                [str(lbe), "session", "continue", "--database", str(database), "--session-id", SESSION_ID, "--task-id", TASK_ID],
                cwd=probe,
                env=env,
            ),
            "fresh-process session continue",
        )
        continued_session = fresh_continue.get("session") or {}
        require(continued_session.get("session_id") == SESSION_ID, "continued session id mismatch")
        require(continued_session.get("project_workspace_id") == PROJECT_ID, "continued workspace identity mismatch")
        require(continued_session.get("provider_id") == "openai-compatible", "continued provider identity mismatch")
        require(continued_session.get("provider_model") == MODEL, "continued provider model mismatch")

        fresh_store = WorkspaceMemoryStore(database)
        fresh_contract = TaskCompletionContractPersistence(fresh_store).load(
            session_id=SESSION_ID,
            task_id=TASK_ID,
            project_workspace_id=PROJECT_ID,
        )
        fresh_evidence = TaskCompletionEvidencePersistence(fresh_store).load(
            session_id=SESSION_ID,
            task_id=TASK_ID,
            project_workspace_id=PROJECT_ID,
        )
        require(fresh_contract is not None, "completion contract missing after fresh process")
        require([item.evidence_kind for item in fresh_contract.requirements] == contract_kinds, "completion contract changed across fresh process")
        require(sorted(item.evidence_id for item in fresh_evidence) == evidence_ids_before, "completion evidence changed across fresh process")
        require(all(item.status == "PASS" for item in fresh_evidence), "fresh completion evidence not all PASS")
        print("R7_OBS11_FRESH_PROCESS_TERMINAL_STATE=PASS")
        print("R7_OBS11_SESSION_TASK_IDENTITY_PRESERVED=PASS")
        print("R7_OBS11_COMPLETION_EVIDENCE_PERSISTED=PASS")
        print("R7_OBS11_VALIDATED_COMPLETION_FRESH_PROCESS=PASS")
        print("R7_OBSERVABLE_11=PASS")
        return 0
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


if __name__ == "__main__":
    raise SystemExit(main())
