"""AnthropicProvider (Phase C10) — storyboard generation via the Claude API.

Generates an :class:`AIStoryboard` with Claude using the official ``anthropic``
SDK and structured outputs (``output_config.format``), so the model returns JSON
that validates against :data:`AI_STORYBOARD_JSON_SCHEMA` directly. Behind the
same :class:`StoryboardProvider` interface as every other provider.

Requires the ``anthropic`` package and an ``ANTHROPIC_API_KEY`` (or an ``ant auth
login`` profile). Imported lazily so the hermetic MockProvider path never needs
either. Notes on the current Claude API surface (see the claude-api skill):
- Default model is ``claude-opus-4-8`` (the latest, most capable Opus).
- ``temperature`` is intentionally NOT sent — sampling params are rejected (400)
  on Opus 4.8 / 4.7 and modern Claude models; prompting steers the output instead.
"""
from __future__ import annotations

import os

from script_engine.providers._common import build_generation_prompt, parse_storyboard
from script_engine.providers.base import GenerationRequest
from script_engine.storyboard.types import AI_STORYBOARD_JSON_SCHEMA, AIStoryboard

#: The latest, most capable Opus model (claude-api skill default).
DEFAULT_MODEL = "claude-opus-4-8"


class AnthropicProvider:
    """Claude-backed storyboard provider (requires ``anthropic`` + an API key)."""

    name = "anthropic"

    def __init__(self, *, api_key: str | None = None, model: str | None = None) -> None:
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self._model = model or DEFAULT_MODEL
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import anthropic
            except ImportError as exc:  # pragma: no cover - integration path only
                raise RuntimeError(
                    "AnthropicProvider requires the 'anthropic' package: pip install anthropic"
                ) from exc
            # The zero-arg client also resolves an `ant auth login` profile when
            # ANTHROPIC_API_KEY is unset; pass api_key only when we have one.
            self._client = (anthropic.Anthropic(api_key=self._api_key)
                            if self._api_key else anthropic.Anthropic())
        return self._client

    def generate(self, request: GenerationRequest) -> AIStoryboard:
        system, user = build_generation_prompt(request)
        model = request.model or self._model
        response = self._get_client().messages.create(
            model=model,
            max_tokens=request.max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"format": {"type": "json_schema",
                                      "schema": AI_STORYBOARD_JSON_SCHEMA}},
        )
        # With output_config.format the first text block is schema-valid JSON.
        text = next((b.text for b in response.content if b.type == "text"), "")
        return parse_storyboard(text, request, provider=self.name, model=model)
