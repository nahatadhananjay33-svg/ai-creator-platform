"""Reusable caption styles (Phase C4).

Named :class:`CaptionStyle` presets — pure data — that the engine/renderer
consume. A preset is just a starting point: every field is overridable via config
or per call (the engine applies overrides with ``dataclasses.replace``). Colours
are RGB triples (IR convention).

Presets are intentionally distinct so the demo can show real variety:
- ``classic``   white text, black outline, bottom (safe default)
- ``modern``    lighter outline, soft shadow, roomy bottom margin
- ``bold``      large uppercase, thick outline, high-impact
- ``minimal``   small, no outline/shadow, understated
- ``youtube``   semi-opaque box behind text, bottom (YT-style legibility)
- ``instagram`` centred, warm highlight colour, medium
- ``tiktok``    large uppercase, centred, strong highlight (karaoke-friendly)
"""
from __future__ import annotations

from reel_engine.interfaces.types import CaptionStyle

_WHITE = (255, 255, 255)
_BLACK = (0, 0, 0)
_GOLD = (255, 215, 0)
_CYAN = (0, 220, 255)
_PINK = (255, 64, 129)

_PRESETS: dict[str, CaptionStyle] = {
    "classic": CaptionStyle(
        name="classic", font_family="DejaVuSans", font_size=64,
        primary_color=_WHITE, highlight_color=_GOLD, outline_color=_BLACK,
        outline_width=4, shadow=True, shadow_offset=2,
        alignment="center", position="bottom", safe_margin_v=0.12,
        max_chars_per_line=38,
    ),
    "modern": CaptionStyle(
        name="modern", font_family="DejaVuSans", font_size=60,
        primary_color=_WHITE, highlight_color=_CYAN, outline_color=(40, 40, 40),
        outline_width=3, shadow=True, shadow_offset=3,
        alignment="center", position="bottom", safe_margin_v=0.16,
        max_chars_per_line=40,
    ),
    "bold": CaptionStyle(
        name="bold", font_family="DejaVuSans", font_size=84,
        primary_color=_WHITE, highlight_color=_GOLD, outline_color=_BLACK,
        outline_width=8, shadow=True, shadow_offset=3, bold=True, uppercase=True,
        alignment="center", position="bottom", safe_margin_v=0.14,
        max_chars_per_line=28,
    ),
    "minimal": CaptionStyle(
        name="minimal", font_family="DejaVuSans", font_size=52,
        primary_color=_WHITE, highlight_color=_WHITE, outline_color=_BLACK,
        outline_width=0, shadow=False, shadow_offset=0,
        alignment="center", position="bottom", safe_margin_v=0.10,
        max_chars_per_line=42,
    ),
    "youtube": CaptionStyle(
        name="youtube", font_family="DejaVuSans", font_size=58,
        primary_color=_WHITE, highlight_color=_GOLD, outline_color=_BLACK,
        outline_width=0, shadow=False, box=True, box_color=_BLACK, box_opacity=0.6,
        alignment="center", position="bottom", safe_margin_v=0.10,
        max_chars_per_line=42,
    ),
    "instagram": CaptionStyle(
        name="instagram", font_family="DejaVuSans", font_size=66,
        primary_color=_WHITE, highlight_color=_PINK, outline_color=_BLACK,
        outline_width=5, shadow=True, shadow_offset=2,
        alignment="center", position="center", safe_margin_v=0.14,
        max_chars_per_line=32,
    ),
    "tiktok": CaptionStyle(
        name="tiktok", font_family="DejaVuSans", font_size=78,
        primary_color=_WHITE, highlight_color=_GOLD, outline_color=_BLACK,
        outline_width=7, shadow=True, shadow_offset=3, bold=True, uppercase=True,
        alignment="center", position="center", safe_margin_v=0.18,
        max_chars_per_line=24,
    ),
}


def get_style(name: str) -> CaptionStyle:
    """Return the preset named ``name`` (raises for an unknown name)."""
    try:
        return _PRESETS[name]
    except KeyError:
        raise KeyError(f"Unknown caption style {name!r}; known: {sorted(_PRESETS)}") from None


def style_names() -> list[str]:
    return sorted(_PRESETS)


def all_styles() -> list[CaptionStyle]:
    return [_PRESETS[n] for n in style_names()]
