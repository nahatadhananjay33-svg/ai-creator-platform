"""Avatar evaluation: automatic metrics, optional backends, human protocol."""

from avatar_engine.evaluation.criteria import (
    AUTO_METRICS,
    HUMAN_METRICS,
    MetricDefinition,
    metric_by_name,
)
from avatar_engine.evaluation.evaluator import GenerationEvaluator
from avatar_engine.evaluation.human_eval import AvatarHumanEvalProtocol, BlindSample
from avatar_engine.evaluation.identity import IdentityConsistencyMetric, IdentityResult
from avatar_engine.evaluation.lip_sync import LipSyncMetric, LipSyncResult
from avatar_engine.evaluation.video_metrics import VideoStats, compute_video_stats

__all__ = [
    "AUTO_METRICS",
    "AvatarHumanEvalProtocol",
    "BlindSample",
    "GenerationEvaluator",
    "HUMAN_METRICS",
    "IdentityConsistencyMetric",
    "IdentityResult",
    "LipSyncMetric",
    "LipSyncResult",
    "MetricDefinition",
    "VideoStats",
    "compute_video_stats",
    "metric_by_name",
]
