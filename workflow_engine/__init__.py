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

M1 exposes the core model + executor; the concrete engine stages (M2) and the
:class:`WorkflowEngine` facade are re-exported here once they land.
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
from workflow_engine.execution import RunJournal, WorkflowExecutor

__version__ = "1.0.0"

__all__ = [
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
]
