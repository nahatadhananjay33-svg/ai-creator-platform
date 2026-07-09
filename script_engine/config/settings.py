"""AI Prompt & Storyboard Engine configuration (Phase C10).

Layered on :class:`foundation.config.ConfigLoader` like every engine: packaged
``defaults.yaml`` <- user file <- ``AICP__script__*`` env <- overrides. Selects
the provider and the generation knobs (temperature, scene bounds, target
duration, language, style, template). Provider API keys are NOT configured here —
they come from the environment at call time, so the hermetic path never needs one.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from foundation.config import ConfigLoader

DEFAULTS_PATH: Path = Path(__file__).resolve().parent / "defaults.yaml"


@dataclass(frozen=True)
class ScriptEngineConfig:
    """Complete, validated AI Prompt & Storyboard Engine configuration."""

    provider: str = "mock"               # mock | openai | anthropic | gemini
    model: str = ""                      # empty -> the provider's own default
    temperature: float = 0.7             # sampling (ignored by providers that reject it)
    min_scenes: int = 3
    max_scenes: int = 8
    target_duration_s: float = 40.0
    language: str = "en"
    style: str = "informative"
    template: str = "general"
    max_tokens: int = 4096
    creator: str = ""                    # optional branding hints passed to the Scene Engine
    channel: str = ""

    def __post_init__(self) -> None:
        if self.min_scenes < 1:
            raise ValueError(f"min_scenes must be >= 1, got {self.min_scenes}")
        if self.max_scenes < self.min_scenes:
            raise ValueError(
                f"max_scenes ({self.max_scenes}) must be >= min_scenes ({self.min_scenes})")
        if self.target_duration_s <= 0:
            raise ValueError(f"target_duration_s must be positive, got {self.target_duration_s}")
        if not (0.0 <= self.temperature <= 2.0):
            raise ValueError(f"temperature must be in [0, 2], got {self.temperature}")

    @classmethod
    def from_mapping(cls, mapping: dict[str, Any]) -> "ScriptEngineConfig":
        s = mapping.get("script", {}) or {}
        return cls(
            provider=s.get("provider", "mock"),
            model=s.get("model", ""),
            temperature=s.get("temperature", 0.7),
            min_scenes=s.get("min_scenes", 3),
            max_scenes=s.get("max_scenes", 8),
            target_duration_s=s.get("target_duration_s", 40.0),
            language=s.get("language", "en"),
            style=s.get("style", "informative"),
            template=s.get("template", "general"),
            max_tokens=s.get("max_tokens", 4096),
            creator=s.get("creator", ""),
            channel=s.get("channel", ""),
        )


def load_script_engine_config(
    config_path: Path | str | None = None,
    overrides: dict[str, Any] | None = None,
    apply_env_vars: bool = True,
) -> ScriptEngineConfig:
    """Load the layered AI Prompt & Storyboard Engine configuration."""
    loader = ConfigLoader(
        defaults_path=DEFAULTS_PATH,
        environment_path=config_path,
        apply_env_vars=apply_env_vars,
    )
    return ScriptEngineConfig.from_mapping(loader.load(overrides))
