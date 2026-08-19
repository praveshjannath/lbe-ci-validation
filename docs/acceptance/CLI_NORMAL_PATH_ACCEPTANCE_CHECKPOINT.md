# CLI Normal-Path Acceptance Checkpoint

```text
phase: CLI_NORMAL_PATH_ACCEPTANCE
slice: PROVE_THIN_NONINTERACTIVE_CLI_OVER_ACCEPTED_PERSISTENT_RUNTIME_AUTHORITIES
status: PASS
base_sha: d12f4d20a462047c0c451d8d1d734601fc1d45e9
implementation_sha: NOT_APPLICABLE_ACCEPTANCE_ONLY
acceptance_head: 0cdd2fa025878f591334409237d0dca8bb615a32
required_evidence_level: INTEGRATION
next_phase_locked: true
```

## Requirements

- prove package `lbe` entry point resolves to the existing CLI owner;
- prove session create/continue/status/inspect use canonical persistent state;
- prove provider selection preserves workspace/mode/policy identity;
- prove invalid/missing inputs fail closed;
- prove validation delegates to R6F completion runtime and accepts no CLI-authored evidence;
- prove normal separate-process CLI invocations preserve state;
- run focused CLI/runtime regression;
- record exact evidence, falsifiers, diff and clean-worktree proof.

## Existing owner

```text
pyproject.toml lbe -> lbe_guard_inspector.cli:main
lbe_guard_inspector.cli
SessionMemoryRuntimeBridge
GovernedAgentGateway
EvidenceService
CodingCompletionRuntime
provider registry/runtime adapters
```

## Reuse decision

```text
decision: REUSE
architecture_change: no
runtime_or_test_source_change: no
```

## Validation evidence

```text
source_owner_inspection: PASS
entrypoint_inspection: PASS
repository_cli_baseline: 78 passed
repository_cli_baseline_hash: F99F0C0A9857AA1322E51D60488A42A6FD0D74FB511C47A88EDE154B022486C0
separate_process_session_persistence: PASS
separate_process_session_persistence_hash: 9FFA8D1A831C394B836DC09CA5D7B15F501D5F141F5499BD7A3CAEA3D766E8FB
provider_switch_policy_stability: PASS
separate_process_continue: PASS
provider_switch_continue_hash: C0FCE90E0449A2063EE195634F182D42EAB7BC0646CB291BCC15CE8470DA3437
validation_seed_build: PASS
validation_seed_build_hash: BD93A900026B5A3F592739E54404AAAAAF0D224C65BD2F79A37CF968D13ABD4E
validation_seed_evidence: PASS
validation_seed_evidence_hash: 91B83A5D2A2F4C0C4F99592BBED86DE37959739465F2CD93F26E3B7A5D50DF6D
persisted_completion_validate: PASS
completion_authority_runtime_owned: PASS
persisted_completion_validate_hash: 313468EAD033D330FA260E1A5A50B54A445E8139CE6E2534BD78B51E2B98342B
missing_contract_fail_closed: PASS
missing_contract_hash: E136BE394882256738CCAADF905E034BBA251416F5085C963591ABF47B029CE5
validate_identity_surface: PASS
validate_no_evidence_injection_surface: PASS
validate_help_hash: 8D13866680263DCE566E737BA1E28D5D70115EE95C76C0F5BC1FA93819665CE4
focused_regression: 115 passed
focused_regression_hash: 7E0351B681A14F14264C066EF7809C4092817ABE10D5794B8AE97AB0EB2C85D2
runtime_test_package_source_unchanged: PASS
git_diff_check: PASS
worktree_clean: PASS
acceptance_scope: PASS
```

## Harness failures classified without product patch

```text
50B5B8FCCFC848E1C44A5B637C08D48FB6C34458D0231927B321EBFB45CBABF7: TEST_HARNESS_TRANSPORT_TRUNCATION / POWERSHELL_PARSE_FAILURE
3D0272AC0D21074C1F3F83964EDD72FA017B5D0471748B86DC29FE6C17C15244: TEST_HARNESS_NULL_STDERR_HANDLING
BFCD8ACDC83E4A2CC9174B63DF16BDB30D09CA2E5F18AB9BF9871510C1606B6C: TEST_HARNESS_NULL_OUTPUT_NORMALIZATION
product_falsifier: NONE
```

## Accepted normal path

```text
operator argv
 -> lbe CLI
 -> persistent session/runtime owners
 -> provider/evidence/completion owners
 -> structured output

separate process create
 -> status/inspect
 -> provider select with policy stable
 -> continue/rehydrate
 -> persisted completion contract/evidence
 -> session validate READY
 -> persisted COMPLETED / VALIDATED_COMPLETION
```

## Readiness

```text
release_path_authorized: true
release_publish_allowed_now: false
project_user_ready: NO
release_ready: NO
next_phase_locked: true
remaining_prerequisites:
- R7 installed end-to-end acceptance
- release/package readiness acceptance
```
