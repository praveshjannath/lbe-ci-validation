"""Typed professional capability truth without provider or tool authority.

This P1 contract separates provider/model technical support, LBE runtime
availability, and what may be projected to a provider. It neither performs
provider discovery nor authorizes, dispatches, or executes capabilities.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Mapping

from .professional_provider_events import ProviderProtocolFamily
from .runtime.authorization_resolver import AuthorizationVerdict


class CapabilitySupport(StrEnum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    CONDITIONAL = "conditional"
    UNKNOWN = "unknown"


class EffectiveAvailability(StrEnum):
    AVAILABLE = "available"
    GATED = "gated"
    UNAVAILABLE = "unavailable"
    CONDITIONAL = "conditional"
    UNKNOWN = "unknown"


class ProviderProjection(StrEnum):
    EXPOSED = "exposed"
    HIDDEN = "hidden"
    CONDITIONAL = "conditional"


class MutationClass(StrEnum):
    NONE = "none"
    MUTATING = "mutating"
    DESTRUCTIVE = "destructive"


class ExternalEffectClass(StrEnum):
    NONE = "none"
    LOCAL_PROCESS = "local_process"
    EXTERNAL = "external"


@dataclass(frozen=True)
class CapabilityClaim:
    """One evidence-backed technical support statement.

    Unknown is deliberate: configuration identity alone does not prove a
    provider/model feature. This object cannot express runtime permission.
    """

    support: CapabilitySupport = CapabilitySupport.UNKNOWN
    reason: str | None = "capability has not been proven"
    source: str = "unproven"

    def __post_init__(self) -> None:
        if not isinstance(self.support, CapabilitySupport):
            raise TypeError("support must be CapabilitySupport")
        _required(self.source, "source")
        if self.reason is not None:
            _required(self.reason, "reason")
        if self.support is CapabilitySupport.CONDITIONAL and self.reason is None:
            raise ValueError("conditional support requires a reason")


@dataclass(frozen=True)
class ProviderModelCapabilities:
    """Technical support claims for one selected provider/model only."""

    provider_id: str
    model_id: str
    protocol_family: ProviderProtocolFamily
    claims: Mapping[str, CapabilityClaim] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _required(self.provider_id, "provider_id")
        _required(self.model_id, "model_id")
        if not isinstance(self.protocol_family, ProviderProtocolFamily):
            raise TypeError("protocol_family must be ProviderProtocolFamily")
        _claims(self.claims)

    def claim(self, capability_id: str) -> CapabilityClaim:
        return self.claims.get(_required(capability_id, "capability_id"), CapabilityClaim())


@dataclass(frozen=True)
class RuntimeCapability:
    """One LBE-owned capability descriptor, independent of a provider."""

    capability_id: str
    family: str
    backend_id: str
    availability: EffectiveAvailability
    availability_reason: str | None = None
    backend_version: str | None = None
    workspace_binding: str = "workspace_bound"
    mode_requirements: tuple[str, ...] = ()
    permission_requirements: tuple[str, ...] = ()
    mutation_class: MutationClass = MutationClass.NONE
    external_effect_class: ExternalEffectClass = ExternalEffectClass.NONE
    supports_streaming: CapabilitySupport = CapabilitySupport.UNKNOWN
    supports_interactive: CapabilitySupport = CapabilitySupport.UNKNOWN
    supports_background: CapabilitySupport = CapabilitySupport.UNKNOWN
    supports_cancellation: CapabilitySupport = CapabilitySupport.UNKNOWN
    supports_parallelism: CapabilitySupport = CapabilitySupport.UNKNOWN
    input_schema: Mapping[str, object] = field(default_factory=dict)
    output_schema: Mapping[str, object] = field(default_factory=dict)
    evidence_types: tuple[str, ...] = ()
    validation_types: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("capability_id", "family", "backend_id", "workspace_binding"):
            _required(getattr(self, name), name)
        if self.backend_version is not None:
            _required(self.backend_version, "backend_version")
        if not isinstance(self.availability, EffectiveAvailability):
            raise TypeError("availability must be EffectiveAvailability")
        if self.availability is not EffectiveAvailability.AVAILABLE and self.availability_reason is None:
            raise ValueError("non-available runtime capability requires availability_reason")
        if self.availability_reason is not None:
            _required(self.availability_reason, "availability_reason")
        if not isinstance(self.mutation_class, MutationClass):
            raise TypeError("mutation_class must be MutationClass")
        if not isinstance(self.external_effect_class, ExternalEffectClass):
            raise TypeError("external_effect_class must be ExternalEffectClass")
        for name in (
            "supports_streaming",
            "supports_interactive",
            "supports_background",
            "supports_cancellation",
            "supports_parallelism",
        ):
            if not isinstance(getattr(self, name), CapabilitySupport):
                raise TypeError(f"{name} must be CapabilitySupport")
        _text_tuple(self.mode_requirements, "mode_requirements")
        _text_tuple(self.permission_requirements, "permission_requirements")
        _text_tuple(self.evidence_types, "evidence_types")
        _text_tuple(self.validation_types, "validation_types")
        if not isinstance(self.input_schema, Mapping) or not isinstance(self.output_schema, Mapping):
            raise TypeError("input_schema and output_schema must be mappings")


@dataclass(frozen=True)
class RuntimeCapabilities:
    """Runtime-owned descriptors with unique IDs and no provider claims."""

    capabilities: tuple[RuntimeCapability, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.capabilities, tuple) or not all(
            isinstance(item, RuntimeCapability) for item in self.capabilities
        ):
            raise TypeError("capabilities must be a tuple of RuntimeCapability")
        ids = [item.capability_id for item in self.capabilities]
        if len(ids) != len(set(ids)):
            raise ValueError("runtime capability IDs must be unique")


@dataclass(frozen=True)
class EffectiveSessionCapability:
    """Session projection retaining runtime availability and provider visibility separately."""

    capability_id: str
    availability: EffectiveAvailability
    availability_reason: str | None
    provider_projection: ProviderProjection
    provider_projection_reason: str

    def __post_init__(self) -> None:
        _required(self.capability_id, "capability_id")
        if not isinstance(self.availability, EffectiveAvailability):
            raise TypeError("availability must be EffectiveAvailability")
        if self.availability is not EffectiveAvailability.AVAILABLE and self.availability_reason is None:
            raise ValueError("non-available effective capability requires availability_reason")
        if self.availability_reason is not None:
            _required(self.availability_reason, "availability_reason")
        if not isinstance(self.provider_projection, ProviderProjection):
            raise TypeError("provider_projection must be ProviderProjection")
        _required(self.provider_projection_reason, "provider_projection_reason")


@dataclass(frozen=True)
class EffectiveSessionCapabilities:
    """Effective session view; projection never becomes authority."""

    capabilities: tuple[EffectiveSessionCapability, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.capabilities, tuple) or not all(
            isinstance(item, EffectiveSessionCapability) for item in self.capabilities
        ):
            raise TypeError("capabilities must be a tuple of EffectiveSessionCapability")
        ids = [item.capability_id for item in self.capabilities]
        if len(ids) != len(set(ids)):
            raise ValueError("effective capability IDs must be unique")


def availability_from_authorization(verdict: AuthorizationVerdict) -> EffectiveAvailability:
    """Map R6C's existing decision without changing its authority semantics."""

    if not isinstance(verdict, AuthorizationVerdict):
        raise TypeError("verdict must be AuthorizationVerdict")
    return {
        AuthorizationVerdict.ALLOW: EffectiveAvailability.AVAILABLE,
        AuthorizationVerdict.DENY: EffectiveAvailability.UNAVAILABLE,
        AuthorizationVerdict.ESCALATE: EffectiveAvailability.GATED,
    }[verdict]


def derive_effective_session_capabilities(
    runtime: RuntimeCapabilities,
    provider: ProviderModelCapabilities,
) -> EffectiveSessionCapabilities:
    """Project runtime capabilities without allowing provider claims to change authority.

    Provider projection uses the provider's ``client_tool_calls`` claim only.
    A missing/unknown claim hides projection but leaves direct runtime
    availability untouched.
    """

    if not isinstance(runtime, RuntimeCapabilities):
        raise TypeError("runtime must be RuntimeCapabilities")
    if not isinstance(provider, ProviderModelCapabilities):
        raise TypeError("provider must be ProviderModelCapabilities")
    tool_calls = provider.claim("client_tool_calls")
    return EffectiveSessionCapabilities(
        tuple(
            EffectiveSessionCapability(
                capability_id=item.capability_id,
                availability=item.availability,
                availability_reason=item.availability_reason,
                provider_projection=_projection(item, tool_calls),
                provider_projection_reason=_projection_reason(item, tool_calls),
            )
            for item in runtime.capabilities
        )
    )


def _projection(item: RuntimeCapability, claim: CapabilityClaim) -> ProviderProjection:
    if item.availability is not EffectiveAvailability.AVAILABLE:
        return ProviderProjection.HIDDEN
    if claim.support is CapabilitySupport.SUPPORTED:
        return ProviderProjection.EXPOSED
    if claim.support is CapabilitySupport.CONDITIONAL:
        return ProviderProjection.CONDITIONAL
    return ProviderProjection.HIDDEN


def _projection_reason(item: RuntimeCapability, claim: CapabilityClaim) -> str:
    if item.availability is not EffectiveAvailability.AVAILABLE:
        return item.availability_reason or "runtime capability is not available"
    if claim.support is CapabilitySupport.SUPPORTED:
        return "selected provider/model supports client tool calls"
    return claim.reason or "selected provider/model client tool-call support is unproven"


def _claims(value: Mapping[str, CapabilityClaim]) -> None:
    if not isinstance(value, Mapping):
        raise TypeError("claims must be a mapping")
    for capability_id, claim in value.items():
        _required(capability_id, "claim capability_id")
        if not isinstance(claim, CapabilityClaim):
            raise TypeError("claims values must be CapabilityClaim")


def _text_tuple(value: tuple[str, ...], name: str) -> None:
    if not isinstance(value, tuple):
        raise TypeError(f"{name} must be a tuple")
    for item in value:
        _required(item, name)


def _required(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()
