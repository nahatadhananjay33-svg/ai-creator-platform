"""Upload Assistant (Phase C18) — generate upload-ready metadata for a finished reel.

A small, **local-only, single-user** assistant that runs *after* a reel is rendered
and quality-checked. Given a completed workflow run it produces the copy a creator
pastes into each platform — a YouTube title/description, Instagram/Facebook captions,
a LinkedIn post, hashtags, thumbnail text, and a suggested filename — plus two files:

    metadata.json          # machine-readable, one field per output
    upload_preview.md      # human-readable, copy-paste-ready per platform

It is deliberately simple and honest:

- **local-only, single-user** — no cloud, no OAuth, no social-media APIs;
- **deterministic** — the words come from the reel's own storyboard (title / hook /
  narration / keywords); a template adds only presentation (emoji, hashtags, CTAs).
  **No AI, no network, no automatic publishing, no scheduling, no analytics**;
- **read-only** — it changes no engine and no artifact; it only *reads* the finished
  run and *writes* the two upload files.

    Workflow Engine -> Quality PASS -> Upload Assistant -> metadata.json + upload_preview.md

Public API:
- :class:`UploadTemplate` / :func:`get_template` / :func:`available_templates` — the
  editable per-vertical templates (real_estate / finance / education / medical / general).
"""
from __future__ import annotations

from upload_engine.templates import (
    UploadTemplate,
    available_templates,
    get_template,
)

__all__ = [
    "UploadTemplate",
    "get_template",
    "available_templates",
]
