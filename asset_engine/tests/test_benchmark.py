"""Asset benchmark smoke test (Phase C6). Hermetic — mock renderer, no ffmpeg.

Runs a tiny deterministic benchmark and asserts every required metric is
recorded (asset loading, timeline generation, render overhead, export, memory,
FPS) and the cases pass.
"""
from __future__ import annotations

from asset_engine.benchmark import AssetBenchmark, AssetBenchmarkConfig


def test_benchmark_runs_and_reports_all_metrics(tmp_path):
    cfg = AssetBenchmarkConfig(
        renderer="mock", layout="picture_in_picture", n_assets=3,
        width=240, height=426, fps=12, scene_duration_s=2.0, n_scenes=2,
        export_profiles=["square_1x1"], repetitions=1, mock_max_dim=96,
    )
    run, reports = AssetBenchmark(cfg, output_dir=tmp_path).run(write_reports=True)

    assert run.cases and all(c.status.value == "passed" for c in run.cases)
    metrics = {m.name for c in run.cases for m in c.measurements}
    for required in ("asset_load_ms", "timeline_gen_ms", "render_base_ms",
                     "render_assets_ms", "asset_render_overhead_ms", "export_ms",
                     "render_fps", "rss_mb"):
        assert required in metrics, f"missing metric {required}"
    assert reports["json"].exists() and reports["csv"].exists()
