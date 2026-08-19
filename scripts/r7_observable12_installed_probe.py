"""Installed R7 observable 12 credential/secret non-leakage probe."""
from __future__ import annotations

import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import threading
from typing import Any
from uuid import uuid4

from lbe_guard_inspector.memory import WorkspaceMemoryStore
from lbe_guard_inspector.memory.completion_evidence import TaskCompletionEvidencePersistence

MODEL = "r7-obs12-model"
SESSION_ID = "r7-obs12-session"
TASK_ID = "r7-obs12-task"
PROJECT_ID = "r7-obs12-project"
CALL_ID = "call_r7_obs12_create_1"
TARGET = "r7-obs12-created.txt"
CONTENT = "R7 observable 12 bounded artifact\n"


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
            "id": "chatcmpl-r7-obs12-tool",
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
            "id": "chatcmpl-r7-obs12-tool",
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
            "id": "chatcmpl-r7-obs12-final",
            "object": "chat.completion.chunk",
            "created": 1,
            "model": MODEL,
            "choices": [
                {
                    "index": 0,
                    "delta": {"role": "assistant", "content": "Governed result received; LBE remains completion authority."},
                    "finish_reason": None,
                }
            ],
        },
        {
            "id": "chatcmpl-r7-obs12-final",
            "object": "chat.completion.chunk",
            "created": 1,
            "model": MODEL,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        },
    ]


class StubServer(ThreadingHTTPServer):
    def __init__(self, canary: str) -> None:
        super().__init__(("127.0.0.1", 0), StubHandler)
        self.canary = canary
        self.responses = [tool_call_response(), final_response()]
        self.requests: list[dict[str, Any]] = []
        self.authorization_matches = 0


class StubHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("content-length", "0"))
        raw = self.rfile.read(length)
        request = json.loads(raw.decode("utf-8")) if raw else {}
        authorization = self.headers.get("Authorization")
        if authorization == f"Bearer {self.server.canary}":
            self.server.authorization_matches += 1
        require(self.server.canary not in raw.decode("utf-8", errors="replace"), "credential leaked into provider JSON body")
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


def assert_text_clean(label: str, value: object, canary: str) -> None:
    serialized = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    require(canary not in serialized, f"credential leaked into {label}")


def assert_tree_clean(root: Path, canary: bytes, *, label: str) -> int:
    checked = 0
    if not root.exists():
        return checked
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise RuntimeError(f"cannot inspect {label} file {path}: {exc}") from exc
        checked += 1
        require(canary not in data, f"credential leaked into {label} file: {path}")
    return checked


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
    print("R7_OBS12_PACKAGE_FILE=" + str(package_file))

    source_root = Path.cwd().resolve()
    require((source_root / ".git").exists(), "probe must run from project source checkout")
    source_status_before = git(source_root, "status", "--porcelain")
    require(source_status_before == "", f"source checkout not clean before probe: {source_status_before!r}")

    probe = installed_root / f"obs12-{uuid4().hex}"
    workspace = probe / "workspace"
    state_dir = probe / "state"
    workspace.mkdir(parents=True)
    state_dir.mkdir(parents=True)
    print("R7_OBS12_PROBE_ROOT=" + str(probe))

    (workspace / "test_smoke.py").write_text("def test_smoke():\n    assert True\n", encoding="utf-8")
    (workspace / ".gitignore").write_text("__pycache__/\n.pytest_cache/\n", encoding="utf-8")
    git(workspace, "init", "-q")
    git(workspace, "config", "user.email", "r7@example.invalid")
    git(workspace, "config", "user.name", "R7 Probe")
    git(workspace, "add", "test_smoke.py", ".gitignore")
    git(workspace, "commit", "-q", "-m", "R7 observable 12 baseline")
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

    canary = f"r7-obs12-canary-{uuid4().hex}"
    canary_hash = hashlib.sha256(canary.encode("utf-8")).hexdigest()
    server = StubServer(canary)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    captured_results: list[subprocess.CompletedProcess[str]] = []
    captured_json: list[dict[str, Any]] = []
    try:
        provider.write_text(
            json.dumps(
                {
                    "endpoint": f"http://127.0.0.1:{server.server_port}/v1/chat/completions",
                    "model": MODEL,
                    "timeout_seconds": 15,
                    "api_key": canary,
                }
            ),
            encoding="utf-8",
        )

        create_result = run(
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
                "--profile", "r7-obs12-profile",
                "--permission-policy", "r7-obs12-permissions",
                "--evidence-policy", "r7-obs12-evidence",
            ],
            cwd=probe,
            env=env,
        )
        captured_results.append(create_result)
        captured_json.append(json_stdout(create_result, "session create"))

        code_result = run(
            [
                str(lbe), "code",
                "--database", str(database),
                "--session-id", SESSION_ID,
                "--task-id", TASK_ID,
                "--provider-config", str(provider),
                "--problem", f"Create {TARGET} with the exact requested content and finish the turn.",
                "--request-id", "r7-obs12-request",
            ],
            cwd=probe,
            env=env,
        )
        captured_results.append(code_result)
        code = json_stdout(code_result, "installed code")
        captured_json.append(code)

        status_result = run(
            [str(lbe), "session", "status", "--database", str(database), "--session-id", SESSION_ID, "--task-id", TASK_ID],
            cwd=probe,
            env=env,
        )
        captured_results.append(status_result)
        captured_json.append(json_stdout(status_result, "session status"))

        validation_result = run(
            [str(lbe), "session", "validate", "--database", str(database), "--session-id", SESSION_ID, "--task-id", TASK_ID],
            cwd=probe,
            env=env,
        )
        captured_results.append(validation_result)
        captured_json.append(json_stdout(validation_result, "session validate"))

        require(server.authorization_matches == 2, f"provider authorization header matches={server.authorization_matches}")
        require(len(server.requests) == 2, f"provider request count={len(server.requests)}")
        assert_text_clean("provider request bodies", server.requests, canary)
        print("R7_OBS12_AUTH_HEADER_ONLY_SECRET_USE=PASS")
        print("R7_OBS12_PROVIDER_JSON_BODY_CLEAN=PASS")

        response = code.get("response") or {}
        deterministic = response.get("deterministic_result") or {}
        receipts = deterministic.get("governed_tool_receipts") or []
        require(len(receipts) == 1, f"expected one governed receipt, got {len(receipts)}")
        require(receipts[0].get("status") == "EXECUTED", f"receipt status={receipts[0].get('status')}")
        assert_text_clean("deterministic result", deterministic, canary)
        assert_text_clean("governed receipts", receipts, canary)
        print("R7_OBS12_RUNTIME_RESULT_CLEAN=PASS")
        print("R7_OBS12_RECEIPTS_CLEAN=PASS")

        store = WorkspaceMemoryStore(database)
        evidence = TaskCompletionEvidencePersistence(store).load(
            session_id=SESSION_ID,
            task_id=TASK_ID,
            project_workspace_id=PROJECT_ID,
        )
        require(len(evidence) >= 3, f"completion evidence count={len(evidence)}")
        assert_text_clean("completion evidence", [item.__dict__ for item in evidence], canary)
        print("R7_OBS12_COMPLETION_EVIDENCE_CLEAN=PASS")

        for index, result in enumerate(captured_results):
            assert_text_clean(f"CLI stdout[{index}]", result.stdout, canary)
            assert_text_clean(f"CLI stderr[{index}]", result.stderr, canary)
        for index, payload in enumerate(captured_json):
            assert_text_clean(f"CLI JSON[{index}]", payload, canary)
        print("R7_OBS12_CLI_STDOUT_STDERR_CLEAN=PASS")

        provider.unlink()
        checked_probe_files = assert_tree_clean(probe, canary.encode("utf-8"), label="probe persistence")
        require(checked_probe_files > 0, "probe persistence scan inspected no files")
        print("R7_OBS12_PERSISTED_STATE_CLEAN=PASS")

        assert_tree_clean(workspace, canary.encode("utf-8"), label="workspace")
        require((workspace / TARGET).read_text(encoding="utf-8") == CONTENT, "governed artifact mismatch")
        print("R7_OBS12_WORKSPACE_FILES_CLEAN=PASS")

        source_scan_roots = [
            source_root / ".lbe",
            source_root / "docs",
            source_root / "scripts",
            source_root / "lbe_guard_inspector",
            source_root / "tests",
        ]
        source_files_checked = sum(
            assert_tree_clean(root, canary.encode("utf-8"), label="source/acceptance")
            for root in source_scan_roots
        )
        require(source_files_checked > 0, "source/acceptance scan inspected no files")
        require(git(source_root, "status", "--porcelain") == source_status_before, "source checkout changed during probe")
        print("R7_OBS12_SOURCE_AND_ACCEPTANCE_ARTIFACTS_CLEAN=PASS")

        raw_db = database.read_bytes()
        require(canary.encode("utf-8") not in raw_db, "credential leaked into SQLite database")
        print("R7_OBS12_SQLITE_RAW_BYTES_CLEAN=PASS")
        print("R7_OBS12_CANARY_SHA256=" + canary_hash)
        print("R7_OBS12_NO_CREDENTIAL_SECRET_LEAKAGE=PASS")
        print("R7_OBSERVABLE_12=PASS")
        return 0
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


if __name__ == "__main__":
    raise SystemExit(main())
