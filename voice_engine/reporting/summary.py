"""Run aggregation (moved to :mod:`foundation.reporting` in Phase A3).

Kept as a re-export so existing imports keep working.
"""
from __future__ import annotations

from foundation.reporting.summary import RunSummary, SubjectSummary, summarize_run

__all__ = ["RunSummary", "SubjectSummary", "summarize_run"]
