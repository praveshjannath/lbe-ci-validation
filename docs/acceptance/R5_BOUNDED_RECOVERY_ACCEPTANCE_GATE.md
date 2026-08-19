# R5 Bounded Classified Recovery Acceptance Gate

Status: **OPEN — ACCEPTANCE PROOF ONLY — NEXT PHASE LOCKED**

```text
phase: R5_BOUNDED_RECOVERY_ACCEPTANCE
slice: PROVE_CLASSIFIED_BOUNDED_RECOVERY_AND_DUPLICATE_PREVENTION
base_sha: 030af54df5ba8a514482e4b27dd41995518ff279
implementation_allowed: false
architecture_changes_allowed: false
next_phase_locked: true
required_evidence_level: INTEGRATION
```

## Acceptance question

Does the existing bounded recovery owner already satisfy the reconciled R5 contract without runtime implementation changes?

## Existing owners

```text
lbe_guard_inspector/recovery.py
  FailureClass
  RetryPolicy
  classify_failure()
  run_with_recovery()
  persist_recovery_state()
  load_recovery_state()

lbe_guard_inspector/session_memory_runtime.py
  SessionMemoryRuntimeBridge.run_recoverable()
  SessionMemoryRuntimeBridge.load_recovery_state()

lbe_guard_inspector.memory.WorkspaceMemoryStore
```

## Reuse decision

```text
REUSE
```

Current source and tests already contain the recovery authority. This slice proves acceptance; it does not authorize a second recovery owner.

## Required observables

1. a classified transient/retryable failure retries only within declared `max_attempts` and can recover;
2. persisted recovery state records exact attempt count and terminal success/failure state;
3. persisted attempt state survives runtime reconstruction where applicable;
4. deterministic/terminal failures such as permission denial do not retry;
5. scope conflict cannot be configured as retryable;
6. retryable operations requiring idempotency reject non-idempotent execution before duplicate mutation can occur;
7. a successfully completed operation cannot execute again under the same task/operation identity;
8. required evidence-between-attempts blocks the next attempt when evidence is absent;
9. cancellation stops before another attempt and persists a terminal cancellation state, or is explicitly classified from source plus focused evidence if no repository-owned direct cancellation harness exists;
10. failure classification remains owned by the existing recovery layer;
11. no new recovery/session/evidence owner is introduced;
12. focused R5 recovery regression passes on the exact acceptance head.

## Required stop behavior

```text
PERMISSION_DENIAL -> no retry
SCOPE_CONFLICT -> cannot be retryable
VALIDATION_FAILURE -> cannot be retryable
CANCELLATION -> terminal stop
successful terminal operation -> duplicate execution blocked
non-idempotent retryable operation -> rejected before retry loop
missing required retry evidence -> terminal stop
```

## Falsifier

R5 cannot PASS if any deterministic/terminal denial loops, a non-idempotent operation can retry, a completed operation executes twice, required retry evidence can be skipped, persisted attempt state is lost, cancellation continues into another attempt, or acceptance requires a parallel recovery owner.

## Evidence ladder

```text
source owner inspection
-> smallest repository-owned R5 discriminators
-> focused recovery regression
-> explicit cancellation/scope classification
-> diff/scope/worktree proof
-> checkpoint
```

## Allowed work

- inspect current recovery/runtime/memory owners;
- execute existing repository-owned recovery tests through LoopTool;
- run bounded runtime/debug diagnostics through LoopTool;
- update acceptance/checkpoint/status documents through GitHub;
- classify missing evidence before any repair.

## Forbidden work

- runtime/test implementation before evidence proves a real defect;
- new recovery owner;
- R6/R7/CLI/TUI/MCP/release work;
- provider architecture changes;
- architecture changes.

## Completion predicate

PASS only when the required observables are supported at the claimed level with no falsifier. PASS does not auto-activate R6.
