# Agent Agency / LBE Authority Separation

Status: **PROPOSED FOLLOW-ON ARCHITECTURE REVIEW** (documentation only — no runtime source
change). This is a future architecture acceptance requirement / proposed review, **not** an
active machine gate.

## Central invariant

> **LBE governs an agent's capabilities and consequences; it does not prescribe the agent's
> reasoning procedure.**

## Ownership boundary

```text
Agent / provider owns:
- reasoning
- investigation strategy
- hypothesis formation
- capability / tool selection
- replanning after results
- interpretation
- communication

LBE owns:
- workspace / session identity
- mode / policy
- authorization
- capability boundaries
- governed execution
- operation identity
- ToolReceipt
- evidence provenance
- persistence
- deterministic validation / completion truth
```

## The architectural mistake

> **Reasoning controller became the agent.**

`LBERequestController` and the fixed `ReasoningPlan` workflow evolved from a bounded,
read-only inspection mechanism into the central cognitive path:

```text
provider = constrained planner / explainer
LBE     = reasoning workflow engine
```

The intended architecture is:

```text
reasoning agent
    ↓ uses
LBE governed capabilities
```

## What was built / what was intended / what must change

| Item | WAS BUILT (current) | WAS INTENDED | MUST CHANGE |
|------|---------------------|--------------|-------------|
| Mandatory `ReasoningPlan` | provider must emit a fixed plan structure every reasoning turn | optional structured output for a planning/inspection capability | make optional; main agent may operate without emitting it |
| Reasoning contract | `_APPROVED_TOOLS = {"workspace.read"}` read-only contract; controller builds evidence, asks plan, selects/runs guard, asks explanation | provider freely chooses among registered LBE capabilities | expose capabilities the agent may invoke; do not encode the sequence |
| Guard selection | driven by LBE workflow in the controller | guard inspection is one available capability | demote `LBERequestController` / `GuardInvestigationCapability` to a bounded/specialist investigation capability an agent may call (`guard.inspect`) |
| Deterministic Guard Inspector | correct deterministic mechanism | same | REPOSITION, not discarded; stays deterministic, exposed as a capability |
| R6C authorization | correct deterministic authorization | same | NOT a mistake; remains the authoritative execution boundary |
| R6E governed tool orchestration | correct deterministic execution/orchestration | same | NOT a mistake; remains the authoritative execution boundary |
| ToolReceipt | correct execution-evidence boundary | same | NOT a mistake; remains the execution evidence boundary |
| Provider continuation | correct receipt-backed continuation | same | NOT a mistake; remains receipt-backed |
| Persistent session/task state | correct LBE-owned persistence | same | NOT a mistake; remains LBE-owned |
| Completion validation | correct LBE-owned deterministic completion truth | same | NOT a mistake; remains LBE-owned |

Deterministic guards, authorization, receipts, persistence, and completion evidence are
**not** mistakes. The mistake is their placement around the reasoning agent — the controller
became the agent instead of the agent using governed capabilities.

## Reposition, do not discard

```text
LBERequestController       -> bounded/specialist investigation capability
ReasoningPlan              -> optional structured contract for specific planning/inspection capabilities
Guard Inspector            -> deterministic capability available to an agent
R6C / R6E / ToolReceipt    -> remain the authoritative governed-execution boundary
memory / context           -> resources supplied to reasoning, not replacements for reasoning
```

## Future architecture acceptance question

> Can a reasoning agent independently choose among registered LBE capabilities, perform
> multiple reasoning/tool turns, revise its approach from receipts/evidence, and complete
> work without LBE prescribing a fixed cognitive workflow, while all mutation, authorization,
> identity, persistence, receipts, and completion authority remain governed by LBE?

This is recorded as a **future architecture acceptance requirement / proposed follow-on
review**. It is not an activated machine gate and does not change current gate state.

## Cross-references

- `docs/IMPLEMENTATION_PLAN.md` — section 15 (doc reconciliation & this proposed review).
- `docs/acceptance/CURRENT_IMPLEMENTATION_GATE.md` — current machine-gate state.
- `.agent/PROJECT_CONTEXT.md` — canonical agent entry point (links here).
- `docs/design/LLM_REASONING_LAYER_ROADMAP.md` — prior reasoning-layer design record.
