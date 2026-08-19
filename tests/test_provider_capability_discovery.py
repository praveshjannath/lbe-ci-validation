from __future__ import annotations

import pytest

from lbe_guard_inspector.professional_capabilities import CapabilityClaim, CapabilitySupport
from lbe_guard_inspector.professional_provider_events import ProviderProtocolFamily
from lbe_guard_inspector.provider_capability_discovery import (
    detect_protocol_family,
    discover_provider_model_capabilities,
)


def test_openai_compatible_endpoint_does_not_infer_model_feature_support() -> None:
    snapshot = discover_provider_model_capabilities(
        provider_id="openai-compatible",
        model_id="local-model",
        endpoint="http://127.0.0.1:1234/v1/chat/completions",
    )

    assert snapshot.capabilities.protocol_family is ProviderProtocolFamily.OPENAI_COMPATIBLE_CHAT
    assert snapshot.capabilities.claim("client_tool_calls").support is CapabilitySupport.UNKNOWN
    assert snapshot.capabilities.claim("streaming_text").support is CapabilitySupport.UNKNOWN


def test_explicit_evidence_is_preserved_without_workspace_or_authority_state() -> None:
    claim = CapabilityClaim(
        support=CapabilitySupport.SUPPORTED,
        reason="selected endpoint/model advertises client tool calls",
        source="provider-model-metadata",
    )
    snapshot = discover_provider_model_capabilities(
        provider_id="openai-compatible",
        model_id="tool-model",
        endpoint="http://127.0.0.1:1234/v1/chat/completions",
        explicit_evidence={"client_tool_calls": claim},
    )

    assert snapshot.capabilities.claim("client_tool_calls") is claim
    for name in ("workspace_root", "authorization", "permission", "provider_projection"):
        assert not hasattr(snapshot, name)
        assert not hasattr(snapshot.capabilities, name)


@pytest.mark.parametrize(
    ("provider_id", "endpoint", "expected"),
    [
        ("openai", "https://api.openai.com/v1/responses", ProviderProtocolFamily.OPENAI_RESPONSES),
        ("anthropic", "https://api.anthropic.com/v1/messages", ProviderProtocolFamily.ANTHROPIC_MESSAGES),
        ("gemini", "https://example.test/v1beta/interactions", ProviderProtocolFamily.GEMINI_INTERACTIONS),
        ("gemini", "https://example.test/v1beta/models/gemini:streamGenerateContent", ProviderProtocolFamily.GEMINI_GENERATE_CONTENT),
        ("routed", "http://localhost:1234/v1/chat/completions", ProviderProtocolFamily.OPENAI_COMPATIBLE_CHAT),
    ],
)
def test_protocol_family_detection_uses_only_configured_endpoint_syntax(
    provider_id: str, endpoint: str, expected: ProviderProtocolFamily
) -> None:
    family, evidence = detect_protocol_family(provider_id=provider_id, endpoint=endpoint)

    assert family is expected
    assert evidence


def test_unrecognized_endpoint_and_invalid_evidence_fail_closed() -> None:
    snapshot = discover_provider_model_capabilities(
        provider_id="routed-provider",
        model_id="model-a",
        endpoint="https://router.example/custom/inference",
    )
    assert snapshot.capabilities.protocol_family is ProviderProtocolFamily.UNKNOWN
    with pytest.raises(TypeError, match="CapabilityClaim"):
        discover_provider_model_capabilities(
            provider_id="routed-provider",
            model_id="model-a",
            endpoint="https://router.example/custom/inference",
            explicit_evidence={"client_tool_calls": object()},  # type: ignore[dict-item]
        )
