"""Deterministic configuration + path layout for media acquisition.

Per the phase spec, the media database (media.*) and the voice dataset
(dataset.*) are co-located under ``tanshi/voice/metadata`` so all metadata lives
in one place; downloaded video files live under ``tanshi/media/{youtube,instagram}``.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

YOUTUBE_CHANNEL = "https://www.youtube.com/@realestatewithtanshi"
INSTAGRAM_PROFILE = "realestatewithtanshi"


@dataclass(frozen=True)
class Paths:
    root: Path                       # production_assets/tanshi

    @property
    def media(self) -> Path: return self.root / "media"
    @property
    def media_youtube(self) -> Path: return self.media / "youtube"
    @property
    def media_instagram(self) -> Path: return self.media / "instagram"
    @property
    def voice(self) -> Path: return self.root / "voice"
    @property
    def voice_raw(self) -> Path: return self.voice / "raw"
    @property
    def metadata(self) -> Path: return self.voice / "metadata"   # media.* + dataset.*
    @property
    def log_file(self) -> Path: return self.media / "download.log"

    def ensure(self) -> "Paths":
        for p in (self.media_youtube, self.media_instagram, self.metadata):
            p.mkdir(parents=True, exist_ok=True)
        return self

    @classmethod
    def for_creator(cls, base: Path, creator: str = "tanshi") -> "Paths":
        return cls(root=Path(base) / creator)


@dataclass(frozen=True)
class Config:
    youtube_channel: str = YOUTUBE_CHANNEL
    instagram_profile: str = INSTAGRAM_PROFILE
    retries: int = 3                 # attempts per item
    retry_backoff_s: float = 2.0     # base backoff between attempts
    limit: int | None = None         # cap items per provider (validate-first workflow)
    youtube_format: str = "bv*+ba/b" # yt-dlp: best video+audio, else best
    merge_format: str = "mp4"

    def base_dir(self) -> Path:
        env = os.environ.get("MEDIA_ACQ_BASE") or os.environ.get("VOICE_DATASET_BASE")
        return Path(env) if env else Path("production_assets")
