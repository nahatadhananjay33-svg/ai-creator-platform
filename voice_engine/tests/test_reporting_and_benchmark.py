"""End-to-end tests: benchmark orchestration + all reporters + human-eval sheets."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from foundation.benchmarking import CaseStatus
from voice_engine.benchmark import VoiceBenchmark, VoiceBenchmarkConfig
from voice_engine.evaluation import HumanEvalProtocol
from voice_engine.reporting import summarize_run


@pytest.fixture(scope="module")
def small_run(tmp_path_factory: pytest.TempPathFactory):
    output_dir = tmp_path_factory.mktemp("bench-out")
    config = VoiceBenchmarkConfig(
        adapters=["mock", "f5-tts"],  # f5-tts must SKIP (deps not installed)
        languages=["en", "hi-en"],
        categories=["pricing", "conversation"],
        output_dir=str(output_dir),
        monitor_resources=False,
    )
    run, reports = VoiceBenchmark(config).run()
    return run, reports, output_dir


def test_mock_cases_pass_and_heavy_adapter_skips(small_run) -> None:  # noqa: ANN001
    run, _, _ = small_run
    by_subject = run.by_subject()
    assert all(c.status is CaseStatus.PASSED for c in by_subject["mock"])
    assert all(c.status is CaseStatus.SKIPPED for c in by_subject["f5-tts"])
    skip_reason = by_subject["f5-tts"][0].error or ""
    assert "pip install" in skip_reason


def test_reports_exist_and_parse(small_run) -> None:  # noqa: ANN001
    run, reports, _ = small_run
    # CSV
    with open(reports["csv"], encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert rows and {"model", "metric", "source"} <= set(rows[0])
    # JSON
    data = json.loads(Path(reports["json"]).read_text(encoding="utf-8"))
    assert data["run_id"] == run.run_id
    assert data["environment"]["os_name"]
    # Markdown
    md = Path(reports["markdown"]).read_text(encoding="utf-8")
    assert "Results by model" in md
    assert "mock" in md and "F5-TTS" in md


def test_summary_aggregation(small_run) -> None:  # noqa: ANN001
    run, _, _ = small_run
    summary = summarize_run(run)
    mock = next(s for s in summary.subjects if s.subject_id == "mock")
    assert mock.pass_rate == 1.0
    assert "real_time_factor" in mock.metric_means
    ranked = summary.ranked_by("real_time_factor", higher_is_better=False)
    assert ranked[0].subject_id == "mock"


def test_streaming_scenario_measured(small_run) -> None:  # noqa: ANN001
    run, _, _ = small_run
    streaming_cases = [c for c in run.cases if c.scenario == "streaming" and c.subject_id == "mock"]
    assert streaming_cases
    for case in streaming_cases:
        assert case.get_value("first_chunk_latency_s") is not None


def test_human_eval_sheet_generation(small_run, tmp_path: Path) -> None:  # noqa: ANN001
    run, _, _ = small_run
    sheet, key = HumanEvalProtocol().write_score_sheet(run, tmp_path)
    with open(sheet, encoding="utf-8") as fh:
        sheet_rows = list(csv.DictReader(fh))
    assert sheet_rows and "mos_naturalness" in sheet_rows[0]
    assert "model" not in sheet_rows[0]  # rater sheet must be blind
    with open(key, encoding="utf-8") as fh:
        key_rows = list(csv.DictReader(fh))
    assert {r["model"] for r in key_rows} == {"mock"}
