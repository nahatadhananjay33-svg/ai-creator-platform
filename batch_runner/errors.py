"""User-facing errors for the batch runner (Phase C20).

Mirrors :class:`creator.errors.CreatorError`: a plain-language ``message`` plus an
actionable ``hint``, so bad batch input is reported cleanly (no traceback).
"""
from __future__ import annotations

from foundation.exceptions import PlatformError


class BatchError(PlatformError):
    """A mistake in the batch input or run the user can fix."""

    def __init__(self, message: str, *, hint: str = "", **details: object) -> None:
        super().__init__(message, **details)
        self.hint = hint
