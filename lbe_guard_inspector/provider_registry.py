"""Provider registry for replaceable reasoning backends.

Provider metadata describes transport/model capabilities only. It never grants
workspace permissions, guard authority, validation authority, or completion
truth.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping

from .reasoning_contracts import ReasoningBackend
from .reasoning_provider import OpenAICompatibleReasoningBackend, ProviderConfig


@dataclass(frozen=True)
class ProviderCapabilities:
    streaming: bool = False
    tool_calls: bool = False
    structured_output: bool = True
    context_limit: int | None = None

    def __post_init__(self) -> None:
        if self.context_limit is not None and self.context_limit <= 0:
            raise ValueError("provider context_limit must be positive when supplied")


@dataclass(frozen=True)
class ProviderDescriptor:
    provider_id: str
    model_id: str
    capabilities: ProviderCapabilities

    def __post_init__(self) -> None:
        if not isinstance(self.provider_id, str) or not self.provider_id.strip():
            raise ValueError("provider_id must be a non-empty string")
        if not isinstance(self.model_id, str) or not self.model_id.strip():
            raise ValueError("model_id must be a non-empty string")


@dataclass(frozen=True)
class ProviderHandle:
    descriptor: ProviderDescriptor
    backend: ReasoningBackend


ProviderFactory = Callable[[ProviderConfig], ProviderHandle]


class ProviderRegistry:
    """Explicit registry of reasoning provider factories.

    Registration is composition metadata only. Runtime policy/capability
    authorization remains owned by LBE's existing mode/governance layers.
    """

    def __init__(self, factories: Mapping[str, ProviderFactory] | None = None) -> None:
        self._factories: dict[str, ProviderFactory] = {}
        for provider_id, factory in dict(factories or {}).items():
            self.register(provider_id, factory)

    def register(self, provider_id: str, factory: ProviderFactory) -> None:
        clean_id = _provider_id(provider_id)
        if not callable(factory):
            raise TypeError("provider factory must be callable")
        if clean_id in self._factories:
            raise ValueError(f"provider already registered: {clean_id}")
        self._factories[clean_id] = factory

    def provider_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._factories))

    def build(self, *, provider_id: str, config: ProviderConfig) -> ProviderHandle:
        clean_id = _provider_id(provider_id)
        if not isinstance(config, ProviderConfig):
            raise TypeError("config must be a ProviderConfig")
        factory = self._factories.get(clean_id)
        if factory is None:
            raise KeyError(f"provider is not registered: {clean_id}")
        handle = factory(config)
        if not isinstance(handle, ProviderHandle):
            raise TypeError("provider factory must return ProviderHandle")
        if handle.descriptor.provider_id != clean_id:
            raise ValueError("provider factory descriptor does not match registered provider_id")
        if handle.descriptor.model_id != config.model.strip():
            raise ValueError("provider factory descriptor model_id does not match config model")
        return handle


def openai_compatible_factory(config: ProviderConfig) -> ProviderHandle:
    return ProviderHandle(
        descriptor=ProviderDescriptor(
            provider_id="openai-compatible",
            model_id=config.model.strip(),
            capabilities=ProviderCapabilities(
                streaming=False,
                tool_calls=False,
                structured_output=True,
                context_limit=None,
            ),
        ),
        backend=OpenAICompatibleReasoningBackend(config=config),
    )


def default_provider_registry() -> ProviderRegistry:
    """Return built-in provider adapters without reading environment/runtime state."""
    return ProviderRegistry({"openai-compatible": openai_compatible_factory})


def _provider_id(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("provider_id must be a non-empty string")
    return value.strip()
