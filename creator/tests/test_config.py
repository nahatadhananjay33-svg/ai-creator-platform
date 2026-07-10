"""Config loading: defaults, --config layering, env vars, CLI overrides."""
from __future__ import annotations

from creator.config import CONFIG_PATH, CreatorConfig, load_creator_config


def test_defaults_load_from_packaged_yaml():
    cfg = load_creator_config()
    assert isinstance(cfg, CreatorConfig)
    assert cfg.prompt                       # the packaged default is non-empty
    assert cfg.renderer == "mock"           # hermetic by default
    assert cfg.profiles == ("reel_9x16", "square_1x1")
    assert cfg.quality_gate is True


def test_packaged_config_file_exists():
    assert CONFIG_PATH.exists()


def test_explicit_overrides_win_over_defaults():
    cfg = load_creator_config(overrides={"generation": {"renderer": "ffmpeg",
                                                        "template": "education"}})
    assert cfg.renderer == "ffmpeg"
    assert cfg.template == "education"
    # untouched keys keep their defaults
    assert cfg.profiles == ("reel_9x16", "square_1x1")


def test_env_vars_override_defaults(monkeypatch):
    monkeypatch.setenv("AICP__generation__renderer", "ffmpeg")
    monkeypatch.setenv("AICP__quality__gate", "false")
    cfg = load_creator_config()
    assert cfg.renderer == "ffmpeg"
    assert cfg.quality_gate is False


def test_cli_override_beats_env_var(monkeypatch):
    monkeypatch.setenv("AICP__generation__template", "finance")
    cfg = load_creator_config(overrides={"generation": {"template": "medical"}})
    assert cfg.template == "medical"        # explicit override is highest priority


def test_user_config_file_layers_on_top(tmp_path):
    user = tmp_path / "mine.yaml"
    user.write_text("generation:\n  template: news\n  prompt: hi\n", encoding="utf-8")
    cfg = load_creator_config(config_path=user)
    assert cfg.template == "news"
    assert cfg.prompt == "hi"
    assert cfg.renderer == "mock"           # still from packaged defaults


def test_to_dict_roundtrips_fields():
    cfg = load_creator_config()
    d = cfg.to_dict()
    assert d["renderer"] == cfg.renderer
    assert d["profiles"] == list(cfg.profiles)
