"""Music benchmark cases (Phase C8).

Subclasses :class:`foundation.benchmarking.BenchmarkCase`, inheriting timing,
resource monitoring (peak RSS), and reporting. One case measures the full
deterministic music path over a fixed reel:

    music loading (generate/resolve the bed) → mixing (voice+music DSP)
    → render overhead (with vs without music) → export → memory → render time

Hermetic by default (mock renderer): the procedural soundtrack is generated
locally and the mock writes the mixed WAV sidecar. No AI, no GPU, no downloads.
"""
from __future__ import annotations

import dataclasses
from pathlib import Path

from foundation.benchmarking import BenchmarkCase, CaseResult, Measurement
from foundation.shared_utils import Stopwatch
from reel_engine.config.settings import ReelEngineConfig, RenderConfig
from reel_engine.interfaces.types import CaptionSegment, CaptionTrack, RenderRequest
from reel_engine.render import get_renderer
from reel_engine.render.base import scene_frame_count
from reel_engine.render.music import mix_timeline_audio
from reel_engine.timeline.model import storyboard

from music_engine.benchmark.config import MusicBenchmarkConfig
from music_engine.engine import MusicEngine


def _rss_mb() -> float:
    try:
        import psutil  # type: ignore[import-not-found]

        return psutil.Process().memory_info().rss / (1024 * 1024)
    except Exception:  # noqa: BLE001 - memory reporting is best-effort
        return 0.0


class MusicBenchmarkCase(BenchmarkCase):
    """Music loading + mixing + render overhead + export timing."""

    def __init__(self, cfg: MusicBenchmarkConfig, out_dir: Path, repetition: int = 0) -> None:
        super().__init__(case_id=f"{cfg.renderer}-{cfg.soundtrack}-r{repetition}",
                         subject_id=f"{cfg.renderer}-{cfg.soundtrack}",
                         scenario="music_render")
        self.cfg = cfg
        self.out_dir = out_dir
        self.repetition = repetition

    def _timeline(self):
        cfg = self.cfg
        scene_dur = cfg.reel_duration_s / cfg.n_scenes
        beats = [(("blue" if i % 2 == 0 else "green"), f"Scene {i + 1}", scene_dur)
                 for i in range(cfg.n_scenes)]
        tl = storyboard(beats, title="music benchmark",
                        width=cfg.width, height=cfg.height, fps=cfg.fps)
        # a caption track gives ducking real speech windows (every other scene)
        segs = tuple(
            CaptionSegment(segment_id=f"seg-{i:03d}", index=i, text=f"line {i}",
                           start_s=round(i * scene_dur, 3),
                           end_s=round(i * scene_dur + scene_dur * 0.7, 3))
            for i in range(cfg.n_scenes) if i % 2 == 0)
        return dataclasses.replace(tl, caption_tracks=(CaptionTrack(
            track_id="captions", kind="sentence", segments=segs),))

    def execute(self, result: CaseResult) -> None:
        cfg = self.cfg
        engine_cfg = ReelEngineConfig(
            render=RenderConfig(width=cfg.width, height=cfg.height, fps=cfg.fps,
                                renderer=cfg.renderer, mock_max_dim=cfg.mock_max_dim,
                                audio_sample_rate=cfg.sample_rate))
        base = self.out_dir / self.case_id
        no_music = self._timeline()
        dur = no_music.duration_s
        total_frames = cfg.n_scenes * scene_frame_count(dur / cfg.n_scenes, cfg.fps)

        # 1) music loading: generate/resolve the bed into a validated MusicTrack.
        with Stopwatch() as sw_load:
            track = MusicEngine().generate(
                dur, soundtrack=cfg.soundtrack, sample_rate=cfg.sample_rate,
                asset_dir=self.out_dir)
        load_s = sw_load.elapsed_s
        with_music = dataclasses.replace(no_music, music_tracks=(track,))

        # 2) mixing: voice+music DSP over the whole reel (the core cost).
        with Stopwatch() as sw_mix:
            mixed = mix_timeline_audio(with_music, cfg.sample_rate)
        mix_s = sw_mix.elapsed_s

        renderer = get_renderer(cfg.renderer, engine_cfg)

        # 3) render WITHOUT music (baseline).
        with Stopwatch() as sw_base:
            renderer.render(RenderRequest(
                timeline=no_music, output_path=base.with_name(base.name + "_base.avi"),
                renderer=cfg.renderer, export_profiles=()))
        render_base_s = sw_base.elapsed_s

        # 4) render WITH music (master only) -> mixing overhead is the delta.
        with Stopwatch() as sw_music:
            master = renderer.render(RenderRequest(
                timeline=with_music, output_path=base.with_name(base.name + "_music.avi"),
                renderer=cfg.renderer, export_profiles=()))
        render_music_s = sw_music.elapsed_s

        # 5) render + export profiles -> export time is the delta.
        with Stopwatch() as sw_full:
            full = renderer.render(RenderRequest(
                timeline=with_music, output_path=base.with_name(base.name + "_full.avi"),
                renderer=cfg.renderer, export_profiles=tuple(cfg.export_profiles)))
        export_s = max(0.0, sw_full.elapsed_s - render_music_s)
        render_fps = total_frames / render_music_s if render_music_s > 0 else 0.0

        result.add(Measurement("music_load_ms", round(load_s * 1000, 3), "ms",
                               higher_is_better=False))
        result.add(Measurement("mix_ms", round(mix_s * 1000, 2), "ms",
                               higher_is_better=False))
        result.add(Measurement("render_base_ms", round(render_base_s * 1000, 2), "ms",
                               higher_is_better=False))
        result.add(Measurement("render_music_ms", round(render_music_s * 1000, 2), "ms",
                               higher_is_better=False))
        result.add(Measurement("music_render_overhead_ms",
                               round((render_music_s - render_base_s) * 1000, 2), "ms",
                               higher_is_better=False))
        result.add(Measurement("export_ms", round(export_s * 1000, 2), "ms",
                               higher_is_better=False))
        result.add(Measurement("render_fps", round(render_fps, 1), "fps",
                               higher_is_better=True))
        result.add(Measurement("rss_mb", round(_rss_mb(), 1), "MB", higher_is_better=False))
        result.add(Measurement("mixed_samples", mixed.n_frames, "", source="static"))
        result.add(Measurement("output_duration_s", master.duration_s, "s", source="static"))
        result.metadata["timeline_hash"] = master.timeline_hash
        result.metadata["soundtrack"] = cfg.soundtrack
        result.artifacts["master"] = str(master.output_path)
        result.artifacts["n_exports"] = str(len(full.exports))
