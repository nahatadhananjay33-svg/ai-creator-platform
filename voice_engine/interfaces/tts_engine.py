"""Text-to-speech engine interface."""
from __future__ import annotations

from abc import ABC, abstractmethod

from foundation.constants import Language
from foundation.model_manager import ModelSpec
from voice_engine.interfaces.types import EngineCapabilities, SynthesisRequest, SynthesisResult


class TTSEngine(ABC):
    """Contract every synthesis backend must satisfy.

    Lifecycle: ``is_available()`` -> ``load()`` -> ``synthesize()`` * N -> ``unload()``.
    Implementations must be safe to construct without their heavy
    dependencies installed; only ``load()`` may import them.
    """

    @property
    @abstractmethod
    def engine_id(self) -> str:
        """Platform-unique identifier (matches the ModelSpec model_id)."""

    @property
    @abstractmethod
    def spec(self) -> ModelSpec:
        """Static model metadata (license, hardware, sources)."""

    @property
    @abstractmethod
    def capabilities(self) -> EngineCapabilities:
        """Declared capabilities (verified empirically by the benchmark)."""

    @abstractmethod
    def is_available(self) -> bool:
        """True if optional dependencies are importable on this machine."""

    @abstractmethod
    def load(self) -> None:
        """Load model weights onto the resolved device. Idempotent."""

    @abstractmethod
    def unload(self) -> None:
        """Release model memory. Idempotent."""

    @abstractmethod
    def synthesize(self, request: SynthesisRequest) -> SynthesisResult:
        """Synthesize speech for one request. Must call load() lazily if needed."""

    def supports_language(self, language: Language) -> bool:
        return language in self.capabilities.languages
