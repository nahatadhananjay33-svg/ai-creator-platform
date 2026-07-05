"""Evaluation framework: metric suites over synthesis results.

Composes ``voice_engine.metrics`` computations into Measurement lists that
attach to benchmark CaseResults. Also defines the human listening protocol —
automatic and human metrics are explicitly separated via Measurement.source.
"""

from voice_engine.evaluation.criteria import AUTO_METRICS, HUMAN_METRICS, MetricDefinition
from voice_engine.evaluation.evaluator import SynthesisEvaluator
from voice_engine.evaluation.human_eval import HumanEvalProtocol

__all__ = [
    "AUTO_METRICS",
    "HUMAN_METRICS",
    "MetricDefinition",
    "SynthesisEvaluator",
    "HumanEvalProtocol",
]
