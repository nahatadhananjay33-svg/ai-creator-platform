"""Local asset catalog — a deterministic metadata index (Phase C9).

Indexes a local asset library so the resolver can look assets up by kind and
tags without any network, stock API, or AI. Supports images, videos, icons,
screenshots, charts (and the other image-like kinds) via three builders:

- :meth:`AssetCatalog.from_entries` — explicit :class:`CatalogEntry` list
  (fully deterministic; used by tests).
- :meth:`AssetCatalog.from_manifest` — a JSON manifest of entries (reproducible,
  no probing).
- :meth:`AssetCatalog.from_directory` — scan a folder: kind from the extension +
  the parent folder name (``charts/`` → ``chart``), tags from the filename,
  image dimensions via Pillow (video dimensions/duration optionally via ffprobe).

Lookups are pure filters over the in-memory index, returned in a stable order,
so the same catalog + query always yields the same candidate set.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from reel_engine.interfaces.types import ASSET_KINDS

from asset_engine.catalog.types import CatalogEntry, kind_family
from asset_engine.providers.base import infer_kind

_VIDEO_EXTS = {".mp4", ".mov", ".webm", ".mkv", ".avi", ".m4v"}
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tif", ".tiff"}
_MEDIA_EXTS = _VIDEO_EXTS | _IMAGE_EXTS

#: Folder-name → asset kind (so a ``charts/`` subtree indexes as ``chart``).
_DIR_KIND = {
    "images": "image", "image": "image", "videos": "video", "video": "video",
    "icons": "icon", "icon": "icon", "screenshots": "screenshot",
    "screenshot": "screenshot", "charts": "chart", "chart": "chart",
    "maps": "map", "map": "map", "documents": "document", "document": "document",
    "illustrations": "illustration", "illustration": "illustration",
}
#: Tiny fixed stopword set for filename tokenisation (deterministic; not NLP).
_STOP = frozenset({"the", "a", "an", "and", "or", "of", "to", "in", "on", "for",
                   "with", "img", "image", "final", "copy", "new", "asset"})
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize_tags(text: str) -> tuple[str, ...]:
    """Deterministic tag tokens from free text: alnum runs, len>=3, no stopwords
    and no bare asset-kind names (those are the *kind*, not a tag)."""
    toks = _TOKEN_RE.findall(text.lower())
    seen: list[str] = []
    for t in toks:
        if len(t) >= 3 and t not in _STOP and t not in ASSET_KINDS and t not in seen:
            seen.append(t)
    return tuple(seen)


def _dims_of_image(path: Path) -> tuple[int, int]:
    try:
        from PIL import Image
        with Image.open(path) as im:
            return int(im.width), int(im.height)
    except Exception:  # noqa: BLE001 - a bad file just indexes with unknown dims
        return 0, 0


def _probe_video(path: Path) -> tuple[int, int, float]:
    try:
        from reel_engine.render.probe import probe_media
        m = probe_media(path)
        return int(m.width), int(m.height), float(m.duration_s)
    except Exception:  # noqa: BLE001 - ffprobe missing/failed -> unknown, still indexed
        return 0, 0, 0.0


@dataclass(frozen=True)
class AssetCatalog:
    """An immutable, deterministic index of local library assets."""

    entries: tuple[CatalogEntry, ...] = ()

    @property
    def size(self) -> int:
        return len(self.entries)

    def kinds(self) -> tuple[str, ...]:
        return tuple(sorted({e.kind for e in self.entries}))

    def search(self, *, kind: str | None = None, family: str | None = None) -> list[CatalogEntry]:
        """Every entry compatible with ``kind`` (same coarse family), stable order.

        Ranking narrows further; the catalog's job is a fast, deterministic first
        cut. Pass ``family`` directly to restrict to ``image``/``video`` without a
        specific kind. Results are sorted by ``entry_id`` for reproducibility."""
        fam = family or (kind_family(kind) if kind else None)
        out = [e for e in self.entries if fam is None or e.family == fam]
        return sorted(out, key=lambda e: e.entry_id)

    # ------------------------------------------------------------- builders
    @classmethod
    def from_entries(cls, entries) -> "AssetCatalog":
        """Build from an explicit iterable of :class:`CatalogEntry` (deterministic)."""
        return cls(entries=tuple(entries))

    @classmethod
    def from_manifest(cls, path: Path | str) -> "AssetCatalog":
        """Build from a JSON manifest: ``[{path, kind, tags, width, height,
        duration_s, ...}, ...]`` — reproducible, no filesystem probing."""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        entries = []
        for i, d in enumerate(data):
            entries.append(CatalogEntry(
                entry_id=d.get("entry_id", d.get("path", f"entry-{i:04d}")),
                path=d["path"], kind=d["kind"], tags=tuple(d.get("tags", ())),
                width=int(d.get("width", 0)), height=int(d.get("height", 0)),
                duration_s=float(d.get("duration_s", 0.0)), meta=dict(d.get("meta", {}))))
        return cls(entries=tuple(entries))

    @classmethod
    def from_directory(cls, root: Path | str, *, probe_videos: bool = False) -> "AssetCatalog":
        """Scan ``root`` recursively into a catalog (deterministic file order).

        Kind comes from the parent folder name when it is a known kind, else the
        file extension. Tags come from the filename (+ parent folder). Image
        dimensions are read via Pillow; video dimensions/duration are read via
        ffprobe only when ``probe_videos`` is set (otherwise left unknown)."""
        root = Path(root)
        entries: list[CatalogEntry] = []
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in _MEDIA_EXTS:
                continue
            parent = path.parent.name.lower()
            kind = _DIR_KIND.get(parent) or infer_kind(path)
            rel = path.relative_to(root).as_posix()
            tags = tokenize_tags(path.stem)     # tags come from the filename only
            width = height = 0
            duration = 0.0
            if path.suffix.lower() in _IMAGE_EXTS:
                width, height = _dims_of_image(path)
            elif probe_videos:
                width, height, duration = _probe_video(path)
            entries.append(CatalogEntry(
                entry_id=rel, path=str(path), kind=kind, tags=tags,
                width=width, height=height, duration_s=duration))
        return cls(entries=tuple(entries))
