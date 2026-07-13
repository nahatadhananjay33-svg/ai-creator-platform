"""Provider interface for media acquisition."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable

from ..models import MediaItem


class MediaProvider(ABC):
    """Yields the media items to process, in a deterministic order."""

    @abstractmethod
    def discover(self) -> Iterable[MediaItem]:
        raise NotImplementedError
