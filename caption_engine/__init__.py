"""Caption Engine (Phase C4) — Timeline-native captions.

Turns speech (a script + its audio/duration) into a validated, styled
``CaptionTrack`` that lives natively in the Timeline IR. The renderer simply
lowers caption tracks to overlays; captions are never hardcoded into it.

Pipeline:  audio -> timing source -> CaptionTrack -> renderer / subtitle export

Public API:
- :class:`CaptionEngine` — the facade (script+audio -> CaptionTrack)
- :class:`CaptionEngineConfig` / :func:`load_caption_engine_config` — configuration
- timing providers in :mod:`caption_engine.providers`
- style presets in :mod:`caption_engine.styles`
- the builder in :mod:`caption_engine.timeline`
- subtitle export in :mod:`caption_engine.export`

The frozen caption IR types (CaptionTrack/CaptionSegment/WordTiming/CaptionStyle/
CaptionAnimation) live in ``reel_engine.interfaces`` — the single Timeline contract.
"""
from __future__ import annotations

from caption_engine.config.settings import (
    CaptionEngineConfig,
    load_caption_engine_config,
)
from caption_engine.engine import CaptionEngine
from caption_engine.providers import HeuristicTimingProvider, TimingProvider, Transcript
from caption_engine.styles import get_style, style_names
from caption_engine.timeline import CAPTION_KINDS, build_caption_track

__version__ = "1.0.0"

__all__ = [
    "CaptionEngine",
    "CaptionEngineConfig",
    "load_caption_engine_config",
    "HeuristicTimingProvider",
    "TimingProvider",
    "Transcript",
    "get_style",
    "style_names",
    "build_caption_track",
    "CAPTION_KINDS",
]
