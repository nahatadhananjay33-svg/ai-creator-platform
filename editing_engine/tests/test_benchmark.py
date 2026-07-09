"""Editing benchmark smoke test (Phase C11). Hermetic — MockProvider, no ffmpeg.

Runs a tiny deterministic benchmark and asserts every required metric is recorded
(patch application, incremental regeneration, timeline validation, memory) and the
case passes with a valid timeline.
"""
from __future__ import annotations

from editing_engine.benchmark import EditBenchmark, EditBenchmarkConfig
from editing_engine.benchmark.orchestrator import summarize


def test_benchmark_runs_and_reports_all_metrics(tmp_path):
    cfg = EditBenchmarkConfig(n_patches=4, repetitions=1)
    run, reports = EditBenchmark(cfg, output_dir=tmp_path).run(write_reports=True)

    assert run.cases and all(c.status.value == "passed" for c in run.cases)
    metrics = {m.name for c in run.cases for m in c.measurements}
    for required in ("patch_apply_ms", "incremental_regen_ms", "timeline_validation_ms",
                     "incremental_plan_ms", "rss_mb"):
        assert required in metrics, f"missing metric {required}"
    assert reports["json"].exists() and reports["csv"].exists()
    assert run.run_id in summarize(run)
    assert all(c.metadata.get("timeline_valid") == "True" for c in run.cases)
