"""The Upload Assistant facade (Phase C18).

A thin object over the deterministic generators. Given a :class:`ReelSummary` it
returns :class:`UploadMetadata`; ``generate_from_storyboard`` is the convenience
path that mines the summary first. Holding the config on the instance mirrors the
other engines' facades (e.g. ``QualityChecker``).
"""
from __future__ import annotations

from typing import Any

from upload_engine.assistant.config import UploadConfig
from upload_engine.assistant.generate import generate_metadata
from upload_engine.assistant.metadata import UploadMetadata
from upload_engine.assistant.summary import ReelSummary
from upload_engine.templates.registry import UploadTemplate


class UploadAssistant:
    """Generate upload-ready metadata from a finished reel's summary."""

    def __init__(self, config: UploadConfig | None = None) -> None:
        self.config = config or UploadConfig()

    def generate(self, summary: ReelSummary, *,
                 template: UploadTemplate | str | None = None) -> UploadMetadata:
        """Generate the eight outputs from a mined :class:`ReelSummary`."""
        return generate_metadata(summary, template=template, config=self.config)

    def generate_from_storyboard(self, storyboard: Any, *, duration_s: float = 0.0,
                                 aspect: str = "",
                                 template: UploadTemplate | str | None = None
                                 ) -> UploadMetadata:
        """Mine a summary from an ``AIStoryboard`` then generate the metadata."""
        summary = ReelSummary.from_storyboard(storyboard, duration_s=duration_s,
                                              aspect=aspect)
        return self.generate(summary, template=template)


def generate_upload_metadata(summary: ReelSummary, *,
                             template: UploadTemplate | str | None = None,
                             config: UploadConfig | None = None) -> UploadMetadata:
    """Convenience one-shot: generate metadata from a summary."""
    return UploadAssistant(config).generate(summary, template=template)
