from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


SESSION_ID = "r7-session-repair"
TASK_ID = "r7-task-create"

SESSION_FIELDS = (
    "session_id",
    "project_workspace_id",
    "canonical_workspace_root",
    "mode",
    "permission",
    "runtime_policy",
    "provider_id",
    "provider_model",
    "active_profile_id",
    "permission_policy_id",
    "evidence_policy_id",
)


def fail(message: str) -> None:
    raise RuntimeError(message)


def run_json(command: list[str], *, cwd: Path, env: dict[str, str], label: str) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        fail(
            f"{label} failed exit={completed.returncode} "
            f"stdout={completed.stdout!r} stderr={completed.stderr!r}"
        )
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        fail(f"{label} did not return JSON: {exc}: {completed.stdout!r}")
    if not isinstance(value, dict):
        fail(f"{label} returned non-object JSON")
    return value


def read_state(lbe: Path, database: Path, *, cwd: Path, env: dict[str, str]) -> tuple[dict[str, Any], dict[str, Any]]:
    inspect = run_json(
        [str(lbe), "session", "inspect", "--database", str(database), "--session-id", SESSION_ID],
        cwd=cwd,
        env=env,
        label="session inspect",
    )
    status = run_json(
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
        cwd=cwd,
        env=env,
        label="session status",
    )
    session = inspect.get("session") or {}
    task = status.get("task") or {}
    if not isinstance(session, dict) or not isinstance(task, dict):
        fail("installed commands returned invalid session/task payloads")
    return session, task


def child_main(args: argparse.Namespace) -> int:
    root = Path(args.installed_root).resolve()
    lbe = root / "venv" / "Scripts" / "lbe.exe"
    database = root / "obs3" / "memory.sqlite"
    if not lbe.is_file():
        fail(f"installed lbe missing: {lbe}")
    if not database.is_file():
        fail(f"R7 database missing: {database}")

    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    session, task = read_state(lbe, database, cwd=root, env=env)
    print(json.dumps({"session": session, "task": task}, sort_keys=True))
    return 0


def parent_main(args: argparse.Namespace) -> int:
    root = Path(args.installed_root).resolve()
    py = root / "venv" / "Scripts" / "python.exe"
    lbe = root / "venv" / "Scripts" / "lbe.exe"
    database = root / "obs3" / "memory.sqlite"
    script = Path(__file__).resolve()
    if not py.is_file() or not lbe.is_file() or not database.is_file():
        fail("installed observable-5 baseline is missing")

    env = dict(os.environ)
    env.pop("PYTHONPATH", None)

    package = subprocess.run(
        [str(py), "-I", "-c", "import lbe_guard_inspector; print(lbe_guard_inspector.__file__)"],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if package.returncode != 0:
        fail(f"isolated installed import failed: {package.stderr!r}")
    package_file = package.stdout.strip()
    source_root = str(Path.cwd().resolve())
    if package_file.lower().startswith(source_root.lower()):
        fail("source-tree import leakage")
    print("R7_OBS5_PACKAGE_FILE=" + package_file)

    child_command = [str(py), "-I", str(script), "--installed-root", str(root), "--child"]

    first = subprocess.run(
        child_command,
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if first.returncode != 0:
        fail(f"first installed process failed: {first.stdout!r} {first.stderr!r}")
    first_pid = first.pid if hasattr(first, "pid") else None
    first_payload = json.loads(first.stdout)

    # subprocess.run() returns only after process A has exited. Process B is then
    # launched independently against the same installed executable/database.
    second = subprocess.run(
        child_command,
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if second.returncode != 0:
        fail(f"second installed process failed: {second.stdout!r} {second.stderr!r}")
    second_payload = json.loads(second.stdout)

    first_session = first_payload.get("session") or {}
    second_session = second_payload.get("session") or {}
    first_task = first_payload.get("task") or {}
    second_task = second_payload.get("task") or {}

    for field in SESSION_FIELDS:
        a = first_session.get(field)
        b = second_session.get(field)
        equal = a == b
        print(f"R7_OBS5_SESSION_INVARIANT_{field.upper()}={equal}")
        if not equal:
            fail(f"session field drifted across fresh process boundary: {field}: {a!r} != {b!r}")

    if second_session.get("session_id") != SESSION_ID:
        fail(f"unexpected resumed session_id={second_session.get('session_id')!r}")
    if second_session.get("provider_id") != "openai-compatible":
        fail(f"unexpected provider_id={second_session.get('provider_id')!r}")
    if second_session.get("provider_model") != "r7-model-b":
        fail(f"observable 4 model selection did not persist: {second_session.get('provider_model')!r}")

    for field in ("task_id", "status", "last_outcome"):
        a = first_task.get(field)
        b = second_task.get(field)
        equal = a == b
        print(f"R7_OBS5_TASK_INVARIANT_{field.upper()}={equal}")
        if not equal:
            fail(f"task field drifted across fresh process boundary: {field}: {a!r} != {b!r}")

    if second_task.get("task_id") != TASK_ID:
        fail(f"unexpected resumed task_id={second_task.get('task_id')!r}")
    if second_task.get("status") != "running":
        fail(f"unexpected resumed task status={second_task.get('status')!r}")
    if second_task.get("last_outcome") != "AWAITING_VALIDATION":
        fail(f"unexpected resumed task last_outcome={second_task.get('last_outcome')!r}")

    print("R7_OBS5_SESSION_ID=" + str(second_session.get("session_id")))
    print("R7_OBS5_PROVIDER=" + str(second_session.get("provider_id")))
    print("R7_OBS5_MODEL=" + str(second_session.get("provider_model")))
    print("R7_OBS5_TASK_ID=" + str(second_task.get("task_id")))
    print("R7_OBS5_TASK_STATUS=" + str(second_task.get("status")))
    print("R7_OBS5_TASK_LAST_OUTCOME=" + str(second_task.get("last_outcome")))
    print("R7_OBS5_PROCESS_A_EXITED_BEFORE_B=PASS")
    print("R7_OBS5_SESSION_RESUME=PASS")
    print("R7_OBS5_TASK_RESUME=PASS")
    print("R7_OBS5_AUTHORITY_INVARIANTS=PASS")
    print("R7_OBSERVABLE_5=PASS")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--installed-root", required=True)
    parser.add_argument("--child", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        return child_main(args) if args.child else parent_main(args)
    except Exception as exc:
        print(f"R7_OBS5_FAIL={type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
