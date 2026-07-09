"""Scene & Storyboard Planning Engine (Phase C7) — deterministic scene planning.

Transforms a finished **script** into a **Storyboard** (an ordered plan of typed
scenes with narration, timing, and visual slots) and lowers it into the existing
Timeline IR. Fully deterministic and rule-based: NO GPT/Gemini/Claude, NO script
generation, NO AI scene planning, NO asset retrieval — those belong to later
phases. The Storyboard shape is frozen so a future AI Script Engine emits the
very same format.

Pipeline:  script -> segment -> classify -> time -> plan visuals -> Storyboard
           -> Timeline IR (scenes + captions) -> existing pipeline -> MP4

Scope (Phase C7): deterministic Storyboard & scene planning ONLY. The planner
emits :class:`AssetSlot` *requests*; the Visual Asset Engine satisfies them later.

Public API:
- :class:`SceneEngine` — the facade (script -> Storyboard -> Timeline)
- :func:`plan_storyboard` — the pure planner (script -> Storyboard)
- :func:`build_timeline` — lower a Storyboard to the Timeline IR
- :class:`Storyboard` / :class:`ScenePlan` / :class:`SceneType` and the slot types
- :class:`SceneEngineConfig` / :func:`load_scene_engine_config` — configuration
"""
from __future__ import annotations

from scene_engine.config.settings import SceneEngineConfig, load_scene_engine_config
from scene_engine.engine import SceneEngine
from scene_engine.planner.planner import plan_storyboard
from scene_engine.storyboard.types import (
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
from scene_engine.timeline.builder import (
    asset_slot_windows,
    build_caption_track,
    build_timeline,
)

__version__ = "1.0.0"

__all__ = [
    "SceneEngine",
    "SceneEngineConfig",
    "load_scene_engine_config",
    "plan_storyboard",
    "build_timeline",
    "build_caption_track",
    "asset_slot_windows",
    "Storyboard",
    "ScenePlan",
    "SceneType",
    "NarrationPlan",
    "TimingPlan",
    "AvatarSlot",
    "AssetSlot",
    "CaptionSlot",
    "BrandingSlot",
    "VisualPlan",
]
