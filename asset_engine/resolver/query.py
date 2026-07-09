"""AssetSlot → AssetQuery (Phase C9).

Turns a Scene-Planner ``AssetSlot`` into the deterministic :class:`AssetQuery` the
providers search and the ranker scores against. The slot is read structurally
(by attribute) so the Asset Engine never has to import the Scene Engine — any
object with ``kind``/``hint``/``layout``/``start_s``/``end_s``/``z_index`` works.

The one derived quantity is the on-screen **region** the asset fills: the slot's
layout is resolved (via the renderer-side geometry) to a placement rectangle,
and the frame size turns that into a target aspect ratio and a minimum pixel
size. Tags come from the slot's keyword hint. All pure and deterministic.
"""
from __future__ import annotations

from reel_engine.render.assets import resolve_layout

from asset_engine.catalog.index import tokenize_tags
from asset_engine.catalog.types import AssetQuery
from asset_engine.layout.presets import make_layout


def region_of(layout_name: str, frame_width: int, frame_height: int) -> tuple:
    """The pixel ``(width, height)`` an asset with ``layout_name`` fills.

    Falls back to full-frame for an unknown layout (defensive; the validator
    already rejects bad layouts upstream)."""
    try:
        placement = resolve_layout(make_layout(layout_name or "full_screen"))
    except ValueError:
        placement = resolve_layout(make_layout("full_screen"))
    w = max(1.0, placement.w * frame_width)
    h = max(1.0, placement.h * frame_height)
    return w, h


def build_query(slot, *, frame_width: int = 1080, frame_height: int = 1920) -> AssetQuery:
    """Build the deterministic :class:`AssetQuery` for one ``AssetSlot``."""
    kind = getattr(slot, "kind", "image") or "image"
    hint = getattr(slot, "hint", "") or ""
    layout_name = getattr(slot, "layout", "full_screen") or "full_screen"
    rw, rh = region_of(layout_name, frame_width, frame_height)
    duration = float(getattr(slot, "duration_s", 0.0)) if kind == "video" else 0.0
    return AssetQuery(
        kind=kind,
        tags=tokenize_tags(hint),
        target_aspect=round(rw / rh, 6),
        target_duration_s=round(duration, 3),
        min_width=int(rw),
        min_height=int(rh),
        slot_id=getattr(slot, "slot_id", ""),
    )
