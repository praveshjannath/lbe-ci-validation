# R4 Checkpoint Resume Acceptance Gate

Status: **OPEN — ACCEPTANCE PROOF ONLY — NEXT PHASE LOCKED**

```text
phase: R4_CHECKPOINT_RESUME_ACCEPTANCE
slice: PROVE_CHECKPOINT_RESTART_REHYDRATION_AND_STALE_STATE_INVALIDATION
kind: acceptance proof, not implementation
base_sha: 9523cf02f8a2e9248ad87d7f6f4cadef6d959f51
implementation_allowed: false
architecture_changes_allowed: false
next_phase_locked: true
required_evidence_level: INTEGRATION
```

## Investigation question

Does the existing persistent runtime already satisfy the reconciled R4 checkpoint/resume contract when a verified workspace fact is checkpointed, the underlying source and Git HEAD change externally, and the same session/task is reconstructed and resumed?

## Existing owners

```text
persistent runtime/session/task:
  lbe_guard_inspector/session_memory_runtime.py
  SessionMemoryRuntimeBridge

checkpoint + runtime adapter:
  lbe_guard_inspector/memory/integration.py
  SessionMemoryAdapter.checkpoint_compaction()
  SessionMemoryAdapter.rehydrate()

live Git/source revalidation:
  lbe_guard_inspector/memory/context.py
  inspect_git_state()
  invalidate_changed_sources()
  protected_checkpoint_eligibility()
  rehydrate_context()

persistent state:
  WorkspaceMemoryStore
```

## Reuse decision

```text
REUSE
```

No second checkpoint owner, session owner, Git-state owner, source-validation owner, memory store, or resume controller is authorized.

## Acceptance contract

The proof must demonstrate one canonical R4 path:

```text
create persistent session/task
 -> record a deterministic verified source-backed fact
 -> checkpoint with active task constraint + compaction history metadata
 -> externally change the source and commit a new Git HEAD
 -> reconstruct SessionMemoryRuntimeBridge from the same database/session/workspace
 -> start_or_resume()
 -> current Git/source state is re-inspected
 -> old source-backed fact is marked STALE and omitted from verified_facts
 -> checkpoint constraint survives
 -> changed HEAD makes the protected checkpoint INELIGIBLE
 -> compaction/history content is not promoted into current workspace truth
```

## Required observable

The bounded integration proof must directly observe:

1. one stable `session_id`, `task_id`, `project_workspace_id`, and canonical workspace root across restart;
2. a source-backed `WORKSPACE_FACT` begins `VERIFIED` with the original file hash;
3. one checkpoint is persisted and bound to the session;
4. active checkpoint constraints survive reconstruction/resume;
5. an external source change produces a different Git HEAD;
6. resume reports the current/new Git HEAD rather than the checkpoint HEAD;
7. checkpoint revalidation reports `head=MISMATCH`, `status=INELIGIBLE`, `reactivation_allowed=false`;
8. the old source-backed fact becomes `STALE` in persistent memory;
9. that stale fact is absent from resumed `verified_facts`;
10. task lifecycle state survives restart;
11. provider/session configuration survives restart where already persisted;
12. compaction summary/history data is not promoted into `verified_facts` or otherwise treated as current source truth;
13. no new runtime/checkpoint/memory owner is introduced;
14. focused R4/session-memory regression passes on the exact acceptance head;
15. broader regression requirement is classified from evidence rather than assumed.

## Falsifiers

Any of these keeps R4 non-PASS:

- resume reuses the checkpoint Git HEAD as current after the repository changed;
- changed source-backed evidence remains `VERIFIED`;
- stale source evidence appears in resumed `verified_facts`;
- active checkpoint constraints disappear or are silently replaced;
- session/task/workspace identity changes across reconstruction;
- a changed HEAD remains checkpoint-eligible without current evidence justifying it;
- compaction/assistant/history prose is promoted as current workspace fact;
- the proof requires a new parallel checkpoint/resume/memory owner;
- focused R4 regression fails on the exact head;
- observed runtime behavior contradicts the R4 roadmap contract.

## Allowed work

- inspect current R4 owners/tests;
- run bounded local integration proof using the existing runtime/store/checkpoint owners;
- create a temporary Git repository for deterministic external source/HEAD change proof;
- record exact memory validation status, checkpoint state, session/task identity and current Git state;
- run existing focused R4/session-memory tests;
- classify broader regression requirement;
- update acceptance/checkpoint/status docs only after evidence is collected;
- run diff scope and clean-worktree validation.

## Forbidden work

- runtime/test source implementation before a real defect is proven;
- second checkpoint/resume/session/memory owner;
- R5/R6/R7 implementation;
- provider architecture changes;
- CLI/TUI/MCP/release work;
- architecture changes;
- weakening stale-state or checkpoint eligibility checks to make the proof pass.

## Evidence ladder

```text
source owner inspection
 -> bounded checkpoint/change/restart integration proof
 -> focused R4/session-memory regression
 -> broader regression classification
 -> git diff/scope/worktree proof
 -> checkpoint
```

## PASS condition

R4 may be marked PASS only when every required observable is supported and no falsifier is observed. Existing focused tests alone are insufficient. A PASS does not activate R5 automatically.

```text
project_user_ready: NO
release_ready: NO
next_phase_locked: true
```
