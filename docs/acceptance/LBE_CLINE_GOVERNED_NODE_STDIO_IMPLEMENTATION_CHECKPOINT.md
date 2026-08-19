# LBE Cline Governed Node STDIO Implementation Checkpoint

```text
phase: LBE_CLINE_GOVERNED_NODE_STDIO_IMPLEMENTATION
slice: IMPLEMENT_GOVERNED_NODE_STDIO_BRIDGE_FOUNDATION
status: UNVERIFIED

base_sha: e0a7c87abbeacb478541dce68de655b483a63f32
implementation_sha: fea42694edd84bbda9c46b18b6626992f536ad0d
checkpoint_sha: populated by GitHub commit containing this file

requirements:
  - define lbe-cline-stdio/1 protocol/frame validation
  - add Python-owned bounded Node child lifecycle
  - add bounded @cline/agents worker bootstrap
  - keep native Cline mutation/execution tools absent or unreachable
  - preserve LBE authorization/tool-orchestration authority
  - pin @cline/agents exact version and Node engine
  - generate deterministic transitive lock
  - prove startup/shutdown/fail-closed behavior and existing orchestration regression
  - complete dependency/security audit before PASS

non_goals:
  - no ClineCore wholesale adoption
  - no second session store
  - no second authorization resolver
  - no second tool dispatcher
  - no TUI redesign
  - no MCP implementation
  - no provider-selection expansion
  - no release-ready claim

existing_owner:
  - authorization decision -> lbe_guard_inspector/runtime/authorization_resolver.py::resolve_authorization
  - governed tool execution/receipt identity -> lbe_guard_inspector/runtime/tool_orchestration.py::GovernedToolOrchestrator.invoke
  - bounded process-safety precedent -> lbe_guard_inspector/runtime/process_events.py::observe_policy_command
  - provider-turn/cancellation ownership -> lbe_guard_inspector/provider_turn_runtime.py

reuse_decision:
  decision: ADAPT
  evidence: Cline AgentRuntime continuation/tool mechanics are reused behind a Python-owned subprocess boundary; LBE remains lifecycle, authorization, execution, receipt, session, evidence, validation, and completion authority.

architecture_change:
  introduced: yes
  user_authorized: yes
  canonical_docs_updated_first: yes

files_changed:
  - lbe_guard_inspector/runtime/cline_stdio_protocol.py
  - lbe_guard_inspector/runtime/cline_stdio_bridge.py
  - lbe_guard_inspector/runtime/cline_worker/package.json
  - lbe_guard_inspector/runtime/cline_worker/worker.mjs
  - pyproject.toml
  - tests/test_cline_stdio_bridge.py

required_evidence_level: INTEGRATION

validation_evidence:
  focused:
    command: python -m pytest tests/test_cline_stdio_bridge.py tests/test_tool_orchestration.py -q
    result: PASS — 20 passed at fea42694edd84bbda9c46b18b6626992f536ad0d
  integration:
    command: real Node worker startup/shutdown through GovernedClineWorker after npm install/npm ci of @cline/agents@0.0.75
    result: PASS — startup/ready, shutdown, allowlist-only exposure, truthful unsupported continuation, and existing LBE orchestration tests passed
  live_runtime:
    command_or_flow: import-time Dify reachability test by temporarily making node_modules/dify-ai-provider unavailable, restoring it immediately, then rerunning bridge tests
    result: PROVEN REACHABLE — import('@cline/agents') fails with ERR_MODULE_NOT_FOUND when dify-ai-provider is unavailable; post-restore bridge tests PASS 8/8
  full_suite:
    command: NOT RUN for this bounded foundation checkpoint; focused changed-owner regression completed
    result: NOT REQUIRED FOR CURRENT CLAIM, but broader release readiness remains unverified
  git_diff_check:
    result: PASS on tracked implementation state

package_runtime_evidence:
  - Node v24.15.0 satisfies worker engine >=22
  - @cline/agents@0.0.75 is the latest stable published version observed during validation
  - @cline/agents@0.0.75 resolves @cline/llms@0.0.75 and @cline/shared@0.0.75
  - generated package-lock.json is lockfileVersion 3 and npm ci reproduces the dependency graph
  - wheel build contains worker.mjs, package.json, and the locally generated package-lock.json
  - Apache-2.0 recorded for @cline/agents package line

security_evidence:
  - npm audit reports 2 transitive vulnerabilities: 1 moderate and 1 high
  - affected branch is reachable at import time through @cline/llms -> dify-ai-provider@1.1.1
  - dify-ai-provider@1.1.1 is the latest published Dify package observed during validation
  - Dify declares @ai-sdk/provider-utils ^3.0.3
  - published @ai-sdk/provider-utils v3 line ends at 3.0.32, inside the reported affected range <=3.0.32
  - Dify resolves undici 5.29.0, while the reported affected undici range includes <=6.27.0
  - no semver-compatible registry-only patched resolution was found for the Dify branch

unverified:
  - dependency-security adoption remains blocked by reachable transitive Dify/provider-utils/undici advisories
  - package-lock.json was generated and validated locally but is not yet canonical in GitHub
  - provider-backed live AgentRuntime continuation intentionally remains unverified in this foundation slice
  - release readiness

document_conflicts:
  - docs/CURRENT_STATUS.md is stale (2026-07-30 and older baseline SHA) relative to current main; it is non-authoritative because docs/IMPLEMENTATION_PLAN.md explicitly says live Git/runtime/validation evidence wins when docs disagree. Refresh is deferred to a separate bounded documentation reconciliation.

workspace_proof:
  repository: Letterblack0306/LBE_Presistent_Agent_wall
  branch: main
  primary_worktree: PASS
  origin: https://github.com/Letterblack0306/LBE_Presistent_Agent_wall.git

push_proof:
  source_ref: refs/heads/main
  destination_ref: refs/heads/main
  pushed_sha: fea42694edd84bbda9c46b18b6626992f536ad0d
  hook_result: prior implementation pushes passed LBE WORKSPACE LOCK; checkpoint itself is written through the GitHub connector and must be pulled/verified locally before any later slice

project_user_ready: NO
release_ready: NO
next_phase_locked: true
```

## Blocking conclusion

The bridge foundation is functionally proven at the required integration level, but this slice is not PASS because the security/dependency requirement is not satisfied. The vulnerable Dify dependency is not merely installed: removing it causes `import('@cline/agents')` to fail, proving import-time reachability. No newer stable `@cline/agents` package or semver-compatible patched Dify dependency line was found during validation.

Do not advance to provider continuation, MCP, TUI, or release work until this dependency-security blocker is resolved through a separately authorized and evidenced decision.

## UI reference preservation

A user-provided `preview.html` visual reference exists outside the repository and is reserved for the later UI/TUI slice. It defines the visual contract for the ANSI/CLI surface; it is not runtime HTML and must not be substituted for a browser UI. No UI implementation is performed in this slice.
