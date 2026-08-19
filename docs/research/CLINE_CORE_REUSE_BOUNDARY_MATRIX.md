# Cline Core Reuse Boundary Matrix

Status: **SOURCE AUDIT COMPLETE — LOCAL VALIDATION PENDING**

Cline repository: `cline/cline`

Audited Cline revision:

```text
8bbdde2a5c1f972864fe1b954f639c21fac61a40
```

LBE audit activation revision:

```text
31df367edcb9fc709ab99b5ce73a00fb3c13ae5a
```

Required classification: `REUSE | ADAPT | REJECT | UNVERIFIED`.

No row is classified from README claims alone. The decisions below are based on current Cline source/API references at the exact revision above plus the already-recorded LBE authority contract. `REUSE` means mechanics may be consumed behind an LBE-owned boundary; it never transfers LBE authorization, evidence, validation, completion, workspace, or canonical session authority.

## Evidence routing used

- GitHub: canonical Cline and LBE source/revision truth.
- Local LBE proof already recorded before this audit: `main == origin/main == 31df367...`, clean worktree, machine gate PASS.
- BirdEye remains the required local evidence/governed-execution route for later implementation or live local verification.
- Runtime-specific proof is deferred to a later implementation slice when behavior cannot be proven statically.

## Matrix

| Capability | Cline package/subsystem | Exact Cline revision | Source path / symbol | Observed behavior | Existing LBE owner | Authority / bypass impact | Decision | Evidence / reason | Follow-up proof |
|---|---|---|---|---|---|---|---|---|---|
| Provider adapters | `@cline/llms` gateway/provider layer | `8bbdde2a...` | `sdk/packages/llms/src/providers/*`; `sdk/packages/agents/src/agent-runtime.ts::resolveRuntimeConfig()` | Provider/model IDs are resolved through `createGateway()` and produce an `AgentModel`; provider implementations normalize provider streams into shared model events. | existing provider/reasoning adapters | Provider transport mechanics are reusable, but LBE must retain normalized product-event, evidence, capability and authorization truth. | ADAPT | Cline already solves provider transport/gateway construction, but direct adoption would otherwise let Cline become provider/runtime authority. | Compatibility test for selected providers/models behind an LBE adapter. |
| Provider/model capability metadata + probes | `@cline/shared` model catalog + provider discovery | `8bbdde2a...` | `sdk/packages/shared/src/llms/model-info.ts::{ModelCapabilitySchema,modelHasCapability,modelSupportsToolCalling}` | Capability metadata includes tools, streaming, reasoning, files, computer-use, modalities, context window and operation. Missing/empty capability lists intentionally carry no signal; tool calling can assume true when unspecified. | LBE capability projection/resolver | Useful metadata, but its fail-open/unspecified semantics cannot be the deterministic LBE capability authority. | ADAPT | Source explicitly treats absent capability lists as ambiguous and `modelSupportsToolCalling()` assumes true when unspecified. | LBE capability overlay/probe contract must remain authoritative. |
| Provider-native streaming | `@cline/agents` + `@cline/llms` | `8bbdde2a...` | `sdk/packages/agents/src/agent-runtime.ts::{generateAssistantMessage,openTaskLifecycleStream}` | Agent runtime consumes an async provider stream and emits text/reasoning/tool/usage/finish events with provider error classification and lifecycle telemetry. | LBE normalized provider event/history owners | Rich stream mechanics are reusable; event shapes still require LBE normalization, sequencing and provenance. | ADAPT | Cline exposes native deltas and tool activity before final assistant message assembly. | Event-mapping integration test against LBE event vocabulary. |
| Tool-call parsing + continuation | `@cline/agents` AgentRuntime | `8bbdde2a...` | `sdk/packages/agents/src/agent-runtime.ts::{execute,generateAssistantMessage,executeToolCalls}` | Model tool calls are assembled, executed, converted to tool-result messages, appended to history, then the loop returns to the provider until no tool calls remain. | provider turn/runtime continuation owners | Continuation mechanics can be reused if tool execution is redirected through LBE and returned as normal tool-result messages. | REUSE | The loop already performs the exact model → tool → result → next-model iteration needed; no separate continuation engine is required. | Prove an LBE-governed custom tool result re-enters the same loop once. |
| Tool interception before mutation | `@cline/agents` hooks + tool policies | `8bbdde2a...` | `sdk/packages/agents/src/agent-runtime.ts::{prepareToolExecution,executePreparedTool}` | `beforeTool` hooks run before policy/approval and before `tool.execute()`. Hooks may change input, stop or skip; policies can disable tools or require approval. | R6C authorization resolver + governed tool dispatcher | There is a viable pre-execution interception point, but it must be wired to existing LBE authorization and fail closed. | ADAPT | Source proves the ordering: hook/policy/approval precede `tool.execute()`. | Integration test: denied LBE action never reaches executor; allowed action executes exactly once. |
| Filesystem/editor mutation | ClineCore built-ins | `8bbdde2a...` | Cline SDK built-ins: `editor`, `apply_patch`, file tools; tool policy/configuration surfaces | Native Cline editor/patch tools can mutate the workspace under Cline's own tool execution path. | LBE governed workspace tools | Direct native reuse would create a second mutation authority unless those tools are disabled/replaced. | REJECT | Strict LBE governance cannot claim exclusivity while overlapping native Cline mutation tools remain executable. | Next adapter must register only LBE-governed mutation tools or prove native mutation paths disabled. |
| Shell/terminal/process execution | ClineCore shell + VS Code terminal integrations | `8bbdde2a...` | `apps/vscode/src/sdk/vscode-run-commands-tool.ts`; ClineCore built-in shell executor | Cline supports child-process/background execution and IDE terminal execution, including detach/proceed-while-running behavior. | LBE governed execution/process owners | Direct reuse would bypass LBE command authorization/receipts/process identity. | REJECT | Mature process mechanics exist, but raw native execution cannot be canonical under strict LBE authority. | Replace/adapter path must route argv through LBE governed execution and preserve process events. |
| Session persistence | `@cline/core` RuntimeHost/SessionRuntime | `8bbdde2a...` | `sdk/packages/core/src/ClineCore.ts`; `sdk/packages/core/src/runtime/host/local-runtime-host.ts`; `session-runtime-orchestrator.ts` | ClineCore owns persistent session records/messages, per-session runtime state, run/continue/abort lifecycle, usage and resume behavior. | LBE canonical Session/Turn/Item persistence | Persistence mechanics can inform/reuse storage plumbing, but Cline cannot become canonical session authority without conflicting with LBE IDs/evidence/checkpoints. | ADAPT | Source shows a complete session runtime, but LBE already declares canonical session/task ownership. | Define ID/projection boundary; prove no duplicate canonical session truth. |
| Checkpoint/undo | `@cline/core` checkpoint services | `8bbdde2a...` | `sdk/packages/core/src/session/checkpoint-diff.ts`; checkpoint restore/history services | Cline uses Git-backed checkpoint refs/stash-shaped snapshots, compares checkpoint content to workspace, and supports restore-oriented APIs. | LBE checkpoint/recovery + validation/evidence policy | Snapshot/diff mechanics are useful but are not LBE validation or completion truth. | ADAPT | Source proves workspace snapshot/diff mechanics and path containment checks, not LBE evidence semantics. | Map checkpoint mechanics to LBE checkpoint identity/evidence without replacing validation authority. |
| Runtime/model event stream | `@cline/agents`, `@cline/core`, `@cline/shared` | `8bbdde2a...` | AgentRuntime events; `RuntimeEventAdapter`; `CoreSessionEvent` projection | Cline has multiple event layers: AgentRuntimeEvent → AgentEvent → CoreSessionEvent; text, reasoning, tool lifecycle, usage, status and terminal events are available, while some lower-layer events are suppressed in projections. | LBE normalized event/history owners | Strong reusable event source, but LBE must normalize one canonical vocabulary and retain provenance/sequence semantics. | ADAPT | Multiple event layers are explicitly documented/implemented and have different shapes. | Deterministic mapping test including suppressed/error/tool events. |
| Cancellation | `@cline/agents` + SessionRuntime | `8bbdde2a...` | AgentRuntime AbortController/abort flow; `SessionRuntime` active runtime abort forwarding | Active runs carry an AbortSignal into model/tool execution and can be aborted; session runtime tracks abort request/reason. | `persistent_turn_control.py`, `provider_turn_runtime.py`, transport capability boundary | Useful cancellation propagation, but LBE's truthful per-transport capability contract remains authoritative; aborting a Cline run is not proof of provider transport cancellation. | ADAPT | Cline abort semantics are broader runtime cancellation; P16 already established LBE's explicit supported/unsupported transport truth. | Adapter test: LBE accepted cancel forwards only when transport capability permits; no late projection. |
| Interrupt / steering | ClineCore pending prompts + turn/session orchestration | `8bbdde2a...` | `local-runtime-host.ts::PendingPromptsController`; `session-runtime-orchestrator.ts`; AgentRuntime pending user-message preparation | Cline supports queued/pending prompts and continued runs, providing mechanics for in-session follow-up/steering. | LBE control protocol / persistent turn control | Mechanics are reusable, but LBE semantics distinguish follow-up, active steering, interrupt and cancel and must remain canonical. | ADAPT | Cline has queue/continue surfaces but not the exact LBE control-state contract. | Control-protocol mapping tests for follow-up vs steer vs interrupt vs cancel. |
| MCP | ClineCore extensions/MCP tool contribution | `8bbdde2a...` | Cline SDK extension/config discovery and MCP tool integration surfaces | MCP tools can appear alongside built-in/custom tools and enter the same agent tool loop. | future LBE MCP client/projection surface + governed dispatcher | MCP is reusable as an external tool transport but does not disable native Cline mutation tools or replace LBE authorization. | ADAPT | Tool contribution architecture supports MCP, but strict governance still depends on exclusive LBE dispatch. | MCP call must traverse LBE authorization/evidence path in integration test. |
| CLI/TUI | Cline CLI / OpenTUI client | `8bbdde2a...` | `apps/cli/src/main.ts`, ACP/session update projection, OpenTUI skill/client components | Cline has mature interactive/headless client machinery consuming runtime/session events. | LBE client/projection layer only | Presentation mechanics are reusable, but commands/state must project LBE runtime truth and never become authority. | ADAPT | Client layer is mature but product semantics/branding/control protocol differ. | Only evaluate after runtime/control/event contracts are stable. |
| Background processes | SDK shell executor + VS Code terminal process integration | `8bbdde2a...` | `apps/vscode/src/sdk/vscode-run-commands-tool.ts::{executeForeground,...}` and SDK shell executor | Supports foreground terminals, background child processes, streaming output, abort/detach and long-running commands. | LBE professional terminal/process capability | Valuable mechanics, but direct execution is outside LBE receipts/authorization/process identity. | ADAPT | Process control can be reused behind an LBE execution adapter; direct native shell remains rejected above. | LBE process IDs/events/receipts must wrap the executor. |
| Context/compaction | `@cline/agents` prepareTurn + `@cline/core` compaction | `8bbdde2a...` | `agent-runtime.ts::{generateAssistantMessageWithOverflowRecovery,prepareTurnForModelRequest}`; `local-runtime-host.ts` compaction wiring | Cline detects context overflow, invokes prepareTurn/compaction, retries once, emits status, and persists compaction state. | LBE context/checkpoint/session truth | Compaction mechanics are useful, but summaries/compacted history cannot replace authoritative LBE evidence/current workspace truth. | ADAPT | Source explicitly separates compaction from provider retry and treats token budgeting as a runtime concern. | Verify LBE evidence/current state is rehydrated independently of compacted narrative. |

## Cross-cutting findings

### 1. Cline already has the professional agent loop

Do **not** rebuild a second generic model/tool continuation engine. `AgentRuntime.execute()` already performs iterative provider calls, tool execution, result insertion and continuation.

### 2. Strict LBE governance is possible only with an adapter boundary

Cline provides a pre-execution `beforeTool` hook and custom tool surface. This creates a viable integration point for LBE. But strict governance is false if Cline's native `editor`, patch, shell, web or other overlapping mutating/external tools remain independently executable.

Therefore the safe adoption shape is:

```text
Cline AgentRuntime mechanics
        ↓
LBE-owned adapter
        ↓
existing LBE resolve_authorization()/governed dispatcher
        ↓
LBE tool/process/workspace owners
        ↓
result returned as Cline tool-result
        ↓
existing Cline continuation loop
```

### 3. Cline capability metadata is evidence, not LBE authority

The current Cline model schema is substantially richer than the old `@cline/llms@0.0.73` evaluation, but current source intentionally allows unspecified capability lists and fail-open assumptions. LBE therefore still needs its own deterministic capability truth/probe contract.

### 4. ClineCore is too authoritative to adopt wholesale

ClineCore already owns sessions, persistence, built-in tools, workspace resolution, checkpoints, event projection and automation. Wholesale adoption would duplicate or displace LBE owners. Reuse must therefore be selective and adapter-based.

## Required audit conclusion

```text
FIRST_GENUINELY_MISSING_DEPENDENCY:
  LBE-to-Cline AgentRuntime governance adapter that registers/routes only LBE-governed executable tools,
  maps pre-execution authorization to existing LBE authority, returns governed tool results into the
  existing Cline continuation loop, and projects Cline runtime events into LBE's canonical event contract.

CLASSIFICATION:
  ADAPT

EXISTING_LBE_OWNER:
  existing R6C/deterministic authorization resolver + governed tool dispatcher + provider turn/runtime
  continuation/event owners; no new authority owner is justified.

CLINE_REUSE_DECISION:
  Reuse Cline AgentRuntime continuation/event/tool mechanics; reject direct native mutation/execution
  tools as canonical LBE execution paths; adapt through the existing LBE owners.

WHY:
  This is the minimal boundary required before any deeper Cline runtime reuse can be safe. Without it,
  native Cline tools can execute outside LBE authority. With it, Cline can remain the mature agent-loop
  mechanics while LBE remains the deterministic authority.

REQUIRED_EVIDENCE_LEVEL_FOR_NEXT_SLICE:
  INTEGRATION — prove deny-before-execute, allow-exactly-once, tool-result continuation, event mapping,
  native mutating-tool disablement, and no duplicate session/authorization authority.
```

## Audit result

All required capability families are classified from exact Cline source. No required row remains `UNVERIFIED` at the source-audit level.

This does **not** authorize implementation. The active slice remains locked until the checkpoint receives local validation (`check-implementation-gate.py`, `git diff --check`, clean changed-file proof) and is explicitly classified PASS.
