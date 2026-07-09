"""Music benchmark smoke test (Phase C8). Hermetic — mock renderer, no ffmpeg.

Runs a tiny deterministic benchmark and asserts every required metric is
recorded (music loading, mixing overhead, render overhead, export, memory, render
time) and the case passes.
"""
from __future__ import annotations

from music_engine.benchmark import MusicBenchmark, MusicBenchmarkConfig
from music_engine.benchmark.orchestrator import summarize


def test_benchmark_runs_and_reports_all_metrics(tmp_path):
    cfg = MusicBenchmarkConfig(
        renderer="mock", soundtrack="ambient", reel_duration_s=4.0, n_scenes=2,
        width=240, height=426, fps=12, sample_rate=8000,
        export_profiles=["square_1x1"], repetitions=1, mock_max_dim=96,
    )
    run, reports = MusicBenchmark(cfg, output_dir=tmp_path).run(write_reports=True)

    assert run.cases and all(c.status.value == "passed" for c in run.cases)
    metrics = {m.name for c in run.cases for m in c.measurements}
    for required in ("music_load_ms", "mix_ms", "render_base_ms", "render_music_ms",
                     "music_render_overhead_ms", "export_ms", "render_fps", "rss_mb"):
        assert required in metrics, f"missing metric {required}"
    assert reports["json"].exists() and reports["csv"].exists()
    assert run.run_id in summarize(run)
