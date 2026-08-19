from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

from setuptools import setup
from setuptools.command.build_py import build_py as _build_py


class BuildPyWithClineWorkerDependencies(_build_py):
    """Materialize the locked Cline worker dependency tree into built artifacts."""

    def run(self) -> None:
        repository_root = Path(__file__).resolve().parent
        worker_root = repository_root / "lbe_guard_inspector" / "runtime" / "cline_worker"
        package_json = worker_root / "package.json"
        package_lock = worker_root / "package-lock.json"

        if not package_json.is_file() or not package_lock.is_file():
            raise RuntimeError("Cline worker package.json and package-lock.json are required")

        npm_name = "npm.cmd" if os.name == "nt" else "npm"
        npm_executable = shutil.which(npm_name)
        if npm_executable is None:
            raise RuntimeError(f"required Node package manager is unavailable: {npm_name}")

        subprocess.run(
            [
                npm_executable,
                "ci",
                "--ignore-scripts",
                "--omit=dev",
                "--no-audit",
                "--no-fund",
            ],
            cwd=worker_root,
            check=True,
        )

        dependency_root = worker_root / "node_modules"
        cline_agents = dependency_root / "@cline" / "agents" / "package.json"
        if not cline_agents.is_file():
            raise RuntimeError("locked Cline worker install did not materialize @cline/agents")

        super().run()

        built_worker_root = (
            Path(self.build_lib)
            / "lbe_guard_inspector"
            / "runtime"
            / "cline_worker"
        )
        shutil.copytree(
            dependency_root,
            built_worker_root / "node_modules",
            dirs_exist_ok=True,
        )


setup(cmdclass={"build_py": BuildPyWithClineWorkerDependencies})
