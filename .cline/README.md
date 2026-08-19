# Cline Project Controls

This directory is intentionally small. It makes the repository's existing governance discoverable to Cline without moving authority into Cline.

Load order:

1. `rules/00-lbe-workspace-and-progression.md` — always-on boundaries.
2. `skills/lbe-phase-execution/SKILL.md` — procedure for one implementation slice.
3. `.agent/PROJECT_CONTEXT.md` — current project routing/status.
4. `.lbe/governance/implementation-gates.json` — machine-readable active gate.
5. the `active_plan` named by that gate.

Cline may reason, inspect, edit, test, commit, and push only inside the active contract. It may not create a branch/worktree or new authority architecture to work around a blocker.

The presence of a Cline rule or skill is never proof that runtime behavior exists. Source, tests, runtime evidence, and acceptance checkpoints remain authoritative.