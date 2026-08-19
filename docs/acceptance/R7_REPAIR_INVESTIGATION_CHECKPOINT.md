# R7 Installed Coding Composition Repair Investigation Checkpoint

```text
phase: R7_REPAIR_INVESTIGATION
slice: TRACE_INSTALLED_CODE_TO_EXISTING_GOVERNED_EXECUTION
status: PASS
base_sha: 677cb96471aaead50b30312aa16eeea04caa8084
investigation_head: 0eed3c8a4c9d6eb8407da639fef086b610a279a4
implementation_sha: NOT_APPLICABLE_INVESTIGATION_ONLY
required_evidence_level: SOURCE_PLUS_RUNTIME_CORRELATION
next_phase_locked: true
implementation_allowed: false
architecture_changes_allowed: false
```

## Trigger evidence

```text
R7 observable 3: FAIL
installed code response.read_only: true
provider approved_tools: workspace.read
governed coding ToolReceipt path reached: no
runtime command hash: A2B146E0501F096D870E2ED15A4331366FB954E8F137D7CD980EC97E2FBAE7B4
```

## Investigation validation evidence

Repository-wide structural discriminator:

```text
command hash: 81684E672EE2A77C49B634D79DF4CBAB84531A613328EC9488434B75BFE6BD2D
head: 0eed3c8a4c9d6eb8407da639fef086b610a279a4
origin/main: 0eed3c8a4c9d6eb8407da639fef086b610a279a4
worktree clean: PASS
machine phase: R7_REPAIR_INVESTIGATION
machine status before closure: OPEN
implementation_allowed: false
scan result: PASS
```

The scan enumerated production `GovernedClineWorker`, `GovernedToolOrchestrator`, `ToolRequest`, receipt-continuation, `ToolSpec`, mutation-tool identifiers, and CLI/server coding routes.

## Proven active producer / consumer chain

### Installed `lbe code` path

```text
cli._run_mode_command
 -> build_provider_controller
 -> GovernedAgentGateway
 -> AgentRequestEnvelope(operation_id=reasoning.inspect)
 -> GovernedAgentGateway.invoke
 -> CodingCompletionRuntime.run_reasoning
 -> SessionMemoryRuntimeBridge.run_reasoning
 -> LBERequestController
```

This path does not construct or invoke `GovernedClineWorker`, `ToolRegistry`, or `GovernedToolOrchestrator`.

### Existing governed Cline/R6E path

```text
Cline AgentRuntime
 -> tool.proposed
 -> GovernedClineWorker._mediate_tool_proposal
 -> ToolRequest
 -> GovernedToolOrchestrator.invoke
 -> R6C resolve_authorization
 -> registered handler when allowed
 -> ToolReceipt
 -> typed tool.result carrying cline_tool_call_id / lbe_call_id / operation_id / receipt_id
 -> same Cline AgentRuntime continuation
```

This path already exists in production source and is independently accepted by the prior governed Cline provider-continuation integration checkpoint.

### Correlation ownership

The bridge/protocol owns provider-turn correlation fields:

```text
session_id
turn_id
cline_tool_call_id
lbe_call_id
operation_id
receipt_id
```

`memory/operational_history.py` can persist provider tool-call ID, LBE call ID, runtime operation ID, and tool receipt ID. Therefore no new correlation authority is required.

## Structural scan conclusions

### Alternate active coding path

```text
result: NOT FOUND
```

Repository scan found no production caller constructing `GovernedClineWorker` or calling `execute_turn()` outside the bridge implementation itself.

### R6E orchestrator production composition

```text
result: NOT FOUND outside GovernedClineWorker mediation
```

No installed CLI/server coding route constructs an R6E `ToolRegistry` + `GovernedToolOrchestrator` execution loop.

### Production coding mutation capability

```text
result: NOT FOUND
```

Within `lbe_guard_inspector`, the only concrete production `ToolSpec` found by the mutation/tool scan is `workspace.read`. No production `workspace.write`, edit, patch, shell, process, apply-patch, file-write, or equivalent coding mutation capability was found.

Test-only handler/spec construction does not establish a production capability.

## Exact defect classification

The failed R7 observable is not one isolated CLI branch bug. The investigation proves two adjacent composition gaps:

```text
GAP 1 — normal-path provider/tool execution composition
installed lbe code / GovernedAgentGateway
    X
existing GovernedClineWorker -> R6E -> ToolReceipt -> same-provider continuation loop

GAP 2 — concrete production coding mutation capability
existing generic R6E ToolRegistry / GovernedToolOrchestrator
    X
production registered write/edit/patch capability
```

Both gaps must be addressed without creating new authorization, dispatch, session, provider, receipt, evidence, or completion authorities.

## Earliest missing composition state

The earliest proven mismatch is the installed coding entry path selecting the read-only `reasoning.inspect` / `LBERequestController` flow instead of composing the already-existing governed provider tool-turn runtime.

Even after that seam is corrected, R7 coding acceptance would still remain unsatisfied unless at least one bounded production coding mutation capability is registered behind R6C/R6E.

## Existing-owner decision

```text
decision: REUSE / EXTEND EXISTING AUTHORITIES

retain:
- SessionMemoryRuntimeBridge for persistent session/task/checkpoint ownership
- GovernedAgentGateway for external request identity/mode boundary
- R6C authorization_resolver for authorization
- R6E ToolRegistry / GovernedToolOrchestrator / ToolReceipt for execution and receipt authority
- GovernedClineWorker and pinned Cline AgentRuntime for provider/tool continuation mechanics
- operational history for correlation persistence
- CodingCompletionRuntime and existing completion evidence/gate owners
```

No second dispatcher, authorization resolver, session store, provider authority, receipt owner, or completion gate is justified.

## Smallest bounded repair surface

The repair implementation should be limited to existing-owner composition and one concrete governed coding capability.

Expected edit surface, subject to implementation-gate confirmation:

```text
1. existing installed coding runtime/gateway composition surface
   - compose provider-backed coding turn through GovernedClineWorker
   - construct existing ToolRegistry / GovernedToolOrchestrator
   - preserve SessionMemoryRuntimeBridge identity and CodingCompletionRuntime lifecycle

2. runtime/tool_orchestration.py or a directly owned adjacent runtime module
   - add one bounded production workspace mutation ToolSpec/handler
   - handler must remain workspace-scoped and receipt-producing through existing R6E
   - no direct provider mutation

3. focused existing-owner tests
   - normal coding provider tool proposal reaches R6C/R6E
   - allowed mutation executes exactly once and yields ToolReceipt
   - denied/escalated mutation does not execute
   - tool.result correlation returns to same Cline continuation
   - completion remains provisional until deterministic validation

4. installed R7 observable 3 rerun
```

This is a composition repair, not an architecture replacement.

## Repair hypothesis

```text
H1:
If the normal installed coding path composes the existing GovernedClineWorker with an existing R6E ToolRegistry/GovernedToolOrchestrator, and that registry contains one bounded production workspace mutation tool whose handler is controlled by R6C/R6E, then a provider tool proposal will execute only through LBE authority, emit a correlated ToolReceipt, continue through the same provider turn, and leave completion under existing deterministic validation authority.
```

## Repair falsifier

H1 is falsified if any of the following occurs after the bounded repair:

```text
- installed `lbe code` still terminates in read-only reasoning without reaching GovernedClineWorker/R6E
- provider can mutate workspace without a ToolReceipt
- mutation executes outside R6C authorization
- no concrete production mutation tool is available to coding mode
- denied/escalated mutation executes a handler
- operation/tool-call/receipt correlation is lost across continuation
- a second session/provider/dispatcher/authorization/completion authority is introduced
- provider completion is treated as terminal completion without existing deterministic validation
```

## Validation contract for implementation

Evidence ladder:

```text
1. source owner/diff review
2. focused ToolSpec/handler authorization tests
3. focused gateway/runtime composition test
4. real Cline local-provider tool-call integration
5. deny/escalate/failure/idempotency regression
6. completion authority regression
7. isolated wheel build/install with PYTHONPATH removed
8. installed R7 observable 3: real governed coding mutation + correlated receipt + continuation
9. clean project worktree / exact-head proof
```

The installed acceptance must prove an actual governed coding effect in the isolated R7 workspace. Merely exposing a write tool or seeing it in a provider request is insufficient.

## Remaining unverified

```text
- implementation correctness: not attempted
- exact final production mutation tool shape/arguments: must be chosen in implementation gate from smallest safe workspace-bound contract
- repaired installed runtime behavior: not attempted
- later R7 observables 4+: remain blocked until observable 3 passes
- release/package readiness: blocked
```

## Document conflicts

```text
none within this closed investigation after machine/human gate reconciliation
```

## Completion decision

```text
investigation_status: PASS
exact missing seams: PROVEN
alternate active coding path: DISPROVEN
production mutation tool registration: NOT PRESENT
smallest authority-preserving repair class: PROVEN
repair hypothesis: RECORDED
repair falsifier: RECORDED
validation contract: RECORDED
implementation authorized: NO
next phase auto-activated: NO
```

The investigation is complete. Stop here until a separate bounded repair implementation gate is explicitly activated.
