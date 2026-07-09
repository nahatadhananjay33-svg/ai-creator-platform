"""Deterministic planning rules (Phase C7) — segmentation, classification, mix.

The rule layer is where all the determinism lives: sentence/scene splitting
(:mod:`segmentation`), scene-type assignment (:mod:`classification`), the keyword
tables that drive it (:mod:`keywords`), and the per-type visual profiles
(:mod:`profiles`). No module here imports a model or touches the network.
"""
from __future__ import annotations

from scene_engine.rules.classification import (
    asset_hint,
    classify_scene,
    refine_asset_kind,
)
from scene_engine.rules.profiles import PROFILES, SceneTypeProfile, profile_for
from scene_engine.rules.segmentation import segment_scenes

__all__ = [
    "segment_scenes",
    "classify_scene",
    "refine_asset_kind",
    "asset_hint",
    "PROFILES",
    "SceneTypeProfile",
    "profile_for",
]
