"""Asset providers (Phase C6) — resolve an asset spec to a local file.

A *provider* answers one question: for this asset request, where is the file and
what kind is it? Phase C6 is deliberately offline and non-AI: the only provider
is :class:`LocalAssetProvider`, which resolves **local paths** (no downloads, no
stock APIs, no AI search — those are later phases). It infers the asset kind
from the file extension when not given and refuses missing files, so the "no
missing assets" invariant is caught early.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from reel_engine.interfaces.types import ASSET_KINDS, AssetRef

#: Extension -> default asset kind. Everything image-like maps to ``image``
#: unless the caller supplies a more specific semantic kind (chart, map, ...).
_VIDEO_EXTS = {".mp4", ".mov", ".webm", ".mkv", ".avi", ".m4v"}
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tif", ".tiff"}


def infer_kind(path: str | Path) -> str:
    """Infer a default asset kind from the file extension (image vs video)."""
    ext = Path(path).suffix.lower()
    if ext in _VIDEO_EXTS:
        return "video"
    return "image"


@dataclass(frozen=True)
class AssetSpec:
    """An authoring request for one visual asset on the timeline.

    ``kind`` is inferred from the extension when None. ``layout``/``layout_params``
    pick the on-screen placement; ``animation_*``/``opacity``/``crop`` are
    optional overrides (None -> engine/config defaults)."""

    path: str
    start_s: float
    end_s: float
    kind: str | None = None
    layout: str | None = None            # None -> engine/config default_layout
    layout_params: dict = field(default_factory=dict)
    animation_in: str | None = None
    animation_out: str | None = None
    animation_duration_s: float | None = None
    transition: str | None = None
    opacity: float | None = None
    z_index: int = 0
    crop: tuple | None = None            # (x, y, w, h) fractions
    clip_id: str | None = None


class AssetProvider(Protocol):
    """Resolves an :class:`AssetSpec` to a concrete :class:`AssetRef` (a file)."""

    def resolve(self, spec: AssetSpec) -> AssetRef: ...


class LocalAssetProvider:
    """Resolves local files. No network, no stock, no AI (Phase C6 scope)."""

    def __init__(self, *, require_exists: bool = True, base_dir: Path | str | None = None) -> None:
        self.require_exists = require_exists
        self.base_dir = Path(base_dir) if base_dir else None

    def resolve(self, spec: AssetSpec) -> AssetRef:
        path = Path(spec.path)
        if self.base_dir and not path.is_absolute():
            path = self.base_dir / path
        if self.require_exists and not path.exists():
            raise FileNotFoundError(f"Asset not found: {path}")
        kind = spec.kind or infer_kind(path)
        if kind not in ASSET_KINDS:
            raise ValueError(f"Unknown asset kind {kind!r}; expected one of {ASSET_KINDS}")
        return AssetRef(kind="file", uri=str(path),
                        meta={"asset_kind": kind, "source_ext": path.suffix.lower()})
