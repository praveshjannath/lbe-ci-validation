from __future__ import annotations

import pytest

from lbe_guard_inspector.professional_capabilities import (
    CapabilityClaim,
    CapabilitySupport,
    EffectiveAvailability,
    MutationClass,
    ProviderModelCapabilities,
    ProviderProjection,
    RuntimeCapabilities,
    RuntimeCapability,
    availability_from_authorization,
    derive_effective_session_capabilities,
)
from lbe_guard_inspector.professional_provider_events import ProviderProtocolFamily
from lbe_guard_inspector.runtime.authorization_resolver import AuthorizationVerdict


def _runtime(*, availability: EffectiveAvailability = EffectiveAvailability.AVAILABLE) -> RuntimeCapabilities:
    return RuntimeCapabilities((
        RuntimeCapability(
            capability_id="workspace.read",
            family="workspace",
            backend_id="governed-tool-orchestrator",
            availability=availability,
            availability_reason="requires approval" if availability is not EffectiveAvailability.AVAILABLE else None,
            mutation_class=MutationClass.NONE,
            evidence_types=("tool_receipt",),
        ),
    ))


def _provider(claim: CapabilityClaim | None = None) -> ProviderModelCapabilities:
    claims = {} if claim is None else {"client_tool_calls": claim}
    return ProviderModelCapabilities(
        provider_id="openai-compatible",
        model_id="model-a",
        protocol_family=ProviderProtocolFamily.OPENAI_COMPATIBLE_CHAT,
        claims=claims,
    )


def test_p1_state_vocabularies_are_exact_and_separate() -> None:
    assert {item.value for item in CapabilitySupport} == {
        "supported", "unsupported", "conditional", "unknown",
    }
    assert {item.value for item in EffectiveAvailability} == {
        "available", "gated", "unavailable", "conditional", "unknown",
    }
    assert {item.value for item in ProviderProjection} == {
        "exposed", "hidden", "conditional",
    }


def test_unknown_provider_support_hides_projection_without_erasing_runtime_availability() -> None:
    effective = derive_effective_session_capabilities(_runtime(), _provider())

    item = effective.capabilities[0]
    assert item.availability is EffectiveAvailability.AVAILABLE
    assert item.provider_projection is ProviderProjection.HIDDEN
    assert "not been proven" in item.provider_projection_reason


def test_supported_provider_tool_calls_expose_only_already_available_runtime_capability() -> None:
    supported = CapabilityClaim(
        support=CapabilitySupport.SUPPORTED,
        reason="provider metadata declares client tool calls",
        source="provider-metadata",
    )
    exposed = derive_effective_session_capabilities(_runtime(), _provider(supported)).capabilities[0]
    unavailable = derive_effective_session_capabilities(
        _runtime(availability=EffectiveAvailability.GATED), _provider(supported)
    ).capabilities[0]

    assert exposed.provider_projection is ProviderProjection.EXPOSED
    assert unavailable.availability is EffectiveAvailability.GATED
    assert unavailable.provider_projection is ProviderProjection.HIDDEN


def test_r6c_verdict_mapping_does_not_create_new_authorization_rules() -> None:
    assert availability_from_authorization(AuthorizationVerdict.ALLOW) is EffectiveAvailability.AVAILABLE
    assert availability_from_authorization(AuthorizationVerdict.DENY) is EffectiveAvailability.UNAVAILABLE
    assert availability_from_authorization(AuthorizationVerdict.ESCALATE) is EffectiveAvailability.GATED


def test_contract_rejects_non_simple_state_without_reason_and_duplicate_capability_ids() -> None:
    with pytest.raises(ValueError, match="availability_reason"):
        RuntimeCapability(
            capability_id="workspace.write",
            family="workspace",
            backend_id="governed-tool-orchestrator",
            availability=EffectiveAvailability.GATED,
        )
    capability = _runtime().capabilities[0]
    with pytest.raises(ValueError, match="unique"):
        RuntimeCapabilities((capability, capability))


def test_professional_capability_layers_do_not_contain_workspace_or_authorization_state() -> None:
    provider = _provider()
    runtime = _runtime()
    effective = derive_effective_session_capabilities(runtime, provider)

    for value in (provider, runtime, effective):
        assert not hasattr(value, "workspace_root")
        assert not hasattr(value, "authorization")
        assert not hasattr(value, "permission")
