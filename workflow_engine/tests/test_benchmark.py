"""Benchmark smoke test (Phase C14) — the workflow benchmark runs and passes.

Hermetic (mock voice + mock renderer, low fps): asserts the case completes, warm
resume is a full cache hit, and the incremental rebuild touches only a subset.
"""
from __future__ import annotations

from workflow_engine.benchmark.config import WorkflowBenchmarkConfig
from workflow_engine.benchmark.orchestrator import WorkflowBenchmark, summarize


def test_benchmark_runs_and_reports():
    cfg = WorkflowBenchmarkConfig(fps=6, repetitions=1)
    run, _reports = WorkflowBenchmark(cfg).run(write_reports=False)
    assert len(run.cases) == 1
    case = run.cases[0]
    assert case.status.value == "passed"

    metrics = {m.name: m.value for m in case.measurements}
    assert metrics["stages_total"] == 10
    assert metrics["cache_hits_warm"] == 10                 # warm resume: all cached
    assert metrics["cache_misses_cold"] == 10               # cold run: all missed
    assert metrics["incremental_reused"] > 0                # incremental reuses some
    assert metrics["incremental_rebuilt"] < 10              # ...and rebuilds only some
    assert case.metadata["warm_all_cached"] == "True"
    assert "Workflow orchestration benchmark" in summarize(run)
