# R6A Provider Abstraction Acceptance Checkpoint

```text
phase: R6A_PROVIDER_ABSTRACTION_ACCEPTANCE
slice: PROVE_SAME_SESSION_PROVIDER_SWITCH_WITHOUT_LBE_AUTHORITY_DRIFT
status: PASS

base_sha: 32a987971ff0ea6643f7ea9ff89df7f5132ef850
acceptance_head: 2f33452c5e45f54e5d60ef16c18c59a224011a11
implementation_sha: NOT_APPLICABLE_ACCEPTANCE_ONLY
required_evidence_level: INTEGRATION
next_phase_locked: true
```

## Requirements

- prove provider A and provider B use the existing registered provider/controller path;
- prove equivalent logical requests execute across A -> B in one persisted session/workspace contract;
- preserve session/task/workspace identity and LBE policy/permission state across provider change;
- allow only intended provider/model configuration fields to change;
- preserve provider-neutral LBE request/response/evidence semantics;
- prove no provider-specific governance/session/reasoning owner is introduced;
- run focused provider/session regression on the exact acceptance head;
- record exact evidence, limitations and falsifiers.

## Existing owner

```text
ProviderRegistry
build_provider_controller
reasoning_provider backend contract
LBERequestController
SessionMemoryRuntimeBridge
WorkspaceMemoryStore
```

## Reuse decision

```text
decision: REUSE
evidence: provider composition and persisted session-provider configuration already existed; R6A required combined acceptance only.
```

## Architecture change

```text
introduced: no
runtime_source_changed: no
test_source_changed: no
```

## Decisive integration evidence

LoopTool command hash:

```text
2F16607C4A8807706BAA13114BCD930B21F3728EF4E487F833D6D46DF7558935
```

Observed result on the checked-out workspace package at acceptance head `2f33452c5e45f54e5d60ef16c18c59a224011a11`:

```text
R6A_PROVIDER_A_OUTCOME=COMPLETED
R6A_PROVIDER_B_OUTCOME=COMPLETED
R6A_SESSION_ID=session-r6a
R6A_WORKSPACE_ID=project-r6a
R6A_MODE=coding
R6A_PERMISSION=write_allowed
R6A_RUNTIME_POLICY=development
R6A_PROVIDER_SWITCH=provider-a->provider-b
R6A_TASK_STATUS=completed
R6A_SAME_SESSION_PROVIDER_SWITCH=PASS
R6A_WORKSPACE_BOUND_DIAGNOSTIC=PASS
```

The same logical request passed through both registered providers and the same `LBERequestController`/`SessionMemoryRuntimeBridge` contract. Session ID, project workspace ID, canonical workspace root, task identity, mode, permission, runtime policy, permission policy and evidence policy remained invariant. Provider/model fields changed only from A/model-a to B/model-b.

## Target identity proof

LoopTool command hash:

```text
93A6B4C3301802876F930F48D3B592901163A645FB28CD2F14A3D8DDED4FFB80
```

```text
LBE_PACKAGE=C:\Agents-Memory-Tool-v6-integration\lbe_guard_inspector\__init__.py
RUNTIME_MODULE=C:\Agents-Memory-Tool-v6-integration\lbe_guard_inspector\session_memory_runtime.py
R6A_WORKSPACE_IMPORT_IDENTITY=PASS
```

This invalidated an earlier installed-package harness attempt and bound the decisive proof to the active workspace source.

## Focused regression

LoopTool command hash:

```text
B8801BF25001FF41F76781E2157DC531A720C3889AD7121F724B9D5EF0835EA6
```

The command ended non-zero only after regression because of an invalid `git diff --check` command form. The actual regression result was:

```text
64 passed in 29.15s
R6A_RUNTIME_TEST_SOURCE_UNCHANGED=PASS
```

Covered existing owners:

```text
tests/test_provider_registry.py
tests/test_reasoning_runtime.py
tests/test_request_controller.py
tests/test_session_resume_runtime.py
tests/test_session_memory_runtime.py
```

The later scope-only command supplied the missing Git/diff proof; the regression itself is accepted as PASS rather than relabeled FAIL because its stdout reached 64/64 before the harness syntax error.

## Final scope/worktree proof

LoopTool command hash:

```text
1EB7542A3DF61BD0B39169739782553F5B4AC9738FF2E0403713D8CB7AE3FA94
```

```text
R6A_RUNTIME_TEST_SOURCE_UNCHANGED=PASS
R6A_DIFF_CHECK=PASS
R6A_WORKTREE_CLEAN=PASS
R6A_FOCUSED_REGRESSION_PREVIOUSLY_PROVEN=64_PASSED
R6A_ACCEPTANCE_SCOPE=PASS
## main...origin/main
```

## Harness failures excluded from product evidence

The following diagnostics failed before reaching a valid claim-matched R6A boundary and are not product defects:

```text
40101886... TEST_HARNESS_TRANSPORT_TRUNCATION
770B7AD0... TEST_HARNESS_MODULE_LAYOUT_FAILURE
25200EBD... TEST_HARNESS_TARGET_IDENTITY_FAILURE / installed package
5E808E20... TEST_HARNESS_WORKSPACE_PRECONDITION_FAILURE / synthetic workspace not Git
43C70360... synthetic fixture reached controller but failed UNKNOWN_GUARD because CEP fixture was missing
```

The `UNKNOWN_GUARD` probe established that provider A had been reached once; correcting the missing synthetic `CSXS/manifest.xml` fixture then produced the decisive PASS.

## Falsifier state

```text
observed_falsifier: NONE
provider_switch_changed_session_identity: no
provider_switch_changed_workspace_identity: no
provider_switch_changed_task_identity: no
provider_switch_changed_mode_or_permission_policy: no
provider_bypassed_LBE_controller: no
parallel_provider_or_session_owner_introduced: no
```

## Unverified

```text
none within the bounded R6A acceptance contract
```

This checkpoint does not prove R6B-R6F, CLI normal-path completeness, R7 installed end-to-end completeness, or release/package readiness.

## Document conflicts

```text
none known at closure
```

## Readiness

```text
R6A: PROVEN_COMPLETE
project_user_ready: NO
release_ready: NO
next_phase_locked: true
```
