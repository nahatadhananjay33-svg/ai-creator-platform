"""Avatar benchmark: config, cases, and orchestration.

Composes the generic ``foundation.benchmarking`` primitives with avatar
scenarios and evaluation — same structure as ``voice_engine.benchmark``.
"""

from avatar_engine.benchmark.config import AvatarBenchmarkConfig
from avatar_engine.benchmark.orchestrator import AvatarBenchmark
from avatar_engine.benchmark.scenarios import GenerationScenarioCase

__all__ = [
    "AvatarBenchmark",
    "AvatarBenchmarkConfig",
    "GenerationScenarioCase",
]
