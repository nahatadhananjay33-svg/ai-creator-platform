"""Caption benchmark cases (Phase C4).

Subclasses :class:`foundation.benchmarking.BenchmarkCase`, inheriting the
platform's timing, resource monitoring (peak RSS), and reporting — the same
mechanism the Reels Engine benchmark uses.

One case measures the full deterministic caption path over a fixed script:

    caption generation → render overhead (with vs without captions) → export →
    subtitle export → memory

Hermetic by default (mock renderer), so it runs anywhere with no FFmpeg/GPU.
"""
from __future__ import annotations

import dataclasses
from pathlib import Path

from foundation.benchmarking import BenchmarkCase, CaseResult, Measurement
from foundation.shared_utils import Stopwatch

from caption_engine.benchmark.config import CaptionBenchmarkConfig
from caption_engine.engine import CaptionEngine
from caption_engine.export.subtitles import write_subtitles


def _rss_mb() -> float:
    """Current process RSS in MB (0.0 if psutil is unavailable)."""
    try:
        import psutil  # type: ignore[import-not-found]

        return psutil.Process().memory_info().rss / (1024 * 1024)
    except Exception:  # noqa: BLE001 - memory reporting is best-effort
        return 0.0


from reel_engine.config.settings import ReelEngineConfig, RenderConfig
from reel_engine.interfaces.types import RenderRequest
from reel_engine.render import get_renderer
from reel_engine.timeline.model import storyboard


class CaptionBenchmarkCase(BenchmarkCase):
    """Caption generation + render overhead + export + subtitle-export timing."""

    def __init__(self, cfg: CaptionBenchmarkConfig, out_dir: Path, repetition: int = 0) -> None:
        super().__init__(case_id=f"{cfg.renderer}-{cfg.kind}-r{repetition}",
                         subject_id=f"{cfg.renderer}-{cfg.kind}", scenario="caption_render")
        self.cfg = cfg
        self.out_dir = out_dir
        self.repetition = repetition

    def _timeline(self):
        cfg = self.cfg
        beats = [(("blue" if i % 2 == 0 else "green"), f"Scene {i + 1}",
                  cfg.scene_duration_s) for i in range(cfg.n_scenes)]
        return storyboard(beats, title="caption benchmark",
                          width=cfg.width, height=cfg.height, fps=cfg.fps)

    def execute(self, result: CaseResult) -> None:
        cfg = self.cfg
        engine_cfg = ReelEngineConfig(
            render=RenderConfig(width=cfg.width, height=cfg.height, fps=cfg.fps,
                                renderer=cfg.renderer, mock_max_dim=cfg.mock_max_dim))
        base = self.out_dir / f"{self.case_id}"

        # 1) caption generation (script -> validated CaptionTrack)
        with Stopwatch() as sw_gen:
            track = CaptionEngine().generate(
                text=cfg.text, duration_s=cfg.duration_s, kind=cfg.kind, preset=cfg.preset)
        gen_s = sw_gen.elapsed_s

        no_caps = self._timeline()
        with_caps = dataclasses.replace(no_caps, caption_tracks=(track,))
        renderer = get_renderer(cfg.renderer, engine_cfg)

        # 2) render WITHOUT captions (baseline)
        with Stopwatch() as sw_base:
            renderer.render(RenderRequest(
                timeline=no_caps, output_path=base.with_name(base.name + "_base.avi"),
                renderer=cfg.renderer, export_profiles=()))
        render_base_s = sw_base.elapsed_s

        # 3) render WITH captions (master only) -> overhead is the delta
        with Stopwatch() as sw_caps:
            master = renderer.render(RenderRequest(
                timeline=with_caps, output_path=base.with_name(base.name + "_caps.avi"),
                renderer=cfg.renderer, export_profiles=()))
        render_caps_s = sw_caps.elapsed_s

        # 4) render + export profiles -> export time is the delta over master
        with Stopwatch() as sw_full:
            full = renderer.render(RenderRequest(
                timeline=with_caps, output_path=base.with_name(base.name + "_full.avi"),
                renderer=cfg.renderer, export_profiles=tuple(cfg.export_profiles)))
        export_s = max(0.0, sw_full.elapsed_s - render_caps_s)

        # 5) subtitle export (SRT + WebVTT + JSON + timeline captions)
        with Stopwatch() as sw_sub:
            paths = write_subtitles(track, base.with_name(base.name + "_subs"), stem="captions")
        subtitle_s = sw_sub.elapsed_s

        result.add(Measurement("caption_gen_ms", round(gen_s * 1000, 3), "ms",
                               higher_is_better=False))
        result.add(Measurement("render_base_ms", round(render_base_s * 1000, 2), "ms",
                               higher_is_better=False))
        result.add(Measurement("render_caps_ms", round(render_caps_s * 1000, 2), "ms",
                               higher_is_better=False))
        result.add(Measurement("caption_render_overhead_ms",
                               round((render_caps_s - render_base_s) * 1000, 2), "ms",
                               higher_is_better=False))
        result.add(Measurement("export_ms", round(export_s * 1000, 2), "ms",
                               higher_is_better=False))
        result.add(Measurement("subtitle_export_ms", round(subtitle_s * 1000, 3), "ms",
                               higher_is_better=False))
        result.add(Measurement("rss_mb", round(_rss_mb(), 1), "MB", higher_is_better=False))
        result.add(Measurement("n_segments", track.n_segments, "", source="static"))
        result.add(Measurement("n_words", len(track.words()), "", source="static"))
        result.add(Measurement("output_duration_s", master.duration_s, "s", source="static"))
        result.metadata["timeline_hash"] = master.timeline_hash
        result.metadata["caption_kind"] = cfg.kind
        result.artifacts["master"] = str(master.output_path)
        result.artifacts["srt"] = str(paths["srt"])
        result.artifacts["n_exports"] = str(len(full.exports))
