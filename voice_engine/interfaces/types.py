"""Core value types shared by all Voice Engine interfaces."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any

from foundation.constants import Language


class StreamingSupport(str, Enum):
    """Streaming capability classification used in research and reports."""

    EXCELLENT = "excellent"      # native chunked streaming, <300 ms first chunk
    GOOD = "good"                # workable streaming (sentence-level or adapted)
    LIMITED = "limited"          # only via external chunking; latency spikes
    NOT_SUITABLE = "not_suitable"


@dataclass(frozen=True)
class EngineCapabilities:
    """What a voice engine/adapter can do. Filled from research + verified at runtime."""

    zero_shot_cloning: bool
    fine_tuning: bool
    streaming: StreamingSupport
    emotion_control: bool
    languages: tuple[Language, ...]
    min_reference_audio_s: float | None = None  # None -> no cloning
    cpu_realtime: bool = False
    notes: str = ""


@dataclass(frozen=True)
class VoiceProfile:
    """A cloned voice identity.

    For zero-shot engines this wraps the reference audio (and any cached
    conditioning latents). For fine-tuned voices it references a checkpoint.
    Profiles are engine-specific but the type is engine-agnostic so pipelines
    can pass them around opaquely.
    """

    profile_id: str
    engine_id: str
    display_name: str
    reference_audio: Path | None = None
    language_hint: Language | None = None
    artifacts: dict[str, str] = field(default_factory=dict)  # engine-specific paths
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SynthesisRequest:
    """One synthesis job."""

    text: str
    language: Language
    voice: VoiceProfile | None = None  # None -> engine default voice
    speed: float = 1.0
    emotion: str | None = None  # engine-interpreted hint, e.g. "excited"
    seed: int | None = None
    output_path: Path | None = None  # where to write the wav; temp if None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class SynthesisResult:
    """Outcome of a synthesis job, including timing needed for benchmarking."""

    audio_path: Path
    sample_rate: int
    audio_duration_s: float
    synthesis_time_s: float
    first_chunk_latency_s: float | None = None  # streaming engines only
    engine_id: str = ""
    request_text_chars: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def real_time_factor(self) -> float | None:
        """RTF = synthesis time / audio duration. <1.0 is faster than real time."""
        if self.audio_duration_s <= 0:
            return None
        return self.synthesis_time_s / self.audio_duration_s

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["audio_path"] = str(self.audio_path)
        d["real_time_factor"] = self.real_time_factor
        return d


@dataclass(frozen=True)
class AudioChunk:
    """One chunk of streamed PCM audio."""

    pcm_s16le: bytes
    sample_rate: int
    chunk_index: int
    is_final: bool = False
