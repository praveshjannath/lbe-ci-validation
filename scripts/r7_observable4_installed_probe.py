from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


INVARIANT_FIELDS = (
    "session_id",
    "project_workspace_id",
    "canonical_workspace_root",
    "mode",
    "permission",
    "runtime_policy",
    "active_profile_id",
    "permission_policy_id",
    "evidence_policy_id",
)


def run_json(command: list[str], *, cwd: Path, env: dict[str, str]) -> dict:
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
        print("R7_OBS4_COMMAND_FAILED=" + " ".join(command), file=sys.stderr)
        print("R7_OBS4_STDOUT=" + completed.stdout, file=sys.stderr)
        print("R7_OBS4_STDERR=" + completed.stderr, file=sys.stderr)
        raise SystemExit(completed.returncode or 1)
    raw = completed.stdout.strip()
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        print("R7_OBS4_NON_JSON_OUTPUT=" + raw, file=sys.stderr)
        raise SystemExit(f"invalid JSON from installed command: {exc}")
    if not isinstance(value, dict):
        raise SystemExit("installed command did not return a JSON object")
    return value


def require_session(payload: dict) -> dict:
    session = payload.get("session")
    if not isinstance(session, dict):
        raise SystemExit("session inspect payload does not contain a session object")
    return session


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--installed-root", required=True)
    parser.add_argument("--database", default=None)
    args = parser.parse_args()

    root = Path(args.installed_root).resolve()
    lbe = root / "venv" / "Scripts" / "lbe.exe"
    python = root / "venv" / "Scripts" / "python.exe"
    database = Path(args.database).resolve() if args.database else root / "obs3" / "memory.sqlite"
    if not lbe.is_file() or not python.is_file() or not database.is_file():
        raise SystemExit("R7_OBS4_INSTALLED_BASELINE_MISSING")

    env = dict(os.environ)
    env.pop("PYTHONPATH", None)

    package_check = subprocess.run(
        [str(python), "-I", "-c", "import lbe_guard_inspector; print(lbe_guard_inspector.__file__)"],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if package_check.returncode != 0:
        print(package_check.stderr, file=sys.stderr)
        raise SystemExit("R7_OBS4_ISOLATED_IMPORT_FAILED")
    package_file = package_check.stdout.strip()
    print(f"R7_OBS4_PACKAGE_FILE={package_file}")
    checkout = Path(r"C:\Agents-Memory-Tool-v6-integration").resolve()
    try:
        Path(package_file).resolve().relative_to(checkout)
    except ValueError:
        pass
    else:
        raise SystemExit("R7_OBS4_SOURCE_IMPORT_LEAKAGE")

    before_payload = run_json(
        [str(lbe), "session", "inspect", "--database", str(database), "--session-id", "r7-session-repair"],
        cwd=root,
        env=env,
    )
    before = require_session(before_payload)
    print(f"R7_OBS4_BEFORE_PROVIDER={before.get('provider_id')}")
    print(f"R7_OBS4_BEFORE_MODEL={before.get('provider_model')}")
    if before.get("provider_id") != "openai-compatible" or before.get("provider_model") != "r7-model-a":
        raise SystemExit("R7_OBS4_UNEXPECTED_BASELINE_PROVIDER_MODEL")

    switch = run_json(
        [
            str(lbe),
            "provider",
            "select",
            "--database",
            str(database),
            "--session-id",
            "r7-session-repair",
            "--provider",
            "openai-compatible",
            "--model",
            "r7-model-b",
        ],
        cwd=root,
        env=env,
    )
    unchanged = switch.get("policy_unchanged")
    if isinstance(unchanged, dict):
        for name, value in unchanged.items():
            print(f"R7_OBS4_SELECT_POLICY_{str(name).upper()}={bool(value)}")
            if value is not True:
                raise SystemExit(f"R7_OBS4_PROVIDER_SELECT_POLICY_DRIFT:{name}")

    after_payload = run_json(
        [str(lbe), "session", "inspect", "--database", str(database), "--session-id", "r7-session-repair"],
        cwd=root,
        env=env,
    )
    after = require_session(after_payload)
    for field in INVARIANT_FIELDS:
        equal = before.get(field) == after.get(field)
        print(f"R7_OBS4_INVARIANT_{field.upper()}={equal}")
        if not equal:
            raise SystemExit(f"R7_OBS4_INVARIANT_DRIFT_{field}")
    if after.get("provider_id") != "openai-compatible" or after.get("provider_model") != "r7-model-b":
        raise SystemExit("R7_OBS4_SWITCH_NOT_PERSISTED")

    fresh_payload = run_json(
        [str(lbe), "session", "inspect", "--database", str(database), "--session-id", "r7-session-repair"],
        cwd=root,
        env=env,
    )
    fresh = require_session(fresh_payload)
    for field in INVARIANT_FIELDS:
        if fresh.get(field) != before.get(field):
            raise SystemExit(f"R7_OBS4_FRESH_INVARIANT_DRIFT_{field}")
    if fresh.get("provider_id") != "openai-compatible" or fresh.get("provider_model") != "r7-model-b":
        raise SystemExit("R7_OBS4_FRESH_PROVIDER_MODEL_NOT_PERSISTED")

    print(f"R7_OBS4_AFTER_PROVIDER={fresh.get('provider_id')}")
    print(f"R7_OBS4_AFTER_MODEL={fresh.get('provider_model')}")
    print("R7_OBS4_PROVIDER_MODEL_SWITCH=PASS")
    print("R7_OBS4_AUTHORITY_INVARIANTS=PASS")
    print("R7_OBS4_FRESH_PROCESS_READBACK=PASS")
    print("R7_OBSERVABLE_4=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
