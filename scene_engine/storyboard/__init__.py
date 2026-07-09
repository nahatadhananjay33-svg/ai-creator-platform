"""Storyboard IR package (Phase C7) — the frozen plan contract.

Re-exports the immutable storyboard dataclasses and the plain-dict serializer.
The types are the stable format the deterministic planner emits today and a
future AI Script Engine will emit tomorrow.
"""
from __future__ import annotations

from scene_engine.storyboard.serde import (
    storyboard_from_dict,
    storyboard_to_dict,
    storyboard_to_json,
)
from scene_engine.storyboard.types import (
    SCENE_TYPES,
    SLOT_KINDS,
    STORYBOARD_SCHEMA_VERSION,
    AssetSlot,
    AvatarSlot,
    BrandingSlot,
    CaptionSlot,
    NarrationPlan,
    ScenePlan,
    SceneType,
    Storyboard,
    TimingPlan,
    VisualPlan,
)

__all__ = [
    "STORYBOARD_SCHEMA_VERSION",
    "SCENE_TYPES",
    "SLOT_KINDS",
    "SceneType",
    "NarrationPlan",
    "TimingPlan",
    "AvatarSlot",
    "AssetSlot",
    "CaptionSlot",
    "BrandingSlot",
    "VisualPlan",
    "ScenePlan",
    "Storyboard",
    "storyboard_to_dict",
    "storyboard_to_json",
    "storyboard_from_dict",
]
