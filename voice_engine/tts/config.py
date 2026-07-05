"""Voice Engine configuration schema.

Layered on :class:`foundation.config.ConfigLoader`: packaged defaults
(``defaults.yaml``) <- optional user config file <- ``AICP__section__key``
environment variables <- explicit overrides. Switching models is a
configuration change (``engine.default_model`` / ``routing``), never a code
change.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from foundation.config import ConfigLoader
from foundation.exceptions import ConfigError

DEFAULTS_PATH: Path = Path(__file__).resolve().parent / "defaults.yaml"


@dataclass(frozen=True)
class EngineDefaults:
    """Which adapter runs by default and how adapters are constructed."""

    default_model: str = "kokoro"
    device: str = "auto"
    #: Per-model adapter config dicts, keyed by adapter id.
    models: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass(frozen=True)
class CacheConfig:
    enabled: bool = True
    namespace: str = "voice_synthesis"
    #: null -> the platform cache root (``foundation/cache/data``).
    directory: str | None = None


@dataclass(frozen=True)
class ProfileStoreConfig:
    #: null -> ``voice_engine/voices/profiles`` (gitignored).
    directory: str | None = None
    require_consent: bool = True


@dataclass(frozen=True)
class PronunciationConfig:
    #: Lexicon YAML paths merged in order (later files win).
    lexicons: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class EmotionConfig:
    #: Per-engine strategy overrides (see ``voice_engine.emotion``).
    strategies: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class StreamingConfig:
    chunk_ms: int = 200
    #: Target PCM sample rate for chunks; None keeps the engine-native rate.
    sample_rate: int | None = None
    #: Fallback (non-native) streaming: max characters per synthesized chunk.
    max_sentence_chars: int = 300


@dataclass(frozen=True)
class ExportConfig:
    format: str = "wav"
    #: Peak-normalization target in dBFS; None disables normalization.
    peak_dbfs: float | None = -1.0


@dataclass(frozen=True)
class VoiceEngineConfig:
    """Complete, validated Voice Engine configuration."""

    engine: EngineDefaults = field(default_factory=EngineDefaults)
    #: Use-case -> adapter-id preference chain (first available wins).
    routing: dict[str, list[str]] = field(default_factory=dict)
    cache: CacheConfig = field(default_factory=CacheConfig)
    profiles: ProfileStoreConfig = field(default_factory=ProfileStoreConfig)
    pronunciation: PronunciationConfig = field(default_factory=PronunciationConfig)
    emotion: EmotionConfig = field(default_factory=EmotionConfig)
    streaming: StreamingConfig = field(default_factory=StreamingConfig)
    export: ExportConfig = field(default_factory=ExportConfig)

    @classmethod
    def from_mapping(cls, mapping: dict[str, Any]) -> "VoiceEngineConfig":
        """Bind a raw (already merged) config mapping onto typed sections."""
        routing = mapping.get("routing", {})
        if not isinstance(routing, dict) or not all(
            isinstance(chain, list) for chain in routing.values()
        ):
            raise ConfigError("routing must map use-case names to adapter-id lists")
        return cls(
            engine=ConfigLoader.bind(mapping.get("engine", {}), EngineDefaults),
            routing={use_case: list(chain) for use_case, chain in routing.items()},
            cache=ConfigLoader.bind(mapping.get("cache", {}), CacheConfig),
            profiles=ConfigLoader.bind(mapping.get("profiles", {}), ProfileStoreConfig),
            pronunciation=ConfigLoader.bind(
                mapping.get("pronunciation", {}), PronunciationConfig
            ),
            emotion=ConfigLoader.bind(mapping.get("emotion", {}), EmotionConfig),
            streaming=ConfigLoader.bind(mapping.get("streaming", {}), StreamingConfig),
            export=ConfigLoader.bind(mapping.get("export", {}), ExportConfig),
        )


def load_voice_engine_config(
    config_path: Path | str | None = None,
    overrides: dict[str, Any] | None = None,
    apply_env_vars: bool = True,
) -> VoiceEngineConfig:
    """Load the layered Voice Engine configuration.

    Args:
        config_path: Optional environment-specific YAML/JSON overlaying the
            packaged defaults.
        overrides: Highest-precedence explicit overrides (nested mapping).
        apply_env_vars: Honor ``AICP__section__key`` environment variables.
    """
    loader = ConfigLoader(
        defaults_path=DEFAULTS_PATH,
        environment_path=config_path,
        apply_env_vars=apply_env_vars,
    )
    return VoiceEngineConfig.from_mapping(loader.load(overrides))
