
LBE Cline Governed Node STDIO Implementation Gate

Status: OPEN — FOUNDATION IMPLEMENTATION ONLY — NEXT SLICE LOCKED

Active slice
phase: LBE_CLINE_GOVERNED_NODE_STDIO_IMPLEMENTATION
slice: IMPLEMENT_GOVERNED_NODE_STDIO_BRIDGE_FOUNDATION
base_sha: e0a7c87abbeacb478541dce68de655b483a63f32
required_evidence_level: INTEGRATION
Authority

This slice implements the architecture checkpointed PASS in:

docs/acceptance/LBE_CLINE_GOVERNED_NODE_STDIO_ARCHITECTURE_GATE.md

Existing owners remain authoritative:

resolve_authorization() — authorization decision;

GovernedToolOrchestrator.invoke() — registered tool execution and receipts;

ToolReceipt / operation_id — execution identity and idempotency;

provider_turn_runtime.py — Python provider-turn/cancellation ownership;

existing LBE session/history/evidence/validation/completion owners.

The Node worker is a mechanics host, not an authority owner.

Required implementation

Define lbe-cline-stdio/1 frame validation and typed message vocabulary.

Implement a Python-owned bounded child-process adapter:

spawn exact worker;

dedicated stdin/stdout JSONL protocol;

stderr diagnostics only;

startup handshake;

timeout/shutdown/termination;

fail closed on malformed/unknown/duplicate frames or child exit.

Add a minimal Node worker bootstrap using Cline AgentRuntime mechanics.

Pin the exact Cline dependency line and Node engine requirement; generate a deterministic lock.

Worker tool exposure must be allowlist-only. Native Cline editor/filesystem/apply-patch/shell/terminal/process mutation surfaces must not be registered or reachable.

Preserve identity:
cline_tool_call_id -> lbe_call_id -> operation_id -> receipt_id.

A tool proposal must return to Python before any executable action. Python remains responsible for authorization and orchestration.

No automatic executable replay after worker restart.

Focused proof required

At minimum:

protocol valid-frame PASS
unknown protocol/message FAIL CLOSED
malformed frame FAIL CLOSED
duplicate message_id FAIL CLOSED
worker startup/ready PASS
worker shutdown PASS
child-exit active-turn FAIL CLOSED
native mutating tools absent/unreachable
tool proposal returns to Python before execution
operation/call correlation preserved
existing Python authorization/orchestrator tests remain PASS

If live Cline continuation cannot yet be proven without expanding beyond this foundation, record it as UNVERIFIED and stop; do not fake continuation proof.

Package/runtime proof required
Python >=3.11 remains canonical package/runtime
Node >=22 requirement declared for worker
@cline/agents exact version pinned
transitive lock generated
Apache-2.0 package license recorded
no credential value appears in argv, source, logs, receipts, or committed files

Security/dependency audit and installed-path launch evidence must be captured before this implementation slice may be classified PASS.

Non-goals

no ClineCore wholesale adoption;

no second session store;

no second authorization resolver;

no second tool dispatcher;

no TUI redesign;

no MCP implementation;

no provider-selection expansion;

no release-ready claim.

Stop rule

After the bounded foundation is implemented and validated, write the checkpoint and stop. Do not automatically expand into full provider continuation or UI integration.