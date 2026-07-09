"""Creator Studio session (Phase C12) — the deterministic UI controller.

:class:`StudioSession` is the interface-layer *controller* a graphical Creator
Studio drives. It holds the UI state a front-end needs — the open project's edit
history, the selected scene, the playhead, the caption-visibility toggle, and the
last preview render — and exposes commands for every user action. It contains **no
business logic of its own**:

* every content edit builds an immutable ``Patch`` and routes it through the
  Editing Engine (``EditHistory.apply`` → ``EditingEngine.apply_patch``); the
  session never mutates a :class:`ReelProject`;
* the project is lowered to the **existing** Timeline IR via
  ``EditingEngine.build_timeline`` (renderer + IR unchanged);
* undo / redo / replay come from the engine's :class:`EditHistory`;
* the incremental plan comes from ``EditingEngine.incremental_plan``;
* preview / export go through the **existing** renderer.

Failures from the engine (invalid patches) are caught and surfaced as
:class:`CommandResult` problems — the session state is left untouched. Everything
is deterministic: the same command sequence always yields the same views and the
same rendered bytes.

Caption *visibility* is the one presentation control that is a view/compositing
option rather than a project edit: the editable model always carries a caption
``kind`` (there is no "captions off" value in the source-of-truth model), so the
toggle omits the native caption track when the Studio hands the Timeline to the
renderer. It changes rendered output but not the ``ReelProject`` (no patch, no
revision bump); the caption *style* itself (kind/preset) is a real ``CaptionPatch``.
"""
from __future__ import annotations

import dataclasses
import tempfile
from pathlib import Path

from reel_engine.interfaces.types import RenderResult, Timeline

from editing_engine import (
    CaptionPatch,
    DeleteScenePatch,
    DurationPatch,
    EditingEngine,
    InsertScenePatch,
    MoveScenePatch,
    MusicPatch,
    Patch,
    PatchError,
    RegenerateScenePatch,
    ReelProject,
    ReplaceAssetPatch,
    ReplaceNarrationPatch,
    ThemePatch,
    review_project,
)
from editing_engine.history.history import EditHistory
from editing_engine.review.review import ReviewReport

from creator_studio import panels
from creator_studio.export import default_output_path, render_timeline_to
from creator_studio.project_io import load_project, save_project
from creator_studio.viewmodels import CommandResult, StudioView


class StudioSession:
    """A single editing session over one :class:`ReelProject` (the UI controller)."""

    def __init__(
        self,
        project: ReelProject,
        *,
        engine: EditingEngine | None = None,
        renderer: str = "mock",
        with_branding: bool = True,
        with_music: bool = True,
        workspace: Path | str | None = None,
        path: Path | str | None = None,
    ) -> None:
        self._engine = engine or EditingEngine()
        self._history = EditHistory(project)
        self._base = project                      # incremental baseline (last render)
        self._renderer = renderer
        self._with_branding = with_branding
        self._with_music = with_music
        self._workspace = Path(workspace) if workspace else Path(
            tempfile.mkdtemp(prefix="studio_"))
        self._workspace.mkdir(parents=True, exist_ok=True)
        self._path: str | None = str(path) if path else None

        # UI state
        self._selected = 0
        self._playhead_s = 0.0
        self._playing = False
        self._captions_enabled = True
        self._dirty = False

        # caches (keyed by the immutable project value → stable per snapshot)
        self._timeline_cache: dict[tuple[ReelProject, bool], Timeline] = {}
        self._preview: dict | None = None         # last render for current project

    # ---------------------------------------------------------------- factories
    @classmethod
    def new(cls, prompt: str, *, engine: EditingEngine | None = None,
            renderer: str = "mock", with_branding: bool = True, with_music: bool = True,
            workspace: Path | str | None = None, **project_settings) -> "StudioSession":
        """Start a session from a prompt (generates the AI storyboard project)."""
        engine = engine or EditingEngine()
        project = engine.new_project(prompt, **project_settings)
        return cls(project, engine=engine, renderer=renderer, with_branding=with_branding,
                   with_music=with_music, workspace=workspace)

    @classmethod
    def open(cls, path: Path | str, *, engine: EditingEngine | None = None,
             renderer: str = "mock", with_branding: bool = True, with_music: bool = True,
             workspace: Path | str | None = None) -> "StudioSession":
        """Open a saved Studio project file into a new session."""
        project = load_project(path)
        return cls(project, engine=engine, renderer=renderer, with_branding=with_branding,
                   with_music=with_music, workspace=workspace, path=path)

    # ------------------------------------------------------------------- state
    @property
    def project(self) -> ReelProject:
        return self._history.current

    @property
    def history(self) -> EditHistory:
        return self._history

    @property
    def selected_index(self) -> int:
        return self._selected

    @property
    def revision(self) -> int:
        return self.project.revision

    @property
    def captions_enabled(self) -> bool:
        return self._captions_enabled

    @property
    def workspace(self) -> Path:
        return self._workspace

    # --------------------------------------------------- lowering to a Timeline
    def build_timeline(self, project: ReelProject | None = None) -> Timeline:
        """Lower a project to the existing Timeline IR (cached per snapshot).

        Respects the Studio's caption-visibility toggle by omitting the native
        caption track when captions are hidden — a compositing choice made where
        the Timeline meets the renderer; the Timeline IR and renderer are
        unchanged and the ``ReelProject`` is never touched."""
        project = project or self.project
        key = (project, self._captions_enabled)
        timeline = self._timeline_cache.get(key)
        if timeline is None:
            _, timeline = self._engine.build_timeline(
                project, with_branding=self._with_branding,
                with_music=self._with_music, asset_dir=self._workspace)
            if not self._captions_enabled:
                timeline = dataclasses.replace(timeline, caption_tracks=())
            self._timeline_cache[key] = timeline
        return timeline

    def incremental_plan(self):
        """Plan the incremental re-render from the baseline to the current project."""
        old = self.build_timeline(self._base)
        new = self.build_timeline(self.project)
        return self._engine.incremental_plan(old, new)

    def review(self) -> ReviewReport:
        """Run the deterministic review over the current project."""
        return review_project(self.project)

    # -------------------------------------------------------- selection / view
    def select_scene(self, index: int) -> CommandResult:
        """Select a storyboard scene (navigation only — no patch)."""
        n = self.project.n_scenes
        if not (0 <= index < n):
            return self._nav_error(f"scene index {index} out of range [0, {n - 1}]")
        self._selected = index
        # move the playhead to the selected scene's start for a coherent preview
        offsets = panels.scene_offsets(self.build_timeline())
        if index < len(offsets):
            self._playhead_s = offsets[index]
        return self._nav_ok(f"selected scene {index}")

    # ------------------------------------------------------ playback controls
    def play(self) -> CommandResult:
        self._playing = True
        return self._nav_ok("play")

    def pause(self) -> CommandResult:
        self._playing = False
        return self._nav_ok("pause")

    def seek(self, time_s: float) -> CommandResult:
        """Move the playhead to an absolute time (clamped to the reel)."""
        dur = self.build_timeline().duration_s
        self._playhead_s = max(0.0, min(float(time_s), dur))
        self._selected = panels.scene_at_time(self.build_timeline(), self._playhead_s)
        return self._nav_ok(f"seek {self._playhead_s:.3f}s")

    def seek_scene(self, index: int) -> CommandResult:
        """Seek the playhead to a rendered scene's start."""
        timeline = self.build_timeline()
        offsets = panels.scene_offsets(timeline)
        if not (0 <= index < len(offsets)):
            return self._nav_error(f"scene index {index} out of range")
        self._playhead_s = offsets[index]
        self._selected = index
        return self._nav_ok(f"seek to scene {index}")

    def next_scene(self) -> CommandResult:
        timeline = self.build_timeline()
        i = min(panels.scene_at_time(timeline, self._playhead_s) + 1,
                timeline.n_scenes - 1)
        return self.seek_scene(i)

    def prev_scene(self) -> CommandResult:
        timeline = self.build_timeline()
        i = max(panels.scene_at_time(timeline, self._playhead_s) - 1, 0)
        return self.seek_scene(i)

    # -------------------------------------------------- caption visibility toggle
    def toggle_captions(self) -> CommandResult:
        """Show/hide captions in the preview + export (a compositing view option).

        This is NOT a project edit: it omits the caption track when lowering to
        the renderer, so it changes the render but never the ``ReelProject`` (no
        patch, no revision bump). Changing the caption *style* is a real edit —
        see :meth:`set_caption`."""
        self._captions_enabled = not self._captions_enabled
        self._invalidate_preview()
        state = "on" if self._captions_enabled else "off"
        return self._nav_ok(f"captions {state}")

    def set_captions_enabled(self, enabled: bool) -> CommandResult:
        self._captions_enabled = bool(enabled)
        self._invalidate_preview()
        return self._nav_ok(f"captions {'on' if enabled else 'off'}")

    # ------------------------------------------------------------- edit commands
    # Storyboard panel -------------------------------------------------------
    def insert_scene(self, index: int, narration: str, scene_type: str = "explanation",
                     asset_type: str = "", layout: str = "") -> CommandResult:
        result = self._apply(InsertScenePatch(
            index, narration, scene_type=scene_type, asset_type=asset_type, layout=layout))
        if result.ok:
            self._selected = min(index, self.project.n_scenes - 1)
        return result

    def delete_scene(self, index: int) -> CommandResult:
        result = self._apply(DeleteScenePatch(index))
        if result.ok:
            self._selected = min(self._selected, self.project.n_scenes - 1)
        return result

    def move_scene(self, from_index: int, to_index: int) -> CommandResult:
        """Drag-and-drop reorder: move a scene to a new position."""
        result = self._apply(MoveScenePatch(from_index, to_index))
        if result.ok:
            self._selected = to_index
        return result

    # Inspector panel --------------------------------------------------------
    def set_narration(self, index: int, narration: str) -> CommandResult:
        return self._apply(ReplaceNarrationPatch(index, narration))

    def set_duration(self, index: int, duration_s: float) -> CommandResult:
        return self._apply(DurationPatch(index, duration_s))

    def replace_asset(self, index: int, asset_type: str = "", layout: str = "") -> CommandResult:
        return self._apply(ReplaceAssetPatch(index, asset_type=asset_type, layout=layout))

    def set_theme(self, theme: str) -> CommandResult:
        return self._apply(ThemePatch(theme))

    def set_music(self, soundtrack: str) -> CommandResult:
        return self._apply(MusicPatch(soundtrack))

    def set_caption(self, kind: str = "", preset: str = "") -> CommandResult:
        return self._apply(CaptionPatch(kind=kind, preset=preset))

    def regenerate_scene(self, index: int, *, provider: str = "mock",
                         instruction: str = "", template: str = "") -> CommandResult:
        return self._apply(RegenerateScenePatch(
            index, provider=provider, instruction=instruction, template=template))

    # ---------------------------------------------------------------- history
    def undo(self) -> CommandResult:
        if not self._history.can_undo:
            return self._nav_error("nothing to undo")
        self._history.undo()
        self._after_edit()
        return self._nav_ok(f"undo → revision {self.revision}")

    def redo(self) -> CommandResult:
        if not self._history.can_redo:
            return self._nav_error("nothing to redo")
        self._history.redo()
        self._after_edit()
        return self._nav_ok(f"redo → revision {self.revision}")

    def replay(self) -> ReelProject:
        """Deterministically replay every recorded patch from the base project."""
        return self._history.replay()

    # ---------------------------------------------------------- project manager
    def save(self, path: Path | str | None = None) -> Path:
        """Save the current project; remembers the path and clears the dirty flag."""
        target = Path(path) if path else (Path(self._path) if self._path else None)
        if target is None:
            raise ValueError("no path given and the session has no backing file")
        save_project(self.project, target)
        self._path = str(target)
        self._dirty = False
        return target

    # ------------------------------------------------------- preview & export
    def preview(self) -> dict:
        """Render the current project with the session renderer (cached per state).

        Marks the incremental baseline as the just-rendered project, so edits made
        after a preview show up as the incremental delta (a real render cache)."""
        if self._preview is not None and self._preview["revision"] == self.revision \
                and self._preview["captions"] == self._captions_enabled:
            return self._preview
        timeline = self.build_timeline()
        out = default_output_path(self._workspace, "preview", self._renderer)
        result = render_timeline_to(
            timeline, out, renderer=self._renderer,
            sample_rate=None)
        self._preview = {
            "revision": self.revision,
            "captions": self._captions_enabled,
            "media_path": str(result.output_path),
            "audio_path": str(result.audio_path) if result.audio_path else None,
            "captions_path": str(result.captions_path) if result.captions_path else None,
            "result": result,
        }
        self._base = self.project             # baseline advances to last render
        return self._preview

    def export(self, output_path: Path | str, *, renderer: str | None = None,
               export_profiles: tuple[str, ...] = ()) -> RenderResult:
        """Export the latest revision through the existing renderer (unmodified).

        A bare stem (no extension) gets the backend's container suffix (``.mp4``
        for ffmpeg, ``.avi`` for the mock proxy), so exporting always yields a
        properly-named playable master."""
        timeline = self.build_timeline()
        renderer = renderer or self._renderer
        output_path = Path(output_path)
        if not output_path.suffix:
            output_path = default_output_path(output_path.parent, output_path.name, renderer)
        return render_timeline_to(
            timeline, output_path, renderer=renderer, export_profiles=export_profiles)

    # ------------------------------------------------------------------- view
    def view(self) -> StudioView:
        """A complete, deterministic snapshot of the whole Studio screen."""
        project = self.project
        timeline = self.build_timeline()
        plan = self.incremental_plan()
        preview = self._preview
        ready = bool(preview) and preview["revision"] == self.revision \
            and preview["captions"] == self._captions_enabled
        return StudioView(
            project=panels.build_project_info(
                project, base_revision=self._base.revision,
                duration_s=timeline.duration_s, dirty=self._dirty, path=self._path),
            storyboard=panels.build_storyboard_panel(project, self._selected),
            timeline=panels.build_timeline_panel(
                timeline, selected_scene=self._selected,
                playhead_s=self._playhead_s, plan=plan),
            inspector=panels.build_inspector_panel(
                project, self._selected, self._captions_enabled),
            incremental=panels.build_incremental_panel(plan),
            history=panels.build_history_panel(self._history),
            preview=panels.build_preview_panel(
                media_path=preview["media_path"] if ready else None,
                audio_path=preview["audio_path"] if ready else None,
                captions_path=preview["captions_path"] if ready else None,
                renderer=self._renderer, timeline=timeline,
                playhead_s=self._playhead_s, playing=self._playing, ready=ready),
        )

    # --------------------------------------------------------------- internals
    def _apply(self, patch: Patch) -> CommandResult:
        """Validate + apply a patch through the engine, surfacing any failure.

        The session never mutates the project — ``EditHistory.apply`` calls
        ``EditingEngine.apply_patch`` which returns a NEW project. A ``PatchError``
        leaves the history (and all UI state) untouched."""
        try:
            self._history.apply(patch)
        except PatchError as exc:
            return CommandResult(
                ok=False, message=f"{patch.op} rejected", revision=self.revision,
                patch_op=patch.op, patch_describe=patch.describe(),
                problems=tuple(exc.problems))
        self._after_edit()
        return CommandResult(
            ok=True, message=patch.describe(), revision=self.revision,
            patch_op=patch.op, patch_describe=patch.describe())

    def _after_edit(self) -> None:
        """Shared post-edit bookkeeping (clamp selection, mark dirty, invalidate)."""
        n = self.project.n_scenes
        self._selected = max(0, min(self._selected, n - 1))
        self._dirty = True
        self._invalidate_preview()

    def _invalidate_preview(self) -> None:
        self._preview = None
        self._playhead_s = min(self._playhead_s, self.build_timeline().duration_s)

    def _nav_ok(self, message: str) -> CommandResult:
        return CommandResult(ok=True, message=message, revision=self.revision)

    def _nav_error(self, message: str) -> CommandResult:
        return CommandResult(ok=False, message=message, revision=self.revision,
                             problems=(message,))
