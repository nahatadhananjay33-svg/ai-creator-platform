"""Caption benchmark smoke test (Phase C4). Hermetic — mock renderer, no ffmpeg.

Runs a tiny deterministic benchmark and asserts every required metric is
recorded (caption generation, render overhead, export, subtitle export, memory)
and the cases pass.
"""
from __future__ import annotations

from caption_engine.benchmark import CaptionBenchmark, CaptionBenchmarkConfig


def test_benchmark_runs_and_reports_all_metrics(tmp_path):
    cfg = CaptionBenchmarkConfig(
        renderer="mock", kind="karaoke", duration_s=3.0,
        width=240, height=426, fps=12, scene_duration_s=1.5, n_scenes=2,
        export_profiles=["square_1x1"], repetitions=1, mock_max_dim=96,
    )
    run, reports = CaptionBenchmark(cfg, output_dir=tmp_path).run(write_reports=True)

    assert run.cases and all(c.status.value == "passed" for c in run.cases)
    metrics = {m.name for c in run.cases for m in c.measurements}
    for required in ("caption_gen_ms", "render_base_ms", "render_caps_ms",
                     "caption_render_overhead_ms", "export_ms",
                     "subtitle_export_ms", "rss_mb"):
        assert required in metrics, f"missing metric {required}"
    assert reports["json"].exists() and reports["csv"].exists()
