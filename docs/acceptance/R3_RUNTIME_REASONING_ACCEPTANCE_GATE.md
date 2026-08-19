# R3 Runtime Reasoning Acceptance Gate

Status: **OPEN — ACCEPTANCE PROOF ONLY — NEXT PHASE LOCKED**

```text
phase: R3_RUNTIME_REASONING_ACCEPTANCE
slice: PROVE_PERSISTENT_RUNTIME_TO_EXISTING_REASONING_BOUNDARY
kind: acceptance proof, not implementation
base_sha: 637e19e251aaad407c9be8502d2c3e2696c28c89
implementation_allowed: false
architecture_changes_allowed: false
next_phase_locked: true
required_evidence_level: INTEGRATION
```

## Investigation question

Does the current persistent runtime already satisfy the reconciled R3 roadmap contract when exercised through the existing reasoning owner, without introducing or patching runtime architecture?

## Existing owners

```text
persistent session/task lifecycle:
  lbe_guard_inspector/session_memory_runtime.py
  SessionMemoryRuntimeBridge

runtime -> reasoning boundary:
  SessionMemoryRuntimeBridge.run_reasoning()

existing reasoning controller:
  lbe_guard_inspector/request_controller.py
  LBERequestController.run()

provider/controller composition root:
  lbe_guard_inspector/reasoning_runtime.py
  build_provider_controller()

request/response contracts:
  lbe_guard_inspector/reasoning_contracts.py
  LBERequest / LBEResponse
```

## Reuse decision

```text
REUSE
```

No new reasoning controller, session owner, response contract, verdict authority, provider authority, or persistence owner is authorized.

## Acceptance contract

The proof must demonstrate one canonical R3 path:

```text
SessionMemoryRuntimeBridge.run_reasoning(...)
        |
        v
construct existing LBERequest
        |
        v
real existing LBERequestController.run(...)
        |
        v
existing LBEResponse
        |
        v
persist canonical task lifecycle outcome
```

The reasoning controller may receive deterministic injected collaborators/backend so the proof is local and reproducible, but the controller object itself must be the real `LBERequestController`. A generic fake object implementing `.run()` is insufficient for acceptance.

## Required observable

At minimum the bounded integration proof must directly observe:

1. one persisted session/task identity;
2. `SessionMemoryRuntimeBridge.run_reasoning()` constructs and passes an `LBERequest` with the expected task ID and canonical workspace root;
3. the invoked controller is the existing `LBERequestController`;
4. the returned object is the existing `LBEResponse` contract;
5. response task identity matches the requested task identity;
6. the runtime persists the corresponding canonical task lifecycle outcome;
7. the reasoning controller remains independently callable/testable outside the runtime bridge;
8. no second reasoning/session owner is introduced;
9. focused R3/session-runtime regression passes on the exact acceptance head;
10. required broader regression level is explicitly classified from evidence rather than assumed.

## Required outcomes

The acceptance proof must cover at least:

```text
COMPLETED -> TaskStatus.COMPLETED
INSUFFICIENT_EVIDENCE -> TaskStatus.BLOCKED
ORCHESTRATION_ERROR -> TaskStatus.FAILED
```

Interruption behavior must either be directly proven or explicitly classified with existing focused evidence if the normal acceptance harness cannot safely synthesize `KeyboardInterrupt` through the real controller.

## Falsifiers

Any of the following disproves R3 acceptance and keeps the slice non-PASS:

- `run_reasoning()` bypasses `LBERequestController` for the claimed canonical path;
- task/workspace identity changes between runtime request and response;
- returned value is not the existing `LBEResponse` contract;
- lifecycle outcome is not persisted or is persisted under the wrong task/session;
- reasoning requires persistence internals or becomes a second session owner;
- acceptance can pass only by introducing a new controller/runtime owner;
- focused regression fails on the exact head;
- observed source/runtime behavior contradicts the reconciled roadmap contract.

## Allowed work

- inspect current R3 source owners and tests;
- add no runtime implementation by default;
- run a bounded local integration probe using the real `LBERequestController` and deterministic injected collaborators/backend;
- run existing focused session/runtime/controller tests;
- record exact stdout/stderr and lifecycle state;
- update this gate/checkpoint/current-status authority only after evidence is collected.

## Forbidden work

- runtime source patch before a real defect is proven;
- second reasoning controller;
- second session/task lifecycle owner;
- provider architecture changes;
- R4/R5/R6/R7 work;
- CLI/TUI/MCP/release changes;
- architecture changes;
- broad refactor to make the acceptance harness easier.

## Evidence ladder

```text
source owner inspection
-> bounded R3 integration proof using real LBERequestController
-> focused R3/session-runtime regression
-> required broader regression classification
-> git diff/scope/worktree proof
-> checkpoint
```

## PASS condition

R3 may be marked PASS only when every required observable is directly supported and no falsifier is observed. A pre-existing unit test alone is insufficient. A successful integration proof does not unlock R4 automatically.

```text
project_user_ready: NO
release_ready: NO
next_phase_locked: true
```
