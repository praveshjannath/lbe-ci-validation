# LBE ↔ Cline AgentRuntime Interop Boundary Checkpoint

phase: LBE_CLINE_AGENTRUNTIME_GOVERNANCE_ADAPTER
slice: PROVE_INTEROP_AND_PREEXECUTION_AUTHORITY_BOUNDARY
status: OPEN

base_sha: ea246b154e00882ac4e29d14f4e244a9e08c2b21
implementation_sha: NOT_IMPLEMENTED_BOUNDARY_PROOF_ONLY
checkpoint_sha: PENDING

cline_repository: cline/cline
cline_revision: 8bbdde2a5c1f972864fe1b954f639c21fac61a40

requirements:
  - prove one exact Python-LBE to TypeScript-Cline AgentRuntime interop mechanism or reject direct reuse
  - preserve existing R6C resolve_authorization authority
  - preserve GovernedToolOrchestrator as the canonical execution/receipt owner
  - prove native overlapping Cline mutation/execution paths can be excluded
  - prove deterministic Cline tool-call -> LBE operation_id/ToolReceipt mapping
  - prove governed LBE result can return to Cline continuation without a second continuation engine
  - record packaging/runtime/dependency/license/security implications

non_goals:
  - production adapter code
  - Node sidecar/daemon/RPC product architecture
  - dependency adoption
  - provider/TUI/MCP feature implementation
  - authorization/session/evidence/validation/completion owner changes

existing_owner:
  - deterministic authorization -> lbe_guard_inspector/runtime/authorization_resolver.py::resolve_authorization
  - governed tool registry/execution/receipt/idempotency -> lbe_guard_inspector/runtime/tool_orchestration.py::GovernedToolOrchestrator
  - provider turn lifecycle -> lbe_guard_inspector/provider_turn_runtime.py::{NonStreamingProviderTurnRuntime,BackgroundProviderTurnRuntime}
  - Cline continuation/tool mechanics under evaluation -> cline/cline sdk/packages/agents/src/agent-runtime.ts

reuse_decision:
  decision: NEW_ARCHITECTURE_REQUIRED
  evidence:
    - canonical main is a Python 3.11+ setuptools package with no root package.json or declared Cline/Node runtime dependency
    - audited Cline AgentRuntime is TypeScript/Node code under @cline/agents
    - repository source search found no existing in-process Python<->Node bridge, stdio/RPC bridge, or canonical Cline runtime host on main
    - historical PR #53 explicitly kept @letterblack/lbe as a thin npm bootstrap while the authoritative runtime remained Python and kept npm free of runtime/governance/session/provider authority; that PR was closed unmerged
  conclusion: direct in-process reuse is not available in the current canonical runtime. Consuming Cline AgentRuntime would require an explicit cross-runtime host/process/RPC/embedding boundary, which is a new architecture surface under the active gate.

architecture_change:
  introduced: no
  user_authorized: no
  canonical_docs_updated_first: yes

files_changed:
  - .lbe/governance/implementation-gates.json
  - docs/acceptance/LBE_CLINE_AGENTRUNTIME_INTEROP_GATE.md
  - docs/acceptance/LBE_CLINE_AGENTRUNTIME_INTEROP_CHECKPOINT.md

required_evidence_level: INTEGRATION

validation_evidence:
  source_boundary:
    result: PASS
    evidence: canonical pyproject.toml is Python-only; exact Cline revision is TypeScript/Node; no existing canonical interop owner was found
  authority_boundary:
    result: PASS
    evidence: resolve_authorization and GovernedToolOrchestrator remain existing deterministic authority/execution owners and cannot be replaced by Cline
  historical_distribution_boundary:
    result: PASS
    evidence: closed unmerged PR #53 documents npm as thin bootstrap only and Python as authoritative runtime; it does not provide a canonical Cline AgentRuntime host
  integration:
    command: NOT RUN
    result: BLOCKED BY ARCHITECTURE DECISION — no existing implementation-ready interop mechanism exists to test without first authorizing a new cross-runtime architecture surface
  live_runtime:
    command_or_flow: NOT RUN
    result: NOT APPLICABLE BEFORE ARCHITECTURE AUTHORIZATION
  full_suite:
    command: NOT REQUIRED FOR DOCUMENT-ONLY CLASSIFICATION
    result: NOT RUN
  git_diff_check:
    result: PENDING LOCAL POST-PULL VALIDATION

unverified:
  - which specific new architecture, if any, should be authorized: governed Node subprocess/stdio host, long-lived sidecar/RPC host, embedding runtime, or reject Cline production reuse entirely
  - fresh dependency/license/security adoption result for the exact Cline packages chosen by any future authorized design
  - local Node/npm availability is environment evidence only and does not change the architecture classification

document_conflicts:
  - none known; current source and historical PR #53 are consistent that Python is authoritative and npm is not runtime authority

workspace_proof:
  repository: Letterblack0306/LBE_Presistent_Agent_wall
  branch: main
  primary_worktree: PENDING LOCAL POST-PULL VALIDATION
  origin: https://github.com/Letterblack0306/LBE_Presistent_Agent_wall.git

push_proof:
  source_ref: refs/heads/main
  destination_ref: refs/heads/main
  pushed_sha: PENDING THIS CLASSIFICATION COMMIT
  hook_result: GitHub-side documentation classification requires local post-pull gate/workspace validation

project_user_ready: UNVERIFIED
release_ready: UNVERIFIED
next_phase_locked: true

## Classification

```text
NEW_ARCHITECTURE_REQUIRED
```

This is not a defect and does not invalidate the completed Cline reuse audit. The audit correctly proved Cline mechanics are reusable in principle. This checkpoint proves the current canonical Python runtime has no existing implementation-ready boundary through which those TypeScript mechanics can be consumed.

The next action is therefore an architecture decision, not adapter implementation.

Allowed decision candidates for a separately authorized design slice:

1. `GOVERNED_NODE_SUBPROCESS_STDIO` — Python remains authoritative; one bounded Node worker hosts Cline AgentRuntime and communicates through a strict typed protocol. LBE owns session IDs, authorization, tool execution, evidence, completion and process lifecycle.
2. `LONG_LIVED_NODE_SIDECAR_RPC` — broader persistent Node runtime host. Higher operational/authority risk and requires stronger lifecycle/authentication/recovery design.
3. `EMBEDDED_JS_RUNTIME` — embed a JS runtime/library into Python. Adds a substantial native/dependency surface and must prove Cline compatibility.
4. `REJECT_CLINE_PRODUCTION_REUSE` — keep Cline as source/reference only and continue native Python implementation.

No candidate is selected by this checkpoint. Selecting one changes architecture and requires explicit user authorization plus a new machine-gated design slice.

After this classification, stop. No production adapter implementation is authorized.