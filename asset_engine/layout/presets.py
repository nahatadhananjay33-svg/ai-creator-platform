"""Layout authoring helpers (Phase C6).

Constructors that produce :class:`AssetLayout` values for the eight supported
layouts. These are *authoring* helpers — the geometry (layout ->
:class:`AssetPlacement` rectangle) is resolved at render time by
``reel_engine.render.assets.resolve_layout`` so the renderer stays
self-contained and this engine never has to know pixel maths.
"""
from __future__ import annotations

from reel_engine.interfaces.types import ASSET_LAYOUTS, AssetLayout

LAYOUT_NAMES = ASSET_LAYOUTS


def make_layout(kind: str, **params) -> AssetLayout:
    """Build an :class:`AssetLayout` of ``kind`` with optional parameters."""
    if kind not in ASSET_LAYOUTS:
        raise ValueError(f"Unknown layout {kind!r}; expected one of {ASSET_LAYOUTS}")
    allowed = {"corner", "side", "scale", "margin"}
    bad = set(params) - allowed
    if bad:
        raise ValueError(f"Unknown layout params {sorted(bad)}; allowed {sorted(allowed)}")
    return AssetLayout(kind=kind, **params)


def full_screen() -> AssetLayout:
    return AssetLayout(kind="full_screen")


def background_replacement() -> AssetLayout:
    return AssetLayout(kind="background_replacement")


def picture_in_picture(corner: str = "bottom_right", scale: float = 0.30,
                       margin: float = 0.05) -> AssetLayout:
    return AssetLayout(kind="picture_in_picture", corner=corner, scale=scale, margin=margin)


def floating_card(corner: str = "bottom_right", scale: float = 0.35,
                  margin: float = 0.06) -> AssetLayout:
    return AssetLayout(kind="floating_card", corner=corner, scale=scale, margin=margin)


def split_screen(side: str = "right") -> AssetLayout:
    return AssetLayout(kind="split_screen", side=side)


def side_by_side(side: str = "right", margin: float = 0.04) -> AssetLayout:
    return AssetLayout(kind="side_by_side", side=side, margin=margin)


def top_banner() -> AssetLayout:
    return AssetLayout(kind="top_banner")


def bottom_banner() -> AssetLayout:
    return AssetLayout(kind="bottom_banner")
