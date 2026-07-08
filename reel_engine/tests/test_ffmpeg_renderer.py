"""FFmpeg renderer tests (Phase C2).

Gated on ffmpeg/ffprobe being present (the platform's pattern for
hardware/binary-bound checks): the full hermetic suite runs without them via the
MockRenderer; when FFmpeg IS available these validate a real, playable MP4.
"""
from __future__ import annotations

import pytest

from reel_engine.config import ReelEngineConfig, RenderConfig
from reel_engine.render import ffprobe_available, probe_media, render_timeline
from reel_engine.timeline import build_demo_timeline

pytestmark = pytest.mark.skipif(not ffprobe_available(),
                                reason="ffmpeg/ffprobe not installed")


@pytest.fixture
def cfg():
    # tiny resolution keeps the real encode fast
    return ReelEngineConfig(render=RenderConfig(width=180, height=320, fps=24,
                                                font_size=28, bitrate="800k"))


def test_ffmpeg_master_is_playable_with_correct_shape(cfg, tmp_path):
    tl = build_demo_timeline(width=180, height=320, fps=24, duration_s=0.5)
    res = render_timeline(tl, tmp_path / "reel.mp4", config=cfg, renderer="ffmpeg",
                          export_profiles=())
    assert res.output_path.exists() and res.output_path.stat().st_size > 0
    p = probe_media(res.output_path)
    assert (p.width, p.height) == (180, 320)
    assert p.readable and p.has_audio
    assert abs(p.duration_s - 1.5) < 0.3          # 3 x 0.5s (+ small container overhead)
    assert res.aspect == "9:16"


def test_ffmpeg_exports_each_profile(cfg, tmp_path):
    tl = build_demo_timeline(width=180, height=320, fps=24, duration_s=0.5)
    res = render_timeline(tl, tmp_path / "reel.mp4", config=cfg, renderer="ffmpeg",
                          export_profiles=("reel_9x16", "square_1x1", "landscape_16x9"))
    shapes = {e.profile: (probe_media(e.path).width, probe_media(e.path).height)
              for e in res.exports}
    assert shapes["reel_9x16"] == (1080, 1920)
    assert shapes["square_1x1"] == (1080, 1080)
    assert shapes["landscape_16x9"] == (1920, 1080)
