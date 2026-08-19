"""Installed R7 observable 8 acceptance probe.

Proves fail-closed behavior at two distinct installed-runtime layers:
1. normal installed coding path rejects forbidden and workspace-escape paths with no mutation;
2. installed R6C/R6E authority returns DENY/DENIED and ESCALATE/ESCALATED before handler execution.

Acceptance infrastructure only; production runtime source is not modified.
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

MODEL = "r7-obs8-model"
TOOL = "workspace.create_candidate_text"
BASELINE_REL = "tracked.txt"
BASELINE_TEXT = "R7 observable 8 baseline\n"
FORBIDDEN_REL = ".env"
ESCAPE_REL = "../r7-obs8-outside.txt"


def fail(message: str) -> None:
    raise RuntimeError(message)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def run(command: list[str], *, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=str(cwd), env=env, text=True, encoding="utf-8", errors="replace", stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def json_stdout(result: subprocess.CompletedProcess[str], label: str) -> dict[str, Any]:
    if result.returncode != 0:
        fail(f"{label} exit={result.returncode}; stderr={result.stderr.strip()!r}; stdout={result.stdout.strip()!r}")
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    require(bool(lines), f"{label} produced no stdout")
    try:
        payload = json.loads(lines[-1])
    except json.JSONDecodeError as exc:
        fail(f"{label} final stdout is not JSON: {exc}; stdout={result.stdout!r}")
    require(isinstance(payload, dict), f"{label} JSON root is not object")
    require(payload.get("ok") is True, f"{label} ok is not true: {payload}")
    return payload


def git(workspace: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(workspace), *args], text=True, encoding="utf-8", errors="replace", stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode != 0:
        fail(f"git {' '.join(args)} failed: {result.stdout}\n{result.stderr}")
    return result.stdout


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tool_call_chunks(path: str, call_id: str) -> list[dict[str, Any]]:
    return [
        {
            "id": f"chatcmpl-{call_id}", "object": "chat.completion.chunk", "created": 1, "model": MODEL,
            "choices": [{"index": 0, "delta": {"role": "assistant", "tool_calls": [{"index": 0, "id": call_id, "type": "function", "function": {"name": "lbe_0_workspace_create_candidate_text", "arguments": json.dumps({"path": path, "content": "R7 obs8 should never be written\n"}, separators=(",", ":"))}}]}, "finish_reason": None}],
        },
        {
            "id": f"chatcmpl-{call_id}", "object": "chat.completion.chunk", "created": 1, "model": MODEL,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        },
    ]


def text_chunks(tag: str) -> list[dict[str, Any]]:
    return [
        {
            "id": f"chatcmpl-{tag}-final", "object": "chat.completion.chunk", "created": 1, "model": MODEL,
            "choices": [{"index": 0, "delta": {"role": "assistant", "content": "tool result received"}, "finish_reason": None}],
        },
        {
            "id": f"chatcmpl-{tag}-final", "object": "chat.completion.chunk", "created": 1, "model": MODEL,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        },
    ]


class StubServer(ThreadingHTTPServer):
    def __init__(self, path: str, tag: str) -> None:
        super().__init__(("127.0.0.1", 0), StubHandler)
        self.responses = [tool_call_chunks(path, f"call_{tag}"), text_chunks(tag)]
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
        require(bool(self.server.responses), "stub provider exhausted responses")
        chunks = self.server.responses.pop(0)
        payload = "".join(f"data: {json.dumps(chunk, separators=(',', ':'))}\n\n" for chunk in chunks) + "data: [DONE]\n\n"
        encoded = payload.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(encoded)
        self.wfile.flush()


def create_session(lbe: Path, *, database: Path, workspace: Path, env: dict[str, str], cwd: Path) -> None:
    payload = json_stdout(run([
        str(lbe), "session", "create", "--database", str(database), "--workspace", str(workspace),
        "--project-workspace-id", "r7-obs8-project", "--session-id", "r7-obs8-session", "--mode", "coding",
        "--permission", "write_allowed", "--runtime-policy", "development", "--provider", "openai-compatible",
        "--model", MODEL, "--profile", "r7-obs8-profile", "--permission-policy", "r7-obs8-permissions",
        "--evidence-policy", "r7-obs8-evidence",
    ], cwd=cwd, env=env), "create coding session")
    session = payload.get("session") or {}
    require(session.get("mode") == "coding", "coding session mode mismatch")


def run_path_attack(lbe: Path, *, database: Path, workspace: Path, env: dict[str, str], cwd: Path, provider_path: Path, target_path: str, tag: str) -> dict[str, Any]:
    server = StubServer(target_path, tag)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        provider_path.write_text(json.dumps({"endpoint": f"http://127.0.0.1:{server.server_port}/v1/chat/completions", "model": MODEL, "timeout_seconds": 15, "api_key": "R7_OBS8_SECRET"}), encoding="utf-8")
        payload = json_stdout(run([
            str(lbe), "code", "--database", str(database), "--session-id", "r7-obs8-session",
            "--task-id", f"r7-obs8-{tag}-task", "--provider-config", str(provider_path),
            "--problem", f"Create {target_path}", "--request-id", f"r7-obs8-{tag}-request",
        ], cwd=cwd, env=env), f"installed code {tag}")
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=5)
    require(len(server.requests) == 2, f"{tag} expected two provider requests, got {len(server.requests)}")
    response = payload.get("response") or {}
    deterministic = response.get("deterministic_result") or {}
    receipts = deterministic.get("governed_tool_receipts") or []
    require(len(receipts) == 1, f"{tag} expected one governed receipt: {receipts}")
    receipt = receipts[0]
    require(receipt.get("tool_id") == TOOL, f"{tag} receipt wrong tool")
    require(receipt.get("status") == "FAILED", f"{tag} path rejection status={receipt.get('status')}")
    require(receipt.get("error_code") == "TOOL_EXECUTION_FAILED", f"{tag} unexpected error={receipt.get('error_code')}")
    require(response.get("read_only") is True, f"{tag} response must remain read_only")
    require(receipt.get("status") != "EXECUTED", f"{tag} mutation unexpectedly executed")
    return receipt


def direct_authority_probe() -> dict[str, Any]:
    from lbe_guard_inspector.runtime.mode_controller import ModeRequest, resolve_mode
    from lbe_guard_inspector.runtime.tool_orchestration import (
        GovernedToolOrchestrator, ToolExecutionContext, ToolExecutionResult, ToolRegistry,
        ToolRequest, ToolSpec, ToolAccessClass, ToolNetworkBehavior, ToolRiskClass,
    )

    decision = resolve_mode(ModeRequest(intent="fix_issue", permission="write_allowed", runtime_policy="development", workspace_root="."))
    require(decision.mode == "coding", "direct R6E discriminator did not resolve coding")
    registry = ToolRegistry()
    calls = {"count": 0}
    spec = ToolSpec(tool_id="obs8.mutate", capability="test_candidate", required_arguments=("value",), access_class=ToolAccessClass.WRITE, network_behavior=ToolNetworkBehavior.NONE, risk_class=ToolRiskClass.MEDIUM)
    def handler(request: ToolRequest) -> ToolExecutionResult:
        calls["count"] += 1
        return ToolExecutionResult(output={"unexpected": True})
    registry.register(spec, handler)
    orchestrator = GovernedToolOrchestrator(registry=registry)
    root = Path.cwd().resolve()

    deny = orchestrator.invoke(ToolRequest(operation_id="obs8-deny", tool_id="obs8.mutate", arguments={"value": "x"}, context=ToolExecutionContext(mode_decision=decision, workspace_id="obs8", workspace_root=root, configured_root_id="obs8", explicitly_forbidden=True)))
    require(deny.status.value == "DENIED", f"explicit forbidden receipt={deny.status.value}")
    require(deny.authorization is not None and deny.authorization.verdict.value == "DENY", "explicit forbidden authorization was not DENY")
    require(deny.error_code == "AUTHORIZATION_DENIED", f"explicit forbidden error={deny.error_code}")
    require(calls["count"] == 0, "DENIED request invoked handler")

    escalate = orchestrator.invoke(ToolRequest(operation_id="obs8-escalate", tool_id="obs8.mutate", arguments={"value": "x"}, context=ToolExecutionContext(mode_decision=decision, workspace_id="obs8", workspace_root=root, configured_root_id="obs8", within_workspace_scope=False)))
    require(escalate.status.value == "ESCALATED", f"out-of-scope receipt={escalate.status.value}")
    require(escalate.authorization is not None and escalate.authorization.verdict.value == "ESCALATE", "out-of-scope authorization was not ESCALATE")
    require(escalate.error_code == "AUTHORIZATION_REQUIRED", f"out-of-scope error={escalate.error_code}")
    require(calls["count"] == 0, "ESCALATED request invoked handler")
    return {"deny": deny, "escalate": escalate, "handler_calls": calls["count"]}


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--installed-root", required=True); args = parser.parse_args()
    installed_root = Path(args.installed_root).expanduser().resolve()
    venv = installed_root / "venv"; lbe = venv / "Scripts" / "lbe.exe"; python_exe = venv / "Scripts" / "python.exe"
    require(lbe.is_file(), f"installed lbe missing: {lbe}"); require(python_exe.is_file(), f"installed Python missing: {python_exe}")

    probe = installed_root / "obs8"
    if probe.exists(): shutil.rmtree(probe)
    workspace = probe / "workspace"; state_dir = probe / "state"; workspace.mkdir(parents=True); state_dir.mkdir(parents=True)
    baseline = workspace / BASELINE_REL; baseline.write_text(BASELINE_TEXT, encoding="utf-8", newline="\n")
    git(workspace, "init", "-q"); git(workspace, "config", "user.email", "r7@example.invalid"); git(workspace, "config", "user.name", "R7 Probe"); git(workspace, "add", BASELINE_REL); git(workspace, "commit", "-q", "-m", "R7 observable 8 baseline")

    database = probe / "memory.sqlite"; config_path = probe / "config.json"; governance_path = probe / "governance.json"; provider_path = probe / "provider.json"
    config_path.write_text(json.dumps({"knowledge_roots": [{"name": "r7-obs8-project", "path": str(workspace)}]}), encoding="utf-8")
    governance_path.write_text(json.dumps({"allowed_read_paths": ["."], "allowed_write_paths": ["."], "forbidden_globs": ["**/.git/**", "**/.env", "**/.env.*", "**/credentials*", "**/secrets*"], "required_files": [], "allowed_commands": [], "required_validation_commands": [], "max_changed_files": 1, "max_patch_bytes": 4096, "require_clean_base_hash": True, "store_only_verified_repairs": True}), encoding="utf-8")
    env = dict(os.environ); env.pop("PYTHONPATH", None); env["PATH"] = str(venv / "Scripts") + os.pathsep + env.get("PATH", ""); env["LBE_GUARD_INSPECTOR_CONFIG_PATH"] = str(config_path); env["LBE_GUARD_INSPECTOR_GOVERNANCE_PATH"] = str(governance_path); env["LBE_GUARD_INSPECTOR_STATE_DIR"] = str(state_dir)

    identity = run([str(python_exe), "-I", "-c", "import lbe_guard_inspector; print(lbe_guard_inspector.__file__)"], cwd=installed_root, env=env)
    require(identity.returncode == 0, f"isolated installed import failed: {identity.stderr.strip()}"); package_file = identity.stdout.strip(); require("site-packages" in package_file.lower(), f"not installed package: {package_file}"); require("Agents-Memory-Tool-v6-integration".lower() not in package_file.lower(), "source checkout import leakage")
    print("R7_OBS8_PACKAGE_FILE=" + package_file)

    create_session(lbe, database=database, workspace=workspace, env=env, cwd=probe)
    baseline_hash = sha256_file(baseline); baseline_status = git(workspace, "status", "--porcelain"); require(baseline_status == "", f"baseline dirty: {baseline_status!r}")

    forbidden_receipt = run_path_attack(lbe, database=database, workspace=workspace, env=env, cwd=probe, provider_path=provider_path, target_path=FORBIDDEN_REL, tag="forbidden")
    require(not (workspace / FORBIDDEN_REL).exists(), "forbidden .env was created")
    require(sha256_file(baseline) == baseline_hash and git(workspace, "status", "--porcelain") == baseline_status, "forbidden attempt changed workspace")
    require("forbidden" in str(forbidden_receipt.get("error_message") or "").lower(), "forbidden attempt did not expose governance rejection")
    print("R7_OBS8_FORBIDDEN_PATH_FAIL_CLOSED=PASS")

    outside = probe / "r7-obs8-outside.txt"; require(not outside.exists(), "outside sentinel already exists")
    escape_receipt = run_path_attack(lbe, database=database, workspace=workspace, env=env, cwd=probe, provider_path=provider_path, target_path=ESCAPE_REL, tag="escape")
    require(not outside.exists(), "workspace escape created outside file")
    require(sha256_file(baseline) == baseline_hash and git(workspace, "status", "--porcelain") == baseline_status, "escape attempt changed workspace")
    require("stay within" in str(escape_receipt.get("error_message") or "").lower() or "escape" in str(escape_receipt.get("error_message") or "").lower(), "escape attempt did not expose bounded path rejection")
    print("R7_OBS8_OUT_OF_WORKSPACE_PATH_FAIL_CLOSED=PASS")

    authority = direct_authority_probe()
    require(authority["handler_calls"] == 0, "rejected authority invoked handler")
    print("R7_OBS8_R6C_EXPLICIT_FORBIDDEN_DENY=PASS")
    print("R7_OBS8_R6C_OUT_OF_SCOPE_ESCALATE=PASS")
    print("R7_OBS8_REJECTED_AUTHORITY_HANDLER_NOT_INVOKED=PASS")

    require(sha256_file(baseline) == baseline_hash, "final baseline bytes changed"); require(git(workspace, "status", "--porcelain") == baseline_status, "final Git state changed")
    print("R7_OBS8_NO_REJECTED_MUTATION_EXECUTED=PASS")
    print("R7_OBS8_WORKSPACE_UNCHANGED=PASS")
    print("R7_OBS8_FAIL_CLOSED_AUTHORITY_BOUNDARIES=PASS")
    print("R7_OBSERVABLE_8=PASS")
    return 0


if __name__ == "__main__":
    try: raise SystemExit(main())
    except Exception as exc:
        print(f"R7_OBS8_FAIL={type(exc).__name__}:{exc}", file=sys.stderr)
        raise
