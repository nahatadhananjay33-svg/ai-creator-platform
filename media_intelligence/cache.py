"""Asset Cache (Phase C13) — a deterministic, in-memory decision cache.

Media decisions (a search ranking, a per-scene recommendation) are pure functions
of their inputs, so caching them is safe and makes repeated work free. The cache
is a plain keyed store with hit/miss/put statistics; keys are content hashes of
the decision inputs, so the **same inputs always hit the same entry** and stable
asset reuse is guaranteed. No time, no eviction policy, no randomness — the cache
never changes an answer, it only avoids recomputing it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from foundation.shared_utils.hashing import short_hash


def cache_key(*parts: Any) -> str:
    """A stable cache key from any hashable-ish parts (order-sensitive)."""
    return short_hash("|".join(str(p) for p in parts), length=16)


@dataclass(frozen=True)
class CacheStats:
    """Deterministic cache counters + derived hit rate."""

    hits: int
    misses: int
    puts: int
    size: int

    @property
    def lookups(self) -> int:
        return self.hits + self.misses

    @property
    def hit_rate(self) -> float:
        return round(self.hits / self.lookups, 6) if self.lookups else 0.0


class AssetCache:
    """A deterministic key→value cache with hit/miss/put statistics."""

    def __init__(self) -> None:
        self._store: dict[str, Any] = {}
        self._hits = 0
        self._misses = 0
        self._puts = 0

    def get(self, key: str, default: Any = None) -> Any:
        if key in self._store:
            self._hits += 1
            return self._store[key]
        self._misses += 1
        return default

    def has(self, key: str) -> bool:
        """Membership test that does NOT count as a hit/miss (pure inspection)."""
        return key in self._store

    def put(self, key: str, value: Any) -> Any:
        self._store[key] = value
        self._puts += 1
        return value

    def get_or_compute(self, key: str, compute: Callable[[], Any]) -> Any:
        """Return the cached value for ``key`` or compute, store, and return it.

        Counts exactly one hit (cached) or one miss + one put (computed), so the
        statistics reflect real reuse."""
        if key in self._store:
            self._hits += 1
            return self._store[key]
        self._misses += 1
        value = compute()
        self._store[key] = value
        self._puts += 1
        return value

    def clear(self) -> None:
        self._store.clear()

    def reset_stats(self) -> None:
        self._hits = self._misses = self._puts = 0

    @property
    def size(self) -> int:
        return len(self._store)

    def stats(self) -> CacheStats:
        return CacheStats(hits=self._hits, misses=self._misses,
                          puts=self._puts, size=self.size)
