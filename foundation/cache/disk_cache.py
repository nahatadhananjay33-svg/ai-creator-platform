"""Simple, robust JSON-indexed disk cache.

Used for: downloaded model weights bookkeeping, reference-audio embeddings,
benchmark intermediates. Values are JSON-serializable metadata; large binary
artifacts are stored as files and referenced by path.

Not a distributed cache — single-process, single-machine by design. Future
phases can swap in a different backend behind the same interface.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from foundation.constants.paths import CACHE_DIR, ensure_dir
from foundation.exceptions import CacheError
from foundation.shared_utils.hashing import short_hash
from foundation.shared_utils.timing import utc_now_iso


class DiskCache:
    """Namespaced key -> (JSON metadata, optional artifact file) cache."""

    def __init__(self, namespace: str, root: Path | None = None) -> None:
        if not namespace or "/" in namespace or "\\" in namespace:
            raise CacheError(f"Invalid cache namespace: {namespace!r}")
        self.namespace = namespace
        self.root = ensure_dir((root or CACHE_DIR) / namespace)

    def _entry_dir(self, key: str) -> Path:
        return self.root / short_hash(key, 16)

    def has(self, key: str) -> bool:
        return (self._entry_dir(key) / "meta.json").exists()

    def get(self, key: str) -> dict[str, Any] | None:
        meta_path = self._entry_dir(key) / "meta.json"
        if not meta_path.exists():
            return None
        try:
            entry = json.loads(meta_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise CacheError(f"Corrupt cache entry for key {key!r}", key=key) from exc
        return entry.get("value")

    def put(self, key: str, value: dict[str, Any]) -> None:
        entry_dir = ensure_dir(self._entry_dir(key))
        payload = {"key": key, "stored_at": utc_now_iso(), "value": value}
        tmp = entry_dir / "meta.json.tmp"
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(entry_dir / "meta.json")

    def artifact_path(self, key: str, filename: str) -> Path:
        """Path where a binary artifact for ``key`` should be stored."""
        return ensure_dir(self._entry_dir(key)) / filename

    def evict(self, key: str) -> bool:
        entry_dir = self._entry_dir(key)
        if entry_dir.exists():
            shutil.rmtree(entry_dir)
            return True
        return False

    def clear(self) -> None:
        if self.root.exists():
            shutil.rmtree(self.root)
        ensure_dir(self.root)
