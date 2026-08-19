"""Conservative P2 provider/model capability discovery from local configuration.

Endpoint syntax may identify a protocol family. It cannot prove model features,
provider health, streaming, or runtime authority; those stay unknown unless
callers provide explicit typed evidence collected elsewhere.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping
from urllib.parse import urlsplit

from .professional_capabilities import CapabilityClaim, ProviderModelCapabilities
from .professional_provider_events import ProviderProtocolFamily


@dataclass(frozen=True)
class ProviderModelCapabilitySnapshot:
    """Configuration-derived P2 snapshot with no network or authority state."""

    capabilities: ProviderModelCapabilities
    endpoint: str
    protocol_evidence: str
    context_window: int | None = None
    max_output_tokens: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.capabilities, ProviderModelCapabilities):
            raise TypeError("capabilities must be ProviderModelCapabilities")
        _required(self.endpoint, "endpoint")
        _required(self.protocol_evidence, "protocol_evidence")
        for name in ("context_window", "max_output_tokens"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value <= 0):
                raise ValueError(f"{name} must be positive when supplied")


def discover_provider_model_capabilities(
    *,
    provider_id: str,
    model_id: str,
    endpoint: str,
    explicit_evidence: Mapping[str, CapabilityClaim] | None = None,
    context_window: int | None = None,
    max_output_tokens: int | None = None,
) -> ProviderModelCapabilitySnapshot:
    """Create an unknown-by-default capability snapshot without provider I/O."""

    clean_provider = _required(provider_id, "provider_id")
    clean_model = _required(model_id, "model_id")
    clean_endpoint = _required(endpoint, "endpoint")
    claims = dict(explicit_evidence or {})
    for capability_id, claim in claims.items():
        _required(capability_id, "capability_id")
        if not isinstance(claim, CapabilityClaim):
            raise TypeError("explicit capability evidence values must be CapabilityClaim")
    family, protocol_evidence = detect_protocol_family(
        provider_id=clean_provider,
        endpoint=clean_endpoint,
    )
    return ProviderModelCapabilitySnapshot(
        capabilities=ProviderModelCapabilities(
            provider_id=clean_provider,
            model_id=clean_model,
            protocol_family=family,
            claims=claims,
        ),
        endpoint=clean_endpoint,
        protocol_evidence=protocol_evidence,
        context_window=context_window,
        max_output_tokens=max_output_tokens,
    )


def detect_protocol_family(*, provider_id: str, endpoint: str) -> tuple[ProviderProtocolFamily, str]:
    """Classify only endpoint syntax already present in local configuration."""

    clean_provider = _required(provider_id, "provider_id").lower()
    clean_endpoint = _required(endpoint, "endpoint")
    path = urlsplit(clean_endpoint).path.lower().rstrip("/")
    if path.endswith("/responses"):
        return ProviderProtocolFamily.OPENAI_RESPONSES, "configured endpoint path ends with /responses"
    if path.endswith("/v1/messages") or path.endswith("/messages"):
        return ProviderProtocolFamily.ANTHROPIC_MESSAGES, "configured endpoint path identifies Messages API"
    if clean_provider == "gemini" and "interactions" in path:
        return ProviderProtocolFamily.GEMINI_INTERACTIONS, "configured Gemini endpoint path identifies Interactions API"
    if clean_provider == "gemini" and ("generatecontent" in path or "streamgeneratecontent" in path):
        return ProviderProtocolFamily.GEMINI_GENERATE_CONTENT, "configured Gemini endpoint path identifies GenerateContent API"
    if path.endswith("/chat/completions"):
        return ProviderProtocolFamily.OPENAI_COMPATIBLE_CHAT, "configured endpoint path identifies chat/completions protocol"
    return ProviderProtocolFamily.UNKNOWN, "configured endpoint does not prove a recognized protocol family"


def _required(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()
