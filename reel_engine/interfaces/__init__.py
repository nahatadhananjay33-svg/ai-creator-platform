"""Reels Engine frozen interfaces (Phase C2).

The public contract: value types only, no behaviour, no heavy imports. Products
and other engines depend on these, never on ``reel_engine`` internals.
"""
from __future__ import annotations

from reel_engine.interfaces.types import (
    TIMELINE_SCHEMA_VERSION,
    AssetRef,
    CaptionAnimation,
    CaptionSegment,
    CaptionStyle,
    CaptionTrack,
    Clip,
    ExportOutput,
    RenderRequest,
    RenderResult,
    Scene,
    Timeline,
    TimelineMeta,
    Track,
    Transition,
    WordTiming,
    aspect_ratio_string,
)

__all__ = [
    "TIMELINE_SCHEMA_VERSION",
    "AssetRef",
    "CaptionAnimation",
    "CaptionSegment",
    "CaptionStyle",
    "CaptionTrack",
    "Clip",
    "ExportOutput",
    "RenderRequest",
    "RenderResult",
    "Scene",
    "Timeline",
    "TimelineMeta",
    "Track",
    "Transition",
    "WordTiming",
    "aspect_ratio_string",
]
