"""The reel facts the Upload Assistant generates metadata from (Phase C18).

A :class:`ReelSummary` is a small, immutable snapshot of the *words and facts* a
finished reel already contains — its title, hook, per-scene narration, keywords,
call-to-action lines, plus a couple of render facts (duration, aspect). It is
mined from the run's ``AIStoryboard`` (the creative brief every provider emits)
and Timeline; nothing is invented and nothing is fetched.

Keeping this a plain value — rather than reaching into a live ``WorkflowResult``
inside the generator — means the generator is trivially testable with a
hand-built summary and stays decoupled from the workflow layer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ReelSummary:
    """The mined text + facts one reel's upload metadata is generated from."""

    title: str = ""
    hook: str = ""
    prompt: str = ""
    template: str = "general"
    narration: tuple[str, ...] = ()      # per-scene spoken lines (non-empty)
    keywords: tuple[str, ...] = ()       # storyboard keywords, order-preserved
    cta_lines: tuple[str, ...] = ()      # narration lines flagged call-to-action
    audience: str = "general audience"
    tone: str = "informative"
    language: str = "en"
    duration_s: float = 0.0
    aspect: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def topic(self) -> str:
        """A best-effort topic phrase for fallbacks (title, else prompt)."""
        return (self.title or self.prompt).strip()

    @classmethod
    def from_storyboard(cls, storyboard: Any, *, duration_s: float = 0.0,
                        aspect: str = "", meta: dict[str, Any] | None = None
                        ) -> "ReelSummary":
        """Mine a summary from an ``AIStoryboard`` (tolerant of missing fields).

        Reads only public attributes, so any object exposing ``title`` / ``hook`` /
        ``scenes`` (each with ``narration`` / ``keywords`` / ``cta``) works — the
        real storyboard, or a stub in a test."""
        scenes = tuple(getattr(storyboard, "scenes", ()) or ())
        narration = tuple(
            n for s in scenes if (n := (getattr(s, "narration", "") or "").strip())
        )
        keywords: list[str] = []
        for s in scenes:
            for kw in (getattr(s, "keywords", ()) or ()):
                kw = (kw or "").strip()
                if kw and kw not in keywords:
                    keywords.append(kw)
        cta_lines = tuple(
            n for s in scenes
            if getattr(s, "cta", False) and (n := (getattr(s, "narration", "") or "").strip())
        )
        hook = (getattr(storyboard, "hook", "") or "").strip()
        if not hook and narration:
            hook = narration[0]
        return cls(
            title=(getattr(storyboard, "title", "") or "").strip(),
            hook=hook,
            prompt=(getattr(storyboard, "prompt", "") or "").strip(),
            template=(getattr(storyboard, "template", "") or "general").strip() or "general",
            narration=narration,
            keywords=tuple(keywords),
            cta_lines=cta_lines,
            audience=(getattr(storyboard, "target_audience", "") or "general audience").strip(),
            tone=(getattr(storyboard, "tone", "") or "informative").strip(),
            language=(getattr(storyboard, "language", "") or "en").strip() or "en",
            duration_s=round(float(duration_s or 0.0), 3),
            aspect=aspect,
            meta=dict(meta or {}),
        )
