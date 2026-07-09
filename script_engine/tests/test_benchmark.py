"""AI prompt-to-reel benchmark smoke test (Phase C10). Hermetic — MockProvider.

Runs a tiny deterministic benchmark and asserts every required metric is recorded
(provider latency, storyboard generation, validation, scene generation, total
pipeline time, memory) and the cases pass.
"""
from __future__ import annotations

from script_engine.benchmark import ScriptBenchmark, ScriptBenchmarkConfig
from script_engine.benchmark.orchestrator import summarize


def test_benchmark_runs_and_reports_all_metrics(tmp_path):
    cfg = ScriptBenchmarkConfig(provider="mock", template="general", repetitions=1)
    run, reports = ScriptBenchmark(cfg, output_dir=tmp_path).run(write_reports=True)

    assert run.cases and all(c.status.value == "passed" for c in run.cases)
    metrics = {m.name for c in run.cases for m in c.measurements}
    for required in ("provider_ms", "storyboard_gen_ms", "validation_ms",
                     "scene_gen_ms", "timeline_gen_ms", "total_pipeline_ms", "rss_mb"):
        assert required in metrics, f"missing metric {required}"
    assert reports["json"].exists() and reports["csv"].exists()
    assert run.run_id in summarize(run)
