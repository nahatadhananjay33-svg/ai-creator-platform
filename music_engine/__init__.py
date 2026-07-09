"""Music & Audio Mixing Engine (Phase C8) — deterministic, Timeline-native audio.

Makes **background music a first-class Timeline track**: the engine builds a
validated :class:`MusicTrack` (a looped, faded, envelope-shaped, speech-ducked
bed) and the renderer *mixes* it under the voice — music is never hardcoded into
the renderer. Fully deterministic and rule-based: NO AI music generation, NO
streaming APIs, NO licensing, NO beat detection, NO AI soundtrack selection —
those belong to later phases.

Pipeline:  reel duration + soundtrack -> plan -> resolve (local file / procedural
           bed) -> MusicTrack -> Timeline.music_tracks -> renderer mixes -> MP4

Public API:
- :class:`MusicEngine` — the facade (intent/specs -> MusicTrack)
- :class:`MusicSpec` — an authoring request for one bed
- :func:`plan_background_music` / :func:`plan_for_timeline` — scene-aware planning
- :func:`mix_timeline_audio` — the shared deterministic mixer (voice + music)
- :class:`MusicEngineConfig` / :func:`load_music_engine_config` — configuration
- :func:`soundtrack_names` / :func:`generate_soundtrack` — built-in procedural beds
"""
from __future__ import annotations

from music_engine.config.settings import MusicEngineConfig, load_music_engine_config
from music_engine.engine import MusicEngine
from music_engine.mixing.planner import plan_background_music, plan_for_timeline
from music_engine.providers.base import (
    LocalMusicProvider,
    MusicProvider,
    MusicSpec,
)
from music_engine.providers.procedural import (
    ProceduralSoundtrack,
    generate_soundtrack,
    soundtrack_names,
)
from music_engine.timeline.builder import build_music_track

# The shared deterministic mixer (implemented renderer-side, re-exported here).
from reel_engine.render.music import mix_timeline_audio, mixed_peak, speech_windows

__version__ = "1.0.0"

__all__ = [
    "MusicEngine",
    "MusicEngineConfig",
    "load_music_engine_config",
    "MusicSpec",
    "MusicProvider",
    "LocalMusicProvider",
    "ProceduralSoundtrack",
    "generate_soundtrack",
    "soundtrack_names",
    "build_music_track",
    "plan_background_music",
    "plan_for_timeline",
    "mix_timeline_audio",
    "mixed_peak",
    "speech_windows",
]
