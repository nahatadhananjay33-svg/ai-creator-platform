"""Timeline IR: construction, validation, serialization, and content hashing.

The IR is a pure data structure; rendering it is a separate concern
(``reel_engine.render``). Nothing here imports a renderer or any heavy dep.
"""
from __future__ import annotations

from reel_engine.timeline.hashing import (
    canonical_json,
    scene_content_hash,
    timeline_content_hash,
)
from reel_engine.timeline.model import (
    COLORS,
    build_demo_timeline,
    new_timeline,
    storyboard,
)
from reel_engine.timeline.serde import (
    timeline_from_dict,
    timeline_from_json,
    timeline_to_dict,
    timeline_to_json,
)
from reel_engine.timeline.validate import (
    TimelineError,
    validate_or_raise,
    validate_timeline,
)

__all__ = [
    "COLORS",
    "TimelineError",
    "build_demo_timeline",
    "canonical_json",
    "new_timeline",
    "scene_content_hash",
    "storyboard",
    "timeline_content_hash",
    "timeline_from_dict",
    "timeline_from_json",
    "timeline_to_dict",
    "timeline_to_json",
    "validate_or_raise",
    "validate_timeline",
]
