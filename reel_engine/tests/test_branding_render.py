"""Renderer branding tests (Phase C5). Fully hermetic — mock renderer, no ffmpeg.

Proves the renderer *consumes* a native ``BrandingTrack``: intro/outro cards
cover the frame only in their windows, the logo sits in its corner within the
safe area, the lower-third band shows in its window, exports inherit branding,
and output is byte-for-byte deterministic. Distinctive theme colours make each
element's pixels unambiguous against the solid background.
"""
from __future__ import annotations

import dataclasses

import pytest

from foundation.shared_utils.video_io import read_raw_avi
from reel_engine.config import ReelEngineConfig, RenderConfig
from reel_engine.interfaces.types import (
    BrandingTrack,
    Intro,
    Logo,
    LowerThird,
    Outro,
    RenderRequest,
    Scene,
    Theme,
    Timeline,
    TimelineMeta,
    Watermark,
)
from reel_engine.render import MockRenderer
from reel_engine.render.branding import anchor_frac

W, H, FPS, DUR = 200, 356, 20, 10.0
_BG = (0, 0, 255)                       # blue scene background
_PRIMARY = (255, 0, 255)                # magenta — logo/lower-third fill
_CARD = (0, 255, 0)                     # green — intro/outro card fill


@pytest.fixture
def cfg():
    return ReelEngineConfig(render=RenderConfig(mock_max_dim=200, audio_sample_rate=8000))


def _theme(**over):
    base = dict(name="t", primary_color=_PRIMARY, background_color=_CARD,
                safe_margin_h=0.05, safe_margin_v=0.06, watermark_opacity=1.0,
                lower_third_opacity=1.0)
    base.update(over)
    return Theme(**base)


def _timeline(branding, dur=DUR):
    scene = Scene.simple(0, _BG, None, duration_s=dur)
    tl = Timeline(meta=TimelineMeta(width=W, height=H, fps=FPS), scenes=(scene,))
    return dataclasses.replace(tl, branding=branding)


def _render(cfg, branding, tmp_path, profiles=()):
    req = RenderRequest(timeline=_timeline(branding), output_path=tmp_path / "reel.avi",
                        renderer="mock", export_profiles=tuple(profiles))
    return MockRenderer(cfg).render(req)


def _bgr(rgb):
    return bytes((rgb[2], rgb[1], rgb[0]))


def _count(frame, w, h, rgb):
    b = _bgr(rgb)
    return sum(1 for i in range(w * h) if frame[i * 3:i * 3 + 3] == b)


def _px(frame, w, x, y):
    o = (y * w + x) * 3
    return bytes(frame[o:o + 3])


# --------------------------------------------------------------- intro / outro
def test_intro_card_covers_frame_only_at_start(cfg, tmp_path):
    b = BrandingTrack(theme=_theme(), intro=Intro("Hi", duration_s=2.0))
    vf = read_raw_avi(_render(cfg, b, tmp_path).output_path)
    # during intro the whole frame is the card colour; after, it's the scene bg
    assert _px(vf.frames[int(1.0 * FPS)], vf.width, 1, 1) == _bgr(_CARD)
    assert _px(vf.frames[int(5.0 * FPS)], vf.width, 1, 1) == _bgr(_BG)


def test_outro_card_covers_frame_only_at_end(cfg, tmp_path):
    b = BrandingTrack(theme=_theme(), outro=Outro("Bye", duration_s=2.0))
    vf = read_raw_avi(_render(cfg, b, tmp_path).output_path)
    assert _px(vf.frames[int(9.0 * FPS)], vf.width, 1, 1) == _bgr(_CARD)   # last 2s
    assert _px(vf.frames[int(5.0 * FPS)], vf.width, 1, 1) == _bgr(_BG)


# ------------------------------------------------------------------- logo
def test_logo_sits_in_corner_within_safe_area(cfg, tmp_path):
    th = _theme(logo_position="top_right", logo_scale=0.15)
    b = BrandingTrack(theme=th, logo=Logo(text="AB", position="top_right", scale=0.15))
    vf = read_raw_avi(_render(cfg, b, tmp_path).output_path)
    frame = vf.frames[int(5.0 * FPS)]
    assert _count(frame, vf.width, vf.height, _PRIMARY) > 0     # logo drawn
    # the exact corner pixel stays clear (safe margin), logo is inset
    assert _px(frame, vf.width, vf.width - 1, 0) == _bgr(_BG)
    # a pixel inside the resolved logo box IS the logo colour
    bw = int(0.15 * vf.width)
    xf, yf = anchor_frac("top_right", bw / vf.width, bw / vf.height, 0.05, 0.06)
    cx = int(xf * vf.width) + bw // 2
    cy = int(yf * vf.height) + bw // 2
    assert _px(frame, vf.width, cx, cy) == _bgr(_PRIMARY)


# ------------------------------------------------------------------- lower third
def test_lower_third_band_shows_only_in_window(cfg, tmp_path):
    b = BrandingTrack(theme=_theme(),
                      lower_thirds=(LowerThird("Name", "Role", 2.0, 5.0, opacity=1.0),))
    vf = read_raw_avi(_render(cfg, b, tmp_path).output_path)
    y = int(vf.height * 0.80)
    assert _px(vf.frames[int(3.0 * FPS)], vf.width, vf.width // 2, y) == _bgr(_PRIMARY)
    assert _px(vf.frames[int(7.0 * FPS)], vf.width, vf.width // 2, y) == _bgr(_BG)


# ------------------------------------------------------------------- watermark
def test_watermark_is_drawn(cfg, tmp_path):
    th = _theme(name="w")
    # secondary_color drives the watermark fill; make it distinctive.
    th = dataclasses.replace(th, secondary_color=_PRIMARY)
    b = BrandingTrack(theme=th, watermark=Watermark(text="@x", position="bottom_right",
                                                    opacity=1.0, scale=0.12))
    vf = read_raw_avi(_render(cfg, b, tmp_path).output_path)
    assert _count(vf.frames[int(5.0 * FPS)], vf.width, vf.height, _PRIMARY) > 0


# ------------------------------------------------------------- determinism/export
def test_branding_render_is_deterministic(cfg, tmp_path):
    b = BrandingTrack(theme=_theme(), intro=Intro("Hi", duration_s=1.0),
                      logo=Logo(text="AB"))
    a = _render(cfg, b, tmp_path / "a", profiles=("square_1x1",))
    c = _render(cfg, b, tmp_path / "b", profiles=("square_1x1",))
    assert a.output_path.read_bytes() == c.output_path.read_bytes()
    assert a.exports[0].path.read_bytes() == c.exports[0].path.read_bytes()


def test_exports_inherit_branding(cfg, tmp_path):
    b = BrandingTrack(theme=_theme(), intro=Intro("Hi", duration_s=2.0))
    res = _render(cfg, b, tmp_path, profiles=("square_1x1",))
    vf = read_raw_avi(res.exports[0].path)
    # intro card colour is present in the export during the intro window
    assert _count(vf.frames[int(1.0 * FPS)], vf.width, vf.height, _CARD) > 0
