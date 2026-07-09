"""MockProvider (Phase C10) — deterministic, offline storyboard generation.

The MockProvider fills the selected template's narration lines with the prompt's
topic to produce a valid :class:`AIStoryboard` WITHOUT any API call, key, network,
or model. It is the hermetic backbone: the same (prompt, template, config) always
yields the same brief, so the entire prompt -> reel pipeline runs and is tested
deterministically. It is NOT AI — it is a template filler that emits exactly the
same structured output the real LLM providers do, so they stay interchangeable.
"""
from __future__ import annotations

from script_engine.providers.base import (
    GenerationRequest,
    clean_topic,
    estimate_duration_s,
    topic_keywords,
)
from script_engine.storyboard.types import AIStoryboard, ScriptScene


class MockProvider:
    """Deterministic template-filling provider (no AI, no network, no key)."""

    name = "mock"

    def generate(self, request: GenerationRequest) -> AIStoryboard:
        tmpl = request.template
        topic = clean_topic(request.prompt)
        n = request.n_scenes
        keywords = topic_keywords(topic)

        scenes: list[ScriptScene] = []
        for i in range(n):
            is_last = i == n - 1
            if i == 0:
                text = tmpl.hook.format(topic=topic)
            elif is_last:
                text = tmpl.cta.format(topic=topic)
            else:
                text = tmpl.body[(i - 1) % len(tmpl.body)].format(topic=topic)
            scenes.append(ScriptScene(
                narration=text,
                scene_type=tmpl.scene_type_at(i, n),
                cta=is_last,
                duration_estimate_s=estimate_duration_s(text),
                keywords=keywords,
            ))

        title = _title_from_topic(topic)
        return AIStoryboard(
            title=title, scenes=tuple(scenes),
            target_audience=tmpl.audience, tone=tmpl.tone,
            hook=scenes[0].narration if scenes else "",
            prompt=request.prompt, template=tmpl.name, language=request.language,
            provider=self.name, model="mock-deterministic-v1",
        )


def _title_from_topic(topic: str) -> str:
    """A short, Title-Cased headline from the topic (deterministic)."""
    words = topic.split()
    head = " ".join(words[:8])
    return head[:1].upper() + head[1:] if head else "Untitled Reel"
