"""Installed R7 observable 6 acceptance probe.

Proves that a fresh installed invocation observes a bounded workspace change made
outside LBE between invocations, instead of treating pre-change evidence as
current truth. This is acceptance infrastructure only; it invokes the installed
`lbe` executable and does not import the source checkout as the runtime under test.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Iterable


SESSION_ID = "r7-session-repair"
TASK_ID = "r7-task-create"
TARGET_REL = "test_smoke.py"
BASELINE_TEXT = "def test_smoke():\n    assert True\n"
CHANGED_TEXT = (
    "def test_smoke():\n"
    "    marker = 'R7_OBS6_EXTERNAL_CHANGE_V1'\n"
    "    assert marker == 'R7_OBS6_EXTERNAL_CHANGE_V1'\n"
)
MARKER = "R7_OBS6_EXTERNAL_CHANGE_V1"


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
        fail(f"{label} exit={result.returncode}; stderr={result.stderr.strip()!r}; stdout={result.stdout.strip()!r}")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        fail(f"{label} did not return JSON: {exc}; stdout={result.stdout!r}")
    require(isinstance(payload, dict), f"{label} JSON root is not an object")
    require(payload.get("ok") is True, f"{label} ok is not true: {payload}")
    return payload


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def walk_values(value: Any) -> Iterable[Any]:
    yield value
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from walk_values(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_values(child)


def serialized(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False)


def evidence_mentions(payload: dict[str, Any], *, required_strings: tuple[str, ...]) -> bool:
    text = serialized(payload)
    return all(item in text for item in required_strings)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--installed-root", required=True)
    args = parser.parse_args()

    installed_root = Path(args.installed_root).resolve()
    venv = installed_root / "venv"
    lbe = venv / "Scripts" / "lbe.exe"
    python = venv / "Scripts" / "python.exe"
    probe = installed_root / "obs3"
    database = probe / "memory.sqlite"
    workspace = probe / "workspace"
    target = workspace / TARGET_REL
    config_path = probe / "config.json"
    governance_path = probe / "governance.json"
    state_dir = probe / "state"

    require(lbe.is_file(), f"installed lbe missing: {lbe}")
    require(python.is_file(), f"installed python missing: {python}")
    require(database.is_file(), f"persistent database missing: {database}")
    require(workspace.is_dir(), f"R7 workspace missing: {workspace}")
    require(config_path.is_file(), f"R7 config missing: {config_path}")
    require(governance_path.is_file(), f"R7 governance missing: {governance_path}")
    require(state_dir.is_dir(), f"R7 state directory missing: {state_dir}")

    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env["PATH"] = str(venv / "Scripts") + os.pathsep + env.get("PATH", "")
    env["LBE_GUARD_INSPECTOR_CONFIG_PATH"] = str(config_path)
    env["LBE_GUARD_INSPECTOR_GOVERNANCE_PATH"] = str(governance_path)
    env["LBE_GUARD_INSPECTOR_STATE_DIR"] = str(state_dir)

    identity = run(
        [str(python), "-I", "-c", "import lbe_guard_inspector; print(lbe_guard_inspector.__file__)"],
        cwd=installed_root,
        env=env,
    )
    require(identity.returncode == 0, f"isolated installed import failed: {identity.stderr.strip()}")
    package_file = identity.stdout.strip()
    require("site-packages" in package_file.lower(), f"package is not from installed site-packages: {package_file}")
    require("Agents-Memory-Tool-v6-integration".lower() not in package_file.lower(), "source checkout import leakage")
    print("R7_OBS6_PACKAGE_FILE=" + package_file)

    target.write_text(BASELINE_TEXT, encoding="utf-8", newline="\n")
    baseline_bytes = target.read_bytes()
    baseline_hash = sha256_bytes(baseline_bytes)

    before_result = run(
        [
            str(lbe),
            "session",
            "evidence",
            "--database",
            str(database),
            "--session-id",
            SESSION_ID,
            "--task-id",
            TASK_ID,
            "--query",
            TARGET_REL,
            "--max-results",
            "10",
        ],
        cwd=installed_root,
        env=env,
    )
    before = json_stdout(before_result, "pre-change installed evidence")
    require(
        evidence_mentions(before, required_strings=(TARGET_REL, baseline_hash)),
        "pre-change LBE evidence does not identify target file and baseline hash",
    )
    require(MARKER not in serialized(before), "pre-change LBE evidence unexpectedly contains external marker")
    print("R7_OBS6_BEFORE_SHA256=" + baseline_hash)
    print("R7_OBS6_PROCESS_A_PRECHANGE_EVIDENCE=PASS")

    target.write_text(CHANGED_TEXT, encoding="utf-8", newline="\n")
    changed_bytes = target.read_bytes()
    changed_hash = sha256_bytes(changed_bytes)
    require(changed_hash != baseline_hash, "external change did not alter target hash")
    require(MARKER.encode("utf-8") in changed_bytes, "external marker missing from changed bytes")
    print("R7_OBS6_EXTERNAL_CHANGE_SHA256=" + changed_hash)
    print("R7_OBS6_EXTERNAL_CHANGE_APPLIED=PASS")

    continuation_result = run(
        [
            str(lbe),
            "session",
            "continue",
            "--database",
            str(database),
            "--session-id",
            SESSION_ID,
            "--task-id",
            TASK_ID,
        ],
        cwd=installed_root,
        env=env,
    )
    continuation = json_stdout(continuation_result, "fresh-process session continue")
    session = continuation.get("session") or {}
    require(session.get("session_id") == SESSION_ID, "fresh continuation session identity changed")
    require(session.get("provider_id") == "openai-compatible", "provider identity changed during external-change resume")
    require(session.get("provider_model") == "r7-model-b", "provider model changed during external-change resume")

    # Query the unique external content marker alone. Current-workspace retrieval
    # scores path and content matches independently and takes their max, so a
    # mixed filename+content two-term query cannot satisfy its two-term threshold.
    # The observable here is freshness, not mixed-field query semantics.
    after_result = run(
        [
            str(lbe),
            "session",
            "evidence",
            "--database",
            str(database),
            "--session-id",
            SESSION_ID,
            "--task-id",
            TASK_ID,
            "--query",
            MARKER,
            "--max-results",
            "10",
        ],
        cwd=installed_root,
        env=env,
    )
    after = json_stdout(after_result, "post-change installed evidence")
    after_text = serialized(after)
    require(TARGET_REL in after_text, "post-change evidence omitted target file")
    require(MARKER in after_text, "post-change evidence did not observe external marker")
    require(changed_hash in after_text, "post-change evidence did not observe changed SHA-256")
    require(changed_hash != baseline_hash, "hash discriminator collapsed")

    status_result = run(
        [
            str(lbe),
            "session",
            "status",
            "--database",
            str(database),
            "--session-id",
            SESSION_ID,
            "--task-id",
            TASK_ID,
        ],
        cwd=installed_root,
        env=env,
    )
    status = json_stdout(status_result, "post-change task status")
    task = status.get("task") or {}
    require(task.get("task_id") == TASK_ID, "task identity changed after external workspace change")
    require(task.get("status") == "running", f"task status changed unexpectedly: {task.get('status')}")
    require(task.get("last_outcome") == "AWAITING_VALIDATION", f"task last_outcome changed unexpectedly: {task.get('last_outcome')}")

    print("R7_OBS6_AFTER_SHA256=" + changed_hash)
    print("R7_OBS6_EXTERNAL_MARKER_OBSERVED=PASS")
    print("R7_OBS6_CURRENT_HASH_OBSERVED=PASS")
    print("R7_OBS6_FRESH_PROCESS_RESUME=PASS")
    print("R7_OBS6_TASK_AUTHORITY_PRESERVED=PASS")
    print("R7_OBS6_CURRENT_WORKSPACE_TRUTH_REVALIDATED=PASS")
    print("R7_OBSERVABLE_6=PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"R7_OBS6_FAIL={type(exc).__name__}:{exc}", file=sys.stderr)
        raise
