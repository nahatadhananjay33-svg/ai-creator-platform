"""GeminiProvider (Phase C10) — storyboard generation via the Google Gemini API.

Generates an :class:`AIStoryboard` with a Gemini model using structured output
(``response_mime_type='application/json'`` + a ``response_schema``), behind the
same :class:`StoryboardProvider` interface as every other provider.

Requires the ``google-generativeai`` package and a ``GEMINI_API_KEY`` (or
``GOOGLE_API_KEY``). Imported lazily so the hermetic MockProvider path never
needs either. The model is configurable; the default can be overridden without a
code change.
"""
from __future__ import annotations

import os

from script_engine.providers._common import build_generation_prompt, parse_storyboard
from script_engine.providers.base import GenerationRequest
from script_engine.storyboard.types import AI_STORYBOARD_JSON_SCHEMA, AIStoryboard

DEFAULT_MODEL = "gemini-1.5-flash"


class GeminiProvider:
    """Gemini-backed storyboard provider (requires ``google-generativeai`` + a key)."""

    name = "gemini"

    def __init__(self, *, api_key: str | None = None, model: str | None = None) -> None:
        self._api_key = (api_key or os.environ.get("GEMINI_API_KEY")
                         or os.environ.get("GOOGLE_API_KEY"))
        self._model = model or DEFAULT_MODEL
        self._genai = None

    def _get_genai(self):
        if self._genai is None:
            try:
                import google.generativeai as genai
            except ImportError as exc:  # pragma: no cover - integration path only
                raise RuntimeError(
                    "GeminiProvider requires 'google-generativeai': pip install google-generativeai"
                ) from exc
            if self._api_key:
                genai.configure(api_key=self._api_key)
            self._genai = genai
        return self._genai

    def generate(self, request: GenerationRequest) -> AIStoryboard:
        system, user = build_generation_prompt(request)
        model_name = request.model or self._model
        genai = self._get_genai()
        model = genai.GenerativeModel(model_name, system_instruction=system)
        response = model.generate_content(
            user,
            generation_config={
                "response_mime_type": "application/json",
                "response_schema": AI_STORYBOARD_JSON_SCHEMA,
                "temperature": request.temperature,
                "max_output_tokens": request.max_tokens,
            },
        )
        return parse_storyboard(response.text, request, provider=self.name, model=model_name)
