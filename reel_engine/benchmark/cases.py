"""Reel benchmark cases (Phase C2).

Subclasses :class:`foundation.benchmarking.BenchmarkCase`, so it inherits the
platform's timing, resource monitoring (peak RSS), and CSV/JSON/Markdown
reporting for free — the mechanism ARCHITECTURE.md describes ("every future
engine gets benchmarking by writing BenchmarkCase subclasses").

One case measures the full deterministic pipeline for a renderer over a fixed
timeline: startup, render (master), export (delta), FPS, and output duration.
"""
from __future__ import annotations

from pathlib import Path

from foundation.benchmarking import BenchmarkCase, CaseResult, Measurement
from foundation.shared_utils import Stopwatch


def _rss_mb() -> float:
    """Current process resident-set size in MB (0.0 if psutil is unavailable).

    A direct snapshot so a memory figure is always recorded even for cases too
    short for the runner's async resource sampler to catch (which then also adds
    a device-wide ``peak_rss_mb`` when it does sample)."""
    try:
        import psutil  # type: ignore[import-not-found]

        return psutil.Process().memory_info().rss / (1024 * 1024)
    except Exception:  # noqa: BLE001 - memory reporting is best-effort
        return 0.0
from reel_engine.benchmark.config import ReelBenchmarkConfig
from reel_engine.config.settings import ReelEngineConfig, RenderConfig
from reel_engine.interfaces.types import RenderRequest
from reel_engine.render import get_renderer
from reel_engine.render.base import scene_frame_count
from reel_engine.timeline.model import build_demo_timeline


class ReelRenderCase(BenchmarkCase):
    """Startup + render + export timing for one renderer over a fixed reel."""

    def __init__(self, cfg: ReelBenchmarkConfig, out_dir: Path, repetition: int = 0) -> None:
        super().__init__(case_id=f"{cfg.renderer}-r{repetition}",
                         subject_id=cfg.renderer, scenario="reel_render")
        self.cfg = cfg
        self.out_dir = out_dir
        self.repetition = repetition

    def execute(self, result: CaseResult) -> None:
        cfg = self.cfg
        engine_cfg = ReelEngineConfig(
            render=RenderConfig(width=cfg.width, height=cfg.height, fps=cfg.fps,
                                renderer=cfg.renderer, mock_max_dim=cfg.mock_max_dim)
        )
        timeline = build_demo_timeline(width=cfg.width, height=cfg.height, fps=cfg.fps,
                                       duration_s=cfg.scene_duration_s)
        total_frames = cfg.n_scenes * scene_frame_count(cfg.scene_duration_s, cfg.fps)
        base = self.out_dir / f"{cfg.renderer}_r{self.repetition}"

        # 1) startup: renderer construction
        with Stopwatch() as sw_start:
            renderer = get_renderer(cfg.renderer, engine_cfg)
        startup_s = sw_start.elapsed_s

        # 2) render master only
        with Stopwatch() as sw_render:
            master = renderer.render(RenderRequest(
                timeline=timeline, output_path=base.with_name(base.name + "_master.avi"),
                renderer=cfg.renderer, export_profiles=()))
        render_s = sw_render.elapsed_s

        # 3) render master + exports; export time is the delta
        with Stopwatch() as sw_full:
            full = renderer.render(RenderRequest(
                timeline=timeline, output_path=base.with_name(base.name + "_full.avi"),
                renderer=cfg.renderer, export_profiles=tuple(cfg.export_profiles)))
        pipeline_s = sw_full.elapsed_s
        export_s = max(0.0, pipeline_s - render_s)

        render_fps = total_frames / render_s if render_s > 0 else 0.0

        result.add(Measurement("startup_ms", round(startup_s * 1000, 2), "ms",
                               higher_is_better=False))
        result.add(Measurement("render_ms", round(render_s * 1000, 2), "ms",
                               higher_is_better=False))
        result.add(Measurement("export_ms", round(export_s * 1000, 2), "ms",
                               higher_is_better=False))
        result.add(Measurement("pipeline_ms", round(pipeline_s * 1000, 2), "ms",
                               higher_is_better=False))
        result.add(Measurement("render_fps", round(render_fps, 1), "fps",
                               higher_is_better=True))
        result.add(Measurement("rss_mb", round(_rss_mb(), 1), "MB",
                               higher_is_better=False))
        result.add(Measurement("output_duration_s", master.duration_s, "s", source="static"))
        result.add(Measurement("total_frames", total_frames, "frames", source="static"))
        result.add(Measurement("n_scenes", timeline.n_scenes, "", source="static"))
        result.add(Measurement("n_exports", len(full.exports), "", source="static"))
        result.metadata["timeline_hash"] = master.timeline_hash
        result.artifacts["master"] = str(master.output_path)
