"""Upload metadata generation (Phase C18) — summary -> the eight outputs."""
from __future__ import annotations

from upload_engine.assistant.config import UploadConfig
from upload_engine.assistant.engine import (
    UploadAssistant,
    generate_upload_metadata,
)
from upload_engine.assistant.generate import generate_metadata
from upload_engine.assistant.metadata import REQUIRED_FIELDS, UploadMetadata
from upload_engine.assistant.outputs import (
    METADATA_FILENAME,
    PREVIEW_FILENAME,
    UploadFiles,
    render_metadata_json,
    render_preview,
    write_upload_assets,
)
from upload_engine.assistant.summary import ReelSummary

__all__ = [
    "UploadAssistant",
    "generate_upload_metadata",
    "generate_metadata",
    "UploadConfig",
    "UploadMetadata",
    "REQUIRED_FIELDS",
    "ReelSummary",
    "write_upload_assets",
    "render_preview",
    "render_metadata_json",
    "UploadFiles",
    "METADATA_FILENAME",
    "PREVIEW_FILENAME",
]
