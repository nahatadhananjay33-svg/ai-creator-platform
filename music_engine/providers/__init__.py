"""Music sources: local files + built-in procedural soundtracks (Phase C8)."""
from __future__ import annotations

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

__all__ = [
    "MusicSpec",
    "MusicProvider",
    "LocalMusicProvider",
    "ProceduralSoundtrack",
    "generate_soundtrack",
    "soundtrack_names",
]
