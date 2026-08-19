# LBE Cline Provider Continuation Gate

```text
phase: LBE_CLINE_PROVIDER_CONTINUATION
slice: ENABLE_PROVIDER_BACKED_AGENTRUNTIME_CONTINUATION
status: OPEN

base_sha: fc5512ffd0c405a9028f08f5a6d80f51fbe1d46d
required_prior_checkpoint: docs/acceptance/LBE_CLINE_DEPENDENCY_SECURITY_RESOLUTION_CHECKPOINT.md = PASS
required_evidence_level: INTEGRATION
next_phase_locked: true
```

## Goal

Enable the already-packaged `@cline/agents@0.0.75` `AgentRuntime` to execute a real provider-backed turn behind the existing Python-owned governed stdio boundary, while keeping all executable tool authority in LBE.

Required continuation path:

```text
Python/LBE turn.execute
        |
        v
bounded Node worker
        |
        v
Cline AgentRuntime.run()/continue()
        |
        +-- provider events -> provider.event frames
        |
        +-- AgentTool proxy -> tool.proposed frame
                              |
                              v
                    Python GovernedToolOrchestrator
                              |
                              v
                         ToolReceipt
                              |
                              v
                         tool.result
                              |
                              v
                    existing Cline continuation loop
        |
        v
turn.completed / turn.failed
```

## Existing owners that must remain authoritative

- provider-neutral LBE runtime/session identity: existing Python runtime/session owners;
- executable authorization: `runtime/authorization_resolver.py::resolve_authorization`;
- registered tool lookup, execution, receipts, and operation-id idempotency: `runtime/tool_orchestration.py::GovernedToolOrchestrator`;
- Node child lifecycle and protocol fail-closed behavior: `runtime/cline_stdio_bridge.py::GovernedClineWorker`;
- continuation/tool-loop mechanics: pinned Cline `AgentRuntime` only.

## Allowed implementation scope

- `lbe_guard_inspector/runtime/cline_worker/worker.mjs`;
- `lbe_guard_inspector/runtime/cline_stdio_bridge.py`;
- `lbe_guard_inspector/runtime/cline_stdio_protocol.py` only if a protocol invariant requires it;
- focused bridge/orchestrator tests;
- this gate/checkpoint and machine-gate state.

## Required behavior

1. `runtime.start` may receive ephemeral provider configuration (`provider_id`, `model_id`, optional API key/base URL/headers/options) and must never echo credentials to stdout protocol frames.
2. The worker must construct `AgentRuntime` from the pinned `@cline/agents@0.0.75` API; it must not create a second continuation loop.
3. Only LBE-supplied `allowed_tools` may be exposed to Cline. No native Cline filesystem/editor/shell/process mutation tool is registered.
4. Each Cline tool callback must emit `tool.proposed` with deterministic correlation IDs and block until a matching `tool.result` arrives.
5. Python mediation must turn each `tool.proposed` into an existing `ToolRequest`, call `GovernedToolOrchestrator.invoke()`, and return the resulting receipt as `tool.result`.
6. Unknown/mismatched/duplicate tool-result identity must fail closed.
7. Cancellation must call the existing Cline runtime abort control; steering may remain explicitly unsupported in this bounded slice unless proven necessary.
8. A terminal Cline result maps to `turn.completed`; provider/runtime exceptions map to `turn.failed` without claiming LBE validation/completion truth.
9. Provider credentials remain process-memory-only and are not written to checkpoint/session/receipt files by this slice.

## Acceptance proof

- existing startup/shutdown/fail-closed tests remain green;
- provider-configured startup proves Cline runtime construction without exposing credentials;
- deterministic fake/local provider proof exercises `turn.execute -> turn.completed` without a tool;
- tool-call proof exercises `tool.proposed -> GovernedToolOrchestrator -> tool.result -> same AgentRuntime continuation -> turn.completed`;
- denial/escalation/tool failure cannot bypass LBE and is returned to Cline as a tool failure;
- direct provider-backed live proof is run when a configured provider endpoint is available; absence of credentials is `BLOCKED_CONFIGURATION`, not a fabricated PASS;
- focused bridge + tool orchestration tests pass;
- dependency-security audit remains zero high/critical;
- implementation gate passes;
- `git diff --check` passes;
- worktree is clean at the proven head.

## Non-goals

- no ClineCore adoption;
- no second session/history store;
- no provider-selection UI;
- no MCP;
- no TUI/preview implementation;
- no new shell/filesystem bypass;
- no retry/recovery redesign;
- no release-ready claim;
- no change to validation/evidence/completion authority.

Stop after this slice is proven and checkpointed. Do not unlock the next phase automatically.
