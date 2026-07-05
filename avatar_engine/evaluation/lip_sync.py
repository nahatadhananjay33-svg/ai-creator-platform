"""Lip-sync metric (optional backend).

Reports SyncNet-style audio-visual synchronization scores — the community
standard LSE-C (confidence, higher better) and LSE-D (distance, lower
better) used by Wav2Lip, LatentSync, and most talking-head papers, so our
numbers are directly comparable with published results.

Backend: ``syncnet`` weights + torch pipeline (see
``avatar_engine/docs/BENCHMARKING.md`` for setup). Until installed the
metric declares itself unavailable and the evaluator records the human
lip-sync MOS as the authoritative score.
"""
from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path

from foundation.exceptions import MetricUnavailableError
from foundation.logging import get_logger

logger = get_logger("avatar_engine.evaluation.lip_sync")


@dataclass(frozen=True)
class LipSyncResult:
    confidence: float  # LSE-C analog, higher is better
    distance: float    # LSE-D analog, lower is better


class LipSyncMetric:
    """SyncNet-based audio-visual sync scoring."""

    @property
    def available(self) -> bool:
        return all(
            importlib.util.find_spec(pkg) is not None for pkg in ("torch", "cv2", "scenedetect")
        ) and self._weights_present()

    @staticmethod
    def _weights_present() -> bool:
        from foundation.constants.paths import MODEL_WEIGHTS_DIR

        return (MODEL_WEIGHTS_DIR / "syncnet" / "syncnet_v2.model").exists()

    def score(self, video_path: Path, audio_path: Path) -> LipSyncResult:
        """Raises :class:`MetricUnavailableError` until the backend is set up.

        GPU-machine setup (Phase A4 prerequisite): clone
        joonson/syncnet_python, place syncnet_v2.model under
        ``MODEL_WEIGHTS_DIR/syncnet/``, and implement the pipeline call here.
        The interface is frozen now so benchmark cases and reports do not
        change when the backend lands.
        """
        if not self.available:
            raise MetricUnavailableError(
                "Lip-sync scoring requires the SyncNet backend (torch + weights); "
                "see avatar_engine/docs/BENCHMARKING.md",
                metric="lip_sync_confidence",
            )
        raise MetricUnavailableError(
            "SyncNet pipeline integration lands with the first GPU benchmark "
            "run (Phase A4); interface is frozen, implementation pending",
            metric="lip_sync_confidence",
        )
