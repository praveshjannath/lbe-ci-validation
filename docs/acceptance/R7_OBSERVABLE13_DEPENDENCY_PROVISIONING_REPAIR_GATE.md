# R7 Observable 13 — Installed Cline Dependency Provisioning Repair Gate

Status: **PASS — REPAIR CLOSED — IMPLEMENTATION LOCKED — NEXT OBSERVABLE MAY PROCEED UNDER R7 GATE**

phase: `R7_OBSERVABLE13_REPAIR_IMPLEMENTATION`

slice: `PROVISION_INSTALLED_CLINE_WORKER_DEPENDENCIES`

required_evidence_level: `INTEGRATION_PLUS_ISOLATED_INSTALLED_RUNTIME`

## Trigger

Observable 13 originally proved that the installed `GovernedClineWorker` could not start because the wheel contained `worker.mjs`, `package.json`, and `package-lock.json` but no deterministic installed dependency provisioning for `@cline/agents`.

Direct isolated Node startup failed with:

`ERR_MODULE_NOT_FOUND: Cannot find package '@cline/agents'`

The historical Observable 3 dependency result was insufficient as self-contained installed-runtime proof because its own checkpoint recorded `worker_node_modules_inside_wheel: absent`, while ignored local source `node_modules` existed.

## Implemented repair

The existing worker architecture was preserved. The repair is limited to the Python package build/distribution seam:

- setuptools build materializes the existing locked worker dependency tree using `npm ci`;
- Windows build execution resolves `npm.cmd` explicitly;
- build execution uses `--ignore-scripts --omit=dev --no-audit --no-fund`;
- the resulting production `node_modules` tree is copied into the built wheel;
- CI and Python-runtime publish workflows establish Node 24 before wheel construction;
- no dependency installation occurs during an agent turn;
- no new provider, worker, authorization, tool, session, persistence, receipt, or completion authority was introduced.

Preserved authorities:

- `GovernedClineWorker`
- current stdio protocol
- Cline `AgentRuntime`
- R6C authorization
- R6E `GovernedToolOrchestrator`
- `ToolReceipt`
- session/provider/completion authority
- existing `package.json` / `package-lock.json` dependency contract

## Validation evidence

Sequential installed-runtime validation reached the following results:

```text
branch: main
validated_head_before_probe_fix: b92f63a72c54df78c2b52fe7cdbab62489377ab6
probe_fix_head: c0c3d452dca6eea1371fa394d19d36fafae49769

wheel build: PASS
wheel size: 34,767,299 bytes
dependency files in wheel: 18,635
@cline/agents files in wheel: 7
worker.mjs present: PASS
@cline/agents/package.json present: PASS
memory_schema.sql present: PASS
fresh isolated venv: PASS
exact wheel install: PASS
site-packages origin proof: PASS
installed @cline/agents resolution: PASS
installed CLI smoke: PASS
```

The first full Observable 13 run then reached LBE completion validation and exposed one **test-harness defect**, not a product defect: the probe compared `CompletionDecision.satisfied_requirement_ids` against `evidence_kind`. The canonical completion gate returns persisted completion `requirement_id` values by design while evidence kinds remain a separate field. The probe was corrected only to compare satisfied IDs against persisted requirement IDs and to continue checking evidence kinds independently.

The corrected installed-runtime Observable 13 rerun passed all predicates:

```text
R7_OBS13_SITE_PACKAGES_ISOLATION=PASS
R7_OBS13_SESSION_CREATE=PASS
R7_OBS13_GOVERNED_TOOL_RECEIPT=PASS
R7_OBS13_PROVIDER_COMPLETION_TRUTH_FALSE=PASS
R7_OBS13_CREDENTIAL_HEADER_ONLY_USE=PASS
R7_OBS13_CLI_ENTRYPOINT_RUNS=PASS
R7_OBS13_CONTRACT_REGISTERED=PASS
R7_OBS13_STORE_PERSISTENCE=PASS
R7_OBS13_VALIDATION_READY=PASS
R7_OBS13_COMPLETION_AUTHORITY_LBE_ONLY=PASS
R7_OBS13_CLI_NO_CANARY_LEAK=PASS
R7_OBS13_FRESH_PROCESS_SESSION_RESTORE=PASS
R7_OBS13_FRESH_PROCESS_TASK_RESTORE=PASS
R7_OBS13_FRESH_PROCESS_CONTINUE=PASS
R7_OBS13_EVIDENCE_PERSISTS_FRESH_PROCESS=PASS
R7_OBS13_PERSISTED_STATE_NO_CANARY=PASS
R7_OBS13_SQLITE_RAW_BYTES_CLEAN=PASS
R7_OBS13_SOURCE_UNCHANGED=PASS
R7_OBS13_NO_UNEXPECTED_WORKSPACE_MUTATION=PASS
R7_OBS13_REGRESSION_PROOF=PASS
R7_OBSERVABLE_13=PASS
```

Observable 13 decisive hash:

`A2AC0D1058E3D817DF8E35A1540D6BC89D492C25F7D2D6A3936D54C44BD9A3AE`

## Repair falsifiers result

- isolated installed worker still produces `ERR_MODULE_NOT_FOUND`: **DISPROVEN**;
- dependency resolution reaches the source checkout: **DISPROVEN**;
- install success depends on pre-existing local `node_modules`: **DISPROVEN**;
- an agent turn performs dependency installation: **DISPROVEN**;
- package lock is bypassed or dependency versions become nondeterministic: **NOT OBSERVED**;
- existing LBE authority ownership changes: **DISPROVEN**;
- Observable 13 governed continuation or receipts regress: **DISPROVEN**.

## Result

```text
R7_OBSERVABLE13_REPAIR_IMPLEMENTATION=PASS
R7_OBSERVABLE_13=PASS
implementation_allowed=false
architecture_changes_allowed=false
publish_allowed_now=false
```

This repair gate is closed. Progression returns to the canonical R7 installed end-to-end acceptance gate. Observable 14 may proceed only under that gate's existing predicate and stop rules.
