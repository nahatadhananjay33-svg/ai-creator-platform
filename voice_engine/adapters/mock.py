"""Mock adapter: dependency-free engine for pipeline and CI testing.

Generates deterministic sine-tone "speech" (duration proportional to text
length, pitch derived from the voice profile) so the full benchmark ->
evaluation -> reporting pipeline runs on any machine in seconds.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Iterator

from foundation.constants import DEFAULT_SAMPLE_RATE, Language
from foundation.model_manager import HardwareRequirements, LicenseInfo, ModelSpec
from foundation.shared_utils import generate_sine_wav, write_wav
from voice_engine.adapters.base import BaseVoiceAdapter
from voice_engine.interfaces import (
    AudioChunk,
    EngineCapabilities,
    StreamingSupport,
    StreamingTTSEngine,
    SynthesisRequest,
)

#: Assumed speaking rate for synthetic duration (chars per second).
_CHARS_PER_SECOND = 15.0


class MockVoiceAdapter(BaseVoiceAdapter, StreamingTTSEngine):
    SPEC = ModelSpec(
        model_id="mock",
        display_name="Mock Voice Engine",
        family="tts",
        version="1.0",
        repo_url="internal",
        weights_source="none",
        license=LicenseInfo("MIT", "MIT", commercial_use=True, notes="Test-only engine"),
        hardware=HardwareRequirements(
            min_vram_gb=None, recommended_vram_gb=None, min_ram_gb=0.1,
            cpu_realtime_capable=True, disk_size_gb=0.0,
        ),
        parameters_millions=0.0,
        languages=("en", "hi", "hi-en", "bn"),
        tags=("test", "streaming", "zero-shot"),
    )
    CAPABILITIES = EngineCapabilities(
        zero_shot_cloning=True,
        fine_tuning=False,
        streaming=StreamingSupport.EXCELLENT,
        emotion_control=False,
        languages=(Language.ENGLISH, Language.HINDI, Language.HINGLISH, Language.BENGALI),
        min_reference_audio_s=1.0,
        cpu_realtime=True,
        notes="Synthetic tones only; validates pipeline plumbing, not audio quality.",
    )
    IMPORT_PACKAGES: tuple[str, ...] = ()
    PIP_PACKAGES: tuple[str, ...] = ()

    def _load_impl(self) -> None:
        self._model = object()  # nothing to load

    def _voice_frequency(self, request: SynthesisRequest) -> float:
        if request.voice is None:
            return 220.0
        return 180.0 + (hash(request.voice.profile_id) % 200)

    def _synthesize_impl(self, request: SynthesisRequest, output_path: Path) -> None:
        simulated_delay_s = float(self.config.get("simulated_delay_s", 0.0))
        if simulated_delay_s > 0:
            time.sleep(simulated_delay_s)
        duration = max(0.2, len(request.text) / (_CHARS_PER_SECOND * request.speed))
        wav = generate_sine_wav(
            duration_s=duration,
            frequency_hz=self._voice_frequency(request),
            sample_rate=DEFAULT_SAMPLE_RATE,
        )
        write_wav(output_path, wav)

    def stream_synthesize(self, request: SynthesisRequest) -> Iterator[AudioChunk]:
        self.load()
        first_chunk_delay_s = float(self.config.get("first_chunk_delay_s", 0.02))
        chunk_ms = int(self.config.get("chunk_ms", 200))
        duration = max(0.2, len(request.text) / (_CHARS_PER_SECOND * request.speed))
        wav = generate_sine_wav(
            duration_s=duration,
            frequency_hz=self._voice_frequency(request),
            sample_rate=DEFAULT_SAMPLE_RATE,
        )
        frames_per_chunk = int(DEFAULT_SAMPLE_RATE * chunk_ms / 1000)
        raw = wav.samples.tobytes()
        bytes_per_chunk = frames_per_chunk * 2
        chunks = [raw[i : i + bytes_per_chunk] for i in range(0, len(raw), bytes_per_chunk)]
        time.sleep(first_chunk_delay_s)
        for idx, chunk in enumerate(chunks):
            yield AudioChunk(
                pcm_s16le=chunk,
                sample_rate=DEFAULT_SAMPLE_RATE,
                chunk_index=idx,
                is_final=idx == len(chunks) - 1,
            )
