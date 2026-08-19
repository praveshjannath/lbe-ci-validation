from __future__ import annotations

import pytest

from lbe_guard_inspector.provider_registry import (
    ProviderCapabilities,
    ProviderDescriptor,
    ProviderHandle,
    ProviderRegistry,
    default_provider_registry,
)
from lbe_guard_inspector.reasoning_contracts import ExplanationResult, ReasoningPlan
from lbe_guard_inspector.reasoning_provider import OpenAICompatibleReasoningBackend, ProviderConfig
from lbe_guard_inspector.reasoning_runtime import (
    build_openai_compatible_controller,
    build_provider_controller,
)
from lbe_guard_inspector.request_controller import LBERequestController


class FakeBackend:
    def plan(self, request):
        return ReasoningPlan(
            interpreted_problem="bounded",
            ambiguities=(),
            candidate_guard_ids=(),
            evidence_requests=(),
            validation_requests=(),
            explanation_focus=(),
        )

    def explain(self, request):
        return ExplanationResult(explanation="bounded")


def config(model: str = "model-a") -> ProviderConfig:
    return ProviderConfig(
        endpoint="http://127.0.0.1:1234/v1/chat/completions",
        model=model,
        timeout_seconds=30,
    )


def test_registry_builds_registered_provider_with_identity_and_capabilities():
    backend = FakeBackend()

    def factory(provider_config):
        return ProviderHandle(
            descriptor=ProviderDescriptor(
                provider_id="fake",
                model_id=provider_config.model,
                capabilities=ProviderCapabilities(
                    streaming=True,
                    tool_calls=True,
                    structured_output=False,
                    context_limit=8192,
                ),
            ),
            backend=backend,
        )

    registry = ProviderRegistry({"fake": factory})
    handle = registry.build(provider_id="fake", config=config())

    assert handle.backend is backend
    assert handle.descriptor.provider_id == "fake"
    assert handle.descriptor.model_id == "model-a"
    assert handle.descriptor.capabilities.streaming is True
    assert handle.descriptor.capabilities.tool_calls is True
    assert handle.descriptor.capabilities.context_limit == 8192


def test_registry_rejects_unknown_provider():
    with pytest.raises(KeyError, match="not registered"):
        ProviderRegistry().build(provider_id="missing", config=config())


def test_registry_rejects_duplicate_provider_registration():
    registry = ProviderRegistry({"fake": lambda cfg: ProviderHandle(
        descriptor=ProviderDescriptor("fake", cfg.model, ProviderCapabilities()),
        backend=FakeBackend(),
    )})
    with pytest.raises(ValueError, match="already registered"):
        registry.register("fake", lambda cfg: None)


def test_registry_rejects_factory_identity_mismatch():
    registry = ProviderRegistry({"fake": lambda cfg: ProviderHandle(
        descriptor=ProviderDescriptor("other", cfg.model, ProviderCapabilities()),
        backend=FakeBackend(),
    )})
    with pytest.raises(ValueError, match="provider_id"):
        registry.build(provider_id="fake", config=config())


def test_registry_rejects_factory_model_mismatch():
    registry = ProviderRegistry({"fake": lambda cfg: ProviderHandle(
        descriptor=ProviderDescriptor("fake", "different", ProviderCapabilities()),
        backend=FakeBackend(),
    )})
    with pytest.raises(ValueError, match="model_id"):
        registry.build(provider_id="fake", config=config())


def test_provider_capabilities_validate_context_limit():
    with pytest.raises(ValueError, match="context_limit"):
        ProviderCapabilities(context_limit=0)


def test_default_registry_exposes_existing_openai_compatible_backend():
    registry = default_provider_registry()
    handle = registry.build(provider_id="openai-compatible", config=config())

    assert registry.provider_ids() == ("openai-compatible",)
    assert handle.descriptor.provider_id == "openai-compatible"
    assert handle.descriptor.model_id == "model-a"
    assert handle.descriptor.capabilities.structured_output is True
    assert isinstance(handle.backend, OpenAICompatibleReasoningBackend)


def test_generic_composition_uses_registered_backend_without_invoking_it():
    backend = FakeBackend()
    calls = []

    def factory(provider_config):
        calls.append(provider_config.model)
        return ProviderHandle(
            descriptor=ProviderDescriptor("fake", provider_config.model, ProviderCapabilities()),
            backend=backend,
        )

    controller, handle = build_provider_controller(
        provider_id="fake",
        provider_config=config("switchable-model"),
        provider_registry=ProviderRegistry({"fake": factory}),
    )

    assert isinstance(controller, LBERequestController)
    assert controller._backend is backend
    assert handle.backend is backend
    assert handle.descriptor.model_id == "switchable-model"
    assert calls == ["switchable-model"]


def test_generic_composition_does_not_allow_backend_override():
    with pytest.raises(ValueError, match="must not override backend"):
        build_provider_controller(
            provider_id="openai-compatible",
            provider_config=config(),
            controller_kwargs={"backend": FakeBackend()},
        )


def test_existing_openai_builder_remains_compatible():
    controller = build_openai_compatible_controller(provider_config=config())
    assert isinstance(controller, LBERequestController)
    assert isinstance(controller._backend, OpenAICompatibleReasoningBackend)
