"""CSV report: one row per (case, measurement) plus a summary CSV."""
from __future__ import annotations

import csv
from pathlib import Path

from foundation.benchmarking import RunResult
from foundation.reporting.base import Reporter
from foundation.reporting.summary import summarize_run


class CsvReporter(Reporter):
    def write(self, run: RunResult, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)

        detail_path = output_dir / "results_detail.csv"
        with open(detail_path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(
                ["run_id", "case_id", "model", "scenario", "status", "duration_s",
                 "metric", "value", "unit", "source", "notes", "error"]
            )
            for case in run.cases:
                if not case.measurements:
                    writer.writerow(
                        [run.run_id, case.case_id, case.subject_id, case.scenario,
                         case.status.value, round(case.duration_s, 3), "", "", "", "", "",
                         case.error or ""]
                    )
                for m in case.measurements:
                    writer.writerow(
                        [run.run_id, case.case_id, case.subject_id, case.scenario,
                         case.status.value, round(case.duration_s, 3), m.name, m.value,
                         m.unit, m.source, m.notes, case.error or ""]
                    )

        summary = summarize_run(run)
        metric_names = sorted({name for s in summary.subjects for name in s.metric_means})
        summary_path = output_dir / "results_summary.csv"
        with open(summary_path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["model", "cases", "passed", "failed", "skipped", *metric_names])
            for s in summary.subjects:
                writer.writerow(
                    [s.subject_id, s.total_cases, s.passed, s.failed, s.skipped,
                     *[s.metric_means.get(name, "") for name in metric_names]]
                )
        return detail_path
