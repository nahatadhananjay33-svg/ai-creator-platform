"""FFmpeg visual-asset tests (Phase C6). Gated on ffmpeg being present.

The hermetic suite covers assets via the MockRenderer; these validate the real
FFmpeg filter_complex the asset compositor builds — cropping, fit modes, and
slide — and that a cropped image asset renders to a playable MP4.
"""
from __future__ import annotations

import dataclasses

import pytest

from reel_engine.config import ReelEngineConfig, RenderConfig
from reel_engine.interfaces.types import (
    AssetAnimation,
    AssetClip,
    AssetCrop,
    AssetLayout,
    AssetRef,
    AssetTrack,
    RenderRequest,
    Scene,
    TimelineMeta,
)
from reel_engine.render import ffprobe_available, probe_media
from reel_engine.timeline.model import new_timeline

pytestmark = pytest.mark.skipif(not ffprobe_available(),
                                reason="ffmpeg/ffprobe not installed")


def _renderer():
    from reel_engine.render.ffmpeg_renderer import FFmpegRenderer
    return FFmpegRenderer(ReelEngineConfig(render=RenderConfig(width=540, height=960, fps=24)))


def _clip(**over):
    base = dict(clip_id="a", kind="image", source=AssetRef(kind="file", uri="/x.png"),
                start_s=1.0, end_s=4.0, layout=AssetLayout(kind="full_screen"),
                animation_in=AssetAnimation("none"), animation_out=AssetAnimation("none"))
    base.update(over)
    return AssetClip(**base)


def test_crop_filter_emitted_when_crop_set():
    meta = TimelineMeta(width=540, height=960, fps=24)
    prep, _ = _renderer()._asset_clip_graph(
        _clip(crop=AssetCrop(0.1, 0.2, 0.5, 0.6)), meta, "1:v", "a1", "0:v")
    assert "crop=iw*0.5000:ih*0.6000:iw*0.1000:ih*0.2000" in prep


def test_cover_fit_scales_then_crops():
    meta = TimelineMeta(width=540, height=960, fps=24)
    clip = _clip(layout=AssetLayout(kind="split_screen", side="right"))  # cover
    prep, _ = _renderer()._asset_clip_graph(clip, meta, "1:v", "a1", "0:v")
    assert "force_original_aspect_ratio=increase" in prep and "crop=" in prep


def test_slide_left_adds_time_expression_to_overlay_x():
    meta = TimelineMeta(width=540, height=960, fps=24)
    clip = _clip(animation_in=AssetAnimation("slide_left", 0.5))
    _, step = _renderer()._asset_clip_graph(clip, meta, "1:v", "a1", "0:v")
    assert "overlay=x='" in step and "min(1,max(0," in step


def test_cropped_image_asset_renders_playable(tmp_path):
    from asset_engine.providers.placeholder import generate_image
    img = generate_image(tmp_path / "a.png", label="x")
    scene = Scene.simple(0, (20, 20, 40), "HEAD", duration_s=3.0)
    tl = new_timeline([scene], width=360, height=640, fps=24)
    clip = _clip(source=AssetRef(kind="file", uri=str(img)), end_s=3.0,
                 crop=AssetCrop(0.1, 0.1, 0.8, 0.8),
                 layout=AssetLayout(kind="picture_in_picture"))
    tl = dataclasses.replace(tl, asset_tracks=(AssetTrack("assets", clips=(clip,)),))
    cfg = ReelEngineConfig(render=RenderConfig(width=360, height=640, fps=24, bitrate="800k"))
    from reel_engine.render import get_renderer
    res = get_renderer("ffmpeg", cfg).render(RenderRequest(
        timeline=tl, output_path=tmp_path / "reel.mp4", renderer="ffmpeg"))
    p = probe_media(res.output_path)
    assert p.readable and (p.width, p.height) == (360, 640) and res.metadata["assets"]
