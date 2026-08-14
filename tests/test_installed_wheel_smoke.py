from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _run(command: list[str], *, cwd: Path, timeout: int = 180) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def test_installed_wheel_can_create_persistent_session(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    wheel_dir = tmp_path / "wheel"
    wheel_dir.mkdir()

    built = _run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--no-build-isolation",
            "--wheel-dir",
            str(wheel_dir),
            str(repo_root),
        ],
        cwd=repo_root,
    )
    assert built.returncode == 0, built.stdout + built.stderr

    wheels = tuple(wheel_dir.glob("lbe_guard_inspector-*.whl"))
    assert len(wheels) == 1

    venv_dir = tmp_path / "venv"
    created = _run(
        [sys.executable, "-m", "venv", "--system-site-packages", str(venv_dir)],
        cwd=repo_root,
    )
    assert created.returncode == 0, created.stdout + created.stderr

    python_exe = venv_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    lbe_exe = venv_dir / ("Scripts/lbe.exe" if os.name == "nt" else "bin/lbe")

    installed = _run(
        [str(python_exe), "-m", "pip", "install", "--force-reinstall", "--no-deps", str(wheels[0])],
        cwd=repo_root,
    )
    assert installed.returncode == 0, installed.stdout + installed.stderr

    for executable in (
        lbe_exe,
        venv_dir / ("Scripts/lbe-guard-inspector.exe" if os.name == "nt" else "bin/lbe-guard-inspector"),
        venv_dir / ("Scripts/lbe-guard-inspector-evidence.exe" if os.name == "nt" else "bin/lbe-guard-inspector-evidence"),
        venv_dir / ("Scripts/lbe-guard-audit.exe" if os.name == "nt" else "bin/lbe-guard-audit"),
    ):
        help_result = _run([str(executable), "--help"], cwd=repo_root)
        assert help_result.returncode == 0, help_result.stdout + help_result.stderr

    schema_probe = _run(
        [
            str(python_exe),
            "-c",
            "from importlib.resources import files; p=files('lbe_guard_inspector.memory').joinpath('memory_schema.sql'); assert p.is_file(); print(p.read_text(encoding='utf-8')[:20])",
        ],
        cwd=repo_root,
    )
    assert schema_probe.returncode == 0, schema_probe.stdout + schema_probe.stderr

    provider_config_probe = _run(
        [
            str(python_exe),
            "-c",
            "from lbe_guard_inspector.reasoning_config import load_provider_config; "
            "config = load_provider_config(r'" + str(repo_root / "reasoning-provider.example.json") + "'); "
            "assert config.api_key is None; print(config.model)",
        ],
        cwd=repo_root,
    )
    assert provider_config_probe.returncode == 0, provider_config_probe.stdout + provider_config_probe.stderr

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    database = tmp_path / "runtime.sqlite3"

    result = _run(
        [
            str(lbe_exe),
            "--format",
            "json",
            "session",
            "create",
            "--database",
            str(database),
            "--workspace",
            str(workspace),
            "--project-workspace-id",
            "wheel-smoke-workspace",
            "--session-id",
            "wheel-smoke-session",
            "--mode",
            "coding",
            "--permission",
            "write_allowed",
            "--runtime-policy",
            "permissive",
            "--provider",
            "openai-compatible",
            "--model",
            "wheel-smoke-model",
        ],
        cwd=workspace,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["action"] == "session.create"
    assert payload["session"]["session_id"] == "wheel-smoke-session"
    assert database.is_file()
    assert database.stat().st_size > 0
