"""Quality Checker internals (Phase C16) — probe, check, report.

The pipeline is three pure steps: :func:`inspect_reel` measures the reel's files
-> :func:`run_checks` applies the fixed rules -> a :class:`QualityReport` rolls up
the verdict. :class:`QualityChecker` is the facade over all three.
"""
from __future__ import annotations

from quality_engine.checker.checks import CHECKS, run_checks
from quality_engine.checker.config import QualityConfig
from quality_engine.checker.engine import QualityChecker, check_reel
from quality_engine.checker.inspect import inspect_reel
from quality_engine.checker.model import (
    ExportInfo,
    ExportProbe,
    ReelArtifacts,
    ReelInspection,
)
from quality_engine.checker.report import CheckResult, CheckStatus, QualityReport

__all__ = [
    "QualityChecker",
    "check_reel",
    "QualityConfig",
    "inspect_reel",
    "run_checks",
    "CHECKS",
    "ReelArtifacts",
    "ExportInfo",
    "ReelInspection",
    "ExportProbe",
    "QualityReport",
    "CheckResult",
    "CheckStatus",
]
