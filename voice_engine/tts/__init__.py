"""Production synthesis service layer.

Configuration schema, output caching, and use-case routing consumed by
:class:`voice_engine.VoiceEngine`. Engines are selected by the Phase A1.5
benchmark results via ``defaults.yaml``; switching models is a config edit.
"""

from voice_engine.tts.config import (
    CacheConfig,
    EmotionConfig,
    EngineDefaults,
    ExportConfig,
    ProfileStoreConfig,
    PronunciationConfig,
    StreamingConfig,
    VoiceEngineConfig,
    load_voice_engine_config,
)
from voice_engine.tts.cache import SynthesisCacheManager
from voice_engine.tts.router import EngineRouter

__all__ = [
    "CacheConfig",
    "EmotionConfig",
    "EngineDefaults",
    "EngineRouter",
    "ExportConfig",
    "ProfileStoreConfig",
    "PronunciationConfig",
    "StreamingConfig",
    "SynthesisCacheManager",
    "VoiceEngineConfig",
    "load_voice_engine_config",
]
