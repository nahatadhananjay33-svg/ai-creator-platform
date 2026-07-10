"""Workflow Engine stages (Phase C14) — one immutable stage per existing engine.

Each stage composes exactly one shipped engine through its public API and emits
content-addressed artifacts; :func:`build_default_workflow` wires them into the
standard prompt-to-export DAG. No engine, the Timeline IR, or the renderer is
modified — the workflow only orchestrates.
"""
from __future__ import annotations

from workflow_engine.stages.base import (
    Presentation,
    base_project,
    patch_from_spec,
    patch_to_spec,
)
from workflow_engine.stages.engine_stages import (
    DEFAULT_ASSETS,
    AssetsStage,
    AvatarStage,
    EditingStage,
    ExportStage,
    MediaIntelligenceStage,
    RenderStage,
    ScenePlanningStage,
    StoryboardStage,
    TimelineStage,
    VoiceStage,
)
from workflow_engine.stages.pipeline import build_default_workflow

__all__ = [
    "Presentation",
    "base_project",
    "patch_to_spec",
    "patch_from_spec",
    "build_default_workflow",
    "DEFAULT_ASSETS",
    "StoryboardStage",
    "ScenePlanningStage",
    "VoiceStage",
    "AvatarStage",
    "AssetsStage",
    "MediaIntelligenceStage",
    "EditingStage",
    "TimelineStage",
    "RenderStage",
    "ExportStage",
]
