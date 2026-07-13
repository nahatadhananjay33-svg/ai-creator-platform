"""Typed models and enums for media acquisition."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum


class Platform(str, Enum):
    YOUTUBE = "youtube"
    INSTAGRAM = "instagram"


class Status(str, Enum):
    DISCOVERED = "discovered"
    DOWNLOADED = "downloaded"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass(frozen=True)
class MediaItem:
    """A discovered, authorized video before download (metadata only)."""
    platform: Platform
    item_id: str             # YouTube video_id or Instagram shortcode
    url: str
    title: str = ""
    publish_date: str = ""   # YYYY-MM-DD if known
    duration: float = 0.0    # seconds if known pre-download
    kind: str = ""           # long_form | short | reel | video_post
    extra: dict = field(default_factory=dict)


@dataclass
class DownloadResult:
    """What a provider returns after fetching a file."""
    filename: str
    checksum: str
    resolution: str = ""
    fps: float = 0.0
    codec: str = ""
    duration: float = 0.0
    thumbnail: str = ""
    description: str = ""


@dataclass
class MediaRecord:
    """One row of the media database."""
    id: int
    platform: str
    url: str
    title: str
    publish_date: str
    duration: float
    resolution: str
    fps: float
    checksum: str
    filename: str
    status: str
    download_time: str        # ISO-8601 UTC
    # provider extras (kept for auditability)
    item_id: str = ""
    codec: str = ""
    kind: str = ""
    thumbnail: str = ""
    description: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


MEDIA_COLUMNS = [
    "id", "platform", "url", "title", "publish_date", "duration", "resolution",
    "fps", "checksum", "filename", "status", "download_time",
    "item_id", "codec", "kind", "thumbnail", "description",
]
