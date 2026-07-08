"""Reels Engine benchmark: deterministic render/export timing + throughput.

Reuses foundation.benchmarking (BenchmarkCase/Runner/RunResult) so it gets
resource monitoring and reporting for free. No AI, no GPU.
"""
from __future__ import annotations

from reel_engine.benchmark.cases import ReelRenderCase
from reel_engine.benchmark.config import ReelBenchmarkConfig
from reel_engine.benchmark.orchestrator import ReelBenchmark, summarize

__all__ = ["ReelBenchmark", "ReelBenchmarkConfig", "ReelRenderCase", "summarize"]
