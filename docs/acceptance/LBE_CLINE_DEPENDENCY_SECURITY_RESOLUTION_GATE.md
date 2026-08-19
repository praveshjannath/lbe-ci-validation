# LBE Cline Dependency Security Resolution Gate

Status: OPEN — DEPENDENCY SECURITY ONLY — NEXT PHASE LOCKED

## Active slice

```text
phase: LBE_CLINE_DEPENDENCY_SECURITY_RESOLUTION
slice: RESOLVE_REACHABLE_DIFY_UNDICI_SECURITY_BLOCKER
base_sha: 999a5b623530229e3135780afa89c984ef227aac
required_evidence_level: INTEGRATION
```

## Why this slice exists

The prior governed stdio foundation is functionally proven but checkpointed `UNVERIFIED` because `@cline/agents@0.0.75` imports a reachable transitive Dify dependency branch that resolves vulnerable `@ai-sdk/provider-utils@3.0.32` / `undici@5.29.0` packages.

Evidence already established:

- `@cline/agents@0.0.75` is the latest stable package observed during validation;
- `dify-ai-provider@1.1.1` is the latest published Dify package observed during validation;
- removing `dify-ai-provider` causes `import('@cline/agents')` to fail, proving import-time reachability;
- npm audit reports one moderate and one high transitive vulnerability on that branch;
- no semver-compatible patched Dify/provider-utils v3/undici v5 release exists;
- Cline upstream draft PR #13223 proposes a root override `undici@<6.0.0 -> >=7.29.0 <8` for the same reachable community-provider security class, but the PR is not merged and still requires provider smoke testing.

The upstream PR is evidence for a candidate mitigation, not proof that the mitigation is safe for LBE.

## Existing authority

No runtime authority changes are permitted.

Existing owners remain authoritative:

- Python LBE owns worker lifecycle;
- `resolve_authorization()` owns authorization;
- `GovernedToolOrchestrator.invoke()` owns governed execution and receipts;
- Cline AgentRuntime remains mechanics only;
- LBE session/evidence/validation/completion owners remain canonical.

## Reuse decision

```text
ADAPT
```

Use the smallest dependency-only mitigation consistent with the upstream Cline remediation direction. Do not fork Cline runtime logic or create a replacement provider stack.

## Allowed implementation

Only the following changes are authorized:

1. Add a narrowly scoped worker dependency override for the vulnerable `undici` line, matching the candidate Cline remediation only if the exact local dependency graph accepts it.
2. Generate and validate a deterministic `package-lock.json` from the changed worker dependency contract.
3. Prove the lock resolves no `undici` version inside the audited affected range.
4. Run `npm audit` against the resulting lock and record exact remaining findings.
5. Prove `import('@cline/agents')` still succeeds from the worker directory.
6. Prove the governed Node worker startup/shutdown and focused bridge/orchestrator regressions still pass.
7. Inspect the exact resolved Dify/provider-utils/undici tree after override.
8. Build the Python wheel and prove the worker package metadata, worker source, and canonical lock are included.
9. Record the upstream Cline PR state as supporting evidence only; do not claim upstream approval or merge.
10. Write a bounded checkpoint with PASS only if all required security/integration evidence is satisfied.
11. A temporary GitHub Actions workflow may be added solely to generate and upload the deterministic worker `package-lock.json` artifact from the canonical GitHub `package.json`. It must not edit source, commit automatically, change runtime behavior, or broaden CI authority, and it must be removed after the exact generated lock is committed through the GitHub connector.

## Candidate mitigation under test

```json
{
  "overrides": {
    "undici@<6.0.0": ">=7.29.0 <8"
  }
}
```

This candidate is based on Cline draft PR #13223. Because it crosses an upstream dependency major, it must be proven by LBE-specific install/import/runtime tests before acceptance.

## Required proof

At minimum:

```text
npm install/package-lock generation: PASS
npm ci from generated lock: PASS
npm ls dependency graph: PASS
no resolved undici <= 6.27.0 on the worker graph: PASS
npm audit: zero high/critical findings for this worker dependency graph
@cline/agents direct import: PASS
GovernedClineWorker startup/ready/shutdown: PASS
focused bridge + GovernedToolOrchestrator regression: PASS
implementation gate: PASS
git diff --check: PASS
wheel includes worker.mjs + package.json + package-lock.json: PASS
```

If the override creates peer/dependency incompatibility, runtime regression, import failure, or unresolved high/critical security findings, status is `UNVERIFIED` or `FAIL`; do not suppress the audit.

## Non-goals

- no provider-backed continuation implementation;
- no provider selection expansion;
- no ClineCore adoption;
- no changes to LBE authorization or tool orchestration;
- no MCP work;
- no TUI/CLI UI implementation;
- no `preview.html` implementation;
- no release-ready claim;
- no general dependency modernization beyond the proven blocker.

## Stop rule

After this dependency-security slice reaches its checkpoint, stop. Do not unlock provider continuation or UI work automatically. Any next slice must be separately defined and activated.