"""Review & Editing Engine facade (Phase C11).

The high-level API for the editable reel model. It generates a :class:`ReelProject`
from a prompt (via the existing AI Prompt & Storyboard Engine), applies immutable
patches, reviews a project, and lowers a project to the EXISTING Timeline IR by
reusing the Scene / Caption / Branding / Music / Asset engines. It also computes
the incremental-render plan between two timelines.

It **does not** modify the Timeline IR and **does not** touch the renderer — it
only assembles the same tracks those engines already produce, honouring the
project's edited presentation settings (theme / soundtrack / caption style).
"""
from __future__ import annotations

import dataclasses
import tempfile
from pathlib import Path

from foundation.logging import get_logger
from reel_engine.config import ReelEngineConfig
from reel_engine.interfaces.types import Timeline

from asset_engine import AssetEngine
from branding_engine import BrandingEngine
from branding_engine.assets import default_logo_path
from caption_engine import CaptionEngine, get_style
from music_engine import MusicEngine
from scene_engine import SceneEngine
from scene_engine.storyboard.types import Storyboard as SceneStoryboard
from scene_engine.timeline.builder import build_timeline as build_scene_timeline
from script_engine import ScriptEngine
from script_engine.storyboard.script import storyboard_to_script

from editing_engine.history.history import EditHistory
from editing_engine.incremental import IncrementalPlan, plan_incremental
from editing_engine.patches.base import Patch
from editing_engine.project import ReelProject
from editing_engine.review.review import ReviewReport, review_project
from editing_engine.validation.validate import apply_patch

logger = get_logger("editing_engine")


class EditingEngine:
    """Prompt -> editable ReelProject -> patches -> (existing pipeline) -> Timeline."""

    def __init__(self, *, script_engine: ScriptEngine | None = None,
                 scene_engine: SceneEngine | None = None) -> None:
        self.script_engine = script_engine or ScriptEngine()
        self.scene_engine = scene_engine or SceneEngine()

    # ------------------------------------------------------------- projects
    def new_project(
        self,
        prompt: str,
        *,
        template: str | None = None,
        provider: str | None = None,
        theme: str = "modern",
        soundtrack: str = "ambient",
        caption_kind: str = "sentence",
        caption_preset: str = "modern",
        width: int = 1080,
        height: int = 1920,
        fps: int = 30,
        creator: str = "",
        channel: str = "",
    ) -> ReelProject:
        """Generate an editable :class:`ReelProject` from a prompt (via the AI engine)."""
        storyboard = self.script_engine.generate_storyboard(
            prompt, template=template, provider=provider)
        return ReelProject(
            storyboard=storyboard, theme=theme, soundtrack=soundtrack,
            caption_kind=caption_kind, caption_preset=caption_preset,
            width=width, height=height, fps=fps, creator=creator, channel=channel)

    def project_from_storyboard(self, storyboard, **settings) -> ReelProject:
        """Wrap an existing AI storyboard into an editable project."""
        return ReelProject(storyboard=storyboard, **settings)

    # ------------------------------------------------------------- editing
    def apply(self, project: ReelProject, patch: Patch) -> ReelProject:
        """Validate + apply one patch, returning the new project."""
        return apply_patch(patch, project)

    def review(self, project: ReelProject) -> ReviewReport:
        """Deterministically review a project."""
        return review_project(project)

    def history(self, project: ReelProject) -> EditHistory:
        """Start an undoable edit history from ``project`` as the base."""
        return EditHistory(project)

    # -------------------------------------------- lower a project to a Timeline
    def plan_scene_storyboard(self, project: ReelProject) -> SceneStoryboard:
        """Lower the project's AI storyboard to the deterministic Scene-Planner
        Storyboard (reusing the Scene Engine — no planning logic duplicated)."""
        script = storyboard_to_script(project.storyboard)
        return self.scene_engine.plan(
            script, title=project.storyboard.title,
            creator=project.creator, channel=project.channel)

    def build_timeline(
        self,
        project: ReelProject,
        *,
        with_branding: bool = True,
        with_music: bool = True,
        with_assets: bool = False,
        asset_library: Path | str | None = None,
        asset_dir: Path | str | None = None,
        sample_rate: int | None = None,
    ) -> tuple[SceneStoryboard, Timeline]:
        """Assemble the full Timeline IR from a project (reusing every engine).

        Captions come from the project's caption kind + style; branding from its
        theme; music from its soundtrack; visual assets are resolved from an
        optional local library. Returns ``(scene_storyboard, timeline)``. The
        Timeline IR and renderer are unchanged — this only stacks native tracks."""
        scene_sb = self.plan_scene_storyboard(project)
        # sentence/static captions come from the Scene Engine's per-scene track;
        # word/karaoke need per-word timings, so those route through the Caption
        # Engine over the full narration (both are valid native caption tracks).
        if project.caption_kind in ("word", "karaoke"):
            timeline = build_scene_timeline(
                scene_sb, width=project.width, height=project.height,
                fps=project.fps, with_captions=False)
            text = " ".join(s.narration for s in project.storyboard.scenes)
            captions = CaptionEngine().generate(
                text=text, duration_s=scene_sb.duration_s,
                kind=project.caption_kind, preset=project.caption_preset)
            timeline = dataclasses.replace(timeline, caption_tracks=(captions,))
        else:
            timeline = build_scene_timeline(
                scene_sb, width=project.width, height=project.height, fps=project.fps,
                with_captions=True, caption_kind=project.caption_kind,
                caption_style=get_style(project.caption_preset))

        if with_assets and asset_library is not None:
            slots = list(scene_sb.all_asset_slots)
            if slots:
                track, _res = AssetEngine().resolve_slots(
                    slots, frame_width=project.width, frame_height=project.height,
                    library_dir=asset_library, strict=False)
                if track.n_clips:
                    timeline = dataclasses.replace(timeline, asset_tracks=(track,))

        if with_branding:
            branding = BrandingEngine().generate(
                reel_duration_s=scene_sb.duration_s, theme=project.theme,
                logo_path=default_logo_path(),
                creator=project.creator or "Creator", channel=project.channel)
            timeline = dataclasses.replace(timeline, branding=branding)

        if with_music:
            sr = sample_rate or ReelEngineConfig().render.audio_sample_rate
            work = Path(asset_dir) if asset_dir is not None else Path(tempfile.mkdtemp())
            music = MusicEngine().generate_for_timeline(
                timeline, soundtrack=project.soundtrack, sample_rate=sr, asset_dir=work)
            timeline = dataclasses.replace(timeline, music_tracks=(music,))

        logger.info("Project lowered to timeline", extra={"context": {
            "revision": project.revision, "scenes": timeline.n_scenes,
            "theme": project.theme, "soundtrack": project.soundtrack,
            "captions": timeline.has_captions}})
        return scene_sb, timeline

    # ----------------------------------------------------------- incremental
    def incremental_plan(self, old: Timeline, new: Timeline) -> IncrementalPlan:
        """Compute which scenes changed between two timelines (only-render-diffs)."""
        return plan_incremental(old, new)
