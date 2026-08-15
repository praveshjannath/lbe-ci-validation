# Professional Agent Runtime — Cline Reuse Direction

Status: **AUTHORITATIVE IMPLEMENTATION DIRECTION ADDENDUM — ACTIVE**
Updated: 2026-08-13

This document updates the implementation direction for the professional LBE runtime without replacing the canonical dependency architecture in `PROFESSIONAL_AGENT_RUNTIME_CANONICAL_IMPLEMENTATION_PLAN.md`.

It must be read with:

- `docs/design/PROFESSIONAL_AGENT_RUNTIME_CANONICAL_IMPLEMENTATION_PLAN.md`
- `docs/design/PROFESSIONAL_AGENT_RUNTIME_PRODUCT_PILLAR.md`
- `docs/design/PROFESSIONAL_AGENT_RUNTIME_P0_P1_IMPLEMENTATION_GATE.md`
- `docs/design/PROFESSIONAL_AGENT_RUNTIME_P0_P1_PROVIDER_MAPPING_AND_AUTHORIZATION_CORRECTIONS.md`
- `docs/design/LBE_AGENT_RUNTIME_CLI_TUI_AND_TOOL_ACCESS_SPEC.md`
- `docs/design/LBE_AGENT_RUNTIME_USER_STEERING_EXTERNAL_CLIENT_AND_CONTROL_PROTOCOL_ADDENDUM.md`
- GPT-Knowledge `ai-agents/cline-runtime-reuse-for-governed-agent-infrastructure.md`

Where this addendum conflicts with an older assumption that LBE must independently implement every provider streaming/agent-loop layer, this addendum controls the implementation strategy. Existing accepted P0/P1/P2 contracts and existing LBE authority owners remain unchanged.

---

## 1. Non-negotiable ownership boundary

Cline is reusable infrastructure beneath LBE. It is not a competing runtime authority.

### LBE remains authoritative for

```text
workspace/project identity
canonical workspace root
session/task identity
mode and permission profile
runtime policy
ProviderModelCapabilities truth/projection
runtime capability availability
R6C authorization
registered governed tool dispatch
operation identity/idempotency
evidence provenance
validation truth
completion truth
checkpoint/recovery policy
Session / Turn / Item durable state
agent-control protocol semantics
TUI/IDE/MCP product projection
```

Existing owners remain authoritative, including:

```text
lbe_guard_inspector/runtime/authorization_resolver.py
lbe_guard_inspector/runtime/tool_orchestration.py
lbe_guard_inspector/session_memory_runtime.py
existing memory/evidence/completion owners
```

### Cline lower layers may own or assist with

```text
provider transport
provider-specific request serialization
provider-native incremental streaming
provider-specific tool-call syntax
partial tool argument handling where genuinely supported
provider continuation serialization
provider retry/error normalization
context/token management
usage events
```

A Cline package must never gain workspace mutation authority merely because it can execute tools in its standalone configuration.

All later sections inherit this boundary and do not redefine it.

---

## 2. Graduated Cline reuse strategy

Before implementing parallel provider-native streaming/tool-call plumbing from scratch, LBE must evaluate selective reuse of the current Cline SDK lower layers.

Required evaluation order:

```text
1. evaluate @cline/llms first
   -> provider transport
   -> provider-native streaming
   -> provider request/response mechanics

2. evaluate @cline/agents only if
   -> LBE still intercepts every tool proposal before mutation
   -> LBE remains the sole tool/governance authority
   -> LBE-produced tool results can drive provider continuation

3. use @cline/shared selectively
   -> types/helpers/events only where they do not leak Cline-owned public semantics

4. avoid @cline/core / full @cline/sdk as runtime authority
   -> unless a future explicit isolation/migration proof replaces an LBE owner
```

The objective is to reuse mature provider and continuation mechanics while preserving LBE's deterministic governance architecture.

---

## 3. Required adapter boundary

The integration boundary must remain explicit and replaceable.

```text
Cline provider event
        |
        v
LBE P0 normalization
        |
        v
ProviderModelCapabilities / capability projection
        |
        v
R6C deterministic authorization
        |
        v
existing GovernedToolOrchestrator
        |
        v
tool receipt + evidence + runtime events
        |
        v
provider continuation serialization
        |
        v
next Cline/provider stream
```

Equivalent product-facing architecture:

```text
                        LBE TUI / IDE / client
                                 |
                        agent-control/event API
                                 |
                    LBE Session / Turn / Item
                                 |
             capabilities + deterministic authorization
                                 |
                    existing governed tools
                                 ^
                                 |
                    normalized P0 model events
                                 |
                     Cline integration adapter
                       /                    \
              @cline/llms            @cline/agents
                 |                     optional
                 +----------+-------------+
                            |
                    provider-native APIs
```

No Cline-native event object becomes the durable LBE public event contract. The adapter is replaceable infrastructure, not a new authority layer.

---

## 4. Cline reuse checkpoints for P3 and P7

Canonical P3 remains **Provider-Native Streaming + Tool-Call Adapters**. Canonical P7 remains **Governed Provider Continuation Loop**. Cline reuse is an implementation strategy inside those phases, not a change to the dependency graph.

### P3 checkpoint — `@cline/llms`

Before building provider adapters independently:

1. Pin the exact Cline package versions under evaluation.
2. Inspect `@cline/llms` provider interfaces and stream event contract.
3. Map real Cline provider events to the frozen LBE P0 normalized event vocabulary.
4. Verify OpenAI, Anthropic, Gemini, and OpenAI-compatible paths do not require fabricated semantics.
5. Verify provider-native IDs, usage, cancellation, incomplete/error states, and continuation metadata can be retained.
6. Verify event fidelity for partial and terminal tool-call state.
7. Verify the accepted bounded Python 0.2.1 reasoning path remains untouched.

Expected result:

```text
Cline native/provider event
        -> LBE adapter
        -> normalized model.* event
```

If `@cline/llms` satisfies P0/P2 truth requirements cleanly, prefer using it rather than maintaining redundant first-party streaming transports.

If it cannot preserve a required provider semantic or imposes unsuitable runtime/dependency constraints, implement the affected provider path natively behind the same LBE adapter contract.

This decision may be per provider; one provider need not force the same backend choice for all providers.

### P7 checkpoint — `@cline/agents`

Evaluate `@cline/agents` only if the tool boundary can be intercepted before mutation.

Required flow:

```text
provider/model stream
        -> normalized LBE tool proposal
        -> EffectiveSessionCapabilities / ProviderProjection
        -> R6C authorization
        -> lbe_guard_inspector.runtime.tool_orchestration
        -> truthful tool/runtime events + evidence
        -> Cline/provider continuation input
        -> next model stream
```

Unacceptable flow:

```text
provider
   -> Cline built-in shell/editor/write tool executes
   -> LBE is informed afterward
```

That path bypasses LBE's execution authority and cannot be used for strict governance claims.

### Shared acceptance gates

P3/P7 Cline reuse is acceptable only if compatibility proof demonstrates:

```text
event fidelity
provider-native and LBE identity preservation
cancellation propagation
truthful terminal attribution
tool-call identity preservation
continuation serialization
host-provided governed tool execution
no direct filesystem/shell/Git/browser mutation outside LBE
bounded-path regression compatibility
backend replacement behind the adapter
```

If `@cline/agents` cannot use host-provided governed tool execution cleanly, LBE will reuse only `@cline/llms` and own P7 itself.

### Current decision record — 2026-08-15

This record applies only to the exact evaluated pin below. It does not make a
claim about later Cline versions.

| Gate | Evidence level | Result |
| --- | --- | --- |
| Exact `@cline/llms@0.0.73` pin | `INSTALLED` | PASS — installed sidecar and manifest match the pinned package. |
| Sidecar runtime prerequisite | `INSTALLED` | PASS — Node `v24.15.0` and isolated sidecar readiness probe passed. |
| Event mapping and identity correlation | `INTEGRATION` | PASS — compatibility and sidecar-adapter tests preserve text, tool, continuation, and correlation boundaries. |
| LBE result to continuation serialization | `INTEGRATION` | PASS — adapter regression covers exact provider/LBE receipt correlation. |
| Cancellation propagation | `LIVE_RUNTIME` | UNVERIFIED — no real provider stream has been cancelled through the sidecar. |
| Pre-mutation LBE interception | `USER_FLOW` | UNVERIFIED — no real provider tool proposal has reached `GovernedToolOrchestrator`. |
| No second authority | `INTEGRATION` | PASS for the adapter boundary; `USER_FLOW` remains UNVERIFIED. |
| Dependency and license review | `INSTALLED` | FAIL — the resolved package tree reports one high and one moderate vulnerability; package metadata did not supply a license value in the evaluated registry response. |

**Decision: `NATIVE` for production P3/P7 at this pin.** The evaluated Cline
sidecar is useful compatibility evidence, but it must not become a production
runtime dependency while the dependency-security gate fails. P7 must remain
LBE-owned unless a future exact Cline pin passes every P7 gate, including
pre-mutation interception and live cancellation.

The decision does not invalidate the Cline-first evaluation order. A later
explicitly pinned version may be evaluated through this same table before any
reuse decision changes.

---

## 5. Why not adopt ClineCore wholesale

Current Cline SDK documentation describes `ClineCore` as owning or providing:

```text
sessions
SQLite persistence
built-in tools
workspace/config discovery
RPC/multi-process support
execution-host behavior
```

Those overlap existing or planned LBE owners.

Using both as authorities would create ambiguous state for:

```text
which session is canonical
which workspace root is authoritative
which permission decision controls a write
which tool receipt proves execution
which checkpoint is resumable
which runtime decides task completion
```

Therefore:

> Do not make `ClineCore` the LBE core runtime unless a future explicit migration replaces an LBE owner with proof and updates the architecture first.

No such migration is currently planned.

---

## 6. P4/P6/P8 lessons from Cline, without authority transfer

Cline remains useful implementation evidence beyond P3/P7.

### P4 — Session / Turn / Item

Use Cline's current session/event coordination as comparative evidence for:

- rejecting stale events from non-active sessions;
- preserving authoritative turn state separately from transcript-tail inference;
- resumption after interruption;
- handling straggler events after cancel.

Do not copy Cline persistence as a second LBE history store.

### P6 — live execution events

Use Cline's streaming/event behavior as proof that client surfaces should receive incremental, typed events rather than polling a status dashboard.

LBE runtime events remain LBE-owned.

### P8 — steering/cancel/control

Use Cline's current session-event handling as comparative evidence for separate states such as running, resumable, completed, awaiting follow-up, and error.

The exact LBE state machine remains governed by the LBE control protocol and persisted runtime semantics.

---

## 7. CLI/TUI direction does not change

Reusing Cline underneath does not make the visible product a Cline CLI.

The primary LBE TUI remains a high-fidelity transcript over LBE runtime events:

```text
user input
agent commentary / streamed answer
in-flight governed tool cell
live stdout/stderr/progress
completed / failed / denied / escalated / cancelled result
agent reaction
edit/diff
validation
final response
```

Compact secondary views remain LBE-owned, including concepts such as:

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

The TUI must consume normalized LBE events, not Cline UI messages or provider-native wire payloads.

---

## 8. Dependency and licensing requirements

The current `cline/cline` repository is Apache License 2.0.

If Cline packages become production dependencies:

- pin exact package versions;
- record package/version provenance in LBE build/release metadata;
- preserve required Apache-2.0 license and NOTICE obligations;
- keep the Cline adapter isolated behind LBE interfaces;
- add compatibility tests before dependency upgrades;
- do not use Cline trademarks as LBE product identity;
- verify the license and package contents again at the version actually adopted.

---

## 9. Migration and fallback rule

Reuse must never weaken an accepted LBE contract.

If a pinned Cline package cannot preserve an LBE requirement without patching around, bypassing, or duplicating the authority boundary, LBE must fall back to the next lower reusable layer or to a native adapter for that capability.

```text
@cline/agents incompatible with governed tool authority
        -> retain @cline/llms only
        -> LBE owns continuation loop

@cline/llms incompatible with required provider truth
        -> native provider adapter behind the same LBE contract

Cline update breaks a proven compatibility gate
        -> hold the pinned version or switch backend
        -> never weaken the LBE contract to accommodate the dependency
```

Forking or vendoring substantial Cline subsystems is not the default remedy. Any such move requires a separate architecture decision with provenance, maintenance cost, and authority-boundary proof.

---

## 10. Revised forward execution sequence

The canonical P0-P16 dependency order remains valid. The immediate forward path becomes:

```text
P2 current capability negotiation
        -> finish acceptance/regression proof

P3 Cline lower-layer compatibility proof
        -> @cline/llms event/provider mapping
        -> event fidelity + cancellation + identity proof
        -> authority-boundary proof
        -> choose per-provider backend

P4 persistent Session / Turn / Item under existing LBE owner

P5 governed professional capabilities under existing dispatcher

P6 live runtime execution events

P7 continuation compatibility proof
        -> evaluate @cline/agents
        -> reuse only if LBE tool execution stays authoritative
        -> otherwise LBE owns continuation loop

P8-P16 continue under canonical plan
```

This is not permission to skip P0/P1/P2/P4 contracts. It is a direction to avoid rebuilding mature separable infrastructure unnecessarily.

---

## 11. Final adoption gate

Cline lower-layer reuse is accepted only when tests/evidence prove all of the following:

- LBE P0 normalized semantics can represent the relevant Cline/provider stream without fabrication;
- selected model capability truth still comes from LBE P2 evidence, not Cline brand assumptions;
- provider-native and LBE tool-call identities remain distinguishable and correlated;
- tool calls are intercepted before any workspace/external mutation;
- all mutations still pass existing LBE authorization and tool orchestration;
- provider continuation can consume LBE-produced tool results;
- cancellation/error attribution remains truthful;
- LBE session/workspace persistence remains authoritative;
- provider/backend replacement remains possible behind the adapter;
- bounded 0.2.1 provider path remains regression-safe until explicitly retired by migration proof;
- LBE TUI/control clients remain independent of Cline-native UI/event serialization.

If any condition fails, apply the migration/fallback rule rather than weakening the contract.

## Final rule

**Evaluate `@cline/llms` first. Evaluate `@cline/agents` only if LBE retains tool execution authority. Avoid `@cline/core`/full SDK runtime ownership unless a future isolation proof explicitly replaces an LBE owner. Reuse Cline where it is mature infrastructure; LBE remains authoritative for governance, workspace/session truth, tools, evidence, validation, completion, and product-facing events.**
