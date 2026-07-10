"""Individual check tests (Phase C16) — each fixed rule, PASS/WARN/FAIL/SKIP."""
from __future__ import annotations

from pathlib import Path

from quality_engine.checker import checks as C
from quality_engine.checker.config import QualityConfig
from quality_engine.checker.model import ExportProbe, ReelArtifacts, ReelInspection
from quality_engine.checker.report import CheckStatus

from quality_engine.tests.conftest import make_timeline

CFG = QualityConfig()
P, W, F, S = CheckStatus.PASS, CheckStatus.WARN, CheckStatus.FAIL, CheckStatus.SKIP


def _insp(**kw):
    base = dict(master_exists=True, video_readable=True, width=1080, height=1920,
                fps=24.0, n_frames=144, video_duration_s=6.0, audio_source="sidecar",
                audio_present=True, audio_duration_s=6.0, audio_silent=False)
    base.update(kw)
    return ReelInspection(**base)


def _art(**kw):
    return ReelArtifacts(master_path=Path("master.avi"), **kw)


# ---- required checks ---------------------------------------------------------
def test_video_exists_pass_and_fail():
    assert C.check_video_exists(_art(), _insp(), CFG).status is P
    assert C.check_video_exists(_art(), _insp(master_exists=False), CFG).status is F


def test_video_playable():
    assert C.check_video_playable(_art(), _insp(), CFG).status is P
    assert C.check_video_playable(_art(), _insp(video_readable=False, n_frames=0,
                                                errors=("boom",)), CFG).status is F
    assert C.check_video_playable(_art(), _insp(master_exists=False), CFG).status is S


def test_audio_exists():
    assert C.check_audio_exists(_art(), _insp(), CFG).status is P
    assert C.check_audio_exists(_art(), _insp(audio_present=False,
                                              audio_source="none"), CFG).status is F


def test_audio_matches_video_tolerance():
    assert C.check_audio_matches_video(_art(), _insp(audio_duration_s=6.2), CFG).status is P
    assert C.check_audio_matches_video(_art(), _insp(audio_duration_s=9.0), CFG).status is F
    # muxed audio is aligned by construction
    assert C.check_audio_matches_video(_art(), _insp(audio_source="muxed"), CFG).status is P
    # no audio -> skip (audio_exists already reported the failure)
    assert C.check_audio_matches_video(_art(), _insp(audio_present=False), CFG).status is S


def test_resolution_correct_aspect_from_timeline():
    art = _art(timeline=make_timeline())
    good = ExportProbe("reel_9x16", Path("a"), True, 90, 160, "9:16", "9:16")
    bad = ExportProbe("square_1x1", Path("b"), True, 160, 90, "16:9", "1:1")
    assert C.check_resolution_correct(art, _insp(exports=(good,)), CFG).status is P
    assert C.check_resolution_correct(art, _insp(exports=(bad,)), CFG).status is F
    # wrong master aspect fails
    assert C.check_resolution_correct(art, _insp(width=1920, height=1080), CFG).status is F


def test_resolution_correct_exact_dims_when_configured():
    cfg = QualityConfig(expected_width=1080, expected_height=1920)
    assert C.check_resolution_correct(_art(), _insp(width=1080, height=1920), cfg).status is P
    assert C.check_resolution_correct(_art(), _insp(width=720, height=1280), cfg).status is F


def test_resolution_skips_when_nothing_to_verify():
    assert C.check_resolution_correct(_art(), _insp(), CFG).status is S


def test_duration_within_limits():
    assert C.check_duration_within_limits(_art(), _insp(video_duration_s=6.0), CFG).status is P
    assert C.check_duration_within_limits(_art(), _insp(video_duration_s=1.0), CFG).status is F
    assert C.check_duration_within_limits(_art(), _insp(video_duration_s=120.0), CFG).status is F
    assert C.check_duration_within_limits(_art(), _insp(video_readable=False), CFG).status is S


# ---- advisory checks ---------------------------------------------------------
def test_avatar_present():
    assert C.check_avatar_present(_art(avatar={"enabled": True, "clips": [1]}),
                                  _insp(), CFG).status is P
    assert C.check_avatar_present(_art(avatar={"enabled": False}), _insp(), CFG).status is W
    assert C.check_avatar_present(_art(), _insp(), CFG).status is W


def test_voice_present(tmp_path):
    clip = tmp_path / "v.wav"
    clip.write_bytes(b"x")
    assert C.check_voice_present(_art(voice_clips=(clip,)), _insp(), CFG).status is P
    # no clips but non-silent audio -> pass
    assert C.check_voice_present(_art(), _insp(), CFG).status is P
    # silent audio, no clips -> warn
    assert C.check_voice_present(_art(), _insp(audio_silent=True), CFG).status is W
    # missing clip file -> falls back to audio (non-silent -> pass)
    assert C.check_voice_present(_art(voice_clips=(tmp_path / "missing.wav",)),
                                 _insp(), CFG).status is P


def test_captions_present_timeline_and_sidecar():
    assert C.check_captions_present(_art(timeline=make_timeline(with_captions=True)),
                                    _insp(), CFG).status is P
    assert C.check_captions_present(_art(timeline=make_timeline(with_captions=False)),
                                    _insp(), CFG).status is W
    # no timeline but a sidecar with cues -> pass
    assert C.check_captions_present(_art(), _insp(captions_sidecar_exists=True,
                                                  n_caption_cues=3), CFG).status is P


def test_branding_present():
    assert C.check_branding_present(_art(timeline=make_timeline(with_branding=True)),
                                    _insp(), CFG).status is P
    assert C.check_branding_present(_art(timeline=make_timeline(with_branding=False)),
                                    _insp(), CFG).status is W
    assert C.check_branding_present(_art(), _insp(), CFG).status is S  # no timeline


def test_music_present():
    tl = make_timeline()
    assert not tl.has_music
    assert C.check_music_present(_art(timeline=tl), _insp(), CFG).status is W
    assert C.check_music_present(_art(), _insp(), CFG).status is S


def test_run_checks_returns_all_in_order():
    results = C.run_checks(_art(timeline=make_timeline()), _insp(), CFG)
    assert [r.key for r in results] == [
        "video_exists", "video_playable", "audio_exists", "audio_matches_video",
        "avatar_present", "voice_present", "captions_present", "branding_present",
        "music_present", "resolution_correct", "duration_within_limits"]
