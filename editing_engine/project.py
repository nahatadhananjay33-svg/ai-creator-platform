"""The editable reel model (Phase C11).

A :class:`ReelProject` is the immutable, editable document a future Creator Studio
manipulates: the AI-generated content (an :class:`AIStoryboard` from C10) plus the
reel-level presentation settings (branding theme, music soundtrack, caption style,
dimensions). Patches transform one project into a NEW project — the value is never
mutated in place, so every revision is a stable, hashable snapshot.

This phase defines the *model* only: it never modifies the Timeline IR and never
touches the renderer. A project is lowered to a Timeline through the EXISTING
Scene/Branding/Music engines (see :mod:`editing_engine.engine`).
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass

from script_engine.storyboard.types import AIStoryboard, ScriptScene


@dataclass(frozen=True)
class ReelProject:
    """An immutable, editable reel: AI content + presentation settings.

    ``revision`` is bumped by every applied patch, so two projects with different
    edit histories are distinguishable even if their content coincides. The
    presentation fields name values the existing engines already understand
    (a Branding theme, a Music soundtrack, a Caption kind + style)."""

    storyboard: AIStoryboard
    theme: str = "modern"                # a branding_engine theme name
    soundtrack: str = "ambient"          # a music_engine soundtrack name
    caption_kind: str = "sentence"       # sentence | word | karaoke | static
    caption_preset: str = "modern"       # a caption_engine style name
    width: int = 1080
    height: int = 1920
    fps: int = 30
    creator: str = ""
    channel: str = ""
    revision: int = 0

    @property
    def scenes(self) -> tuple[ScriptScene, ...]:
        return self.storyboard.scenes

    @property
    def n_scenes(self) -> int:
        return self.storyboard.n_scenes

    # ------------------------------------------------------------- edit helpers
    def with_scenes(self, scenes) -> "ReelProject":
        """A new project with the storyboard's scenes replaced (revision bumped)."""
        new_sb = dataclasses.replace(self.storyboard, scenes=tuple(scenes))
        return dataclasses.replace(self, storyboard=new_sb, revision=self.revision + 1)

    def with_settings(self, **changes) -> "ReelProject":
        """A new project with presentation settings changed (revision bumped)."""
        return dataclasses.replace(self, revision=self.revision + 1, **changes)
