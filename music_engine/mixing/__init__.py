"""Music mixing (Phase C8): scene-aware planning + the shared render-side mixer.

Planning (``plan_background_music`` / ``plan_for_timeline``) turns intent into a
:class:`MusicSpec`; the actual sample mixing lives in the renderer-side
:mod:`reel_engine.render.music` (the single implementation both backends use),
re-exported here so callers have one place to reach for mixing.
"""
from __future__ import annotations

# The deterministic mixer both renderers share (re-exported for convenience).
from reel_engine.render.music import (
    mix_timeline_audio,
    mixed_peak,
    speech_windows,
)

from music_engine.mixing.planner import plan_background_music, plan_for_timeline

__all__ = [
    "plan_background_music",
    "plan_for_timeline",
    "mix_timeline_audio",
    "mixed_peak",
    "speech_windows",
]
