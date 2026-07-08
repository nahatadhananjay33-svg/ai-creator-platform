"""Caption Engine benchmark (Phase C4): deterministic caption generation,
render-overhead, export, and subtitle-export timing.

Reuses foundation.benchmarking (BenchmarkCase/Runner/RunResult) for resource
monitoring and reporting. Hermetic by default (mock renderer); no AI, no GPU.
"""
from __future__ import annotations

from caption_engine.benchmark.cases import CaptionBenchmarkCase
from caption_engine.benchmark.config import CaptionBenchmarkConfig
from caption_engine.benchmark.orchestrator import CaptionBenchmark, summarize

__all__ = [
    "CaptionBenchmark",
    "CaptionBenchmarkConfig",
    "CaptionBenchmarkCase",
    "summarize",
]
