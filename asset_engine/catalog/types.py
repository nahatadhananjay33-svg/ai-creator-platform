"""Core value types for asset retrieval (Phase C9).

The currency the provider → ranking → resolver pipeline passes around, all
immutable and deterministic:

- :class:`AssetQuery` — what a scene needs (derived from a Scene-Planner
  ``AssetSlot``): a kind, tags, a target aspect/duration, a minimum resolution.
- :class:`AssetCandidate` — one asset a provider offers to satisfy a query: a
  local file with its metadata (kind, tags, dimensions, duration, provenance).
- :class:`CatalogEntry` — one indexed local-library asset; converts to a
  candidate when a provider surfaces it.

These carry NO behaviour beyond trivial derived properties and NO I/O, so they
are safe to share across every retrieval module without import cycles.
"""
from __future__ import annotations

from dataclasses import dataclass, field

#: The image-like asset kinds (everything except ``video``). A still can stand in
#: for any of these; it can never satisfy a ``video`` request (and vice versa).
IMAGE_LIKE_KINDS = ("image", "screenshot", "chart", "document", "map",
                    "icon", "illustration")


def kind_family(kind: str) -> str:
    """The coarse family a kind belongs to: ``video`` or ``image``."""
    return "video" if kind == "video" else "image"


@dataclass(frozen=True)
class AssetQuery:
    """What a scene needs from a provider — derived from an ``AssetSlot``.

    ``target_aspect`` is width/height of the on-screen region the asset fills
    (0 = don't care); ``target_duration_s`` matters only for video (0 = a still /
    don't care); ``min_width``/``min_height`` are the pixel size of that region,
    used to reward sufficiently-detailed assets. All fields are deterministic
    functions of the slot + frame — never a model."""

    kind: str
    tags: tuple[str, ...] = ()
    target_aspect: float = 0.0
    target_duration_s: float = 0.0
    min_width: int = 0
    min_height: int = 0
    slot_id: str = ""

    @property
    def family(self) -> str:
        return kind_family(self.kind)

    @property
    def min_pixels(self) -> int:
        return max(0, self.min_width) * max(0, self.min_height)


@dataclass(frozen=True)
class AssetCandidate:
    """One asset a provider offers for a query — a concrete local file + metadata.

    ``provider`` records provenance (which provider surfaced it); ``candidate_id``
    is stable and unique so ranking ties break deterministically."""

    candidate_id: str
    path: str
    kind: str
    tags: tuple[str, ...] = ()
    width: int = 0
    height: int = 0
    duration_s: float = 0.0
    provider: str = ""
    meta: dict = field(default_factory=dict)

    @property
    def aspect_ratio(self) -> float:
        return self.width / self.height if self.height else 0.0

    @property
    def pixels(self) -> int:
        return max(0, self.width) * max(0, self.height)

    @property
    def is_video(self) -> bool:
        return self.kind == "video"

    @property
    def family(self) -> str:
        return kind_family(self.kind)


@dataclass(frozen=True)
class CatalogEntry:
    """One indexed asset in the local library (metadata only, no pixels loaded)."""

    entry_id: str
    path: str
    kind: str
    tags: tuple[str, ...] = ()
    width: int = 0
    height: int = 0
    duration_s: float = 0.0
    meta: dict = field(default_factory=dict)

    @property
    def family(self) -> str:
        return kind_family(self.kind)

    def to_candidate(self, provider: str) -> AssetCandidate:
        """Surface this entry as a provider :class:`AssetCandidate`."""
        return AssetCandidate(
            candidate_id=f"{provider}:{self.entry_id}", path=self.path, kind=self.kind,
            tags=self.tags, width=self.width, height=self.height,
            duration_s=self.duration_s, provider=provider, meta=dict(self.meta))
