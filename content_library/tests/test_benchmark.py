"""Benchmark smoke test (Phase C15) — the library benchmark runs and passes."""
from __future__ import annotations

from content_library.benchmark.config import LibraryBenchmarkConfig
from content_library.benchmark.orchestrator import LibraryBenchmark, summarize


def test_benchmark_runs_and_reports():
    cfg = LibraryBenchmarkConfig(n_projects=20, n_queries=10, repetitions=1)
    run, _reports = LibraryBenchmark(cfg).run(write_reports=False)
    assert len(run.cases) == 1
    case = run.cases[0]
    assert case.status.value == "passed"
    metrics = {m.name: m.value for m in case.measurements}
    assert metrics["n_projects"] == 20
    assert metrics["save_ms_per_project"] >= 0
    assert metrics["load_projects_per_s"] > 0
    assert case.metadata["index_size"] == "20"
    assert "Content Library benchmark" in summarize(run)
