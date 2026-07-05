"""Automatic evaluation of synthesis results."""
from __future__ import annotations

from pathlib import Path

from foundation.benchmarking import Measurement
from foundation.exceptions import MetricUnavailableError
from foundation.logging import get_logger
from foundation.shared_utils import read_wav
from voice_engine.datasets import PromptItem
from voice_engine.interfaces import SynthesisResult
from voice_engine.metrics import (
    SpeakerSimilarityMetric,
    compute_audio_stats,
    compute_performance,
)

logger = get_logger("voice_engine.evaluation")

#: Natural speech-rate window (chars of text per second of audio) used by the
#: truncation/runaway detector. Wide on purpose — flags only gross failures.
_EXPECTED_CHARS_PER_S = (6.0, 30.0)


class SynthesisEvaluator:
    """Turns one synthesis result into a list of automatic Measurements."""

    def __init__(self, similarity_metric: SpeakerSimilarityMetric | None = None) -> None:
        self.similarity_metric = similarity_metric or SpeakerSimilarityMetric()

    def evaluate(
        self,
        result: SynthesisResult,
        prompt: PromptItem,
        reference_audio: Path | None = None,
    ) -> list[Measurement]:
        measurements: list[Measurement] = []

        perf = compute_performance(result)
        for name, value in perf.to_dict().items():
            if value is not None:
                measurements.append(Measurement(name, value, source="auto"))

        stats = compute_audio_stats(read_wav(result.audio_path))
        for name, value in stats.to_dict().items():
            if name == "duration_s":
                continue  # already reported as audio_duration_s
            measurements.append(Measurement(name, value, source="auto"))

        if result.audio_duration_s > 0 and prompt.char_count:
            rate = prompt.char_count / result.audio_duration_s
            lo, hi = _EXPECTED_CHARS_PER_S
            expected_mid_duration = prompt.char_count / ((lo + hi) / 2)
            measurements.append(
                Measurement(
                    "duration_ratio_vs_expected",
                    round(result.audio_duration_s / expected_mid_duration, 3),
                    source="auto",
                    notes="~1.0 normal; <<1 truncated; >>1 runaway/hallucination",
                )
            )
            if not (lo <= rate <= hi):
                measurements.append(
                    Measurement(
                        "speech_rate_anomaly",
                        True,
                        source="auto",
                        notes=f"chars/s={rate:.1f} outside [{lo},{hi}]",
                    )
                )

        if reference_audio is not None:
            try:
                score = self.similarity_metric.compare(reference_audio, result.audio_path)
                measurements.append(
                    Measurement("speaker_similarity", round(score, 4), source="auto", higher_is_better=True)
                )
            except (MetricUnavailableError, ImportError):
                logger.debug("Speaker similarity backend unavailable; skipping")

        return measurements
