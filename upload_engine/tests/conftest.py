"""Shared hermetic fixtures for upload_engine tests (Phase C18).

No APIs, no GPU, no network. A tiny storyboard stub (duck-typed like the real
``AIStoryboard`` — title / hook / scenes with narration / keywords / cta) plus a
mined :class:`ReelSummary` cover the generators without running the pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from upload_engine.assistant.summary import ReelSummary


@dataclass(frozen=True)
class StubScene:
    narration: str
    keywords: tuple[str, ...] = ()
    cta: bool = False


@dataclass(frozen=True)
class StubStoryboard:
    """Duck-typed like AIStoryboard — enough for ReelSummary.from_storyboard."""

    title: str = "Why investing in real estate early is beneficial"
    hook: str = "Thinking about property? Start earlier than you think."
    prompt: str = "Why investing in real estate early is beneficial"
    template: str = "real_estate"
    tone: str = "confident"
    target_audience: str = "aspiring property investors"
    language: str = "en"
    scenes: tuple[StubScene, ...] = field(default_factory=lambda: (
        StubScene("Buying property early lets compounding work for you.",
                  keywords=("real estate", "compounding")),
        StubScene("Over 70 percent of investors wish they had started sooner.",
                  keywords=("investing", "property")),
        StubScene("Follow for more real-estate tips.",
                  keywords=("real estate tips",), cta=True),
    ))


@pytest.fixture
def storyboard() -> StubStoryboard:
    return StubStoryboard()


@pytest.fixture
def summary(storyboard) -> ReelSummary:
    return ReelSummary.from_storyboard(storyboard, duration_s=42.0, aspect="9:16")
