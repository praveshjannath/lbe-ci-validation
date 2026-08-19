# Skill: Execute One Governed LBE Implementation Slice

Use this skill whenever Cline is asked to implement, continue, fix, refactor, validate, or advance work in this repository.

## Goal

Execute exactly one authorized slice without branch/worktree drift, architecture duplication, or premature readiness claims.

## Step 1 — Load the project contract

Read:

- `.agent/PROJECT_CONTEXT.md`
- `.lbe/governance/workspace-lock.json`
- `.lbe/governance/implementation-gates.json`
- the exact `active_plan` declared by `.lbe/governance/implementation-gates.json`
- `docs/governance/AGENT_IMPLEMENTATION_EXECUTION_GUIDE.md`

Do not substitute an older/similarly named acceptance file for the machine-declared `active_plan`.

Resolve:

```text
active_phase
active_slice
implementation_allowed
architecture_changes_allowed
next_phase_locked
required_evidence_level
blocking_statuses
allowed_scope
```

If the request is outside the active slice, stop and report `BLOCKED_OUTSIDE_ACTIVE_SLICE`.

## Step 2 — Prove canonical workspace

Record:

```text
repository root
branch
HEAD
origin URL
primary worktree
working-tree status
```

Required:

```text
branch == main
current worktree == primary worktree
origin == canonical repository
```

If not, stop with `BLOCKED_WORKSPACE_AUTHORITY`.

Do not clean unrelated changes. Do not create a branch/worktree.

## Step 3 — Record the base SHA

The base SHA is the exact `git rev-parse HEAD` before this slice begins.

Add it to the active checkpoint record before implementation when the slice has not yet been activated.

Never reuse an older base SHA after new commits land.

## Step 4 — Inspect existing owners

Search current source/tests/call sites for the responsibility being changed.

For each responsibility record:

```text
responsibility
existing owner file/class/function
current call path
current tests
gaps proven by evidence
```

If an existing owner can be extended, extend it. Do not create a second authority.

## Step 5 — Evaluate reuse/adaptation

Before writing new architecture, inspect:

- existing LBE owner;
- project migration/reuse direction;
- relevant Cline lower-layer reuse decision for provider/continuation work;
- previously carried LBE Core functionality when relevant.

Record one decision:

```text
REUSE
ADAPT
PARTIAL_REUSE
NATIVE_FALLBACK
NEW_ARCHITECTURE_REQUIRED
```

`NEW_ARCHITECTURE_REQUIRED` is blocked unless `architecture_changes_allowed=true`, the active plan names the authorized change, and explicit user authorization is recorded.

## Step 6 — Define the bounded slice

Before code changes, the active gate must state:

```text
phase
slice
requirements
non_goals
existing_owner
reuse_decision
allowed_files_or_owners
required_evidence_level
validation_plan
blockers
```

Do not expand scope while implementing. New discoveries become follow-up findings unless they are required to make the current slice correct.

## Step 7 — Implement only the slice

Rules:

- preserve existing authority boundaries;
- no speculative adjacent architecture;
- no provider/tool/session persistence duplication;
- no UI-owned runtime behavior;
- no fake streaming/cancellation/approval semantics;
- no undocumented dependency adoption;
- no destructive Git operations.

## Step 8 — Validate in ascending evidence order

Run the minimum relevant sequence:

```text
syntax/static checks
focused UNIT tests
INTEGRATION tests
installed-path proof if required
LIVE_RUNTIME proof if required
USER_FLOW proof if required
full regression suite when gate requires it
git diff --check
```

Capture exact commands and results.

If any required proof is unavailable, status is `UNVERIFIED`, not PASS.

## Step 9 — Re-open changed files

After editing, inspect every changed implementation and test file again.

Confirm:

- intended code actually exists;
- no stale temporary code remains;
- no accidental authority bypass;
- tests test the real claim rather than only a mock call;
- unsupported capabilities remain reported as unsupported.

## Step 10 — Write the checkpoint

Use `.agent/IMPLEMENTATION_CHECKPOINT_TEMPLATE.md`.

A PASS checkpoint requires:

```text
unverified: none for this slice's required evidence
blocking_document_conflicts: none
status: PASS
```

Items outside the slice may remain unverified, but they must be listed and may block overall project readiness.

## Step 11 — Commit and push

Only after required validation:

```text
git add <bounded files>
git commit -m "<slice-specific message>"
git push --verbose origin HEAD:refs/heads/main
```

Do not use `--no-verify`.

The pre-push hook must print:

```text
LBE WORKSPACE LOCK: PASS — canonical primary-worktree main -> origin/main
```

If push is blocked, report the exact hook output. Do not invent a lock owner, wait state, approval service, or race explanation without evidence.

## Step 12 — Stop

After one slice reaches its checkpoint, STOP.

Do not activate or implement the next slice unless the current gate has been explicitly reconciled to PASS and the next slice has its own documented contract.