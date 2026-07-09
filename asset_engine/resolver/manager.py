"""Provider manager (Phase C9) — gather candidates from ordered providers.

The manager is the single entry point the resolver asks for candidates. It runs a
query through every registered :class:`CandidateProvider` in order and returns the
union, de-duplicated by file path so the same asset surfaced by two providers is
counted once (the earlier provider wins — provider order is priority). Adding a
future provider (stock media, AI generation) is just registering it here; nothing
downstream changes. Deterministic given deterministic providers.
"""
from __future__ import annotations

from asset_engine.catalog.types import AssetCandidate, AssetQuery


class ProviderManager:
    """An ordered set of candidate providers queried as one source."""

    def __init__(self, providers=()) -> None:
        self.providers = list(providers)

    @property
    def names(self) -> list[str]:
        return [p.name for p in self.providers]

    def add(self, provider) -> "ProviderManager":
        """Register a provider (lowest priority — appended after existing ones)."""
        self.providers.append(provider)
        return self

    def candidates(self, query: AssetQuery, *, per_provider_limit: int = 16) -> list[AssetCandidate]:
        """Every candidate across all providers for ``query`` (dedup by path).

        Provider order is priority: when two providers offer the same file, the
        earlier provider's candidate is kept. Order within the result is
        provider-order then each provider's own (deterministic) order."""
        seen: set[str] = set()
        out: list[AssetCandidate] = []
        for provider in self.providers:
            for cand in provider.search(query, limit=per_provider_limit):
                if cand.path in seen:
                    continue
                seen.add(cand.path)
                out.append(cand)
        return out
