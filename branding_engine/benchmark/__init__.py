"""Branding Engine benchmark (Phase C5): deterministic branding generation,
render-overhead, export, startup, and memory timing.

Reuses foundation.benchmarking for resource monitoring and reporting. Hermetic
by default (mock renderer); no AI, no GPU.
"""
from __future__ import annotations

from branding_engine.benchmark.cases import BrandingBenchmarkCase
from branding_engine.benchmark.config import BrandingBenchmarkConfig
from branding_engine.benchmark.orchestrator import BrandingBenchmark, summarize

__all__ = [
    "BrandingBenchmark",
    "BrandingBenchmarkConfig",
    "BrandingBenchmarkCase",
    "summarize",
]
