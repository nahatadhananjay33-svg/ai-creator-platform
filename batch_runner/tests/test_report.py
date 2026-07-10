"""Batch report + summary generation."""
from __future__ import annotations

import json

from batch_runner.report import (
    REPORT_JSON,
    SUMMARY_MD,
    build_report,
    render_summary_md,
    write_reports,
)
from batch_runner.runner import BatchResult, ReelOutcome


def _result():
    outcomes = [
        ReelOutcome("reel-a", "passed", code=0, duration_s=10.0,
                    output_dir="/ws/exports/reel-a"),
        ReelOutcome("reel-b", "failed", code=2,
                    error="did not pass quality / empty output",
                    duration_s=5.0, output_dir="/ws/exports/reel-b"),
        ReelOutcome("reel-c", "skipped", code=0, duration_s=8.0,
                    output_dir="/ws/exports/reel-c"),
    ]
    return BatchResult(total=3, passed=1, failed=1, skipped=1, elapsed_s=15.0,
                       workspace="/ws", batch_dir="/ws/batch", outcomes=outcomes)


def test_report_totals_and_times():
    report = build_report(_result())
    assert (report["total"], report["passed"], report["failed"],
            report["skipped"]) == (3, 1, 1, 1)
    assert report["ok"] is False
    # generation times aggregate only the reels actually run (a + b)
    assert report["generation_times"]["total_s"] == 15.0
    assert report["generation_times"]["average_s"] == 7.5
    assert report["generation_times"]["per_reel"]["reel-a"] == 10.0
    assert len(report["reels"]) == 3


def test_summary_md_lists_reels_and_failures():
    md = render_summary_md(_result())
    assert "# Batch Report" in md
    assert "1 passed" in md and "1 failed" in md and "1 skipped" in md
    assert "reel-a" in md and "reel-b" in md and "reel-c" in md
    assert "## Failures" in md
    assert "reel-b" in md and "logs/reel-b.log" in md


def test_write_reports_roundtrip(tmp_path):
    json_path, md_path = write_reports(_result(), tmp_path / "batch")
    assert json_path.name == REPORT_JSON and md_path.name == SUMMARY_MD
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["failed"] == 1
    assert md_path.read_text(encoding="utf-8").startswith("# Batch Report")


def test_no_failures_section_when_all_pass():
    outcomes = [ReelOutcome("a", "passed", code=0, duration_s=1.0),
                ReelOutcome("b", "passed", code=0, duration_s=1.0)]
    result = BatchResult(total=2, passed=2, failed=0, skipped=0, elapsed_s=2.0,
                         workspace="/ws", batch_dir="/ws/batch", outcomes=outcomes)
    md = render_summary_md(result)
    assert "## Failures" not in md
