"""Run aggregation shared by all reporters."""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field

from foundation.benchmarking import CaseStatus, RunResult


@dataclass
class SubjectSummary:
    """Aggregated view of one subject (model) across a run."""

    subject_id: str
    total_cases: int
    passed: int
    failed: int
    skipped: int
    metric_means: dict[str, float] = field(default_factory=dict)
    scenarios: list[str] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        executed = self.total_cases - self.skipped
        return self.passed / executed if executed else 0.0


@dataclass
class RunSummary:
    run_id: str
    title: str
    subjects: list[SubjectSummary] = field(default_factory=list)

    def ranked_by(self, metric: str, higher_is_better: bool = True) -> list[SubjectSummary]:
        scored = [s for s in self.subjects if metric in s.metric_means]
        return sorted(scored, key=lambda s: s.metric_means[metric], reverse=higher_is_better)


def summarize_run(run: RunResult) -> RunSummary:
    summary = RunSummary(run_id=run.run_id, title=run.title)
    for subject_id, cases in sorted(run.by_subject().items()):
        metric_values: dict[str, list[float]] = {}
        scenarios: set[str] = set()
        counts = {CaseStatus.PASSED: 0, CaseStatus.FAILED: 0, CaseStatus.SKIPPED: 0}
        for case in cases:
            counts[case.status] += 1
            scenarios.add(case.scenario)
            if case.status is not CaseStatus.PASSED:
                continue
            for m in case.measurements:
                if isinstance(m.value, (int, float)) and not isinstance(m.value, bool):
                    metric_values.setdefault(m.name, []).append(float(m.value))
        summary.subjects.append(
            SubjectSummary(
                subject_id=subject_id,
                total_cases=len(cases),
                passed=counts[CaseStatus.PASSED],
                failed=counts[CaseStatus.FAILED],
                skipped=counts[CaseStatus.SKIPPED],
                metric_means={
                    name: round(statistics.fmean(vals), 4) for name, vals in metric_values.items()
                },
                scenarios=sorted(scenarios),
            )
        )
    return summary
