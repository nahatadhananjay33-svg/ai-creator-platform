"""Public Voice Engine interfaces.

Everything outside the Voice Engine (benchmark, avatar engine, reel engine,
real-estate voice AI) programs against these types only — never against a
concrete adapter.
"""

from voice_engine.interfaces.types import (
    EngineCapabilities,
    StreamingSupport,
    SynthesisRequest,
    SynthesisResult,
    AudioChunk,
    VoiceProfile,
)
from voice_engine.interfaces.tts_engine import TTSEngine
from voice_engine.interfaces.voice_cloner import VoiceCloner
from voice_engine.interfaces.streaming import StreamingTTSEngine

__all__ = [
    "EngineCapabilities",
    "StreamingSupport",
    "SynthesisRequest",
    "SynthesisResult",
    "AudioChunk",
    "VoiceProfile",
    "TTSEngine",
    "VoiceCloner",
    "StreamingTTSEngine",
]
