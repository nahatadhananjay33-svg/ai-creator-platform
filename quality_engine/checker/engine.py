"""The Quality Checker facade (Phase C16).

One small object ties the pieces together: probe the reel's files, run the fixed
checks over the measured facts, and roll them into a :class:`QualityReport`. It is
a pure function of its inputs — the same rendered reel always yields the same
report — and it is the single entry point the CLI and the Workflow integration use.
"""
from __future__ import annotations

from quality_engine.checker.checks import run_checks
from quality_engine.checker.config import QualityConfig
from quality_engine.checker.inspect import inspect_reel
from quality_engine.checker.model import ReelArtifacts
from quality_engine.checker.report import QualityReport


class QualityChecker:
    """Runs the deterministic reel checks and produces a :class:`QualityReport`."""

    def __init__(self, config: QualityConfig | None = None) -> None:
        self.config = config or QualityConfig()

    def check(self, artifacts: ReelArtifacts) -> QualityReport:
        """Probe + check one rendered reel."""
        inspection = inspect_reel(artifacts)
        checks = run_checks(artifacts, inspection, self.config)
        meta = {
            "renderer": artifacts.renderer,
            "master": str(artifacts.master_path),
            "width": inspection.width,
            "height": inspection.height,
            "fps": inspection.fps,
            "duration_s": round(inspection.video_duration_s, 3),
            "n_frames": inspection.n_frames,
            "audio_source": inspection.audio_source,
            "n_exports": len(inspection.exports),
            "probe_errors": list(inspection.errors),
        }
        return QualityReport(checks=checks, meta=meta)


def check_reel(artifacts: ReelArtifacts, *, config: QualityConfig | None = None) -> QualityReport:
    """Convenience: check one reel with a fresh :class:`QualityChecker`."""
    return QualityChecker(config).check(artifacts)
