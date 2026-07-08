"""Visual Asset Engine facade / providers / layout / builder / config tests (C6).

Fully hermetic and deterministic: no renderer, no ffmpeg, no models, no
downloads. Every built track is checked against the Timeline validator so the
engine can never emit an unrenderable asset track.
"""
from __future__ import annotations

import pytest

from reel_engine.interfaces.types import Scene, Timeline
from reel_engine.timeline.validate import validate_timeline

from asset_engine import AssetEngine, AssetSpec, load_asset_engine_config
from asset_engine.layout import LAYOUT_NAMES, make_layout, picture_in_picture
from asset_engine.providers.base import LocalAssetProvider, infer_kind
from asset_engine.providers.placeholder import generate_image

DUR = 12.0


@pytest.fixture
def img(tmp_path):
    return generate_image(tmp_path / "chart.png", label="x")


def _valid(track, duration_s=DUR):
    tl = Timeline(scenes=(Scene.simple(0, (0, 0, 255), "x", duration_s=duration_s),),
                  asset_tracks=(track,))
    return validate_timeline(tl)


# ------------------------------------------------------------------- providers
def test_infer_kind():
    assert infer_kind("a.mp4") == "video" and infer_kind("a.MOV") == "video"
    assert infer_kind("a.png") == "image" and infer_kind("a.jpg") == "image"


def test_local_provider_resolves_and_flags_missing(img):
    ref = LocalAssetProvider().resolve(AssetSpec(str(img), 0.0, 2.0))
    assert ref.kind == "file" and ref.meta["asset_kind"] == "image"
    with pytest.raises(FileNotFoundError):
        LocalAssetProvider().resolve(AssetSpec("/nope/missing.png", 0.0, 2.0))


def test_explicit_kind_overrides_inference(img):
    ref = LocalAssetProvider().resolve(AssetSpec(str(img), 0.0, 2.0, kind="chart"))
    assert ref.meta["asset_kind"] == "chart"


# --------------------------------------------------------------------- layouts
def test_eight_layouts_and_helpers():
    assert len(LAYOUT_NAMES) == 8
    assert picture_in_picture(scale=0.25).kind == "picture_in_picture"
    with pytest.raises(ValueError):
        make_layout("orbit")
    with pytest.raises(ValueError):
        make_layout("full_screen", bogus=1)


# -------------------------------------------------------------------- builder
def test_build_applies_config_defaults(img):
    track = AssetEngine().build([AssetSpec(str(img), start_s=1.0, end_s=0.0)])  # no end
    c = track.clips[0]
    assert c.layout.kind == "full_screen"          # config default_layout
    assert c.animation_in.kind == "fade_in" and c.animation_out.kind == "fade_out"
    assert c.end_s == pytest.approx(1.0 + 3.0)      # default_duration_s
    assert _valid(track) == []


def test_build_pip_defaults_and_layout_params(img):
    track = AssetEngine().build([
        AssetSpec(str(img), 1.0, 4.0, layout="picture_in_picture"),
        AssetSpec(str(img), 4.0, 7.0, layout="split_screen", layout_params={"side": "left"}),
    ])
    pip, split = track.clips
    assert pip.layout.kind == "picture_in_picture" and pip.layout.scale == 0.30
    assert pip.layout.corner == "bottom_right"     # PIP defaults from config
    assert split.layout.side == "left"
    assert _valid(track) == []


def test_kind_inferred_and_clip_ids_unique(img):
    track = AssetEngine().build([AssetSpec(str(img), 0.0, 2.0),
                                 AssetSpec(str(img), 2.0, 4.0)])
    assert [c.kind for c in track.clips] == ["image", "image"]
    assert len({c.clip_id for c in track.clips}) == 2


# --------------------------------------------------------------------- config
def test_config_defaults():
    cfg = load_asset_engine_config()
    assert cfg.default_layout == "full_screen" and cfg.pip_scale == 0.30
    assert cfg.animation_in == "fade_in" and cfg.default_duration_s == 3.0


def test_config_overrides_and_env(img, monkeypatch):
    cfg = load_asset_engine_config(overrides={"assets": {
        "default_layout": "top_banner", "overlay_opacity": 0.7,
        "animation": {"kind_in": "slide_left"}}})
    c = AssetEngine(cfg).build([AssetSpec(str(img), 0.0, 3.0)]).clips[0]
    assert c.layout.kind == "top_banner" and c.opacity == 0.7
    assert c.animation_in.kind == "slide_left"
    monkeypatch.setenv("AICP__assets__default_layout", "bottom_banner")
    assert load_asset_engine_config().default_layout == "bottom_banner"
