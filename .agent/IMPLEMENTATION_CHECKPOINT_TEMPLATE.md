# LBE Implementation Checkpoint Template

Use one checkpoint per bounded implementation slice.

```text
phase: <phase id>
slice: <slice id>
status: OPEN | PASS | FAIL | UNVERIFIED | DOCUMENT_CONFLICT | MISSING_EVIDENCE

base_sha: <exact HEAD before implementation>
implementation_sha: <exact commit containing implementation>
checkpoint_sha: <exact commit containing this checkpoint, if separate>

requirements:
  - <requirement 1>
  - <requirement 2>

non_goals:
  - <explicitly excluded behavior>

existing_owner:
  - <responsibility -> file/class/function>

reuse_decision:
  decision: REUSE | ADAPT | PARTIAL_REUSE | NATIVE_FALLBACK | NEW_ARCHITECTURE_REQUIRED
  evidence: <why>

architecture_change:
  introduced: yes | no
  user_authorized: yes | no
  canonical_docs_updated_first: yes | no

files_changed:
  - <path>

required_evidence_level: UNIT | INTEGRATION | INSTALLED | LIVE_RUNTIME | USER_FLOW | RELEASE

validation_evidence:
  focused:
    command: <exact command>
    result: <exact result>
  integration:
    command: <exact command or NOT REQUIRED>
    result: <result>
  live_runtime:
    command_or_flow: <exact proof or NOT REQUIRED>
    result: <result>
  full_suite:
    command: <exact command>
    result: <result>
  git_diff_check:
    result: PASS | FAIL

unverified:
  - <remaining item or none>

document_conflicts:
  - <conflict or none>

workspace_proof:
  repository: Letterblack0306/LBE_Presistent_Agent_wall
  branch: main
  primary_worktree: PASS | FAIL
  origin: <remote URL>

push_proof:
  source_ref: refs/heads/main
  destination_ref: refs/heads/main
  pushed_sha: <sha>
  hook_result: <exact LBE WORKSPACE LOCK result>

project_user_ready: YES | NO | UNVERIFIED
release_ready: YES | NO | UNVERIFIED
next_phase_locked: true | false
```

## PASS rules

A slice may be `PASS` only when:

- every requirement of that slice is directly proven;
- evidence level matches the claim;
- required regression passes on the exact implementation SHA;
- `git diff --check` passes;
- no blocking document conflict exists;
- no unapproved architecture owner was introduced;
- the checkpoint lists any broader project limitations honestly.

A slice PASS does **not** automatically mean project READY or release READY.

## Forward-progression rule

Do not set `next_phase_locked: false` merely because this checkpoint is PASS. The next slice must be separately defined and activated in:

- `.lbe/governance/implementation-gates.json`;
- `docs/acceptance/CURRENT_IMPLEMENTATION_GATE.md`.

Then stop and await/perform the explicitly authorized next slice only.