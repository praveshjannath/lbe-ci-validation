# Professional Agent Runtime — Canonical Implementation Plan

Status: **AUTHORITATIVE FORWARD IMPLEMENTATION PLAN — ACTIVE**
Updated: 2026-08-13

This document is the independent GitHub-grounded implementation plan for the professional LBE agent runtime.

It is not derived from any single local-agent plan. Local-agent plans, runtime traces, provider experiments, and future reviews are comparison inputs against this plan. If either this plan or a local-agent plan misses a requirement, the stronger evidence-backed requirement is incorporated here before implementation proceeds.

This plan must be read with:

- `docs/design/PROFESSIONAL_AGENT_RUNTIME_PRODUCT_PILLAR.md`
- `docs/design/PROFESSIONAL_AGENT_RUNTIME_P0_P1_IMPLEMENTATION_GATE.md`
- `docs/design/PROFESSIONAL_AGENT_RUNTIME_P0_P1_PROVIDER_MAPPING_AND_AUTHORIZATION_CORRECTIONS.md`
- `docs/research/POST_V1_PROFESSIONAL_AGENT_CLI_PROVIDER_RUNTIME_RESEARCH.md`
- `docs/design/LBE_AGENT_RUNTIME_CLI_TUI_AND_TOOL_ACCESS_SPEC.md`
- `docs/design/LBE_AGENT_RUNTIME_USER_STEERING_EXTERNAL_CLIENT_AND_CONTROL_PROTOCOL_ADDENDUM.md`

Where an older implementation sequence conflicts with this plan, reconcile the documentation first.

---

## 1. Product objective

Build one persistent professional agent runtime that can support:

- hosted first-party providers;
- routed/OpenAI-compatible providers;
- local models;
- professional workspace/code/Git/terminal workflows;
- live user steering;
- long-running and interactive processes;
- deterministic LBE authorization;
- durable evidence/validation/completion;
- replay/resume/fork;
- first-party CLI/TUI/IDE/GUI clients;
- external-agent capability access through MCP;
- truthful cooperative versus strict external-agent governance.

The visible CLI/TUI is a client over this runtime. It is not the runtime owner.

---

## 2. Existing owners that must remain authoritative

Current source evidence on `feat/c5-governed-coding-execution` establishes these owners.

### Provider registry

`lbe_guard_inspector/provider_registry.py`

Current responsibility:

- explicit provider factory registration;
- provider/model descriptor construction;
- transport/model metadata;
- no workspace authority.

The current `ProviderCapabilities` shape is intentionally minimal and all built-in providers currently advertise `streaming=False` and `tool_calls=False`. The professional capability model must evolve without turning provider metadata into workspace authorization.

### Current provider transport

`lbe_guard_inspector/reasoning_provider.py`

Current responsibility:

- synchronous JSON request/response transport;
- bounded structured planning/explanation contract;
- provider transport errors.

It does not currently provide native incremental streaming, PTY/process streaming, or a professional tool-continuation loop.

### First-party bounded adapters

`lbe_guard_inspector/first_party_reasoning_provider.py`

Current responsibility:

- translate Anthropic/Gemini request/response envelopes into the existing bounded reasoning contract;
- no policy/tool/session ownership.

These accepted adapters are foundation and compatibility surfaces. The professional streaming/interactive path must be introduced with a clear migration/evolution boundary rather than silently changing their accepted semantics.

### Tool orchestration

`lbe_guard_inspector/runtime/tool_orchestration.py`

Current responsibility:

- registered tool lookup;
- argument validation;
- R6C authorization;
- bounded handler invocation;
- operation-id idempotency;
- structured receipts/evidence.

The professional tool layer must extend this owner rather than create a second dispatcher.

### Authorization

`lbe_guard_inspector/runtime/authorization_resolver.py`

Current responsibility:

- deterministic `ALLOW | DENY | ESCALATE` based on active delegated authority, scope, destructive authority, persistent-policy authority, and conflicts.

P1 does not invent a new approval model. Effective capability availability consumes this owner.

### Session/workspace persistence

`lbe_guard_inspector/session_memory_runtime.py` plus existing memory store/adapter owners.

Current responsibility:

- project workspace identity;
- canonical workspace root;
- session mode/permission/runtime policy;
- provider/model identity;
- task lifecycle;
- checkpoint/recovery integration.

Professional turn/item/event persistence must attach to this authoritative session/workspace identity. No second `EventRecorder` history database is allowed.

---

## 3. Architectural dependency graph

```text
P0 Provider Event Normalization Contract
        |
        v
P1 Professional Runtime Capability Contract
        |
        v
P2 Provider/Model Capability Discovery + Negotiation
        |
        v
P3 Provider-Native Streaming + Tool-Call Adapters
        |
        v
P4 Persistent Session / Turn / Item / Event Substrate
        |
        v
P5 Professional Capability Backends
   workspace/code + Git + terminal/process + validation
        |
        v
P6 Live Tool / Process Event Production
        |
        v
P7 Governed Provider Continuation Loop
        |
        v
P8 Bidirectional Agent-Control Protocol
        |
        v
P9 Replay / Resume / Fork / Recovery Proof
        |
        v
P10 MCP External-Agent Surface
        |
        v
P11 Transcript Projection / Non-Interactive Client
        |
        v
P12 Professional Interactive CLI/TUI
        |
        v
P13 IDE Bridge / Rich Client Integration
        |
        v
P14 Browser Capability Integration
        |
        v
P15 Cooperative + Strict External-Agent Acceptance
        |
        v
P16 Professional End-to-End Acceptance
```

No later phase may be used to bypass an unresolved earlier contract.

---

## 4. P0 — Provider Event Normalization Contract

### Goal

Define normalized provider/model semantics before any generic Session/Turn/Item persistence implementation.

### Required provider protocol families

Initial contract must distinguish at least:

```text
openai_responses
anthropic_messages
gemini_interactions
gemini_generate_content
openai_compatible_chat
```

Additional endpoint/model families may be added when proven necessary.

### Required normalized model semantics

The exact final class layout remains implementation-deferred, but the contract must support at least:

```text
model.turn.started
model.message.delta
model.message.completed
model.reasoning_summary.delta
model.reasoning_summary.completed
model.tool_call.started
model.tool_call.arguments.delta
model.tool_call.completed
model.usage.updated
model.turn.requires_tool
model.turn.requires_continuation
model.turn.completed
model.turn.incomplete
model.turn.refused
model.cancelled
model.error
```

### Event-domain boundary

Provider/model events never represent LBE tool execution.

Correct flow:

```text
model.tool_call.completed
        -> deterministic LBE authorization
        -> tool.started
        -> tool.output/progress if truly supported
        -> tool.completed | tool.failed | tool.cancelled | tool.denied | tool.escalated
        -> provider-specific continuation serialization
        -> next model events
```

There is no `model.tool_call.result` emitted by LBE runtime execution.

### Identity

Preserve separately:

```text
provider_request_id
provider-native item/step/block ID
provider-native tool/function call ID
lbe_call_id
runtime operation_id / tool receipt identity
```

`lbe_call_id` is durable across approval wait, tool execution, replay, reconnect, provider continuation, and evidence correlation.

### Provider diagnostic/state metadata

Preserve provider-native information without coupling clients to raw wire payloads:

```text
provider_id
model_id
provider_protocol_family
provider_event_type
provider_stop_reason
provider_request_id
continuation_ref
provider_state_metadata_ref
raw_diagnostic_ref
```

Provider continuation state is not automatically user-visible reasoning.

### OpenAI requirements

The mapping must use real Responses lifecycle semantics, including:

```text
response.output_item.added/done
response.function_call_arguments.delta/done
response.output_text.delta/done
response.reasoning_summary_part.* lifecycle
response.reasoning_summary_text.delta/done
response.incomplete
refusal lifecycle
response.failed / error distinction
```

Do not invent a `response.output_tool_call` protocol.

### Anthropic requirements

Preserve:

```text
message_start
content_block_start/delta/stop
message_delta
message_stop
tool_use
partial tool-input JSON
end_turn
max_tokens
refusal
pause_turn
```

Distinguish:

```text
tool_use -> LBE/client tool execution required
pause_turn -> provider/server-side continuation required
```

### Gemini requirements

Do not merge Interactions and GenerateContent.

Interactions:

```text
interaction.* lifecycle
step.start / step.delta / step.stop
thought
function_call
model_output
interaction.requires_action
```

GenerateContent:

```text
streamed GenerateContentResponse
text parts
functionCall parts
finishReason
thoughtSignature/provider continuation metadata
```

Do not manufacture argument deltas if GenerateContent supplies a complete function call.

Thought signatures/encrypted continuation state must be preserved independently from user-visible reasoning summaries.

### OpenAI-compatible/local/routed requirements

Treat compatibility as transport syntax, not capability truth.

Capability must be determined by:

```text
provider/endpoint + selected model + enabled features + observed/probed behavior
```

Unknown capability remains unknown until evidence establishes it.

### P0 acceptance

P0 passes only when:

- every supported initial protocol family has a primary-source-backed native-to-normalized mapping;
- provider-native and runtime event domains are cleanly separated;
- continuation state is explicitly represented;
- no fabricated stream/tool/reasoning capability exists;
- provider-native tool identity can be correlated with durable LBE call identity;
- terminal states preserve source attribution where provider-native equivalence differs.

---

## 5. P1 — Professional Runtime Capability Contract

### Goal

Define technical support, current-session runtime availability, and provider projection separately.

### Layer A — ProviderModelCapabilities

Describes what `provider + endpoint + model + feature configuration` can express reliably.

Minimum dimensions:

```text
protocol_family
streaming_text
streaming_reasoning_summary
reasoning_visibility
client_tool_calls
server_tool_calls
parallel_tool_calls
streamed_tool_arguments
strict_tool_schema
tool_choice_modes
structured_output
native_mcp
server_side_state
previous_response_or_interaction_state
context_window
max_output_tokens
image_input
file_input
cache_controls
usage_reporting
cancellation
provider_request_id
retryable_error_signals
```

Use:

```text
CapabilitySupport = SUPPORTED | UNSUPPORTED | CONDITIONAL | UNKNOWN
```

Conditional support requires a reason/condition source.

### Layer B — RuntimeCapabilities

Describes real LBE/back-end operations independent of model/provider ability.

A runtime capability descriptor must carry at least:

```text
capability_id
family
backend_id
backend_version
support
support_reason
workspace_binding
mode_requirements
mutation_class
external_effect_class
supports_streaming
supports_interactive
supports_background
supports_cancellation
supports_parallelism
input_schema
output_schema
evidence_types
validation_types
```

### Layer C — EffectiveSessionCapabilities

Current runtime availability is derived from:

```text
runtime backend support
+ workspace binding/backend health
+ active mode capability eligibility
+ existing R6C authorization semantics
```

Use:

```text
EffectiveAvailability = AVAILABLE | GATED | UNAVAILABLE | CONDITIONAL | UNKNOWN
```

R6C mapping conceptually:

```text
ALLOW -> AVAILABLE
DENY -> UNAVAILABLE / denied
ESCALATE -> GATED
```

Do not introduce `write_allowed -> always approval required`.

### Provider projection

Provider projection is a separate state from runtime availability.

Use a typed projection concept such as:

```text
ProviderProjection = EXPOSED | HIDDEN | CONDITIONAL
```

Example:

```text
workspace.read
runtime_availability = AVAILABLE
provider_projection = HIDDEN
reason = selected model cannot emit client tool calls
```

Provider outage or lack of tool-calling support hides projection; it does not erase direct-user/runtime capability support.

### Projection resolution

Conceptually:

```text
ProviderModelCapabilities
+ provider endpoint/model health
+ runtime EffectiveAvailability
+ projection policy
    -> ProviderProjection
    -> provider-visible tool schemas
```

The model sees only the authorized, truthfully projectable subset.

### P1 acceptance

P1 passes only when:

- support and availability are different types;
- runtime availability and provider projection are different state dimensions;
- R6C remains the authorization owner;
- workspace binding is explicit;
- backend provenance is explicit;
- streaming/interactivity/background/cancellation claims require real backend evidence;
- provider inability cannot erase direct runtime capabilities;
- the effective provider-visible schema set is deterministically reproducible.

---

## 6. P2 — Capability discovery and negotiation

### Goal

Implement truthful capability discovery without granting authority.

### Required behavior

Resolve capability evidence in this order:

```text
explicit provider/model metadata
-> current primary API/model declarations where available
-> endpoint/model feature configuration
-> deterministic local capability probes where safe and appropriate
-> UNKNOWN if still unproven
```

Do not infer tool/streaming capability from provider brand alone.

### Output

Produce a `ProviderModelCapabilities` snapshot attached to the active provider/model session identity.

### Acceptance

- changing model can change provider/model capabilities without changing LBE workspace authority;
- unknown remains unknown;
- local/routed endpoints can report different capabilities under the same transport family;
- provider switch recomputes projection but does not rewrite runtime capability ownership.

---

## 7. P3 — Provider-native streaming and tool-call adapters

### Goal

Introduce a professional provider path without breaking the accepted bounded 0.2.1 reasoning path.

### Design rule

Do not blindly replace `OpenAICompatibleReasoningBackend._complete()` or the first-party bounded adapters.

**Default implementation strategy:** before independently implementing any
provider transport, streaming parser, tool-call grammar, retry mechanism, or
context-management path, complete the `@cline/llms` compatibility decision
artifact required by
`PROFESSIONAL_AGENT_RUNTIME_CLINE_REUSE_DIRECTION.md`. The pinned Cline lower
layer is evaluated first; native LBE transport is a documented fallback, not
the default assumption.

At implementation time classify each current owner as:

```text
reuse unchanged
extend with compatible interface
wrap with new streaming adapter
retain as bounded compatibility path
replace only with migration proof
```

### Required output

Each professional adapter emits normalized P0 events and accepts provider-continuation input produced after LBE tool execution.

### Acceptance

- real incremental model text is observable where supported;
- tool-call argument streaming is preserved where supported;
- complete one-shot tool calls remain complete without fabricated deltas;
- cancellation behavior is provider-correct;
- bounded 0.2.1 path remains regression-tested.

P3 cannot proceed from implementation presence alone. Its decision artifact
must record the exact Cline package/source pin, event-fidelity result,
cancellation result, identity-correlation result, dependency/license result,
authority-boundary result, and a per-provider decision of `REUSE`, `PARTIAL
REUSE`, or `NATIVE`.

---

## 8. P4 — Persistent Session / Turn / Item / Event substrate

### Goal

Persist normalized operational history under the existing authoritative session/workspace owner.

### Required hierarchy

```text
Session
  -> Turn
      -> ordered Items
          -> lifecycle/runtime events
```

### Required properties

- monotonic ordering per session/turn;
- durable IDs;
- replayable final state;
- mutable in-flight presentation derived from events;
- finalized immutable outcomes;
- provider-native diagnostic references retained separately;
- no second independent event history database.

### Persistence rule

Extend or compose with the existing memory/session store only after inspecting the current schema in the implementation slice.

JSONL is an export/projection, not authority.

---

## 9. P5 — Professional capability backends

Implement professional typed backends progressively.

### Workspace/code

```text
workspace.read
workspace.search
workspace.glob
workspace.inspect
workspace.diff
workspace.replace_text
workspace.apply_patch
workspace.symbols
workspace.definition
workspace.references
workspace.diagnostics
```

Semantic capabilities are exposed only when an LSP/IDE/parser/project backend proves them.

### Git

```text
git.status
git.diff
git.log
git.show
git.branch
git.remote
git.blame
git.worktree.list
```

Governed mutations later include stage/commit/branch/worktree operations. Push/PR/release/publish remain separate external-effect capabilities.

### Terminal/process

Distinguish:

```text
terminal.exec
terminal.session.*       # PTY/ConPTY interactive
terminal.background.*    # long-lived process
```

Do not model all terminal work as one synchronous command tool.

### Validation/evidence/session capabilities

Preserve existing owners; expose typed capability descriptors over them.

---

## 10. P6 — Live execution events

### Goal

Produce truthful runtime events from real asynchronous/streaming backends.

Required terminal/process semantics:

```text
command.started
command.stdout.delta
command.stderr.delta
command.progress
command.completed
command.failed
command.cancelled
```

A synchronous `subprocess.run()` backend cannot claim live deltas.

Tool lifecycle:

```text
tool.started
tool.output.delta
tool.progress
tool.completed
tool.failed
tool.cancelled
tool.denied
tool.escalated
```

Events originate from existing runtime owners or their explicit backend extensions.

---

## 11. P7 — Governed provider continuation loop

### Goal

Turn one provider response into a persistent professional agent loop.

**Default implementation strategy:** evaluate the pinned `@cline/agents`
continuation loop only after P3's `@cline/llms` decision. It may be reused only
when every tool proposal is intercepted before mutation, all execution remains
with `GovernedToolOrchestrator`, and the exact LBE receipt/evidence result can
be serialized back to the provider. Otherwise retain the same adapter boundary
and implement continuation in LBE.

Canonical loop:

```text
provider/model event stream
-> normalized tool proposal
-> effective capability/projection check
-> R6C authorization
-> governed tool execution
-> runtime/evidence result
-> provider-specific continuation serialization
-> next provider turn
-> validation/completion evaluation
```

Stop/continue decisions must distinguish:

- client tool required;
- provider/server continuation required;
- approval/escalation required;
- user steering received;
- interrupt;
- cancel;
- terminal completion;
- unsupported capability;
- credential/manual blocker.

P7 cannot adopt an agent layer unless its decision artifact records `PASS` or
`FAIL` for pre-mutation interception, LBE-result-to-continuation correlation,
cancellation propagation, durable identity preservation, no-second-authority,
and dependency/license review. The only allowed decisions are `REUSE`,
`PARTIAL REUSE`, or `NATIVE`; a failed gate must select a lower Cline layer or
native LBE, never a bypass.

---

## 12. P8 — Bidirectional agent-control protocol

### Goal

Expose one runtime control surface to first-party clients.

Required operations include:

```text
initialize
session.create
session.resume
session.read
session.fork
turn.start
turn.steer
turn.interrupt
turn.cancel
approval.respond
provider.list/select
model.select
capabilities.list
permissions.read/update-if-authorized
events.subscribe
events.replay
validation.get
evidence.get
```

First transport may be stdio with versioned JSONL/JSON-RPC-like framing.

MCP is not a substitute for this protocol.

---

## 13. P9 — replay/resume/fork proof

Prove that:

- the same authoritative session can reconnect after process/client restart;
- provider/model state required for continuation is retained or explicitly unavailable;
- turn/item histories replay deterministically;
- checkpoint/compaction does not become workspace truth;
- fork creates explicit state lineage rather than hidden mutation of the original session.

---

## 14. P10 — MCP external-agent surface

Expose selected LBE capabilities to external agents.

Maintain two claims:

```text
COOPERATIVE ATTACHMENT
LBE governs only LBE-routed operations.

STRICT ATTACHMENT
Overlapping native external-agent mutation paths are disabled/restricted/sandboxed/routed through LBE.
```

Never claim whole-agent governance merely because MCP is connected.

---

## 15. P11/P12 — transcript and TUI

Only after runtime replay/control is proven:

### Transcript projection

Render the real ordered runtime:

```text
user message
agent commentary
active tool invocation
live output
edit/diff
failure
agent reaction
validation
completion
```

### TUI

The primary surface is the agent session, not a telemetry dashboard.

Composer remains usable for steering when safe.

Secondary views may include:

```text
/diff
/git
/validation
/processes
/tools
/provider
/context
/evidence
/checkpoints
/mcp
/logs
```

---

## 16. P13–P16 professional expansion and acceptance

### IDE bridge

Editor-native selection/open-files/diagnostics/symbol/diff capabilities without duplicating runtime authority.

### Browser

Advertise browser capabilities only with a real backend and observed rendered outcomes.

### External-agent acceptance

Prove cooperative and strict attachment separately.

### End-to-end professional acceptance

A clean installed consumer must complete representative professional workflows including:

- repository identity establishment;
- multi-file code understanding/change;
- long-running validation with live output;
- user steering during execution;
- failure recovery;
- provider/model switch without workspace-authority drift;
- session resume/replay;
- Git/worktree workflow;
- evidence-bound completion.

---

## 17. Cross-plan comparison protocol

When a local agent, external reviewer, or another model produces a plan, do not accept or reject it wholesale.

Compare it against this canonical plan in a requirement matrix.

For every proposed requirement classify:

```text
MATCH
CANONICAL_PLAN_MISSING
LOCAL_PLAN_MISSING
CONFLICT
UNPROVEN
OBSOLETE
```

Then apply these rules:

1. Current source/runtime evidence outranks both plans.
2. Current primary provider/API evidence outranks remembered provider behavior.
3. Existing accepted LBE authority owners are preserved unless implementation evidence proves a necessary migration.
4. A new useful requirement missing here is added here before coding.
5. A local-agent requirement that conflicts with authority, provider truth, or runtime evidence is rejected or corrected.
6. No implementation begins from an unresolved `CONFLICT` or critical `UNPROVEN` item.
7. Comparison never changes accepted historical foundations unless a real regression is demonstrated.

This makes the repository plan the durable integration point while still allowing other agents to improve it.

---

## 18. Immediate next action

The next work is **final P0/P1 contract freeze**, not P2 implementation.

Before P2 begins, produce one final P0/P1 acceptance record containing:

- exact provider-native mapping tables for the initial protocol families;
- normalized P0 event semantics;
- continuation-state semantics;
- `CapabilitySupport` contract;
- `RuntimeCapability` descriptor contract;
- `EffectiveAvailability` contract;
- `ProviderProjection` contract;
- deterministic resolution flow using existing R6C authorization;
- acceptance fixtures/tests to be implemented in P2/P3;
- explicit unresolved provider/API questions, if any.

P2 begins only when that record has no critical unresolved mapping or authority conflicts.

## Final invariant

> **The canonical plan lives in GitHub and is continuously reconciled against current source, provider truth, runtime evidence, and independent-agent reviews. No single agent is the source of architectural truth. LBE authority remains deterministic; provider behavior remains provider-specific; clients remain projections over one persistent professional runtime.**
