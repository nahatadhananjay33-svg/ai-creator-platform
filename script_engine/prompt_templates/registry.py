"""Prompt template registry (Phase C10).

Loads the configuration-driven templates from ``templates.yaml`` into immutable
:class:`PromptTemplate` values. A template supplies the *system prompt* a real LLM
provider is given, the advisory *scene arc*, and the deterministic *narration
templates* the MockProvider fills — so adding a content vertical is a YAML edit,
never a code change. All templates yield the same :class:`AIStoryboard` shape.
"""
from __future__ import annotations

import functools
from dataclasses import dataclass
from pathlib import Path

from foundation.config import load_yaml

TEMPLATES_PATH: Path = Path(__file__).resolve().parent / "templates.yaml"


@dataclass(frozen=True)
class PromptTemplate:
    """One content-vertical template: LLM system prompt + deterministic fill data."""

    name: str
    audience: str
    tone: str
    system_prompt: str
    arc: tuple[str, ...]                  # advisory scene-type sequence
    hook: str                            # narration template (uses {topic})
    cta: str                             # narration template (uses {topic})
    body: tuple[str, ...]                # body narration templates (use {topic})

    def scene_type_at(self, index: int, n_scenes: int) -> str:
        """The advisory scene type for scene ``index`` of ``n_scenes`` (from the
        arc, with the last scene forced to the arc's closing beat)."""
        if index == 0:
            return self.arc[0]
        if index == n_scenes - 1:
            return self.arc[-1]
        body_types = self.arc[1:-1] or ("explanation",)
        return body_types[(index - 1) % len(body_types)]


@functools.lru_cache(maxsize=1)
def _load() -> dict[str, PromptTemplate]:
    data = load_yaml(TEMPLATES_PATH) or {}
    out: dict[str, PromptTemplate] = {}
    for name, t in (data.get("templates", {}) or {}).items():
        out[name] = PromptTemplate(
            name=name,
            audience=t.get("audience", "a general audience"),
            tone=t.get("tone", "informative"),
            system_prompt=" ".join((t.get("system_prompt", "") or "").split()),
            arc=tuple(t.get("arc", ("hook", "explanation", "call_to_action"))),
            hook=t.get("hook", "Here is what you need to know about {topic}."),
            cta=t.get("cta", "Follow for more on {topic}."),
            body=tuple(t.get("body", ("Let's talk about {topic}.",))),
        )
    return out


def template_names() -> tuple[str, ...]:
    """All available template names, sorted (stable for reporting/tests)."""
    return tuple(sorted(_load()))


def get_template(name: str) -> PromptTemplate:
    """Return the named template, falling back to ``general`` for an unknown name."""
    templates = _load()
    return templates.get(name) or templates["general"]
