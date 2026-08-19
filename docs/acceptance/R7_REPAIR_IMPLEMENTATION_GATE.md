# R7 Repair Implementation Gate

```text
phase: R7_REPAIR_IMPLEMENTATION
slice: COMPOSE_INSTALLED_CODING_WITH_EXISTING_GOVERNED_EXECUTION
status: OPEN
base_sha: 9138b47b279c0f4207bda952fd30521a828c952a
implementation_allowed: true
architecture_changes_allowed: false
required_evidence_level: INTEGRATION_PLUS_INSTALLED_RUNTIME
next_phase_locked: true
publish_allowed_now: false
```

## Trigger

R7 observable 3 failed because installed `lbe code` routes through read-only `reasoning.inspect` / `LBERequestController`, exposes only `workspace.read`, and never reaches the accepted governed Cline/R6E execution loop.

The completed repair investigation also proved that no production workspace mutation `ToolSpec` is registered.

## Authorized repair

Only these changes are authorized:

1. compose installed coding through the existing `GovernedClineWorker` + existing R6E `ToolRegistry` / `GovernedToolOrchestrator` path;
2. add one smallest safe workspace-bound production mutation capability behind existing R6C/R6E authorization;
3. preserve ToolReceipt correlation and same-provider continuation;
4. preserve existing session, provider, evidence, completion and validation authority;
5. add claim-matched focused/integration tests;
6. rebuild/install the exact repaired head and rerun R7 observable 3.

## Existing authority to reuse

```text
SessionMemoryRuntimeBridge
GovernedAgentGateway
resolve_authorization
ToolRegistry
GovernedToolOrchestrator
ToolReceipt
GovernedClineWorker
operational history correlation
CodingCompletionRuntime
```

## Forbidden

```text
second authorization resolver
second tool dispatcher
second session/provider/completion authority
provider-direct workspace mutation
native Cline mutation authority
architecture rewrite
release/version/tag/publish work
```

## Repair hypothesis

If installed coding composes the existing governed Cline/R6E turn loop and the existing registry exposes one bounded workspace mutation tool, provider proposals can mutate only through R6C/R6E, emit correlated ToolReceipts, continue in the same Cline turn, and remain provisional until deterministic completion validation.

## Falsifiers

- installed `lbe code` remains read-only;
- provider mutation occurs without ToolReceipt;
- mutation bypasses R6C;
- no concrete production mutation tool is exposed;
- denied/escalated mutation executes;
- operation/tool-call/receipt correlation is lost;
- a parallel authority is introduced;
- provider completion bypasses deterministic validation.

## Validation ladder

```text
source/diff inspection
 -> focused mutation-tool authorization tests
 -> Cline/R6E composition integration
 -> deny/escalate/failure/idempotency regression
 -> completion-authority regression
 -> isolated wheel build/install with PYTHONPATH removed
 -> R7 observable 3: real governed coding effect + ToolReceipt + continuation
 -> exact-head/clean-worktree proof
```

PASS does not automatically resume later R7 observables. The repaired installed observable must be recorded first and the next gate remains locked.
