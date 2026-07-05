"""Generic benchmarking framework.

Engine-agnostic: knows nothing about voice, avatars, or any specific model.
The Voice Engine benchmark (and future Avatar/Reel benchmarks) compose these
primitives with their own cases and metrics.
"""

from foundation.benchmarking.results import (
    CaseStatus,
    Measurement,
    CaseResult,
    RunResult,
)
from foundation.benchmarking.runner import BenchmarkCase, BenchmarkRunner
from foundation.benchmarking.resource_monitor import ResourceMonitor, ResourceSample

__all__ = [
    "CaseStatus",
    "Measurement",
    "CaseResult",
    "RunResult",
    "BenchmarkCase",
    "BenchmarkRunner",
    "ResourceMonitor",
    "ResourceSample",
]
