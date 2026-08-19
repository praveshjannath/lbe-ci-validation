"""Installed-runtime acceptance probe for repaired R7 observable #3.

This script is test infrastructure only. It does not import the source checkout's
LBE package. Instead it invokes an explicitly supplied installed ``lbe.exe`` and
uses a local deterministic OpenAI-compatible SSE stub to force one governed
``workspace.create_candidate_text`` call followed by same-turn continuation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


_SECRET = "r7-secret-never-echo"
_EXPECTED_TEXT = "governed installed R7 proof\n"


def _tool_call_response() -> list[dict[str, Any]]:
    return [
        {
            "id": "chatcmpl-r7-tool",
            "object": "chat.completion.chunk",
            "created": 1,
            "model": "r7-model-a",
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "call_r7_create_1",
                                "type": "function",
                                "function": {
                                    "name": "lbe_0_workspace_create_candidate_text",
                                    "arguments": json.dumps(
                                        {
                                            "path": "r7-created.txt",
                                            "content": _EXPECTED_TEXT,
                                        },
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
            "id": "chatcmpl-r7-tool",
            "object": "chat.completion.chunk",
            "created": 1,
            "model": "r7-model-a",
            "choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        },
    ]


def _text_response() -> list[dict[str, Any]]:
    return [
        {
            "id": "chatcmpl-r7-final",
            "object": "chat.completion.chunk",
            "created": 1,
            "model": "r7-model-a",
            "choices": [
                {
                    "index": 0,
                    "delta": {"role": "assistant", "content": "governed tool completed"},
                    "finish_reason": None,
                }
            ],
        },
        {
            "id": "chatcmpl-r7-final",
            "object": "chat.completion.chunk",
            "created": 1,
            "model": "r7-model-a",
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        },
    ]


class _StubServer(ThreadingHTTPServer):
    def __init__(self) -> None:
        super().__init__(("127.0.0.1", 0), _StubHandler)
        self.responses = [_tool_call_response(), _text_response()]
        self.requests: list[dict[str, Any]] = []


class _StubHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("content-length", "0"))
        raw = self.rfile.read(length)
        request = json.loads(raw.decode("utf-8")) if raw else {}
        self.server.requests.append({"path": self.path, "body": request})
        if not self.server.responses:
            self.send_error(500, "no scripted response")
            return
        chunks = self.server.responses.pop(0)
        payload = "".join(
            f"data: {json.dumps(chunk, separators=(',', ':'))}\n\n" for chunk in chunks
        ) + "data: [DONE]\n\n"
        encoded = payload.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(encoded)
        self.wfile.flush()


def _run(command: list[str], *, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )


def _json_stdout(result: subprocess.CompletedProcess[str], label: str) -> dict[str, Any]:
    if result.returncode != 0:
        raise RuntimeError(
            f"{label} failed exit={result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}"
        )
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not lines:
        raise RuntimeError(f"{label} produced no stdout")
    try:
        value = json.loads(lines[-1])
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{label} final stdout line is not JSON: {lines[-1]!r}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"{label} JSON output must be an object")
    return value


def _git(workspace: Path, *args: str) -> None:
    result = subprocess.run(
        ["git", "-C", str(workspace), *args],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed: {result.stdout}\n{result.stderr}"
        )


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--installed-root", required=True)
    args = parser.parse_args()

    installed_root = Path(args.installed_root).expanduser().resolve()
    venv = installed_root / "venv"
    lbe = venv / "Scripts" / "lbe.exe"
    python_exe = venv / "Scripts" / "python.exe"
    _assert(lbe.is_file(), f"installed lbe missing: {lbe}")
    _assert(python_exe.is_file(), f"installed Python missing: {python_exe}")

    probe = installed_root / "obs3"
    if probe.exists():
        shutil.rmtree(probe)
    workspace = probe / "workspace"
    state_dir = probe / "state"
    workspace.mkdir(parents=True)
    state_dir.mkdir(parents=True)

    (workspace / "test_smoke.py").write_text(
        "def test_smoke():\n    assert True\n",
        encoding="utf-8",
        newline="\n",
    )
    _git(workspace, "init", "-q")
    _git(workspace, "config", "user.email", "r7@example.invalid")
    _git(workspace, "config", "user.name", "R7 Probe")
    _git(workspace, "add", "test_smoke.py")
    _git(workspace, "commit", "-q", "-m", "R7 baseline")

    database = probe / "memory.sqlite"
    config_path = probe / "config.json"
    governance_path = probe / "governance.json"
    provider_path = probe / "provider.json"

    config_path.write_text(
        json.dumps({"knowledge_roots": [{"name": "r7-project", "path": str(workspace)}]}),
        encoding="utf-8",
    )
    governance_path.write_text(
        json.dumps(
            {
                "allowed_read_paths": ["."],
                "allowed_write_paths": ["."],
                "forbidden_globs": [
                    "**/.git/**",
                    "**/.env",
                    "**/.env.*",
                    "**/credentials*",
                    "**/secrets*",
                ],
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

    server = _StubServer()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        provider_path.write_text(
            json.dumps(
                {
                    "endpoint": f"http://127.0.0.1:{server.server_port}/v1/chat/completions",
                    "model": "r7-model-a",
                    "timeout_seconds": 15,
                    "api_key": _SECRET,
                }
            ),
            encoding="utf-8",
        )

        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        env["PATH"] = str(venv / "Scripts") + os.pathsep + env.get("PATH", "")
        env["LBE_GUARD_INSPECTOR_CONFIG_PATH"] = str(config_path)
        env["LBE_GUARD_INSPECTOR_GOVERNANCE_PATH"] = str(governance_path)
        env["LBE_GUARD_INSPECTOR_STATE_DIR"] = str(state_dir)

        create = _run(
            [
                str(lbe),
                "session",
                "create",
                "--database",
                str(database),
                "--workspace",
                str(workspace),
                "--project-workspace-id",
                "r7-project",
                "--session-id",
                "r7-session-repair",
                "--mode",
                "coding",
                "--permission",
                "write_allowed",
                "--runtime-policy",
                "development",
                "--provider",
                "openai-compatible",
                "--model",
                "r7-model-a",
                "--profile",
                "r7-profile",
                "--permission-policy",
                "r7-permissions",
                "--evidence-policy",
                "r7-evidence",
            ],
            cwd=probe,
            env=env,
        )
        _json_stdout(create, "session create")

        code = _run(
            [
                str(lbe),
                "code",
                "--database",
                str(database),
                "--session-id",
                "r7-session-repair",
                "--task-id",
                "r7-task-create",
                "--provider-config",
                str(provider_path),
                "--problem",
                "Create r7-created.txt containing exactly: governed installed R7 proof",
                "--request-id",
                "r7-request-create",
            ],
            cwd=probe,
            env=env,
        )
        print(f"R7_CODE_EXIT={code.returncode}")
        print(code.stdout.strip())
        if code.stderr.strip():
            print("R7_CODE_STDERR=" + code.stderr.strip().replace("\n", " | "))
        _assert(_SECRET not in code.stdout and _SECRET not in code.stderr, "secret leaked to code output")
        code_json = _json_stdout(code, "installed lbe code")

        created = workspace / "r7-created.txt"
        _assert(created.is_file(), "governed mutation file missing")
        created_bytes = created.read_bytes()
        _assert(created_bytes == _EXPECTED_TEXT.encode("utf-8"), "governed mutation content mismatch")

        response = code_json.get("response") or {}
        deterministic = response.get("deterministic_result") or {}
        receipts = deterministic.get("governed_tool_receipts") or []
        _assert(isinstance(receipts, list) and len(receipts) == 1, f"receipt count={len(receipts)}")
        receipt = receipts[0]
        _assert(receipt.get("tool_id") == "workspace.create_candidate_text", "wrong tool receipt")
        _assert(receipt.get("status") == "EXECUTED", f"receipt status={receipt.get('status')}")
        authorization = receipt.get("authorization") or {}
        _assert(authorization.get("verdict") == "ALLOW", f"authorization={authorization.get('verdict')}")
        _assert(bool(receipt.get("receipt_id")), "receipt_id missing")
        _assert(bool(receipt.get("operation_id")), "operation_id missing")
        _assert(response.get("read_only") is False, "response still read_only")
        _assert(deterministic.get("runtime") == "governed_cline", "runtime is not governed_cline")
        _assert(deterministic.get("lbe_completion_truth") is False, "provider asserted LBE completion truth")
        _assert(code_json.get("outcome") == "COMPLETED", f"outcome={code_json.get('outcome')}")
        _assert(code_json.get("status") == "running", f"task status={code_json.get('status')}")

        status = _run(
            [
                str(lbe),
                "session",
                "status",
                "--database",
                str(database),
                "--session-id",
                "r7-session-repair",
                "--task-id",
                "r7-task-create",
            ],
            cwd=probe,
            env=env,
        )
        status_json = _json_stdout(status, "session status")
        task = status_json.get("task") or {}
        _assert(task.get("status") == "running", f"persisted task status={task.get('status')}")
        _assert(task.get("last_outcome") == "AWAITING_VALIDATION", f"persisted last_outcome={task.get('last_outcome')}")

        _assert(len(server.requests) == 2, f"provider request count={len(server.requests)}")
        _assert(all(item.get("path") == "/v1/chat/completions" for item in server.requests), "provider path mismatch")
        serialized_requests = json.dumps(server.requests, sort_keys=True)
        _assert(_SECRET not in serialized_requests, "secret leaked to captured provider body")

        expected_hash = hashlib.sha256(created_bytes).hexdigest()
        output = receipt.get("output") or {}
        _assert(output.get("sha256") == expected_hash, "receipt hash does not match created file")

        print("R7_OBS3_RECEIPT_ID=" + str(receipt["receipt_id"]))
        print("R7_OBS3_OPERATION_ID=" + str(receipt["operation_id"]))
        print("R7_OBS3_AUTHORIZATION=" + str(authorization["verdict"]))
        print("R7_OBS3_TOOL_STATUS=" + str(receipt["status"]))
        print("R7_OBS3_CREATED_FILE=" + str(created))
        print("R7_OBS3_CREATED_SHA256=" + expected_hash)
        print("R7_OBS3_PROVIDER_REQUESTS=2")
        print("R7_OBS3_PERSISTED_TASK_STATUS=running")
        print("R7_OBS3_PERSISTED_LAST_OUTCOME=AWAITING_VALIDATION")
        print("R7_OBS3_SECRET_OUTPUT_CHECK=PASS")
        print("R7_OBS3_GOVERNED_MUTATION=PASS")
        print("R7_OBS3_R6C_AUTHORIZATION=PASS")
        print("R7_OBS3_R6E_RECEIPT=PASS")
        print("R7_OBS3_PROVIDER_CONTINUATION=PASS")
        print("R7_OBS3_COMPLETION_AUTHORITY=PASS")
        print("R7_OBSERVABLE_3_REPAIR=PASS")
        return 0
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


if __name__ == "__main__":
    raise SystemExit(main())
