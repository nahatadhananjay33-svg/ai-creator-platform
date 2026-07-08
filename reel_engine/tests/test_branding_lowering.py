"""Branding lowering + layout tests (Phase C5). Pure, hermetic — no renderer.

Pins how a native ``BrandingTrack`` resolves to absolutely-timed elements
(order, timing, full-frame cards, theme colours) and the safe-area-aware anchor
math both renderer backends share.
"""
from __future__ import annotations

import pytest

from reel_engine.interfaces.types import (
    BrandingTrack,
    Intro,
    Logo,
    LowerThird,
    Outro,
    Scene,
    Theme,
    Timeline,
    TimelineMeta,
    Watermark,
)
from reel_engine.render.branding import anchor_frac, resolve_branding

DUR = 10.0


def _timeline(branding):
    return Timeline(meta=TimelineMeta(width=1080, height=1920, fps=30),
                    scenes=(Scene.simple(0, (0, 0, 255), None, duration_s=DUR),),
                    branding=branding)


def _full_branding():
    th = Theme(name="corporate", primary_color=(1, 2, 3), background_color=(4, 5, 6))
    return BrandingTrack(
        theme=th,
        logo=Logo(text="AB", position="top_right"),
        watermark=Watermark(text="@x", position="bottom_right", opacity=0.4),
        intro=Intro("Hello", "sub", duration_s=2.0),
        outro=Outro("Bye", "sub", duration_s=2.5, handles=("@a", "b.com")),
        lower_thirds=(LowerThird("Name", "Role", 1.0, 4.0),))


# ------------------------------------------------------------------- resolve
def test_resolve_order_and_timing():
    els = resolve_branding(_timeline(_full_branding()))
    assert [e.kind for e in els] == ["logo", "watermark", "lower_third", "intro", "outro"]
    kinds = {e.kind: e for e in els}
    assert (kinds["logo"].start_s, kinds["logo"].end_s) == (0.0, DUR)        # spans reel
    assert (kinds["intro"].start_s, kinds["intro"].end_s) == (0.0, 2.0)      # from start
    assert (kinds["outro"].start_s, kinds["outro"].end_s) == (DUR - 2.5, DUR)  # to end
    assert (kinds["lower_third"].start_s, kinds["lower_third"].end_s) == (1.0, 4.0)


def test_cards_are_full_frame_others_are_not():
    kinds = {e.kind: e for e in resolve_branding(_timeline(_full_branding()))}
    assert kinds["intro"].full_frame and kinds["outro"].full_frame
    assert not kinds["logo"].full_frame and not kinds["lower_third"].full_frame


def test_element_colours_come_from_theme():
    kinds = {e.kind: e for e in resolve_branding(_timeline(_full_branding()))}
    assert kinds["logo"].fill_color == (1, 2, 3)          # primary
    assert kinds["intro"].fill_color == (4, 5, 6)         # background
    assert kinds["outro"].lines == ("@a", "b.com")


def test_no_branding_resolves_empty():
    assert resolve_branding(_timeline(BrandingTrack())) == []
    assert resolve_branding(Timeline(scenes=(Scene.simple(0, (0, 0, 0), None, 3.0),))) == []


def test_bounded_logo_window_is_respected():
    b = BrandingTrack(logo=Logo(text="X", start_s=2.0, end_s=5.0))
    logo = resolve_branding(_timeline(b))[0]
    assert (logo.start_s, logo.end_s) == (2.0, 5.0)


# -------------------------------------------------------------------- anchors
@pytest.mark.parametrize("position,expect", [
    ("top_left", (0.05, 0.06)),
    ("top_right", (1 - 0.05 - 0.1, 0.06)),
    ("bottom_center", ((1 - 0.1) / 2, 1 - 0.06 - 0.2)),
    ("center", ((1 - 0.1) / 2, (1 - 0.2) / 2)),
])
def test_anchor_frac_positions(position, expect):
    x, y = anchor_frac(position, 0.1, 0.2, safe_h=0.05, safe_v=0.06)
    assert x == pytest.approx(expect[0]) and y == pytest.approx(expect[1])


def test_anchor_respects_safe_margins():
    # A right/bottom box never crosses into the safe margin.
    x, y = anchor_frac("bottom_right", 0.12, 0.12, safe_h=0.08, safe_v=0.07)
    assert x + 0.12 <= 1 - 0.08 + 1e-9
    assert y + 0.12 <= 1 - 0.07 + 1e-9
    assert x >= 0 and y >= 0
