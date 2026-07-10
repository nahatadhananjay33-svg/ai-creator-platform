"""Editable upload templates (Phase C18) — one per content vertical."""
from __future__ import annotations

from upload_engine.templates.registry import (
    DEFAULT_TEMPLATE,
    TEMPLATES_PATH,
    UploadTemplate,
    available_templates,
    get_template,
)

__all__ = [
    "UploadTemplate",
    "get_template",
    "available_templates",
    "DEFAULT_TEMPLATE",
    "TEMPLATES_PATH",
]
