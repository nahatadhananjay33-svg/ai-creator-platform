"""Music sources (Phase C8) — authoring spec + local/procedural resolution.

A :class:`MusicSpec` is an authoring *request* for one background bed; a provider
resolves it to a concrete local audio file (an :class:`AssetRef` the renderer's
mixer reads). Two sources only, both offline and deterministic:

  - a **local** WAV the creator supplies (``source=...``), and
  - a **built-in procedural** bed (``soundtrack="ambient"``) rendered by
    :mod:`music_engine.providers.procedural`.

NO streaming APIs, NO stock libraries, NO downloads, NO licensing, NO AI
selection — those belong to later phases. The provider only ever touches a local
file it was handed or one it generated deterministically into ``asset_dir``.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from foundation.exceptions import PlatformError
from reel_engine.interfaces.types import AssetRef

from music_engine.providers.procedural import (
    DEFAULT_BED_DURATION_S,
    ProceduralSoundtrack,
    soundtrack_names,
)


@dataclass(frozen=True)
class MusicSpec:
    """An authoring request for one music bed (the builder fills the rest).

    Exactly one source is used: an explicit local ``source`` file, else a built-in
    ``soundtrack`` name rendered procedurally. ``end_s == 0`` means "to the end of
    the reel" (the builder fills it). The ``*_override`` / optional fields let a
    caller pin any parameter; when left ``None`` the engine config supplies it."""

    source: str | None = None            # local audio file path
    soundtrack: str | None = None        # built-in procedural bed name
    start_s: float = 0.0
    end_s: float = 0.0                    # 0 => whole reel (filled by the builder)
    gain: float | None = None
    source_offset_s: float = 0.0
    fade_in_s: float | None = None
    fade_out_s: float | None = None
    loop: bool | None = None
    loop_crossfade_s: float | None = None
    duck: bool | None = None
    duck_level: float | None = None
    envelope_points: tuple = ()          # ((time_s, gain), ...) absolute reel time
    mute_sections: tuple = ()            # ((start_s, end_s), ...) absolute reel time
    clip_id: str | None = None


class MusicProvider(ABC):
    """Resolves a :class:`MusicSpec` to a local audio :class:`AssetRef`."""

    @abstractmethod
    def resolve(self, spec: MusicSpec, *, sample_rate: int,
                asset_dir: Path | None = None) -> AssetRef:
        ...


class LocalMusicProvider(MusicProvider):
    """Resolves a music bed from a **local file** or a **built-in procedural**
    soundtrack — never a download or a network call."""

    def __init__(self, generator: ProceduralSoundtrack | None = None) -> None:
        self._generator = generator

    def resolve(self, spec: MusicSpec, *, sample_rate: int,
                asset_dir: Path | None = None) -> AssetRef:
        if spec.source:
            path = Path(spec.source)
            if not path.exists():
                raise PlatformError(f"Music source not found: {path}", path=str(path))
            return AssetRef(kind="file", uri=str(path),
                            meta={"music_source": "local"})
        name = spec.soundtrack
        if not name:
            raise PlatformError("MusicSpec needs a 'source' file or a 'soundtrack' name")
        if name not in soundtrack_names():
            raise PlatformError(
                f"Unknown soundtrack {name!r}; expected one of {soundtrack_names()}")
        gen = self._generator or ProceduralSoundtrack(sample_rate=sample_rate)
        out_dir = Path(asset_dir) if asset_dir is not None else Path(".")
        out_dir.mkdir(parents=True, exist_ok=True)
        # deterministic filename so repeated builds reuse the same generated bed
        path = out_dir / f"soundtrack_{name}_{sample_rate}.wav"
        gen.generate(name, path, DEFAULT_BED_DURATION_S)
        return AssetRef(kind="file", uri=str(path),
                        meta={"music_source": "procedural", "soundtrack": name})
