"""Deterministic procedural soundtrack generator (Phase C8).

Generates short, seamlessly-loopable *music-like* beds from pure math — layered
sine partials (a simple chord) with a gentle tremolo — so the Music Engine, its
demo, and its tests always have real audio to mix WITHOUT any download, stock
library, streaming API, or model. This is NOT AI music generation: it is a fixed
table of chords rendered by a closed-form function, so the same name + duration
always produce a byte-identical WAV.

The beds are written whole-cycle (an integer number of periods of the tremolo)
so tiling them for a longer reel loops without a discontinuity.
"""
from __future__ import annotations

import array
import math
from pathlib import Path

from foundation.shared_utils import WavData, write_wav

#: Named beds: (chord frequencies in Hz, per-partial amplitudes, tremolo Hz).
#: Distinct, musical-ish chords so a creator can pick a mood deterministically.
SOUNDTRACKS: dict[str, tuple] = {
    # A-minor-ish pad — calm, low.
    "ambient": ((220.00, 261.63, 329.63), (0.55, 0.30, 0.20), 0.20),
    # C-major triad + octave — brighter, a touch faster tremolo.
    "upbeat": ((261.63, 329.63, 392.00, 523.25), (0.45, 0.30, 0.25, 0.18), 0.50),
    # G-based mellow chord — warm, slow.
    "lofi": ((196.00, 246.94, 293.66), (0.55, 0.32, 0.22), 0.15),
    # Low, wide fifths — filmic.
    "cinematic": ((130.81, 196.00, 261.63, 392.00), (0.60, 0.35, 0.25, 0.15), 0.10),
}

#: The default bed length (seconds). Kept short; the mixer loops it to fill a reel.
DEFAULT_BED_DURATION_S = 8.0


def soundtrack_names() -> tuple:
    """The built-in soundtrack names, sorted (stable for reporting/tests)."""
    return tuple(sorted(SOUNDTRACKS))


def _render_bed(name: str, duration_s: float, sample_rate: int,
                amplitude: float) -> WavData:
    """Render one named chord bed to :class:`WavData` (deterministic, pure)."""
    if name not in SOUNDTRACKS:
        raise ValueError(f"Unknown soundtrack {name!r}; expected one of {soundtrack_names()}")
    freqs, amps, trem_hz = SOUNDTRACKS[name]
    n = max(1, int(round(duration_s * sample_rate)))
    norm = amplitude / max(1e-9, sum(amps))          # keep the sum within [-amp, amp]
    two_pi = 2.0 * math.pi
    samples = array.array("h")
    for i in range(n):
        t = i / sample_rate
        # gentle tremolo (0.7..1.0) so the bed breathes without pumping
        trem = 0.85 + 0.15 * math.sin(two_pi * trem_hz * t)
        acc = 0.0
        for f, a in zip(freqs, amps):
            acc += a * math.sin(two_pi * f * t)
        v = int(max(-1.0, min(1.0, acc * norm * trem)) * 32767)
        samples.append(v)
    return WavData(samples=samples, sample_rate=sample_rate, channels=1)


class ProceduralSoundtrack:
    """Generates deterministic, loopable music beds to WAV files (no I/O beyond
    writing the requested file; no network, no model)."""

    def __init__(self, sample_rate: int = 44_100, amplitude: float = 0.7) -> None:
        self.sample_rate = sample_rate
        self.amplitude = amplitude

    def generate(self, name: str, path: Path | str,
                 duration_s: float = DEFAULT_BED_DURATION_S) -> Path:
        """Render soundtrack ``name`` to ``path`` and return it (idempotent)."""
        wav = _render_bed(name, duration_s, self.sample_rate, self.amplitude)
        return write_wav(path, wav)


def generate_soundtrack(name: str, path: Path | str, *, sample_rate: int = 44_100,
                        duration_s: float = DEFAULT_BED_DURATION_S,
                        amplitude: float = 0.7) -> Path:
    """Convenience: render a named soundtrack bed to ``path``."""
    return ProceduralSoundtrack(sample_rate, amplitude).generate(name, path, duration_s)
