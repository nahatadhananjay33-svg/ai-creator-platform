"""Typed data structures and enums for the voice dataset builder.

All enums are ``str``-valued so they serialize cleanly to SQLite/CSV/XLSX and
compare deterministically.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional


class Platform(str, Enum):
    INSTAGRAM = "instagram"
    YOUTUBE = "youtube"
    UNKNOWN = "unknown"


class Classification(str, Enum):
    TALKING_HEAD = "talking_head"
    INTERVIEW = "interview"
    PODCAST = "podcast"
    LONG_FORM = "long_form"
    SHORT_REEL = "short_reel"
    CAROUSEL_VIDEO = "carousel_video"
    MEME = "meme"
    MUSIC_ONLY = "music_only"
    UNKNOWN = "unknown"


class Quality(str, Enum):
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"

    @property
    def rank(self) -> int:
        return {"poor": 0, "fair": 1, "good": 2, "excellent": 3}[self.value]


class Decision(str, Enum):
    ACCEPT = "accept"
    REJECT = "reject"


@dataclass(frozen=True)
class MediaItem:
    """A single source file discovered by a provider."""
    path: str            # absolute path to the source media on disk
    filename: str        # basename
    platform: Platform
    source: str          # provider-relative identifier (e.g. "instagram/clip.mp4")


@dataclass
class AudioMeta:
    """Objective, measured properties of the extracted audio (Step 3)."""
    duration: float          # seconds
    sample_rate: int         # Hz
    channels: int
    bitrate: int             # bits/second (PCM-equivalent for WAV)
    silence_pct: float       # fraction 0..1 of frames below the silence floor
    speech_duration: float   # seconds estimated as speech
    loudness_dbfs: float     # integrated RMS loudness in dBFS (<=0)


@dataclass
class Detection:
    """Content signals derived from the audio (Step 5). Heuristic, deterministic."""
    has_speech: bool
    multi_speaker: bool
    has_music: bool
    noise_floor_dbfs: float
    snr_db: float
    noise_estimate: str      # "low" | "moderate" | "high"


@dataclass
class Record:
    """One row of the dataset — the persisted result for a media item."""
    id: int
    platform: str
    source: str
    filename: str
    duration: float
    speech_duration: float
    classification: str
    quality: str
    accepted: bool
    reason: str
    audio_path: str
    # extra measured fields (kept in sqlite/csv/xlsx for auditability)
    sample_rate: int = 0
    channels: int = 0
    bitrate: int = 0
    silence_pct: float = 0.0
    loudness_dbfs: float = 0.0
    snr_db: float = 0.0
    has_speech: bool = False
    multi_speaker: bool = False
    has_music: bool = False
    noise_estimate: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


# Column order used consistently across SQLite / CSV / XLSX.
RECORD_COLUMNS = [
    "id", "platform", "source", "filename", "duration", "speech_duration",
    "classification", "quality", "accepted", "reason", "audio_path",
    "sample_rate", "channels", "bitrate", "silence_pct", "loudness_dbfs",
    "snr_db", "has_speech", "multi_speaker", "has_music", "noise_estimate",
]
