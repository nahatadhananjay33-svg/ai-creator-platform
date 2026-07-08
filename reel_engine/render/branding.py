"""Branding lowering (Phase C5) — ``BrandingTrack`` → timed overlay ops.

The renderer must *consume* branding tracks, never special-case them: this
module is the single place that resolves a declarative :class:`BrandingTrack`
(a theme + typed components) into concrete, absolutely-timed
:class:`BrandingElement` ops. Both backends (the hermetic mock proxy and the
real FFmpeg MP4) lower with the SAME code.

Resolution rules (all in absolute reel time):

- **logo** / **watermark** — span the reel unless the component bounds them.
- **lower thirds** — their explicit windows.
- **intro** — a full-frame card over ``[0, intro.duration_s]``.
- **outro** — a full-frame card over ``[reel - outro.duration_s, reel]``.

Elements are returned bottom-to-top: logo, watermark, lower thirds, then the
intro/outro cards LAST so a card cleanly covers everything during its window.
Positions are resolution-independent fractions; pure and deterministic.
"""
from __future__ import annotations

from reel_engine.interfaces.types import BrandingElement, Timeline


def anchor_frac(position: str, box_w_frac: float, box_h_frac: float,
                safe_h: float, safe_v: float) -> tuple:
    """Top-left (x_frac, y_frac) for a box of the given fractional size at
    ``position``, honouring the safe-area margins (fractions of the frame)."""
    if "left" in position:
        x = safe_h
    elif "right" in position:
        x = 1.0 - safe_h - box_w_frac
    else:                                   # center / *_center / bottom band
        x = (1.0 - box_w_frac) / 2.0
    if "top" in position:
        y = safe_v
    elif "bottom" in position:
        y = 1.0 - safe_v - box_h_frac
    else:                                   # center / center_left / center_right
        y = (1.0 - box_h_frac) / 2.0
    return max(0.0, x), max(0.0, y)


def _window(start, end, reel_duration: float) -> tuple:
    s = start if start is not None else 0.0
    e = end if end is not None else reel_duration
    return max(0.0, s), min(reel_duration, e)


def resolve_branding(timeline: Timeline) -> list[BrandingElement]:
    """Resolve ``timeline.branding`` into ordered, absolutely-timed elements."""
    b = timeline.branding
    if b is None or not b.has_elements:
        return []
    dur = timeline.duration_s
    th = b.theme
    els: list[BrandingElement] = []

    if b.logo is not None:
        s, e = _window(b.logo.start_s, b.logo.end_s, dur)
        els.append(BrandingElement(
            kind="logo", start_s=s, end_s=e, position=b.logo.position,
            scale=b.logo.scale, opacity=b.logo.opacity, text=b.logo.text,
            source=b.logo.source, fill_color=th.primary_color,
            text_color=th.text_color, font_family=th.font_family))

    if b.watermark is not None:
        s, e = _window(b.watermark.start_s, b.watermark.end_s, dur)
        els.append(BrandingElement(
            kind="watermark", start_s=s, end_s=e, position=b.watermark.position,
            scale=b.watermark.scale, opacity=b.watermark.opacity, text=b.watermark.text,
            source=b.watermark.source, fill_color=th.secondary_color,
            text_color=th.secondary_color, font_family=th.font_family))

    for lt in b.lower_thirds:
        els.append(BrandingElement(
            kind="lower_third", start_s=lt.start_s, end_s=lt.end_s, position=lt.position,
            opacity=lt.opacity, text=lt.title, subtitle=lt.subtitle,
            fill_color=th.primary_color, text_color=th.text_color,
            font_family=th.font_family))

    if b.intro is not None:
        els.append(BrandingElement(
            kind="intro", start_s=0.0, end_s=min(b.intro.duration_s, dur),
            position="center", text=b.intro.title, subtitle=b.intro.subtitle,
            fill_color=th.background_color, text_color=th.text_color,
            font_family=th.font_family, full_frame=True))

    if b.outro is not None:
        od = min(b.outro.duration_s, dur)
        els.append(BrandingElement(
            kind="outro", start_s=max(0.0, dur - od), end_s=dur, position="center",
            text=b.outro.title, subtitle=b.outro.subtitle, lines=tuple(b.outro.handles),
            fill_color=th.background_color, text_color=th.text_color,
            font_family=th.font_family, full_frame=True))

    return els
