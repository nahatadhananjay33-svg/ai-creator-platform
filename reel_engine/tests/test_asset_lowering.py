"""Visual-asset lowering tests (Phase C6). Pure, hermetic — no renderer.

Pins layout -> placement geometry for all eight layouts, explicit placement
override, the deterministic animation state (fade/slide/scale/cross-dissolve,
enter + exit), z-ordered paint order, safe-margin insets, and the mock colour
map — the contract both renderer backends share.
"""
from __future__ import annotations

import pytest

from reel_engine.interfaces.types import (
    AssetAnimation,
    AssetClip,
    AssetLayout,
    AssetPlacement,
    AssetRef,
    AssetTrack,
    AssetTransition,
    Scene,
    Timeline,
    TimelineMeta,
)
from reel_engine.render.assets import (
    asset_anim_state,
    asset_mock_color,
    resolve_assets,
    resolve_layout,
    resolve_placement,
)


def _clip(cid="c", **over):
    base = dict(clip_id=cid, kind="image", source=AssetRef(kind="file", uri="/x.png"),
                start_s=0.0, end_s=4.0)
    base.update(over)
    return AssetClip(**base)


# -------------------------------------------------------------- layout geometry
def test_full_screen_and_background_fill_frame():
    for kind in ("full_screen", "background_replacement"):
        p = resolve_layout(AssetLayout(kind=kind))
        assert (p.x, p.y, p.w, p.h, p.fit) == (0.0, 0.0, 1.0, 1.0, "cover")


def test_pip_sits_in_corner_within_margin():
    p = resolve_layout(AssetLayout(kind="picture_in_picture", corner="top_right",
                                   scale=0.3, margin=0.05))
    assert p.w == 0.3 and p.h == 0.3 and p.fit == "cover"
    assert p.x == pytest.approx(1 - 0.05 - 0.3) and p.y == pytest.approx(0.05)
    # never touches the frame edge (safe): inset by the margin
    assert p.x > 0 and p.x + p.w < 1 and p.y > 0


def test_floating_card_uses_contain():
    assert resolve_layout(AssetLayout(kind="floating_card")).fit == "contain"


@pytest.mark.parametrize("side,expect_x", [("left", 0.0), ("right", 0.5)])
def test_split_screen_halves(side, expect_x):
    p = resolve_layout(AssetLayout(kind="split_screen", side=side))
    assert (p.x, p.w, p.fit) == (expect_x, 0.5, "cover")


def test_side_by_side_has_inset_margins():
    p = resolve_layout(AssetLayout(kind="side_by_side", side="left", margin=0.04))
    assert p.fit == "contain" and p.x == pytest.approx(0.04) and p.w == pytest.approx(0.5 - 1.5 * 0.04)


def test_banners():
    top = resolve_layout(AssetLayout(kind="top_banner"))
    bot = resolve_layout(AssetLayout(kind="bottom_banner"))
    assert (top.x, top.y, top.w, top.h) == (0.0, 0.0, 1.0, 0.25)
    assert (bot.y, bot.h) == (0.75, 0.25)


def test_explicit_placement_overrides_layout():
    p = resolve_placement(_clip(placement=AssetPlacement(0.1, 0.2, 0.3, 0.4, "stretch"),
                                layout=AssetLayout(kind="full_screen")))
    assert (p.x, p.y, p.w, p.h, p.fit) == (0.1, 0.2, 0.3, 0.4, "stretch")


# ------------------------------------------------------------------ animation
def test_fade_in_ramps_alpha():
    c = _clip(animation_in=AssetAnimation("fade_in", 1.0),
              animation_out=AssetAnimation("none"))
    assert asset_anim_state(c, 0.0)[0] == 0.0
    assert asset_anim_state(c, 0.5)[0] == pytest.approx(0.5)
    assert asset_anim_state(c, 2.0)[0] == 1.0


def test_fade_out_ramps_alpha_to_zero():
    c = _clip(animation_in=AssetAnimation("none"),
              animation_out=AssetAnimation("fade_out", 1.0))
    assert asset_anim_state(c, 2.0)[0] == 1.0
    assert asset_anim_state(c, 4.0)[0] == 0.0


def test_slide_left_offsets_then_settles():
    c = _clip(animation_in=AssetAnimation("slide_left", 1.0),
              animation_out=AssetAnimation("none"))
    assert asset_anim_state(c, 0.0)[1] == pytest.approx(1.0)   # off to the right
    assert asset_anim_state(c, 2.0)[1] == pytest.approx(0.0)   # settled


def test_scale_grows_from_small():
    c = _clip(animation_in=AssetAnimation("scale", 1.0),
              animation_out=AssetAnimation("none"))
    assert asset_anim_state(c, 0.0)[3] == pytest.approx(0.3)
    assert asset_anim_state(c, 2.0)[3] == pytest.approx(1.0)


def test_cross_dissolve_transition_fades_in():
    c = _clip(animation_in=AssetAnimation("none"),
              animation_out=AssetAnimation("none"),
              transition=AssetTransition("cross_dissolve", 1.0))
    assert asset_anim_state(c, 0.0)[0] == 0.0
    assert asset_anim_state(c, 1.0)[0] == pytest.approx(1.0)


# ------------------------------------------------------------- order / colour
def test_resolve_assets_sorts_by_zindex_then_start():
    tl = Timeline(meta=TimelineMeta(width=1080, height=1920),
                  scenes=(Scene.simple(0, (0, 0, 0), None, 6.0),),
                  asset_tracks=(AssetTrack("assets", clips=(
                      _clip("late-hi", z_index=5, start_s=0.0, end_s=2.0),
                      _clip("early-lo", z_index=0, start_s=3.0, end_s=5.0),
                      _clip("first-lo", z_index=0, start_s=0.0, end_s=2.0),
                  )),))
    assert [c.clip_id for c in resolve_assets(tl)] == ["first-lo", "early-lo", "late-hi"]


def test_mock_color_is_deterministic_and_distinct():
    assert asset_mock_color("a") == asset_mock_color("a")
    assert asset_mock_color("a") != asset_mock_color("b")
    assert all(0 <= ch <= 255 for ch in asset_mock_color("x"))
