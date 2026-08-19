# Cline Runtime Reuse Boundary Rule

Applies when the active phase is `CLINE_CORE_REUSE_BOUNDARY_AUDIT` or later work relies on Cline/provider runtime reuse.

## Reuse before rebuild

Before implementing provider, event, session, tool-loop, checkpoint, control, process, MCP, transcript, or CLI/TUI plumbing:
1. inspect the current Cline implementation at an exact revision;
2. inspect the current LBE owner;
3. evaluate reuse/adaptation;
4. record the decision in `docs/research/CLINE_CORE_REUSE_BOUNDARY_MATRIX.md`.

Allowed decisions: `REUSE | ADAPT | REJECT | UNVERIFIED`

`UNVERIFIED` blocks implementation.

## Evidence routing

- BirdEye = local LBE workspace truth and governed local execution.
- GitHub = canonical remote repository/commit/source truth.
- GPT-Knowledge = architecture/reference methodology.
- Runtime-specific proof = live behavior only when required.

Never substitute one evidence class for another.

## No parallel authority

Cline may provide mature mechanics, but LBE retains deterministic authority for workspace, permissions, governed tools, evidence, validation, completion, and canonical runtime contracts.

If direct reuse would create a second authority or native mutation bypass, classify `REJECT` or `ADAPT`; do not hide the bypass.

## Strict governance claim

Do not claim Cline is fully governed by LBE merely because Cline can call LBE/MCP tools.

A strict-governance claim requires proof that overlapping native mutation paths are disabled, restricted, sandboxed, intercepted, or independently verified.

## Current audit restriction

During `CLINE_CORE_REUSE_BOUNDARY_AUDIT`:
- no product/runtime implementation source changes;
- no dependency adoption;
- no architecture changes;
- documentation/audit/governance changes only;
- checkpoint and stop when complete.
