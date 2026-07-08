"""Branding Engine facade / themes / builder / config tests (Phase C5).

Fully hermetic and deterministic: no renderer, no ffmpeg, no models. Every
generated track is checked against the Timeline validator so the engine can
never emit an unrenderable branding track.
"""
from __future__ import annotations

import pytest

from reel_engine.interfaces.types import Scene, Theme, Timeline
from reel_engine.timeline.validate import validate_timeline

from branding_engine import (
    BrandingEngine,
    load_branding_engine_config,
    theme_names,
)
from branding_engine.themes import all_themes, get_theme
from branding_engine.timeline import build_branding_track, initials

DUR = 12.0


def _valid(track, duration_s=DUR):
    tl = Timeline(scenes=(Scene.simple(0, (0, 0, 255), "x", duration_s=duration_s),),
                  branding=track)
    return validate_timeline(tl)


# --------------------------------------------------------------------- themes
def test_ten_themes_exist_and_are_distinct():
    names = theme_names()
    for expected in ("classic", "minimal", "corporate", "modern", "real_estate",
                     "finance", "education", "medical", "dark", "light"):
        assert expected in names
    assert len(names) == 10
    assert all(get_theme(n).name == n for n in names)
    # themes carry visibly different primary colours
    assert len({t.primary_color for t in all_themes()}) >= 8


def test_unknown_theme_raises():
    with pytest.raises(KeyError):
        get_theme("nope")


# ------------------------------------------------------------------- builder
def test_initials():
    assert initials("AI Creator Platform") == "ACP"
    assert initials("finance daily") == "FD"
    assert initials("") == ""


def test_generate_every_theme_is_valid():
    for name in theme_names():
        track = BrandingEngine().generate(reel_duration_s=DUR, theme=name,
                                          creator="Jane Doe", channel="My Channel")
        assert track.theme.name == name
        assert _valid(track) == []
        assert track.intro and track.outro and track.logo and track.watermark
        assert track.lower_thirds and track.lower_thirds[0].title == "Jane Doe"


def test_lower_third_window_is_clamped_to_reel():
    # start 1.0 + duration 3.0 would overrun a 2s reel; must be clamped.
    # (intro/outro off so the short reel is purely about the lower-third window.)
    cfg = load_branding_engine_config(overrides={"branding": {
        "components": {"intro": False, "outro": False}}})
    track = BrandingEngine(cfg).generate(reel_duration_s=2.0, theme="classic",
                                         creator="X")
    lt = track.lower_thirds[0]
    assert lt.end_s <= 2.0 + 1e-9 and lt.start_s < lt.end_s
    assert _valid(track, duration_s=2.0) == []


def test_logo_falls_back_to_initials_badge_without_image():
    track = BrandingEngine().generate(reel_duration_s=DUR, channel="Finance Daily")
    assert track.logo.source is None
    assert track.logo.text == "FD"


# --------------------------------------------------------------------- config
def test_config_defaults():
    cfg = load_branding_engine_config()
    assert cfg.theme == "classic"
    assert cfg.component_enabled("intro") and cfg.component_enabled("watermark")
    assert cfg.lower_third["start_s"] == 1.0


def test_config_overrides_resolve_into_theme_and_components():
    cfg = load_branding_engine_config(overrides={"branding": {
        "theme": "finance", "creator": "Ada L", "channel": "FinTips",
        "primary_color": [1, 2, 3], "watermark_opacity": 0.9,
        "components": {"watermark": False, "outro": False}}})
    eng = BrandingEngine(cfg)
    track = eng.generate(reel_duration_s=DUR)
    assert track.theme.name == "finance"
    assert track.theme.primary_color == (1, 2, 3)        # override wins
    assert track.theme.watermark_opacity == 0.9
    assert track.watermark is None and track.outro is None   # components off
    assert track.lower_thirds[0].title == "Ada L"


def test_env_override(monkeypatch):
    monkeypatch.setenv("AICP__branding__theme", "dark")
    cfg = load_branding_engine_config()
    assert cfg.theme == "dark"


def test_call_theme_object_bypasses_preset():
    eng = BrandingEngine()
    track = eng.generate(reel_duration_s=DUR, theme=Theme(name="explicit",
                                                          primary_color=(9, 9, 9)))
    assert track.theme.name == "explicit" and track.theme.primary_color == (9, 9, 9)


def test_generate_respects_component_toggles_via_call_config():
    cfg = load_branding_engine_config(overrides={"branding": {
        "components": {"intro": False, "logo": False}}})
    track = BrandingEngine(cfg).generate(reel_duration_s=DUR, creator="X", channel="Y")
    assert track.intro is None and track.logo is None
    assert track.outro is not None and track.lower_thirds
