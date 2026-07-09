"""Candidate providers (Phase C9) — search a source for assets matching a query.

A *candidate provider* answers a richer question than the C6
:class:`~asset_engine.providers.base.LocalAssetProvider` (which resolves one known
path): given an :class:`AssetQuery`, *which* local assets could satisfy it? Each
returns a list of :class:`AssetCandidate` for the resolver to rank and select.

Phase C9 ships three deterministic, offline providers:

- :class:`LocalLibraryProvider` — a curated :class:`AssetCatalog` (the local
  asset library).
- :class:`FileSystemProvider` — a raw folder scanned into a catalog on init.
- :class:`MockProvider` — deterministic synthetic candidates (no files), for
  hermetic tests of the ranking/selection logic.

Future providers (stock media, AI image/video generation) implement the SAME
:class:`CandidateProvider` interface; their stubs live in
:mod:`asset_engine.providers.future` and are intentionally not implemented here.
"""
from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from asset_engine.catalog.index import AssetCatalog
from asset_engine.catalog.types import AssetCandidate, AssetQuery


@runtime_checkable
class CandidateProvider(Protocol):
    """Searches a source for assets that could satisfy an :class:`AssetQuery`.

    Implementations are deterministic: the same ``(query, limit)`` always returns
    the same candidates in the same order. ``name`` records provenance on every
    candidate. ``limit`` bounds how many candidates the provider returns (paging
    providers respect it; the local providers return up to it)."""

    name: str

    def search(self, query: AssetQuery, *, limit: int = 8) -> list[AssetCandidate]:
        ...


class _CatalogBackedProvider:
    """Shared search logic for providers backed by an :class:`AssetCatalog`."""

    name = "catalog"

    def __init__(self, catalog: AssetCatalog, *, name: str | None = None) -> None:
        self.catalog = catalog
        if name:
            self.name = name

    def search(self, query: AssetQuery, *, limit: int = 8) -> list[AssetCandidate]:
        entries = self.catalog.search(kind=query.kind)      # family-compatible, stable order
        cands = [e.to_candidate(self.name) for e in entries]
        return cands[:max(0, limit)] if limit else cands


class LocalLibraryProvider(_CatalogBackedProvider):
    """The local asset library: a curated, pre-indexed :class:`AssetCatalog`."""

    name = "local_library"


class FileSystemProvider(_CatalogBackedProvider):
    """A raw asset folder scanned into a catalog on construction (no curation)."""

    name = "filesystem"

    def __init__(self, root: Path | str, *, probe_videos: bool = False,
                 name: str | None = None) -> None:
        super().__init__(AssetCatalog.from_directory(root, probe_videos=probe_videos),
                         name=name)


class MockProvider:
    """Deterministic synthetic candidates for hermetic tests — never real files.

    Fabricates ``n`` candidates for a query: the first is an exact-kind,
    full-tag, correctly-sized match (the clear winner); the rest are weaker
    (generic family kind, fewer tags) so ranking/selection is exercised without
    any filesystem. Paths are ``mock://…`` sentinels — not renderable."""

    name = "mock"

    def __init__(self, *, n: int = 3, name: str | None = None) -> None:
        self.n = n
        if name:
            self.name = name

    def search(self, query: AssetQuery, *, limit: int = 8) -> list[AssetCandidate]:
        count = min(self.n, limit) if limit else self.n
        family_kind = "video" if query.family == "video" else "image"
        out: list[AssetCandidate] = []
        for i in range(count):
            out.append(AssetCandidate(
                candidate_id=f"{self.name}:{query.kind}:{i}",
                path=f"mock://{query.kind}/{i}",
                kind=query.kind if i == 0 else family_kind,
                tags=query.tags if i == 0 else query.tags[:max(0, len(query.tags) - i)],
                width=1920, height=1080,
                duration_s=(query.target_duration_s + 1.0 if query.family == "video" else 0.0),
                provider=self.name, meta={"synthetic": True}))
        return out
