"""Branding benchmark smoke test (Phase C5). Hermetic — mock renderer, no ffmpeg.

Runs a tiny deterministic benchmark and asserts every required metric is
recorded (branding generation, render overhead, export, startup, memory) and
the cases pass.
"""
from __future__ import annotations

from branding_engine.benchmark import BrandingBenchmark, BrandingBenchmarkConfig


def test_benchmark_runs_and_reports_all_metrics(tmp_path):
    cfg = BrandingBenchmarkConfig(
        renderer="mock", theme="corporate", width=240, height=426, fps=12,
        scene_duration_s=3.0, n_scenes=2, export_profiles=["square_1x1"],
        repetitions=1, mock_max_dim=96,
    )
    run, reports = BrandingBenchmark(cfg, output_dir=tmp_path).run(write_reports=True)

    assert run.cases and all(c.status.value == "passed" for c in run.cases)
    metrics = {m.name for c in run.cases for m in c.measurements}
    for required in ("startup_ms", "branding_gen_ms", "render_base_ms",
                     "render_brand_ms", "branding_render_overhead_ms",
                     "export_ms", "rss_mb"):
        assert required in metrics, f"missing metric {required}"
    assert reports["json"].exists() and reports["csv"].exists()
