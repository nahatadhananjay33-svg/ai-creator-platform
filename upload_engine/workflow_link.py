"""Workflow Engine integration for the Upload Assistant (Phase C18).

The single place that reads a finished :class:`WorkflowResult` and turns it into
upload metadata. It is **read-only**: it pulls the run's storyboard (the words) and
timeline (duration + aspect) and generates from them — it mutates no artifact and
touches no engine.

    Workflow Engine -> Quality PASS -> [ this module ] -> metadata.json + upload_preview.md

The quality gate is the caller's responsibility (see the CLI): per the phase spec
the assistant runs *after* a reel passes quality, so these helpers assume a
completed run and simply read it.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from upload_engine.assistant.config import UploadConfig
from upload_engine.assistant.generate import generate_metadata
from upload_engine.assistant.metadata import UploadMetadata
from upload_engine.assistant.outputs import UploadFiles, write_upload_assets
from upload_engine.assistant.summary import ReelSummary
from upload_engine.templates.registry import UploadTemplate


def _duration_and_aspect(result: Any) -> tuple[float, str]:
    """Best-effort (duration_s, aspect) from the timeline, else the master meta."""
    timeline_art = result.artifacts.get("timeline")
    if timeline_art is not None and timeline_art.value is not None:
        tl = timeline_art.value
        aspect = getattr(getattr(tl, "meta", None), "aspect", "") or ""
        return float(getattr(tl, "duration_s", 0.0) or 0.0), aspect
    master = result.artifacts.get("master")
    if master is not None:
        meta = master.meta
        exports = meta.get("exports") or []
        aspect = exports[0].get("aspect", "") if exports else ""
        return float(meta.get("duration_s", 0.0) or 0.0), aspect
    return 0.0, ""


def summary_from_result(result: Any) -> ReelSummary:
    """Mine a :class:`ReelSummary` from a completed workflow run.

    Reads the ``storyboard`` artifact (the AIStoryboard the run produced) plus the
    timeline/master for duration and aspect. Raises ``KeyError`` if the run has no
    storyboard (nothing to write metadata from)."""
    storyboard = result.artifact("storyboard").value
    duration_s, aspect = _duration_and_aspect(result)
    return ReelSummary.from_storyboard(storyboard, duration_s=duration_s, aspect=aspect)


def generate_from_result(result: Any, *,
                         template: UploadTemplate | str | None = None,
                         config: UploadConfig | None = None) -> UploadMetadata:
    """Generate :class:`UploadMetadata` for the reel a workflow run produced."""
    return generate_metadata(summary_from_result(result), template=template,
                             config=config)


def generate_upload_assets(result: Any, out_dir: Path | str, *,
                           template: UploadTemplate | str | None = None,
                           config: UploadConfig | None = None
                           ) -> tuple[UploadMetadata, UploadFiles]:
    """Generate metadata for a run and write ``metadata.json`` + ``upload_preview.md``.

    Returns ``(metadata, files)``."""
    metadata = generate_from_result(result, template=template, config=config)
    files = write_upload_assets(metadata, out_dir)
    return metadata, files
