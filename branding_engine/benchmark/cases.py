"""Branding benchmark cases (Phase C5).

Subclasses :class:`foundation.benchmarking.BenchmarkCase`, inheriting timing,
resource monitoring (peak RSS), and reporting. One case measures the full
deterministic branding path over a fixed timeline:

    startup → branding generation → render overhead (with vs without branding)
    → export → memory

Hermetic by default (mock renderer): no FFmpeg/GPU.
"""
from __future__ import annotations

import dataclasses
from pathlib import Path

from foundation.benchmarking import BenchmarkCase, CaseResult, Measurement
from foundation.shared_utils import Stopwatch

from branding_engine.assets import default_logo_path
from branding_engine.benchmark.config import BrandingBenchmarkConfig
from branding_engine.engine import BrandingEngine


def _rss_mb() -> float:
    try:
        import psutil  # type: ignore[import-not-found]

        return psutil.Process().memory_info().rss / (1024 * 1024)
    except Exception:  # noqa: BLE001 - memory reporting is best-effort
        return 0.0


from reel_engine.config.settings import ReelEngineConfig, RenderConfig
from reel_engine.interfaces.types import RenderRequest
from reel_engine.render import get_renderer
from reel_engine.timeline.model import storyboard


class BrandingBenchmarkCase(BenchmarkCase):
    """Startup + branding generation + render overhead + export timing."""

    def __init__(self, cfg: BrandingBenchmarkConfig, out_dir: Path, repetition: int = 0) -> None:
        super().__init__(case_id=f"{cfg.renderer}-{cfg.theme}-r{repetition}",
                         subject_id=f"{cfg.renderer}-{cfg.theme}", scenario="branding_render")
        self.cfg = cfg
        self.out_dir = out_dir
        self.repetition = repetition

    def _timeline(self):
        cfg = self.cfg
        beats = [(("blue" if i % 2 == 0 else "green"), f"Scene {i + 1}",
                  cfg.scene_duration_s) for i in range(cfg.n_scenes)]
        return storyboard(beats, title="branding benchmark",
                          width=cfg.width, height=cfg.height, fps=cfg.fps)

    def execute(self, result: CaseResult) -> None:
        cfg = self.cfg
        engine_cfg = ReelEngineConfig(
            render=RenderConfig(width=cfg.width, height=cfg.height, fps=cfg.fps,
                                renderer=cfg.renderer, mock_max_dim=cfg.mock_max_dim))
        base = self.out_dir / f"{self.case_id}"
        no_brand = self._timeline()
        dur = no_brand.duration_s

        # 1) startup: renderer construction
        with Stopwatch() as sw_start:
            renderer = get_renderer(cfg.renderer, engine_cfg)
        startup_s = sw_start.elapsed_s

        # 2) branding generation (theme + brand facts -> BrandingTrack)
        with Stopwatch() as sw_gen:
            track = BrandingEngine().generate(
                reel_duration_s=dur, theme=cfg.theme, creator=cfg.creator,
                channel=cfg.channel, logo_path=default_logo_path())
        gen_s = sw_gen.elapsed_s
        with_brand = dataclasses.replace(no_brand, branding=track)

        # 3) render WITHOUT branding (baseline)
        with Stopwatch() as sw_base:
            renderer.render(RenderRequest(
                timeline=no_brand, output_path=base.with_name(base.name + "_base.avi"),
                renderer=cfg.renderer, export_profiles=()))
        render_base_s = sw_base.elapsed_s

        # 4) render WITH branding (master only) -> overhead is the delta
        with Stopwatch() as sw_brand:
            master = renderer.render(RenderRequest(
                timeline=with_brand, output_path=base.with_name(base.name + "_brand.avi"),
                renderer=cfg.renderer, export_profiles=()))
        render_brand_s = sw_brand.elapsed_s

        # 5) render + export profiles -> export time is the delta
        with Stopwatch() as sw_full:
            full = renderer.render(RenderRequest(
                timeline=with_brand, output_path=base.with_name(base.name + "_full.avi"),
                renderer=cfg.renderer, export_profiles=tuple(cfg.export_profiles)))
        export_s = max(0.0, sw_full.elapsed_s - render_brand_s)

        result.add(Measurement("startup_ms", round(startup_s * 1000, 3), "ms",
                               higher_is_better=False))
        result.add(Measurement("branding_gen_ms", round(gen_s * 1000, 3), "ms",
                               higher_is_better=False))
        result.add(Measurement("render_base_ms", round(render_base_s * 1000, 2), "ms",
                               higher_is_better=False))
        result.add(Measurement("render_brand_ms", round(render_brand_s * 1000, 2), "ms",
                               higher_is_better=False))
        result.add(Measurement("branding_render_overhead_ms",
                               round((render_brand_s - render_base_s) * 1000, 2), "ms",
                               higher_is_better=False))
        result.add(Measurement("export_ms", round(export_s * 1000, 2), "ms",
                               higher_is_better=False))
        result.add(Measurement("rss_mb", round(_rss_mb(), 1), "MB", higher_is_better=False))
        n_components = (sum(x is not None for x in
                            (track.logo, track.watermark, track.intro, track.outro))
                        + len(track.lower_thirds))
        result.add(Measurement("n_components", n_components, "", source="static"))
        result.add(Measurement("output_duration_s", master.duration_s, "s", source="static"))
        result.metadata["timeline_hash"] = master.timeline_hash
        result.metadata["theme"] = cfg.theme
        result.artifacts["master"] = str(master.output_path)
        result.artifacts["n_exports"] = str(len(full.exports))
