"""Provider interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterable, Optional

from ..models import DownloadResult, MediaItem, Platform


class MediaProvider(ABC):
    """Discovers authorized videos and downloads them.

    ``list_items`` applies the platform's skip rules (no live/community/images/
    carousels/stories) and returns only downloadable video items. ``fetch``
    downloads one item at highest quality, resuming any partial file, and returns
    the resulting filename + checksum + technical metadata.
    """
    platform: Platform

    def is_available(self) -> bool:
        """True when the tool + credentials needed to run this provider exist."""
        return True

    @abstractmethod
    def list_items(self, limit: Optional[int] = None) -> Iterable[MediaItem]:
        raise NotImplementedError

    @abstractmethod
    def fetch(self, item: MediaItem, dest_dir: Path) -> DownloadResult:
        raise NotImplementedError
