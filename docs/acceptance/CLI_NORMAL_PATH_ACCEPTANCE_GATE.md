# CLI Normal-Path Acceptance Gate

Status: **PASS — PROVEN_COMPLETE — RELEASE PATH ACTIVE — NEXT PHASE LOCKED**

```text
phase: CLI_NORMAL_PATH_ACCEPTANCE
slice: PROVE_THIN_NONINTERACTIVE_CLI_OVER_ACCEPTED_PERSISTENT_RUNTIME_AUTHORITIES
base_sha: d12f4d20a462047c0c451d8d1d734601fc1d45e9
acceptance_head: 0cdd2fa025878f591334409237d0dca8bb615a32
implementation_allowed: false
architecture_changes_allowed: false
next_phase_locked: true
required_evidence_level: INTEGRATION
release_path_authorized: true
publish_allowed_now: false
status: PASS
```

## Accepted question

The existing non-interactive `lbe` CLI is proven as a thin persistent control surface over accepted runtime authorities. It preserves persistent session/workspace identity across separate processes, changes provider/model without policy drift, delegates completion to the R6F owner, fails closed for missing completion state, and exposes no CLI completion-evidence injection surface.

## Existing owner and reuse decision

```text
pyproject.toml [project.scripts] lbe -> lbe_guard_inspector.cli:main
lbe_guard_inspector.cli
SessionMemoryRuntimeBridge
GovernedAgentGateway
EvidenceService
provider registry/runtime adapters
CodingCompletionRuntime
reuse: REUSE
new authority introduced: no
```

## Decisive evidence

```text
repository baseline: 78 passed
hash: F99F0C0A9857AA1322E51D60488A42A6FD0D74FB511C47A88EDE154B022486C0

separate-process session persistence: PASS
hash: 9FFA8D1A831C394B836DC09CA5D7B15F501D5F141F5499BD7A3CAEA3D766E8FB

provider switch policy stability + continue: PASS
hash: C0FCE90E0449A2063EE195634F182D42EAB7BC0646CB291BCC15CE8470DA3437

persisted completion validation: PASS
completion authority remains runtime-owned: PASS
hash: 313468EAD033D330FA260E1A5A50B54A445E8139CE6E2534BD78B51E2B98342B

missing completion contract fail-closed: PASS
hash: E136BE394882256738CCAADF905E034BBA251416F5085C963591ABF47B029CE5

no completion-evidence injection surface: PASS
hash: 8D13866680263DCE566E737BA1E28D5D70115EE95C76C0F5BC1FA93819665CE4

focused regression: 115 passed
hash: 7E0351B681A14F14264C066EF7809C4092817ABE10D5794B8AE97AB0EB2C85D2

runtime/test/package source unchanged: PASS
diff check: PASS
worktree clean: PASS
acceptance scope: PASS
observed product falsifier: NONE
```

## Harness failures

Three failed diagnostic commands were classified as harness failures only: one PowerShell transport truncation/parser failure and two null-output wrapper failures. None executed evidence sufficient to falsify CLI behavior; no product source was patched from them.

## Accepted invariant

```text
CLI accepts operator intent and identity inputs.
Persistent runtime owns session/workspace state.
Provider adapters own provider mechanics.
Evidence owners supply evidence.
R6F completion runtime owns terminal completion truth.
CLI only projects structured results.
```

## Release boundary

```text
CLI_NORMAL_PATH_ACCEPTANCE: PASS / PROVEN_COMPLETE
R7: still required
release/package readiness: still required
publish_allowed_now: false
next_phase_locked: true
```

PASS does not auto-activate R7 and does not authorize version bump, tag, package publish, or external release publication.
