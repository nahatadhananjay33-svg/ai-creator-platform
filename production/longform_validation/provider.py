"""Long-form-only YouTube provider.

Composes the existing ``YouTubeProvider`` unchanged: discovery and download are
fully delegated; the only added behaviour is filtering the listing to
``kind == "long_form"`` (the channel's Videos tab), so Shorts — and everything
the inner provider already skips (Instagram, community posts, live/upcoming) —
are never downloaded.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from production.media_acquisition.config import Config
from production.media_acquisition.models import DownloadResult, MediaItem, Platform
from production.media_acquisition.providers.base import MediaProvider
from production.media_acquisition.providers.youtube import YouTubeProvider

LONG_FORM = "long_form"


class LongFormYouTubeProvider(MediaProvider):
    platform = Platform.YOUTUBE

    def __init__(self, cfg: Optional[Config] = None,
                 inner: Optional[MediaProvider] = None):
        self.inner = inner if inner is not None else YouTubeProvider(cfg or Config())

    def is_available(self) -> bool:
        return self.inner.is_available()

    def list_items(self, limit: Optional[int] = None) -> List[MediaItem]:
        # List unbounded, then filter, then cap — otherwise Shorts occupying the
        # first N listing slots would silently shrink the long-form set.
        items = [i for i in self.inner.list_items(limit=None) if i.kind == LONG_FORM]
        return items[:limit] if limit is not None else items

    def fetch(self, item: MediaItem, dest_dir: Path) -> DownloadResult:
        return self.inner.fetch(item, dest_dir)
