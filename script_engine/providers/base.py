"""Provider interface (Phase C10) — one contract, many backends.

A *storyboard provider* answers one question: given a prompt (+ a template and
generation knobs), produce an :class:`AIStoryboard`. Every provider — the
deterministic :class:`~script_engine.providers.mock.MockProvider` and the real
LLM providers (OpenAI / Anthropic / Gemini) — implements the SAME
:class:`StoryboardProvider` interface and emits the SAME structured output, so
they are fully interchangeable behind the facade. Providers never generate video,
never touch the Timeline IR, and never call the renderer.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from script_engine.config.settings import ScriptEngineConfig
from script_engine.prompt_templates.registry import PromptTemplate
from script_engine.storyboard.types import AIStoryboard

#: ~words spoken per second at 150 wpm — used to turn a target reel length into a
#: scene count and to estimate per-scene durations. Matches the Scene Engine pace.
_WORDS_PER_SECOND = 2.5
_SECONDS_PER_SCENE = 5.0

#: Common prompt lead-ins stripped to recover the bare topic (deterministic).
_LEADINS = (
    "please ", "can you ", "i want ", "make a reel about ", "make a video about ",
    "create a reel about ", "create a video about ", "write a script about ",
    "a reel about ", "a video about ", "tell me about ", "explain how ",
    "explain why ", "explain ", "why ", "how ", "what ", "the benefits of ",
    "benefits of ",
)
_STOP = frozenset({"the", "a", "an", "and", "or", "of", "to", "in", "on", "for",
                   "with", "is", "are", "why", "how", "early", "beneficial", "your"})
_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")


def clean_topic(prompt: str) -> str:
    """Recover a bare topic phrase from a prompt (strip lead-ins + trailing punct)."""
    t = " ".join((prompt or "").strip().split())
    low = t.lower()
    for lead in _LEADINS:
        if low.startswith(lead):
            t = t[len(lead):]
            break
    t = t.strip().rstrip(" .?!,:;")
    return t or "this topic"


def topic_keywords(topic: str, *, limit: int = 4) -> tuple[str, ...]:
    """A few salient keyword tokens from a topic (stopwords dropped; deterministic)."""
    seen: list[str] = []
    for tok in _TOKEN_RE.findall(topic.lower()):
        if len(tok) >= 3 and tok not in _STOP and tok not in seen:
            seen.append(tok)
    return tuple(seen[:limit])


def estimate_duration_s(text: str) -> float:
    """Rough spoken duration for a narration line (at the shared pace)."""
    words = len(text.split())
    return round(max(1.5, words / _WORDS_PER_SECOND), 2)


@dataclass(frozen=True)
class GenerationRequest:
    """A fully-resolved request handed to a provider (prompt + template + knobs)."""

    prompt: str
    template: PromptTemplate
    n_scenes: int
    min_scenes: int
    max_scenes: int
    language: str
    style: str
    model: str
    temperature: float
    max_tokens: int
    target_duration_s: float

    @classmethod
    def build(cls, prompt: str, template: PromptTemplate,
              config: ScriptEngineConfig) -> "GenerationRequest":
        """Resolve a request from a prompt + template + engine config.

        The scene count aims for ``target_duration_s`` at ~5s/scene, clamped to
        ``[min_scenes, max_scenes]`` and capped by the template's own capacity
        (hook + body lines + cta) so the deterministic MockProvider never repeats
        a body line."""
        cap = 2 + len(template.body)
        want = round(config.target_duration_s / _SECONDS_PER_SCENE)
        n = max(config.min_scenes, min(want, config.max_scenes, cap))
        return cls(
            prompt=prompt, template=template, n_scenes=n,
            min_scenes=config.min_scenes, max_scenes=config.max_scenes,
            language=config.language, style=config.style, model=config.model,
            temperature=config.temperature, max_tokens=config.max_tokens,
            target_duration_s=config.target_duration_s)


@runtime_checkable
class StoryboardProvider(Protocol):
    """Turns a :class:`GenerationRequest` into an :class:`AIStoryboard`."""

    name: str

    def generate(self, request: GenerationRequest) -> AIStoryboard:
        ...
