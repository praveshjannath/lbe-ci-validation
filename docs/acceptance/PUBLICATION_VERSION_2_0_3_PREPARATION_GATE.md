# Publication Version 2.0.3 Preparation Gate

Status: **OPEN — VERSION PREPARATION AUTHORIZED — PUBLISH LOCKED**

phase: `PUBLICATION_VERSION_PREPARATION`

slice: `SET_AND_VALIDATE_CANONICAL_VERSION_2_0_3`

required_evidence_level: `EXACT_VERSION_PLUS_PACKAGE_AND_INSTALLED_RUNTIME_PROOF`

## User authorization

The user explicitly authorized publication and clarified that the intended release version is **`2.0.3`**.

This supersedes the earlier `0.2.0` publication target. It does not authorize publishing before the new canonical version is prepared and validated.

## Exact target

- repository: `Letterblack0306/LBE_Presistent_Agent_wall`
- canonical ref: `main`
- distribution: `lbe-guard-inspector`
- target version: `2.0.3`
- workflow: `.github/workflows/publish-python-runtime.yml`
- environment: `pypi`
- authentication: PyPI trusted publishing through GitHub OIDC

## Proven prerequisites retained

- R7 installed end-to-end acceptance: PASS;
- release/package readiness: PASS for the pre-version-change package state;
- repaired publish workflow derives version from `pyproject.toml`;
- workflow is manual-only;
- GitHub `pypi` environment exists;
- PyPI trusted publisher configuration is user-confirmed for repository `Letterblack0306/LBE_Presistent_Agent_wall`, workflow `publish-python-runtime.yml`, environment `pypi`;
- PyPI currently contains versions `2.0.1` and `2.0.2`.

## Authorized changes

Only the release-version preparation surface is authorized:

1. change `pyproject.toml` project version from `0.2.0` to `2.0.3`;
2. update publication-governance documentation/state to identify `2.0.3` as the sole target;
3. validate the exact `2.0.3` artifact and installed runtime;
4. query PyPI immediately before dispatch and prove `2.0.3` is absent.

No runtime, architecture, provider, authorization, tool, memory, or completion behavior change is authorized.

## Validation requirements

Before publication may be unlocked:

- canonical `main == origin/main`;
- `pyproject.toml` reports exactly `2.0.3`;
- changed paths remain inside the bounded version-preparation scope;
- release packaging tests pass against `2.0.3`;
- wheel filename and installed metadata report `2.0.3`;
- required packaged assets remain present, including memory schema, governed Cline worker, and `@cline/agents` dependency tree;
- installed CLI smoke passes from the exact `2.0.3` wheel;
- PyPI does not already contain `2.0.3` immediately before dispatch;
- tracked source is clean at execution boundary.

## Publish boundary

`publish_allowed_now` remains **false** during this slice.

A PASS on version preparation may advance to the already-authorized single publication execution for `lbe-guard-inspector==2.0.3`. The publish workflow must still be observed to completion and post-publish PyPI state must be verified.

## Forbidden

- publishing `0.2.0`, `2.0.1`, or `2.0.2`;
- publishing before exact `2.0.3` validation passes;
- changing runtime/product behavior as part of the version bump;
- tags or GitHub releases without separate authorization;
- API-token fallback;
- blind retry after a publication failure.
