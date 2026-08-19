# Publication Precheck Gate

Status: **PASS — REPOSITORY/SERVICE PRECHECK COMPLETE — PYPI TRUST BINDING ONLY PROVABLE DURING REAL PUBLISH — PUBLISH STILL LOCKED**

phase: `PUBLICATION_PRECHECK`

slice: `VERIFY_PYPI_NAMESPACE_VERSION_AND_TRUSTED_PUBLISHING`

required_evidence_level: `LIVE_REGISTRY_PLUS_GITHUB_PUBLISHING_CONFIGURATION`

## Entry condition

`RELEASE_PACKAGE_READINESS_ACCEPTANCE=PASS`.

## Purpose

Determine whether the already-validated canonical Python package may be published without guessing about public registry state or trusted-publishing configuration.

## Canonical package target

- distribution: `lbe-guard-inspector`
- canonical version authority: `pyproject.toml`
- canonical version: `0.2.0`
- publication workflow: `.github/workflows/publish-python-runtime.yml`
- trigger: manual `workflow_dispatch` only

## Decisive live evidence

Publication precheck command hash:

`CB87655106DEB0D947FD03546929CB9B6B0432A2707539C5A3D2B16C8B962D4D`

Proven:

- canonical `main` matched `origin/main`;
- PyPI project `lbe-guard-inspector` exists;
- published PyPI versions are `2.0.1` and `2.0.2`;
- canonical `0.2.0` is not currently published and therefore has no version collision;
- workflow contains `id-token: write`;
- workflow targets GitHub environment `pypi`;
- workflow uses `pypa/gh-action-pypi-publish@release/v1`;
- workflow remains manual-only;
- tracked source remained clean;
- publication was not executed.

Additional authenticated GitHub evidence:

- GitHub environment `pypi` exists;
- historical workflow runs exist, but none completed a successful publication;
- latest historical failure produced no executed workflow steps, so it does not prove or disprove PyPI trusted-publisher binding.

## Trusted-publisher binding limitation

PyPA's current trusted-publishing guidance states that trusted publishing cannot be fully tested in CI without entering the actual publishing flow. Therefore the PyPI-side repository/workflow/environment binding cannot be truthfully promoted to proven before an explicitly authorized real publication attempt.

This is **not** classified as a package defect or repository workflow defect. Repository-side prerequisites are proven. The remaining uncertainty is an external service binding that is only exercised during publication.

## Classification

```text
PUBLICATION_PRECHECK: PASS
PYPI_NAMESPACE_STATE: PRESENT
PYPI_EXISTING_VERSIONS: 2.0.1,2.0.2
CANONICAL_VERSION_0.2.0_COLLISION: NONE
GITHUB_PYPI_ENVIRONMENT: PASS
WORKFLOW_OIDC_CONTRACT: PASS
HISTORICAL_SUCCESSFUL_PUBLISH_RUN: NONE
PYPI_TRUST_BINDING_PRE_PUBLISH_PROOF: NOT_POSSIBLE_WITHOUT_REAL_PUBLISH
PUBLISH_EXECUTION: NOT_PERFORMED
```

## Forbidden after closure

- publishing without separate explicit publication execution authorization;
- changing `pyproject.toml` version by inference;
- creating tags or GitHub releases as a side effect of this closure;
- adding an npm publication path;
- weakening trusted-publishing permissions or environment controls.

## Advancement rule

The next admissible phase is a separate explicit publication execution authorization for exactly:

- project: `lbe-guard-inspector`
- version: `0.2.0`
- workflow: `.github/workflows/publish-python-runtime.yml`
- ref: canonical `main`

Until that authorization exists, `publish_allowed_now` remains `false`.
