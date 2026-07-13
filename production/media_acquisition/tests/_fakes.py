"""In-memory fake provider for hermetic tests (no network, no external tools)."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from production.media_acquisition.models import DownloadResult, MediaItem, Platform
from production.media_acquisition.providers.base import MediaProvider


class FakeProvider(MediaProvider):
    def __init__(self, platform: Platform, items: List[MediaItem],
                 contents: Optional[Dict[str, bytes]] = None,
                 fail_first: Optional[Dict[str, int]] = None,
                 available: bool = True, ext: str = "mp4"):
        self.platform = platform
        self._items = items
        self._contents = contents or {}
        self._fail_first = fail_first or {}   # item_id -> fail this many times, then succeed
        self._attempts: Dict[str, int] = {}
        self._available = available
        self._ext = ext

    def is_available(self) -> bool:
        return self._available

    def list_items(self, limit: Optional[int] = None):
        return self._items[:limit] if limit is not None else list(self._items)

    def fetch(self, item: MediaItem, dest_dir: Path) -> DownloadResult:
        n = self._attempts.get(item.item_id, 0) + 1
        self._attempts[item.item_id] = n
        if n <= self._fail_first.get(item.item_id, 0):
            raise RuntimeError(f"simulated failure {n} for {item.item_id}")
        content = self._contents.get(item.item_id, item.item_id.encode())
        fn = f"{item.item_id}.{self._ext}"
        (Path(dest_dir) / fn).write_bytes(content)
        return DownloadResult(filename=fn, checksum="", resolution="1080p",
                              fps=30.0, codec="h264", duration=item.duration or 10.0)


def make_items(platform: Platform, ids, duration: float = 10.0) -> List[MediaItem]:
    return [MediaItem(platform=platform, item_id=i, url=f"https://example/{i}",
                      title=f"title {i}", publish_date="2026-01-01",
                      duration=duration, kind="long_form") for i in ids]
