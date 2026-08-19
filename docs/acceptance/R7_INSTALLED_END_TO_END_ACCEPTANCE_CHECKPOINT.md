# R7 Installed End-to-End Acceptance Checkpoint

```text
phase: R7_INSTALLED_END_TO_END_ACCEPTANCE
slice: OBSERVABLE_12_CREDENTIAL_SECRET_NON_LEAKAGE
status: OPEN
base_sha: 69c6ae764bc217cd5795ddf8a972658223a681a0
required_evidence_level: INSTALLED_RUNTIME_CREDENTIAL_SECRET_NON_LEAKAGE_PROOF
implementation_allowed: false
next_phase_locked: true
```

## Accepted R7 evidence carried forward

```text
observable 1: PASS
observable 2: PASS
observable 3: PASS_AFTER_REPAIR
observable 4: PASS
observable 5: PASS
observable 6: PASS
observable 7: PASS
observable 8: PASS
observable 9: PASS
observable 10: PASS
observable 11: PASS
  decisive command hash: 6234EA61F2A2E8A8FE962515278B3ED8229EC5B2CD4AB92FFBAABCEAC6D2DA6D
```

## Observable 12 — active

Question:

> Does a synthetic provider credential remain confined to its explicit ephemeral credential input and outbound provider transport header(s), without leaking into runtime/persistence/repository/acceptance surfaces?

Method follows GPT-Knowledge `ai-agents/unified-agent-engineering-methods.md`: establish revision identity, use live runtime proof for security/integration claims, distinguish observation from inference, inspect exact outputs/state, and treat credential configuration separately from evidence/receipts.

### Allowed credential locus

```text
ephemeral disposable provider.json input
outbound provider transport header received by local deterministic provider stub
```

The provider input file is deleted before persistence/file scans. The raw canary must never be printed; only its SHA-256 and transport header name(s) may be emitted as test identity.

### Forbidden leakage surfaces

```text
provider JSON request bodies
CLI stdout/stderr and JSON responses
deterministic_result/provider events
governed R6E ToolReceipt payloads
persisted completion evidence
raw SQLite/state files
workspace/Git files
source checkout files
acceptance docs/scripts/artifacts
```

### First invocation — classified harness assumption

Command hash:

`F92FFB2C41E692FF4B44A2E7EF4E9C94027F69A94148655E19C07F7289B9ACAC`

Observed:

```text
installed package isolation reached
normal provider flow reached two requests
probe expected Authorization: Bearer <canary>
authorization_matches = 0
no target leakage predicate failed before that assertion
```

Classification:

```text
TEST_HARNESS_PROVIDER_HEADER_SHAPE_ASSUMPTION
product secret leak: NOT PROVEN
product credential drop: NOT PROVEN
production patch justified: NO
```

Reason: the acceptance harness assumed the `@cline/agents` provider adapter must serialize `apiKey` specifically as an `Authorization: Bearer` header. The provider/client layer owns exact header serialization. Current primary Cline documentation confirms `apiKey`/`baseUrl` configuration for OpenAI-compatible use but does not make one exact transport-header name an LBE contract.

### Current diagnostic

`scripts/r7_observable12_header_diagnostic.py` performs a bounded local diagnostic over the existing installed observable-12 flow. It scans outbound HTTP **header values** for the runtime-generated canary and reports only matching header **names**. It does not alter installed or production LBE code.

Diagnostic discriminator:

```text
one or more outbound header values contain exact canary
  -> transport credential is proven present; correct acceptance predicate and continue non-leakage proof

no outbound header value contains canary
  -> configured credential was not transmitted; classify as a real provider-transport/configuration falsifier before any patch
```

### Required proof after diagnostic

1. installed package resolves from isolated site-packages;
2. local provider receives the exact synthetic credential in an outbound HTTP transport header on both provider requests;
3. provider JSON bodies do not contain the canary;
4. installed governed coding executes one normal tool-call/continuation flow;
5. CLI output, deterministic result, receipts, and completion evidence do not contain the canary;
6. provider input is deleted, then all remaining disposable persistence files are scanned byte-for-byte for the canary;
7. raw SQLite bytes and state files are clean;
8. workspace files and project source/acceptance surfaces are clean;
9. source worktree remains unchanged;
10. no production/source patch is made unless runtime evidence proves a real leak or credential transport defect.

## Falsifiers

```text
canary in provider JSON body
canary in CLI stdout/stderr
canary in deterministic result or ToolReceipt
canary in completion evidence / SQLite / state files
canary in workspace/source/acceptance files
configured canary absent from every outbound provider HTTP header
```

## Current classification

```text
credential_secret_non_leakage: PENDING_DIAGNOSTIC
implementation_changes: FORBIDDEN
observable_13: LOCKED
release_publish_allowed_now: false
```
