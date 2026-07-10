"""Upload output files (Phase C18) — write metadata.json + upload_preview.md.

Two deliverables per reel:

- ``metadata.json`` — the machine-readable record (one field per output), for tools
  or a later import step;
- ``upload_preview.md`` — a human-readable, **copy-paste-ready** sheet: each output
  sits in its own fenced block so a creator can copy a whole caption in one go and
  paste it straight into YouTube / Instagram / etc.

Both are written deterministically (pretty JSON, UTF-8, stable key order), so the
same metadata always produces byte-identical files.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from upload_engine.assistant.metadata import UploadMetadata

METADATA_FILENAME = "metadata.json"
PREVIEW_FILENAME = "upload_preview.md"

#: Ordered (heading, attribute) pairs for the per-platform preview sections.
_SECTIONS: tuple[tuple[str, str], ...] = (
    ("▶️  YouTube — Title", "youtube_title"),
    ("▶️  YouTube — Description", "youtube_description"),
    ("📸  Instagram — Caption", "instagram_caption"),
    ("👍  Facebook — Caption", "facebook_caption"),
    ("💼  LinkedIn — Post", "linkedin_post"),
    ("🖼️  Thumbnail Text", "thumbnail_text"),
    ("📁  Suggested Filename", "suggested_filename"),
)


@dataclass(frozen=True)
class UploadFiles:
    """Paths to the two files the assistant wrote."""

    metadata_json: Path
    preview_md: Path


def _fenced(body: str) -> str:
    """A copy-paste fenced block (guards against backticks in the content)."""
    fence = "```"
    while fence in body:
        fence += "`"
    return f"{fence}\n{body}\n{fence}"


def render_preview(metadata: UploadMetadata) -> str:
    """Render the copy-paste ``upload_preview.md`` markdown."""
    title = metadata.source_title or metadata.youtube_title
    parts = [
        f"# Upload Preview — {title}".rstrip(" —"),
        f"*Template: `{metadata.template}` · Duration: {metadata.duration_s:g}s · "
        f"Aspect: {metadata.aspect or 'n/a'}*",
        "> Copy any block below straight into the platform.",
    ]
    for heading, attr in _SECTIONS:
        parts.append(f"## {heading}")
        parts.append(_fenced(str(getattr(metadata, attr))))
    # Hashtags get their own space-joined block (the canonical set).
    parts.append("## #️⃣  Hashtags")
    parts.append(_fenced(" ".join(metadata.hashtags)))
    return "\n\n".join(parts) + "\n"


def render_metadata_json(metadata: UploadMetadata) -> str:
    """Render the pretty ``metadata.json`` text (UTF-8, stable order)."""
    return json.dumps(metadata.to_dict(), indent=2, ensure_ascii=False) + "\n"


def write_upload_assets(metadata: UploadMetadata, out_dir: Path | str) -> UploadFiles:
    """Write ``metadata.json`` + ``upload_preview.md`` into ``out_dir``.

    The directory is created if missing. Returns the two written paths."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    metadata_path = out / METADATA_FILENAME
    preview_path = out / PREVIEW_FILENAME
    metadata_path.write_text(render_metadata_json(metadata), encoding="utf-8")
    preview_path.write_text(render_preview(metadata), encoding="utf-8")
    return UploadFiles(metadata_json=metadata_path, preview_md=preview_path)
