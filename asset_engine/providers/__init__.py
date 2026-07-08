"""Asset providers (Phase C6): local-file resolution + placeholder generation."""
from __future__ import annotations

from asset_engine.providers.base import (
    AssetProvider,
    AssetSpec,
    LocalAssetProvider,
    infer_kind,
)

__all__ = ["AssetProvider", "AssetSpec", "LocalAssetProvider", "infer_kind"]
