"""Deterministic asset resolution (Phase C9): query → manager → ranking → select."""
from __future__ import annotations

from asset_engine.resolver.manager import ProviderManager
from asset_engine.resolver.query import build_query, region_of
from asset_engine.resolver.resolver import (
    AssetResolutionError,
    AssetResolver,
    Resolution,
)

__all__ = [
    "AssetResolver",
    "Resolution",
    "AssetResolutionError",
    "ProviderManager",
    "build_query",
    "region_of",
]
