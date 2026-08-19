# LBE ↔ Cline AgentRuntime Interop Boundary Gate

Status: **OPEN — BOUNDARY PROOF ONLY — NEXT IMPLEMENTATION PHASE LOCKED**

## Active phase

```text
phase: LBE_CLINE_AGENTRUNTIME_GOVERNANCE_ADAPTER
slice: PROVE_INTEROP_AND_PREEXECUTION_AUTHORITY_BOUNDARY
```

## Why this slice exists

The completed Cline reuse audit proved that Cline's `@cline/agents` AgentRuntime already provides a mature model → tool-call → tool-result → provider-continuation loop and exposes a `beforeTool` interception point before `tool.execute()`.

The canonical LBE repository, however, is currently a Python 3.11+ package with no `package.json` and no declared Node/Cline runtime dependency. Therefore **direct reuse of the TypeScript Cline AgentRuntime is not yet an implementation-ready fact**. A cross-language/runtime boundary must be proven before production adapter code is authorized.

This slice prevents the project from silently inventing a sidecar, subprocess protocol, embedded Node runtime, second session authority, or Python rewrite and calling it "Cline reuse".

## Exact base

Activation base:

```text
ea246b154e00882ac4e29d14f4e244a9e08c2b21
```

Cline source revision already audited:

```text
cline/cline
8bbdde2a5c1f972864fe1b954f639c21fac61a40
```

## Existing owners

### LBE deterministic authorization

```text
lbe_guard_inspector/runtime/authorization_resolver.py
  AuthorizationRequest
  AuthorizationDecision
  AuthorizationVerdict
  resolve_authorization()
```

`resolve_authorization()` remains the R6C authority. This slice may not introduce another authorization engine.

### LBE governed tool execution

```text
lbe_guard_inspector/runtime/tool_orchestration.py
  ToolRegistry
  ToolRequest
  ToolExecutionContext
  ToolReceipt
  GovernedToolOrchestrator.invoke()
```

`GovernedToolOrchestrator` already owns registered-tool lookup, R6C authorization, bounded handler invocation, receipt identity/status, and operation-id idempotency. This slice may not create another canonical tool executor.

### LBE provider-turn lifecycle

```text
lbe_guard_inspector/provider_turn_runtime.py
  NonStreamingProviderTurnRuntime
  BackgroundProviderTurnRuntime
```

These remain the current LBE provider-turn owners until a later accepted migration/adaptation slice explicitly changes wiring.

### Cline mechanics under evaluation

```text
cline/cline @ 8bbdde2a5c1f972864fe1b954f639c21fac61a40
sdk/packages/agents/src/agent-runtime.ts
  AgentRuntime
  prepareToolExecution()
  executePreparedTool()
  execute()
```

Cline mechanics are reusable only behind LBE authority; they are not an authority owner.

## Mandatory questions this slice must answer

1. **Interop mechanism** — What exact mechanism can a Python LBE runtime use to consume the TypeScript Cline AgentRuntime: existing in-repo owner, package boundary, process boundary, RPC boundary, or none?
2. **No parallel runtime** — Does the mechanism create a second session/controller/evidence/authorization/completion authority?
3. **Pre-execution interception** — Can every LBE-governed Cline tool proposal reach LBE authorization before any mutating/external executor runs?
4. **Native-tool exclusion** — Can overlapping Cline filesystem/editor/shell/process tools be disabled or made unreachable so they cannot bypass LBE?
5. **Exactly-once execution** — Can one Cline tool-call identity map deterministically to one LBE operation ID and one `ToolReceipt`, preserving `GovernedToolOrchestrator` idempotency?
6. **Continuation return path** — Can a governed LBE receipt/result be converted back into the existing Cline tool-result continuation path without a second continuation engine?
7. **Event projection** — Can Cline runtime/tool/provider events be projected into existing LBE normalized/persisted event owners without becoming authoritative themselves?
8. **Cancellation/control boundary** — Can existing LBE control/cancellation truth remain authoritative rather than inheriting broader Cline semantics?
9. **Packaging/runtime prerequisite** — What exact runtime/dependency would production installation require, and is that acceptable under the current Python package/distribution model?
10. **License/security/dependency gate** — If any Cline npm package becomes a production dependency, does the exact selected package/version/revision pass a fresh adoption gate? The historical `@cline/llms@0.0.73` rejection is not silently overridden.

## Required decision vocabulary

```text
REUSE_IN_PROCESS
REUSE_GOVERNED_PROCESS_BOUNDARY
ADAPT_EXISTING_LBE_BOUNDARY
REJECT_DIRECT_REUSE
UNVERIFIED
NEW_ARCHITECTURE_REQUIRED
```

`UNVERIFIED` and `NEW_ARCHITECTURE_REQUIRED` block implementation. If `NEW_ARCHITECTURE_REQUIRED` is the truthful result, stop for explicit user authorization before changing architecture.

## Allowed work

- inspect exact current LBE source/tests/package metadata;
- inspect exact Cline source at the audited revision;
- use GitHub for canonical remote source/revision truth;
- use BirdEye for local workspace identity/diff/inspection and governed local commands;
- run non-mutating local probes needed to determine installed Node/npm/package availability;
- write/update this gate and its checkpoint;
- add a research/design decision record only if evidence requires one;
- run `python scripts/check-implementation-gate.py` and `git diff --check`.

## Not allowed in this slice

- production adapter implementation;
- adding npm/Node/Cline dependencies to the canonical product;
- adding a Node sidecar/daemon/service;
- adding a new RPC/MCP bridge as product architecture;
- rewriting Cline AgentRuntime mechanics in Python and calling it reuse;
- changing `resolve_authorization()` authority semantics;
- replacing `GovernedToolOrchestrator`;
- enabling native Cline editor/filesystem/shell/process mutation paths;
- changing canonical LBE session/evidence/validation/completion ownership;
- provider/TUI/MCP feature expansion;
- new branch/worktree;
- next-slice implementation.

## Required evidence level

This boundary slice requires **INTEGRATION-DESIGN evidence backed by current source plus local runtime/package facts**. It does not claim product integration.

Required proof:

1. canonical main/primary-worktree proof;
2. exact LBE and Cline revisions recorded;
3. current Python packaging/runtime facts recorded;
4. exact candidate interop path identified or rejected;
5. authority/bypass analysis completed;
6. exactly-once identity mapping design tied to existing LBE `operation_id`/`ToolReceipt`;
7. native Cline mutation bypass disposition recorded;
8. dependency/license/security implications recorded for any production package candidate;
9. no product/runtime implementation source changed;
10. machine gate PASS;
11. `git diff --check` PASS;
12. checkpoint classified.

## Exit conditions

### PASS

PASS means **one implementation-ready interop boundary has been proven without introducing a new authority**, and the exact next implementation slice can be bounded.

PASS does **not** authorize implementation automatically. Stop and activate a separate implementation slice.

### NEW_ARCHITECTURE_REQUIRED

If reuse requires a new Node sidecar, daemon, RPC authority, session owner, or comparable architectural surface, classify `NEW_ARCHITECTURE_REQUIRED` and stop. Architecture changes remain disabled until the user explicitly authorizes the specific design.

### REJECT_DIRECT_REUSE

If Cline AgentRuntime cannot be consumed safely under current LBE packaging/authority constraints, record the exact reason. Do not fabricate an adapter.
