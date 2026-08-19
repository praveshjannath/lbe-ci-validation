from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / ".lbe" / "governance" / "implementation-gates.json"

DOC_ALLOW_PREFIXES = (".agent/", "docs/")
DOC_ALLOW_SUFFIXES = (".md", ".mdx", ".rst", ".txt")


def fail(message: str) -> None:
    print(f"LBE IMPLEMENTATION GATE: BLOCKED: {message}", file=sys.stderr)
    raise SystemExit(1)


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=ROOT,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        fail(f"cannot inspect staged changes: {exc}")


def _staged_paths() -> tuple[str, ...]:
    result = _git("diff", "--cached", "--name-only", "--diff-filter=ACMR")
    if result.returncode != 0:
        fail(f"cannot enumerate staged paths: {result.stderr.strip() or 'git diff failed'}")
    return tuple(line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip())


def _documentation_only_commit_allowed() -> bool:
    staged = _staged_paths()
    if not staged:
        fail("implementation is locked and no staged documentation paths were found")

    disallowed = tuple(
        path
        for path in staged
        if not path.startswith(DOC_ALLOW_PREFIXES)
        or not path.lower().endswith(DOC_ALLOW_SUFFIXES)
    )
    if disallowed:
        fail(
            "implementation is locked; documentation-only allowance rejected staged path(s): "
            + ", ".join(disallowed)
        )

    diff_check = _git("diff", "--cached", "--check")
    if diff_check.returncode != 0:
        detail = (diff_check.stdout + diff_check.stderr).strip()
        fail(f"documentation-only staged diff failed git diff --cached --check: {detail}")

    return True


def main() -> None:
    if not GATE.is_file():
        fail(f"missing gate file: {GATE.relative_to(ROOT)}")

    try:
        data = json.loads(GATE.read_text(encoding="utf-8"))
    except Exception as exc:  # fail closed on malformed governance state
        fail(f"cannot parse gate file: {exc}")

    if not data.get("active_plan"):
        fail("active_plan is not declared")
    if not data.get("active_phase") or not data.get("active_slice"):
        fail("active phase/slice is not declared")
    if data.get("status") != "OPEN":
        fail(f"current gate status is {data.get('status')!r}, expected 'OPEN'")

    if data.get("implementation_allowed") is not True:
        if _documentation_only_commit_allowed():
            print(
                "LBE IMPLEMENTATION GATE: PASS — documentation-only exception; "
                f"phase={data['active_phase']} slice={data['active_slice']} implementation_allowed=false"
            )
            return
        fail("implementation_allowed is not true")

    if data.get("next_phase_locked") is not True:
        fail("next_phase_locked must remain true while the current slice is active")

    blocking = set(data.get("blocking_statuses", []))
    required = {"FAIL", "UNVERIFIED", "DOCUMENT_CONFLICT", "MISSING_EVIDENCE"}
    if not required.issubset(blocking):
        fail("blocking_statuses does not contain all mandatory fail-closed states")

    rules = data.get("rules") or {}
    for key in (
        "one_active_slice",
        "no_next_phase_without_pass",
        "no_parallel_architecture",
        "existing_owner_audit_required",
        "reuse_evaluation_required",
        "architecture_change_requires_user_authorization",
        "checkpoint_required_before_advance",
        "fail_closed",
    ):
        if rules.get(key) is not True:
            fail(f"mandatory rule disabled: {key}")

    print(
        "LBE IMPLEMENTATION GATE: PASS — "
        f"phase={data['active_phase']} slice={data['active_slice']} next_phase_locked=true"
    )


if __name__ == "__main__":
    main()
