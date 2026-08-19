# R7 Installed Coding Composition Repair Investigation Gate

Status: **OPEN — INVESTIGATION ONLY — IMPLEMENTATION LOCKED — NEXT PHASE LOCKED**

```text
phase: R7_REPAIR_INVESTIGATION
slice: TRACE_INSTALLED_CODE_TO_EXISTING_GOVERNED_EXECUTION
base_sha: 677cb96471aaead50b30312aa16eeea04caa8084
implementation_allowed: false
architecture_changes_allowed: false
next_phase_locked: true
required_evidence_level: SOURCE_PLUS_RUNTIME_CORRELATION
release_path_authorized: true
publish_allowed_now: false
```

## Proven trigger

R7 installed end-to-end acceptance failed on observable 3. The installed `lbe code` path reached `GovernedAgentGateway` and `LBERequestController`, the provider received only `approved_tools=[workspace.read]`, and the response remained `read_only=true`. The accepted R6E governed coding execution/ToolReceipt path was not reached.

This gate does not reopen accepted R3-R6F or CLI contracts unless new evidence directly falsifies one of them.

## Investigation question

> What existing active-owner seam should connect installed `lbe code` / `GovernedAgentGateway` reasoning to the already accepted R6C authorization, R6E governed tool execution, ToolReceipt, and receipt-backed provider continuation path, and what is the smallest correction that restores this composition without creating parallel authority?

## Existing owners that must be reused unless disproven

```text
CLI transport: lbe_guard_inspector/cli.py
persistent session/task: SessionMemoryRuntimeBridge
identity/mode gateway: GovernedAgentGateway
reasoning/inspection: LBERequestController
R6C authorization: runtime/authorization_resolver.py
R6E execution: runtime/tool_orchestration.py
receipt continuation: provider_continuation.py
completion: runtime/completion_runtime.py and accepted evidence/gate owners
```

## Required investigation sequence

1. lock exact repository/revision and retain the R7 reproduction;
2. trace `cli._run_mode_command -> GovernedAgentGateway -> reasoning controller`;
3. enumerate every current `ToolRequest` producer and consumer;
4. enumerate every `GovernedToolOrchestrator` construction and invocation;
5. enumerate every `ToolReceipt` consumer/correlation path;
6. enumerate provider tool-call and provider-turn continuation implementations;
7. trace session/task/request/tool-call/operation correlation requirements;
8. scan for alternate or legacy coding execution paths before proposing a new seam;
9. identify the earliest missing or incorrect composition state;
10. state one bounded repair hypothesis and a falsifier;
11. define focused, integration, and installed-runtime validation before implementation.

## Completion predicate

The investigation may close only when all are proven:

```text
exact provider tool-request producer identified
exact intended R6E executor/consumer identified
exact ToolReceipt continuation seam identified
exact persistence/correlation owner identified
no already-active alternate coding path missed
smallest edit surface identified
no new authority required
repair hypothesis + falsifier recorded
claim-matched validation plan recorded
```

## Forbidden work

- runtime/CLI/test/package implementation changes;
- architecture rewrite;
- second tool dispatcher or authorization owner;
- provider-direct workspace/process mutation;
- CLI-owned execution;
- provider-owned completion truth;
- new session/provider/receipt authority;
- continuation of later R7 observables;
- release/package-readiness activation, version bump, tag, or publish.

## Advance rule

A PASS investigation does not authorize implementation automatically. It only permits creation/activation of a separately bounded repair implementation gate after the exact owner, edit surface, hypothesis, falsifier, and validation contract are recorded.
