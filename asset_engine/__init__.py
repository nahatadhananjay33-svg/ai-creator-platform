"""Visual Asset Engine (Phase C6) — Timeline-native B-roll / visual assets.

Turns a list of local asset requests into a validated ``AssetTrack`` that lives
natively in the Timeline IR. The renderer simply lowers asset tracks to
overlays; assets are never hardcoded in it.

Pipeline:  asset specs -> provider -> AssetTrack -> Timeline -> renderer -> MP4

Scope (Phase C6): Timeline-native visual assets ONLY — no AI generation, no AI
search, no downloads, no stock providers, no scene planning (later phases).

Public API:
- :class:`AssetEngine` — the facade (asset specs -> AssetTrack)
- :class:`AssetSpec` — an authoring request for one asset
- :class:`AssetEngineConfig` / :func:`load_asset_engine_config` — configuration
- providers in :mod:`asset_engine.providers`
- layout helpers in :mod:`asset_engine.layout`
- the builder in :mod:`asset_engine.timeline`

The frozen asset IR types (AssetTrack/AssetClip/AssetLayout/AssetPlacement/
AssetCrop/AssetAnimation/AssetTransition) live in ``reel_engine.interfaces``.
"""
from __future__ import annotations

from asset_engine.config.settings import AssetEngineConfig, load_asset_engine_config
from asset_engine.engine import AssetEngine
from asset_engine.providers import AssetSpec, LocalAssetProvider, infer_kind
from asset_engine.timeline import build_asset_track

__version__ = "1.0.0"

__all__ = [
    "AssetEngine",
    "AssetEngineConfig",
    "load_asset_engine_config",
    "AssetSpec",
    "LocalAssetProvider",
    "infer_kind",
    "build_asset_track",
]
