# Cline Core Reuse Boundary Audit Gate

Status: **AUDIT PASS — NEXT IMPLEMENTATION PHASE LOCKED**

## Active phase

```text
phase: CLINE_CORE_REUSE_BOUNDARY_AUDIT
slice: CLASSIFY_CLINE_PROFESSIONAL_RUNTIME_REUSE
```

## Purpose

Before LBE builds another professional-runtime subsystem, determine from current Cline source which mature mechanisms can be reused or adapted without transferring LBE authority to Cline or creating a parallel runtime.

This is a **read-only architecture/reuse audit**. It does not authorize product/runtime implementation.

## Mandatory evidence routing

```text
GPT-Knowledge -> canonical architecture/methodology/reference routing
GitHub        -> canonical remote repository, commit, PR, patch, Cline source and revision truth
BirdEye       -> local LBE workspace identity, revision state, local diff, indexed inspection,
                 governed local argv execution and command receipts/history
runtime tools -> live user-visible behavior only when source/static evidence cannot prove it
```

Never infer local state from GitHub or remote state from local indexed evidence.

If BirdEye cannot perform a required local action because policy blocks it, record the limitation. Do not silently bypass it through an ungoverned shell path.

## Required Cline layers

Audit current source for:

```text
@cline/core
@cline/agents
@cline/llms
@cline/shared
```

and at minimum:

- provider adapters;
- provider/model capability metadata and probes;
- provider-native streaming;
- tool-call parsing and continuation;
- tool interception before mutation;
- filesystem/editor mutation;
- shell/terminal/process execution;
- session persistence;
- checkpoint/undo semantics;
- normalized/internal event stream;
- cancellation;
- interrupt and active-turn steering;
- MCP;
- CLI/TUI;
- background processes;
- context/compaction.

## Required classification

Every row must be exactly one of:

```text
REUSE
ADAPT
REJECT
UNVERIFIED
```

- **REUSE** — mature Cline mechanics can be consumed behind an LBE-owned contract without another authority or bypass.
- **ADAPT** — useful Cline mechanics can be wrapped/intercepted, but LBE-specific authority/evidence/session/tool semantics remain LBE-owned.
- **REJECT** — direct reuse cannot satisfy a stated LBE requirement or creates a bypass/parallel owner.
- **UNVERIFIED** — evidence is insufficient. This blocks implementation.

## Mandatory row evidence

For every audited capability record:

```text
Cline repository + exact revision
package/subsystem
source path
symbol/owner
observed behavior
evidence source
existing LBE owner
LBE invariant affected
mutation/authority impact
bypass analysis
classification
reason
required follow-up proof
```

## Existing LBE authority that cannot silently move

LBE retains authority for workspace/project identity, canonical session/task persistence contract, mode and permission state, capability truth/projection, deterministic authorization, governed tool dispatch, operation/receipt identity, evidence provenance, validation truth, completion truth, checkpoint/recovery policy, product-facing normalized events, and agent-control protocol semantics.

## Special checks

### Tool interception
Prove whether Cline can be configured/wrapped so every filesystem, editor, shell, browser, network, and external mutation that LBE claims to govern is intercepted **before execution**.

If native Cline tools can mutate outside LBE, record the bypass and do not claim strict governance.

### Provider continuation
Determine whether an LBE-executed tool result can return into Cline's existing continuation loop without rebuilding provider continuation.

### Session persistence
Determine whether Cline persistence is reusable as mechanics while LBE keeps canonical identifiers/evidence/authorization semantics, or whether coexistence creates competing session authority.

### Capability truth
Transport compatibility does not equal model capability compatibility. Determine what Cline exposes at provider + endpoint + selected model granularity.

## Non-goals

No new Cline dependency adoption, no product/runtime source changes, no replacement of LBE authority owners, no new provider architecture, no new tool authority, no streaming/TUI/MCP implementation, no branch/worktree creation, and no architecture ownership change.

## Exit condition

PASS requires:
1. all required capability families classified;
2. no required UNVERIFIED row;
3. each REUSE/ADAPT decision names its LBE owner/boundary;
4. each REJECT names the exact incompatible requirement;
5. bypass paths explicitly recorded;
6. the first genuinely missing professional-runtime dependency identified without guessing;
7. no implementation source changed;
8. `python scripts/check-implementation-gate.py` PASS;
9. `git diff --check` PASS;
10. checkpoint completed.

## PASS evidence

The source audit is classified **PASS** in `docs/acceptance/CLINE_CORE_REUSE_BOUNDARY_AUDIT_CHECKPOINT.md`.

Recorded local validation on the exact source-audit lineage:

```text
HEAD == origin/main == f8c82b01faf602364a614e820675e489078d9e1c
machine gate: PASS
git diff --check: PASS
worktree: clean
changes since audit activation: audit checkpoint + reuse matrix only
```

The first genuinely missing dependency is the **LBE-to-Cline AgentRuntime governance adapter**, classified `ADAPT`, with future implementation evidence level `INTEGRATION`.

The machine gate `.lbe/governance/implementation-gates.json` intentionally remains operationally `OPEN` with `next_phase_locked=true`. This preserves fail-closed behavior while the completed slice remains registered.

After PASS, stop. Do not activate or implement the next slice automatically.
