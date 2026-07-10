"""Inputs + measured facts for the Quality Checker (Phase C16).

Two value families:

- :class:`ReelArtifacts` — *what to check*: the rendered master (+ its audio and
  caption sidecars, and the platform exports) together with the declarative facts
  it was rendered from (the :class:`~reel_engine.interfaces.types.Timeline`) and
  the upstream pieces (voice clips, the avatar plan). It is the single, renderer-
  agnostic bundle every check reads from.
- :class:`ReelInspection` — *what was measured*: the deterministic result of
  probing the actual files (dimensions, duration, audio, caption cues, exports).

Nothing here decodes with a model or calls a network — probing is either the
stdlib raw-AVI/WAV readers (the hermetic mock path) or the existing ``ffprobe``
wrapper (real MP4s). See :mod:`quality_engine.checker.inspect`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from reel_engine.interfaces.types import RenderResult, Timeline


@dataclass(frozen=True)
class ExportInfo:
    """One platform rendition the renderer produced (its declared shape)."""

    profile: str
    path: Path
    width: int = 0
    height: int = 0
    aspect: str = ""


@dataclass(frozen=True)
class ReelArtifacts:
    """Everything the checker needs about one rendered reel.

    ``timeline`` is the declarative source of truth for *content* presence
    (captions/branding/music) and the expected aspect — so those checks are
    identical for the mock and ffmpeg backends. ``audio_path`` / ``captions_path``
    are the mock's sidecars (``None`` for a muxed MP4, where audio lives in the
    container and captions are burned in — the checker then falls back to the
    Timeline). ``voice_clips`` and ``avatar`` come from the upstream stages."""

    master_path: Path
    timeline: Timeline | None = None
    audio_path: Path | None = None
    captions_path: Path | None = None
    exports: tuple[ExportInfo, ...] = ()
    voice_clips: tuple[Path, ...] = ()
    avatar: dict[str, Any] | None = None
    renderer: str = "mock"

    @classmethod
    def from_render_result(
        cls,
        result: RenderResult,
        *,
        timeline: Timeline | None = None,
        voice_clips: tuple = (),
        avatar: dict[str, Any] | None = None,
    ) -> "ReelArtifacts":
        """Build artifacts straight from a :class:`RenderResult` (+ upstream bits)."""
        exports = tuple(
            ExportInfo(profile=e.profile, path=Path(e.path), width=e.width,
                       height=e.height, aspect=e.aspect)
            for e in result.exports
        )
        return cls(
            master_path=Path(result.output_path), timeline=timeline,
            audio_path=Path(result.audio_path) if result.audio_path else None,
            captions_path=Path(result.captions_path) if result.captions_path else None,
            exports=exports, voice_clips=tuple(Path(p) for p in voice_clips),
            avatar=avatar, renderer=result.renderer,
        )


@dataclass(frozen=True)
class ExportProbe:
    """A probed export rendition: does it exist, and does its shape match the
    profile it claims (aspect ratio is the renderer-agnostic invariant — the mock
    writes a downscaled proxy that preserves aspect, ffmpeg writes exact dims)."""

    profile: str
    path: Path
    exists: bool
    width: int
    height: int
    aspect: str
    expected_aspect: str

    @property
    def aspect_ok(self) -> bool:
        return self.exists and self.aspect == self.expected_aspect


@dataclass(frozen=True)
class ReelInspection:
    """The deterministic result of probing a reel's actual files.

    Volatile only in the sense that it reflects the bytes on disk; for a fixed
    Timeline + renderer it is identical every run (the mock is byte-deterministic).
    ``audio_source`` is ``"muxed"`` (audio inside the video container), ``"sidecar"``
    (a separate WAV), or ``"none"``."""

    master_exists: bool = False
    video_readable: bool = False
    width: int = 0
    height: int = 0
    fps: float = 0.0
    n_frames: int = 0
    video_duration_s: float = 0.0
    audio_source: str = "none"           # "muxed" | "sidecar" | "none"
    audio_present: bool = False
    audio_duration_s: float | None = None
    audio_silent: bool = False
    captions_sidecar_exists: bool = False
    n_caption_cues: int = 0
    exports: tuple[ExportProbe, ...] = ()
    errors: tuple[str, ...] = ()

    @property
    def aspect(self) -> str:
        from reel_engine.interfaces.types import aspect_ratio_string
        return aspect_ratio_string(self.width, self.height)
