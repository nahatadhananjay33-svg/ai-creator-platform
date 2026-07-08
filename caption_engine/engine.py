"""Caption Engine facade (Phase C4).

The high-level, reusable API: turn speech (script + its audio/duration) into a
validated, Timeline-native :class:`CaptionTrack`. It wires the three pieces —

    timing provider  →  style resolution  →  builder

— and nothing else. It generates *data* (a caption track); rendering and
subtitle export are separate concerns (the renderer and the export module).

Everything is configuration-driven and deterministic: the default heuristic
provider needs no ASR/GPU, so ``generate`` is reproducible and hermetic.
"""
from __future__ import annotations

import dataclasses
from pathlib import Path

from foundation.logging import get_logger
from foundation.shared_utils import read_wav
from reel_engine.interfaces.types import CaptionAnimation, CaptionStyle, CaptionTrack

from caption_engine.config.settings import CaptionEngineConfig, load_caption_engine_config
from caption_engine.providers.base import TimingProvider
from caption_engine.providers.heuristic import HeuristicTimingProvider
from caption_engine.styles.presets import get_style
from caption_engine.timeline.builder import build_caption_track

logger = get_logger("caption_engine")


class CaptionEngine:
    """Script + audio -> a validated, styled CaptionTrack."""

    def __init__(
        self,
        config: CaptionEngineConfig | None = None,
        *,
        provider: TimingProvider | None = None,
    ) -> None:
        self.config = config or load_caption_engine_config()
        self.provider = provider or HeuristicTimingProvider()

    def resolve_style(
        self,
        preset: str | None = None,
        overrides: dict | None = None,
    ) -> CaptionStyle:
        """A concrete style = preset base + config overrides + call overrides."""
        base = get_style(preset or self.config.preset)
        merged = {**self.config.style_overrides, **(overrides or {})}
        return dataclasses.replace(base, **merged) if merged else base

    def generate(
        self,
        *,
        text: str,
        audio_path: Path | str | None = None,
        duration_s: float | None = None,
        kind: str | None = None,
        preset: str | None = None,
        style: CaptionStyle | None = None,
        style_overrides: dict | None = None,
        animation: CaptionAnimation | None = None,
        track_id: str = "captions",
    ) -> CaptionTrack:
        """Produce a caption track for ``text`` timed against the audio.

        Duration comes from ``duration_s`` or is read from ``audio_path``; it is
        the hard bound captions must fit inside. ``kind``/``preset``/``animation``
        fall back to config. Pass an explicit ``style`` to bypass preset resolution.
        """
        if duration_s is None:
            if audio_path is None:
                raise ValueError("generate() needs either duration_s or audio_path")
            duration_s = read_wav(Path(audio_path)).duration_s

        kind = kind or self.config.kind
        resolved_style = style or self.resolve_style(preset, style_overrides)
        resolved_anim = animation or self.config.animation()

        transcript = self.provider.transcribe(
            text=text, duration_s=duration_s,
            audio_path=Path(audio_path) if audio_path else None)
        track = build_caption_track(
            transcript, kind=kind, style=resolved_style,
            animation=resolved_anim, track_id=track_id)
        logger.info("Captions generated", extra={"context": {
            "kind": kind, "style": resolved_style.name,
            "segments": track.n_segments, "duration_s": round(duration_s, 3)}})
        return track
