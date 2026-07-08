"""Reusable brand themes (Phase C5).

Named :class:`Theme` presets — pure data — that the engine/renderer consume. A
theme is a starting point: every field is overridable via config or per call
(the engine applies overrides with ``dataclasses.replace``). Colours are RGB
triples; margins are fractions of the frame (resolution independent).

Each theme defines a font, primary/secondary colours, a logo placement, safe
margins, a lower-third look, and intro/outro lengths — so a creator picks a
theme and overrides only what they must.
"""
from __future__ import annotations

from reel_engine.interfaces.types import Theme

_WHITE = (255, 255, 255)
_BLACK = (10, 10, 12)

_PRESETS: dict[str, Theme] = {
    "classic": Theme(
        name="classic", font_family="DejaVuSans",
        primary_color=(24, 119, 242), secondary_color=_WHITE, text_color=_WHITE,
        background_color=(12, 14, 20), logo_position="top_right", logo_scale=0.14,
        safe_margin_v=0.06, safe_margin_h=0.05, lower_third_opacity=0.85,
        watermark_opacity=0.45, intro_duration_s=2.0, outro_duration_s=2.5),
    "minimal": Theme(
        name="minimal", font_family="DejaVuSans",
        primary_color=(20, 20, 20), secondary_color=(90, 90, 90), text_color=(20, 20, 20),
        background_color=(248, 248, 248), logo_position="top_left", logo_scale=0.10,
        safe_margin_v=0.05, safe_margin_h=0.04, lower_third_opacity=0.7,
        watermark_opacity=0.3, intro_duration_s=1.5, outro_duration_s=2.0),
    "corporate": Theme(
        name="corporate", font_family="DejaVuSans",
        primary_color=(10, 37, 64), secondary_color=(0, 160, 220), text_color=_WHITE,
        background_color=(10, 20, 35), logo_position="top_right", logo_scale=0.13,
        safe_margin_v=0.07, safe_margin_h=0.06, lower_third_opacity=0.9,
        watermark_opacity=0.4, intro_duration_s=2.0, outro_duration_s=3.0),
    "modern": Theme(
        name="modern", font_family="DejaVuSans",
        primary_color=(255, 45, 120), secondary_color=(0, 220, 255), text_color=_WHITE,
        background_color=(18, 18, 24), logo_position="top_right", logo_scale=0.15,
        safe_margin_v=0.06, safe_margin_h=0.05, lower_third_opacity=0.8,
        watermark_opacity=0.5, intro_duration_s=1.8, outro_duration_s=2.5),
    "real_estate": Theme(
        name="real_estate", font_family="DejaVuSans",
        primary_color=(176, 141, 87), secondary_color=_WHITE, text_color=_WHITE,
        background_color=(28, 28, 30), logo_position="top_left", logo_scale=0.14,
        safe_margin_v=0.07, safe_margin_h=0.06, lower_third_opacity=0.85,
        watermark_opacity=0.4, intro_duration_s=2.2, outro_duration_s=3.0),
    "finance": Theme(
        name="finance", font_family="DejaVuSans",
        primary_color=(0, 102, 68), secondary_color=(212, 175, 55), text_color=_WHITE,
        background_color=(8, 20, 16), logo_position="top_right", logo_scale=0.13,
        safe_margin_v=0.07, safe_margin_h=0.06, lower_third_opacity=0.9,
        watermark_opacity=0.4, intro_duration_s=2.0, outro_duration_s=3.0),
    "education": Theme(
        name="education", font_family="DejaVuSans",
        primary_color=(255, 145, 0), secondary_color=(33, 150, 243), text_color=_WHITE,
        background_color=(20, 24, 32), logo_position="top_right", logo_scale=0.14,
        safe_margin_v=0.06, safe_margin_h=0.05, lower_third_opacity=0.85,
        watermark_opacity=0.4, intro_duration_s=2.0, outro_duration_s=2.5),
    "medical": Theme(
        name="medical", font_family="DejaVuSans",
        primary_color=(0, 150, 170), secondary_color=(0, 90, 110), text_color=(15, 30, 35),
        background_color=(240, 248, 250), logo_position="top_right", logo_scale=0.13,
        safe_margin_v=0.06, safe_margin_h=0.05, lower_third_opacity=0.85,
        watermark_opacity=0.35, intro_duration_s=2.0, outro_duration_s=2.5),
    "dark": Theme(
        name="dark", font_family="DejaVuSans",
        primary_color=(235, 235, 235), secondary_color=(150, 150, 150), text_color=_WHITE,
        background_color=(0, 0, 0), logo_position="top_right", logo_scale=0.14,
        safe_margin_v=0.06, safe_margin_h=0.05, lower_third_opacity=0.8,
        watermark_opacity=0.5, intro_duration_s=1.8, outro_duration_s=2.5),
    "light": Theme(
        name="light", font_family="DejaVuSans",
        primary_color=(15, 15, 18), secondary_color=(90, 90, 90), text_color=(15, 15, 18),
        background_color=(255, 255, 255), logo_position="top_right", logo_scale=0.14,
        safe_margin_v=0.06, safe_margin_h=0.05, lower_third_opacity=0.75,
        watermark_opacity=0.35, intro_duration_s=1.8, outro_duration_s=2.5),
}


def get_theme(name: str) -> Theme:
    """Return the theme preset named ``name`` (raises for an unknown name)."""
    try:
        return _PRESETS[name]
    except KeyError:
        raise KeyError(f"Unknown theme {name!r}; known: {sorted(_PRESETS)}") from None


def theme_names() -> list[str]:
    return sorted(_PRESETS)


def all_themes() -> list[Theme]:
    return [_PRESETS[n] for n in theme_names()]
