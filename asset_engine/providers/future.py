"""Future provider interfaces (Phase C9) — designed, deliberately NOT implemented.

Phase C9 defines the extension points for later phases so the resolver/ranking
pipeline never has to change to gain new sources. Each future provider implements
the SAME :class:`~asset_engine.providers.candidate.CandidateProvider` interface
(``name`` + ``search(query, limit)``) — so dropping a real implementation in later
is a one-line registration with the :class:`ProviderManager`, nothing else.

These classes intentionally raise :class:`NotImplementedError`: stock media, AI
image generation, and AI video generation belong to later phases and are OUT OF
SCOPE for C9. They exist to pin the contract and document the seam.
"""
from __future__ import annotations

from asset_engine.catalog.types import AssetCandidate, AssetQuery


class _FutureProvider:
    """Base for not-yet-implemented providers; ``search`` raises with guidance."""

    name = "future"
    phase = "a later phase"
    capability = "external asset retrieval"

    def search(self, query: AssetQuery, *, limit: int = 8) -> list[AssetCandidate]:
        raise NotImplementedError(
            f"{type(self).__name__} ({self.capability}) is planned for {self.phase}. "
            "Phase C9 ships deterministic local providers only "
            "(LocalLibraryProvider / FileSystemProvider / MockProvider). "
            "Implement search() returning AssetCandidate list to enable it.")


class StockMediaProvider(_FutureProvider):
    """Future: query a licensed stock-media library/API for candidates."""

    name = "stock_media"
    phase = "the Stock Media phase (future)"
    capability = "stock media retrieval"


class AIImageProvider(_FutureProvider):
    """Future: generate a matching still with an image model, return it as a
    candidate. NOT implemented in C9 (no AI generation)."""

    name = "ai_image"
    phase = "the AI Image Generation phase (future)"
    capability = "AI image generation"


class AIVideoProvider(_FutureProvider):
    """Future: generate matching B-roll with a video model, return it as a
    candidate. NOT implemented in C9 (no AI generation)."""

    name = "ai_video"
    phase = "the AI Video Generation phase (future)"
    capability = "AI video generation"
