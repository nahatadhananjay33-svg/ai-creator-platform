"""Reels Engine frozen interfaces (Phase C2).

The public contract: value types only, no behaviour, no heavy imports. Products
and other engines depend on these, never on ``reel_engine`` internals.
"""
from __future__ import annotations

from reel_engine.interfaces.types import (
    BRANDING_POSITIONS,
    TIMELINE_SCHEMA_VERSION,
    AssetRef,
    BrandingElement,
    BrandingTrack,
    CaptionAnimation,
    CaptionSegment,
    CaptionStyle,
    CaptionTrack,
    Clip,
    ExportOutput,
    Intro,
    Logo,
    LowerThird,
    Outro,
    RenderRequest,
    RenderResult,
    Scene,
    Theme,
    Timeline,
    TimelineMeta,
    Track,
    Transition,
    Watermark,
    WordTiming,
    aspect_ratio_string,
)

__all__ = [
    "BRANDING_POSITIONS",
    "TIMELINE_SCHEMA_VERSION",
    "AssetRef",
    "BrandingElement",
    "BrandingTrack",
    "CaptionAnimation",
    "CaptionSegment",
    "CaptionStyle",
    "CaptionTrack",
    "Clip",
    "ExportOutput",
    "Intro",
    "Logo",
    "LowerThird",
    "Outro",
    "RenderRequest",
    "RenderResult",
    "Scene",
    "Theme",
    "Timeline",
    "TimelineMeta",
    "Track",
    "Transition",
    "Watermark",
    "WordTiming",
    "aspect_ratio_string",
]
