"""Engine-agnostic report generation from benchmark runs.

Knows nothing about voice, avatars, or any specific model: reporters consume
:class:`foundation.benchmarking.RunResult` only. Engines add their own
Markdown/recommendation reporters on top (those need engine catalogs).
"""

from foundation.reporting.base import Reporter
from foundation.reporting.csv_reporter import CsvReporter
from foundation.reporting.json_reporter import JsonReporter
from foundation.reporting.summary import RunSummary, SubjectSummary, summarize_run

__all__ = [
    "Reporter",
    "CsvReporter",
    "JsonReporter",
    "RunSummary",
    "SubjectSummary",
    "summarize_run",
]
