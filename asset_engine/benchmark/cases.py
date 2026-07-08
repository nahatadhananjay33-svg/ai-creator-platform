"""Asset benchmark cases (Phase C6).

Subclasses :class:`foundation.benchmarking.BenchmarkCase`, inheriting timing,
resource monitoring (peak RSS), and reporting. One case measures the full
deterministic visual-asset path over a fixed timeline:

    asset loading → timeline generation → render overhead (with vs without
    assets) → export → memory → FPS

Hermetic by default (mock renderer): images are placeholder PNGs, never decoded
by the mock backend. No AI, no GPU, no downloads.
"""
from __future__ import annotations

import dataclasses
from pathlib import Path

from foundation.benchmarking import BenchmarkCase, CaseResult, Measurement
from foundation.shared_utils import Stopwatch

from asset_engine.benchmark.config import AssetBenchmarkConfig
from asset_engine.engine import AssetEngine
from asset_engine.providers.base import AssetSpec, LocalAssetProvider
from asset_engine.providers.placeholder import generate_image


def _rss_mb() -> float:
    try:
        import psutil  # type: ignore[import-not-found]

        return psutil.Process().memory_info().rss / (1024 * 1024)
    except Exception:  # noqa: BLE001 - memory reporting is best-effort
        return 0.0


from reel_engine.config.settings import ReelEngineConfig, RenderConfig
from reel_engine.interfaces.types import RenderRequest
from reel_engine.render import get_renderer
from reel_engine.render.base import scene_frame_count
from reel_engine.timeline.model import storyboard


class AssetBenchmarkCase(BenchmarkCase):
    """Asset loading + timeline gen + render overhead + export timing."""

    def __init__(self, cfg: AssetBenchmarkConfig, out_dir: Path, repetition: int = 0) -> None:
        super().__init__(case_id=f"{cfg.renderer}-{cfg.layout}-r{repetition}",
                         subject_id=f"{cfg.renderer}-{cfg.layout}", scenario="asset_render")
        self.cfg = cfg
        self.out_dir = out_dir
        self.repetition = repetition

    def _timeline(self):
        cfg = self.cfg
        beats = [(("blue" if i % 2 == 0 else "green"), f"Scene {i + 1}",
                  cfg.scene_duration_s) for i in range(cfg.n_scenes)]
        return storyboard(beats, title="asset benchmark",
                          width=cfg.width, height=cfg.height, fps=cfg.fps)

    def _specs(self, img: Path, dur: float) -> list[AssetSpec]:
        cfg = self.cfg
        span = dur / (cfg.n_assets + 1)
        return [AssetSpec(str(img), start_s=round((i + 0.5) * span, 3),
                          end_s=round((i + 1.5) * span, 3), layout=cfg.layout,
                          clip_id=f"bench-{i:02d}")
                for i in range(cfg.n_assets)]

    def execute(self, result: CaseResult) -> None:
        cfg = self.cfg
        engine_cfg = ReelEngineConfig(
            render=RenderConfig(width=cfg.width, height=cfg.height, fps=cfg.fps,
                                renderer=cfg.renderer, mock_max_dim=cfg.mock_max_dim))
        base = self.out_dir / f"{self.case_id}"
        no_assets = self._timeline()
        dur = no_assets.duration_s
        img = generate_image(self.out_dir / "asset.png", width=640, height=360, label="B")
        specs = self._specs(img, dur)
        total_frames = cfg.n_scenes * scene_frame_count(cfg.scene_duration_s, cfg.fps)

        # 1) asset loading: provider resolves every spec to a file (stat + ref)
        provider = LocalAssetProvider()
        with Stopwatch() as sw_load:
            refs = [provider.resolve(s) for s in specs]
        load_s = sw_load.elapsed_s

        # 2) timeline generation: specs -> validated AssetTrack
        with Stopwatch() as sw_gen:
            track = AssetEngine(config=None).build(specs)
        gen_s = sw_gen.elapsed_s
        with_assets = dataclasses.replace(no_assets, asset_tracks=(track,))
        renderer = get_renderer(cfg.renderer, engine_cfg)

        # 3) render WITHOUT assets (baseline)
        with Stopwatch() as sw_base:
            renderer.render(RenderRequest(
                timeline=no_assets, output_path=base.with_name(base.name + "_base.avi"),
                renderer=cfg.renderer, export_profiles=()))
        render_base_s = sw_base.elapsed_s

        # 4) render WITH assets (master only) -> overhead is the delta
        with Stopwatch() as sw_assets:
            master = renderer.render(RenderRequest(
                timeline=with_assets, output_path=base.with_name(base.name + "_assets.avi"),
                renderer=cfg.renderer, export_profiles=()))
        render_assets_s = sw_assets.elapsed_s

        # 5) render + export profiles -> export time is the delta
        with Stopwatch() as sw_full:
            full = renderer.render(RenderRequest(
                timeline=with_assets, output_path=base.with_name(base.name + "_full.avi"),
                renderer=cfg.renderer, export_profiles=tuple(cfg.export_profiles)))
        export_s = max(0.0, sw_full.elapsed_s - render_assets_s)
        render_fps = total_frames / render_assets_s if render_assets_s > 0 else 0.0

        result.add(Measurement("asset_load_ms", round(load_s * 1000, 3), "ms",
                               higher_is_better=False))
        result.add(Measurement("timeline_gen_ms", round(gen_s * 1000, 3), "ms",
                               higher_is_better=False))
        result.add(Measurement("render_base_ms", round(render_base_s * 1000, 2), "ms",
                               higher_is_better=False))
        result.add(Measurement("render_assets_ms", round(render_assets_s * 1000, 2), "ms",
                               higher_is_better=False))
        result.add(Measurement("asset_render_overhead_ms",
                               round((render_assets_s - render_base_s) * 1000, 2), "ms",
                               higher_is_better=False))
        result.add(Measurement("export_ms", round(export_s * 1000, 2), "ms",
                               higher_is_better=False))
        result.add(Measurement("render_fps", round(render_fps, 1), "fps",
                               higher_is_better=True))
        result.add(Measurement("rss_mb", round(_rss_mb(), 1), "MB", higher_is_better=False))
        result.add(Measurement("n_assets", len(refs), "", source="static"))
        result.add(Measurement("output_duration_s", master.duration_s, "s", source="static"))
        result.metadata["timeline_hash"] = master.timeline_hash
        result.metadata["layout"] = cfg.layout
        result.artifacts["master"] = str(master.output_path)
        result.artifacts["n_exports"] = str(len(full.exports))
