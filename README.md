# LBE Guard Inspector

This package provides deterministic, evidence-bound workspace inspection. It
does not modify the audited workspace or generate repairs.

## Release contract

- Python: 3.11 or later.
- Network surface: local-only by default (`127.0.0.1`).
- Stable inspection endpoints: `POST /guard-inspector/callback` and
  `POST /guard-inspector/module-registry`.
- Stable commands: `lbe-guard-inspector` for the fixed inspection endpoints,
  `lbe-guard-inspector-evidence` for the evidence API, and
  `lbe-guard-audit` for the deterministic project-scoped audit controller.
- Runtime configuration is explicit. Set
  `LBE_GUARD_INSPECTOR_CONFIG_PATH`,
  `LBE_GUARD_INSPECTOR_GOVERNANCE_PATH`, and
  `LBE_GUARD_INSPECTOR_STATE_DIR` for an installed package; absent variables
  preserve the repository-local defaults.

The package includes:

- five JSON Schema contracts;
- runtime JSON Schema validation;
- a read-only SQLite retrieval adapter;
- `POST /evidence-package`;
- `POST /guard-result` — evidence-bound Guard Inspector evaluation layer;
- archive/build/backup exclusion;
- exact path, hash, snippet, line range, score, authority, and verification metadata;
- evidence-policy enforcement that maps a deterministic rule result plus the
  current evidence package to a `guard_result` verdict
  (`PASS` / `FAIL` / `INSUFFICIENT_EVIDENCE` / `NOT_APPLICABLE`);
- `POST /guard-run` — the full vertical slice: select a registered guard,
  execute it against the workspace, run validation, and produce the verdict
  from the original problem request;
- tests proving schema enforcement, exclusion behavior, verdict mapping, and
  the full guard vertical slice (65 passed as of current HEAD).

## Files

```text
schemas/
  task_record.schema.json
  evidence_package.schema.json
  guard_request.schema.json
  guard_result.schema.json
  rule_proposal.schema.json

lbe_guard_inspector/
  contracts.py
  config.py
  evidence_service.py
  guard_inspector.py
  guard_runner.py
  server.py

tests/
  test_contracts.py
  test_evidence_service.py
  test_guard_inspector.py
  test_guard_runner.py
```

## Install

```powershell
Set-Location "<repo-path>"
python -m pip install .
Copy-Item .\config.example.json .\config.json
```

Edit `config.json` and set `database_path`.

The adapter automatically discovers a table containing path and content columns. For deterministic production use, configure the exact table and column names.

For an installed package, keep runtime configuration outside `site-packages`:

```powershell
$env:LBE_GUARD_INSPECTOR_CONFIG_PATH = "C:\\GuardInspector\\config.json"
$env:LBE_GUARD_INSPECTOR_GOVERNANCE_PATH = "C:\\GuardInspector\\governance.json"
$env:LBE_GUARD_INSPECTOR_STATE_DIR = "C:\\GuardInspector\\state"
lbe-guard-inspector
```

Run a project-scoped audit with an explicit current workspace root:

```powershell
lbe-guard-audit audit --workspace-root "C:\\Projects\\target-project"
```

## Test

```powershell
python -m pytest -q
```

Latest run: **65 passed** (0.32 s).

## Run

```powershell
python -m lbe_guard_inspector.server --config .\config.json --port 8766
```

## Health

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8766/health"
```

## Create evidence package

```powershell
$body = @{
    problem = "Provided callback is not a function"
    workspace_id = "cep-project"
    mode = "inspect"
    max_results = 10
} | ConvertTo-Json

Invoke-RestMethod `
    -Method Post `
    -Uri "http://127.0.0.1:8766/evidence-package" `
    -ContentType "application/json" `
    -Body $body
```

## Evaluate a guard result

`POST /guard-result` takes the outcome of an existing registered deterministic
rule (`rule_result`) plus the current `evidence_package` and returns a
`guard_result` contract. The mapping is **not** a blind rename — an evidence
policy gates every promotion to a workspace compliance verdict.

```text
existing registered deterministic rule (rule_result)
        ↓
current evidence package
        ↓
evidence-policy enforcement
        ↓
guard_result contract
        ↓
PASS / FAIL / INSUFFICIENT_EVIDENCE / NOT_APPLICABLE
```

Mapping rules enforced by `lbe_guard_inspector.guard_inspector.GuardInspector`:

- `passed → PASS` only when current workspace evidence refs support it, there
  are no contradictions, and validation refs are present;
- `failed → FAIL` only when current workspace evidence refs support it;
- `blocked → INSUFFICIENT_EVIDENCE`;
- `not_applicable → NOT_APPLICABLE`;
- indexed-only rule results (e.g. `generic.index_present`) can never become
  `PASS` or `FAIL` — they cannot claim a workspace compliance verdict;
- any rule result lacking current workspace evidence refs is downgraded to
  `INSUFFICIENT_EVIDENCE`;
- contradictions between indexed and workspace evidence prevent an
  unsupported `PASS`.

```powershell
$body = @{
    rule_result = @{
        rule_id = "cep.manifest_exists"
        status  = "passed"
        message = "CEP manifest.xml is present."
        evidence = @{ path = "CEP_Project/CSXS/manifest.xml" }
    }
    evidence_package = @{
        package_id         = "ep-1"
        task_id            = "task-1"
        query              = "Provided callback is not a function"
        workspace_id       = "cep-project"
        indexed_reference_evidence   = @()
        current_workspace_evidence = @(
            @{ ref = "workspace:cep-project:src/panel.js"; source_type = "workspace"; authority = 2; verified = $true; classification = "current_workspace" }
        )
        validation_evidence = @(
            @{ ref = "validation:manifest-schema:1"; source_type = "validation"; authority = 5; verified = $true; classification = "validation" }
        )
        contradictions = @()
        missing_evidence = @()
        generated_at   = "2026-07-25T00:00:00+00:00"
    }
} | ConvertTo-Json -Depth 10

Invoke-RestMethod `
    -Method Post `
    -Uri "http://127.0.0.1:8766/guard-result" `
    -ContentType "application/json" `
    -Body $body
```

## Run the full vertical slice

`POST /guard-run` implements the Phase 2 vertical slice from the original
problem request, reusing the existing deterministic rule-execution
infrastructure (`audit_controller` + `rules/`):

```text
user problem
        ↓
search  (agent.search_workspace)
        ↓
evidence package  (EvidenceService)
        ↓
guard selection  (audit_controller.resolve_rule)
        ↓
guard execution against the workspace  (audit_controller.run_rule)
        ↓
validation  (independent inspect_file corroboration)
        ↓
LBE decision context  (GuardInspector.evaluate)
        ↓
verdict  (PASS / FAIL / INSUFFICIENT_EVIDENCE / NOT_APPLICABLE)
```

Unlike `POST /guard-result` (which accepts a supplied `rule_result`), this
endpoint *selects* a registered guard by `pack_id` + `rule_id`, *executes* it
against the workspace, *runs validation*, and *produces the verdict* from the
original problem. The response carries the full decision context: `task`,
`evidence_package` (with injected `validation_evidence`), `rule_result`, and
`guard_result`.

```powershell
$body = @{
    problem       = "Provided callback is not a function"
    workspace_id  = "cep-project"
    workspace_root = "G:\Developments\CEP_Project"
    pack_id       = "cep"
    rule_id       = "cep.manifest_exists"
    extensions    = @(".xml")
    max_results   = 10
} | ConvertTo-Json -Depth 6

Invoke-RestMethod `
    -Method Post `
    -Uri "http://127.0.0.1:8766/guard-run" `
    -ContentType "application/json" `
    -Body $body
```

## Phase boundary

This package does not:

- run a reasoning model;
- modify a workspace;
- create permanent rules;
- promote memory.

### Handoff status

Older deterministic rule execution infrastructure already exists in
`audit_controller.py` and `rules/`. The Drive source confirms the contradiction
files were modified recently, while the existing rules predate the new
evidence-package layer.

The new evidence-bound Guard Inspector evaluation layer is now integrated into
a full read-only vertical slice:

- `lbe_guard_inspector/guard_inspector.py` maps a registered rule's
  `RuleResult` plus the current evidence package to a `guard_result` verdict
  under evidence-policy enforcement;
- `lbe_guard_inspector/guard_runner.py` selects and executes a registered guard
  (`audit_controller.resolve_rule` / `run_rule`), builds the current evidence
  package, runs validation, and produces the verdict from the original problem
  request — exposed at `POST /guard-run`.

It proves typed contracts, read-only indexed evidence packaging,
evidence-bound verdict mapping, and the full guard vertical slice. The known
"search re-reads source files every time" gap (see `BASELINE_VALIDATION.md`)
still makes live searches over large network roots slow; slice tests therefore
inject fakes, and live `/guard-run` validation uses an empty extension scope to
exercise the real stack without re-reading 80k+ files.
