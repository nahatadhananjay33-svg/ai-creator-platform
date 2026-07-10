"""Batch Reel Generator — sequential productivity layer (Phase C20).

An optional layer over Version 1.0 that generates **many reels, one at a time**,
by reusing ``creator.run`` exactly as-is. No parallelism, no cloud, no
distributed rendering — just a queue, progress, resume, and a batch report.

    python -m batch_runner.run reels.csv

Read a batch of reels from CSV / JSON / YAML, generate each one sequentially
(prompt -> workflow -> quality -> upload), keep going if one fails, and write a
``batch_report.json`` + ``batch_summary.md`` at the end. Interrupted runs resume
from the first unfinished reel.
"""
from __future__ import annotations

from batch_runner.entry import BatchEntry
from batch_runner.errors import BatchError
from batch_runner.input import load_entries
from batch_runner.runner import BatchResult, BatchRunner, ReelOutcome

__all__ = [
    "BatchEntry",
    "BatchError",
    "load_entries",
    "BatchRunner",
    "BatchResult",
    "ReelOutcome",
]
