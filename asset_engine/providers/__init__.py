"""Asset providers.

C6: local-file resolution + placeholder generation (`LocalAssetProvider`).
C9: candidate providers that *search* a source for assets matching a query
(`LocalLibraryProvider`, `FileSystemProvider`, `MockProvider`) plus the
not-yet-implemented future interfaces (stock media, AI image/video).
"""
from __future__ import annotations

from asset_engine.providers.base import (
    AssetProvider,
    AssetSpec,
    LocalAssetProvider,
    infer_kind,
)
from asset_engine.providers.candidate import (
    CandidateProvider,
    FileSystemProvider,
    LocalLibraryProvider,
    MockProvider,
)
from asset_engine.providers.future import (
    AIImageProvider,
    AIVideoProvider,
    StockMediaProvider,
)

__all__ = [
    # C6 spec-resolution provider
    "AssetProvider",
    "AssetSpec",
    "LocalAssetProvider",
    "infer_kind",
    # C9 candidate providers
    "CandidateProvider",
    "LocalLibraryProvider",
    "FileSystemProvider",
    "MockProvider",
    # C9 future interfaces (not implemented)
    "StockMediaProvider",
    "AIImageProvider",
    "AIVideoProvider",
]
