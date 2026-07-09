"""AIStoryboard -> plain script (Phase C10).

The single seam into the deterministic pipeline: an :class:`AIStoryboard` is
lowered to a plain script string whose scene boundaries are marked with the
Scene Engine's manual scene marker (``---``). The existing Scene Engine then
segments, classifies, times, and plans visuals from it — **no scene-planning
logic is duplicated here**. The AI's scene breaks become hard boundaries the
Scene Engine honours; within a scene the Scene Engine may still split on its own
word/duration caps (that is intended — the deterministic layer stays authoritative).
"""
from __future__ import annotations

from script_engine.storyboard.types import AIStoryboard

#: The Scene Engine's manual scene-break marker (see scene_engine segmentation).
SCENE_MARKER = "---"


def storyboard_to_script(storyboard: AIStoryboard) -> str:
    """Lower an :class:`AIStoryboard` to a marker-delimited script string.

    Each scene's narration becomes one block separated by a ``---`` marker, so the
    Scene Engine treats every AI scene as a hard break. Empty-narration scenes are
    dropped (the validator flags them separately)."""
    blocks = [s.narration.strip() for s in storyboard.scenes if s.narration.strip()]
    return f"\n\n{SCENE_MARKER}\n\n".join(blocks)
