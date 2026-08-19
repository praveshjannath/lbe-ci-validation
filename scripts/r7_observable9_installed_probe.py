"""Installed R7 observable 9 receipt/provider-continuation correlation probe."""
from __future__ import annotations

import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
from typing import Any

MODEL = "r7-obs9-model"
CALL_ID = "call_r7_obs9_create_1"
TARGET = "r7-obs9-created.txt"
CONTENT = "R7 observable 9 correlated result\n"


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
            "id": "chatcmpl-r7-obs9-tool",
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
            "id": "chatcmpl-r7-obs9-tool",
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
            "id": "chatcmpl-r7-obs9-final",
            "object": "chat.completion.chunk",
            "created": 1,
            "model": MODEL,
            "choices": [
                {
                    "index": 0,
                    "delta": {"role": "assistant", "content": "correlated governed result received"},
                    "finish_reason": None,
                }
            ],
        },
        {
            "id": "chatcmpl-r7-obs9-final",
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


def message_has_assistant_call(messages: list[Any]) -> bool:
    for message in messages:
        if not isinstance(message, dict):
            continue
        for call in message.get("tool_calls") or []:
            if isinstance(call, dict) and call.get("id") == CALL_ID:
                return True
    return False


def message_has_tool_result(messages: list[Any], expected_hash: str) -> bool:
    for message in messages:
        if not isinstance(message, dict) or message.get("tool_call_id") != CALL_ID:
            continue
        serialized = json.dumps(message, sort_keys=True)
        if TARGET in serialized and expected_hash in serialized:
            return True
    return False


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

    probe = installed_root / "obs9"
    if probe.exists():
        shutil.rmtree(probe)
    workspace = probe / "workspace"
    state_dir = probe / "state"
    workspace.mkdir(parents=True)
    state_dir.mkdir(parents=True)
    (workspace / "test_smoke.py").write_text("def test_smoke():\n    assert True\n", encoding="utf-8")
    git(workspace, "init", "-q")
    git(workspace, "config", "user.email", "r7@example.invalid")
    git(workspace, "config", "user.name", "R7 Probe")
    git(workspace, "add", "test_smoke.py")
    git(workspace, "commit", "-q", "-m", "R7 observable 9 baseline")

    database = probe / "memory.sqlite"
    config = probe / "config.json"
    governance = probe / "governance.json"
    provider = probe / "provider.json"
    config.write_text(
        json.dumps({"knowledge_roots": [{"name": "r7-obs9-project", "path": str(workspace)}]}),
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

    identity = run(
        [str(python_exe), "-I", "-c", "import lbe_guard_inspector; print(lbe_guard_inspector.__file__)"],
        cwd=installed_root,
        env=env,
    )
    require(identity.returncode == 0, f"isolated import failed: {identity.stderr}")
    package_file = identity.stdout.strip()
    require("site-packages" in package_file.lower(), "runtime is not installed site-packages")
    require("agents-memory-tool-v6-integration" not in package_file.lower(), "source checkout import leakage")
    print("R7_OBS9_PACKAGE_FILE=" + package_file)

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
                    "api_key": "R7_OBS9_SECRET_NEVER_ECHO",
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
                    "--project-workspace-id", "r7-obs9-project",
                    "--session-id", "r7-obs9-session",
                    "--mode", "coding",
                    "--permission", "write_allowed",
                    "--runtime-policy", "development",
                    "--provider", "openai-compatible",
                    "--model", MODEL,
                    "--profile", "r7-obs9-profile",
                    "--permission-policy", "r7-obs9-permissions",
                    "--evidence-policy", "r7-obs9-evidence",
                ],
                cwd=probe,
                env=env,
            ),
            "session create",
        )
        result = json_stdout(
            run(
                [
                    str(lbe), "code",
                    "--database", str(database),
                    "--session-id", "r7-obs9-session",
                    "--task-id", "r7-obs9-task",
                    "--provider-config", str(provider),
                    "--problem", f"Create {TARGET} with the exact requested content.",
                    "--request-id", "r7-obs9-request",
                ],
                cwd=probe,
                env=env,
            ),
            "installed code",
        )

        target = workspace / TARGET
        require(target.is_file(), "correlated mutation target missing")
        raw = target.read_bytes()
        require(raw == CONTENT.encode("utf-8"), "created content mismatch")
        expected_hash = hashlib.sha256(raw).hexdigest()

        response = result.get("response") or {}
        deterministic = response.get("deterministic_result") or {}
        receipts = deterministic.get("governed_tool_receipts") or []
        require(len(receipts) == 1, f"expected one receipt, got {len(receipts)}")
        receipt = receipts[0]
        require(receipt.get("status") == "EXECUTED", f"receipt status={receipt.get('status')}")
        require(receipt.get("tool_id") == "workspace.create_candidate_text", "wrong receipt tool")
        receipt_id = str(receipt.get("receipt_id") or "")
        operation_id = str(receipt.get("operation_id") or "")
        turn_id = str(deterministic.get("turn_id") or "")
        require(receipt_id.startswith("receipt-"), "receipt identity missing")
        require(bool(turn_id), "turn identity missing")
        require(operation_id == f"{turn_id}:tool:{CALL_ID}", f"operation correlation mismatch: {operation_id}")
        output = receipt.get("output") or {}
        require(output.get("path") == TARGET, "receipt output path mismatch")
        require(output.get("sha256") == expected_hash, "receipt output hash mismatch")
        require(deterministic.get("lbe_completion_truth") is False, "provider asserted completion truth")

        require(len(server.requests) == 2, f"provider request count={len(server.requests)}")
        first_body = server.requests[0].get("body") or {}
        second_body = server.requests[1].get("body") or {}
        require(CALL_ID not in json.dumps(first_body, sort_keys=True), "call id unexpectedly existed before provider emitted it")
        messages = second_body.get("messages") or []
        require(isinstance(messages, list), "second provider request messages missing")
        require(message_has_assistant_call(messages), "continuation lost assistant tool_call_id")
        require(message_has_tool_result(messages, expected_hash), "continuation lost correlated governed tool result")
        require(json.dumps(second_body, sort_keys=True).count(CALL_ID) >= 2, "tool-call identity not paired in continuation")
        require(git(workspace, "status", "--porcelain").count(TARGET) == 1, "mutation executed more than once or Git result unexpected")

        print("R7_OBS9_PROVIDER_TOOL_CALL_ID=" + CALL_ID)
        print("R7_OBS9_TURN_ID=" + turn_id)
        print("R7_OBS9_OPERATION_ID=" + operation_id)
        print("R7_OBS9_RECEIPT_ID=" + receipt_id)
        print("R7_OBS9_CREATED_SHA256=" + expected_hash)
        print("R7_OBS9_PROVIDER_REQUESTS=2")
        print("R7_OBS9_ONE_TOOL_CALL_ONE_RECEIPT=PASS")
        print("R7_OBS9_OPERATION_ID_CORRELATED=PASS")
        print("R7_OBS9_RECEIPT_OUTPUT_CORRELATED=PASS")
        print("R7_OBS9_CONTINUATION_TOOL_CALL_ID_CORRELATED=PASS")
        print("R7_OBS9_CONTINUATION_GOVERNED_RESULT_CORRELATED=PASS")
        print("R7_OBS9_SINGLE_MUTATION_EXECUTION=PASS")
        print("R7_OBS9_SAME_TURN_PROVIDER_CONTINUATION=PASS")
        print("R7_OBS9_RECEIPT_PROVIDER_CONTINUATION_CORRELATION=PASS")
        print("R7_OBSERVABLE_9=PASS")
        return 0
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


if __name__ == "__main__":
    raise SystemExit(main())
