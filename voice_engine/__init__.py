"""Voice Engine: voice cloning, TTS, and streaming speech for the platform.

Phase A1 built the research infrastructure (interfaces, adapters, datasets,
evaluation, benchmark, reporting); Phase A2 adds the production facade on
top of the same interfaces and adapters. Consumers (reel engine, avatar
engine, real-estate voice AI, benchmark) import :class:`VoiceEngine` and
program against :mod:`voice_engine.interfaces` types only::

    from voice_engine import VoiceEngine

    voice = VoiceEngine()
    result = voice.generate("Welcome to Capital Greens!", language="en")
"""

from voice_engine.engine import VoiceEngine
from voice_engine.interfaces import (
    AudioChunk,
    EngineCapabilities,
    StreamingSupport,
    SynthesisRequest,
    SynthesisResult,
    VoiceProfile,
)

__version__ = "0.2.0"

__all__ = [
    "AudioChunk",
    "EngineCapabilities",
    "StreamingSupport",
    "SynthesisRequest",
    "SynthesisResult",
    "VoiceEngine",
    "VoiceProfile",
]
