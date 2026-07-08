"""Reel benchmark tests (Phase C2). Hermetic — mock renderer, no FFmpeg/GPU."""
from __future__ import annotations

from reel_engine.benchmark import ReelBenchmark, ReelBenchmarkConfig, summarize


def _cfg():
    return ReelBenchmarkConfig(renderer="mock", n_scenes=3, scene_duration_s=1.0,
                               width=1080, height=1920, fps=20, repetitions=2,
                               mock_max_dim=64)


def test_benchmark_runs_all_cases_passed(tmp_path):
    run, reports = ReelBenchmark(_cfg(), output_dir=tmp_path).run()
    assert len(run.cases) == 2
    assert all(c.status.value == "passed" for c in run.cases)
    assert run.environment  # hardware probe populated
    assert reports["json"].exists() and reports["csv"].exists()


def test_benchmark_measurements_present_and_sane(tmp_path):
    run, _ = ReelBenchmark(_cfg(), output_dir=tmp_path).run()
    case = run.cases[0]
    names = {m.name for m in case.measurements}
    for expected in ("startup_ms", "render_ms", "export_ms", "pipeline_ms",
                     "render_fps", "output_duration_s", "total_frames"):
        assert expected in names, expected
    assert case.get_value("output_duration_s") == 3.0        # 3 x 1.0s
    assert case.get_value("total_frames") == 3 * 20          # deterministic workload
    assert case.get_value("render_fps") > 0
    # memory: the case always records a direct RSS snapshot; the generic runner
    # additionally attaches peak_rss_mb when its async sampler catches a sample.
    assert case.get_value("rss_mb") is not None and case.get_value("rss_mb") > 0


def test_workload_is_deterministic_across_repetitions(tmp_path):
    run, _ = ReelBenchmark(_cfg(), output_dir=tmp_path).run()
    hashes = {c.metadata.get("timeline_hash") for c in run.cases}
    assert len(hashes) == 1 and next(iter(hashes))            # identical workload


def test_summarize_is_readable(tmp_path):
    run, _ = ReelBenchmark(_cfg(), output_dir=tmp_path).run()
    text = summarize(run)
    assert "mock" in text and "render_fps" in text
