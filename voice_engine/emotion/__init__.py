"""Emotion and style control normalized behind one enum-based API.

Per-engine controls (Chatterbox exaggeration, CosyVoice instruct, Parler
descriptions) are strategy mappings selected by configuration.
"""

from voice_engine.emotion.manager import (
    DEFAULT_ENGINE_STRATEGIES,
    STRATEGIES,
    Emotion,
    EmotionManager,
    EmotionSpec,
    resolve_emotion,
)

__all__ = [
    "DEFAULT_ENGINE_STRATEGIES",
    "STRATEGIES",
    "Emotion",
    "EmotionManager",
    "EmotionSpec",
    "resolve_emotion",
]
