"""Persistent per-reel state that makes a batch resumable (Phase C20).

The batch writes one ``state.json`` next to its reports. Each reel is tracked by
its stable ``name`` (the output folder). After every reel the state is saved, so
an interrupted batch can be re-run and **skip the reels already completed**,
resuming from the first unfinished one.

Statuses:

- ``pending``    — not attempted yet.
- ``completed``  — the reel finished and passed (``creator.run`` returned 0).
- ``failed``     — the reel errored or did not pass; retried on the next run.

This module is pure persistence + bookkeeping — it runs nothing and imports no
engine, so it is trivially hermetic to test.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable

STATE_FILENAME = "state.json"

STATUS_PENDING = "pending"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"


@dataclass
class EntryRecord:
    """The recorded outcome of one reel."""

    name: str
    status: str = STATUS_PENDING
    code: int | None = None
    error: str = ""
    duration_s: float = 0.0
    attempts: int = 0
    output_dir: str = ""

    @property
    def completed(self) -> bool:
        return self.status == STATUS_COMPLETED


@dataclass
class BatchState:
    """The persisted state of a batch run, keyed by reel name."""

    path: Path
    records: dict[str, EntryRecord] = field(default_factory=dict)

    # ---- persistence ------------------------------------------------------- #
    @classmethod
    def load(cls, path: str | Path) -> "BatchState":
        """Load state from ``path`` (an empty state if the file is absent)."""
        path = Path(path)
        if not path.exists():
            return cls(path=path, records={})
        data = json.loads(path.read_text(encoding="utf-8"))
        records = {
            name: EntryRecord(**rec)
            for name, rec in (data.get("records") or {}).items()
        }
        return cls(path=path, records=records)

    def save(self) -> None:
        """Atomically write the state to disk (stable, sorted JSON)."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "records": {name: asdict(rec)
                        for name, rec in sorted(self.records.items())},
        }
        text = json.dumps(payload, indent=2, sort_keys=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, self.path)

    # ---- bookkeeping ------------------------------------------------------- #
    def record(self, name: str) -> EntryRecord:
        """Get (or create) the record for ``name``."""
        return self.records.setdefault(name, EntryRecord(name=name))

    def is_completed(self, name: str) -> bool:
        rec = self.records.get(name)
        return bool(rec and rec.completed)

    def mark_completed(self, name: str, *, code: int, duration_s: float,
                       output_dir: str = "") -> EntryRecord:
        rec = self.record(name)
        rec.status = STATUS_COMPLETED
        rec.code = code
        rec.error = ""
        rec.duration_s = duration_s
        rec.attempts += 1
        rec.output_dir = output_dir
        return rec

    def mark_failed(self, name: str, *, code: int | None, error: str,
                    duration_s: float) -> EntryRecord:
        rec = self.record(name)
        rec.status = STATUS_FAILED
        rec.code = code
        rec.error = error
        rec.duration_s = duration_s
        rec.attempts += 1
        return rec

    # ---- resume ------------------------------------------------------------ #
    def partition(self, entries: Iterable) -> "tuple[list, list]":
        """Split ``entries`` into (to_run, to_skip) using completed status.

        Completed reels are skipped; everything else (pending, failed, unseen)
        is run — so a batch resumes from the first unfinished reel and retries a
        previously failed one.
        """
        to_run, to_skip = [], []
        for entry in entries:
            (to_skip if self.is_completed(entry.name) else to_run).append(entry)
        return to_run, to_skip
