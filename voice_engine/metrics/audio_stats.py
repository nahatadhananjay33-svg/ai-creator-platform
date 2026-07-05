"""Signal statistics computed directly from 16-bit PCM (stdlib only).

These catch the gross failure modes of TTS output — silence, clipping,
truncated audio, dead air — cheaply and objectively. Perceptual quality
still requires the human listening protocol (evaluation/human_eval.py).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, asdict

from foundation.shared_utils.audio_io import WavData

_FRAME_MS = 30
_SILENCE_DBFS = -45.0


@dataclass(frozen=True)
class AudioStats:
    duration_s: float
    rms_dbfs: float
    peak_dbfs: float
    clipping_ratio: float        # fraction of samples at/near full scale
    silence_ratio: float         # fraction of frames below silence floor
    leading_silence_s: float
    trailing_silence_s: float
    longest_internal_silence_s: float

    def to_dict(self) -> dict[str, float]:
        return {k: round(v, 4) for k, v in asdict(self).items()}


def _frame_rms_dbfs(samples: list[int] | memoryview) -> float:
    if not len(samples):
        return -120.0
    acc = 0.0
    for s in samples:
        acc += (s / 32768.0) ** 2
    rms = math.sqrt(acc / len(samples))
    return 20.0 * math.log10(rms) if rms > 1e-9 else -120.0


def compute_audio_stats(wav: WavData, silence_dbfs: float = _SILENCE_DBFS) -> AudioStats:
    """Compute robustness statistics for a mono synthesis output."""
    samples = wav.samples
    n = len(samples)
    if n == 0:
        return AudioStats(0.0, -120.0, -120.0, 0.0, 1.0, 0.0, 0.0, 0.0)

    peak = max(abs(s) for s in samples)
    peak_dbfs = 20.0 * math.log10(peak / 32768.0) if peak else -120.0
    clipped = sum(1 for s in samples if abs(s) >= 32700)

    frame_len = max(1, int(wav.sample_rate * _FRAME_MS / 1000))
    frame_flags: list[bool] = []  # True = silent frame
    total_sq = 0.0
    for start in range(0, n, frame_len):
        frame = samples[start : start + frame_len]
        db = _frame_rms_dbfs(frame)
        frame_flags.append(db < silence_dbfs)
        for s in frame:
            total_sq += (s / 32768.0) ** 2

    rms = math.sqrt(total_sq / n)
    rms_dbfs = 20.0 * math.log10(rms) if rms > 1e-9 else -120.0

    frame_s = frame_len / wav.sample_rate
    leading = 0
    for silent in frame_flags:
        if not silent:
            break
        leading += 1
    trailing = 0
    for silent in reversed(frame_flags):
        if not silent:
            break
        trailing += 1

    longest_internal = 0
    current = 0
    interior = frame_flags[leading : len(frame_flags) - trailing] if trailing else frame_flags[leading:]
    for silent in interior:
        current = current + 1 if silent else 0
        longest_internal = max(longest_internal, current)

    return AudioStats(
        duration_s=wav.duration_s,
        rms_dbfs=rms_dbfs,
        peak_dbfs=peak_dbfs,
        clipping_ratio=clipped / n,
        silence_ratio=sum(frame_flags) / len(frame_flags),
        leading_silence_s=leading * frame_s,
        trailing_silence_s=trailing * frame_s,
        longest_internal_silence_s=longest_internal * frame_s,
    )
