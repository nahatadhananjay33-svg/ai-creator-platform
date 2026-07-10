"""User-facing errors for the Version 1.0 command (Phase C19).

:class:`CreatorError` carries a plain-language ``message`` plus an optional
actionable ``hint`` so the ``creator.run`` command can tell a creator what went
wrong *and* what to do about it — without ever showing a Python traceback for an
ordinary mistake (empty prompt, missing FFmpeg, unknown template).

The friendly top-level handler that turns these into clean console output lives
in :mod:`creator.run` (added alongside the command itself).
"""
from __future__ import annotations

from foundation.exceptions import PlatformError


class CreatorError(PlatformError):
    """A mistake the user can fix, reported without a stack trace.

    ``hint`` is a short, actionable suggestion shown under the error message.
    """

    def __init__(self, message: str, *, hint: str = "", **details: object) -> None:
        super().__init__(message, **details)
        self.hint = hint
