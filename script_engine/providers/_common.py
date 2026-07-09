"""Shared helpers for the real LLM providers (Phase C10).

Every real provider (OpenAI / Anthropic / Gemini) builds the same instruction
from the template + request, asks for JSON matching
:data:`AI_STORYBOARD_JSON_SCHEMA` via that SDK's structured-output feature, and
parses the response back into an :class:`AIStoryboard`. Keeping the prompt and
parse here guarantees the three providers stay behaviourally identical and emit
the SAME structured output.

These are only exercised with a live API key (integration tests) — the hermetic
suite uses the deterministic MockProvider and never imports an LLM SDK.
"""
from __future__ import annotations

import json

from script_engine.providers.base import GenerationRequest
from script_engine.storyboard.serde import storyboard_from_dict
from script_engine.storyboard.types import SUPPORTED_SCENE_TYPES, AIStoryboard


def build_generation_prompt(request: GenerationRequest) -> tuple[str, str]:
    """Return ``(system_prompt, user_prompt)`` for a real LLM provider."""
    tmpl = request.template
    types = ", ".join(SUPPORTED_SCENE_TYPES)
    system = (
        f"{tmpl.system_prompt} "
        f"Write for {tmpl.audience} in a {tmpl.tone} tone. "
        f"Return ONLY a JSON object matching the provided schema — no prose. "
        f"Produce between {request.min_scenes} and {request.max_scenes} scenes, "
        f"targeting about {int(request.target_duration_s)} seconds total. "
        f"Write the narration in language code '{request.language}'. "
        f"Overall style: {request.style}. "
        f"Each scene's scene_type MUST be one of: {types}. "
        f"The first scene is the hook and the last is a call to action. "
        f"Keep each scene to one or two spoken sentences; set duration_estimate_s "
        f"to a realistic spoken length."
    )
    user = f"Create a short-form vertical video storyboard about: {request.prompt}"
    return system, user


def parse_storyboard(text: str, request: GenerationRequest, *, provider: str,
                     model: str) -> AIStoryboard:
    """Parse an LLM JSON response into an :class:`AIStoryboard` (with provenance).

    Raises :class:`ValueError` if the response is not valid JSON — the caller's
    validation layer then surfaces any structural problems."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{provider} returned non-JSON output: {exc}") from exc
    return storyboard_from_dict(
        data, provider=provider, model=model, prompt=request.prompt,
        template=request.template.name, language=request.language)
