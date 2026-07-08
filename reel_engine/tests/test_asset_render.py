"""Renderer visual-asset tests (Phase C6). Fully hermetic — mock renderer, no ffmpeg.

Proves the renderer *consumes* a native ``AssetTrack``: PIP sits in its corner,
split-screen fills a half, higher ``z_index`` paints on top, clips appear only in
their window, fade animation ramps opacity, safe margins keep PIP off the edge,
exports inherit assets, and output is byte-for-byte deterministic. Mock assets
are solid per-clip colours (``asset_mock_color``) so pixels are unambiguous.
"""
from __future__ import annotations

import dataclasses

import pytest

from foundation.shared_utils.video_io import read_raw_avi
from reel_engine.config import ReelEngineConfig, RenderConfig
from reel_engine.interfaces.types import (
    AssetAnimation,
    AssetClip,
    AssetLayout,
    AssetRef,
    AssetTrack,
    RenderRequest,
    Scene,
    Timeline,
    TimelineMeta,
)
from reel_engine.render import MockRenderer
from reel_engine.render.assets import asset_mock_color

W, H, FPS, DUR = 200, 356, 20, 8.0
_BG = (0, 0, 255)          # blue scene background
_NONE = AssetAnimation("none")


@pytest.fixture
def cfg():
    return ReelEngineConfig(render=RenderConfig(mock_max_dim=200, audio_sample_rate=8000))


def _clip(cid, layout, start=1.0, end=5.0, **over):
    base = dict(clip_id=cid, kind="image", source=AssetRef(kind="file", uri="/x.png"),
                start_s=start, end_s=end, layout=layout,
                animation_in=_NONE, animation_out=_NONE)
    base.update(over)
    return AssetClip(**base)


def _render(cfg, clips, tmp_path, profiles=()):
    scene = Scene.simple(0, _BG, None, duration_s=DUR)
    tl = Timeline(meta=TimelineMeta(width=W, height=H, fps=FPS), scenes=(scene,))
    tl = dataclasses.replace(tl, asset_tracks=(AssetTrack("assets", clips=tuple(clips)),))
    req = RenderRequest(timeline=tl, output_path=tmp_path / "reel.avi",
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


# ------------------------------------------------------------------ PIP / timing
def test_pip_in_corner_and_only_in_window(cfg, tmp_path):
    clip = _clip("pip", AssetLayout(kind="picture_in_picture", corner="top_right",
                                    scale=0.3, margin=0.05), start=1.0, end=4.0)
    vf = read_raw_avi(_render(cfg, [clip], tmp_path).output_path)
    col = asset_mock_color("pip")
    inw = vf.frames[int(2.5 * FPS)]
    outw = vf.frames[int(6.0 * FPS)]
    assert _count(inw, vf.width, vf.height, col) > 0        # present in window
    assert _count(outw, vf.width, vf.height, col) == 0      # gone after
    # in the top-right region, not the top-left
    right = _px(inw, vf.width, int(vf.width * 0.80), int(vf.height * 0.12))
    assert right == _bgr(col)
    # safe margin: extreme top-right corner stays background (PIP is inset)
    assert _px(inw, vf.width, vf.width - 1, 0) == _bgr(_BG)


# ------------------------------------------------------------------- split screen
def test_split_screen_fills_one_half(cfg, tmp_path):
    clip = _clip("split", AssetLayout(kind="split_screen", side="right"))
    vf = read_raw_avi(_render(cfg, [clip], tmp_path).output_path)
    col = asset_mock_color("split")
    frame = vf.frames[int(3.0 * FPS)]
    y = vf.height // 2
    assert _px(frame, vf.width, int(vf.width * 0.75), y) == _bgr(col)   # right half
    assert _px(frame, vf.width, int(vf.width * 0.25), y) == _bgr(_BG)   # left half untouched


# ------------------------------------------------------------------- layer order
def test_higher_z_index_paints_on_top(cfg, tmp_path):
    lo = _clip("lo", AssetLayout(kind="full_screen"), z_index=0)
    hi = _clip("hi", AssetLayout(kind="full_screen"), z_index=5)
    vf = read_raw_avi(_render(cfg, [hi, lo], tmp_path).output_path)   # order irrelevant
    frame = vf.frames[int(3.0 * FPS)]
    assert _px(frame, vf.width, vf.width // 2, vf.height // 2) == _bgr(asset_mock_color("hi"))


# ------------------------------------------------------------------- animation
def test_fade_in_is_partially_transparent_at_edge(cfg, tmp_path):
    clip = _clip("fade", AssetLayout(kind="full_screen"), start=0.0, end=6.0,
                 animation_in=AssetAnimation("fade_in", 1.0))
    vf = read_raw_avi(_render(cfg, [clip], tmp_path).output_path)
    col = asset_mock_color("fade")
    edge = _count(vf.frames[2], vf.width, vf.height, col)          # ~0.1s in (faint)
    mid = _count(vf.frames[int(3.0 * FPS)], vf.width, vf.height, col)
    assert mid > 0 and edge < mid


# ------------------------------------------------------------- determinism/export
def test_asset_render_is_deterministic(cfg, tmp_path):
    clip = _clip("pip", AssetLayout(kind="picture_in_picture"))
    a = _render(cfg, [clip], tmp_path / "a", profiles=("square_1x1",))
    b = _render(cfg, [clip], tmp_path / "b", profiles=("square_1x1",))
    assert a.output_path.read_bytes() == b.output_path.read_bytes()
    assert a.exports[0].path.read_bytes() == b.exports[0].path.read_bytes()


def test_exports_inherit_assets(cfg, tmp_path):
    clip = _clip("full", AssetLayout(kind="full_screen"), start=0.0, end=6.0)
    res = _render(cfg, [clip], tmp_path, profiles=("square_1x1",))
    vf = read_raw_avi(res.exports[0].path)
    assert _count(vf.frames[int(3.0 * FPS)], vf.width, vf.height,
                  asset_mock_color("full")) > 0
