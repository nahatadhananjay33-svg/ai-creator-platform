"""Packaged branding assets (Phase C5)."""
from __future__ import annotations

from pathlib import Path

_DEFAULT_LOGO = Path(__file__).resolve().parent / "default_logo.png"


def default_logo_path() -> Path:
    """Absolute path to the packaged placeholder logo PNG (RGBA)."""
    return _DEFAULT_LOGO
