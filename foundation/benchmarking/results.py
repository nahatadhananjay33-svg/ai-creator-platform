"""Benchmark result data model.

Serializable, engine-agnostic containers. Reporters consume these directly;
evaluation frameworks attach their scores as :class:`Measurement` objects.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any

from foundation.shared_utils.timing import utc_now_iso


class CaseStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"  # e.g. adapter dependencies not installed


@dataclass(frozen=True)
class Measurement:
    """A single named measurement.

    ``source`` distinguishes automatically measured values from human
    listening scores — reports must never mix the two silently.
    """

    name: str
    value: float | str | bool | None
    unit: str = ""
    source: str = "auto"  # "auto" | "human" | "static" (from research/spec)
    higher_is_better: bool | None = None
    notes: str = ""


@dataclass
class CaseResult:
    """Outcome of one benchmark case (one adapter x one scenario x one item)."""

    case_id: str
    subject_id: str  # what is being benchmarked, e.g. adapter/model id
    scenario: str
    status: CaseStatus
    started_at: str = field(default_factory=utc_now_iso)
    duration_s: float = 0.0
    measurements: list[Measurement] = field(default_factory=list)
    artifacts: dict[str, str] = field(default_factory=dict)  # name -> file path
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def add(self, measurement: Measurement) -> None:
        self.measurements.append(measurement)

    def get_value(self, name: str) -> float | str | bool | None:
        for m in self.measurements:
            if m.name == name:
                return m.value
        return None


@dataclass
class RunResult:
    """A complete benchmark run: environment + all case results."""

    run_id: str
    title: str
    started_at: str = field(default_factory=utc_now_iso)
    finished_at: str | None = None
    environment: dict[str, Any] = field(default_factory=dict)
    config: dict[str, Any] = field(default_factory=dict)
    cases: list[CaseResult] = field(default_factory=list)

    def by_subject(self) -> dict[str, list[CaseResult]]:
        grouped: dict[str, list[CaseResult]] = {}
        for case in self.cases:
            grouped.setdefault(case.subject_id, []).append(case)
        return grouped

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def save_json(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return path

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RunResult":
        cases = []
        for c in data.get("cases", []):
            measurements = [Measurement(**m) for m in c.pop("measurements", [])]
            case = CaseResult(**{**c, "status": CaseStatus(c["status"]), "measurements": []})
            case.measurements = measurements
            cases.append(case)
        return cls(
            run_id=data["run_id"],
            title=data.get("title", ""),
            started_at=data.get("started_at", utc_now_iso()),
            finished_at=data.get("finished_at"),
            environment=data.get("environment", {}),
            config=data.get("config", {}),
            cases=cases,
        )
