"""Media Provider Interface (Phase C13) — one contract, many future sources.

Every media source — the local registry, a stock library (Pexels / Pixabay /
Unsplash / Shutterstock), or a generative model (Stability AI / Runway) —
implements the SAME deterministic :class:`MediaProvider` contract: given an
:class:`AssetQuery`, return ranked-able :class:`AssetCandidate` objects. This is the
existing Phase C9 :class:`CandidateProvider` protocol, reused verbatim so the
ranking/resolver pipeline never changes to gain a source.

This phase ships **deterministic mocks only** (per the constraint "Mock providers
must exist for every external AI/media service"): the real network/generative
providers are pinned as stubs that raise :class:`NotImplementedError`, and each has
a paired ``Mock*`` implementation that fabricates deterministic candidates for
hermetic tests. Wiring a real provider later is a one-line registration with the
existing :class:`ProviderManager`.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from asset_engine.catalog.types import AssetCandidate, AssetQuery
from asset_engine.providers.candidate import MockProvider

#: The external services this seam is designed for (documented, not implemented).
FUTURE_SERVICES = ("pexels", "pixabay", "unsplash", "shutterstock",
                   "stability_ai", "runway")


@runtime_checkable
class MediaProvider(Protocol):
    """Searches a media source for candidates satisfying an :class:`AssetQuery`.

    Identical to the C9 ``CandidateProvider`` contract: deterministic, ``name``
    for provenance, ``search(query, limit)`` returning candidates in stable order.
    """

    name: str

    def search(self, query: AssetQuery, *, limit: int = 8) -> list[AssetCandidate]:
        ...


# --------------------------------------------------------------- future (real)
class _FutureMediaProvider:
    """Base for a not-yet-implemented external provider (pins the contract)."""

    name = "future"
    service = "external media"
    kind = "retrieval"

    def search(self, query: AssetQuery, *, limit: int = 8) -> list[AssetCandidate]:
        raise NotImplementedError(
            f"{type(self).__name__} ({self.service} {self.kind}) is out of scope for "
            "Phase C13, which ships deterministic mocks only. Implement search() "
            f"returning AssetCandidate list to enable it; use Mock{type(self).__name__[:-8]}"
            "Provider for tests.")


class PexelsProvider(_FutureMediaProvider):
    name = "pexels"; service = "Pexels stock media"


class PixabayProvider(_FutureMediaProvider):
    name = "pixabay"; service = "Pixabay stock media"


class UnsplashProvider(_FutureMediaProvider):
    name = "unsplash"; service = "Unsplash stock photos"


class ShutterstockProvider(_FutureMediaProvider):
    name = "shutterstock"; service = "Shutterstock stock media"


class StabilityAIProvider(_FutureMediaProvider):
    name = "stability_ai"; service = "Stability AI image generation"; kind = "generation"


class RunwayProvider(_FutureMediaProvider):
    name = "runway"; service = "Runway video generation"; kind = "generation"


#: The real provider classes, by service name (for later registration).
REAL_PROVIDERS = {
    "pexels": PexelsProvider, "pixabay": PixabayProvider, "unsplash": UnsplashProvider,
    "shutterstock": ShutterstockProvider, "stability_ai": StabilityAIProvider,
    "runway": RunwayProvider,
}


# ------------------------------------------------------------------- mocks
class MockMediaProvider:
    """A deterministic stand-in for any external service (no files, no network).

    Delegates to the existing C9 :class:`MockProvider` (a proven deterministic
    candidate fabricator) but stamps the candidates with the service ``name`` so a
    test can assert *which* mocked provider a candidate came from. Generative mocks
    additionally tag their candidates ``generated`` so consistency/reporting can
    tell synthesized media apart from retrieved media."""

    def __init__(self, name: str, *, n: int = 3, generated: bool = False) -> None:
        self.name = name
        self.generated = generated
        self._inner = MockProvider(n=n, name=name)

    def search(self, query: AssetQuery, *, limit: int = 8) -> list[AssetCandidate]:
        candidates = self._inner.search(query, limit=limit)
        if not self.generated:
            return candidates
        from dataclasses import replace
        return [replace(c, meta={**c.meta, "generated": True}) for c in candidates]


def mock_provider_for(service: str, *, n: int = 3) -> MockMediaProvider:
    """A deterministic mock for a named future service (generative ones flagged)."""
    generative = service in ("stability_ai", "runway")
    return MockMediaProvider(service, n=n, generated=generative)


def all_mock_providers(*, n: int = 3) -> list[MockMediaProvider]:
    """One deterministic mock per future service (for pipeline/integration tests)."""
    return [mock_provider_for(s, n=n) for s in FUTURE_SERVICES]
