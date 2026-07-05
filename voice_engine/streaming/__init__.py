"""Real-time streaming synthesis.

Wraps native :class:`StreamingTTSEngine` adapters and sentence-chunks the
rest; converts sample rates for telephony (8 kHz) and conversational
(16 kHz) consumers such as Pipecat.
"""

from voice_engine.streaming.manager import StreamingManager
from voice_engine.streaming.pcm import (
    resample,
    resample_pcm_bytes,
    to_mono,
    wav_to_chunks,
)

__all__ = [
    "StreamingManager",
    "resample",
    "resample_pcm_bytes",
    "to_mono",
    "wav_to_chunks",
]
