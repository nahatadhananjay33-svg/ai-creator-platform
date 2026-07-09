"""Music & Audio Mixing Engine tests (Phase C8).

Fully hermetic and deterministic: NO renderer, NO ffmpeg, NO GPU, NO model, NO
network, NO downloads. Covers the authoring surface — config, providers
(procedural + local), scene-aware planning, the MusicSpec -> MusicTrack builder,
and the facade — plus the built-in soundtrack generator. Every built track is run
through the shared Timeline validator so the engine can never emit an
unrenderable music track.
"""
from __future__ import annotations

import dataclasses

import pytest

from foundation.shared_utils import read_wav
from reel_engine.interfaces.types import (
    BrandingTrack,
    Intro,
    Outro,
    Scene,
    Timeline,
)
from reel_engine.timeline.validate import validate_timeline

from music_engine import (
    MusicEngine,
    MusicSpec,
    generate_soundtrack,
    load_music_engine_config,
    plan_background_music,
    plan_for_timeline,
    soundtrack_names,
)
from music_engine.config.settings import MusicEngineConfig
from music_engine.providers.base import LocalMusicProvider

REEL = 12.0


def _valid_with(track, dur=REEL):
    tl = Timeline(scenes=(Scene.simple(0, (0, 0, 255), "x", duration_s=dur),),
                  music_tracks=(track,))
    return validate_timeline(tl)


# ----------------------------------------------------------------- providers
def test_soundtrack_names_are_stable():
    assert soundtrack_names() == ("ambient", "cinematic", "lofi", "upbeat")


def test_procedural_soundtrack_is_deterministic(tmp_path):
    a = generate_soundtrack("ambient", tmp_path / "a.wav", sample_rate=8000, duration_s=2.0)
    b = generate_soundtrack("ambient", tmp_path / "b.wav", sample_rate=8000, duration_s=2.0)
    assert read_wav(a).samples == read_wav(b).samples
    # different moods differ
    c = generate_soundtrack("upbeat", tmp_path / "c.wav", sample_rate=8000, duration_s=2.0)
    assert read_wav(a).samples != read_wav(c).samples
    # peak within range (won't clip on its own)
    assert max(abs(s) for s in read_wav(a).samples) <= 32767


def test_unknown_soundtrack_raises(tmp_path):
    with pytest.raises(ValueError):
        generate_soundtrack("dubstep", tmp_path / "x.wav")


def test_local_provider_resolves_and_flags_missing(tmp_path):
    wav = generate_soundtrack("lofi", tmp_path / "bed.wav", sample_rate=8000, duration_s=1.0)
    ref = LocalMusicProvider().resolve(MusicSpec(source=str(wav)), sample_rate=8000)
    assert ref.kind == "file" and ref.meta["music_source"] == "local"
    from foundation.exceptions import PlatformError
    with pytest.raises(PlatformError):
        LocalMusicProvider().resolve(MusicSpec(source="/nope/missing.wav"), sample_rate=8000)


def test_local_provider_generates_procedural(tmp_path):
    ref = LocalMusicProvider().resolve(MusicSpec(soundtrack="upbeat"),
                                       sample_rate=8000, asset_dir=tmp_path)
    assert ref.meta["music_source"] == "procedural" and ref.meta["soundtrack"] == "upbeat"
    assert read_wav(ref.uri).sample_rate == 8000


# ------------------------------------------------------------------ planning
def test_plan_background_music_defaults_to_config_soundtrack():
    cfg = MusicEngineConfig()
    spec = plan_background_music(REEL, cfg)
    assert spec.soundtrack == cfg.default_soundtrack and spec.end_s == 0.0


def test_plan_source_wins_over_soundtrack():
    spec = plan_background_music(REEL, MusicEngineConfig(), source="/x/bed.wav",
                                 soundtrack="upbeat")
    assert spec.source == "/x/bed.wav" and spec.soundtrack is None


def test_plan_for_timeline_matches_branding_fades():
    tl = Timeline(scenes=(Scene.simple(0, (0, 0, 255), "x", duration_s=REEL),),
                  branding=BrandingTrack(intro=Intro("Hi", duration_s=2.5),
                                         outro=Outro("Bye", duration_s=3.5)))
    spec = plan_for_timeline(tl, MusicEngineConfig(fade_in_s=1.0, fade_out_s=1.0))
    assert spec.fade_in_s == 2.5 and spec.fade_out_s == 3.5     # matched to cards


# ------------------------------------------------------------------- builder
def test_generate_builds_valid_full_reel_bed(tmp_path):
    track = MusicEngine().generate(REEL, soundtrack="ambient", sample_rate=8000,
                                   asset_dir=tmp_path)
    assert track.n_clips == 1
    c = track.clips[0]
    assert (c.start_s, c.end_s) == (0.0, REEL)                  # end_s filled
    assert c.gain == 0.18 and c.loop.enabled and c.ducking.enabled
    assert _valid_with(track) == []


def test_spec_overrides_win_over_config(tmp_path):
    spec = MusicSpec(soundtrack="lofi", gain=0.4, fade_in_s=0.0, duck=False,
                     loop=False, clip_id="bg")
    track = MusicEngine().build([spec], REEL, sample_rate=8000, asset_dir=tmp_path)
    c = track.clips[0]
    assert c.gain == 0.4 and c.fade.fade_in_s == 0.0
    assert not c.ducking.enabled and not c.loop.enabled and c.clip_id == "bg"
    assert _valid_with(track) == []


def test_generate_for_timeline_is_scene_aware(tmp_path):
    tl = Timeline(scenes=(Scene.simple(0, (0, 0, 255), "x", duration_s=REEL),),
                  branding=BrandingTrack(outro=Outro("Bye", duration_s=3.0)))
    track = MusicEngine().generate_for_timeline(tl, soundtrack="cinematic",
                                                sample_rate=8000, asset_dir=tmp_path)
    assert track.clips[0].fade.fade_out_s == 3.0
    assert _valid_with(dataclasses.replace(track)) == []


def test_engine_output_is_deterministic(tmp_path):
    t1 = MusicEngine().generate(REEL, soundtrack="ambient", sample_rate=8000, asset_dir=tmp_path)
    t2 = MusicEngine().generate(REEL, soundtrack="ambient", sample_rate=8000, asset_dir=tmp_path)
    assert t1 == t2


# ------------------------------------------------------------------- config
def test_config_defaults_and_overrides(monkeypatch):
    cfg = load_music_engine_config()
    assert cfg.volume == 0.18 and cfg.ducking_level == 0.35 and cfg.default_soundtrack == "ambient"
    cfg2 = load_music_engine_config(overrides={"music": {
        "volume": 0.3, "ducking": {"level": 0.5}, "loop": {"crossfade_s": 1.0}}})
    assert cfg2.volume == 0.3 and cfg2.ducking_level == 0.5 and cfg2.loop_crossfade_s == 1.0
    monkeypatch.setenv("AICP__music__default_soundtrack", "upbeat")
    assert load_music_engine_config().default_soundtrack == "upbeat"


def test_config_rejects_invalid_values():
    with pytest.raises(ValueError):
        MusicEngineConfig(volume=1.5)
    with pytest.raises(ValueError):
        MusicEngineConfig(ducking_level=-0.1)
    with pytest.raises(ValueError):
        MusicEngineConfig(fade_in_s=-1.0)
