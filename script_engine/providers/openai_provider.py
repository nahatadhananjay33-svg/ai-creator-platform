"""OpenAIProvider (Phase C10) — storyboard generation via the OpenAI API.

Generates an :class:`AIStoryboard` with an OpenAI chat model using structured
outputs (``response_format`` with a JSON schema), behind the same
:class:`StoryboardProvider` interface as every other provider.

Requires the ``openai`` package and an ``OPENAI_API_KEY``. Imported lazily so the
hermetic MockProvider path never needs either. The model is configurable
(``config.script.model`` or the ``model=`` arg); the default is a reasonable
current chat model but can be overridden without a code change.
"""
from __future__ import annotations

import os

from script_engine.providers._common import build_generation_prompt, parse_storyboard
from script_engine.providers.base import GenerationRequest
from script_engine.storyboard.types import AI_STORYBOARD_JSON_SCHEMA, AIStoryboard

DEFAULT_MODEL = "gpt-4o-mini"


class OpenAIProvider:
    """OpenAI-backed storyboard provider (requires ``openai`` + an API key)."""

    name = "openai"

    def __init__(self, *, api_key: str | None = None, model: str | None = None) -> None:
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self._model = model or DEFAULT_MODEL
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:  # pragma: no cover - integration path only
                raise RuntimeError(
                    "OpenAIProvider requires the 'openai' package: pip install openai"
                ) from exc
            self._client = OpenAI(api_key=self._api_key) if self._api_key else OpenAI()
        return self._client

    def generate(self, request: GenerationRequest) -> AIStoryboard:
        system, user = build_generation_prompt(request)
        model = request.model or self._model
        response = self._get_client().chat.completions.create(
            model=model,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "ai_storyboard", "strict": True,
                                "schema": AI_STORYBOARD_JSON_SCHEMA},
            },
        )
        text = response.choices[0].message.content or ""
        return parse_storyboard(text, request, provider=self.name, model=model)
