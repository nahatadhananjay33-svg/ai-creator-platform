"""Voice model benchmark: thin orchestration over production modules.

Architectural rule (Phase A1): this package contains NO model logic, NO
metric math, and NO report formatting — it only composes:

- ``voice_engine.adapters``      (production model access)
- ``voice_engine.datasets``      (prompt corpora)
- ``voice_engine.evaluation``    (metric suites)
- ``voice_engine.reporting``     (outputs)
- ``foundation.benchmarking``    (runner, timing, resources)
"""

from voice_engine.benchmark.config import VoiceBenchmarkConfig
from voice_engine.benchmark.orchestrator import VoiceBenchmark

__all__ = ["VoiceBenchmarkConfig", "VoiceBenchmark"]
