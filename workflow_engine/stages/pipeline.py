"""The default production pipeline (Phase C14) — wire the engine stages into a DAG.

:func:`build_default_workflow` assembles the standard prompt-to-export pipeline as
a dependency graph (not a straight line): after the storyboard, the scene-plan /
voice / asset branches run independently and rejoin at the render, which is what
lets the executor schedule independent stages in parallel and reuse unaffected
branches on an incremental rebuild.

    storyboard ─┬─► scene_plan ─► assets ─► media_intel ─► editing ─► timeline ─┐
                └─► voice ─► avatar ───────────────────────────────► render ◄──┘
                                                                        └─► export

The single source of truth for reel-wide presentation settings is the
:class:`Presentation` value threaded to every stage that builds a project, so the
branches never disagree.
"""
from __future__ import annotations

from workflow_engine.core.workflow import Workflow
from workflow_engine.stages.base import Presentation
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


def build_default_workflow(
    prompt: str,
    *,
    template: str = "",
    provider: str = "mock",
    presentation: Presentation | None = None,
    voice_model: str = "mock",
    language: str = "en",
    renderer: str = "mock",
    profiles: tuple[str, ...] = ("reel_9x16", "square_1x1"),
    assets: tuple = DEFAULT_ASSETS,
    apply_media: bool = True,
    extra_patches: tuple = (),
    with_branding: bool = True,
    with_music: bool = True,
    with_assets: bool = False,
    name: str = "reel_production",
) -> Workflow:
    """Build the standard prompt -> export pipeline as an immutable :class:`Workflow`."""
    pres = presentation or Presentation()
    stages = [
        StoryboardStage(name="storyboard", produces=("storyboard",),
                        prompt=prompt, template=template, provider=provider),
        ScenePlanningStage(name="scene_plan", needs=("storyboard",),
                           produces=("scene_plan",), presentation=pres),
        VoiceStage(name="voice", needs=("storyboard",), produces=("voice",),
                   model=voice_model, language=language),
        AvatarStage(name="avatar", needs=("voice",), produces=("avatar",)),
        AssetsStage(name="assets", needs=("scene_plan",), produces=("assets",),
                    assets=assets),
        MediaIntelligenceStage(name="media_intel", needs=("storyboard", "assets"),
                               produces=("media_plan",), presentation=pres,
                               language=language),
        EditingStage(name="editing", needs=("storyboard", "media_intel"),
                     produces=("project",), presentation=pres,
                     apply_media=apply_media, extra_patches=tuple(extra_patches)),
        TimelineStage(name="timeline",
                      needs=("editing",) + (("assets",) if with_assets else ()),
                      produces=("timeline",), with_branding=with_branding,
                      with_music=with_music, with_assets=with_assets),
        RenderStage(name="render", needs=("timeline", "avatar"), produces=("master",),
                    renderer=renderer, profiles=tuple(profiles)),
        ExportStage(name="export", needs=("render",), produces=("exports",)),
    ]
    return Workflow(name, stages)
