"""Workflow Engine (Phase C14) — the deterministic production orchestrator.

The single execution layer for the AI Creator Platform. It composes the EXISTING
engines — AI Storyboard, Scene Planning, Voice, Avatar, Assets, Media Intelligence,
Editing, the Timeline IR, the Renderer, and Export — into one deterministic,
resumable, content-addressed pipeline. It changes **no** engine: every stage only
invokes existing public APIs, and the Timeline IR and renderer are untouched.

    prompt ─► Storyboard ─► Scene Planning ─► Voice ─► Avatar ─► Assets
           ─► Media Intelligence ─► Editing ─► Timeline ─► Renderer ─► Export

Design in one line: **stages are immutable values, artifacts are content-addressed,
and a stage is re-run only when the content of its inputs changes** — which gives
resume, retry, and incremental rebuild from a single caching rule.

Public API:
- :class:`WorkflowEngine` — the facade (build the default pipeline, run, resume, rebuild)
- :func:`build_default_workflow` — the standard prompt-to-export pipeline
- :class:`Workflow` / :class:`WorkflowResult` — the DAG description + a run's outcome
- :class:`WorkflowStage` / :class:`WorkflowContext` / :class:`Artifact` — the core model
- :class:`WorkflowExecutor` — the deterministic run/resume/retry/incremental engine
- :class:`Presentation` + the ten concrete engine stages
"""
from __future__ import annotations

from workflow_engine.core import (
    Artifact,
    DependencyGraph,
    GraphError,
    StageResult,
    StageStatus,
    Workflow,
    WorkflowContext,
    WorkflowResult,
    WorkflowStage,
)
from workflow_engine.engine import WorkflowEngine
from workflow_engine.execution import RunJournal, WorkflowExecutor
from workflow_engine.stages import (
    DEFAULT_ASSETS,
    AssetsStage,
    AvatarStage,
    EditingStage,
    ExportStage,
    MediaIntelligenceStage,
    Presentation,
    RenderStage,
    ScenePlanningStage,
    StoryboardStage,
    TimelineStage,
    VoiceStage,
    build_default_workflow,
)

__version__ = "1.0.0"

__all__ = [
    "WorkflowEngine",
    "build_default_workflow",
    "Workflow",
    "WorkflowResult",
    "WorkflowStage",
    "WorkflowContext",
    "WorkflowExecutor",
    "RunJournal",
    "Artifact",
    "StageStatus",
    "StageResult",
    "DependencyGraph",
    "GraphError",
    "Presentation",
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
    "DEFAULT_ASSETS",
]
