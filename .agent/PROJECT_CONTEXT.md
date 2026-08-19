# LBE Project Context for Cline and Other Coding Agents

Status: **CANONICAL AGENT ENTRYPOINT**

Repository: `Letterblack0306/LBE_Presistent_Agent_wall`

This file is the first project-context file an agent must read. It summarizes routing; it does not replace the machine gates or acceptance records.

## Canonical delivery authority

```text
remote: origin
branch: main
worktree: primary Git worktree only
push source: current main HEAD only
push destination: refs/heads/main
```

No implementation branch. No implementation worktree. No detached-HEAD implementation. No alternate remote push.

Tracked enforcement:

- `.lbe/governance/workspace-lock.json`
- `.githooks/pre-commit`
- `.githooks/pre-push`
- `scripts/enable-workspace-lock.ps1`

## Mandatory routing order

Read every time before significant implementation:

1. `.agent/PROJECT_CONTEXT.md`
2. `.lbe/governance/workspace-lock.json`
3. `.lbe/governance/implementation-gates.json`
4. the exact `active_plan` path declared by `.lbe/governance/implementation-gates.json`
5. `docs/governance/AGENT_IMPLEMENTATION_EXECUTION_GUIDE.md`
6. architecture/design docs referenced by the active plan
7. current source, tests, Git state, and runtime evidence
8. older acceptance/plan records only as historical evidence unless the active gate explicitly names them

Never substitute a similarly named document for the machine-declared `active_plan`.

Authority for current facts:

```text
current validation
> current workspace/Git/runtime evidence
> active machine gate
> machine-declared active plan/checkpoint
> canonical design/plan
> verified historical records
> reference knowledge
> model inference
```

If these disagree, do not silently choose. Record `DOCUMENT_CONFLICT` and reconcile before moving forward.

## Current baseline at creation of this context

The context package was created after canonical `main` reached:

```text
95f8be0eb98f57ad050ae662ae1add0d5f9de8ab
implement cancellation support through transport capability checking
```

That commit established a truthful cancellation capability boundary:

- transports declare whether cancellation is supported;
- supported transports can receive cancellation;
- `UrllibJsonTransport` declares cancellation unsupported;
- unsupported live cancellation is rejected rather than faked;
- cancelled runtime turns suppress late provider projection.

Focused validation was reported as 18 passing tests plus `git diff --check`.

**This does not authorize another implementation phase.** The active machine gate now points to `docs/acceptance/CURRENT_AGENT_EXECUTION_GATE.md`, whose first required action is checkpoint reconciliation: run/record the required full regression and update the acceptance state for the cancellation change before advancing.

Always verify the current live HEAD because this baseline becomes historical as soon as newer commits land.

## Product architecture invariants

LBE is the authority. Providers reason; clients render/control.

LBE owns:

- workspace/project identity;
- canonical session/task persistence;
- mode and permission state;
- capability availability/projection;
- R6C/deterministic authorization;
- governed tool execution;
- operation/receipt identity;
- evidence provenance;
- validation truth;
- completion truth;
- checkpoint/recovery policy;
- durable Session/Turn/Item state;
- agent-control protocol semantics;
- product-facing normalized events.

Provider/Cline/native adapters may own provider mechanics only within the accepted adapter boundary.

The TUI/CLI/IDE/MCP surfaces must not become second runtime authorities.

## Architectural correction — required reading

A documented architectural lesson supersedes how "provider reasons" was first wired:

> **LBE governs an agent's capabilities and consequences; it does not prescribe the agent's
> reasoning procedure.**

**The reasoning controller became the agent.** `LBERequestController` plus the fixed
`ReasoningPlan` workflow must be treated as a bounded/specialist investigation capability
(`guard.inspect`), not the central cognitive path.

- The provider owns: reasoning, investigation strategy, hypothesis formation, capability/tool
  selection, replanning after results, interpretation, and communication.
- LBE owns: workspace/session identity, mode/policy, authorization, capability boundaries,
  governed execution, operation identity, ToolReceipt, evidence provenance, persistence, and
  deterministic validation/completion truth.
- Deterministic guards, R6C/R6E authorization and orchestration, ToolReceipt, provider
  continuation, persistence, and completion validation are **NOT mistakes**; only their
  placement around the reasoning agent is.

**Read first:** `docs/design/AGENT_AGENCY_LBE_AUTHORITY_SEPARATION.md` and
`docs/IMPLEMENTATION_PLAN.md` section 15. This is a **proposed follow-on architecture review**,
not an active machine gate, and does not change current gate state.


## Reuse-before-rebuild direction

Existing owners must be inspected and extended before new systems are introduced.

For Cline/provider work:

- the project evaluated `@cline/llms@0.0.73`;
- that exact production adoption was rejected at its recorded dependency/license gate;
- the recorded decision for that pin was `NATIVE` while retaining Cline as comparison evidence;
- a future Cline version/layer may be reevaluated only through a new documented compatibility gate;
- do not silently vendor/fork/adopt `@cline/core` as LBE authority.

For older LBE Core material brought into this repository, reuse/migration must be assessed before equivalent functionality is rebuilt.

## Progression law

Exactly one implementation slice may be active.

```text
PLAN
 -> owner audit
 -> reuse decision
 -> slice contract
 -> implementation
 -> focused proof
 -> required live/installed/integration proof
 -> regression
 -> checkpoint
 -> PASS
 -> next slice activation
```

No arrow may be skipped.

The following block progress:

```text
FAIL
UNVERIFIED
MISSING_EVIDENCE
DOCUMENT_CONFLICT
BLOCKED_WORKSPACE_AUTHORITY
BLOCKED_PARALLEL_ARCHITECTURE
```

## Architecture change law

Creating another owner for an existing responsibility is forbidden unless all are true:

1. current owner inspected;
2. current owner proven insufficient for a stated requirement;
3. reuse/adaptation evaluated;
4. evidence recorded;
5. user explicitly authorizes architecture change;
6. canonical design docs updated first;
7. `.lbe/governance/implementation-gates.json` explicitly allows it for that slice.

Otherwise stop with `BLOCKED_PARALLEL_ARCHITECTURE`.

## Readiness vocabulary

Never say simply `READY`.

Use scoped claims:

```text
<phase/slice>: PASS at <evidence level>
Project user-ready: YES/NO/UNVERIFIED
Release-ready: YES/NO/UNVERIFIED
```

Evidence levels:

```text
UNIT
INTEGRATION
INSTALLED
LIVE_RUNTIME
USER_FLOW
RELEASE
```

## Agent stop rule

When the current slice is complete, checkpoint it and stop. Do not automatically proceed to the next phase. The next slice must first be explicitly activated in the machine gate and acceptance document.