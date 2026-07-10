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
- :class:`UploadAssistant` / :func:`generate_upload_metadata` — generate the eight
  outputs from a :class:`ReelSummary`
- :class:`ReelSummary` — the mined text/facts a reel's metadata is generated from
- :class:`UploadMetadata` — the eight outputs (+ ``missing_fields`` validation hook)
- :class:`UploadConfig` — platform limits/knobs
- :func:`write_upload_assets` — write ``metadata.json`` + ``upload_preview.md``
- :func:`generate_from_result` / :func:`generate_upload_assets` /
  :func:`summary_from_result` — Workflow Engine integration
- :class:`UploadTemplate` / :func:`get_template` / :func:`available_templates` — the
  editable per-vertical templates (real_estate / finance / education / medical / general)
"""
from __future__ import annotations

from upload_engine.assistant import (
    REQUIRED_FIELDS,
    ReelSummary,
    UploadAssistant,
    UploadConfig,
    UploadFiles,
    UploadMetadata,
    generate_metadata,
    generate_upload_metadata,
    render_metadata_json,
    render_preview,
    write_upload_assets,
)
from upload_engine.templates import (
    UploadTemplate,
    available_templates,
    get_template,
)
from upload_engine.workflow_link import (
    generate_from_result,
    generate_upload_assets,
    summary_from_result,
)

__all__ = [
    # generation
    "UploadAssistant",
    "generate_upload_metadata",
    "generate_metadata",
    "ReelSummary",
    "UploadMetadata",
    "UploadConfig",
    "REQUIRED_FIELDS",
    # outputs
    "write_upload_assets",
    "render_preview",
    "render_metadata_json",
    "UploadFiles",
    # workflow integration
    "summary_from_result",
    "generate_from_result",
    "generate_upload_assets",
    # templates
    "UploadTemplate",
    "get_template",
    "available_templates",
]
