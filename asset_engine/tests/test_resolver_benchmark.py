"""Resolver benchmark smoke test (Phase C9). Hermetic — no ffmpeg, no AI.

Runs a tiny deterministic retrieval benchmark and asserts every required metric
is recorded (catalog loading, lookup, ranking, selection, memory) and the cases
pass with every slot satisfied.
"""
from __future__ import annotations

from asset_engine.benchmark import ResolverBenchmark, ResolverBenchmarkConfig
from asset_engine.benchmark.resolver import summarize


def test_resolver_benchmark_reports_all_metrics(tmp_path):
    cfg = ResolverBenchmarkConfig(catalog_size=10, n_slots=5, repetitions=1)
    run, reports = ResolverBenchmark(cfg, output_dir=tmp_path).run(write_reports=True)

    assert run.cases and all(c.status.value == "passed" for c in run.cases)
    metrics = {m.name for c in run.cases for m in c.measurements}
    for required in ("catalog_load_ms", "lookup_ms_per_slot", "ranking_ms_per_slot",
                     "selection_ms_per_slot", "resolve_throughput", "rss_mb"):
        assert required in metrics, f"missing metric {required}"
    assert reports["json"].exists() and reports["csv"].exists()
    assert run.run_id in summarize(run)
