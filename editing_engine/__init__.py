"""Review & Editing Engine (Phase C11) — the editable, human-in-the-loop model.

Lets a user modify AI-generated content **without rebuilding the whole reel**.
This phase defines the editable *model* a future Creator Studio will drive — there
is NO graphical UI here. Edits are **immutable patch operations** over a
:class:`ReelProject` (the AI storyboard + presentation settings); each patch
validates before it applies and yields a NEW project. A project is lowered to the
EXISTING Timeline IR by reusing the Scene / Caption / Branding / Music / Asset
engines — the Timeline IR and the renderer are untouched.

    prompt -> AI Storyboard -> Review -> Patch Set -> Scene Engine -> Timeline -> MP4

Incremental rendering: the existing Timeline per-scene hashes are diffed so a
future renderer can re-render only the changed scenes.

Public API:
- :class:`EditingEngine` — the facade (new project, apply, review, build, incremental)
- :class:`ReelProject` — the immutable editable document
- the patch types (`InsertScenePatch`, `MoveScenePatch`, `ThemePatch`, …)
- :func:`apply_patch` / :class:`PatchError` — safe application + errors
- :class:`EditHistory` — undo/redo/replay
- :func:`review_project` / :class:`ReviewReport` — the review step
- :func:`plan_incremental` / :class:`IncrementalPlan` — the incremental-render plan
"""
from __future__ import annotations

from editing_engine.engine import EditingEngine
from editing_engine.history.history import EditHistory
from editing_engine.incremental import IncrementalPlan, plan_incremental
from editing_engine.patches import (
    PATCH_TYPES,
    CaptionPatch,
    DeleteScenePatch,
    DurationPatch,
    InsertScenePatch,
    MoveScenePatch,
    MusicPatch,
    Patch,
    RegenerateScenePatch,
    ReplaceAssetPatch,
    ReplaceNarrationPatch,
    ThemePatch,
)
from editing_engine.project import ReelProject
from editing_engine.review.review import ReviewFinding, ReviewReport, review_project
from editing_engine.validation.validate import (
    PatchError,
    apply_patch,
    validate_patch,
    validate_project,
)

__version__ = "1.0.0"

__all__ = [
    "EditingEngine",
    "ReelProject",
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
    "apply_patch",
    "validate_patch",
    "validate_project",
    "PatchError",
    "EditHistory",
    "review_project",
    "ReviewReport",
    "ReviewFinding",
    "plan_incremental",
    "IncrementalPlan",
]
