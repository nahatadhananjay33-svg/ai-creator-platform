"""Creator Studio (Phase C12) — the deterministic visual editor, interface layer.

The first graphical Creator Studio for the AI Creator Platform, built **on top of**
the Editing Engine as an interface layer only. It contains no business logic that
already lives in the engine:

- the **Editing Engine is the single source of truth**; the Studio never mutates a
  :class:`~editing_engine.ReelProject` — every user action builds an immutable
  ``Patch`` and routes it through ``EditingEngine.apply_patch``;
- the **Timeline IR is unchanged** and the **renderer is unchanged** — the Studio
  lowers a project with ``EditingEngine.build_timeline`` and renders with the
  existing ``mock`` / ``ffmpeg`` backends;
- everything is **deterministic**: the same command sequence yields the same
  views and the same rendered bytes.

    open ─► storyboard/timeline ─► edit (patches) ─► incremental plan ─► preview ─► export

Public API:
- :class:`StudioSession` — the UI controller (open/save, edit commands, undo/redo,
  preview, export, and a whole-screen :class:`StudioView`)
- the panel view models (:class:`StudioView` and its panels)
- :func:`save_project` / :func:`load_project` — Project Manager persistence
"""
from __future__ import annotations

from creator_studio.project_io import (
    load_project,
    project_from_dict,
    project_from_json,
    project_to_dict,
    project_to_json,
    save_project,
)
from creator_studio.session import StudioSession
from creator_studio.viewmodels import (
    CommandResult,
    HistoryEntry,
    HistoryPanel,
    IncrementalPanel,
    InspectorPanel,
    PreviewPanel,
    ProjectInfo,
    SceneRow,
    StoryboardPanel,
    StudioView,
    TimelineBar,
    TimelinePanel,
)

__version__ = "1.0.0"

__all__ = [
    "StudioSession",
    "StudioView",
    "CommandResult",
    "ProjectInfo",
    "StoryboardPanel",
    "SceneRow",
    "TimelinePanel",
    "TimelineBar",
    "InspectorPanel",
    "IncrementalPanel",
    "HistoryPanel",
    "HistoryEntry",
    "PreviewPanel",
    "save_project",
    "load_project",
    "project_to_dict",
    "project_from_dict",
    "project_to_json",
    "project_from_json",
]
