# LBE Cline Workspace Authority and Progression Rules

Status: **ALWAYS ON**

These rules apply to every Cline task in this repository. They do not replace LBE runtime governance. They tell Cline how to obey the canonical project controls.

## 1. Read authority before acting

Before planning or changing anything, read in this order:

1. `.agent/PROJECT_CONTEXT.md`
2. `.lbe/governance/workspace-lock.json`
3. `.lbe/governance/implementation-gates.json`
4. the exact `active_plan` path declared by `.lbe/governance/implementation-gates.json`
5. `docs/governance/AGENT_IMPLEMENTATION_EXECUTION_GUIDE.md`
6. architecture/design documents referenced by the active plan
7. relevant current source/tests/runtime evidence
8. `docs/acceptance/CURRENT_IMPLEMENTATION_GATE.md` only as historical checkpoint ledger when it is not the active plan

Never substitute a similarly named document for the machine-declared `active_plan`.

If any required file is missing, malformed, contradictory, or stale relative to live Git evidence, stop implementation and report `DOCUMENT_CONFLICT` or `MISSING_EVIDENCE`.

## 2. Canonical Git authority

Implementation and delivery are allowed only from:

```text
repository: Letterblack0306/LBE_Presistent_Agent_wall
remote: origin
branch: main
worktree: primary Git worktree
push target: origin/main
```

Before any write, commit, or push prove with live Git commands:

```text
git rev-parse --show-toplevel
git branch --show-current
git rev-parse HEAD
git remote get-url origin
git worktree list --porcelain
git status --short --branch
```

Hard rules:

- Never create or switch to a feature branch for implementation.
- Never create a secondary worktree for implementation.
- Never commit from detached HEAD.
- Never push any ref except `refs/heads/main` to `origin/main`.
- Never bypass `.githooks/pre-commit` or `.githooks/pre-push`.
- Never use `--no-verify`, force push, alternate remote, GitHub ref/API mutation, or another clone to bypass the workspace lock.
- Side branches/worktrees may be inspected read-only only.

If the primary `main` worktree is dirty with unrelated user-owned changes, stop and report them. Do not stash, reset, clean, delete, commit, or move them without explicit user instruction.

## 3. One active implementation slice

Only the `active_phase` + `active_slice` in `.lbe/governance/implementation-gates.json` may be worked on.

Do not begin the next phase because the current code "looks done". `next_phase_locked=true` means exactly that.

Blocking states are:

```text
FAIL
UNVERIFIED
DOCUMENT_CONFLICT
MISSING_EVIDENCE
BLOCKED_WORKSPACE_AUTHORITY
BLOCKED_PARALLEL_ARCHITECTURE
```

Any blocking state stops forward implementation.

## 4. Required phase workflow

Every slice must follow, in order:

```text
G0  authoritative plan loaded
G1  canonical repo/main/primary worktree proven
G2  exact base SHA recorded
G3  existing owner(s) inspected
G4  reuse/adaptation options evaluated
G5  bounded slice contract documented BEFORE implementation
G6  only the approved slice implemented
G7  focused tests/checks pass
G8  required integration/live/installed/user-flow evidence passes
G9  full regression required by the slice passes
G10 checkpoint record written with exact implementation SHA
G11 current slice explicitly PASS
G12 only then activate the next slice
G13 push only main HEAD -> origin/main
```

Never combine activation of a future architecture with implementation of that architecture in the same undocumented step.

## 5. Reuse before rebuild

Before creating a new runtime/provider/session/tool/event/persistence/control owner:

1. identify the existing owner;
2. inspect its current code and tests;
3. inspect the active reuse plan;
4. test whether extension/adaptation satisfies the requirement;
5. document why reuse fails if proposing a new owner;
6. obtain explicit user authorization for an architecture change;
7. update canonical design/gate documents first.

For provider/continuation work, preserve the recorded Cline reuse decision and evaluate any newly proposed Cline version/layer before rebuilding equivalent mature plumbing when the active plan requires it.

## 6. Protected authority categories

Do not create parallel owners for:

- workspace/project identity;
- session/task persistence;
- provider/model capability truth;
- provider event normalization;
- authorization;
- governed tool dispatch;
- operation/receipt identity;
- runtime-event persistence;
- checkpoint/recovery;
- evidence provenance;
- validation truth;
- completion truth;
- control protocol semantics;
- transcript persistence;
- TUI/runtime execution.

A new class/file is not automatically a new architecture, but if it becomes an independent authority for one of these responsibilities it is blocked unless the architecture-change gate explicitly permits it.

## 7. Evidence discipline

Use these evidence levels exactly:

```text
UNIT
INTEGRATION
INSTALLED
LIVE_RUNTIME
USER_FLOW
RELEASE
```

A lower level cannot satisfy a higher-level claim. "Tests pass" does not prove a live provider flow; a live provider flow does not prove release readiness.

Never claim `READY` without naming the exact scope, for example:

```text
P16 cancellation capability slice: PASS at INTEGRATION
Project user-ready: UNVERIFIED
Release-ready: NO
```

## 8. Completion behavior

At the end of every implementation slice report:

- exact base SHA;
- exact implementation SHA;
- files changed;
- existing owners reused;
- new authority introduced: yes/no;
- focused validation;
- full-suite validation when required;
- evidence level achieved;
- remaining `UNVERIFIED` items;
- current gate status;
- whether next phase remains locked;
- push result and exact remote ref.

If the gate is not PASS, stop. Do not start the next implementation.