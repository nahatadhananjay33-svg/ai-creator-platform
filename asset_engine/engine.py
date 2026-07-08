"""Visual Asset Engine facade (Phase C6).

The high-level, reusable API: turn a list of asset requests into a validated,
Timeline-native :class:`AssetTrack`. It wires two pieces —

    provider (resolve local file)  →  builder (apply config + layout)

— and nothing else. It produces *data* (an asset track); rendering is a separate
concern (the renderer lowers the track to overlays). No AI generation, no asset
search, no downloads — Phase C6 is purely about making visual assets a
first-class Timeline citizen.
"""
from __future__ import annotations

from foundation.logging import get_logger
from reel_engine.interfaces.types import AssetTrack

from asset_engine.config.settings import AssetEngineConfig, load_asset_engine_config
from asset_engine.providers.base import AssetProvider, AssetSpec, LocalAssetProvider
from asset_engine.timeline.builder import build_asset_track

logger = get_logger("asset_engine")


class AssetEngine:
    """Asset requests -> a validated, laid-out AssetTrack."""

    def __init__(
        self,
        config: AssetEngineConfig | None = None,
        *,
        provider: AssetProvider | None = None,
    ) -> None:
        self.config = config or load_asset_engine_config()
        self.provider = provider or LocalAssetProvider()

    def build(self, specs: list[AssetSpec], *, track_id: str = "assets") -> AssetTrack:
        """Resolve and assemble a :class:`AssetTrack` from authoring specs."""
        track = build_asset_track(specs, config=self.config,
                                  provider=self.provider, track_id=track_id)
        logger.info("Asset track built", extra={"context": {
            "clips": track.n_clips,
            "layouts": sorted({c.layout.kind for c in track.clips}),
            "kinds": sorted({c.kind for c in track.clips})}})
        return track
