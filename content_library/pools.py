"""Content pools (Phase C15) — managed folders for the non-project content types.

Besides projects, the library manages shared **content pools**: assets, voices,
avatars, music, brand kits, and exports. Each pool is one folder plus a
``registry.json`` of immutable :class:`PoolItem` metadata. An item may carry a file
(copied into the pool, e.g. an image or a WAV) or be metadata-only (e.g. a brand
kit dict). Listing and search are deterministic — sorted, rule-based, no database.
"""
from __future__ import annotations

import dataclasses
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from foundation.shared_utils.hashing import sha256_file, short_hash
from foundation.shared_utils.text import slugify
from foundation.shared_utils.timing import utc_now_iso

from content_library.store import LibraryStore, read_json, write_json

REGISTRY_NAME = "registry.json"
REGISTRY_SCHEMA_VERSION = 1
_FILES_SUBDIR = "files"


def make_item_id(name: str, kind: str = "") -> str:
    """A deterministic, readable pool-item id."""
    return f"{slugify(name, 40)}-{short_hash(f'{name}|{kind}', 6)}"


@dataclass(frozen=True)
class PoolItem:
    """One immutable entry in a content pool."""

    item_id: str
    name: str
    kind: str = ""                       # pool-specific type hint (image/video/voice/…)
    path: str = ""                       # POSIX path relative to the pool dir ("" = metadata-only)
    tags: tuple[str, ...] = ()
    meta: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = dataclasses.asdict(self)
        d["tags"] = list(self.tags)
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "PoolItem":
        return cls(item_id=d["item_id"], name=d.get("name", ""), kind=d.get("kind", ""),
                   path=d.get("path", ""), tags=tuple(d.get("tags", ())),
                   meta=dict(d.get("meta", {})), created_at=d.get("created_at", ""))


class ContentPool:
    """A managed folder + JSON registry for one content type."""

    def __init__(self, name: str, store: LibraryStore,
                 *, clock: Callable[[], str] = utc_now_iso) -> None:
        self.name = name
        self.dir = store.pool_dir(name)
        self.dir.mkdir(parents=True, exist_ok=True)
        self._clock = clock
        self._items: dict[str, PoolItem] = {}
        self._load()

    # ---- persistence ---------------------------------------------------------
    @property
    def registry_path(self) -> Path:
        return self.dir / REGISTRY_NAME

    def _load(self) -> None:
        if self.registry_path.exists():
            data = read_json(self.registry_path)
            self._items = {i["item_id"]: PoolItem.from_dict(i)
                           for i in data.get("items", [])}

    def _save(self) -> None:
        items = [self._items[k].to_dict() for k in sorted(self._items)]
        write_json(self.registry_path, {"schema_version": REGISTRY_SCHEMA_VERSION,
                                        "pool": self.name, "items": items})

    # ---- mutation ------------------------------------------------------------
    def add(self, name: str, *, source: Path | str | None = None, kind: str = "",
            tags: tuple[str, ...] = (), meta: dict[str, Any] | None = None,
            item_id: str | None = None, copy: bool = True, dedup: bool = True) -> PoolItem:
        """Register an item, optionally copying ``source`` file into the pool.

        Metadata-only items (no ``source``) are allowed — a brand kit, a voice
        profile descriptor, etc. Re-adding the same id overwrites its metadata.

        Deduplication (Phase C17): when ``dedup`` is on (default) and an existing
        item already holds a file with the *same content hash*, the new item simply
        references that stored file instead of writing a second identical copy — so
        adding the same asset/export twice never duplicates bytes on disk. Removal
        is reference-counted, so a shared file survives until its last referrer goes.
        """
        iid = item_id or make_item_id(name, kind)
        rel = ""
        item_meta = dict(meta or {})
        if source is not None:
            src = Path(source)
            content_hash = sha256_file(src)
            existing = self.find_by_hash(content_hash) if dedup else None
            if existing is not None:
                rel = existing.path                       # reuse the stored file (no copy)
                item_meta.setdefault("dedup_of", existing.item_id)
            else:
                files_dir = self.dir / _FILES_SUBDIR
                files_dir.mkdir(parents=True, exist_ok=True)
                dest = files_dir / f"{iid}{src.suffix}"
                if copy:
                    shutil.copy2(src, dest)
                else:
                    dest.write_bytes(src.read_bytes())
                rel = f"{_FILES_SUBDIR}/{dest.name}"
            item_meta.setdefault("content_hash", content_hash)
            item_meta.setdefault("source_name", src.name)
        item = PoolItem(item_id=iid, name=name, kind=kind, path=rel,
                        tags=tuple(dict.fromkeys(tags)), meta=item_meta,
                        created_at=self._clock())
        self._items[iid] = item
        self._save()
        return item

    def remove(self, item_id: str) -> None:
        item = self._items.pop(item_id, None)
        if item is not None and item.path:
            # Reference-counted: only delete the file when no other item shares it
            # (deduped items point at the same stored path).
            shared = any(o.path == item.path for o in self._items.values())
            if not shared:
                (self.dir / item.path).unlink(missing_ok=True)
        self._save()

    # ---- read ----------------------------------------------------------------
    def get(self, item_id: str) -> PoolItem:
        return self._items[item_id]

    def has(self, item_id: str) -> bool:
        return item_id in self._items

    def path_of(self, item: PoolItem | str) -> Path | None:
        """Absolute path to an item's file (``None`` for metadata-only items)."""
        it = item if isinstance(item, PoolItem) else self._items[item]
        return (self.dir / it.path) if it.path else None

    def list(self) -> list[PoolItem]:
        return [self._items[k] for k in sorted(self._items)]

    def find_by_hash(self, content_hash: str) -> PoolItem | None:
        """The first file-item whose stored content matches ``content_hash``.

        Used for deduplication: returns an existing item (in deterministic id
        order) whose file is still on disk, or ``None``. Metadata-only items and
        items whose file has since been removed are ignored."""
        for it in self.list():
            if it.path and it.meta.get("content_hash") == content_hash:
                if (self.dir / it.path).exists():
                    return it
        return None

    def search(self, *, name: str = "", tag: str = "", kind: str = "") -> list[PoolItem]:
        """Deterministic filter by name substring, tag membership, and kind."""
        out = []
        for it in self.list():
            if name and name.lower() not in it.name.lower():
                continue
            if tag and tag not in it.tags:
                continue
            if kind and it.kind != kind:
                continue
            out.append(it)
        return out

    def __len__(self) -> int:
        return len(self._items)
