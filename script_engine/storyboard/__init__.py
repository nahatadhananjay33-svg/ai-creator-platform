"""AI Storyboard IR (Phase C10): the structured brief every provider emits."""
from __future__ import annotations

from script_engine.storyboard.script import SCENE_MARKER, storyboard_to_script
from script_engine.storyboard.serde import (
    scene_from_dict,
    scene_to_dict,
    storyboard_from_dict,
    storyboard_from_json,
    storyboard_to_dict,
    storyboard_to_json,
)
from script_engine.storyboard.types import (
    AI_STORYBOARD_JSON_SCHEMA,
    SCRIPT_SCHEMA_VERSION,
    SUPPORTED_SCENE_TYPES,
    AIStoryboard,
    ScriptScene,
)

__all__ = [
    "AIStoryboard",
    "ScriptScene",
    "SUPPORTED_SCENE_TYPES",
    "SCRIPT_SCHEMA_VERSION",
    "AI_STORYBOARD_JSON_SCHEMA",
    "storyboard_to_script",
    "SCENE_MARKER",
    "storyboard_to_dict",
    "storyboard_to_json",
    "storyboard_from_dict",
    "storyboard_from_json",
    "scene_to_dict",
    "scene_from_dict",
]
