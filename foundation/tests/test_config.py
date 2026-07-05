"""Tests for foundation.config."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from foundation.config import ConfigLoader, deep_merge, load_yaml
from foundation.config.loader import env_overrides
from foundation.exceptions import ConfigError


@dataclass
class DummyConfig:
    name: str
    repetitions: int = 3
    enabled: bool = True


def test_load_yaml_and_bind(tmp_path: Path) -> None:
    cfg_file = tmp_path / "cfg.yaml"
    cfg_file.write_text("section:\n  name: bench\n  repetitions: 5\n", encoding="utf-8")
    data = load_yaml(cfg_file)
    bound = ConfigLoader.bind(data["section"], DummyConfig)
    assert bound.name == "bench"
    assert bound.repetitions == 5
    assert bound.enabled is True


def test_missing_file_raises() -> None:
    with pytest.raises(ConfigError):
        load_yaml("does/not/exist.yaml")


def test_bind_rejects_unknown_keys() -> None:
    with pytest.raises(ConfigError, match="Unknown config keys"):
        ConfigLoader.bind({"name": "x", "bogus": 1}, DummyConfig)


def test_deep_merge_nested() -> None:
    base = {"a": {"x": 1, "y": 2}, "b": 1}
    override = {"a": {"y": 3}, "c": 4}
    merged = deep_merge(base, override)
    assert merged == {"a": {"x": 1, "y": 3}, "b": 1, "c": 4}
    assert base["a"]["y"] == 2  # base untouched


def test_env_overrides_parsing() -> None:
    overrides = env_overrides(
        {"AICP__BENCHMARK__REPETITIONS": "7", "AICP__LOGGING__JSON": "true", "OTHER": "x"}
    )
    assert overrides == {"benchmark": {"repetitions": 7}, "logging": {"json": True}}


def test_layered_load(tmp_path: Path) -> None:
    defaults = tmp_path / "defaults.yaml"
    defaults.write_text("a: 1\nb: {c: 2}\n", encoding="utf-8")
    env = tmp_path / "prod.yaml"
    env.write_text("b: {c: 3}\n", encoding="utf-8")
    loader = ConfigLoader(defaults_path=defaults, environment_path=env, apply_env_vars=False)
    cfg = loader.load(overrides={"d": 4})
    assert cfg == {"a": 1, "b": {"c": 3}, "d": 4}
