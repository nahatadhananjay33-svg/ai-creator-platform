"""Music mixing + renderer-integration tests (Phase C8). Hermetic — mock, no ffmpeg.

Proves the renderer *consumes* a native ``MusicTrack`` by mixing it under the
voice: the mixed audio loops a short bed to fill the reel, fades in/out, dips
under speech (ducking), honours the volume envelope and mute sections, never
clips, and is byte-for-byte deterministic. The mock renderer writes the mix as
its WAV sidecar, so every property is asserted directly from samples.
"""
from __future__ import annotations

import dataclasses

import pytest

from foundation.shared_utils import generate_sine_wav, read_wav, write_wav
from foundation.shared_utils.audio_mix import to_float
from reel_engine.config import ReelEngineConfig, RenderConfig
from reel_engine.interfaces.types import (
    AssetRef,
    AudioEnvelope,
    AudioFade,
    CaptionSegment,
    CaptionTrack,
    DuckingRule,
    LoopRule,
    MusicClip,
    MusicTrack,
    RenderRequest,
    Scene,
    Timeline,
)
from reel_engine.render import MockRenderer
from reel_engine.render.music import mix_timeline_audio, speech_windows

SR = 8000
DUR = 12.0


@pytest.fixture
def bed(tmp_path):
    # a short 2s bed so a 12s reel must LOOP it 6x
    p = tmp_path / "bed.wav"
    write_wav(p, generate_sine_wav(2.0, 330.0, SR, amplitude=0.5))
    return str(p)


def _clip(bed, **over):
    base = dict(clip_id="m0", source=AssetRef("file", bed), start_s=0.0, end_s=DUR,
                gain=0.6, fade=AudioFade(1.0, 1.0), loop=LoopRule(True, 0.0),
                ducking=DuckingRule(False))
    base.update(over)
    return MusicClip(**base)


def _tl(bed, *, clip=None, captions=True, scene_audio=None):
    scene = (Scene.from_video(0, "/x/v.mp4", duration_s=DUR, audio_uri=scene_audio)
             if scene_audio else Scene.simple(0, (0, 0, 255), "x", duration_s=DUR))
    caps = ()
    if captions:
        caps = (CaptionTrack("captions", "sentence",
                             (CaptionSegment("s0", 0, "hello world", 4.0, 8.0),)),)
    return Timeline(scenes=(scene,), caption_tracks=caps,
                    music_tracks=(MusicTrack(clips=(clip or _clip(bed),)),))


def _rms(f, a, b):
    seg = f[int(a * SR):int(b * SR)]
    return (sum(x * x for x in seg) / max(1, len(seg))) ** 0.5


def _mixed(tl):
    return to_float(mix_timeline_audio(tl, SR).samples)


# ------------------------------------------------------------------- mixing
def test_music_present_and_loops_past_source_length(bed):
    f = _mixed(_tl(bed, clip=_clip(bed, fade=AudioFade(0, 0))))
    assert len(f) == int(DUR * SR)
    # source is only 2s; music still audible at 5s and 11s -> it looped
    assert _rms(f, 5.0, 5.5) > 0.05 and _rms(f, 10.8, 11.5) > 0.05


def test_fades_ramp_edges(bed):
    f = _mixed(_tl(bed))
    assert _rms(f, 0.0, 0.3) < _rms(f, 2.5, 3.5)     # fade-in
    assert _rms(f, 11.7, 12.0) < _rms(f, 2.5, 3.5)   # fade-out


def test_ducking_lowers_music_under_speech(bed):
    ducked = _clip(bed, fade=AudioFade(0, 0),
                   ducking=DuckingRule(True, 0.3, 0.1, 0.1))
    f = _mixed(_tl(bed, clip=ducked))
    # caption speech window is [4, 8]; music there is quieter than outside it
    assert _rms(f, 5.0, 7.5) < 0.5 * _rms(f, 1.0, 3.0)


def test_no_ducking_when_disabled(bed):
    f = _mixed(_tl(bed, clip=_clip(bed, fade=AudioFade(0, 0), ducking=DuckingRule(False))))
    assert _rms(f, 5.0, 7.5) == pytest.approx(_rms(f, 1.0, 3.0), rel=0.2)


def test_volume_envelope_dips_middle(bed):
    env = _clip(bed, fade=AudioFade(0, 0),
                envelope=AudioEnvelope(((0.0, 1.0), (6.0, 0.1), (12.0, 1.0))))
    f = _mixed(_tl(bed, clip=env))
    assert _rms(f, 5.5, 6.5) < 0.4 * _rms(f, 0.5, 1.5)   # trough near t=6


def test_mute_sections_silence_music(bed):
    muted = _clip(bed, fade=AudioFade(0, 0), mute_sections=((3.0, 5.0),))
    f = _mixed(_tl(bed, clip=muted))
    assert _rms(f, 3.5, 4.5) < 1e-4
    assert _rms(f, 6.0, 7.0) > 0.05


def test_mix_never_clips_even_with_hot_gain(bed):
    hot = _clip(bed, gain=1.0, fade=AudioFade(0, 0))
    f = _mixed(_tl(bed, clip=hot))
    assert max(abs(x) for x in f) < 1.0


def test_mix_is_deterministic(bed):
    tl = _tl(bed)
    assert mix_timeline_audio(tl, SR).samples == mix_timeline_audio(tl, SR).samples


def test_speech_windows_prefers_captions(bed):
    assert speech_windows(_tl(bed)) == [(4.0, 8.0)]


def test_voice_bed_is_mixed_in(bed, tmp_path):
    # a real scene-audio file becomes the voice bed and appears in the mix
    voice = tmp_path / "voice.wav"
    write_wav(voice, generate_sine_wav(DUR, 180.0, SR, amplitude=0.5))
    silent_music = _clip(bed, gain=0.0)          # no music -> mix is only the voice
    f = _mixed(_tl(bed, clip=silent_music, captions=False, scene_audio=str(voice)))
    assert _rms(f, 3.0, 5.0) > 0.1


# ------------------------------------------------------- renderer integration
def test_mock_renderer_writes_mixed_sidecar(bed, tmp_path):
    cfg = ReelEngineConfig(render=RenderConfig(mock_max_dim=80, audio_sample_rate=SR))
    ducked = _clip(bed, fade=AudioFade(1.0, 1.0), ducking=DuckingRule(True, 0.3, 0.1, 0.1))
    tl = _tl(bed, clip=ducked)
    res = MockRenderer(cfg).render(RenderRequest(
        timeline=tl, output_path=tmp_path / "reel.avi", renderer="mock",
        export_profiles=("square_1x1",)))
    assert res.metadata["music"] is True
    f = to_float(read_wav(res.audio_path).samples)
    assert len(f) == int(DUR * SR)
    assert max(abs(x) for x in f) < 1.0                       # no clipping
    assert _rms(f, 5.0, 7.5) < 0.5 * _rms(f, 1.5, 3.0)        # ducked under speech


def test_mock_render_is_byte_identical(bed, tmp_path):
    cfg = ReelEngineConfig(render=RenderConfig(mock_max_dim=80, audio_sample_rate=SR))
    tl = _tl(bed)
    a = MockRenderer(cfg).render(RenderRequest(timeline=tl, output_path=tmp_path / "a.avi",
                                               renderer="mock"))
    b = MockRenderer(cfg).render(RenderRequest(timeline=tl, output_path=tmp_path / "b.avi",
                                               renderer="mock"))
    assert read_wav(a.audio_path).samples == read_wav(b.audio_path).samples
    assert a.timeline_hash == b.timeline_hash


def test_no_music_writes_silent_sidecar(tmp_path):
    cfg = ReelEngineConfig(render=RenderConfig(mock_max_dim=80, audio_sample_rate=SR))
    tl = Timeline(scenes=(Scene.simple(0, (0, 0, 255), "x", duration_s=4.0),))
    res = MockRenderer(cfg).render(RenderRequest(timeline=tl, output_path=tmp_path / "s.avi",
                                                 renderer="mock"))
    assert res.metadata["music"] is False
    assert set(read_wav(res.audio_path).samples) == {0}       # silent
