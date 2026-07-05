"""Tests for foundation.cache."""
from __future__ import annotations

from pathlib import Path

import pytest

from foundation.cache import DiskCache
from foundation.exceptions import CacheError


def test_put_get_roundtrip(tmp_path: Path) -> None:
    cache = DiskCache("test-ns", root=tmp_path)
    assert cache.get("k1") is None
    assert not cache.has("k1")
    cache.put("k1", {"path": "weights.bin", "size": 42})
    assert cache.has("k1")
    assert cache.get("k1") == {"path": "weights.bin", "size": 42}


def test_evict_and_clear(tmp_path: Path) -> None:
    cache = DiskCache("test-ns", root=tmp_path)
    cache.put("a", {"v": 1})
    cache.put("b", {"v": 2})
    assert cache.evict("a") is True
    assert cache.evict("a") is False
    assert cache.get("b") == {"v": 2}
    cache.clear()
    assert cache.get("b") is None


def test_artifact_path_is_stable(tmp_path: Path) -> None:
    cache = DiskCache("test-ns", root=tmp_path)
    p1 = cache.artifact_path("model-x", "weights.bin")
    p2 = cache.artifact_path("model-x", "weights.bin")
    assert p1 == p2
    assert p1.parent.exists()


def test_invalid_namespace_rejected(tmp_path: Path) -> None:
    with pytest.raises(CacheError):
        DiskCache("bad/ns", root=tmp_path)
