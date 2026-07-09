"""Concrete patch operations (Phase C11).

The deterministic edit vocabulary the objective lists — reorder / insert / delete
scenes, replace narration, replace an asset slot, change the branding theme, music
track, or caption style, adjust a scene's duration, and regenerate a single scene
through the existing AI Storyboard interface. Every patch is an immutable frozen
dataclass that validates before it applies and returns a NEW :class:`ReelProject`.
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field

from script_engine.storyboard.types import ScriptScene

from editing_engine.patches.base import (
    VALID_ASSET_KINDS,
    VALID_ASSET_LAYOUTS,
    VALID_SCENE_TYPES,
    Patch,
    _index_in_range,
    valid_caption_kinds,
    valid_caption_styles,
    valid_soundtracks,
    valid_themes,
)
from editing_engine.project import ReelProject


@dataclass(frozen=True)
class InsertScenePatch(Patch):
    """Insert a new scene at ``index`` (0..n, where n appends at the end)."""

    op = "insert_scene"
    index: int
    narration: str
    scene_type: str = "explanation"
    asset_type: str = ""
    layout: str = ""

    def validate(self, project: ReelProject) -> list[str]:
        problems: list[str] = []
        if not _index_in_range(self.index, project.n_scenes, inclusive=True):
            problems.append(f"insert index {self.index} out of range [0, {project.n_scenes}]")
        if not (self.narration and self.narration.strip()):
            problems.append("insert_scene: empty narration")
        if self.scene_type not in VALID_SCENE_TYPES:
            problems.append(f"insert_scene: unsupported scene_type {self.scene_type!r}")
        return problems

    def apply(self, project: ReelProject) -> ReelProject:
        scene = ScriptScene(narration=self.narration.strip(), scene_type=self.scene_type,
                            asset_type=self.asset_type, layout=self.layout)
        scenes = list(project.scenes)
        scenes.insert(self.index, scene)
        return project.with_scenes(scenes)

    def describe(self) -> str:
        return f"insert scene at {self.index}: {self.narration[:40]!r}"


@dataclass(frozen=True)
class DeleteScenePatch(Patch):
    """Delete the scene at ``index`` (a reel must keep at least one scene)."""

    op = "delete_scene"
    index: int

    def validate(self, project: ReelProject) -> list[str]:
        problems: list[str] = []
        if not _index_in_range(self.index, project.n_scenes):
            problems.append(f"delete index {self.index} out of range [0, {project.n_scenes - 1}]")
        if project.n_scenes <= 1:
            problems.append("delete_scene: cannot delete the only remaining scene")
        return problems

    def apply(self, project: ReelProject) -> ReelProject:
        scenes = list(project.scenes)
        del scenes[self.index]
        return project.with_scenes(scenes)

    def describe(self) -> str:
        return f"delete scene {self.index}"


@dataclass(frozen=True)
class MoveScenePatch(Patch):
    """Reorder: move the scene at ``from_index`` to ``to_index``."""

    op = "move_scene"
    from_index: int
    to_index: int

    def validate(self, project: ReelProject) -> list[str]:
        n = project.n_scenes
        problems: list[str] = []
        if not _index_in_range(self.from_index, n):
            problems.append(f"move from_index {self.from_index} out of range [0, {n - 1}]")
        if not _index_in_range(self.to_index, n):
            problems.append(f"move to_index {self.to_index} out of range [0, {n - 1}]")
        return problems

    def apply(self, project: ReelProject) -> ReelProject:
        scenes = list(project.scenes)
        scene = scenes.pop(self.from_index)
        scenes.insert(self.to_index, scene)
        return project.with_scenes(scenes)

    def describe(self) -> str:
        return f"move scene {self.from_index} -> {self.to_index}"


@dataclass(frozen=True)
class ReplaceNarrationPatch(Patch):
    """Replace the narration text of the scene at ``index``."""

    op = "replace_narration"
    index: int
    narration: str

    def validate(self, project: ReelProject) -> list[str]:
        problems: list[str] = []
        if not _index_in_range(self.index, project.n_scenes):
            problems.append(f"replace_narration index {self.index} out of range")
        if not (self.narration and self.narration.strip()):
            problems.append("replace_narration: empty narration")
        return problems

    def apply(self, project: ReelProject) -> ReelProject:
        scenes = list(project.scenes)
        scenes[self.index] = dataclasses.replace(
            scenes[self.index], narration=self.narration.strip())
        return project.with_scenes(scenes)

    def describe(self) -> str:
        return f"replace narration of scene {self.index}"


@dataclass(frozen=True)
class ReplaceAssetPatch(Patch):
    """Change the suggested asset slot (kind and/or layout) of scene ``index``."""

    op = "replace_asset"
    index: int
    asset_type: str = ""                 # "" leaves it unchanged
    layout: str = ""                     # "" leaves it unchanged

    def validate(self, project: ReelProject) -> list[str]:
        problems: list[str] = []
        if not _index_in_range(self.index, project.n_scenes):
            problems.append(f"replace_asset index {self.index} out of range")
        if self.asset_type and self.asset_type not in VALID_ASSET_KINDS:
            problems.append(f"replace_asset: unknown asset_type {self.asset_type!r}")
        if self.layout and self.layout not in VALID_ASSET_LAYOUTS:
            problems.append(f"replace_asset: unknown layout {self.layout!r}")
        if not self.asset_type and not self.layout:
            problems.append("replace_asset: nothing to change (asset_type and layout both empty)")
        return problems

    def apply(self, project: ReelProject) -> ReelProject:
        scenes = list(project.scenes)
        old = scenes[self.index]
        scenes[self.index] = dataclasses.replace(
            old, asset_type=self.asset_type or old.asset_type,
            layout=self.layout or old.layout)
        return project.with_scenes(scenes)

    def describe(self) -> str:
        return f"replace asset of scene {self.index} -> {self.asset_type}/{self.layout}"


@dataclass(frozen=True)
class DurationPatch(Patch):
    """Adjust the estimated duration of scene ``index``."""

    op = "adjust_duration"
    index: int
    duration_s: float

    def validate(self, project: ReelProject) -> list[str]:
        problems: list[str] = []
        if not _index_in_range(self.index, project.n_scenes):
            problems.append(f"adjust_duration index {self.index} out of range")
        if self.duration_s <= 0:
            problems.append(f"adjust_duration: duration must be positive, got {self.duration_s}")
        return problems

    def apply(self, project: ReelProject) -> ReelProject:
        scenes = list(project.scenes)
        scenes[self.index] = dataclasses.replace(
            scenes[self.index], duration_estimate_s=round(self.duration_s, 3))
        return project.with_scenes(scenes)

    def describe(self) -> str:
        return f"set scene {self.index} duration -> {self.duration_s}s"


@dataclass(frozen=True)
class ThemePatch(Patch):
    """Change the reel's branding theme."""

    op = "change_theme"
    theme: str

    def validate(self, project: ReelProject) -> list[str]:
        if self.theme not in valid_themes():
            return [f"change_theme: unknown theme {self.theme!r} (expected one of {valid_themes()})"]
        return []

    def apply(self, project: ReelProject) -> ReelProject:
        return project.with_settings(theme=self.theme)

    def describe(self) -> str:
        return f"change theme -> {self.theme}"


@dataclass(frozen=True)
class MusicPatch(Patch):
    """Change the reel's music track."""

    op = "change_music"
    soundtrack: str

    def validate(self, project: ReelProject) -> list[str]:
        if self.soundtrack not in valid_soundtracks():
            return [f"change_music: unknown soundtrack {self.soundtrack!r} "
                    f"(expected one of {valid_soundtracks()})"]
        return []

    def apply(self, project: ReelProject) -> ReelProject:
        return project.with_settings(soundtrack=self.soundtrack)

    def describe(self) -> str:
        return f"change music -> {self.soundtrack}"


@dataclass(frozen=True)
class CaptionPatch(Patch):
    """Change the caption style (kind and/or preset)."""

    op = "change_caption"
    kind: str = ""                       # "" leaves it unchanged
    preset: str = ""                     # "" leaves it unchanged

    def validate(self, project: ReelProject) -> list[str]:
        problems: list[str] = []
        if self.kind and self.kind not in valid_caption_kinds():
            problems.append(f"change_caption: unknown kind {self.kind!r}")
        if self.preset and self.preset not in valid_caption_styles():
            problems.append(f"change_caption: unknown preset {self.preset!r}")
        if not self.kind and not self.preset:
            problems.append("change_caption: nothing to change (kind and preset both empty)")
        return problems

    def apply(self, project: ReelProject) -> ReelProject:
        return project.with_settings(
            caption_kind=self.kind or project.caption_kind,
            caption_preset=self.preset or project.caption_preset)

    def describe(self) -> str:
        return f"change caption -> {self.kind or '-'}/{self.preset or '-'}"


@dataclass(frozen=True)
class RegenerateScenePatch(Patch):
    """Regenerate one scene's narration through the existing AI Storyboard interface.

    Runs the named provider (deterministic ``mock`` by default) on the reel's
    prompt plus an optional ``instruction`` and swaps in the regenerated narration
    for scene ``index``. With the mock provider this is deterministic (same
    instruction -> same narration), so an edit history stays replayable; a real
    provider re-generates on apply (documented)."""

    op = "regenerate_scene"
    index: int
    provider: str = "mock"
    template: str = ""                   # "" -> the storyboard's own template
    instruction: str = ""                # "" -> the storyboard's original prompt

    def validate(self, project: ReelProject) -> list[str]:
        from script_engine.providers import PROVIDER_NAMES
        problems: list[str] = []
        if not _index_in_range(self.index, project.n_scenes):
            problems.append(f"regenerate_scene index {self.index} out of range")
        if self.provider not in PROVIDER_NAMES:
            problems.append(f"regenerate_scene: unknown provider {self.provider!r}")
        return problems

    def apply(self, project: ReelProject) -> ReelProject:
        from script_engine.config import ScriptEngineConfig
        from script_engine.prompt_templates import get_template
        from script_engine.providers import GenerationRequest, get_provider

        sb = project.storyboard
        template = get_template(self.template or sb.template)
        prompt = self.instruction or sb.prompt or sb.title
        cfg = ScriptEngineConfig(provider=self.provider, template=template.name)
        request = GenerationRequest.build(prompt, template, cfg)
        fresh = get_provider(self.provider).generate(request)
        j = min(self.index, fresh.n_scenes - 1)
        new_narration = fresh.scenes[j].narration if fresh.scenes else ""

        scenes = list(project.scenes)
        scenes[self.index] = dataclasses.replace(scenes[self.index], narration=new_narration)
        return project.with_scenes(scenes)

    def describe(self) -> str:
        via = f" via {self.provider}" + (f" ({self.instruction!r})" if self.instruction else "")
        return f"regenerate scene {self.index}{via}"
