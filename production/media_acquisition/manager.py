"""Per-provider orchestration and stats."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .config import Config
from .download import DownloadEngine
from .providers.base import MediaProvider


@dataclass
class ProviderStats:
    platform: str
    available: bool = True
    discovered: int = 0
    downloaded: int = 0
    skipped: int = 0
    failed: int = 0
    hours: float = 0.0
    note: str = ""


def run_provider(provider: MediaProvider, dest_dir: Path, engine: DownloadEngine,
                 cfg: Config, limit: Optional[int] = None) -> ProviderStats:
    stats = ProviderStats(platform=provider.platform.value)
    if not provider.is_available():
        stats.available = False
        stats.note = "provider unavailable (tool or credentials missing) — skipped"
        return stats

    effective_limit = limit if limit is not None else cfg.limit
    items = list(provider.list_items(limit=effective_limit))
    stats.discovered = len(items)
    for item in items:
        result = engine.process(provider, item, dest_dir)
        setattr(stats, result, getattr(stats, result) + 1)
    stats.hours = engine.db.downloaded_hours(provider.platform.value)
    return stats
