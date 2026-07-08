"""Visual-asset lowering (Phase C6) — ``AssetTrack`` → placed, timed overlays.

The renderer must *consume* asset tracks, never special-case them: this module
is the single place that turns declarative :class:`AssetClip` data into concrete
geometry (an :class:`AssetPlacement` rectangle from a layout) and a per-time
animation state (alpha + slide offset + scale). Both backends (the hermetic
mock proxy and the real FFmpeg MP4) lower with the SAME code.

Everything is resolution-independent (fractions) and deterministic; pure, no I/O.
"""
from __future__ import annotations

import hashlib

from reel_engine.interfaces.types import AssetClip, AssetPlacement, Timeline


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def _corner_xy(corner: str, w: float, h: float, m: float) -> tuple:
    x = m if "left" in corner else 1.0 - m - w
    y = m if "top" in corner else 1.0 - m - h
    return max(0.0, x), max(0.0, y)


def resolve_layout(layout) -> AssetPlacement:
    """Resolve a high-level :class:`AssetLayout` into a destination rectangle."""
    k, s, m = layout.kind, layout.scale, layout.margin
    if k in ("full_screen", "background_replacement"):
        return AssetPlacement(0.0, 0.0, 1.0, 1.0, "cover")
    if k == "picture_in_picture":
        x, y = _corner_xy(layout.corner, s, s, m)
        return AssetPlacement(x, y, s, s, "cover")
    if k == "floating_card":
        x, y = _corner_xy(layout.corner, s, s, m)
        return AssetPlacement(x, y, s, s, "contain")
    if k == "split_screen":
        return (AssetPlacement(0.0, 0.0, 0.5, 1.0, "cover") if layout.side == "left"
                else AssetPlacement(0.5, 0.0, 0.5, 1.0, "cover"))
    if k == "side_by_side":
        w = 0.5 - 1.5 * m
        x = m if layout.side == "left" else 0.5 + 0.5 * m
        return AssetPlacement(x, m, w, 1.0 - 2 * m, "contain")
    if k == "top_banner":
        return AssetPlacement(0.0, 0.0, 1.0, 0.25, "cover")
    if k == "bottom_banner":
        return AssetPlacement(0.0, 0.75, 1.0, 0.25, "cover")
    return AssetPlacement(0.0, 0.0, 1.0, 1.0, "cover")   # defensive default


def resolve_placement(clip: AssetClip) -> AssetPlacement:
    """The clip's explicit placement, else the placement its layout resolves to."""
    return clip.placement if clip.placement is not None else resolve_layout(clip.layout)


def _enter_mod(kind: str, p: float) -> tuple:
    """(alpha, x_off_frac, y_off_frac, scale) for an enter effect at progress p."""
    if kind in ("fade_in", "cross_dissolve"):
        return p, 0.0, 0.0, 1.0
    if kind == "slide_left":               # enters from the right, moves left
        return 1.0, (1.0 - p) * 1.0, 0.0, 1.0
    if kind == "slide_right":              # enters from the left
        return 1.0, -(1.0 - p) * 1.0, 0.0, 1.0
    if kind == "scale":
        return 1.0, 0.0, 0.0, 0.3 + 0.7 * p
    return 1.0, 0.0, 0.0, 1.0


def _exit_mod(kind: str, r: float) -> tuple:
    """(alpha, x_off, y_off, scale) for an exit effect; r goes 1→0 to the end."""
    if kind in ("fade_out", "cross_dissolve"):
        return r, 0.0, 0.0, 1.0
    if kind == "slide_left":               # leaves to the left
        return 1.0, -(1.0 - r) * 1.0, 0.0, 1.0
    if kind == "slide_right":
        return 1.0, (1.0 - r) * 1.0, 0.0, 1.0
    if kind == "scale":
        return 1.0, 0.0, 0.0, 0.3 + 0.7 * r
    return 1.0, 0.0, 0.0, 1.0


def asset_anim_state(clip: AssetClip, t: float) -> tuple:
    """(alpha, x_off_frac, y_off_frac, scale) for ``clip`` at absolute time ``t``.

    Enter effect ramps over ``[start, start+in.dur]``; exit over
    ``[end-out.dur, end]``; a ``cross_dissolve`` transition fades in like
    ``fade_in`` when no explicit enter animation is set. Deterministic."""
    alpha, ox, oy, sc = 1.0, 0.0, 0.0, 1.0
    s, e = clip.start_s, clip.end_s
    ai, ao = clip.animation_in, clip.animation_out
    if ai.kind != "none" and ai.duration_s > 0 and t < s + ai.duration_s:
        p = _clamp((t - s) / ai.duration_s)
        a, x, y, z = _enter_mod(ai.kind, p)
        alpha, ox, oy, sc = alpha * a, ox + x, oy + y, sc * z
    if ao.kind != "none" and ao.duration_s > 0 and t > e - ao.duration_s:
        r = _clamp((e - t) / ao.duration_s)
        a, x, y, z = _exit_mod(ao.kind, r)
        alpha, ox, oy, sc = alpha * a, ox + x, oy + y, sc * z
    tr = clip.transition
    if (tr.kind == "cross_dissolve" and tr.duration_s > 0
            and ai.kind == "none" and t < s + tr.duration_s):
        alpha *= _clamp((t - s) / tr.duration_s)
    return alpha, ox, oy, sc


def resolve_assets(timeline: Timeline) -> list[AssetClip]:
    """Every asset clip across all asset tracks, in paint order.

    Sorted by ``(z_index, start_s)`` so lower layers paint first and earlier
    clips before later ones at the same layer."""
    clips: list[AssetClip] = [c for track in timeline.asset_tracks for c in track.clips]
    clips.sort(key=lambda c: (c.z_index, c.start_s))
    return clips


def asset_mock_color(clip_id: str) -> tuple:
    """A deterministic, distinctive RGB for a clip in the mock renderer (which
    has no image decoder). Stable across runs so hermetic tests can assert it."""
    d = hashlib.sha256(clip_id.encode("utf-8")).digest()
    return (60 + d[0] % 180, 60 + d[1] % 180, 60 + d[2] % 180)
