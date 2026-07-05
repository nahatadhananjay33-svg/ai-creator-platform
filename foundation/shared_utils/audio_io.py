"""Dependency-free WAV I/O.

Uses only the stdlib so that dataset validation, benchmarking, and basic
metrics run on any machine without numpy/soundfile. Heavier analysis
(spectral metrics, resampling) belongs in ``voice_engine.metrics`` behind
optional extras.

Only 16-bit PCM mono/stereo WAV is supported — the platform's canonical
interchange format.
"""
from __future__ import annotations

import array
import math
import wave
from dataclasses import dataclass
from pathlib import Path

from foundation.exceptions import PlatformError


@dataclass(frozen=True)
class WavData:
    """In-memory 16-bit PCM audio."""

    samples: array.array  # signed 16-bit, interleaved if stereo
    sample_rate: int
    channels: int = 1

    @property
    def n_frames(self) -> int:
        return len(self.samples) // self.channels

    @property
    def duration_s(self) -> float:
        return self.n_frames / self.sample_rate if self.sample_rate else 0.0


def read_wav(path: Path | str) -> WavData:
    """Read a 16-bit PCM WAV file."""
    path = Path(path)
    try:
        with wave.open(str(path), "rb") as wf:
            if wf.getsampwidth() != 2:
                raise PlatformError(
                    f"Only 16-bit PCM WAV supported, got {wf.getsampwidth() * 8}-bit",
                    path=str(path),
                )
            raw = wf.readframes(wf.getnframes())
            samples = array.array("h")
            samples.frombytes(raw)
            return WavData(samples=samples, sample_rate=wf.getframerate(), channels=wf.getnchannels())
    except wave.Error as exc:
        raise PlatformError(f"Failed to read WAV: {path}", path=str(path)) from exc


def write_wav(path: Path | str, data: WavData) -> Path:
    """Write 16-bit PCM WAV to disk, creating parent directories."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(data.channels)
        wf.setsampwidth(2)
        wf.setframerate(data.sample_rate)
        wf.writeframes(data.samples.tobytes())
    return path


def generate_sine_wav(
    duration_s: float,
    frequency_hz: float = 440.0,
    sample_rate: int = 24_000,
    amplitude: float = 0.4,
) -> WavData:
    """Generate a sine tone (used by the mock adapter and metric tests)."""
    n = int(duration_s * sample_rate)
    peak = int(32767 * max(0.0, min(amplitude, 1.0)))
    samples = array.array(
        "h",
        (int(peak * math.sin(2.0 * math.pi * frequency_hz * i / sample_rate)) for i in range(n)),
    )
    return WavData(samples=samples, sample_rate=sample_rate, channels=1)
