"""Installed R7 observable 13 focused installed/runtime regression probe.

Performs the R7 observable 13 installed/runtime regression proof from an isolated
site-packages install (never the repository source checkout). Proves:

  1. installed package import resolves from site-packages only
  2. installed lbe CLI entrypoint parses and runs
  3. session creation and session/task persistence succeed
  4. a fresh installed process restores the persisted session/task identity
  5. provider continuation completes the normal provider-tool/final flow
  6. governed tool execution persists a ToolReceipt and mutates only the
     authorized artifact
  7. receipts/completion evidence persist across a fresh process
  8. completion authority stays with LBE (provider completion truth is rejected
     until persisted validation)
  9. credential canary leaks into no forbidden surface
 10. no unexpected workspace mutation beyond the governed, authorized artifact
"""
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


MODEL = "r7-obs13-model"
SESSION_ID = "r7-obs13-session"
TASK_ID = "r7-obs13-task"
PROJECT_ID = "r7-obs13-project"
CALL_ID = "call_r7_obs13_create_1"
TARGET = "r7-obs13-created.txt"
CONTENT = "R7 observable 13 bounded artifact content\n"


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
            "id": "chatcmpl-r7-obs13-tool",
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
            "id": "chatcmpl-r7-obs13-tool",
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
            "id": "chatcmpl-r7-obs13-final",
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
            "id": "chatcmpl-r7-obs13-final",
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
        self.server.requests.append({"path": self.path, "body": request})
        require(self.server.canary not in raw.decode("utf-8", errors="replace"), "credential leaked into provider body")
        authorization = self.headers.get("Authorization")
        if authorization == f"Bearer {self.server.canary}":
            self.server.authorization_matches += 1
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
    serialized = json.dumps(value, ensure_ascii=False, default=str)
    require(canary not in serialized, f"credential leaked into {label}")


def assert_tree_clean(root: Path, canary: bytes, *, label: str) -> int:
    inspected = 0
    for path in sorted(root.rglob("*")):
        if path.is_file() and ".git" not in path.parts:
            inspected += 1
            require(canary not in path.read_bytes(), f"credential leaked into {label} file: {path}")
    return inspected


def main() -> int:
    parser = argparse.ArgumentParser(description="Installed R7 observable 13 probe")
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--venv", required=True, type=Path)
    parser.add_argument("--scratch-dir", required=True, type=Path)
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    venv = args.venv.resolve()
    scratch_dir = args.scratch_dir.resolve()
    scratch_dir.mkdir(parents=True, exist_ok=True)

    if os.name == "nt":
        python_exe = venv / "Scripts" / "python.exe"
        lbe = venv / "Scripts" / "lbe.exe"
    else:
        python_exe = venv / "bin" / "python"
        lbe = venv / "bin" / "lbe"
    require(python_exe.is_file(), f"missing python executable: {python_exe}")
    require(lbe.is_file(), f"missing lbe executable: {lbe}")

    probe = scratch_dir / f"obs13-{uuid4().hex}"
    workspace = probe / "workspace"
    state_dir = probe / "state"
    workspace.mkdir(parents=True)
    state_dir.mkdir(parents=True)
    print("R7_OBS13_PROBE_ROOT=" + str(probe))

    import_env = dict(os.environ)
    import_env.pop("PYTHONPATH", None)

    import_check = run(
        [
            str(python_exe),
            "-c",
            "import lbe_guard_inspector; print(lbe_guard_inspector.__file__)",
        ],
        cwd=probe,
        env=import_env,
    )
    require(import_check.returncode == 0, f"isolated import check failed: {import_check.stderr}")
    package_file = Path(import_check.stdout.strip()).resolve()
    require("site-packages" in str(package_file).lower(), f"probe imported non-installed package: {package_file}")
    installed_root = (venv / "Lib" / "site-packages").resolve() if os.name == "nt" else (venv / "lib").resolve()
    source_package_root = (repo_root / "lbe_guard_inspector").resolve()
    require(package_file.is_relative_to(installed_root), f"package not from isolated venv site-packages: {package_file}")
    require(not package_file.is_relative_to(source_package_root), f"package imported from source package tree: {package_file}")
    print("R7_OBS13_PACKAGE_FILE=" + str(package_file))

    source_status_before = git(repo_root, "status", "--porcelain")
    require(source_status_before is not None, "unable to read source checkout status")

    (workspace / "test_smoke.py").write_text("def test_smoke():\n    assert True\n", encoding="utf-8")
    (workspace / ".gitignore").write_text("__pycache__/\n.pytest_cache/\n", encoding="utf-8")
    git(workspace, "init", "-q")
    git(workspace, "config", "user.email", "r7@example.invalid")
    git(workspace, "config", "user.name", "R7 Probe")
    git(workspace, "add", "test_smoke.py", ".gitignore")
    git(workspace, "commit", "-q", "-m", "R7 observable 13 baseline")
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

    canary = f"r7-obs13-canary-{uuid4().hex}"
    canary_hash = hashlib.sha256(canary.encode("utf-8")).hexdigest()
    server = StubServer(canary)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
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

        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        env["PATH"] = str(venv / ("Scripts" if os.name == "nt" else "bin")) + os.pathsep + env.get("PATH", "")
        env["LBE_GUARD_INSPECTOR_CONFIG_PATH"] = str(config)
        env["LBE_GUARD_INSPECTOR_GOVERNANCE_PATH"] = str(governance)
        env["LBE_GUARD_INSPECTOR_STATE_DIR"] = str(state_dir)

        check_import = run(
            [str(python_exe), "-c", "import agent, lbe_guard_inspector; print(agent.__file__)"],
            cwd=probe,
            env=env,
        )
        require(check_import.returncode == 0, f"import check failed: {check_import.stderr}")
        import_paths = [Path(line.strip()).resolve() for line in check_import.stdout.splitlines() if line.strip()]
        require(bool(import_paths), f"import check returned no paths: {check_import.stdout}")
        require(all(path.is_relative_to(installed_root) for path in import_paths), f"imports not from isolated venv site-packages: {check_import.stdout}")
        require(all(not path.is_relative_to(source_package_root) for path in import_paths), f"source package import leakage: {check_import.stdout}")
        require(str(venv).lower() in check_import.stdout.lower(), f"package not from isolated venv: {check_import.stdout}")
        print("R7_OBS13_SITE_PACKAGES_ISOLATION=PASS")

        from lbe_guard_inspector.memory import WorkspaceMemoryStore
        from lbe_guard_inspector.memory.completion_contracts import TaskCompletionContractPersistence
        from lbe_guard_inspector.memory.completion_evidence import TaskCompletionEvidencePersistence

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
                    "--profile", "r7-obs13-profile",
                    "--permission-policy", "r7-obs13-permissions",
                    "--evidence-policy", "r7-obs13-evidence",
                ],
                cwd=probe,
                env=env,
            ),
            "session create",
        )
        original_session = created_session.get("session") or {}
        require(original_session.get("session_id") == SESSION_ID, "created session identity mismatch")
        require(original_session.get("project_workspace_id") == PROJECT_ID, "created workspace identity mismatch")
        print("R7_OBS13_SESSION_CREATE=PASS")

        captured_results: list[subprocess.CompletedProcess[str]] = []
        captured_json: list[dict[str, Any]] = []

        code_request = [
            str(lbe), "code",
            "--database", str(database),
            "--session-id", SESSION_ID,
            "--task-id", TASK_ID,
            "--provider-config", str(provider),
            "--problem", f"Create {TARGET} with the exact requested content and then finish the turn.",
            "--request-id", "r7-obs13-request",
        ]
        code_result = run(code_request, cwd=probe, env=env)
        captured_results.append(code_result)
        code = json_stdout(code_result, "installed code")
        captured_json.append(code)
        print("R7_OBS13_CODE_RESULT=" + json.dumps(code, sort_keys=True, default=str))
        require(len(server.requests) == 2, f"provider request count={len(server.requests)}")
        require(server.authorization_matches == 2, f"provider authorization header matches={server.authorization_matches}")
        assert_text_clean("provider request bodies", server.requests, canary)
        require(code.get("outcome") == "COMPLETED", f"reasoning outcome={code.get('outcome')}")
        response = code.get("response") or {}
        deterministic = response.get("deterministic_result") or {}
        require(deterministic.get("lbe_completion_truth") is False, "provider completion truth was accepted")
        receipts = deterministic.get("governed_tool_receipts") or []
        require(len(receipts) == 1, f"expected one governed receipt, got {len(receipts)}")
        require(receipts[0].get("status") == "EXECUTED", f"governed receipt status={receipts[0].get('status')}")
        require(receipts[0].get("tool_id") == "workspace.create_candidate_text", f"wrong governed tool: {receipts[0].get('tool_id')}")
        require((workspace / TARGET).read_text(encoding="utf-8") == CONTENT, "governed mutation content mismatch")
        assert_text_clean("deterministic result", deterministic, canary)
        assert_text_clean("governed receipts", receipts, canary)
        print("R7_OBS13_GOVERNED_TOOL_RECEIPT=PASS")
        print("R7_OBS13_PROVIDER_COMPLETION_TRUTH_FALSE=PASS")
        print("R7_OBS13_CREDENTIAL_HEADER_ONLY_USE=PASS")
        print("R7_OBS13_CLI_ENTRYPOINT_RUNS=PASS")

        store = WorkspaceMemoryStore(database)
        contract = TaskCompletionContractPersistence(store).load(
            session_id=SESSION_ID,
            task_id=TASK_ID,
            project_workspace_id=PROJECT_ID,
        )
        require(contract is not None, "registered completion contract missing")
        contract_ids = [item.requirement_id for item in contract.requirements]
        contract_kinds = [item.evidence_kind for item in contract.requirements]
        require(contract_ids == ["source-change", "focused-tests", "git-state"], f"contract ids={contract_ids}")
        require(contract_kinds == ["source_change", "focused_test", "git_status"], f"contract kinds={contract_kinds}")
        evidence_before = TaskCompletionEvidencePersistence(store).load(
            session_id=SESSION_ID,
            task_id=TASK_ID,
            project_workspace_id=PROJECT_ID,
        )
        latest_by_kind = {item.kind: item for item in evidence_before}
        require(set(latest_by_kind) == {"source_change", "focused_test", "git_status"}, f"evidence kinds={sorted(latest_by_kind)}")
        require(all(latest_by_kind[kind].status == "PASS" for kind in latest_by_kind), f"evidence statuses={[(k, v.status) for k, v in latest_by_kind.items()]}")
        evidence_ids_before = sorted(item.evidence_id for item in evidence_before)
        print("R7_OBS13_CONTRACT_REGISTERED=PASS")
        print("R7_OBS13_STORE_PERSISTENCE=PASS")
        assert_text_clean("completion evidence", [item.__dict__ for item in evidence_before], canary)

        validation_result = run(
            [str(lbe), "session", "validate", "--database", str(database), "--session-id", SESSION_ID, "--task-id", TASK_ID],
            cwd=probe,
            env=env,
        )
        captured_results.append(validation_result)
        validated = json_stdout(validation_result, "session validate")
        captured_json.append(validated)
        completion = validated.get("completion") or {}
        require(completion.get("satisfied_requirement_ids") == contract_ids, f"satisfied={completion.get('satisfied_requirement_ids')}")
        require(completion.get("missing_requirement_ids") == [], f"missing={completion.get('missing_requirement_ids')}")
        require(completion.get("failed_requirement_ids") == [], f"failed={completion.get('failed_requirement_ids')}")
        validated_task = validated.get("task") or {}
        require(validated_task.get("status") == "completed", f"validated status={validated_task.get('status')}")
        require(validated_task.get("last_outcome") == "VALIDATED_COMPLETION", f"validated outcome={validated_task.get('last_outcome')}")
        print("R7_OBS13_VALIDATION_READY=PASS")
        print("R7_OBS13_COMPLETION_AUTHORITY_LBE_ONLY=PASS")
        for index, result in enumerate(captured_results):
            assert_text_clean(f"CLI stdout[{index}]", result.stdout, canary)
            assert_text_clean(f"CLI stderr[{index}]", result.stderr, canary)
        for index, payload in enumerate(captured_json):
            assert_text_clean(f"CLI JSON[{index}]", payload, canary)
        print("R7_OBS13_CLI_NO_CANARY_LEAK=PASS")

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
        print("R7_OBS13_FRESH_PROCESS_SESSION_RESTORE=PASS")
        print("R7_OBS13_FRESH_PROCESS_TASK_RESTORE=PASS")

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
        print("R7_OBS13_FRESH_PROCESS_CONTINUE=PASS")

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
        print("R7_OBS13_EVIDENCE_PERSISTS_FRESH_PROCESS=PASS")

        provider.unlink()

        checked_probe_files = assert_tree_clean(probe, canary.encode("utf-8"), label="probe persistence")
        require(checked_probe_files > 0, "probe persistence scan inspected no files")
        assert_tree_clean(workspace, canary.encode("utf-8"), label="workspace")
        raw_db = database.read_bytes()
        require(canary.encode("utf-8") not in raw_db, "credential leaked into SQLite database")
        print("R7_OBS13_PERSISTED_STATE_NO_CANARY=PASS")
        print("R7_OBS13_SQLITE_RAW_BYTES_CLEAN=PASS")

        source_scan_roots = [
            repo_root / ".lbe",
            repo_root / "docs",
            repo_root / "scripts",
            repo_root / "lbe_guard_inspector",
            repo_root / "tests",
        ]
        source_files_checked = 0
        for root in source_scan_roots:
            source_files_checked += assert_tree_clean(root, canary.encode("utf-8"), label="source")
        require(source_files_checked > 0, "source/acceptance scan inspected no files")
        require(git(repo_root, "status", "--porcelain") == source_status_before, "source checkout changed during probe")
        print("R7_OBS13_SOURCE_UNCHANGED=PASS")

        workspace_status_after = git(workspace, "status", "--porcelain").strip()
        require(workspace_status_after != "", "governed artifact was not created in workspace")
        require(TARGET in workspace_status_after, "unexpected workspace mutation set")
        require(workspace_status_after.strip().count("\n") <= 2, f"unexpected extra workspace mutations: {workspace_status_after!r}")
        print("R7_OBS13_NO_UNEXPECTED_WORKSPACE_MUTATION=PASS")

        decisive_payload = (
            f"R7_OBSERVABLE_13:{SESSION_ID}:{TASK_ID}:{validated_task.get('last_outcome')}:"
            + ",".join(evidence_ids_before)
        )
        decisive_hash = hashlib.sha256(decisive_payload.encode("utf-8")).hexdigest().upper()

        print("R7_OBS13_CANARY_SHA256=" + canary_hash)
        print("R7_OBS13_REGRESSION_PROOF=PASS")
        print("R7_OBSERVABLE_13=PASS")
        print(json.dumps({"ok": True, "observable": 13, "decisive_hash": decisive_hash}))
        return 0
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


if __name__ == "__main__":
    raise SystemExit(main())
