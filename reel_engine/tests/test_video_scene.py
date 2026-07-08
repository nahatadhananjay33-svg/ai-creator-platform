"""Video-backed scene tests (Phase C3 architectural fix).

C2 scenes are synthetic (solid colour + text). C3 introduces the *video scene*:
a real media file (a talking-head MP4) placed on a ``video`` track, optionally
with the authoritative speech WAV on an ``audio`` track. These tests pin the
IR builder, validation, serde round-trip (all hermetic), and — when ffmpeg is
present — the real render path that muxes footage + audio into a playable MP4.
"""
from __future__ import annotations

import pytest

from foundation.shared_utils import generate_sine_wav, write_wav
from foundation.shared_utils.video_io import generate_test_pattern_video
from reel_engine.config import ReelEngineConfig, RenderConfig
from reel_engine.interfaces.types import Scene
from reel_engine.render import ffprobe_available, probe_media, render_timeline
from reel_engine.timeline import new_timeline
from reel_engine.timeline.serde import (
    timeline_from_json,
    timeline_to_dict,
    timeline_to_json,
)
from reel_engine.timeline.hashing import timeline_content_hash
from reel_engine.timeline.validate import validate_timeline


# ------------------------------------------------------------------ hermetic IR
def test_from_video_builds_video_and_audio_tracks():
    scene = Scene.from_video(0, "/tmp/avatar.mp4", duration_s=2.0,
                             audio_uri="/tmp/speech.wav")
    assert {t.kind for t in scene.tracks} == {"video", "audio"}
    vc = scene.video_clip()
    assert vc is not None and vc.kind == "video"
    assert vc.source.kind == "file" and vc.source.uri == "/tmp/avatar.mp4"
    ac = scene.audio_file_clip()
    assert ac is not None and ac.kind == "audio_file"
    assert ac.source.uri == "/tmp/speech.wav"
    assert scene.duration_s == 2.0


def test_from_video_without_audio_uses_silent_bed():
    scene = Scene.from_video(1, "/tmp/a.mp4", duration_s=1.5)
    assert scene.video_clip() is not None
    assert scene.audio_file_clip() is None            # no real-audio clip
    audio = scene.track("audio")
    assert audio.clips[0].kind == "silent_audio"


def test_video_timeline_validates():
    tl = new_timeline([Scene.from_video(0, "/tmp/a.mp4", duration_s=1.0,
                                        audio_uri="/tmp/a.wav")],
                      width=540, height=960, fps=30, validate=False)
    assert validate_timeline(tl) == []


def test_video_clip_without_source_is_rejected():
    from reel_engine.interfaces.types import Clip, Track
    bad = Scene(scene_id="s0", index=0, duration_s=1.0,
                tracks=(Track(track_id="vt", kind="video",
                              clips=(Clip(clip_id="v", kind="video",
                                          start_s=0.0, end_s=1.0, source=None),)),))
    problems = validate_timeline(new_timeline([bad], validate=False))
    assert any("no source file" in p for p in problems)


def test_scene_with_neither_background_nor_video_is_rejected():
    from reel_engine.interfaces.types import Clip, Track
    empty = Scene(scene_id="s0", index=0, duration_s=1.0,
                  tracks=(Track(track_id="at", kind="audio",
                                clips=(Clip(clip_id="a", kind="silent_audio",
                                            start_s=0.0, end_s=1.0),)),))
    problems = validate_timeline(new_timeline([empty], validate=False))
    assert any("nothing to render" in p for p in problems)


def test_video_timeline_serde_roundtrip_is_lossless():
    tl = new_timeline([Scene.from_video(0, "/tmp/a.mp4", duration_s=1.0,
                                        audio_uri="/tmp/a.wav")],
                      title="video", width=180, height=320, fps=24, validate=False)
    restored = timeline_from_json(timeline_to_json(tl))
    assert timeline_to_dict(restored) == timeline_to_dict(tl)
    assert timeline_content_hash(restored) == timeline_content_hash(tl)


# --------------------------------------------------------- real render (ffmpeg)
@pytest.fixture
def media(tmp_path):
    """A raw-AVI 'talking head' (as the mock avatar produces) + a speech WAV."""
    vid = generate_test_pattern_video(tmp_path / "avatar.avi",
                                      width=128, height=96, n_frames=48, fps=24.0)
    wav = tmp_path / "speech.wav"
    write_wav(wav, generate_sine_wav(duration_s=2.0, frequency_hz=220.0, sample_rate=24000))
    return vid, wav


@pytest.mark.skipif(not ffprobe_available(), reason="ffmpeg/ffprobe not installed")
def test_ffmpeg_renders_video_scene_to_playable_mp4(media, tmp_path):
    vid, wav = media
    tl = new_timeline([Scene.from_video(0, str(vid), duration_s=2.0, audio_uri=str(wav))],
                      title="video reel", width=180, height=320, fps=24)
    cfg = ReelEngineConfig(render=RenderConfig(width=180, height=320, fps=24, bitrate="800k"))
    res = render_timeline(tl, tmp_path / "reel.mp4", config=cfg, renderer="ffmpeg",
                          export_profiles=("reel_9x16",))
    p = probe_media(res.output_path)
    assert res.output_path.exists() and res.output_path.stat().st_size > 0
    assert (p.width, p.height) == (180, 320)          # letterboxed into master frame
    assert p.readable and p.has_audio                 # footage + muxed speech
    assert abs(p.duration_s - 2.0) < 0.3
    assert res.aspect == "9:16"
    (export,) = res.exports
    ep = probe_media(export.path)
    assert (ep.width, ep.height) == (1080, 1920)


@pytest.mark.skipif(not ffprobe_available(), reason="ffmpeg/ffprobe not installed")
def test_ffmpeg_video_scene_render_is_deterministic(media, tmp_path):
    vid, wav = media
    tl = new_timeline([Scene.from_video(0, str(vid), duration_s=2.0, audio_uri=str(wav))],
                      width=180, height=320, fps=24)
    cfg = ReelEngineConfig(render=RenderConfig(width=180, height=320, fps=24, bitrate="800k"))
    a = render_timeline(tl, tmp_path / "a.mp4", config=cfg, renderer="ffmpeg")
    b = render_timeline(tl, tmp_path / "b.mp4", config=cfg, renderer="ffmpeg")
    assert a.timeline_hash == b.timeline_hash          # same IR ⇒ same content hash
