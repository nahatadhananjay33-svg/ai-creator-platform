"""Creator Studio view models (Phase C12) — the presentation-only data shapes.

The Creator Studio is an **interface layer only**: it never contains business
logic that already lives in the Editing Engine. These frozen dataclasses are the
*view models* a graphical front-end (web / desktop) renders — one per panel, plus
a single :class:`StudioView` that aggregates a whole-screen snapshot. They carry
NO behaviour: they are computed from a :class:`~editing_engine.ReelProject`, its
lowered Timeline, the :class:`~editing_engine.EditHistory`, and the incremental
plan, all owned by the engine. Because every field is derived deterministically,
the same session state always yields the same view — the basis for the hermetic
UI tests.

Nothing here mutates a project, builds a patch, or touches the renderer; the
:class:`~creator_studio.session.StudioSession` does the driving and this module
only *describes* what the user would see.
"""
from __future__ import annotations

from dataclasses import dataclass, field


# ------------------------------------------------------------- command results
@dataclass(frozen=True)
class CommandResult:
    """The outcome of one Studio command (an edit or a navigation action).

    Every edit command builds an immutable ``Patch`` and routes it through
    ``EditingEngine.apply_patch`` (via the :class:`EditHistory`). On success
    ``ok`` is True, ``patch`` is the applied patch (``None`` for navigation
    commands), and ``revision`` is the resulting project revision. On a
    validation failure ``ok`` is False, ``problems`` carries every message the
    engine surfaced, and the session state is left completely unchanged."""

    ok: bool
    message: str
    revision: int
    patch_op: str = ""
    patch_describe: str = ""
    problems: tuple[str, ...] = ()


# --------------------------------------------------------------- project manager
@dataclass(frozen=True)
class ProjectInfo:
    """Project Manager: identity, current revision indicator, and dirty state."""

    title: str
    revision: int
    base_revision: int
    n_scenes: int
    duration_s: float
    theme: str
    soundtrack: str
    caption_kind: str
    caption_preset: str
    width: int
    height: int
    fps: int
    dirty: bool                          # edited since last save
    path: str | None                     # backing file, if saved/opened from disk
    provider: str


# ------------------------------------------------------------- storyboard panel
@dataclass(frozen=True)
class SceneRow:
    """One editable storyboard scene (the reorderable/selectable unit)."""

    index: int
    narration: str
    preview: str                         # truncated narration for a compact list
    scene_type: str
    asset_type: str
    layout: str
    duration_estimate_s: float
    word_count: int
    cta: bool
    selected: bool


@dataclass(frozen=True)
class StoryboardPanel:
    """Scene list with selection — supports insert / delete / drag-reorder."""

    scenes: tuple[SceneRow, ...]
    n_scenes: int
    selected_index: int


# --------------------------------------------------------------- timeline view
@dataclass(frozen=True)
class TimelineBar:
    """One rendered scene as a visual bar, with its incremental-render status.

    ``status`` is ``"reused"`` (byte-identical, render cached), ``"changed"``
    (must re-render), or ``"base"`` (no baseline to diff against). ``cacheable``
    means the scene's render exists somewhere in the baseline (e.g. moved by a
    reorder) so it can be reused from cache even when it is not at the same
    position."""

    index: int
    scene_id: str
    start_s: float
    end_s: float
    duration_s: float
    status: str
    cacheable: bool
    selected: bool


@dataclass(frozen=True)
class TimelinePanel:
    """Visual scene bars, a playhead, and the reel dimensions."""

    bars: tuple[TimelineBar, ...]
    total_duration_s: float
    playhead_s: float
    playhead_scene: int
    fps: int
    width: int
    height: int
    aspect: str


# --------------------------------------------------------------- inspector panel
@dataclass(frozen=True)
class InspectorPanel:
    """Editable properties of the selected scene + reel-wide presentation.

    The scene fields drive narration / duration / asset patches; the
    presentation fields drive theme / music / caption patches. The ``*_options``
    tuples are the exact valid value sets the engines accept (so the UI can only
    offer choices a patch would accept), pulled straight from those engines."""

    scene_index: int
    narration: str
    duration_estimate_s: float
    scene_type: str
    asset_type: str
    layout: str
    # reel-wide presentation
    theme: str
    soundtrack: str
    caption_kind: str
    caption_preset: str
    captions_enabled: bool
    # option lists (from the owning engines)
    theme_options: tuple[str, ...]
    soundtrack_options: tuple[str, ...]
    caption_kind_options: tuple[str, ...]
    caption_preset_options: tuple[str, ...]
    asset_kind_options: tuple[str, ...]
    asset_layout_options: tuple[str, ...]
    scene_type_options: tuple[str, ...]


# ----------------------------------------------------- incremental regeneration
@dataclass(frozen=True)
class IncrementalPanel:
    """Incremental regeneration plan: reused vs regenerated scenes + cache stats.

    Indices refer to the current timeline. ``scene_status`` is a per-scene label
    (``reused`` / ``changed``) aligned to the timeline bars. The cache statistics
    summarise how much work an incremental renderer would skip."""

    total: int
    changed: tuple[int, ...]
    reused: tuple[int, ...]
    cacheable: tuple[int, ...]
    overlays_changed: bool
    needs_render: bool
    reuse_fraction: float
    n_changed: int
    n_reused: int
    scene_status: tuple[str, ...]
    # cache statistics
    cache_hits: int                      # scenes served from cache (reused)
    cache_misses: int                    # scenes that must be re-rendered (changed)
    cacheable_hits: int                  # renders reusable from anywhere in cache


# ------------------------------------------------------------------- history
@dataclass(frozen=True)
class HistoryEntry:
    """One applied patch in the audit trail."""

    revision: int
    op: str
    describe: str
    current: bool                        # is the undo cursor at this entry?


@dataclass(frozen=True)
class HistoryPanel:
    """Undo/redo state + the patch timeline (deterministically replayable)."""

    entries: tuple[HistoryEntry, ...]
    can_undo: bool
    can_redo: bool
    n_patches: int
    cursor: int                          # index of the current entry (-1 == base)


# ----------------------------------------------------------------- preview player
@dataclass(frozen=True)
class PreviewPanel:
    """Preview Player: the current render, playback state, and seek offsets.

    ``media_path`` is the last render produced for the current project (``None``
    until :meth:`StudioSession.preview` is called or after an edit invalidates
    it). ``scene_offsets`` are the absolute start times of each rendered scene,
    so the UI can seek to a scene boundary. Playback state is pure and
    deterministic (no real clock)."""

    media_path: str | None
    audio_path: str | None
    captions_path: str | None
    renderer: str
    duration_s: float
    playhead_s: float
    playing: bool
    current_scene: int
    scene_offsets: tuple[float, ...]
    ready: bool                          # media matches the current project revision


# --------------------------------------------------------------- whole screen
@dataclass(frozen=True)
class StudioView:
    """A complete, deterministic snapshot of the Creator Studio screen."""

    project: ProjectInfo
    storyboard: StoryboardPanel
    timeline: TimelinePanel
    inspector: InspectorPanel
    incremental: IncrementalPanel
    history: HistoryPanel
    preview: PreviewPanel
