"""Avatar metric catalog: what we measure, how, and which direction is better.

The contract between evaluation, reporting, and documentation — reports
group by ``source`` so automatically measured values are never presented as
perceptual judgments (same rule as the voice engine).

Three sources:
- ``auto``   — measured by code in this package during a benchmark run
- ``human``  — blind rater scores collected via the human-eval protocol
- ``static`` — research priors from the catalog (papers/community), used
               only until measurements exist
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
    # --- performance
    MetricDefinition("generation_time_s", "Wall-clock generation time", "s", "auto", False),
    MetricDefinition("real_time_factor", "Generation time / video duration", "x", "auto", False),
    MetricDefinition("video_duration_s", "Duration of generated video", "s", "auto", None),
    MetricDefinition("output_fps", "Frame rate of generated video", "fps", "auto", None),
    MetricDefinition("output_width", "Frame width", "px", "auto", None),
    MetricDefinition("output_height", "Frame height", "px", "auto", None),
    MetricDefinition("peak_rss_mb", "Peak process RAM during case", "MB", "auto", False),
    MetricDefinition("peak_gpu_mem_mb", "Peak GPU memory during case", "MB", "auto", False),
    # --- frame statistics (dependency-free)
    MetricDefinition("mean_frame_difference", "Mean abs luma delta between consecutive frames (motion energy)", "", "auto", None),
    MetricDefinition("flicker_index", "Std-dev of frame-to-frame luma delta (temporal instability)", "", "auto", False),
    MetricDefinition("frozen_frame_ratio", "Fraction of consecutive frame pairs with ~zero change (stalls)", "", "auto", False),
    MetricDefinition("mean_sharpness", "Mean Laplacian energy over sampled frames (blur detector)", "", "auto", True),
    MetricDefinition("sharpness_drift", "Relative sharpness change first->last third (quality decay)", "", "auto", None),
    MetricDefinition("mean_brightness", "Mean luma over sampled frames", "", "auto", None),
    # --- optional-backend metrics
    MetricDefinition("lip_sync_confidence", "SyncNet-style audio-visual sync confidence (LSE-C analog)", "", "auto", True),
    MetricDefinition("lip_sync_distance", "SyncNet-style audio-visual sync distance (LSE-D analog)", "", "auto", False),
    MetricDefinition("identity_similarity", "Mean face-embedding cosine similarity of frames vs source image", "", "auto", True),
    MetricDefinition("identity_drift", "Similarity drop from first to last video third", "", "auto", False),
)

HUMAN_METRICS: tuple[MetricDefinition, ...] = (
    MetricDefinition("mos_lip_sync", "Lip-sync accuracy and naturalness (1-5)", "MOS", "human", True),
    MetricDefinition("mos_expression", "Facial expression quality/appropriateness (1-5)", "MOS", "human", True),
    MetricDefinition("mos_head_movement", "Head movement naturalness (1-5)", "MOS", "human", True),
    MetricDefinition("mos_motion_realism", "Overall motion realism, body incl. if present (1-5)", "MOS", "human", True),
    MetricDefinition("mos_identity", "Does it stay the same person as the source? (1-5)", "MOS", "human", True),
    MetricDefinition("mos_video_quality", "Perceived visual quality: sharpness, artifacts (1-5)", "MOS", "human", True),
    MetricDefinition("mos_uncanny", "Comfort level: 5=natural, 1=deeply uncanny", "MOS", "human", True),
    MetricDefinition("mos_overall", "Overall usability as creator content (1-5)", "MOS", "human", True),
)


def metric_by_name(name: str) -> MetricDefinition | None:
    for metric in (*AUTO_METRICS, *HUMAN_METRICS):
        if metric.name == name:
            return metric
    return None
