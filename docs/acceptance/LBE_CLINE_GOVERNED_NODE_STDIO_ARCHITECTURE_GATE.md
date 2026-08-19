
LBE Cline Governed Node STDIO Architecture Gate

Status: PASS - ARCHITECTURE BOUNDED - PRODUCTION IMPLEMENTATION REQUIRES SEPARATE SLICE

Active phase
phase: LBE_CLINE_GOVERNED_NODE_STDIO_ARCHITECTURE
slice: DEFINE_GOVERNED_NODE_SUBPROCESS_STDIO_BOUNDARY
base_sha: 726f6b776dfa82778c2a4b400a84adb9c91cb078
Authorization

The user explicitly authorized continuing with the existing Cline reuse study rather than rebuilding mechanics already proven reusable.

Authorized architecture candidate:

GOVERNED_NODE_SUBPROCESS_STDIO

No other architecture candidate is authorized by this slice.

Why this slice exists

The completed Cline source audit proved that Cline AgentRuntime already owns mature reusable mechanics for:

model -> tool -> result -> continuation;

tool-call parsing and continuation;

pre-tool interception through beforeTool;

provider-native streaming/event mechanics;

cancellation and queued/continued turn mechanics.

The subsequent interop checkpoint classified direct in-process reuse as:

NEW_ARCHITECTURE_REQUIRED

because canonical LBE is Python-owned while audited Cline AgentRuntime is TypeScript/Node and no existing canonical Python-to-Node runtime boundary exists.

This slice therefore defines the smallest new boundary required to consume those mechanics without creating a second authority.

Existing authority owners that must remain authoritative
authorization:
  lbe_guard_inspector/runtime/authorization_resolver.py::resolve_authorization


governed tool execution and receipts:
  lbe_guard_inspector/runtime/tool_orchestration.py::GovernedToolOrchestrator


provider-turn ownership:
  lbe_guard_inspector/provider_turn_runtime.py


canonical session/history/evidence:
  existing LBE session, operational-history, receipt, validation and completion owners


process lifecycle:
  LBE/Python parent process

The Node worker is never an authority owner.

Architecture contract
Python LBE runtime - authoritative parent
        |
        | strict typed stdin/stdout protocol
        v
bounded Node child worker
        |
        v
Cline AgentRuntime mechanics
        |
        | tool proposal only
        v
Python LBE resolve_authorization
        |
        v
GovernedToolOrchestrator
        |
        | ToolReceipt + governed result
        v
Node worker / Cline AgentRuntime
        |
        v
existing Cline continuation loop
Required invariants

Python LBE owns child-process start, stop, timeout, restart policy and termination.

Node may propose a tool call but may never execute LBE workspace/process mutations directly.

Every executable proposal crosses resolve_authorization() before any executor.

Every allowed execution crosses GovernedToolOrchestrator.

Every tool result returned to Cline is correlated to the canonical LBE operation_id and ToolReceipt.

Native Cline editor, apply-patch, filesystem mutation, shell, terminal, process and equivalent direct mutation/execution surfaces are disabled, omitted, or unreachable.

Cline session/runtime IDs are correlation IDs only; canonical session/turn/history identity remains LBE-owned.

Node stdout is protocol-only. Diagnostic output must not corrupt the protocol channel.

Malformed protocol, unknown message types, duplicate request IDs, child exit, timeout, or identity mismatch fail closed.

Node never decides LBE validation, evidence sufficiency, approval, completion or release readiness.

Protocol direction
Python -> Node

The design must define typed envelopes for at least:

runtime.start
turn.execute
tool.result
control.cancel
control.steer
runtime.shutdown
Node -> Python

The design must define typed envelopes for at least:

runtime.ready
provider.event
tool.proposed
turn.completed
turn.failed
runtime.error

Every envelope must have:

protocol_version
message_id
session_id
turn_id
message_type

Tool-related envelopes additionally require:

cline_tool_call_id
lbe_call_id
operation_id
receipt_id when produced
Fail-closed tool flow
Cline tool proposal
    -> Python receives typed proposal
    -> map proposal identity
    -> resolve_authorization()
    -> denied/escalated => no executor call
    -> allowed => GovernedToolOrchestrator.invoke() exactly once
    -> persist/project ToolReceipt through existing LBE owners
    -> return governed result to Cline
    -> Cline continuation resumes
Explicitly rejected designs in this slice
LONG_LIVED_NODE_SIDECAR_RPC
EMBEDDED_JS_RUNTIME
ClineCore wholesale runtime/session adoption
second authorization resolver
second tool dispatcher
second canonical session/history store
native Cline filesystem/editor/shell/process authority
Node-owned validation/completion truth
Required design proof

Before this slice may become PASS, repository evidence must establish:

existing LBE owner call paths for authorization, orchestration, receipt identity, provider continuation and session/history;

exact Cline AgentRuntime integration symbols reused from the audited revision;

a complete typed protocol and identity map;

a native-tool disablement strategy;

fail-closed process/protocol lifecycle rules;

package/runtime/license/security evidence required by the next implementation slice;

implementation test plan proving deny-before-execute, allow-exactly-once, receipt-backed continuation, event mapping, cancellation/error attribution and no duplicate authority;

implementation-gate validator PASS;

git diff --check PASS.

Required evidence level
ARCHITECTURE / SOURCE

No runtime integration claim is permitted from this slice.

PASS meaning

PASS means the governed subprocess/stdio architecture is sufficiently bounded that one later production implementation slice can be activated without inventing additional authority or protocol semantics during coding.

PASS does not authorize production implementation automatically.

After PASS, stop and activate a separate implementation slice.

Non-goals

This slice does not:

add Node or Cline packages;

create a Node worker;

change Python runtime code;

enable native Cline tools;

change provider selection;

change TUI behavior;

add MCP;

change canonical session persistence;

claim installed/live/user-flow/release readiness.

## Architecture proof checkpoint
phase: LBE_CLINE_GOVERNED_NODE_STDIO_ARCHITECTURE
slice: DEFINE_GOVERNED_NODE_SUBPROCESS_STDIO_BOUNDARY
base_sha: 726f6b776dfa82778c2a4b400a84adb9c91cb078
activation_sha: b0a9df6bc718ea1c680465e053bd94b0efaf109c
reuse_decision: ADAPT Cline AgentRuntime mechanics behind one LBE-owned governed subprocess/stdio boundary
new_authority_owner_introduced: no
required_evidence_level: ARCHITECTURE / SOURCE
Proven source boundary

resolve_authorization() remains decision-only and returns ALLOW / DENY / ESCALATE before execution.

GovernedToolOrchestrator.invoke() remains the governed tool execution boundary.

operation_id is idempotent: repeated invocation returns the prior receipt.

ToolReceipt provides durable receipt_id, operation identity, status, authorization result, output/evidence and failure metadata.

denied/escalated requests return before handler execution.

provider_turn_runtime.py remains the Python provider-turn/cancellation owner.

existing LBE session/history/evidence/validation/completion owners remain canonical.

Pinned Cline boundary
revision: 8bbdde2a5c1f972864fe1b954f639c21fac61a40
package: @cline/agents
version: 0.0.75
module: ESM
node: >=22
license: Apache-2.0
dependencies: @cline/llms, @cline/shared, nanoid

Reuse symbols:

AgentRuntime / createAgentRuntime
AgentRuntime.execute()
generateAssistantMessage()
executeToolCalls()
prepareToolExecution()
executePreparedTool()
beforeTool
AgentRuntimeEvent
AbortController / abort propagation
Protocol
protocol_version: lbe-cline-stdio/1
framing: newline-delimited UTF-8 JSON
stdout: protocol only
stderr: diagnostics only

Every message requires:

protocol_version
message_id
message_type
session_id
turn_id

Python -> Node:

runtime.start
turn.execute
tool.result
control.cancel
control.steer
runtime.shutdown

Node -> Python:

runtime.ready
provider.event
tool.proposed
turn.completed
turn.failed
runtime.error

Tool identity:

cline_tool_call_id -> lbe_call_id -> operation_id -> receipt_id

A conflicting or missing identity fails closed.

Native Cline tool exclusion

The Node worker must receive an allowlisted tool set derived only from LBE-governed tool definitions.

Native Cline editor, apply-patch, filesystem mutation, shell, terminal and process execution surfaces must be absent or unreachable. Policy denial alone is insufficient if an independent native executor remains reachable.

Fail-closed lifecycle

Python owns child spawn, pipes, startup timeout, turn timeout, cancellation forwarding, shutdown, forced termination and restart policy.

Fail closed on:

child exit during active turn
startup timeout
turn timeout
malformed JSON/frame
unknown protocol version
unknown message type
duplicate message_id
identity mismatch
unexpected tool-result correlation
non-protocol stdout

Worker restart must never replay an executable proposal whose operation_id already has a persisted receipt.

Production implementation adoption gate

The later implementation slice must prove:

Node >=22 on installed path
exact @cline/agents pin and transitive lock
license inventory
dependency/security audit
worker packaging/install path
installed worker launch path
Windows process behavior
credentials absent from argv/logs/receipts
provider credential transport/storage contract
Required implementation tests
deny-before-execute
escalation-before-execute
allow-exactly-once
operation-id idempotency
receipt-backed continuation into same Cline loop
call -> operation -> receipt correlation
forbidden native tools absent/unreachable
deterministic Cline -> LBE event mapping
truthful cancellation forwarding
child crash fail-closed
malformed protocol fail-closed
restart without duplicate execution
Node cannot mutate outside LBE orchestrator
installed LBE launches exact worker
Checkpoint
phase: LBE_CLINE_GOVERNED_NODE_STDIO_ARCHITECTURE
slice: DEFINE_GOVERNED_NODE_SUBPROCESS_STDIO_BOUNDARY
base_sha: 726f6b776dfa82778c2a4b400a84adb9c91cb078
implementation_sha: b0a9df6bc718ea1c680465e053bd94b0efaf109c
requirements: bounded Python-owned Node subprocess/stdio architecture; typed protocol; identity law; native mutation exclusion; fail-closed lifecycle; adoption proof requirements; implementation test contract
existing_owner: resolve_authorization; GovernedToolOrchestrator; ToolReceipt; provider_turn_runtime; existing LBE session/history/evidence/validation/completion owners
reuse_decision: ADAPT Cline AgentRuntime continuation/event/tool mechanics; reject Cline native execution authority
required_evidence_level: ARCHITECTURE / SOURCE
validation_evidence: exact LBE owners inspected; exact Cline revision/package/symbols pinned; protocol and failure law defined; gate validator PASS; git diff --check PASS
unverified: production worker/adapter, installed Node/Cline path, live continuation, event mapping, cancellation integration, dependency/security adoption; intentionally deferred
document_conflicts: none known
status: PASS
project_user_ready: UNVERIFIED
release_ready: UNVERIFIED
next_phase_locked: true
