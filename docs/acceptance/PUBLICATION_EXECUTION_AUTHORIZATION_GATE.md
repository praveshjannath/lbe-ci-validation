# Publication Execution Authorization Gate

Status: **AUTHORIZED FOR 2.0.3 — PUBLISH LOCKED PENDING VERSION VALIDATION**

phase: `PUBLICATION_EXECUTION_AUTHORIZATION`

slice: `AUTHORIZE_PYPI_2_0_3_WORKFLOW_DISPATCH`

required_evidence_level: `EXPLICIT_USER_AUTHORIZATION_PLUS_EXACT_VERSION_VALIDATION_PLUS_LIVE_WORKFLOW_EXECUTION`

## Proven prerequisite

`PUBLICATION_PRECHECK=PASS`.

## Exact publication target

- repository: `Letterblack0306/LBE_Presistent_Agent_wall`
- canonical ref: `main`
- distribution: `lbe-guard-inspector`
- version: `2.0.3`
- workflow: `.github/workflows/publish-python-runtime.yml`
- GitHub environment: `pypi`
- authentication: OIDC trusted publishing

## User authorization

The user explicitly authorized publication and then clarified the intended version as **`2.0.3`**. This supersedes the earlier `0.2.0` target.

## Already proven

- release/package readiness: PASS for the pre-version-change package state;
- repaired distribution contract: PASS;
- PyPI namespace exists;
- PyPI versions `2.0.1` and `2.0.2` exist;
- GitHub `pypi` environment exists;
- workflow OIDC contract is present;
- workflow is manual-only;
- PyPI trusted publisher configuration is confirmed for repository `Letterblack0306/LBE_Presistent_Agent_wall`, workflow `publish-python-runtime.yml`, environment `pypi`.

## Remaining validation before dispatch

The canonical version must first be prepared and validated as `2.0.3` under `docs/acceptance/PUBLICATION_VERSION_2_0_3_PREPARATION_GATE.md`.

No workflow dispatch is permitted until that gate passes.

## Execution requirements after version validation

1. re-confirm `main == origin/main`;
2. re-confirm canonical version is exactly `2.0.3`;
3. re-query PyPI and prove `2.0.3` is still absent immediately before dispatch;
4. dispatch only `.github/workflows/publish-python-runtime.yml` on `main`;
5. observe the exact workflow run to completion;
6. if any step fails, stop and classify the failure; do not retry blindly;
7. if publish succeeds, query PyPI and prove `2.0.3` exists;
8. record workflow run ID, commit SHA, published artifact state, and final gate closure.

## Forbidden

- publication of any version other than `2.0.3`;
- publication before exact-version validation;
- alternate branches/worktrees;
- API-token fallback without a separate authorized security decision;
- repeated publish attempts after a failure without diagnosis;
- tags or GitHub releases unless separately authorized.
