"""Asset Registry (Phase C13) — the central catalog of project media assets.

The registry is the single, deterministic source of truth for the media a project
*could* use: every asset gets a **stable ID** (a content hash of its identity, so
the same asset always registers to the same ID) and carries metadata (kind,
duration, dimensions/aspect, source, license, tags). It is metadata-only — it
never loads pixels and never touches the Timeline IR or the renderer.

It is built on the existing Phase C9 retrieval vocabulary (:class:`AssetCandidate`
/ :class:`CatalogEntry` / :class:`AssetCatalog`) rather than duplicating it: a
registry converts to/from those types, and exposes itself as a
:class:`CandidateProvider` so the existing ranking/resolver pipeline searches it
unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

from foundation.shared_utils.hashing import short_hash

from asset_engine.catalog.index import AssetCatalog
from asset_engine.catalog.types import AssetCandidate, CatalogEntry, kind_family

#: License classes the registry understands. ``unknown`` is allowed but flagged by
#: :meth:`AssetRegistry.validate`; ``proprietary``/``editorial`` need review before
#: a production render (documented — no enforcement in this deterministic phase).
LICENSES = ("cc0", "royalty_free", "editorial", "proprietary", "unknown")


def make_asset_id(kind: str, uri: str, width: int, height: int, duration_s: float) -> str:
    """A stable, content-derived asset ID (same identity → same ID, always)."""
    key = f"{kind}|{uri}|{int(width)}x{int(height)}|{round(float(duration_s), 3)}"
    return f"asset_{short_hash(key)}"


@dataclass(frozen=True)
class RegisteredAsset:
    """One catalogued asset: a stable ID + full metadata (no pixels).

    ``source`` records provenance (which provider/library/service supplied it);
    ``license`` is one of :data:`LICENSES`. ``meta`` carries free-form descriptive
    metadata the Consistency Engine reads (e.g. ``dominant_color``, ``style``,
    ``subject``)."""

    asset_id: str
    uri: str
    kind: str
    tags: tuple[str, ...] = ()
    width: int = 0
    height: int = 0
    duration_s: float = 0.0
    source: str = ""
    license: str = "unknown"
    meta: dict = field(default_factory=dict)

    @property
    def aspect_ratio(self) -> float:
        return round(self.width / self.height, 6) if self.height else 0.0

    @property
    def pixels(self) -> int:
        return max(0, self.width) * max(0, self.height)

    @property
    def family(self) -> str:
        return kind_family(self.kind)

    @property
    def is_video(self) -> bool:
        return self.kind == "video"

    # ------------------------------------------------------- retrieval interop
    def to_candidate(self, provider: str | None = None) -> AssetCandidate:
        """Surface this asset as a ranking :class:`AssetCandidate`."""
        src = provider or self.source or "registry"
        return AssetCandidate(
            candidate_id=f"{src}:{self.asset_id}", path=self.uri, kind=self.kind,
            tags=self.tags, width=self.width, height=self.height,
            duration_s=self.duration_s, provider=src,
            meta={**self.meta, "asset_id": self.asset_id, "license": self.license})

    @classmethod
    def from_candidate(cls, candidate: AssetCandidate, *, source: str | None = None,
                       license: str = "unknown") -> "RegisteredAsset":
        aid = make_asset_id(candidate.kind, candidate.path, candidate.width,
                            candidate.height, candidate.duration_s)
        meta = dict(candidate.meta)
        return cls(
            asset_id=aid, uri=candidate.path, kind=candidate.kind, tags=candidate.tags,
            width=candidate.width, height=candidate.height, duration_s=candidate.duration_s,
            source=source or candidate.provider or "registry",
            license=meta.pop("license", license), meta=meta)

    @classmethod
    def from_entry(cls, entry: CatalogEntry, *, source: str = "library",
                   license: str = "unknown") -> "RegisteredAsset":
        aid = make_asset_id(entry.kind, entry.path, entry.width, entry.height, entry.duration_s)
        return cls(
            asset_id=aid, uri=entry.path, kind=entry.kind, tags=entry.tags,
            width=entry.width, height=entry.height, duration_s=entry.duration_s,
            source=source, license=license, meta=dict(entry.meta))

    def to_entry(self) -> CatalogEntry:
        """Back to a :class:`CatalogEntry` (for the existing catalog tooling)."""
        return CatalogEntry(
            entry_id=self.asset_id, path=self.uri, kind=self.kind, tags=self.tags,
            width=self.width, height=self.height, duration_s=self.duration_s,
            meta={**self.meta, "source": self.source, "license": self.license})


class RegistryProvider:
    """A :class:`CandidateProvider` view over a registry (family-compatible search).

    Lets the existing ranking/resolver pipeline treat the registry as just another
    deterministic provider — same ``search(query, limit)`` contract, stable order."""

    def __init__(self, registry: "AssetRegistry", *, name: str = "registry") -> None:
        self.registry = registry
        self.name = name

    def search(self, query, *, limit: int = 8) -> list[AssetCandidate]:
        fam = kind_family(query.kind) if getattr(query, "kind", None) else None
        assets = self.registry.all() if fam is None else self.registry.by_family(fam)
        cands = [a.to_candidate(self.name) for a in assets]
        return cands[:max(0, limit)] if limit else cands


@dataclass(frozen=True)
class RegistryStats:
    """A deterministic summary of registry contents."""

    total: int
    by_kind: tuple[tuple[str, int], ...]
    by_license: tuple[tuple[str, int], ...]
    by_source: tuple[tuple[str, int], ...]
    n_videos: int
    n_images: int


class AssetRegistry:
    """A central, deterministic catalog of assets keyed by stable asset ID."""

    def __init__(self, assets=()) -> None:
        self._assets: dict[str, RegisteredAsset] = {}
        for asset in assets:
            self.register(asset)

    # -------------------------------------------------------------- mutation
    def register(self, asset: RegisteredAsset) -> str:
        """Register (or replace) an asset; returns its stable ID (idempotent)."""
        self._assets[asset.asset_id] = asset
        return asset.asset_id

    def register_candidate(self, candidate: AssetCandidate, *, source: str | None = None,
                           license: str = "unknown") -> RegisteredAsset:
        asset = RegisteredAsset.from_candidate(candidate, source=source, license=license)
        self.register(asset)
        return asset

    def register_many(self, assets) -> tuple[str, ...]:
        return tuple(self.register(a) for a in assets)

    def remove(self, asset_id: str) -> bool:
        return self._assets.pop(asset_id, None) is not None

    def with_meta(self, asset_id: str, **meta) -> RegisteredAsset:
        """Return + store a copy of an asset with extra ``meta`` merged in."""
        asset = self._assets[asset_id]
        updated = replace(asset, meta={**asset.meta, **meta})
        self.register(updated)
        return updated

    # ---------------------------------------------------------------- lookup
    def get(self, asset_id: str) -> RegisteredAsset | None:
        return self._assets.get(asset_id)

    def __contains__(self, asset_id: str) -> bool:
        return asset_id in self._assets

    @property
    def size(self) -> int:
        return len(self._assets)

    def all(self) -> list[RegisteredAsset]:
        """Every asset, sorted by stable ID (deterministic order)."""
        return [self._assets[k] for k in sorted(self._assets)]

    def by_kind(self, kind: str) -> list[RegisteredAsset]:
        return [a for a in self.all() if a.kind == kind]

    def by_family(self, family: str) -> list[RegisteredAsset]:
        return [a for a in self.all() if a.family == family]

    def by_tag(self, tag: str) -> list[RegisteredAsset]:
        return [a for a in self.all() if tag in a.tags]

    def by_license(self, license: str) -> list[RegisteredAsset]:
        return [a for a in self.all() if a.license == license]

    # ---------------------------------------------------------- interop / stats
    def as_provider(self, name: str = "registry") -> RegistryProvider:
        return RegistryProvider(self, name=name)

    def as_catalog(self) -> AssetCatalog:
        return AssetCatalog.from_entries(a.to_entry() for a in self.all())

    def validate(self) -> list[str]:
        """Deterministic metadata problems (empty == clean).

        Flags unknown/invalid licenses and image/video assets missing dimensions —
        the sort of gaps that make a downstream ranking or render decision unsafe."""
        problems: list[str] = []
        for a in self.all():
            if a.license not in LICENSES:
                problems.append(f"{a.asset_id}: invalid license {a.license!r}")
            if a.license == "unknown":
                problems.append(f"{a.asset_id}: license unknown ({a.uri})")
            if a.pixels == 0:
                problems.append(f"{a.asset_id}: missing dimensions ({a.uri})")
            if a.is_video and a.duration_s <= 0:
                problems.append(f"{a.asset_id}: video has no duration ({a.uri})")
        return problems

    def stats(self) -> RegistryStats:
        def _counts(key) -> tuple[tuple[str, int], ...]:
            counts: dict[str, int] = {}
            for a in self._assets.values():
                counts[key(a)] = counts.get(key(a), 0) + 1
            return tuple(sorted(counts.items()))
        return RegistryStats(
            total=self.size,
            by_kind=_counts(lambda a: a.kind),
            by_license=_counts(lambda a: a.license),
            by_source=_counts(lambda a: a.source),
            n_videos=len(self.by_family("video")),
            n_images=len(self.by_family("image")),
        )

    # ------------------------------------------------------------- builders
    @classmethod
    def from_catalog(cls, catalog: AssetCatalog, *, source: str = "library",
                     license: str = "unknown") -> "AssetRegistry":
        return cls(RegisteredAsset.from_entry(e, source=source, license=license)
                   for e in catalog.entries)

    @classmethod
    def from_directory(cls, root, *, source: str = "library", license: str = "unknown",
                       probe_videos: bool = False) -> "AssetRegistry":
        catalog = AssetCatalog.from_directory(root, probe_videos=probe_videos)
        return cls.from_catalog(catalog, source=source, license=license)
