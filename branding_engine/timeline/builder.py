"""Brand info + theme -> BrandingTrack builder (Phase C5).

Composes the frozen Timeline IR :class:`BrandingTrack` from a :class:`Theme` and
plain brand facts (creator, channel, website, handles, logo). This is where the
component defaults come from: an intro titled by the channel, an outro thanking
viewers with the handles, a lower third naming the creator, a logo, and a
watermark from the website/handle — each independently toggleable.

Pure and deterministic: no I/O. Timing is left mostly symbolic (intro from reel
start, outro from reel end are resolved at render/lowering time); the lower
third gets an explicit window, clamped to the reel when its duration is known.
The result is validated by the Timeline validator before rendering.
"""
from __future__ import annotations

from reel_engine.interfaces.types import (
    AssetRef,
    BrandingTrack,
    Intro,
    Logo,
    LowerThird,
    Outro,
    Theme,
    Watermark,
)


def initials(text: str, limit: int = 3) -> str:
    """Uppercase initials from ``text`` (e.g. "AI Creator Platform" -> "ACP")."""
    parts = [w for w in text.split() if w]
    if not parts:
        return ""
    return "".join(w[0] for w in parts[:limit]).upper()


def _first(*values: str | None) -> str:
    for v in values:
        if v and v.strip():
            return v.strip()
    return ""


def build_branding_track(
    theme: Theme,
    *,
    creator: str = "",
    channel: str = "",
    website: str = "",
    handles: tuple = (),
    logo_source: AssetRef | None = None,
    logo_text: str | None = None,
    reel_duration_s: float | None = None,
    include_logo: bool = True,
    include_watermark: bool = True,
    include_intro: bool = True,
    include_outro: bool = True,
    include_lower_third: bool = True,
    intro_title: str | None = None,
    intro_subtitle: str | None = None,
    intro_duration_s: float | None = None,
    outro_title: str | None = None,
    outro_subtitle: str | None = None,
    outro_duration_s: float | None = None,
    lower_third_title: str | None = None,
    lower_third_subtitle: str | None = None,
    lower_third_start_s: float = 1.0,
    lower_third_duration_s: float = 3.0,
    watermark_text: str | None = None,
    track_id: str = "branding",
) -> BrandingTrack:
    """Assemble a :class:`BrandingTrack` from a theme + brand facts."""
    handles = tuple(handles)

    logo = None
    if include_logo:
        badge = logo_text or initials(_first(channel, creator))
        if logo_source is not None or badge:
            logo = Logo(source=logo_source, text=badge or None,
                        position=theme.logo_position, scale=theme.logo_scale, opacity=1.0)

    watermark = None
    if include_watermark:
        wtext = _first(watermark_text, website, handles[0] if handles else None, channel)
        if wtext:
            watermark = Watermark(text=wtext, position="bottom_right",
                                  scale=0.10, opacity=theme.watermark_opacity)

    intro = None
    if include_intro:
        intro = Intro(
            title=_first(intro_title, channel, creator, "Welcome"),
            subtitle=_first(intro_subtitle, handles[0] if handles else None, website),
            duration_s=intro_duration_s if intro_duration_s is not None else theme.intro_duration_s,
        )

    outro = None
    if include_outro:
        outro = Outro(
            title=_first(outro_title, "Thanks for watching"),
            subtitle=_first(outro_subtitle, (f"Follow {channel}" if channel else "")),
            duration_s=outro_duration_s if outro_duration_s is not None else theme.outro_duration_s,
            handles=handles,
        )

    lower_thirds: tuple = ()
    if include_lower_third:
        title = _first(lower_third_title, creator, channel)
        if title:
            start = max(0.0, lower_third_start_s)
            end = start + max(0.1, lower_third_duration_s)
            if reel_duration_s is not None:
                end = min(end, reel_duration_s)
                start = min(start, max(0.0, end - 0.1))
            lower_thirds = (LowerThird(
                title=title,
                subtitle=_first(lower_third_subtitle, channel if creator else "",
                                handles[0] if handles else ""),
                start_s=round(start, 3), end_s=round(end, 3),
                position=theme.lower_third_position, opacity=theme.lower_third_opacity),)

    return BrandingTrack(track_id=track_id, theme=theme, logo=logo, watermark=watermark,
                         intro=intro, outro=outro, lower_thirds=lower_thirds)
