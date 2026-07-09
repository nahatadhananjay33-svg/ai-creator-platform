"""AI Storyboard IR — the structured output of the AI Prompt & Storyboard Engine (Phase C10).

This is the schema every provider (Mock / OpenAI / Anthropic / Gemini) emits: a
high-level *creative brief* generated from a prompt. It is **NOT** the Timeline IR
and **NOT** the deterministic Scene-Planner ``Storyboard`` — it is the layer
*above* both. The AI decides what to say and how to break the reel into scenes;
the existing deterministic Scene Engine (Phase C7) then classifies, times, and
plans visuals from it. The AI layer never generates video, never touches the
Timeline IR, and never talks to the renderer.

    prompt -> provider -> AIStoryboard -> validate -> script -> Scene Engine -> ...

Everything is an immutable ``@dataclass(frozen=True)`` with tuple collections, so
a generated brief is a stable, hashable value. The shape is frozen and shared by
all providers, exactly as the objective requires ("All providers must emit the
SAME structured output").
"""
from __future__ import annotations

from dataclasses import dataclass, field

from scene_engine.storyboard.types import SCENE_TYPES

#: Bumped whenever the AI-storyboard schema changes incompatibly.
SCRIPT_SCHEMA_VERSION = 1

#: The scene types a provider may assign — the SAME closed set the deterministic
#: Scene Engine uses, so the two layers agree. (Advisory: the Scene Engine
#: re-derives the authoritative type deterministically from the narration.)
SUPPORTED_SCENE_TYPES: tuple[str, ...] = SCENE_TYPES


@dataclass(frozen=True)
class ScriptScene:
    """One AI-authored scene: what to say + creative suggestions for it.

    ``narration`` is the spoken copy (the only field the deterministic pipeline
    strictly needs). The rest are *suggestions* the AI offers — a scene type, a
    suggested asset kind and layout, whether it is a call-to-action, an estimated
    duration, and salient keywords. They are carried for reporting and future use;
    the deterministic Scene Engine remains authoritative for the actual plan."""

    narration: str
    scene_type: str = "explanation"      # a SUPPORTED_SCENE_TYPES value (advisory)
    asset_type: str = ""                 # suggested visual asset kind (advisory)
    layout: str = ""                     # suggested layout (advisory)
    cta: bool = False                    # is this a call-to-action beat?
    duration_estimate_s: float = 0.0     # the AI's rough estimate (advisory)
    keywords: tuple[str, ...] = ()

    @property
    def word_count(self) -> int:
        return len(self.narration.split())


@dataclass(frozen=True)
class AIStoryboard:
    """A complete AI-generated creative brief for one reel.

    The top-level fields (``title``/``target_audience``/``tone``/``hook``) frame
    the reel; ``scenes`` is the ordered narration plan. ``prompt``/``template``/
    ``provider``/``model`` record provenance. Duration/word/type stats are derived
    (never stored) so they cannot drift from the scenes."""

    title: str
    scenes: tuple[ScriptScene, ...]
    target_audience: str = "general audience"
    tone: str = "informative"
    hook: str = ""
    prompt: str = ""
    template: str = "general"
    language: str = "en"
    provider: str = ""
    model: str = ""
    schema_version: int = SCRIPT_SCHEMA_VERSION

    @property
    def n_scenes(self) -> int:
        return len(self.scenes)

    @property
    def word_count(self) -> int:
        return sum(s.word_count for s in self.scenes)

    @property
    def total_duration_estimate_s(self) -> float:
        return round(sum(s.duration_estimate_s for s in self.scenes), 3)

    def scene_types(self) -> tuple[str, ...]:
        return tuple(s.scene_type for s in self.scenes)


#: JSON Schema handed to real LLM providers (via structured outputs) so their
#: response validates as an AIStoryboard with no post-hoc coercion. Kept in sync
#: with the dataclasses above; ``additionalProperties: false`` per the structured-
#: output requirement. ``duration_estimate_s`` has no numeric bound (the API
#: rejects ``minimum``/``maximum`` in strict schemas); the validator checks it.
AI_STORYBOARD_JSON_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "target_audience": {"type": "string"},
        "tone": {"type": "string"},
        "hook": {"type": "string"},
        "scenes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "narration": {"type": "string"},
                    "scene_type": {"type": "string", "enum": list(SUPPORTED_SCENE_TYPES)},
                    "asset_type": {"type": "string"},
                    "layout": {"type": "string"},
                    "cta": {"type": "boolean"},
                    "duration_estimate_s": {"type": "number"},
                    "keywords": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["narration", "scene_type"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["title", "target_audience", "tone", "hook", "scenes"],
    "additionalProperties": False,
}
