"""Content Library benchmark configuration (Phase C15)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LibraryBenchmarkConfig:
    """A fixed, hermetic workload: populate N projects, then load/search/index them."""

    n_projects: int = 250
    n_queries: int = 50
    repetitions: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {"n_projects": self.n_projects, "n_queries": self.n_queries,
                "repetitions": self.repetitions}
