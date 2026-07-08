"""Reels Engine config tests (Phase C2). Hermetic."""
from __future__ import annotations

from reel_engine.config import ReelEngineConfig, load_reel_engine_config


def test_defaults_load_and_bind():
    cfg = load_reel_engine_config(apply_env_vars=False)
    assert cfg.render.width == 1080 and cfg.render.height == 1920
    assert cfg.render.fps == 30
    assert cfg.render.codec == "libx264" and cfg.render.pix_fmt == "yuv420p"
    assert cfg.render.renderer == "ffmpeg"
    assert cfg.export.profiles == ["reel_9x16", "square_1x1", "landscape_16x9"]


def test_overrides_win():
    cfg = load_reel_engine_config(
        overrides={"render": {"renderer": "mock", "fps": 24}},
        apply_env_vars=False,
    )
    assert cfg.render.renderer == "mock"
    assert cfg.render.fps == 24
    # untouched keys keep their defaults
    assert cfg.render.width == 1080


def test_config_is_frozen():
    cfg = load_reel_engine_config(apply_env_vars=False)
    assert isinstance(cfg, ReelEngineConfig)
    import dataclasses
    import pytest
    with pytest.raises(dataclasses.FrozenInstanceError):
        cfg.output_dir = "/tmp/x"  # type: ignore
