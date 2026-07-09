"""Visual Asset Engine benchmark (Phase C6): deterministic asset loading,
timeline generation, render-overhead, export, memory, and FPS timing.

Reuses foundation.benchmarking for resource monitoring and reporting. Hermetic
by default (mock renderer); no AI, no GPU, no downloads.
"""
from __future__ import annotations

from asset_engine.benchmark.cases import AssetBenchmarkCase
from asset_engine.benchmark.config import AssetBenchmarkConfig
from asset_engine.benchmark.orchestrator import AssetBenchmark, summarize
from asset_engine.benchmark.resolver import (
    ResolverBenchmark,
    ResolverBenchmarkCase,
    ResolverBenchmarkConfig,
)

__all__ = [
    "AssetBenchmark", "AssetBenchmarkConfig", "AssetBenchmarkCase", "summarize",
    "ResolverBenchmark", "ResolverBenchmarkConfig", "ResolverBenchmarkCase",
]
