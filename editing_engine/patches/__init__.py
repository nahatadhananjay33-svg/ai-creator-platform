"""Immutable patch operations (Phase C11)."""
from __future__ import annotations

from editing_engine.patches.base import Patch
from editing_engine.patches.operations import (
    CaptionPatch,
    DeleteScenePatch,
    DurationPatch,
    InsertScenePatch,
    MoveScenePatch,
    MusicPatch,
    RegenerateScenePatch,
    ReplaceAssetPatch,
    ReplaceNarrationPatch,
    ThemePatch,
)

#: Every concrete patch type (for reporting / factories / tests).
PATCH_TYPES = (
    InsertScenePatch, DeleteScenePatch, MoveScenePatch, ReplaceNarrationPatch,
    ReplaceAssetPatch, DurationPatch, ThemePatch, MusicPatch, CaptionPatch,
    RegenerateScenePatch,
)

__all__ = [
    "Patch",
    "InsertScenePatch",
    "DeleteScenePatch",
    "MoveScenePatch",
    "ReplaceNarrationPatch",
    "ReplaceAssetPatch",
    "DurationPatch",
    "ThemePatch",
    "MusicPatch",
    "CaptionPatch",
    "RegenerateScenePatch",
    "PATCH_TYPES",
]
