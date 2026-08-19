# LBE Runtime Roadmap Reconciliation Gate

```text
phase: LBE_RUNTIME_ROADMAP_RECONCILIATION
slice: CLASSIFY_IMPLEMENTED_VS_ACCEPTED_RUNTIME_CAPABILITIES
status: OPEN

required_evidence_level: SOURCE + ACCEPTANCE_RECORD_RECONCILIATION
next_phase_locked: true
implementation_allowed: false
architecture_changes_allowed: false
```

## Question

What is the earliest required persistent-runtime capability that current `main` and current acceptance evidence cannot prove?

This slice exists because `docs/IMPLEMENTATION_PLAN.md` still describes R2 as current while live source and accepted checkpoints contain later runtime owners, including resume, recovery, provider/runtime control, mode policy, authorization, governed tool orchestration, completion gating, CLI/TUI surfaces, and the accepted Cline AgentRuntime continuation boundary.

## Authority order

Use:

```text
current validation/runtime evidence
> current workspace/Git evidence
> active machine gate
> current acceptance/checkpoint records
> current source/tests
> current architecture/design docs
> historical roadmap/status text
> inference
```

Do not mark a roadmap item complete merely because a file or unit test exists. Do not mark it missing merely because an older roadmap lists it as future work.

## Existing owners that must be inspected, not duplicated

- persistent session/task lifecycle: `lbe_guard_inspector/session_memory_runtime.py`
- reasoning boundary: existing `LBERequest` / `LBEResponse` controller path
- checkpoint/resume/rehydration: existing session-memory runtime + validated memory owners
- recovery: `lbe_guard_inspector/recovery.py`
- provider registry/capabilities/turn control: existing provider/runtime owners
- mode policy: `lbe_guard_inspector/runtime/mode_controller.py`
- authorization: `lbe_guard_inspector/runtime/authorization_resolver.py`
- context assembly: `lbe_guard_inspector/runtime/context_assembly.py`
- governed tools/receipts: `lbe_guard_inspector/runtime/tool_orchestration.py`
- completion/validation: existing completion runtime/gate/evidence owners
- CLI: `lbe_guard_inspector/cli.py`
- Cline continuation mechanics: accepted bounded Node worker behind LBE authority

## Required classification vocabulary

For each roadmap family R3 through R7 and release/package readiness, classify only as:

- `PROVEN_COMPLETE`
- `IMPLEMENTED_NOT_ACCEPTED`
- `PARTIALLY_PROVEN`
- `NOT_IMPLEMENTED`
- `BLOCKED_CONFIGURATION`
- `STALE_DOCUMENT_ONLY`
- `UNKNOWN`

Every classification must cite current source and/or current acceptance evidence.

## Required work

1. Prove canonical repository/main/primary-worktree state locally.
2. Inventory current runtime source owners and tests.
3. Inventory current acceptance/checkpoint records and their status.
4. Compare live implementation against `docs/IMPLEMENTATION_PLAN.md` R3-R7.
5. Separate implementation existence from acceptance level.
6. Identify stale or conflicting active-roadmap documents, including `CURRENT_AGENT_EXECUTION_GATE.md` where applicable.
7. Determine the first genuinely missing or insufficiently proven capability.
8. Reconcile `docs/IMPLEMENTATION_PLAN.md` and current execution/status records to that evidence.
9. Record a checkpoint containing the classification matrix and exact first missing capability.
10. Stop. Do not implement that capability until a separate machine/human implementation gate is explicitly activated.

## Explicit non-goals

- no runtime source changes;
- no new provider adapter;
- no retry/recovery redesign;
- no resume redesign;
- no new CLI/TUI behavior;
- no MCP;
- no ClineCore adoption;
- no release action;
- no architecture ownership change.

## Exit condition

PASS requires:

- every R3-R7 family classified from current evidence;
- stale roadmap/current-gate contradictions reconciled;
- exactly one earliest next capability/acceptance gap identified, or explicit proof that only R7/release acceptance remains;
- machine and human current-slice records agree;
- local gate check passes;
- `git diff --check` passes;
- canonical worktree is clean at the reconciled head.

After PASS, `next_phase_locked` remains true. A new bounded implementation or acceptance-proof slice must be activated separately.