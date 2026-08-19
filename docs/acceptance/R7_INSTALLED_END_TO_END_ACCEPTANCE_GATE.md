# R7 Installed End-to-End Acceptance Gate

Status: **PASS — R7 INSTALLED END-TO-END ACCEPTANCE COMPLETE — RELEASE/PUBLISH STILL LOCKED**

```text
phase: R7_INSTALLED_END_TO_END_ACCEPTANCE
slice: R7_ACCEPTANCE_COMPLETE
base_sha: 69c6ae764bc217cd5795ddf8a972658223a681a0
original_activation_sha: 401a4f184fcbeae5ff6e4d58be139515b9861ed2
resume_after_repair: true
status: PASS
implementation_allowed: false
architecture_changes_allowed: false
next_phase_locked: true
release_path_authorized: true
publish_allowed_now: false
```

## Acceptance result

R7 installed end-to-end acceptance is complete.

Accepted observables:

1. exact-head isolated install without source leakage — `PASS`;
2. persistent installed session identity — `PASS`;
3. governed installed coding execution/receipts — `PASS_AFTER_REPAIR`;
4. provider/model switch preserves workspace, mode, permission, profile, evidence policy, and LBE authority identity — `PASS`;
5. fresh installed process resumes the same persistent session/task identity — `PASS`;
6. bounded external workspace change is observed/revalidated rather than stale checkpoint state — `PASS`;
7. audit/investigation cannot mutate workspace state — `PASS`;
8. out-of-workspace/forbidden/out-of-authority action fails closed without mutation — `PASS`;
9. receipt/provider continuation correlation remains intact — `PASS`;
10. provider completion remains provisional until deterministic persisted validation — `PASS`;
11. terminal `COMPLETED / VALIDATED_COMPLETION` persists across a fresh process — `PASS`;
12. no credential/secret leakage into repo/logs/receipts/artifacts — `PASS`;
13. focused installed/runtime regression with exact package/head/environment evidence — `PASS_AFTER_REPAIR`;
14. source remains unchanged unless a real falsifier activates a separate repair slice — `PASS`;
15. clean worktree plus exact limitations/falsifiers — `PASS`.

## Decisive evidence

```text
observable 3 decisive hash:
F3FB75C252CB7B561C05A233D4F93FC981032A0DAF41F9B90E9952FB9677F882

observable 4 decisive hash:
E0CB10D5EE683C0485D44AB7FC51A17591716D3BB2EF62F77E2A48D6559E97E6

observable 5 decisive hash:
EDAB5DB0FB2667F241AEB1BC1F90832759C085AEDD984BD6BE09561F5F9C8376

observable 6 decisive hash:
4B11427423FE60EFD1E77271A424390F2E91813A9A1E80E961A3C5FDF0BB78CC

observable 11 decisive hash:
6234EA61F2A2E8A8FE962515278B3ED8229EC5B2CD4AB92FFBAABCEAC6D2DA6D

observable 13 decisive hash:
A2AC0D1058E3D817DF8E35A1540D6BC89D492C25F7D2D6A3936D54C44BD9A3AE

observable 14 decisive hash:
ED2E9D5763EEB5C57B073C002D616B3DC4298C067D5EFDBE3D463088E74DD054

observable 15 decisive hash:
1EA6416387E3A1AF9F2ABEC5CFA84ED414CDBCB11793C13AAB6FE34B00BE6919
```

## Repaired Observable 13

Observable 13 initially exposed a real installed-package defect: the Python wheel contained the Cline worker entry files but did not provision the locked `@cline/agents` dependency tree into the installed runtime. The bounded repair retained the existing `GovernedClineWorker`, stdio protocol, Cline `AgentRuntime`, R6C/R6E authority owners, and completion ownership while adding deterministic build-time dependency provisioning from the existing worker lockfile.

The repaired wheel then proved:

- isolated `site-packages` origin;
- locked worker dependency tree inside the wheel;
- installed `@cline/agents` resolution without source-tree `node_modules`;
- governed provider/tool/final continuation;
- executed `ToolReceipt` persistence;
- LBE-only completion authority;
- fresh-process session/task restoration;
- credential non-leakage;
- no unexpected workspace mutation;
- canonical source unchanged.

The intermediate completion assertion failure after the repair was a harness defect: the probe compared `CompletionDecision.satisfied_requirement_ids` against contract `evidence_kind` values. The canonical runtime correctly returns `requirement_id` values. Only the probe was corrected.

## Observable 14 result

Observable 14 proved:

- canonical branch remained `main`;
- `HEAD == origin/main`;
- implementation remained locked;
- architecture changes remained locked;
- tracked canonical source remained unchanged;
- generated validation evidence remained untracked and separately reported.

The first Observable 14 command incorrectly invoked `scripts/check-implementation-gate.py` as a read-only runtime validator. That checker is a staging/commit gate when implementation is locked. The failure was therefore classified as harness-only and did not authorize source changes.

## Observable 15 result

Observable 15 proved:

- canonical branch remained `main`;
- `HEAD == origin/main`;
- tracked worktree was clean;
- remaining untracked artifacts were enumerated and classified as generated validation evidence or standalone documentation instruction material;
- implementation remained locked;
- architecture changes remained locked;
- exact limitations were present in this acceptance record;
- publish readiness remained locked.

Observed untracked categories at closure included:

```text
.observable13_fresh_wheel/
.observable13_pipeline/
.observable13_scratch/
LBE Documentation-Only Correction Instruction.md
```

These are not accepted product source.

## Exact remaining limitations after R7

```text
R7 proves the accepted installed-runtime behaviors only for the bounded evidence and environments exercised by its observables.
The repaired Python wheel carries the locked Cline worker dependency tree; this increases wheel size and requires the package build environment to provide the declared Node runtime/npm build dependency path.
Generated local validation directories and the standalone documentation instruction file are not accepted product source and remain outside canonical tracked source state.
R7 acceptance is not release/package readiness acceptance and does not authorize versioning, tagging, or publishing.
publish_allowed_now remains false until a separate release/package readiness acceptance passes.
```

## Remaining falsifiers

A later result must reopen a bounded repair/review gate rather than silently modifying accepted source if it proves any of the following:

- installed package source leakage;
- persistent session/task identity loss;
- mutation outside governed R6C/R6E execution;
- missing or unpersisted receipts;
- provider/model switch changing LBE authority identity;
- stale evidence accepted after external workspace change;
- audit/investigation mutation;
- out-of-authority execution that does not fail closed;
- provider completion becoming authoritative without deterministic validation;
- credential/secret leakage;
- installed Cline worker dependency resolution depending on source-tree state;
- tracked source mutation caused by acceptance execution itself;
- release or publish readiness being claimed without separate package/release acceptance.

## Closure rule

R7 is closed `PASS`.

No implementation, architecture, version, tag, release, or publish work is authorized merely by this closure. The only remaining progression prerequisite recorded by this gate is a **separate release/package readiness acceptance**. That next phase remains locked until explicitly activated under its own gate.
