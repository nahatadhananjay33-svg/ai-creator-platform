"""Renderer caption tests (Phase C4). Fully hermetic — mock renderer, no ffmpeg.

Proves the renderer *consumes* a native ``CaptionTrack``: captions appear only
in their absolute time window, honour the style's vertical position, light up
the active karaoke word, are byte-for-byte deterministic, propagate to exports,
and drive the SRT sidecar. Uses distinctive caption colours so a caption pixel
is unambiguous against the solid background.
"""
from __future__ import annotations

import dataclasses

import pytest

from foundation.shared_utils.video_io import read_raw_avi
from reel_engine.config import ReelEngineConfig, RenderConfig
from reel_engine.interfaces.types import (
    CaptionAnimation,
    CaptionSegment,
    CaptionStyle,
    CaptionTrack,
    RenderRequest,
    Scene,
    WordTiming,
)
from reel_engine.render import MockRenderer
from reel_engine.timeline.model import new_timeline

W, H, FPS, DUR = 180, 320, 20, 2.0
_MAGENTA = (255, 0, 255)      # caption colour, distinct from the blue background
_BLUE_BG = (0, 0, 255)


@pytest.fixture
def cfg():
    return ReelEngineConfig(render=RenderConfig(mock_max_dim=160, audio_sample_rate=8000))


def _timeline(track, dur=DUR):
    scene = Scene.simple(0, _BLUE_BG, None, duration_s=dur)   # no text band
    tl = new_timeline([scene], width=W, height=H, fps=FPS)
    return dataclasses.replace(tl, caption_tracks=(track,))


def _render(cfg, track, tmp_path, profiles=()):
    tl = _timeline(track)
    req = RenderRequest(timeline=tl, output_path=tmp_path / "reel.avi",
                        renderer="mock", export_profiles=tuple(profiles))
    return MockRenderer(cfg).render(req)


def _count_color(frame: bytes, w: int, h: int, rgb: tuple) -> int:
    bgr = bytes((rgb[2], rgb[1], rgb[0]))
    return sum(1 for i in range(w * h) if frame[i * 3:i * 3 + 3] == bgr)


def _rows_with_color(vf, frame_idx: int, rgb: tuple) -> list[int]:
    bgr = bytes((rgb[2], rgb[1], rgb[0]))
    frame = vf.frames[frame_idx]
    return [y for y in range(vf.height)
            if any(frame[(y * vf.width + x) * 3:(y * vf.width + x) * 3 + 3] == bgr
                   for x in range(vf.width))]


def _sentence_track(start=0.0, end=1.0, color=_MAGENTA):
    return CaptionTrack("c", kind="sentence", style=CaptionStyle(primary_color=color),
                        segments=(CaptionSegment("s0", 0, "hello", start, end),))


# -------------------------------------------------------- timing (in/out window)
def test_caption_present_in_window_absent_outside(cfg, tmp_path):
    res = _render(cfg, _sentence_track(0.0, 1.0), tmp_path)
    vf = read_raw_avi(res.output_path)
    in_frame = int(0.5 * FPS)          # inside [0, 1]
    out_frame = int(1.5 * FPS)         # after the caption ends
    assert _count_color(vf.frames[in_frame], vf.width, vf.height, _MAGENTA) > 0
    assert _count_color(vf.frames[out_frame], vf.width, vf.height, _MAGENTA) == 0


def test_no_caption_track_leaves_frames_clean(cfg, tmp_path):
    # A caption whose colour never appears means a plain background everywhere.
    tl = new_timeline([Scene.simple(0, _BLUE_BG, None, duration_s=DUR)],
                      width=W, height=H, fps=FPS)
    req = RenderRequest(timeline=tl, output_path=tmp_path / "r.avi", renderer="mock")
    vf = read_raw_avi(MockRenderer(cfg).render(req).output_path)
    assert _count_color(vf.frames[0], vf.width, vf.height, _MAGENTA) == 0


# ------------------------------------------------------------------- position
@pytest.mark.parametrize("position,expect_bottom_half", [("bottom", True), ("top", False)])
def test_vertical_position_respected(cfg, tmp_path, position, expect_bottom_half):
    track = CaptionTrack("c", kind="sentence",
                         style=CaptionStyle(primary_color=_MAGENTA, position=position),
                         segments=(CaptionSegment("s", 0, "hi", 0.0, 1.0),))
    vf = read_raw_avi(_render(cfg, track, tmp_path).output_path)
    rows = _rows_with_color(vf, int(0.5 * FPS), _MAGENTA)
    assert rows, "caption not drawn"
    assert (min(rows) > vf.height / 2) == expect_bottom_half


# ------------------------------------------------------------------- karaoke
def test_karaoke_active_word_highlights(cfg, tmp_path):
    seg = CaptionSegment("s0", 0, "hello world", 0.0, 2.0,
                         words=(WordTiming("hello", 0.0, 1.0), WordTiming("world", 1.0, 2.0)))
    track = CaptionTrack("c", kind="karaoke", segments=(seg,),
                         style=CaptionStyle(primary_color=(255, 255, 255),
                                            highlight_color=_MAGENTA, position="center"))
    vf = read_raw_avi(_render(cfg, track, tmp_path).output_path)
    # base phrase (white) is visible throughout the segment...
    assert _count_color(vf.frames[int(0.5 * FPS)], vf.width, vf.height, (255, 255, 255)) > 0
    # ...and the highlight colour appears while a word is spoken.
    assert _count_color(vf.frames[int(0.5 * FPS)], vf.width, vf.height, _MAGENTA) > 0


# ------------------------------------------------------------------- animation
def test_fade_animation_is_partially_transparent_at_edges(cfg, tmp_path):
    track = CaptionTrack("c", kind="sentence",
                         style=CaptionStyle(primary_color=_MAGENTA),
                         animation=CaptionAnimation("fade", 0.4),
                         segments=(CaptionSegment("s", 0, "hi", 0.0, 2.0),))
    vf = read_raw_avi(_render(cfg, track, tmp_path).output_path)
    # Fully-opaque mid-caption yields pure magenta; the fade-in edge blends, so
    # pure-magenta pixels are strictly more numerous mid-window than at the edge.
    edge = _count_color(vf.frames[1], vf.width, vf.height, _MAGENTA)     # ~0.05s in
    mid = _count_color(vf.frames[int(1.0 * FPS)], vf.width, vf.height, _MAGENTA)
    assert mid > 0 and edge < mid


# ------------------------------------------------------------- determinism/export
def test_caption_render_is_deterministic(cfg, tmp_path):
    a = _render(cfg, _sentence_track(), tmp_path / "a", profiles=("square_1x1",))
    b = _render(cfg, _sentence_track(), tmp_path / "b", profiles=("square_1x1",))
    assert a.output_path.read_bytes() == b.output_path.read_bytes()
    assert a.exports[0].path.read_bytes() == b.exports[0].path.read_bytes()


def test_exports_inherit_captions(cfg, tmp_path):
    res = _render(cfg, _sentence_track(0.0, 1.0), tmp_path, profiles=("square_1x1",))
    vf = read_raw_avi(res.exports[0].path)
    assert _count_color(vf.frames[int(0.5 * FPS)], vf.width, vf.height, _MAGENTA) > 0


def test_srt_sidecar_comes_from_caption_track(cfg, tmp_path):
    seg = CaptionSegment("s0", 0, "native captions", 0.0, 1.0)
    res = _render(cfg, CaptionTrack("c", kind="sentence", segments=(seg,)), tmp_path)
    srt = res.captions_path.read_text(encoding="utf-8")
    assert "native captions" in srt
    assert "00:00:00,000 --> 00:00:01,000" in srt
