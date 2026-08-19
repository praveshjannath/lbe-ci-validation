from __future__ import annotations

import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_wheel_contains_only_runtime_modules_and_contracts(
    tmp_path: Path,
) -> None:
    wheel_dir = tmp_path / "wheel"
    wheel_dir.mkdir()
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--no-build-isolation",
            "--wheel-dir",
            str(wheel_dir),
            str(REPOSITORY_ROOT),
        ],
        check=True,
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    wheels = list(wheel_dir.glob("lbe_guard_inspector-*.whl"))
    assert len(wheels) == 1

    with zipfile.ZipFile(wheels[0]) as archive:
        names = set(archive.namelist())

    assert {
        "agent.py",
        "audit_controller.py",
        "server.py",
        "lbe_guard_inspector/callback_vertical_slice.py",
        "lbe_guard_inspector/memory/memory_schema.sql",
        "lbe_guard_inspector/module_registry_vertical_slice.py",
        "rules/cep_callback.py",
        "rules/module_registry.py",
        "schemas/evidence_package.schema.json",
        "schemas/guard_result.schema.json",
    } <= names
    assert not any(name.startswith("tests/") for name in names)
    assert not any(name.startswith("state/") for name in names)
    assert not any(name.startswith("docs/") for name in names)


def test_installed_wheel_runs_both_fixed_guard_slices(tmp_path: Path) -> None:
    wheel_dir = tmp_path / "wheel"
    target = tmp_path / "installed"
    runtime = tmp_path / "runtime"
    workspace = tmp_path / "workspace"
    callback_project = workspace / "callback-project"
    wheel_dir.mkdir()
    target.mkdir()
    callback_project.mkdir(parents=True)
    (callback_project / "panel.js").write_text(
        "cs.evalScript(payload, function () {});\n", encoding="utf-8"
    )
    registry = workspace / ".lbe" / "module-registry.json"
    registry.parent.mkdir()
    registry.write_text(
        json.dumps(
            {
                "declarations": [{"id": "app.launcher"}],
                "receipts": [
                    {
                        "type": "loaded",
                        "module_id": "app.launcher",
                        "instance_id": "app-1",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    config = runtime / "config.json"
    governance = runtime / "governance.json"
    runtime.mkdir()
    config.write_text(
        json.dumps(
            {
                "knowledge_roots": [{"name": "workspace", "path": str(workspace)}],
                "max_file_bytes": 1_000_000,
                "exclude_patterns": [],
            }
        ),
        encoding="utf-8",
    )
    governance.write_text(
        json.dumps({"allowed_read_paths": ["."], "forbidden_globs": ["*.secret"]}),
        encoding="utf-8",
    )
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--no-build-isolation",
            "--wheel-dir",
            str(wheel_dir),
            str(REPOSITORY_ROOT),
        ],
        check=True,
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    wheel = next(wheel_dir.glob("lbe_guard_inspector-*.whl"))
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-deps",
            "--target",
            str(target),
            str(wheel),
        ],
        check=True,
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    environment = dict(os.environ)
    environment.update(
        {
            "PYTHONPATH": str(target),
            "LBE_GUARD_INSPECTOR_CONFIG_PATH": str(config),
            "LBE_GUARD_INSPECTOR_GOVERNANCE_PATH": str(governance),
            "LBE_GUARD_INSPECTOR_STATE_DIR": str(runtime / "state"),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    program = """
import json
import sys
import server

callback = server.run_callback_inspection({"workspace_root": sys.argv[1]})
registry = server.run_module_registry_inspection({"workspace_root": sys.argv[2]})
assert callback["decision"]["guard_result"]["verdict"] == "PASS"
assert registry["decision"]["guard_result"]["verdict"] == "PASS"
assert callback["workspace_unchanged"] is True
assert registry["workspace_unchanged"] is True
print(json.dumps({"callback": "PASS", "module_registry": "PASS"}))
"""
    result = subprocess.run(
        [sys.executable, "-c", program, str(callback_project), str(workspace)],
        check=True,
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
    )
    assert json.loads(result.stdout) == {
        "callback": "PASS",
        "module_registry": "PASS",
    }

    audit = subprocess.run(
        [
            sys.executable,
            "-m",
            "audit_controller",
            "audit",
            "--workspace-root",
            str(workspace),
        ],
        check=True,
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
    )
    audit_payload = json.loads(audit.stdout.split("\nReport:", 1)[0])
    assert audit_payload["audit_status"] == "completed"
    assert audit_payload["project_profile"]["workspace_root"] == str(workspace.resolve())
