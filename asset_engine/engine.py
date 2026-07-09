"""Visual Asset Engine facade (Phase C6 + C9).

The high-level, reusable API. Two capabilities:

- **C6** — turn explicit :class:`AssetSpec` requests into a validated,
  Timeline-native :class:`AssetTrack` (``build``).
- **C9** — automatically *satisfy* Scene-Planner ``AssetSlot`` requests from
  configurable providers (a local catalog / filesystem), rank the candidates
  deterministically, select the best, and assemble the same :class:`AssetTrack`
  (``resolve_slots``). No AI generation, no stock APIs, no downloads — only
  deterministic resolution from local assets.

It produces *data* (an asset track); rendering is a separate concern (the
renderer lowers the track to overlays — unchanged by this phase).
"""
from __future__ import annotations

from pathlib import Path

from foundation.logging import get_logger
from reel_engine.interfaces.types import ASSET_KINDS, AssetTrack

from asset_engine.catalog.index import AssetCatalog
from asset_engine.config.settings import AssetEngineConfig, load_asset_engine_config
from asset_engine.providers.base import AssetProvider, AssetSpec, LocalAssetProvider
from asset_engine.providers.candidate import (
    FileSystemProvider,
    LocalLibraryProvider,
)
from asset_engine.resolver.manager import ProviderManager
from asset_engine.resolver.resolver import (
    AssetResolutionError,
    AssetResolver,
    Resolution,
)
from asset_engine.timeline.builder import build_asset_track

logger = get_logger("asset_engine")

#: Layouts whose side is chosen per-slot so two clips (e.g. a comparison) tile
#: opposite halves instead of overlapping.
_SIDED_LAYOUTS = ("side_by_side", "split_screen")


class AssetEngine:
    """Asset specs/slots -> a validated, laid-out AssetTrack."""

    def __init__(
        self,
        config: AssetEngineConfig | None = None,
        *,
        provider: AssetProvider | None = None,
    ) -> None:
        self.config = config or load_asset_engine_config()
        self.provider = provider or LocalAssetProvider()

    def build(self, specs: list[AssetSpec], *, track_id: str = "assets") -> AssetTrack:
        """Resolve and assemble an :class:`AssetTrack` from explicit specs (C6)."""
        track = build_asset_track(specs, config=self.config,
                                  provider=self.provider, track_id=track_id)
        logger.info("Asset track built", extra={"context": {
            "clips": track.n_clips,
            "layouts": sorted({c.layout.kind for c in track.clips}),
            "kinds": sorted({c.kind for c in track.clips})}})
        return track

    # ------------------------------------------------------------ resolver (C9)
    def build_resolver(
        self,
        *,
        providers=None,
        catalog: AssetCatalog | None = None,
        library_dir: Path | str | None = None,
    ) -> AssetResolver:
        """Assemble an :class:`AssetResolver` from a catalog / directory / providers.

        Provider order is priority: explicit ``providers`` first, then a
        ``catalog`` (local library), then a scanned ``library_dir`` (falling back
        to the configured ``resolver.library_dir``). Uses the config's ranking
        weights, acceptance floor, and per-provider limit."""
        provs = list(providers or [])
        if catalog is not None:
            provs.append(LocalLibraryProvider(catalog))
        lib = library_dir if library_dir is not None else self.config.resolver_library_dir
        if lib:
            provs.append(FileSystemProvider(lib))
        return AssetResolver(
            ProviderManager(provs), weights=self.config.resolver_weights,
            min_score=self.config.resolver_min_score,
            per_provider_limit=self.config.resolver_per_provider_limit)

    def resolve_slots(
        self,
        slots,
        *,
        frame_width: int = 1080,
        frame_height: int = 1920,
        resolver: AssetResolver | None = None,
        catalog: AssetCatalog | None = None,
        library_dir: Path | str | None = None,
        providers=None,
        strict: bool = True,
        track_id: str = "assets",
    ) -> tuple[AssetTrack, list[Resolution]]:
        """Satisfy Scene-Planner ``AssetSlot`` requests from providers → AssetTrack.

        Each slot is resolved (query → candidates → ranking → selection); the
        chosen asset becomes an :class:`AssetSpec` honouring the slot's layout,
        window, and z-order (sided layouts alternate halves by z-index). Returns
        the assembled :class:`AssetTrack` and the per-slot :class:`Resolution`
        list. With ``strict`` (default), an unsatisfied *required* slot raises
        :class:`AssetResolutionError` — enforcing "no missing assets"."""
        resolver = resolver or self.build_resolver(
            providers=providers, catalog=catalog, library_dir=library_dir)
        resolutions: list[Resolution] = []
        specs: list[AssetSpec] = []
        for slot in slots:
            res = resolver.resolve_slot(slot, frame_width=frame_width,
                                        frame_height=frame_height)
            resolutions.append(res)
            if res.satisfied:
                specs.append(self._spec_from(slot, res))
            elif strict and getattr(slot, "required", True):
                raise AssetResolutionError(
                    f"No asset found for required slot {getattr(slot, 'slot_id', '?')!r} "
                    f"(kind={getattr(slot, 'kind', '?')}, hint={getattr(slot, 'hint', '')!r})")
        track = build_asset_track(specs, config=self.config,
                                  provider=self.provider, track_id=track_id)
        satisfied = sum(1 for r in resolutions if r.satisfied)
        logger.info("Asset slots resolved", extra={"context": {
            "slots": len(resolutions), "satisfied": satisfied, "clips": track.n_clips,
            "providers": resolver.manager.names}})
        return track, resolutions

    @staticmethod
    def _spec_from(slot, resolution: Resolution) -> AssetSpec:
        """Map a satisfied slot + its selected candidate to an :class:`AssetSpec`."""
        cand = resolution.candidate
        layout = getattr(slot, "layout", None)
        params: dict = {}
        if layout in _SIDED_LAYOUTS:              # alternate halves so pairs don't overlap
            params["side"] = "left" if getattr(slot, "z_index", 0) % 2 == 0 else "right"
        kind = cand.kind if cand.kind in ASSET_KINDS else None
        return AssetSpec(
            path=cand.path, start_s=slot.start_s, end_s=slot.end_s, kind=kind,
            layout=layout, layout_params=params, z_index=getattr(slot, "z_index", 0),
            clip_id=getattr(slot, "slot_id", None))
