# Agent Instructions — Cline Reuse Boundary Audit

Read this file when the active machine phase is `CLINE_CORE_REUSE_BOUNDARY_AUDIT`.

## First action

Read, in order:
1. `.agent/PROJECT_CONTEXT.md`
2. `.lbe/governance/workspace-lock.json`
3. `.lbe/governance/implementation-gates.json`
4. `docs/acceptance/CLINE_CORE_REUSE_BOUNDARY_AUDIT_GATE.md`
5. `docs/research/CLINE_CORE_REUSE_BOUNDARY_MATRIX.md`
6. relevant GPT-Knowledge Cline/professional-runtime references
7. current LBE source/tests and exact Cline source being audited

## Evidence routing

Use BirdEye for local LBE evidence and governed local execution.

Use GitHub for canonical remote repository/commit/patch/source truth, including exact Cline source revision.

Do not infer local state from GitHub or remote state from BirdEye.

If BirdEye is unavailable or policy-blocked for required local proof, record `UNVERIFIED` or `BLOCKED_WORKSPACE_AUTHORITY`. Do not silently bypass through raw shell execution.

## Audit discipline

For each required matrix row:
1. establish exact Cline repository/revision;
2. inspect actual source, not README claims alone;
3. identify package, path, and symbol/owner;
4. state observed behavior;
5. identify corresponding existing LBE owner;
6. analyze whether mutation/authority can bypass LBE;
7. classify `REUSE`, `ADAPT`, `REJECT`, or `UNVERIFIED`;
8. record evidence and follow-up proof.

## Hard rule

**No professional-runtime subsystem may be newly implemented because Cline reuse was assumed.**

A new subsystem can only be justified after the corresponding matrix row is `REJECT`, or `ADAPT` with the exact missing LBE requirement stated.

`UNVERIFIED` is blocking.

## Cline authority boundary

Never transfer workspace identity, canonical LBE session/task contract, authorization, governed tool dispatch, evidence provenance, validation/completion truth, product-facing normalized events, or checkpoint/recovery policy to Cline without explicit architecture authorization.

## Stop condition

Complete the matrix and checkpoint, classify the first genuinely missing dependency, then STOP.

Do not activate the next implementation slice.
