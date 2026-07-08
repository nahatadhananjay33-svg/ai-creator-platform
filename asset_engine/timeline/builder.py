"""AssetSpec list -> AssetTrack builder (Phase C6).

Lowers authoring :class:`AssetSpec` requests into the frozen Timeline IR
:class:`AssetTrack`. This is where config defaults fill unset fields (layout,
animation, duration, opacity) and the provider resolves each spec to a concrete
local file. Pure and deterministic apart from the provider's filesystem check;
the result is validated by the Timeline validator before rendering.
"""
from __future__ import annotations

from reel_engine.interfaces.types import (
    AssetAnimation,
    AssetClip,
    AssetCrop,
    AssetLayout,
    AssetTrack,
    AssetTransition,
)

from asset_engine.config.settings import AssetEngineConfig
from asset_engine.providers.base import AssetProvider, AssetSpec, LocalAssetProvider


def _crop(spec: AssetSpec) -> AssetCrop:
    if not spec.crop:
        return AssetCrop()
    x, y, w, h = spec.crop
    return AssetCrop(x=x, y=y, w=w, h=h)


def _layout(spec: AssetSpec, cfg: AssetEngineConfig) -> AssetLayout:
    kind = spec.layout or cfg.default_layout
    params = dict(spec.layout_params or {})
    # PIP defaults come from config unless the spec overrides them.
    if kind == "picture_in_picture":
        params.setdefault("scale", cfg.pip_scale)
        params.setdefault("corner", cfg.pip_corner)
        params.setdefault("margin", cfg.pip_margin)
    return AssetLayout(kind=kind, **params)


def build_asset_track(
    specs: list[AssetSpec],
    *,
    config: AssetEngineConfig | None = None,
    provider: AssetProvider | None = None,
    track_id: str = "assets",
) -> AssetTrack:
    """Resolve and assemble a validated-shape :class:`AssetTrack` from specs."""
    cfg = config or AssetEngineConfig()
    provider = provider or LocalAssetProvider()
    clips: list[AssetClip] = []
    for i, spec in enumerate(specs):
        source = provider.resolve(spec)
        kind = spec.kind or source.meta.get("asset_kind", "image")
        end_s = spec.end_s if spec.end_s else spec.start_s + cfg.default_duration_s
        dur = spec.animation_duration_s if spec.animation_duration_s is not None \
            else cfg.animation_duration_s
        clips.append(AssetClip(
            clip_id=spec.clip_id or f"asset-{i:03d}",
            kind=kind, source=source, start_s=spec.start_s, end_s=end_s,
            layout=_layout(spec, cfg), crop=_crop(spec),
            animation_in=AssetAnimation(spec.animation_in or cfg.animation_in, dur),
            animation_out=AssetAnimation(spec.animation_out or cfg.animation_out, dur),
            transition=AssetTransition(spec.transition or cfg.transition),
            opacity=spec.opacity if spec.opacity is not None else cfg.overlay_opacity,
            z_index=spec.z_index,
        ))
    return AssetTrack(track_id=track_id, clips=tuple(clips))
