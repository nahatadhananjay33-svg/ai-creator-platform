"""AI Prompt & Storyboard Engine (Phase C10) — prompt -> structured storyboard.

The front of the pipeline: turn a natural-language **prompt** into a validated,
structured :class:`AIStoryboard` (via a configurable provider), then feed it into
the EXISTING deterministic Scene Engine (Phase C7), which owns all scene planning,
timing, and visual slotting. The AI layer's ONLY responsibility is:

    prompt -> structured script -> storyboard -> Scene Engine -> Timeline IR -> pipeline

It does **not** generate video, **not** modify the Timeline IR, and **not** talk
to the renderer. Multiple providers (Mock / OpenAI / Anthropic / Gemini) sit
behind one interface and all emit the SAME structured output; the deterministic
MockProvider is the default, so the whole pipeline runs with no API key.

Public API:
- :class:`ScriptEngine` — the facade (prompt -> AIStoryboard -> Scene Engine)
- :class:`AIStoryboard` / :class:`ScriptScene` — the structured brief
- :func:`validate_storyboard` / :func:`validate_or_raise` — AI-output validation
- :func:`get_provider` / :class:`MockProvider` — providers behind one interface
- :func:`get_template` / :func:`template_names` — prompt templates
- :class:`ScriptEngineConfig` / :func:`load_script_engine_config` — configuration
"""
from __future__ import annotations

from script_engine.config.settings import ScriptEngineConfig, load_script_engine_config
from script_engine.planner.engine import ScriptEngine
from script_engine.prompt_templates.registry import (
    PromptTemplate,
    get_template,
    template_names,
)
from script_engine.providers import (
    GenerationRequest,
    MockProvider,
    StoryboardProvider,
    get_provider,
)
from script_engine.storyboard.script import storyboard_to_script
from script_engine.storyboard.serde import storyboard_from_json, storyboard_to_json
from script_engine.storyboard.types import (
    AIStoryboard,
    ScriptScene,
)
from script_engine.validator.validator import (
    ScriptValidationError,
    validate_or_raise,
    validate_storyboard,
)

__version__ = "1.0.0"

__all__ = [
    "ScriptEngine",
    "ScriptEngineConfig",
    "load_script_engine_config",
    "AIStoryboard",
    "ScriptScene",
    "storyboard_to_script",
    "storyboard_to_json",
    "storyboard_from_json",
    "validate_storyboard",
    "validate_or_raise",
    "ScriptValidationError",
    "get_provider",
    "MockProvider",
    "StoryboardProvider",
    "GenerationRequest",
    "PromptTemplate",
    "get_template",
    "template_names",
]
