"""Scene-aware music planning (Phase C8).

Turns high-level intent ("put an ambient bed under this reel") into a concrete
:class:`MusicSpec` the builder can lower — deterministically, from the config and
the reel's structure. This is the "scene-aware music timing" step: the bed spans
the whole reel by default, and when the Timeline carries branding the fades are
matched to the intro/outro so the music breathes up under the opening card and
tails out under the closing one. No model, no I/O, no randomness.
"""
from __future__ import annotations

from reel_engine.interfaces.types import Timeline

from music_engine.config.settings import MusicEngineConfig
from music_engine.providers.base import MusicSpec


def plan_background_music(
    reel_duration_s: float,
    cfg: MusicEngineConfig,
    *,
    soundtrack: str | None = None,
    source: str | None = None,
    start_s: float = 0.0,
    end_s: float = 0.0,
    duck: bool | None = None,
    gain: float | None = None,
    mute_sections: tuple = (),
    clip_id: str = "music-000",
) -> MusicSpec:
    """A whole-reel background bed (fades + loop + ducking from config).

    ``end_s == 0`` spans to the reel end. ``source`` (a local file) wins over
    ``soundtrack``; when neither is given the config's ``default_soundtrack`` is
    used, so a caller can ask for music with nothing but a reel duration."""
    name = None if source else (soundtrack or cfg.default_soundtrack)
    return MusicSpec(
        source=source, soundtrack=name, start_s=start_s, end_s=end_s,
        gain=gain, duck=duck, mute_sections=tuple(mute_sections), clip_id=clip_id,
    )


def plan_for_timeline(
    timeline: Timeline,
    cfg: MusicEngineConfig,
    *,
    soundtrack: str | None = None,
    source: str | None = None,
    duck: bool | None = None,
    gain: float | None = None,
) -> MusicSpec:
    """Scene-aware plan: a whole-reel bed with fades matched to any branding.

    When the timeline has a branding intro/outro the fade-in covers the intro and
    the fade-out covers the outro (clamped to the config lengths as a floor), so
    the music rises under the opening card and settles under the closing one.
    Falls back to :func:`plan_background_music` (config fades) with no branding."""
    spec = plan_background_music(
        timeline.duration_s, cfg, soundtrack=soundtrack, source=source,
        duck=duck, gain=gain)
    br = timeline.branding
    if br is not None:
        fade_in = max(cfg.fade_in_s, br.intro.duration_s if br.intro else 0.0)
        fade_out = max(cfg.fade_out_s, br.outro.duration_s if br.outro else 0.0)
        # keep the two fades inside the reel
        total = timeline.duration_s
        if fade_in + fade_out > total:
            scale = total / (fade_in + fade_out)
            fade_in, fade_out = fade_in * scale, fade_out * scale
        spec = MusicSpec(**{**spec.__dict__, "fade_in_s": round(fade_in, 3),
                            "fade_out_s": round(fade_out, 3)})
    return spec
