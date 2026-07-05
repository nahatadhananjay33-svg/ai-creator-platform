"""Voice cloning interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from foundation.constants import Language
from voice_engine.interfaces.types import VoiceProfile


class VoiceCloner(ABC):
    """Creates reusable :class:`VoiceProfile` objects from reference audio.

    Zero-shot engines implement this as prompt-conditioning setup (possibly
    caching conditioning latents); fine-tuning engines implement it as a
    training job that yields a checkpoint reference.
    """

    @abstractmethod
    def create_voice_profile(
        self,
        reference_audio: Path,
        display_name: str,
        language_hint: Language | None = None,
    ) -> VoiceProfile:
        """Build a voice profile from reference audio.

        Raises:
            AdapterDependencyError: engine dependencies missing.
            ModelError: reference audio unusable (too short, wrong format...).
        """

    @abstractmethod
    def validate_reference(self, reference_audio: Path) -> list[str]:
        """Return a list of problems with the reference audio (empty = OK).

        Checks duration against the engine's minimum, sample rate, clipping,
        and silence content. Used by the benchmark and by production intake.
        """
