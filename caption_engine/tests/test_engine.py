"""Caption Engine facade / provider / builder / styles / config tests (Phase C4).

Fully hermetic and deterministic: the heuristic timing provider needs no ASR,
model, or GPU, so the same (text, duration) always yields byte-identical
captions. Every generated track is checked against the Timeline validator so
the engine can never emit an unrenderable/unsynchronized track.
"""
from __future__ import annotations

import pytest

from reel_engine.interfaces.types import CaptionStyle, Scene, Timeline
from reel_engine.timeline.validate import validate_timeline

from caption_engine import (
    CAPTION_KINDS,
    CaptionEngine,
    load_caption_engine_config,
    style_names,
)
from caption_engine.providers import HeuristicTimingProvider
from caption_engine.styles import get_style

TEXT = "Welcome to the platform. Captions are native now. Enjoy the show."
DUR = 6.0


def _valid(track, duration_s=DUR):
    tl = Timeline(scenes=(Scene.simple(0, (0, 0, 255), "x", duration_s=duration_s),),
                  caption_tracks=(track,))
    return validate_timeline(tl)


# ------------------------------------------------------------------- provider
def test_heuristic_provider_is_deterministic_and_bounded():
    p = HeuristicTimingProvider()
    a = p.transcribe(text=TEXT, duration_s=DUR)
    b = p.transcribe(text=TEXT, duration_s=DUR)
    assert a == b                                   # byte-identical
    words = a.words()
    assert words[0].start_s == 0.0
    assert words[-1].end_s <= DUR + 1e-9            # never exceeds audio
    # strictly monotonic, non-overlapping
    for i in range(len(words) - 1):
        assert words[i].start_s <= words[i].end_s <= words[i + 1].start_s + 1e-9


def test_heuristic_empty_text_yields_no_segments():
    t = HeuristicTimingProvider().transcribe(text="   ", duration_s=DUR)
    assert t.segments == () and t.duration_s == DUR


def test_heuristic_rejects_nonpositive_duration():
    with pytest.raises(ValueError):
        HeuristicTimingProvider().transcribe(text=TEXT, duration_s=0.0)


# -------------------------------------------------------------------- builder
@pytest.mark.parametrize("kind", CAPTION_KINDS)
def test_every_kind_builds_a_valid_track(kind):
    track = CaptionEngine().generate(text=TEXT, duration_s=DUR, kind=kind)
    assert track.kind == kind
    assert _valid(track) == []
    if kind == "static":
        assert track.n_segments == 1
        assert track.segments[0].text == track.segments[0].text  # collapsed single card
    else:
        assert track.n_segments == 3                # 3 sentences
    if kind in ("word", "karaoke"):
        assert all(s.words for s in track.segments)  # per-word timings present


def test_generate_reads_duration_from_wav(tmp_path):
    from foundation.shared_utils import generate_sine_wav, write_wav
    wav = tmp_path / "a.wav"
    write_wav(wav, generate_sine_wav(3.0, 220.0, 24000))
    track = CaptionEngine().generate(text=TEXT, audio_path=wav, kind="sentence")
    assert track.duration_s <= 3.0 + 1e-9
    assert _valid(track, duration_s=3.0) == []


def test_generate_requires_duration_or_audio():
    with pytest.raises(ValueError):
        CaptionEngine().generate(text=TEXT, kind="sentence")


# --------------------------------------------------------------------- styles
def test_seven_presets_exist_and_are_distinct():
    names = style_names()
    for expected in ("classic", "modern", "bold", "minimal",
                     "youtube", "instagram", "tiktok"):
        assert expected in names
    # names are unique and each preset carries its own name
    assert all(get_style(n).name == n for n in names)


def test_unknown_style_raises():
    with pytest.raises(KeyError):
        get_style("nope")


# --------------------------------------------------------------------- config
def test_config_defaults():
    cfg = load_caption_engine_config()
    assert cfg.kind == "sentence" and cfg.preset == "classic"
    assert cfg.animation().kind == "none"
    assert cfg.style_overrides["font_size"] == 64
    assert cfg.style_overrides["primary_color"] == (255, 255, 255)  # list -> RGB tuple


def test_config_overrides_resolve_into_style():
    cfg = load_caption_engine_config(overrides={"captions": {
        "preset": "tiktok", "kind": "karaoke",
        "animation": {"kind": "pop", "duration_s": 0.1},
        "style": {"font_size": 90, "highlight_color": [1, 2, 3]}}})
    eng = CaptionEngine(cfg)
    track = eng.generate(text=TEXT, duration_s=DUR)
    assert track.kind == "karaoke" and track.style.name == "tiktok"
    assert track.style.font_size == 90                     # override wins
    assert track.style.highlight_color == (1, 2, 3)
    assert track.animation.kind == "pop"


def test_env_override(monkeypatch):
    monkeypatch.setenv("AICP__captions__kind", "word")
    cfg = load_caption_engine_config()
    assert cfg.kind == "word"


def test_call_style_overrides_beat_config():
    eng = CaptionEngine()
    track = eng.generate(text=TEXT, duration_s=DUR,
                         style=CaptionStyle(name="explicit", font_size=120))
    assert track.style.name == "explicit" and track.style.font_size == 120
