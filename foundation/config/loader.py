"""Configuration-driven design support.

Every engine reads behavior from YAML files rather than hardcoding values.
The loader supports:

- YAML and JSON files
- layered configs (defaults <- environment file <- explicit overrides)
- environment-variable overrides using ``AICP__section__key=value``
- dataclass binding for type-safe access
"""
from __future__ import annotations

import dataclasses
import json
import os
from pathlib import Path
from typing import Any, Type, TypeVar

import yaml

from foundation.exceptions import ConfigError

T = TypeVar("T")

ENV_PREFIX = "AICP"
ENV_SEPARATOR = "__"


def load_yaml(path: Path | str) -> dict[str, Any]:
    """Load a YAML (or JSON) mapping from disk."""
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}", path=str(path))
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text) if path.suffix == ".json" else yaml.safe_load(text)
    except (yaml.YAMLError, json.JSONDecodeError) as exc:
        raise ConfigError(f"Failed to parse config: {path}", path=str(path)) from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ConfigError(f"Config root must be a mapping: {path}", path=str(path))
    return data


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge ``override`` into ``base`` (returns a new dict)."""
    merged = dict(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _coerce(raw: str) -> Any:
    """Best-effort scalar coercion for env-var overrides."""
    lowered = raw.lower()
    if lowered in ("true", "false"):
        return lowered == "true"
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw


def env_overrides(environ: dict[str, str] | None = None) -> dict[str, Any]:
    """Extract nested overrides from ``AICP__a__b=value`` env vars."""
    environ = dict(os.environ) if environ is None else environ
    result: dict[str, Any] = {}
    prefix = ENV_PREFIX + ENV_SEPARATOR
    for key, raw in environ.items():
        if not key.startswith(prefix):
            continue
        parts = [p.lower() for p in key[len(prefix):].split(ENV_SEPARATOR) if p]
        if not parts:
            continue
        node = result
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = _coerce(raw)
    return result


class ConfigLoader:
    """Layered configuration loader with dataclass binding.

    Example::

        loader = ConfigLoader(defaults_path=cfg_dir / "defaults.yaml")
        cfg = loader.load(overrides={"benchmark": {"repetitions": 5}})
        bench_cfg = loader.bind(cfg["benchmark"], BenchmarkConfig)
    """

    def __init__(
        self,
        defaults_path: Path | str | None = None,
        environment_path: Path | str | None = None,
        apply_env_vars: bool = True,
    ) -> None:
        self._defaults_path = Path(defaults_path) if defaults_path else None
        self._environment_path = Path(environment_path) if environment_path else None
        self._apply_env_vars = apply_env_vars

    def load(self, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
        config: dict[str, Any] = {}
        if self._defaults_path is not None:
            config = deep_merge(config, load_yaml(self._defaults_path))
        if self._environment_path is not None and self._environment_path.exists():
            config = deep_merge(config, load_yaml(self._environment_path))
        if self._apply_env_vars:
            config = deep_merge(config, env_overrides())
        if overrides:
            config = deep_merge(config, overrides)
        return config

    @staticmethod
    def bind(section: dict[str, Any], schema: Type[T]) -> T:
        """Bind a config mapping onto a dataclass, rejecting unknown keys."""
        if not dataclasses.is_dataclass(schema):
            raise ConfigError(f"Schema must be a dataclass: {schema!r}")
        field_names = {f.name for f in dataclasses.fields(schema)}
        unknown = set(section) - field_names
        if unknown:
            raise ConfigError(
                f"Unknown config keys for {schema.__name__}: {sorted(unknown)}",
                schema=schema.__name__,
            )
        try:
            return schema(**section)  # type: ignore[return-value]
        except TypeError as exc:
            raise ConfigError(
                f"Invalid config for {schema.__name__}: {exc}", schema=schema.__name__
            ) from exc
