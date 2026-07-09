"""MusicSpec list -> MusicTrack builder (Phase C8).

Lowers authoring :class:`MusicSpec` requests into the frozen Timeline IR
:class:`MusicTrack`. This is where config defaults fill unset fields (music
level, fades, loop, ducking) and the provider resolves each spec to a concrete
local audio file (a supplied WAV or a deterministically-generated procedural
bed). Pure and deterministic apart from the provider's filesystem access; the
result is validated by the Timeline validator before rendering.
"""
from __future__ import annotations

from pathlib import Path

from reel_engine.interfaces.types import (
    AudioEnvelope,
    AudioFade,
    DuckingRule,
    LoopRule,
    MusicClip,
    MusicTrack,
)

from music_engine.config.settings import MusicEngineConfig
from music_engine.providers.base import LocalMusicProvider, MusicProvider, MusicSpec


def _pick(value, default):
    return default if value is None else value


def build_music_clip(spec: MusicSpec, index: int, reel_duration_s: float,
                     cfg: MusicEngineConfig, provider: MusicProvider,
                     *, sample_rate: int, asset_dir: Path | None) -> MusicClip:
    """Resolve one :class:`MusicSpec` into a fully-defaulted :class:`MusicClip`."""
    source = provider.resolve(spec, sample_rate=sample_rate, asset_dir=asset_dir)
    end_s = spec.end_s if spec.end_s else reel_duration_s
    fade = AudioFade(
        fade_in_s=_pick(spec.fade_in_s, cfg.fade_in_s),
        fade_out_s=_pick(spec.fade_out_s, cfg.fade_out_s),
        curve=cfg.fade_curve,
    )
    loop = LoopRule(
        enabled=_pick(spec.loop, cfg.loop_enabled),
        crossfade_s=_pick(spec.loop_crossfade_s, cfg.loop_crossfade_s),
    )
    ducking = DuckingRule(
        enabled=_pick(spec.duck, cfg.ducking_enabled),
        duck_level=_pick(spec.duck_level, cfg.ducking_level),
        attack_s=cfg.ducking_attack_s,
        release_s=cfg.ducking_release_s,
        pad_s=cfg.ducking_pad_s,
    )
    return MusicClip(
        clip_id=spec.clip_id or f"music-{index:03d}",
        source=source,
        start_s=spec.start_s,
        end_s=end_s,
        gain=_pick(spec.gain, cfg.volume),
        source_offset_s=spec.source_offset_s,
        fade=fade,
        envelope=AudioEnvelope(points=tuple(spec.envelope_points)),
        loop=loop,
        ducking=ducking,
        mute_sections=tuple(spec.mute_sections),
    )


def build_music_track(
    specs: list[MusicSpec],
    reel_duration_s: float,
    *,
    config: MusicEngineConfig | None = None,
    provider: MusicProvider | None = None,
    sample_rate: int = 44_100,
    asset_dir: Path | None = None,
    track_id: str = "music",
) -> MusicTrack:
    """Resolve and assemble a validated-shape :class:`MusicTrack` from specs.

    ``reel_duration_s`` fills any spec whose ``end_s`` is 0 (whole-reel bed).
    ``sample_rate`` is used when generating a procedural soundtrack; ``asset_dir``
    is where those generated beds are written."""
    cfg = config or MusicEngineConfig()
    provider = provider or LocalMusicProvider()
    clips = tuple(
        build_music_clip(spec, i, reel_duration_s, cfg, provider,
                         sample_rate=sample_rate, asset_dir=asset_dir)
        for i, spec in enumerate(specs)
    )
    return MusicTrack(track_id=track_id, clips=clips, gain=cfg.track_gain)
