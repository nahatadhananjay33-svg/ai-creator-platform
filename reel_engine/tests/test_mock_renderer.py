"""Mock renderer tests (Phase C2). Fully hermetic — no FFmpeg, no AI, no GPU.

Verifies the mock produces a real, readable reel with correct timing, colours,
aspect, sidecars, exports, and byte-for-byte determinism.
"""
from __future__ import annotations

import pytest

from foundation.shared_utils import read_wav
from foundation.shared_utils.video_io import read_raw_avi
from reel_engine.config import ReelEngineConfig, RenderConfig
from reel_engine.interfaces import RenderRequest, Timeline, TimelineMeta
from reel_engine.render import MockRenderer
from reel_engine.timeline import build_demo_timeline

FPS = 25
DUR = 1.0


@pytest.fixture
def cfg():
    return ReelEngineConfig(render=RenderConfig(mock_max_dim=64, audio_sample_rate=8000))


@pytest.fixture
def demo():
    return build_demo_timeline(width=1080, height=1920, fps=FPS, duration_s=DUR)


def _render(cfg, demo, tmp_path, profiles=()):
    req = RenderRequest(timeline=demo, output_path=tmp_path / "reel.avi",
                        renderer="mock", export_profiles=tuple(profiles))
    return MockRenderer(cfg).render(req)


def test_master_dimensions_preserve_aspect(cfg, demo, tmp_path):
    res = _render(cfg, demo, tmp_path)
    assert (res.width, res.height) == (36, 64)   # 9:16 within max_dim=64
    assert res.aspect == "9:16"
    assert res.renderer == "mock" and res.metadata["proxy"] is True


def test_frame_count_matches_duration_times_fps(cfg, demo, tmp_path):
    res = _render(cfg, demo, tmp_path)
    vf = read_raw_avi(res.output_path)
    assert vf.n_frames == 3 * round(DUR * FPS)     # 75
    assert res.duration_s == 3 * DUR
    assert vf.width == 36 and vf.height == 64


def test_scene_background_colors_are_bgr_correct(cfg, demo, tmp_path):
    res = _render(cfg, demo, tmp_path)
    vf = read_raw_avi(res.output_path)
    n = round(DUR * FPS)
    corner = lambda i: bytes(vf.frames[i][0:3])    # top-left pixel (outside text band)
    assert corner(0) == bytes((255, 0, 0))         # blue  RGB(0,0,255) -> BGR
    assert corner(n) == bytes((0, 128, 0))         # green RGB(0,128,0) -> BGR
    assert corner(3 * n - 1) == bytes((0, 0, 255)) # red   RGB(255,0,0) -> BGR


def test_title_band_drawn_in_center(cfg, demo, tmp_path):
    res = _render(cfg, demo, tmp_path)
    vf = read_raw_avi(res.output_path)
    # center pixel of frame 0 sits inside the white title band
    center = (vf.height // 2) * vf.width + (vf.width // 2)
    assert bytes(vf.frames[0][center * 3:center * 3 + 3]) == bytes((255, 255, 255))


def test_silent_audio_and_captions_sidecars(cfg, demo, tmp_path):
    res = _render(cfg, demo, tmp_path)
    wav = read_wav(res.audio_path)
    assert abs(wav.duration_s - 3 * DUR) < 0.05
    assert max(abs(s) for s in wav.samples) == 0   # silent
    srt = res.captions_path.read_text(encoding="utf-8")
    assert "Title" in srt and "Subtitle" in srt and "Call To Action" in srt
    assert "00:00:00,000 --> 00:00:01,000" in srt


def test_exports_have_correct_profile_dimensions(cfg, demo, tmp_path):
    res = _render(cfg, demo, tmp_path, profiles=("reel_9x16", "square_1x1", "landscape_16x9"))
    by = {e.profile: e for e in res.exports}
    assert by["reel_9x16"].aspect == "9:16"
    assert by["square_1x1"].aspect == "1:1" and by["square_1x1"].width == by["square_1x1"].height
    assert by["landscape_16x9"].aspect == "16:9"
    for e in res.exports:                          # every export is a readable AVI
        vf = read_raw_avi(e.path)
        assert vf.n_frames == 3 * round(DUR * FPS)
        assert (vf.width, vf.height) == (e.width, e.height)


def test_render_is_deterministic(cfg, demo, tmp_path):
    a = _render(cfg, demo, tmp_path / "a", profiles=("square_1x1",))
    b = _render(cfg, demo, tmp_path / "b", profiles=("square_1x1",))
    assert a.output_path.read_bytes() == b.output_path.read_bytes()
    assert a.timeline_hash == b.timeline_hash
    assert a.exports[0].path.read_bytes() == b.exports[0].path.read_bytes()


def test_invalid_timeline_is_rejected(cfg, tmp_path):
    from reel_engine.timeline import TimelineError
    bad = Timeline(meta=TimelineMeta(width=1081, height=1920),
                   scenes=build_demo_timeline().scenes)
    with pytest.raises(TimelineError):
        MockRenderer(cfg).render(
            RenderRequest(timeline=bad, output_path=tmp_path / "x.avi", renderer="mock")
        )
