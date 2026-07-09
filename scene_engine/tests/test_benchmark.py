"""Scene planning benchmark smoke test (Phase C7). Hermetic — pure CPU, no I/O.

Runs a tiny deterministic planning benchmark and asserts every required metric
is recorded (planning time, scene-generation time, timeline-generation time,
throughput, memory) and the case passes. No renderer, ffmpeg, GPU, or model.
"""
from __future__ import annotations

from scene_engine.benchmark import SceneBenchmark, SceneBenchmarkConfig
from scene_engine.benchmark.orchestrator import summarize


def test_benchmark_runs_and_reports_all_metrics(tmp_path):
    cfg = SceneBenchmarkConfig(script_repeats=1, repetitions=1,
                               width=240, height=426, fps=12)
    run, reports = SceneBenchmark(cfg, output_dir=tmp_path).run(write_reports=True)

    assert run.cases and all(c.status.value == "passed" for c in run.cases)
    metrics = {m.name for c in run.cases for m in c.measurements}
    for required in ("planning_ms", "scene_gen_ms", "timeline_gen_ms",
                     "scenes_per_s", "words_per_s", "rss_mb",
                     "n_scenes", "n_words", "plan_duration_s"):
        assert required in metrics, f"missing metric {required}"
    assert reports["json"].exists() and reports["csv"].exists()
    # the summary renders without error and names the run
    assert run.run_id in summarize(run)


def test_benchmark_is_deterministic_in_scene_count():
    cfg = SceneBenchmarkConfig(script_repeats=2, repetitions=2)
    run, _ = SceneBenchmark(cfg).run(write_reports=False)
    counts = {m.value for c in run.cases for m in c.measurements if m.name == "n_scenes"}
    assert len(counts) == 1                       # same input => same scene count
