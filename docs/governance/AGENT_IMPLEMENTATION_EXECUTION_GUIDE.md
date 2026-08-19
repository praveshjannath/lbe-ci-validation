# Agent Implementation Execution Guide

Status: **CANONICAL OPERATING GUIDE**

This guide defines how any coding agent must implement work in `Letterblack0306/LBE_Presistent_Agent_wall` without branch/worktree drift, undocumented phase advancement, or parallel architecture creation.

It complements machine enforcement in `.lbe/governance/` and Git hooks. Machine gates win over prose when they disagree; disagreement itself must be reported as `DOCUMENT_CONFLICT`.

---

# 1. Exact repository and push destination

Allowed implementation repository:

```text
Letterblack0306/LBE_Presistent_Agent_wall
```

Allowed local Git state:

```text
branch: main
worktree: primary worktree only
HEAD: attached to refs/heads/main
remote: origin
```

Allowed push:

```text
local:  refs/heads/main at current HEAD
remote: origin
remote ref: refs/heads/main
```

Recommended push command:

```powershell
git push --verbose origin HEAD:refs/heads/main
```

Forbidden:

```text
feature branches
agent/* branches
release implementation branches
secondary implementation worktrees
detached HEAD implementation
alternate remotes
force push
--no-verify
GitHub API/ref updates used to bypass local hooks
```

Historical branches/worktrees may be inspected read-only.

---

# 2. Files that declare authority

## Machine authority

### `.lbe/governance/workspace-lock.json`
Declares repository/branch/worktree/push restrictions.

### `.lbe/governance/implementation-gates.json`
Declares exactly one active phase and slice, whether implementation/architecture change is allowed, blocking statuses, and whether the next phase is locked.

### `.githooks/pre-commit`
Rejects commit operations outside canonical main/primary-worktree conditions and invokes the implementation gate check.

### `.githooks/pre-push`
Rejects push operations not matching canonical main HEAD -> origin/main.

### `scripts/check-implementation-gate.py`
Fail-closed structural validation of the machine gate.

## Agent routing authority

### `.agent/PROJECT_CONTEXT.md`
First-read project context and current known baseline.

### `.cline/rules/00-lbe-workspace-and-progression.md`
Always-on Cline instructions.

### `.cline/skills/lbe-phase-execution/SKILL.md`
Exact procedure for executing one slice.

## Acceptance authority

### `docs/acceptance/CURRENT_IMPLEMENTATION_GATE.md`
Human-readable active slice contract and completed checkpoint history.

### `.agent/IMPLEMENTATION_CHECKPOINT_TEMPLATE.md`
Required format for recording every new slice.

## Architecture/plan authority

Use the active architecture/design file named by the current gate. Do not select an old branch document merely because it is more detailed.

GPT-Knowledge is reference/architecture knowledge, not live repository truth. Use it to challenge/reconcile the plan, then update canonical repo documents before implementation if the plan changes.

---

# 3. Required phase lifecycle

Every implementation slice follows these phases exactly.

## G0 — Authority load

Read all authority files.

**BLOCK if:** missing, malformed, contradictory, or gate does not identify one active slice.

Status:

```text
MISSING_EVIDENCE
DOCUMENT_CONFLICT
```

## G1 — Workspace proof

Verify repo, branch, HEAD, origin, primary worktree, working-tree state.

**BLOCK if:** non-main, detached, secondary worktree, wrong remote, Git operation in progress.

Status:

```text
BLOCKED_WORKSPACE_AUTHORITY
```

## G2 — Base checkpoint

Record exact pre-change SHA.

**BLOCK if:** base cannot be tied to current main HEAD.

## G3 — Existing-owner audit

Identify existing owner files/classes/functions/tests/call sites for the requested responsibility.

**BLOCK if:** implementation starts before ownership is known.

## G4 — Reuse/adaptation decision

Evaluate:

```text
existing LBE implementation
existing migrated LBE Core material
current project reuse decisions
Cline lower layers when applicable
other specifically approved dependencies
```

Record:

```text
REUSE
ADAPT
PARTIAL_REUSE
NATIVE_FALLBACK
NEW_ARCHITECTURE_REQUIRED
```

**BLOCK if:** new parallel architecture is attempted before this decision.

## G5 — Slice activation

Before implementation, record:

```text
phase
slice
requirements
non-goals
existing owner
reuse decision
allowed ownership/files
required evidence level
validation plan
blockers
```

Update both machine gate and human acceptance record.

**BLOCK if:** agent tries to implement an undeclared adjacent task.

## G6 — Implementation

Change only the bounded slice.

**BLOCK if:** scope expands into a new authority owner or unrelated phase.

## G7 — Focused proof

Run focused unit/static/check tests.

**BLOCK if:** any required focused proof fails.

## G8 — Claim-level proof

Match proof to claim:

```text
UNIT
INTEGRATION
INSTALLED
LIVE_RUNTIME
USER_FLOW
RELEASE
```

**BLOCK if:** proof level is lower than claim level.

## G9 — Regression proof

Run the full suite when the active gate requires it, on the exact implementation SHA/state.

**BLOCK if:** suite fails, times out without accepted evidence, or result belongs to another SHA.

## G10 — Re-open/review changed files

Confirm implementation, tests, unsupported-capability truthfulness, and no accidental owner duplication.

**BLOCK if:** review reveals drift or unproven semantics.

## G11 — Checkpoint record

Use `.agent/IMPLEMENTATION_CHECKPOINT_TEMPLATE.md`.

**BLOCK if:** required fields/evidence are absent.

## G12 — PASS classification

Current slice may become PASS only when its requirements and evidence are satisfied.

Broader project limitations stay listed separately.

**BLOCK if:** any slice requirement remains `UNVERIFIED`, `FAIL`, `DOCUMENT_CONFLICT`, or `MISSING_EVIDENCE`.

## G13 — Delivery

Commit current bounded slice and push only main HEAD -> origin/main.

**BLOCK if:** hook rejects.

## G14 — Stop boundary

After delivery/checkpoint, stop.

Do not automatically begin the next slice.

The next slice requires separate activation through G0-G5.

---

# 4. Architecture-change blocker

The following responsibilities are protected owners:

```text
workspace/project identity
session/task persistence
provider/model capability truth
provider-event normalization
authorization
governed tool dispatch
operation/receipt identity
runtime-event persistence
checkpoint/recovery
evidence provenance
validation truth
completion truth
control protocol
transcript persistence
TUI/runtime execution ownership
```

A new architecture owner is allowed only when all seven conditions are true:

1. current owner identified;
2. current owner inspected in source/tests;
3. exact unmet requirement documented;
4. reuse/adaptation tested/evaluated;
5. evidence proves current owner cannot satisfy it cleanly;
6. user explicitly authorizes architecture change;
7. canonical design docs and machine gate are updated before implementation.

Otherwise:

```text
BLOCKED_PARALLEL_ARCHITECTURE
```

`architecture_changes_allowed=true` alone is not enough; the active gate must name the authorized architecture change and evidence.

---

# 5. Provider/Cline implementation rule

Cline is reusable lower-layer infrastructure only when it preserves LBE authority.

Previously recorded decision:

```text
@cline/llms@0.0.73 -> NATIVE fallback for that evaluated pin
```

because its production-adoption gate failed at that time. Do not interpret that as a permanent ban on every future Cline version.

For any new Cline adoption proposal:

```text
pin exact package/version
inspect current package/API/license/dependencies
map events to LBE normalized semantics
prove pre-mutation tool interception
prove LBE result -> provider continuation
prove cancellation/error attribution
prove session/workspace/tool authority stays with LBE
record REUSE/PARTIAL_REUSE/NATIVE decision
```

Never adopt `@cline/core` wholesale as session/tool/runtime authority without a separately authorized migration.

---

# 6. Current cancellation checkpoint rule

Canonical main includes commit:

```text
95f8be0eb98f57ad050ae662ae1add0d5f9de8ab
```

which adds transport capability checking for cancellation.

Truthful contract:

```text
transport supports cancellation -> runtime may accept and propagate cancel
transport does not support cancellation -> runtime rejects live cancel
UrllibJsonTransport -> supports_cancellation = false
```

Before any later implementation phase is activated, this change requires checkpoint reconciliation on the exact current lineage:

- run the required full repository suite;
- run focused cancellation/provider/control tests;
- run `git diff --check`;
- confirm no late provider result changes a cancelled turn for supported transports;
- record exact evidence in `docs/acceptance/CURRENT_IMPLEMENTATION_GATE.md`;
- set architecture changes to false unless the next separately activated slice explicitly requires one.

Until then:

```text
NEXT IMPLEMENTATION PHASE = LOCKED
```

---

# 7. Required agent report format

Every implementation completion report must use this structure:

## Scope

```text
phase:
slice:
required evidence level:
```

## Git proof

```text
base SHA:
implementation SHA:
branch: main
primary worktree: PASS/FAIL
push ref: origin/main
```

## Ownership/reuse

```text
existing owner(s):
reuse decision:
new architecture owner introduced: yes/no
```

## Changes

```text
files changed:
behavior added/changed:
non-goals preserved:
```

## Validation

```text
focused:
integration:
installed/live/user-flow if required:
full suite:
git diff --check:
```

## Remaining truth

```text
UNVERIFIED:
DOCUMENT CONFLICTS:
known limitations:
```

## Status

```text
slice: PASS/FAIL/UNVERIFIED
project user-ready: YES/NO/UNVERIFIED
release-ready: YES/NO/UNVERIFIED
next phase locked: true/false
```

Do not output plain `READY`.

---

# 8. Pull/start procedure for a local agent

From the canonical primary worktree:

```powershell
git checkout main
git pull --ff-only origin main
powershell -ExecutionPolicy Bypass -File scripts/enable-workspace-lock.ps1
python scripts/check-implementation-gate.py
```

Then the agent reads `.agent/PROJECT_CONTEXT.md` and performs only the active slice.

If the worktree contains unrelated user changes, stop before pull if the pull would overwrite/conflict. Preserve user state; never auto-stash/reset/clean.

---

# Final rule

**One main worktree. One main branch. One active slice. One set of authority owners. Reuse before rebuild. Proof before PASS. PASS before the next phase. Push only canonical main HEAD to origin/main.**