"""Metric catalog: what we measure, how, and which direction is better.

This is the contract between evaluation, reporting, and documentation.
Reports group by ``source`` so automatically measured values are never
presented as if they were perceptual judgments.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MetricDefinition:
    name: str
    description: str
    unit: str
    source: str  # "auto" | "human"
    higher_is_better: bool | None


AUTO_METRICS: tuple[MetricDefinition, ...] = (
    MetricDefinition("real_time_factor", "Synthesis time / audio duration", "x", "auto", False),
    MetricDefinition("first_chunk_latency_s", "Time to first streamed audio chunk", "s", "auto", False),
    MetricDefinition("synthesis_time_s", "Wall-clock synthesis time", "s", "auto", False),
    MetricDefinition("audio_duration_s", "Duration of generated audio", "s", "auto", None),
    MetricDefinition("chars_per_second_audio", "Text chars per second of audio (speech-rate proxy; ~12-18 natural for EN)", "chars/s", "auto", None),
    MetricDefinition("rms_dbfs", "Overall loudness", "dBFS", "auto", None),
    MetricDefinition("clipping_ratio", "Fraction of clipped samples", "", "auto", False),
    MetricDefinition("silence_ratio", "Fraction of silent frames", "", "auto", False),
    MetricDefinition("leading_silence_s", "Dead air before speech", "s", "auto", False),
    MetricDefinition("trailing_silence_s", "Dead air after speech", "s", "auto", False),
    MetricDefinition("longest_internal_silence_s", "Longest mid-utterance gap (stall/hallucination indicator)", "s", "auto", False),
    MetricDefinition("speaker_similarity", "Embedding cosine similarity to reference voice (GE2E)", "", "auto", True),
    MetricDefinition("peak_rss_mb", "Peak process RAM during case", "MB", "auto", False),
    MetricDefinition("peak_gpu_mem_mb", "Peak allocated GPU memory during case", "MB", "auto", False),
    MetricDefinition("duration_ratio_vs_expected", "Audio duration vs speech-rate expectation (truncation/runaway detector)", "", "auto", None),
)

HUMAN_METRICS: tuple[MetricDefinition, ...] = (
    MetricDefinition("mos_naturalness", "Mean opinion score: naturalness (1-5)", "MOS", "human", True),
    MetricDefinition("mos_pronunciation", "Pronunciation correctness incl. names/numbers (1-5)", "MOS", "human", True),
    MetricDefinition("mos_accent", "Accent authenticity for target language (1-5)", "MOS", "human", True),
    MetricDefinition("mos_emotion", "Expressiveness / emotional appropriateness (1-5)", "MOS", "human", True),
    MetricDefinition("smos_similarity", "Similarity MOS vs reference speaker (1-5)", "SMOS", "human", True),
    MetricDefinition("code_switch_quality", "Fluency across HI<->EN switch points (1-5)", "MOS", "human", True),
    MetricDefinition("longform_consistency", "Voice/energy consistency across long narration (1-5)", "MOS", "human", True),
    MetricDefinition("artifact_severity", "Audible artifacts: 5=none, 1=unusable", "MOS", "human", True),
)


def metric_by_name(name: str) -> MetricDefinition | None:
    for metric in (*AUTO_METRICS, *HUMAN_METRICS):
        if metric.name == name:
            return metric
    return None
