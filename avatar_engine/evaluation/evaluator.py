"""Automatic evaluation of avatar generation results.

Turns one :class:`GenerationResult` into a list of Measurements. Optional
backends (identity, lip-sync) degrade gracefully: a missing backend logs
once and the corresponding metrics are simply absent from the run — never
silently faked.
"""
from __future__ import annotations

from foundation.benchmarking import Measurement
from foundation.exceptions import MetricUnavailableError
from foundation.logging import get_logger

from avatar_engine.datasets.manager import ResolvedAssets
from avatar_engine.datasets.schema import AvatarScenario
from avatar_engine.evaluation.identity import IdentityConsistencyMetric
from avatar_engine.evaluation.lip_sync import LipSyncMetric
from avatar_engine.evaluation.video_metrics import compute_video_stats
from avatar_engine.models.interface import GenerationResult

logger = get_logger("avatar_engine.evaluation")


class GenerationEvaluator:
    """Computes all automatic metrics for one generated avatar video."""

    def __init__(
        self,
        identity_metric: IdentityConsistencyMetric | None = None,
        lip_sync_metric: LipSyncMetric | None = None,
    ) -> None:
        self.identity_metric = identity_metric or IdentityConsistencyMetric()
        self.lip_sync_metric = lip_sync_metric or LipSyncMetric()
        self._warned: set[str] = set()

    def _warn_once(self, metric: str, reason: str) -> None:
        if metric not in self._warned:
            self._warned.add(metric)
            logger.warning(
                "Optional metric unavailable — omitted from this run",
                extra={"context": {"metric": metric, "reason": reason}},
            )

    def evaluate(
        self,
        result: GenerationResult,
        scenario: AvatarScenario,
        assets: ResolvedAssets,
    ) -> list[Measurement]:
        measurements: list[Measurement] = [
            Measurement("generation_time_s", round(result.generation_time_s, 3), "s"),
            Measurement("video_duration_s", round(result.duration_s, 3), "s"),
            Measurement("output_fps", result.fps, "fps"),
            Measurement("output_width", result.width, "px"),
            Measurement("output_height", result.height, "px"),
        ]
        rtf = result.real_time_factor
        if rtf is not None:
            measurements.append(Measurement("real_time_factor", round(rtf, 3), "x"))

        # Device actually used for inference (A3.8) — so reports show CPU vs GPU.
        device = result.metadata.get("device_actual")
        if device:
            measurements.append(Measurement("device", device, source="static"))

        # Frame statistics (dependency-free for raw AVI, cv2 for codecs)
        try:
            stats = compute_video_stats(result.video_path)
            for name in (
                "mean_frame_difference", "flicker_index", "frozen_frame_ratio",
                "mean_sharpness", "sharpness_drift", "mean_brightness",
            ):
                measurements.append(Measurement(name, getattr(stats, name)))
        except MetricUnavailableError as exc:
            self._warn_once("video_stats", str(exc))

        # Identity consistency (optional backend)
        try:
            identity = self.identity_metric.compare(assets.source_image, result.video_path)
            measurements.append(Measurement("identity_similarity", identity.mean_similarity))
            measurements.append(Measurement("identity_drift", identity.drift))
        except MetricUnavailableError as exc:
            self._warn_once("identity_similarity", str(exc))

        # Lip sync (optional backend), only meaningful with driving audio
        if assets.driving_audio.exists():
            try:
                sync = self.lip_sync_metric.score(result.video_path, assets.driving_audio)
                measurements.append(Measurement("lip_sync_confidence", sync.confidence))
                measurements.append(Measurement("lip_sync_distance", sync.distance))
            except MetricUnavailableError as exc:
                self._warn_once("lip_sync_confidence", str(exc))

        return measurements
