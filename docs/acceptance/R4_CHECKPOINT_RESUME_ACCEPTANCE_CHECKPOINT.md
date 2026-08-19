# R4 Checkpoint Resume Acceptance Checkpoint

```text
phase: R4_CHECKPOINT_RESUME_ACCEPTANCE
slice: PROVE_CHECKPOINT_RESTART_REHYDRATION_AND_STALE_STATE_INVALIDATION
status: PASS

base_sha: 9523cf02f8a2e9248ad87d7f6f4cadef6d959f51
implementation_sha: NOT_APPLICABLE_ACCEPTANCE_ONLY
acceptance_head: 7369ae41311870866a919092c59d13d02a99c942
required_evidence_level: INTEGRATION
next_phase_locked: true
```

## Requirements

- prove checkpoint/restart/resume through existing `SessionMemoryRuntimeBridge` and `SessionMemoryAdapter`;
- preserve session/task/workspace identity and persisted provider/session configuration;
- prove active checkpoint constraints survive restart;
- prove external source/Git changes are re-inspected on resume;
- prove old source-backed facts become `STALE` and are removed from resumed `verified_facts`;
- prove changed HEAD makes the protected checkpoint `INELIGIBLE` with `reactivation_allowed=false`;
- prove compaction/history material is not promoted into current workspace truth;
- introduce no runtime/checkpoint/memory source changes unless a real defect is first proven;
- run focused R4/session-memory regression on the exact acceptance head;
- record exact evidence and falsifiers.

## Existing owner

```text
SessionMemoryRuntimeBridge.start_or_resume
SessionMemoryAdapter.checkpoint_compaction / rehydrate
memory.context.invalidate_changed_sources
memory.context.protected_checkpoint_eligibility
memory.context.rehydrate_context
WorkspaceMemoryStore
```

## Reuse decision

```text
decision: REUSE
evidence: current source/tests already contain the R4 path; missing artifact was dedicated roadmap acceptance evidence.
```

## Architecture change

```text
introduced: no
user_authorized: no new architecture requested
canonical_docs_updated_first: yes
```

## Validation evidence

```text
workspace_gate_identity:
  PASS
  command_hash: 274E71C81BDC6B6BF9B701B5679B2ED9A7824EE4A66D9CB7ECDAD1CB640915C2
  head: 7369ae41311870866a919092c59d13d02a99c942
  origin_main: 7369ae41311870866a919092c59d13d02a99c942
  branch: main
  worktree: clean

source_owner_inspection: PASS

checkpoint_change_restart_integration:
  PASS
  repository_test: tests/test_session_resume_runtime.py::test_resume_invalidates_changed_source_fact_and_reports_changed_head
  command_hash: 75671F43AA1BE3A1DA1F67BFC34CFD39CD30326FC3AEA1CCE5C55393DF66A779

session_task_workspace_identity: PASS
constraint_survival: PASS
changed_head_revalidation: PASS
stale_source_fact_invalidation: PASS
stale_fact_removed_from_verified_context: PASS
provider_session_preservation: PASS

compaction_not_current_truth:
  PASS_SOURCE_CONTRACT
  evidence:
    - SessionMemoryAdapter accepts structured deterministic evidence only and does not parse assistant prose or compaction summaries into verified workspace facts.
    - rehydrate_context loads only VERIFIED records, revalidates source hashes, and emits the explicit rule: `Do not use assistant reasoning or compaction summaries as authority.`
    - checkpoint payload contains structured checkpoint metadata/constraints, not assistant compaction prose as current workspace truth.

focused_regression:
  PASS
  command_hash: DDF73255339D42EE149AC6D15920AA108F40FDB530738A1364268A9E2806B9DD
  command: python -m pytest -q tests/test_session_resume_runtime.py tests/test_session_memory_runtime.py tests/test_session_memory_adapter.py tests/test_checkpoint_eligibility.py
  result: 37 passed in 34.45s

broader_regression_classification:
  NOT_REQUIRED_FOR_R4_ACCEPTANCE_CLOSURE
  rationale: acceptance-only slice changed no runtime/test implementation; focused suites cover the existing R4 owners and the decisive external-change resume path.

runtime_or_test_source_changes: NONE
git_diff_check: PENDING_FINAL_SYNC
worktree_clean: PASS_AT_ACCEPTANCE_HEAD
```

## Harness failures observed

Two earlier ad hoc embedded-Python LoopTool probes failed before product behavior executed because command transport corrupted Python quoting/indentation.

```text
classification: TEST_HARNESS_TRANSPORT_FAILURE
product/runtime implication: none
```

These failures were not used as R4 product evidence. The method was corrected by switching to repository-owned tests.

## Falsifier state

```text
observed_falsifier: NONE
```

The decisive repository-owned integration test proved the opposite of the R4 falsifiers: changed source evidence did not remain current, changed HEAD was surfaced as a mismatch, the checkpoint became ineligible, and the active task/constraint survived reconstruction.

## Unverified

- overall project/user readiness;
- R5 and later roadmap families;
- installed-path R7 resume workflow.

These are outside the R4 acceptance slice.

## Document conflicts

```text
none known after R4 closure update
```

## Readiness

```text
R4_checkpoint_resume_rehydration: PROVEN_COMPLETE
project_user_ready: NO
release_ready: NO
next_phase_locked: true
```
