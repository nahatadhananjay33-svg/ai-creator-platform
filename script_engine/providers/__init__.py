"""Storyboard providers (Phase C10): one interface, deterministic + LLM backends.

C10 ships the deterministic :class:`MockProvider` (hermetic default) plus the real
LLM providers (OpenAI / Anthropic / Gemini), all behind the same
:class:`StoryboardProvider` interface. Real providers are imported lazily by
:func:`get_provider` so the hermetic path never needs their SDKs or API keys.
"""
from __future__ import annotations

from script_engine.providers.base import (
    GenerationRequest,
    StoryboardProvider,
    clean_topic,
    estimate_duration_s,
    topic_keywords,
)
from script_engine.providers.mock import MockProvider

#: Provider names C10 knows about (mock is always available; the rest need a key).
PROVIDER_NAMES: tuple[str, ...] = ("mock", "openai", "anthropic", "gemini")


def get_provider(name: str, **kwargs) -> StoryboardProvider:
    """Instantiate a provider by name. Real providers are imported lazily, so the
    ``mock`` path (and the whole hermetic suite) never needs their SDKs."""
    if name == "mock":
        return MockProvider()
    if name == "openai":
        from script_engine.providers.openai_provider import OpenAIProvider
        return OpenAIProvider(**kwargs)
    if name == "anthropic":
        from script_engine.providers.anthropic_provider import AnthropicProvider
        return AnthropicProvider(**kwargs)
    if name == "gemini":
        from script_engine.providers.gemini_provider import GeminiProvider
        return GeminiProvider(**kwargs)
    raise ValueError(f"Unknown provider {name!r}; expected one of {PROVIDER_NAMES}")


__all__ = [
    "StoryboardProvider",
    "GenerationRequest",
    "MockProvider",
    "get_provider",
    "PROVIDER_NAMES",
    "clean_topic",
    "topic_keywords",
    "estimate_duration_s",
]
