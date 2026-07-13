"""Local-folder provider: the creator's own exported media on disk."""
from __future__ import annotations

from typing import Iterator

from ..config import MEDIA_EXTS, Paths
from ..models import MediaItem, Platform
from .base import MediaProvider


class LocalFolderProvider(MediaProvider):
    """Discovers media in ``raw/instagram`` and ``raw/youtube``.

    Files are yielded in sorted order for deterministic runs. Nested folders are
    supported. Only recognised media extensions are returned.
    """

    def __init__(self, paths: Paths):
        self.paths = paths

    def discover(self) -> Iterator[MediaItem]:
        for platform, folder in ((Platform.INSTAGRAM, self.paths.raw_instagram),
                                 (Platform.YOUTUBE, self.paths.raw_youtube)):
            if not folder.exists():
                continue
            for p in sorted(folder.rglob("*"), key=lambda x: x.as_posix()):
                if p.is_file() and p.suffix.lower() in MEDIA_EXTS:
                    rel = f"{platform.value}/{p.relative_to(folder).as_posix()}"
                    yield MediaItem(path=str(p), filename=p.name,
                                    platform=platform, source=rel)
