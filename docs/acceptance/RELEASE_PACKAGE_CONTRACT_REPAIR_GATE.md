# Release Package Contract Repair Gate

Status: **PASS — REPAIR CLOSED — PUBLISH LOCKED — ARCHITECTURE CHANGES FORBIDDEN**

phase: `RELEASE_PACKAGE_CONTRACT_REPAIR`

slice: `ALIGN_PUBLISH_WORKFLOW_WITH_CANONICAL_PACKAGE_METADATA`

required_evidence_level: `WORKFLOW_CONTRACT_PLUS_LOCAL_PACKAGE_PROOF`

## Trigger

The release-readiness audit proved a current distribution-contract conflict:

- canonical `pyproject.toml` declares `lbe-guard-inspector` version `0.2.0`;
- `.github/workflows/publish-python-runtime.yml` hard-coded `2.0.1` in version validation, artifact names, installed-version validation, and its historical push branch trigger;
- current-head packaging tests passed (`2 passed in 1206.98s`) and build/install the current wheel successfully;
- no package/build/runtime files changed between the proven R7 Observable 13 installed-runtime package proof and the release audit state.

The audit command timeout after those tests remains classified `HARNESS_TIMEOUT_AFTER_DECISIVE_TEST_PASS`; it is not a package failure.

## Authorized repair

The repair was limited to the existing Python publication contract:

1. `pyproject.toml` remains the version authority;
2. the workflow derives the version from `pyproject.toml` instead of embedding a historical version;
3. wheel/sdist names and installed metadata are verified using the derived version;
4. the historical `release/python-runtime-v2.0.1` automatic push trigger was removed;
5. explicit `workflow_dispatch` is the only publish trigger;
6. Node 24 setup required by the locked Cline worker build is preserved;
7. the existing PyPI trusted-publishing action and environment are preserved.

## Validation evidence

```text
command_hash: F55FC30C77F746DC035A7D82C3241ADC8552C5B9418F6B390D75EF778FAB3140
HEAD: a99984e812c11b4ecc0dd13514c99d28a6aa4918
ORIGIN_MAIN: a99984e812c11b4ecc0dd13514c99d28a6aa4918
canonical_version: 0.2.0
expected_wheel: lbe_guard_inspector-0.2.0-py3-none-any.whl
expected_sdist: lbe_guard_inspector-0.2.0.tar.gz
version_authority: PASS
stale_2.0.1_removed: PASS
historical_release_branch_removed: PASS
manual_only_trigger: PASS
repair_scope: PASS
tracked_worktree: CLEAN
classification: RELEASE_PACKAGE_CONTRACT_REPAIR=PASS
```

Exact changed paths between audit baseline `a90503b40793e61ef693559070c5ffd5bfa59018` and repaired head were limited to:

- `.github/workflows/publish-python-runtime.yml`
- `.lbe/governance/implementation-gates.json`
- `docs/acceptance/RELEASE_PACKAGE_CONTRACT_REPAIR_GATE.md`

No package version, runtime/provider/tool/authorization/memory/completion source, tag, release, or publication was changed or executed.

## Closed falsifiers

- no literal `2.0.1` remains as the Python artifact/version authority in the workflow;
- the historical release branch is no longer an automatic publication trigger;
- workflow artifact validation derives from `pyproject.toml`;
- the repair did not change package/runtime source or package version;
- no publication occurred during repair validation.

## Result

```text
RELEASE_PACKAGE_CONTRACT_REPAIR: PASS
implementation_allowed_after_closure: false
architecture_changes_allowed: false
publish_allowed_now: false
```

Publication remains locked. Control returns to `RELEASE_PACKAGE_READINESS_ACCEPTANCE` for verification of the repaired current distribution contract before any publication decision.
