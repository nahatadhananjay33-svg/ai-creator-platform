"""Per-scene-type visual profiles (Phase C7).

A deterministic lookup table: given a :class:`SceneType`, what does the scene
look like by default — is the avatar on screen and how (full frame vs inset),
what asset kinds does it request, which layout do those assets use, and what
solid background colour stands in for it until real footage lands. The planner
reads this table (then refines asset kinds by keyword) to fill each scene's
:class:`VisualPlan`. Pure policy, no I/O, no model.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from scene_engine.storyboard.types import SceneType


@dataclass(frozen=True)
class SceneTypeProfile:
    """The default visual intent for one scene type."""

    avatar_present: bool
    avatar_layout: str                    # full_screen | picture_in_picture
    asset_kinds: tuple[str, ...]          # default asset slot kinds (may be empty)
    asset_layout: str                     # layout those asset slots prefer
    background: tuple                      # RGB scene background hint


#: Scene type -> its default visual profile. Backgrounds are distinct so the
#: deterministic solid-card demo makes scene structure legible at a glance.
PROFILES: dict[SceneType, SceneTypeProfile] = {
    SceneType.HOOK: SceneTypeProfile(
        True, "full_screen", (), "full_screen", (18, 22, 40)),
    SceneType.TALKING_HEAD: SceneTypeProfile(
        True, "full_screen", (), "full_screen", (24, 28, 44)),
    SceneType.EXPLANATION: SceneTypeProfile(
        True, "full_screen", (), "full_screen", (20, 24, 40)),
    SceneType.IMAGE_INSERT: SceneTypeProfile(
        True, "picture_in_picture", ("image",), "full_screen", (12, 16, 24)),
    SceneType.VIDEO_INSERT: SceneTypeProfile(
        True, "picture_in_picture", ("video",), "full_screen", (10, 14, 20)),
    SceneType.COMPARISON: SceneTypeProfile(
        True, "picture_in_picture", ("image", "image"), "side_by_side", (16, 18, 28)),
    SceneType.BULLET_LIST: SceneTypeProfile(
        True, "full_screen", (), "full_screen", (26, 20, 36)),
    SceneType.CHART: SceneTypeProfile(
        True, "picture_in_picture", ("chart",), "full_screen", (10, 20, 30)),
    SceneType.QUOTE: SceneTypeProfile(
        False, "full_screen", (), "full_screen", (30, 26, 22)),
    SceneType.CALL_TO_ACTION: SceneTypeProfile(
        True, "full_screen", (), "full_screen", (40, 20, 24)),
    SceneType.OUTRO: SceneTypeProfile(
        True, "picture_in_picture", (), "full_screen", (14, 14, 18)),
}


def profile_for(scene_type: SceneType) -> SceneTypeProfile:
    """The visual profile for ``scene_type`` (never raises; falls back to talking
    head for an unknown member, which cannot happen with the closed enum)."""
    return PROFILES.get(scene_type, PROFILES[SceneType.TALKING_HEAD])
