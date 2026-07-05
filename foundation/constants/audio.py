"""Audio constants shared by all engines."""
from __future__ import annotations

from enum import Enum

#: Default synthesis sample rate for content creation output.
DEFAULT_SAMPLE_RATE: int = 24_000

#: Telephony (phone-call voice AI) sample rate.
TELEPHONY_SAMPLE_RATE: int = 8_000

#: Wideband conversational AI sample rate (e.g. WebRTC / Pipecat pipelines).
CONVERSATIONAL_SAMPLE_RATE: int = 16_000


class AudioFormat(str, Enum):
    WAV = "wav"
    MP3 = "mp3"
    FLAC = "flac"
    OGG = "ogg"
    PCM_S16LE = "pcm_s16le"  # raw stream chunks
