"""Workflow Engine core (Phase C14) — the deterministic orchestration primitives.

Pure, engine-agnostic building blocks: immutable :class:`Artifact` values, the
immutable :class:`WorkflowStage`, the :class:`WorkflowContext` artifact store, the
:class:`DependencyGraph`, and the :class:`Workflow` / :class:`WorkflowResult`
containers. Nothing here knows about voice, avatars, timelines, or rendering — the
concrete engine stages live in :mod:`workflow_engine.stages`.
"""
from __future__ import annotations

from workflow_engine.core.artifact import (
    KIND_FILE,
    KIND_FILESET,
    KIND_JSON,
    KIND_PROJECT,
    KIND_STORYBOARD,
    KIND_TIMELINE,
    Artifact,
    canonical_json,
    hash_files,
    hash_json,
)
from workflow_engine.core.context import WorkflowContext
from workflow_engine.core.graph import DependencyGraph, GraphError
from workflow_engine.core.stage import (
    SATISFIED_STATUSES,
    StageResult,
    StageStatus,
    WorkflowStage,
)
from workflow_engine.core.workflow import Workflow, WorkflowResult

__all__ = [
    "Artifact",
    "canonical_json",
    "hash_json",
    "hash_files",
    "KIND_STORYBOARD",
    "KIND_PROJECT",
    "KIND_TIMELINE",
    "KIND_JSON",
    "KIND_FILE",
    "KIND_FILESET",
    "WorkflowStage",
    "StageStatus",
    "StageResult",
    "SATISFIED_STATUSES",
    "WorkflowContext",
    "DependencyGraph",
    "GraphError",
    "Workflow",
    "WorkflowResult",
]
