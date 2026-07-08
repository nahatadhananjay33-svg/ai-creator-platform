"""Caption timing sources (Phase C4).

One protocol, one deterministic default. Real ASR aligners can be added later
behind the same :class:`TimingProvider` interface without touching the builder.
"""
from __future__ import annotations

from caption_engine.providers.base import (
    TimingProvider,
    Transcript,
    TranscriptSegment,
    TranscriptWord,
)
from caption_engine.providers.heuristic import HeuristicTimingProvider

__all__ = [
    "TimingProvider",
    "Transcript",
    "TranscriptSegment",
    "TranscriptWord",
    "HeuristicTimingProvider",
]
