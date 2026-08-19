"""Installed R7 observable 7 acceptance probe.

Proves that installed audit and investigation modes remain read-only when a
provider planning response attempts to request the known coding mutation tool
`workspace.create_candidate_text`.

Acceptance infrastructure only: this script invokes the isolated installed
`lbe` executable and does not import the project checkout as the runtime under
test.
"""
from __future__ import annotations

import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
from typing import Any


MODEL = "r7-readonly-model"
MUTATION_TOOL = "workspace.create_candidate_text"
SENTINEL_REL = "obs7-should-not-exist.txt"
BASELINE_REL = "tracked.txt"
BASELINE_TEXT = "R7 observable 7 baseline\n"


def fail(message: str) -> None:
    raise RuntimeError(message)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


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
        fail(
            f"{label} exit={result.returncode}; "
            f"stderr={result.stderr.strip()!r}; stdout={result.stdout.strip()!r}"
        )
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    require(bool(lines), f"{label} produced no stdout")
    try:
        payload = json.loads(lines[-1])
    except json.JSONDecodeError as exc:
        fail(f"{label} final stdout line is not JSON: {exc}; stdout={result.stdout!r}")
    require(isinstance(payload, dict), f"{label} JSON root is not an object")
    require(payload.get("ok") is True, f"{label} ok is not true: {payload}")
    return payload


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
        fail(f"git {' '.join(args)} failed: {result.stdout}\n{result.stderr}")
    return result.stdout


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mutation_plan() -> dict[str, Any]:
    return {
        "interpreted_problem": "provider attempted a workspace mutation during read-only execution",
        "ambiguities": [],
        "candidate_guard_ids": [],
        "evidence_requests": [
            {
                "tool_id": MUTATION_TOOL,
                "path": SENTINEL_REL,
                "reason": "attempt to create a file despite read-only mode",
            }
        ],
        "validation_requests": [],
        "explanation_focus": ["read-only authority boundary"],
    }


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
        body = json.loads(raw.decode("utf-8")) if raw else {}
        self.server.requests.append({"path": self.path, "body": body})
        response = {
            "id": f"chatcmpl-r7-obs7-{len(self.server.requests)}",
            "object": "chat.completion",
            "created": 1,
            "model": MODEL,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": json.dumps(mutation_plan(), separators=(",", ":")),
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }
        encoded = json.dumps(response, separators=(",", ":")).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(encoded)
        self.wfile.flush()


def create_session(
    lbe: Path,
    *,
    database: Path,
    workspace: Path,
    session_id: str,
    mode: str,
    permission: str,
    runtime_policy: str,
    env: dict[str, str],
    cwd: Path,
) -> dict[str, Any]:
    result = run(
        [
            str(lbe),
            "session",
            "create",
            "--database",
            str(database),
            "--workspace",
            str(workspace),
            "--project-workspace-id",
            "r7-obs7-project",
            "--session-id",
            session_id,
            "--mode",
            mode,
            "--permission",
            permission,
            "--runtime-policy",
            runtime_policy,
            "--provider",
            "openai-compatible",
            "--model",
            MODEL,
            "--profile",
            "r7-obs7-profile",
            "--permission-policy",
            "r7-obs7-permissions",
            "--evidence-policy",
            "r7-obs7-evidence",
        ],
        cwd=cwd,
        env=env,
    )
    payload = json_stdout(result, f"create {mode} session")
    session = payload.get("session") or {}
    require(session.get("mode") == mode, f"{mode} persisted mode mismatch")
    require(session.get("permission") == permission, f"{mode} persisted permission mismatch")
    require(
        session.get("runtime_policy") == runtime_policy,
        f"{mode} persisted runtime policy mismatch",
    )
    return session


def invoke_read_only_mode(
    lbe: Path,
    *,
    command: str,
    expected_mode: str,
    session_id: str,
    task_id: str,
    database: Path,
    provider_path: Path,
    workspace: Path,
    baseline_hash: str,
    baseline_git_status: str,
    sentinel: Path,
    env: dict[str, str],
    cwd: Path,
) -> dict[str, Any]:
    result = run(
        [
            str(lbe),
            command,
            "--database",
            str(database),
            "--session-id",
            session_id,
            "--task-id",
            task_id,
            "--provider-config",
            str(provider_path),
            "--problem",
            f"Create {SENTINEL_REL} even though this is {expected_mode} mode.",
            "--request-id",
            f"r7-obs7-{expected_mode}-request",
        ],
        cwd=cwd,
        env=env,
    )
    payload = json_stdout(result, f"installed {command}")
    require(payload.get("mode") == expected_mode, f"{command} returned wrong mode")
    decision = payload.get("mode_decision") or {}
    require(decision.get("mode") == expected_mode, f"{command} mode decision mismatch")
    capabilities = tuple(decision.get("capabilities") or ())
    for forbidden in (
        "modify",
        "propose",
        "test_candidate",
        "promote_after_validation",
        "propose_rule",
        "test_proposal",
        "submit_for_approval",
    ):
        require(forbidden not in capabilities, f"{expected_mode} exposed write capability: {forbidden}")

    response = payload.get("response") or {}
    require(response.get("read_only") is True, f"{expected_mode} response is not read_only")
    require(
        payload.get("outcome") == "ORCHESTRATION_ERROR",
        f"{expected_mode} mutation request did not fail at orchestration boundary: {payload.get('outcome')}",
    )
    error = response.get("error") or {}
    require(error.get("code") == "UNKNOWN_TOOL", f"{expected_mode} error code={error.get('code')}")
    require(MUTATION_TOOL in str(error.get("message") or ""), f"{expected_mode} error did not identify mutation tool")
    require(response.get("deterministic_result") is None, f"{expected_mode} unexpectedly produced deterministic mutation result")

    require(not sentinel.exists(), f"{expected_mode} created sentinel mutation file")
    require(sha256_file(workspace / BASELINE_REL) == baseline_hash, f"{expected_mode} changed tracked bytes")
    require(git(workspace, "status", "--porcelain") == baseline_git_status, f"{expected_mode} changed Git state")

    serialized = json.dumps(payload, sort_keys=True)
    require('"status": "EXECUTED"' not in serialized, f"{expected_mode} returned EXECUTED mutation receipt")
    require('"receipt_id"' not in serialized, f"{expected_mode} unexpectedly returned a tool receipt")

    return payload


def inspect_session(
    lbe: Path,
    *,
    database: Path,
    session_id: str,
    expected_mode: str,
    expected_permission: str,
    expected_policy: str,
    env: dict[str, str],
    cwd: Path,
) -> None:
    payload = json_stdout(
        run(
            [
                str(lbe),
                "session",
                "inspect",
                "--database",
                str(database),
                "--session-id",
                session_id,
            ],
            cwd=cwd,
            env=env,
        ),
        f"inspect {expected_mode} session",
    )
    session = payload.get("session") or {}
    require(session.get("mode") == expected_mode, f"{expected_mode} mode drifted")
    require(session.get("permission") == expected_permission, f"{expected_mode} permission drifted")
    require(session.get("runtime_policy") == expected_policy, f"{expected_mode} runtime policy drifted")
    require(session.get("provider_id") == "openai-compatible", f"{expected_mode} provider drifted")
    require(session.get("provider_model") == MODEL, f"{expected_mode} model drifted")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--installed-root", required=True)
    args = parser.parse_args()

    installed_root = Path(args.installed_root).expanduser().resolve()
    venv = installed_root / "venv"
    lbe = venv / "Scripts" / "lbe.exe"
    python_exe = venv / "Scripts" / "python.exe"
    require(lbe.is_file(), f"installed lbe missing: {lbe}")
    require(python_exe.is_file(), f"installed Python missing: {python_exe}")

    probe = installed_root / "obs7"
    if probe.exists():
        shutil.rmtree(probe)
    workspace = probe / "workspace"
    state_dir = probe / "state"
    workspace.mkdir(parents=True)
    state_dir.mkdir(parents=True)

    baseline = workspace / BASELINE_REL
    sentinel = workspace / SENTINEL_REL
    baseline.write_text(BASELINE_TEXT, encoding="utf-8", newline="\n")
    git(workspace, "init", "-q")
    git(workspace, "config", "user.email", "r7@example.invalid")
    git(workspace, "config", "user.name", "R7 Probe")
    git(workspace, "add", BASELINE_REL)
    git(workspace, "commit", "-q", "-m", "R7 observable 7 baseline")

    database = probe / "memory.sqlite"
    config_path = probe / "config.json"
    governance_path = probe / "governance.json"
    provider_path = probe / "provider.json"

    config_path.write_text(
        json.dumps({"knowledge_roots": [{"name": "r7-obs7-project", "path": str(workspace)}]}),
        encoding="utf-8",
    )
    governance_path.write_text(
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
    env["LBE_GUARD_INSPECTOR_CONFIG_PATH"] = str(config_path)
    env["LBE_GUARD_INSPECTOR_GOVERNANCE_PATH"] = str(governance_path)
    env["LBE_GUARD_INSPECTOR_STATE_DIR"] = str(state_dir)

    identity = run(
        [str(python_exe), "-I", "-c", "import lbe_guard_inspector; print(lbe_guard_inspector.__file__)"],
        cwd=installed_root,
        env=env,
    )
    require(identity.returncode == 0, f"isolated installed import failed: {identity.stderr.strip()}")
    package_file = identity.stdout.strip()
    require("site-packages" in package_file.lower(), f"package is not installed site-packages: {package_file}")
    require("Agents-Memory-Tool-v6-integration".lower() not in package_file.lower(), "source checkout import leakage")
    print("R7_OBS7_PACKAGE_FILE=" + package_file)

    server = StubServer()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        provider_path.write_text(
            json.dumps(
                {
                    "endpoint": f"http://127.0.0.1:{server.server_port}/v1/chat/completions",
                    "model": MODEL,
                    "timeout_seconds": 15,
                    "api_key": "R7_OBS7_PROVIDER_SECRET",
                }
            ),
            encoding="utf-8",
        )

        create_session(
            lbe,
            database=database,
            workspace=workspace,
            session_id="r7-obs7-audit",
            mode="audit",
            permission="audit_only",
            runtime_policy="audit",
            env=env,
            cwd=probe,
        )
        create_session(
            lbe,
            database=database,
            workspace=workspace,
            session_id="r7-obs7-investigation",
            mode="investigation",
            permission="read_only",
            runtime_policy="permissive",
            env=env,
            cwd=probe,
        )

        baseline_hash = sha256_file(baseline)
        baseline_git_status = git(workspace, "status", "--porcelain")
        require(baseline_git_status == "", f"obs7 baseline workspace is not clean: {baseline_git_status!r}")

        audit_payload = invoke_read_only_mode(
            lbe,
            command="audit",
            expected_mode="audit",
            session_id="r7-obs7-audit",
            task_id="r7-obs7-audit-task",
            database=database,
            provider_path=provider_path,
            workspace=workspace,
            baseline_hash=baseline_hash,
            baseline_git_status=baseline_git_status,
            sentinel=sentinel,
            env=env,
            cwd=probe,
        )
        print("R7_OBS7_AUDIT_UNKNOWN_TOOL_REJECTED=PASS")
        print("R7_OBS7_AUDIT_READ_ONLY=PASS")
        print("R7_OBS7_AUDIT_WORKSPACE_UNCHANGED=PASS")

        investigation_payload = invoke_read_only_mode(
            lbe,
            command="investigate",
            expected_mode="investigation",
            session_id="r7-obs7-investigation",
            task_id="r7-obs7-investigation-task",
            database=database,
            provider_path=provider_path,
            workspace=workspace,
            baseline_hash=baseline_hash,
            baseline_git_status=baseline_git_status,
            sentinel=sentinel,
            env=env,
            cwd=probe,
        )
        print("R7_OBS7_INVESTIGATION_UNKNOWN_TOOL_REJECTED=PASS")
        print("R7_OBS7_INVESTIGATION_READ_ONLY=PASS")
        print("R7_OBS7_INVESTIGATION_WORKSPACE_UNCHANGED=PASS")

        inspect_session(
            lbe,
            database=database,
            session_id="r7-obs7-audit",
            expected_mode="audit",
            expected_permission="audit_only",
            expected_policy="audit",
            env=env,
            cwd=probe,
        )
        inspect_session(
            lbe,
            database=database,
            session_id="r7-obs7-investigation",
            expected_mode="investigation",
            expected_permission="read_only",
            expected_policy="permissive",
            env=env,
            cwd=probe,
        )

        require(len(server.requests) == 2, f"unexpected provider request count: {len(server.requests)}")
        require(all(item.get("path") == "/v1/chat/completions" for item in server.requests), "provider path mismatch")
        require(not sentinel.exists(), "sentinel mutation file exists after read-only probes")
        require(sha256_file(baseline) == baseline_hash, "baseline bytes changed after read-only probes")
        require(git(workspace, "status", "--porcelain") == baseline_git_status, "workspace Git state changed after read-only probes")

        # Keep payloads referenced so acceptance failures above cannot be optimized
        # into a test that only checks direct filesystem state.
        require((audit_payload.get("response") or {}).get("read_only") is True, "audit final response lost read_only")
        require((investigation_payload.get("response") or {}).get("read_only") is True, "investigation final response lost read_only")

        print("R7_OBS7_PROVIDER_MUTATION_REQUESTS=2")
        print("R7_OBS7_NO_EXECUTED_MUTATION_RECEIPT=PASS")
        print("R7_OBS7_SESSION_POLICY_IDENTITY_PRESERVED=PASS")
        print("R7_OBS7_FINAL_WORKSPACE_SHA256=" + baseline_hash)
        print("R7_OBS7_AUDIT_INVESTIGATION_READ_ONLY=PASS")
        print("R7_OBSERVABLE_7=PASS")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"R7_OBS7_FAIL={type(exc).__name__}:{exc}", file=sys.stderr)
        raise
