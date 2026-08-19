# LBE Persistent Agent — Canonical Implementation Plan

Updated: 2026-08-17
Status: Active canonical roadmap — R7 installed end-to-end acceptance failed on installed coding composition; repair investigation required before any implementation or release progression
## Authority reconciliation (READ FIRST)

Current machine-gate authority — `.lbe/governance/implementation-gates.json` and
`docs/acceptance/R7_INSTALLED_END_TO_END_ACCEPTANCE_GATE.md`:

```text
phase: R7_INSTALLED_END_TO_END_ACCEPTANCE
slice: OBSERVABLE_13_INSTALLED_RUNTIME_REGRESSION
status: OPEN
observables 1-12: PASS (observable 3 PASS_AFTER_REPAIR)
observable 13: OPEN (current active slice)
implementation_allowed: false
architecture_changes_allowed: false
next_phase_locked: true
base_sha: 69c6ae764bc217cd5795ddf8a972658223a681a0
HEAD: 24d6e5950b912c0889396e95d307e41bdf05d06f
```

The status lines in the body below that describe "R7 FAIL / repair not yet activated" are
**historical records** of the earlier observable-3 installed coding-composition failure and
its repair investigation. They are not current machine-gate state. Live Git/runtime/validation
evidence and the machine gate outrank them.

**Architecture correction — read before extending the LBE wall:** the reasoning controller
became the agent. See `docs/design/AGENT_AGENCY_LBE_AUTHORITY_SEPARATION.md` and section 15.



## 1. Product goal

Build a persistent, provider-neutral LBE runtime where the provider reasons while LBE owns workspace/session identity, context/evidence authority, mode/policy, authorization, governed execution, receipts, validation/completion truth, and persistent state.

## 2. Non-negotiable invariants

- provider/model changes must not change LBE authority;
- current workspace/runtime evidence outranks memory/reference history;
- only registered governed tools may execute;
- operation IDs/receipts prevent unintended duplicate execution;
- provider continuation consumes receipts but owns no execution authority;
- terminal completion belongs to deterministic LBE validation, not provider/model prose;
- CLI/TUI/API surfaces are control/projection layers, never duplicate authority owners;
- installed behavior must compose the same authorities proven in source/runtime acceptance;
- no second session/context/retrieval/mode/authorization/tool/receipt/completion/continuation/recovery owner;
- lower-layer acceptance does not imply end-to-end installed composition;
- a failed harness invocation is not a product defect; a product defect requires evidence from the intended runtime boundary.

## 3. Current roadmap state

```text
R3  PROVEN_COMPLETE
R4  PROVEN_COMPLETE
R5  PROVEN_COMPLETE
R6A PROVEN_COMPLETE
R6B PROVEN_COMPLETE
R6C PROVEN_COMPLETE
R6D PROVEN_COMPLETE
R6E PROVEN_COMPLETE
R6F PROVEN_COMPLETE
CLI PROVEN_COMPLETE
R7  FAIL — INSTALLED NORMAL-PATH CODING COMPOSITION GAP
repair investigation NOT YET ACTIVATED
release/package readiness BLOCKED_BY_R7
```

Current active gate remains the failed R7 acceptance gate:

```text
phase: R7_INSTALLED_END_TO_END_ACCEPTANCE
slice: PROVE_INSTALLED_PERSISTENT_AGENT_NORMAL_PATH_OVER_ACCEPTED_AUTHORITIES
status: FAIL
implementation_allowed: false
architecture_changes_allowed: false
next_phase_locked: true
base_sha: 69c6ae764bc217cd5795ddf8a972658223a681a0
activation_sha: 401a4f184fcbeae5ff6e4d58be139515b9861ed2
failure_record_head: 66e46b5886d2e71d0542ce782179722ae476d3f6
required_evidence_level: USER_VISIBLE_RUNTIME
release_path_authorized: true
publish_allowed_now: false
```

## 4. Accepted phases and what they do — and do not — prove

R3 through R6F and CLI normal-path acceptance remain `PROVEN_COMPLETE` for their bounded contracts.

They establish accepted constituent authorities:

```text
R3  runtime -> reasoning integration
R4  checkpoint/resume/rehydration
R5  bounded classified recovery
R6A provider abstraction
R6B typed mode/policy resolution
R6C authorization resolution
R6D context/rule/guard assembly
R6E governed tool orchestration + ToolReceipt
R6F evidence-owned completion/validation
CLI persistent control/projection surface
```

They did not prove that the installed `lbe code` command composes all of those authorities in one real coding path. R7 is the first release-level installed composition proof and correctly found that gap.

## 5. R7 — Installed end-to-end persistent agent proof

**Classification: `FAIL` — decisive observable-3 falsifier.**

Evidence reached:

```text
exact-head isolated install                         PASS
installed lbe identity without source-tree leakage PASS
persistent installed session create                PASS
fresh-process session status/inspect                PASS
one governed coding execution with receipts        FAIL
```

Decisive runtime evidence:

```text
command_hash: A2B146E0501F096D870E2ED15A4331366FB954E8F137D7CD980EC97E2FBAE7B4
installed lbe code exit: 0
outcome: INSUFFICIENT_EVIDENCE
task status: blocked
response.read_only: true
provider stage: planning
provider approved_tools: workspace.read
marker: R7_CODE_PROVIDER_AUTHORITY_READ_ONLY=PROVEN
```

Expected composition:

```text
installed lbe code
 -> CLI transport
 -> persisted SessionMemoryRuntimeBridge identity
 -> GovernedAgentGateway
 -> provider reasoning/tool proposal
 -> R6C authorization_resolver
 -> R6E GovernedToolOrchestrator
 -> registered tool handler
 -> ToolReceipt
 -> receipt-backed provider continuation
 -> persistent task/checkpoint state
 -> CodingCompletionRuntime / deterministic validation
```

Observed composition:

```text
installed lbe code
 -> CLI transport
 -> persisted SessionMemoryRuntimeBridge
 -> GovernedAgentGateway
 -> LBERequestController
 -> read-only planning / deterministic inspection / explanation
 -> approved_tools = [workspace.read]
 -> read_only response
 -> R6E coding execution/receipt path not reached
```

Later R7 observables are stopped because they cannot compensate for the missing required coding execution path.

Canonical R7 records:

```text
docs/acceptance/R7_INSTALLED_END_TO_END_ACCEPTANCE_GATE.md
docs/acceptance/R7_INSTALLED_END_TO_END_ACCEPTANCE_CHECKPOINT.md
```

## 6. Current owner map after full plan re-review

### 6.1 CLI

`lbe_guard_inspector/cli.py`

Owns argument parsing and transport into existing owners. It must remain thin and must not become a tool executor, authorization resolver, provider authority, or completion gate.

### 6.2 Persistent runtime/session

`lbe_guard_inspector/session_memory_runtime.py`

Owns persistent session identity, task lifecycle, recovery/checkpoint state, and invocation of the reasoning controller. It does not currently own governed tool dispatch.

### 6.3 Reasoning/gateway

`lbe_guard_inspector/agent_integration.py`

`GovernedAgentGateway` validates persisted identity/mode and currently routes `reasoning.inspect` into the reasoning controller. It can build an R6E `ToolRequest`, but the installed `code` path does not presently execute a provider tool loop through an R6E orchestrator.

### 6.4 Reasoning controller

`lbe_guard_inspector/request_controller.py`

Owns bounded reasoning, evidence selection, deterministic guard inspection, explanation, and optional proposal generation. Its current provider tool contract is read-only (`workspace.read`). This is not a coding execution owner.

### 6.5 Authorization

`lbe_guard_inspector/runtime/authorization_resolver.py`

Accepted R6C owner. Reuse; do not duplicate or move authorization into provider/CLI code.

### 6.6 Governed tool execution

`lbe_guard_inspector/runtime/tool_orchestration.py`

Accepted R6E owner. Owns registered tool lookup, argument validation, R6C authorization, handler invocation, `ToolReceipt`, and operation-id idempotency. Reuse; do not create another dispatcher.

### 6.7 Provider continuation

`lbe_guard_inspector/provider_continuation.py`

Consumes an already-governed `ToolReceipt` and sends a receipt-backed continuation. It deliberately owns no execution authority.

### 6.8 Completion

`lbe_guard_inspector/runtime/completion_runtime.py` plus accepted completion evidence/gate owners.

Terminal completion remains evidence-owned and must not move into provider prose or CLI logic.

## 7. Defect classification

Current classification:

```text
failure class: INTEGRATION / COMPOSITION
location: installed normal coding path
proven earliest incorrect boundary:
  provider reasoning contract on lbe code receives only workspace.read
  and returns read_only before R6E coding execution/receipt is reached
```

This classification does **not** yet prove the exact function that should be edited.

Evidence classes:

```text
PROVEN
- installed lbe code reaches GovernedAgentGateway / reasoning controller
- provider receives approved_tools=[workspace.read]
- response is read_only
- existing R6C/R6E/provider-continuation owners exist independently
- no governed coding receipt is reached on observable 3

SUPPORTED
- repair should be a composition/wiring correction using existing owners

HYPOTHESIS
- an existing provider tool-call loop/composition surface is missing or not wired into the installed code route

UNKNOWN
- exact minimal edit surface until all ToolRequest/ToolReceipt/provider-turn consumers and registrations are traced
```

## 8. Required bounded repair investigation before implementation

No implementation is authorized by the failed R7 gate itself.

The next engineering slice must first be an investigation-only gate with one question:

> What existing active-owner seam should connect installed `lbe code` / `GovernedAgentGateway` reasoning to the already accepted R6C/R6E governed tool execution and receipt-continuation path, and what is the smallest correction that restores the composition without creating parallel authority?

### Investigation sequence

```text
1. lock target identity/revision and retain the R7 reproduction
2. trace cli._run_mode_command -> GovernedAgentGateway -> reasoning controller
3. enumerate every current ToolRequest / GovernedToolOrchestrator / ToolReceipt construction and consumer
4. enumerate provider tool-call and continuation implementations, including provider-turn runtimes
5. trace persistence/correlation requirements for session/task/request/tool-call/operation IDs
6. identify earliest missing or incorrect composition state
7. compare with accepted R6E/R6F contracts and tests
8. state one bounded repair hypothesis
9. state a falsifier that would disprove that hypothesis
10. only then activate a separate implementation slice
```

### Investigation completion predicate

The repair investigation is complete only when all of the following are proven:

```text
- exact current producer of provider tool requests identified
- exact intended consumer/executor identified
- exact receipt continuation seam identified
- exact persistence/correlation owner identified
- no already-active alternate coding path was missed
- smallest edit surface identified
- no new authority is required
- focused regression and installed runtime acceptance plan defined before editing
```

## 9. Repair constraints

Any later implementation slice must:

```text
reuse SessionMemoryRuntimeBridge
reuse R6C authorization_resolver
reuse R6E GovernedToolOrchestrator / ToolRegistry / ToolReceipt
reuse receipt-backed provider continuation
reuse CodingCompletionRuntime
preserve provider-neutral architecture
preserve operation-id idempotency
preserve workspace/mode/policy identity
preserve read-only audit/investigation behavior
```

Forbidden repair patterns:

```text
second tool dispatcher
second authorization resolver
provider-direct filesystem/process writes
CLI-owned execution
provider-owned completion truth
new session store
new provider authority
new receipt type that bypasses ToolReceipt
hardcoded provider-specific coding authority outside accepted adapters
architecture rewrite before proving the missing seam
```

## 10. Planned implementation sequence — provisional until repair investigation closes

The following is **not yet authorized implementation**. It is the expected evidence-driven sequence once the owner is proven:

```text
A. add/adjust focused contract test reproducing the missing installed/gateway composition
B. make the smallest change in the proven active composition owner
C. wire existing R6E registry/orchestrator into the provider tool-call path
D. convert the resulting ToolReceipt through existing provider continuation
E. preserve correlation IDs and persisted task lifecycle
F. preserve audit/investigation read-only routes
G. run focused R6C/R6E/gateway/provider-continuation/completion regressions
H. run duplicate-authority scan
I. build/install exact repair head into clean isolated environment
J. rerun R7 observable 3 and require a real governed execution receipt
K. only after observable 3 PASS continue R7 observables 4-15
```

If investigation disproves any step or reveals an already-correct alternate owner, revise this sequence before editing.

## 11. R7 rerun acceptance after repair

Observable 3 must prove all of the following on the installed path:

```text
provider proposes/requests one bounded coding action
LBE constructs the registered governed ToolRequest
authorization is resolved by R6C
R6E executes or fail-closes the action
ToolReceipt is produced with operation/tool/auth/result correlation
provider continuation consumes that receipt
no direct provider workspace mutation occurs
fresh installed process can inspect persisted task/session consequence
```

Only then continue:

```text
4. provider/model switch preserves LBE identity/policy
5. fresh-process resume preserves same session/task
6. external workspace change is re-observed/revalidated
7. audit/investigation remains read-only
8. out-of-authority request fail-closes without mutation
9. receipt/provider continuation correlation persists
10. provider completion remains provisional
11. validated terminal completion persists fresh-process
12. secret/state leakage exclusion
13. focused installed/runtime regression
14. source/diff discipline
15. clean worktree + exact limitations
```

## 12. Release/package readiness

**Classification: `BLOCKED_BY_R7`.**

Release/package readiness cannot activate until repaired R7 returns PASS. Publication remains blocked.

After R7 PASS, release/package readiness must separately prove package contents, exact installed identity, secret/state exclusion, supported runtime/environment assumptions, regression results, release metadata, and clean publication inputs.

## 13. Evidence-reconciled progression

```text
R3 PASS
 -> R4 PASS
 -> R5 PASS
 -> R6A PASS
 -> R6B PASS
 -> R6C PASS
 -> R6D PASS
 -> R6E PASS
 -> R6F PASS
 -> CLI normal-path PASS
 -> R7 installed E2E FAIL on coding composition
 -> activate bounded composition-repair INVESTIGATION
 -> prove exact owner/seam + falsifier
 -> activate bounded repair IMPLEMENTATION
 -> focused/integration/runtime validation
 -> rebuild/install exact repair head
 -> rerun R7 observable 3
 -> finish remaining R7 observables
 -> R7 PASS
 -> release/package readiness acceptance
 -> version/tag/publish
```

## 14. Final invariant

```text
Provider reasons and proposes.
Persistent runtime preserves session/task state.
LBE owns authorization and execution.
Installed CLI exposes existing authority but does not own or bypass it.
R6E ToolReceipt is the governed execution evidence boundary.
Provider continuation consumes receipts but never grants execution authority.
Validation proves.
Completion truth belongs to LBE.
Release claims require installed/runtime/package evidence, not lower-layer inference.
```

## 15. Documentation reconciliation & proposed agent-agency architecture review

This section records the architectural lesson and the proposed future correction. It does
**not** change current machine-gate state and does **not** activate any new gate.

### CURRENT MACHINE STATE (authoritative)

See the banner at the top of this file and the machine gate:

```text
phase: R7_INSTALLED_END_TO_END_ACCEPTANCE
slice: OBSERVABLE_13_INSTALLED_RUNTIME_REGRESSION
status: OPEN
observables 1-12: PASS (observable 3 PASS_AFTER_REPAIR)
observable 13: OPEN (current active slice)
implementation_allowed: false
architecture_changes_allowed: false
next_phase_locked: true
```

### HISTORICAL FAILURE (preserved, not current state)

The earlier observable-3 installed coding-composition failure (installed `lbe code` reached
`GovernedAgentGateway` → `LBERequestController` with `approved_tools=[workspace.read]` and
`read_only=true`, never reaching the accepted R6E governed coding path) is **historical
evidence**. It was addressed by the recorded repair investigation and observable 3 is recorded
`PASS_AFTER_REPAIR`. Any "R7 FAIL / repair not yet activated" lines in the body above are
historical records, not current machine-gate state.

### ARCHITECTURAL LESSON

> **The reasoning controller became the agent.**

`LBERequestController` and the fixed `ReasoningPlan` workflow evolved from a bounded read-only
inspection mechanism into the central cognitive path:

```text
provider = constrained planner / explainer
LBE     = reasoning workflow engine
```

The intended architecture is:

```text
reasoning agent
    ↓ uses
LBE governed capabilities
```

Corrected invariant:

> **LBE governs an agent's capabilities and consequences; it does not prescribe the agent's
> reasoning procedure.**

Ownership boundary:

```text
Agent / provider owns:
- reasoning
- investigation strategy
- hypothesis formation
- capability / tool selection
- replanning after results
- interpretation
- communication

LBE owns:
- workspace / session identity
- mode / policy
- authorization
- capability boundaries
- governed execution
- operation identity
- ToolReceipt
- evidence provenance
- persistence
- deterministic validation / completion truth
```

### WHAT WAS BUILT / WHAT WAS INTENDED / WHAT MUST CHANGE

| Item | WAS BUILT | WAS INTENDED | MUST CHANGE |
|------|-----------|--------------|-------------|
| Mandatory `ReasoningPlan` | provider must emit a fixed plan structure each turn | optional structured output for planning/inspection | make optional; main agent may operate without it |
| Reasoning contract | `workspace.read`-only; LBE builds evidence, asks plan, selects/runs guard, asks explanation | provider freely chooses among registered capabilities | expose capabilities the agent may invoke; do not encode the sequence |
| Guard selection | driven by LBE workflow | one available capability | `LBERequestController` -> bounded/specialist investigation capability (`guard.inspect`) |
| Deterministic Guard Inspector | correct deterministic mechanism | same | REPOSITION, not discarded |
| R6C authorization | correct deterministic authorization | same | NOT a mistake; remains authoritative execution boundary |
| R6E governed tool orchestration | correct deterministic execution | same | NOT a mistake; remains authoritative execution boundary |
| ToolReceipt | correct execution-evidence boundary | same | NOT a mistake; remains the execution evidence boundary |
| Provider continuation | correct receipt-backed continuation | same | NOT a mistake; remains receipt-backed |
| Persistent session/task state | correct LBE-owned persistence | same | NOT a mistake; remains LBE-owned |
| Completion validation | correct LBE-owned deterministic truth | same | NOT a mistake; remains LBE-owned |

Deterministic guards, authorization, receipts, persistence, and completion evidence are
**not mistakes**. The mistake is their placement around the reasoning agent — the controller
became the agent instead of the agent using governed capabilities.

### PROPOSED FUTURE CORRECTION (proposed follow-on review, not an active gate)

Reposition rather than discard:

```text
LBERequestController    -> bounded/specialist investigation capability
ReasoningPlan           -> optional structured contract for planning/inspection
Guard Inspector         -> deterministic capability available to an agent
R6C / R6E / ToolReceipt -> remain the authoritative governed-execution boundary
memory / context        -> resources supplied to reasoning, not replacements for reasoning
```

Future architecture acceptance question (recorded as a proposed follow-on review):

> Can a reasoning agent independently choose among registered LBE capabilities, perform
> multiple reasoning/tool turns, revise its approach from receipts/evidence, and complete
> work without LBE prescribing a fixed cognitive workflow, while all mutation, authorization,
> identity, persistence, receipts, and completion authority remain governed by LBE?

Primary record: `docs/design/AGENT_AGENCY_LBE_AUTHORITY_SEPARATION.md`.
