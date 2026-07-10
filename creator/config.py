"""The single Version 1.0 user configuration (Phase C19).

One documented file — :file:`creator/config.yaml` — holds every option a
single-user creator touches. This module loads it through the platform's
standard layered :class:`~foundation.config.ConfigLoader` (defaults <- optional
user ``--config`` file <- ``AICP__*`` env vars <- explicit overrides) and binds
it to a flat, typed :class:`CreatorConfig` the ``creator.run`` command consumes.

It deliberately surfaces only the handful of knobs that matter for producing one
reel; the per-engine ``defaults.yaml`` files remain the advanced layer beneath.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from foundation.config import ConfigLoader

#: The packaged single-user config file.
CONFIG_PATH: Path = Path(__file__).resolve().parent / "config.yaml"


@dataclass(frozen=True)
class CreatorConfig:
    """Flat, typed view of :file:`creator/config.yaml`."""

    prompt: str
    template: str
    renderer: str
    profiles: tuple[str, ...]
    language: str
    creator: str
    channel: str
    quality_gate: bool
    workspace_root: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt": self.prompt,
            "template": self.template,
            "renderer": self.renderer,
            "profiles": list(self.profiles),
            "language": self.language,
            "creator": self.creator,
            "channel": self.channel,
            "quality_gate": self.quality_gate,
            "workspace_root": self.workspace_root,
        }


def load_creator_config(
    config_path: Path | str | None = None,
    overrides: dict[str, Any] | None = None,
    apply_env_vars: bool = True,
) -> CreatorConfig:
    """Load the layered Version 1.0 configuration into a :class:`CreatorConfig`.

    ``config_path`` is an optional user file (``--config``) layered on top of the
    packaged defaults. ``overrides`` is a nested mapping (same shape as the YAML)
    applied last — the command uses it to fold in explicit CLI flags.
    """
    loader = ConfigLoader(
        defaults_path=CONFIG_PATH,
        environment_path=config_path,
        apply_env_vars=apply_env_vars,
    )
    data = loader.load(overrides)

    gen = data.get("generation", {}) or {}
    brand = data.get("branding", {}) or {}
    quality = data.get("quality", {}) or {}
    paths = data.get("paths", {}) or {}

    profiles = gen.get("profiles") or ["reel_9x16"]
    return CreatorConfig(
        prompt=str(gen.get("prompt", "")),
        template=str(gen.get("template", "general")),
        renderer=str(gen.get("renderer", "mock")),
        profiles=tuple(str(p) for p in profiles),
        language=str(gen.get("language", "en")),
        creator=str(brand.get("creator", "")),
        channel=str(brand.get("channel", "")),
        quality_gate=bool(quality.get("gate", True)),
        workspace_root=str(paths.get("root", "") or ""),
    )
