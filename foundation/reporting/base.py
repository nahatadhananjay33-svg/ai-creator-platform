"""Reporter interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from foundation.benchmarking import RunResult


class Reporter(ABC):
    """Writes one representation of a benchmark run to disk."""

    @abstractmethod
    def write(self, run: RunResult, output_dir: Path) -> Path:
        """Write the report; return the primary file path."""
