"""Performance metrics: RTF, speech rate, latency aggregates."""
from __future__ import annotations

import statistics
from dataclasses import dataclass, asdict

from voice_engine.interfaces import SynthesisResult


@dataclass(frozen=True)
class PerformanceStats:
    synthesis_time_s: float
    audio_duration_s: float
    real_time_factor: float | None      # <1.0 = faster than real time
    chars_per_second_audio: float | None  # speech rate proxy
    first_chunk_latency_s: float | None

    def to_dict(self) -> dict[str, float | None]:
        return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in asdict(self).items()}


def compute_performance(result: SynthesisResult) -> PerformanceStats:
    chars_per_s = (
        result.request_text_chars / result.audio_duration_s
        if result.audio_duration_s > 0 and result.request_text_chars
        else None
    )
    return PerformanceStats(
        synthesis_time_s=result.synthesis_time_s,
        audio_duration_s=result.audio_duration_s,
        real_time_factor=result.real_time_factor,
        chars_per_second_audio=chars_per_s,
        first_chunk_latency_s=result.first_chunk_latency_s,
    )


def aggregate_rtf(values: list[float]) -> dict[str, float]:
    """Median/p95 aggregation for RTF across repeated runs."""
    if not values:
        return {}
    ordered = sorted(values)
    p95_idx = min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))
    return {
        "rtf_median": round(statistics.median(ordered), 4),
        "rtf_p95": round(ordered[p95_idx], 4),
        "rtf_mean": round(statistics.fmean(ordered), 4),
    }
