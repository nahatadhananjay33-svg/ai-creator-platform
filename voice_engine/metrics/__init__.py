"""Low-level metric computations for synthesized speech.

Pure functions / small classes with no orchestration logic. The evaluation
framework (voice_engine/evaluation) composes these into metric suites.

Dependency policy: everything in ``audio_stats``, ``performance``, and
``text_metrics`` is stdlib-only. Heavier metrics (speaker similarity, ASR
intelligibility) live behind optional extras and raise
:class:`foundation.exceptions.MetricUnavailableError` when missing.
"""

from voice_engine.metrics.audio_stats import AudioStats, compute_audio_stats
from voice_engine.metrics.performance import PerformanceStats, compute_performance
from voice_engine.metrics.text_metrics import code_switch_segments, script_coverage
from voice_engine.metrics.similarity import SpeakerSimilarityMetric

__all__ = [
    "AudioStats",
    "compute_audio_stats",
    "PerformanceStats",
    "compute_performance",
    "code_switch_segments",
    "script_coverage",
    "SpeakerSimilarityMetric",
]
