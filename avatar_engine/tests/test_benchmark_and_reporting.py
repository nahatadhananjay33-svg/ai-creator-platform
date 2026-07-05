"""End-to-end tests: benchmark orchestration + reporters + research reports."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from foundation.benchmarking import CaseStatus

from avatar_engine.benchmark import AvatarBenchmark, AvatarBenchmarkConfig
from avatar_engine.evaluation import AvatarHumanEvalProtocol
from avatar_engine.reporting import ResearchReportGenerator, summarize_run


@pytest.fixture(scope="module")
def small_run(tmp_path_factory: pytest.TempPathFactory):
    output_dir = tmp_path_factory.mktemp("avatar-bench-out")
    assets_dir = tmp_path_factory.mktemp("avatar-assets")
    config = AvatarBenchmarkConfig(
        adapters=["mock", "echomimic-v3"],  # echomimic-v3 must SKIP (planned adapter)
        categories=["neutral_speech", "fast_speech"],
        output_dir=str(output_dir),
        assets_dir=str(assets_dir),
        monitor_resources=False,
    )
    run, reports = AvatarBenchmark(config).run()
    return run, reports, output_dir


def test_mock_passes_and_planned_adapter_skips(small_run) -> None:  # noqa: ANN001
    run, _, _ = small_run
    by_subject = run.by_subject()
    assert all(c.status is CaseStatus.PASSED for c in by_subject["mock"])
    assert all(c.status is CaseStatus.SKIPPED for c in by_subject["echomimic-v3"])
    assert "Phase A4" in (by_subject["echomimic-v3"][0].error or "")


def test_video_artifacts_and_metrics_recorded(small_run) -> None:  # noqa: ANN001
    run, _, _ = small_run
    mock_cases = [c for c in run.cases if c.subject_id == "mock"]
    for case in mock_cases:
        assert Path(case.artifacts["video"]).exists()
        assert case.get_value("real_time_factor") is not None
        assert case.get_value("frozen_frame_ratio") is not None
        assert case.get_value("commercial_use_ok") is True


def test_reports_exist_and_parse(small_run) -> None:  # noqa: ANN001
    run, reports, _ = small_run
    with open(reports["csv"], encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert rows and {"model", "metric", "source"} <= set(rows[0])
    data = json.loads(Path(reports["json"]).read_text(encoding="utf-8"))
    assert data["run_id"] == run.run_id
    md = Path(reports["markdown"]).read_text(encoding="utf-8")
    assert "Results by model" in md
    assert "EchoMimicV3" in md  # static context table pulls from the catalog


def test_summary_aggregation(small_run) -> None:  # noqa: ANN001
    run, _, _ = small_run
    summary = summarize_run(run)
    mock = next(s for s in summary.subjects if s.subject_id == "mock")
    assert mock.pass_rate == 1.0
    assert "real_time_factor" in mock.metric_means


def test_human_eval_sheet_is_blind(small_run, tmp_path: Path) -> None:  # noqa: ANN001
    run, _, _ = small_run
    sheet, key = AvatarHumanEvalProtocol().write_score_sheet(run, tmp_path)
    with open(sheet, encoding="utf-8") as fh:
        sheet_rows = list(csv.DictReader(fh))
    assert sheet_rows and "mos_lip_sync" in sheet_rows[0]
    assert "model" not in sheet_rows[0]  # rater sheet must be blind
    with open(key, encoding="utf-8") as fh:
        key_rows = list(csv.DictReader(fh))
    assert {r["model"] for r in key_rows} == {"mock"}  # only cases with videos


def test_research_reports_generate(tmp_path: Path) -> None:
    paths = ResearchReportGenerator().write_all(tmp_path)
    with open(paths["csv"], encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) >= 12
    assert {"model_id", "commercial_use", "readiness_score"} <= set(rows[0])
    data = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert data["awards"] and data["models"]
    md = paths["markdown"].read_text(encoding="utf-8")
    assert "Best in class" in md
    assert "Overall recommendation" in md
    assert "static research priors" in md  # never presented as measurements
