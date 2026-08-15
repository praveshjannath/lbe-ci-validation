# Current Status Routing

`docs/CURRENT_STATUS.md` is a historical July-era snapshot and must not be used by itself for current product, CLI, C5/R7, package, npm-distribution, or post-V1 professional-agent decisions.

## Active product priority

The main post-V1 product pillar is now:

`docs/design/PROFESSIONAL_AGENT_RUNTIME_PRODUCT_PILLAR.md`

Status: **AUTHORITATIVE PRODUCT PILLAR — ACTIVE PRIORITY**

The canonical forward implementation plan is:

`docs/design/PROFESSIONAL_AGENT_RUNTIME_CANONICAL_IMPLEMENTATION_PLAN.md`

Status: **AUTHORITATIVE FORWARD IMPLEMENTATION PLAN — ACTIVE**

The immediate P0/P1 implementation gate is:

`docs/design/PROFESSIONAL_AGENT_RUNTIME_P0_P1_IMPLEMENTATION_GATE.md`

Status: **AUTHORITATIVE IMPLEMENTATION GATE — ACTIVE**

The provider-mapping/authorization correction companion is:

`docs/design/PROFESSIONAL_AGENT_RUNTIME_P0_P1_PROVIDER_MAPPING_AND_AUTHORIZATION_CORRECTIONS.md`

Status: **AUTHORITATIVE COMPANION CORRECTION — ACTIVE**

The canonical plan is maintained independently from any one local-agent plan. Local-agent plans, runtime traces, external reviews, and provider research are comparison inputs. Current source/runtime evidence and current primary provider/API evidence outrank either plan when a conflict appears.

The P0/P1 gate exists specifically to prevent premature implementation of a generic `RuntimeEvent` / `EventRecorder` before provider-native event semantics, provider/model capability semantics, runtime capability semantics, and effective session capability projection are defined.

This pillar starts now. It defines the forward implementation priority for provider-native events, capability negotiation, professional tools, persistent agent interaction, terminal/process execution, Git/worktrees, agent-control protocol, MCP, IDE integration, and the eventual professional CLI/TUI.

The existing persistent runtime, C5/R7 acceptance, provider adapters, package release, npm bootstrap, and global project profiling remain accepted foundations. They must not be mistaken for the complete professional product.

For current work, read in this order:

1. `docs/design/PROFESSIONAL_AGENT_RUNTIME_PRODUCT_PILLAR.md` — primary post-V1 product direction and implementation priority.
2. `docs/design/PROFESSIONAL_AGENT_RUNTIME_CANONICAL_IMPLEMENTATION_PLAN.md` — independent GitHub-grounded forward plan and cross-plan comparison protocol.
3. `docs/design/PROFESSIONAL_AGENT_RUNTIME_P0_P1_IMPLEMENTATION_GATE.md` — immediate implementation gate; P0 provider event normalization and P1 professional runtime capability contract must be reviewed before P2 or Session/Turn/Item event implementation.
4. `docs/design/PROFESSIONAL_AGENT_RUNTIME_P0_P1_PROVIDER_MAPPING_AND_AUTHORIZATION_CORRECTIONS.md` — exact provider-mapping and R6C authorization corrections controlling conflicting earlier P0/P1 drafts.
5. `docs/design/PROFESSIONAL_AGENT_RUNTIME_CLINE_REUSE_DIRECTION.md` — mandatory P3/P7 Cline lower-layer evaluation and LBE authority boundary.
6. `docs/research/POST_V1_PROFESSIONAL_AGENT_CLI_PROVIDER_RUNTIME_RESEARCH.md` — provider/runtime/CLI research evidence underlying the pillar.
7. `docs/design/LBE_AGENT_RUNTIME_CLI_TUI_AND_TOOL_ACCESS_SPEC.md` — agent interaction and governed tool-access design gate.
8. `docs/design/LBE_AGENT_RUNTIME_USER_STEERING_EXTERNAL_CLIENT_AND_CONTROL_PROTOCOL_ADDENDUM.md` — active user steering, external-agent boundary, MCP vs control protocol, provenance.
9. `README.md` — current CLI-first product identity and user-facing architecture.
10. `docs/IMPLEMENTATION_PLAN.md` — established persistent-runtime architecture and implementation history; reconcile it with the professional-agent pillar/canonical plan for new post-V1 work.
11. `docs/acceptance/C5_R7_ACCEPTANCE_RECORD.md` — accepted persistent-runtime V1 proof record.
12. `docs/acceptance/POST_V1_RELEASE_PACKAGE_READINESS.md` — Python package/install readiness.
13. `docs/acceptance/POST_V1_NPM_CONSUMER_DISTRIBUTION_READINESS.md` — npm bootstrap/public-consumer release evidence.
14. current Git/source/runtime/provider/registry evidence.

Current distribution routing remains:

```text
npm / npx
  -> @letterblack/lbe
  -> thin Node bootstrap / launcher
  -> managed Python LBE runtime
  -> `lbe` CLI
```

The distribution path is not the complete professional-agent architecture. The professional runtime direction is:

```text
provider-native stream
  -> provider adapter
  -> normalized LBE model events
  -> persistent Session / Turn / Item runtime
  -> capability negotiation + LBE authorization
  -> governed professional tools
  -> live runtime/tool events
  -> provider continuation
  -> evidence / validation / completion
  -> agent-control protocol / MCP / IDE bridge
  -> CLI/TUI / GUI / IDE / automation / external agents
```

The historical Guard Inspector service/read-only commands remain compatibility and implementation surfaces, but they are no longer the complete product identity or the primary user control surface.

Do not route new product work through old `lbe-core`/Core-package assumptions unless a specific historical component is actually in scope. Python LBE remains the sole runtime/governance authority.

## Immediate implementation order

The next work is **not** TUI styling and not another shallow provider-name adapter.

Required active sequence:

```text
P0 provider event normalization contract
P1 professional runtime capability contract
P2 provider/model capability negotiation and probes
P3 provider-native streaming/tool-call adapters
P4 normalized Session / Turn / Item persistence
P5 professional workspace/Git/terminal capability foundation
P6 live tool/process execution events
P7 governed provider continuation loop
P8 bidirectional agent-control protocol
P9 replay/resume/fork proof
P10 MCP external-agent surface
P11 transcript projection
P12 professional interactive TUI
P13 IDE bridge / richer client integration
P14 browser capability integration
P15 cooperative and strict external-agent acceptance
P16 professional end-to-end acceptance
```

## Evidence-level acceptance control

Every unproven capability begins as `UNVERIFIED`. A status may change to `PASS`
only when its recorded evidence meets or exceeds the capability's required
evidence level. Implementation presence, handler existence, and a lower-level
test are not substitutes for a higher-level proof claim.

| Evidence level | What it proves |
| --- | --- |
| `UNIT` | Isolated behavior of the named unit only. |
| `INTEGRATION` | Interaction among the named components only. |
| `INSTALLED` | The packaged, installed execution path. |
| `LIVE_RUNTIME` | A real configured runtime/provider/tool interaction. |
| `USER_FLOW` | A complete user-facing interaction through the real control path. |
| `RELEASE` | Distribution, fresh install, and release smoke requirements. |

Each active acceptance matrix row must record: capability, status, current
evidence, evidence level achieved, required evidence level, source/command or
receipt, and remaining proof gap. It must not inherit `PASS` from a related
capability.

| Capability | Initial status | Minimum required evidence level |
| --- | --- | --- |
| Session task and steering | `UNVERIFIED` | `LIVE_RUNTIME` |
| Interrupt and cancel | `UNVERIFIED` | `LIVE_RUNTIME` |
| Provider selection/switch | `UNVERIFIED` | `INSTALLED` + `LIVE_RUNTIME` |
| Approval response and governed action | `UNVERIFIED` | `USER_FLOW` |
| Transcript replay/resume | `UNVERIFIED` | `USER_FLOW` |
| CLI/TUI interactive command surface | `UNVERIFIED` | `USER_FLOW` |
| Python-version support | `UNVERIFIED` | `INSTALLED` + full relevant suite |
| Package publication/installability | `UNVERIFIED` | `RELEASE` |

Release readiness is supported only after every required scope row is `PASS`
at its own required level. It is never inferred from an implementation diff,
unit suite, CI startup, or a successful install alone.

P0/P1 must explicitly distinguish:

```text
ProviderModelCapabilities
RuntimeCapabilities
EffectiveSessionCapabilities
```

and separately preserve:

```text
CapabilitySupport
EffectiveAvailability
ProviderProjection
```

Effective runtime availability must consume existing R6C `resolve_authorization()` semantics rather than inventing a new approval model. Provider/model/backend health affects provider projection; it must not erase direct-user/runtime capabilities.

Do not implement a flat generic event taxonomy or a second `EventRecorder` persistence authority before those contracts are accepted. JSONL is a projection/export/transport over authoritative runtime state, not a competing session-history database.

Do not claim live output merely because an event type exists. `command.stdout.delta`, `command.stderr.delta`, PTY/ConPTY, and background-process events require a backend that actually emits incremental process state.

## Cross-plan comparison rule

When a local agent or external reviewer supplies a plan, compare it against `PROFESSIONAL_AGENT_RUNTIME_CANONICAL_IMPLEMENTATION_PLAN.md` requirement-by-requirement using:

```text
MATCH
CANONICAL_PLAN_MISSING
LOCAL_PLAN_MISSING
CONFLICT
UNPROVEN
OBSOLETE
```

If the local plan finds a real requirement the canonical plan missed, update the canonical plan before implementation. If the canonical plan contains a requirement the local plan missed, keep the canonical requirement. If either plan conflicts with live source/runtime/provider evidence, evidence wins and the documentation is reconciled before coding.

Later IDE/browser/external-agent acceptance work follows the canonical plan.

Do not start CLI/TUI implementation from generic dashboard assumptions. The primary user-facing surface must be the reference-derived live agent runtime stream with mutable tool invocation cells, user steering, truthful capability gating, live process output, and replayable session events.

When repository documentation disagrees with live Git/runtime/provider evidence, current evidence wins and the relevant current-status/design document must be reconciled. Historical acceptance receipts should not be rewritten merely to modernize terminology.

When a proposed post-V1 feature conflicts with `PROFESSIONAL_AGENT_RUNTIME_PRODUCT_PILLAR.md`, `PROFESSIONAL_AGENT_RUNTIME_CANONICAL_IMPLEMENTATION_PLAN.md`, `PROFESSIONAL_AGENT_RUNTIME_P0_P1_IMPLEMENTATION_GATE.md`, or the active P0/P1 correction companion, reconcile the documentation before implementation. Do not silently create a competing roadmap.
