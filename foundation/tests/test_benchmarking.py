"""Tests for foundation.benchmarking."""
from __future__ import annotations

from pathlib import Path

from foundation.benchmarking import (
    BenchmarkCase,
    BenchmarkRunner,
    CaseResult,
    CaseStatus,
    Measurement,
    RunResult,
)
from foundation.exceptions import AdapterNotAvailableError, BenchmarkError


class _PassingCase(BenchmarkCase):
    def execute(self, result: CaseResult) -> None:
        result.add(Measurement("rtf", 0.25, "x", higher_is_better=False))


class _SkippingCase(BenchmarkCase):
    def execute(self, result: CaseResult) -> None:
        raise AdapterNotAvailableError("deps missing")


class _FailingCase(BenchmarkCase):
    def execute(self, result: CaseResult) -> None:
        raise BenchmarkError("boom")


def _runner() -> BenchmarkRunner:
    return BenchmarkRunner(title="test", monitor_resources=False)


def test_runner_statuses() -> None:
    run = _runner().run(
        [
            _PassingCase("c1", "model-a", "latency"),
            _SkippingCase("c2", "model-b", "latency"),
            _FailingCase("c3", "model-c", "latency"),
        ]
    )
    statuses = {c.case_id: c.status for c in run.cases}
    assert statuses == {
        "c1": CaseStatus.PASSED,
        "c2": CaseStatus.SKIPPED,
        "c3": CaseStatus.FAILED,
    }
    assert run.finished_at is not None
    assert run.cases[0].get_value("rtf") == 0.25
    assert run.cases[2].error is not None


def test_runner_survives_unexpected_exception() -> None:
    class Crash(BenchmarkCase):
        def execute(self, result: CaseResult) -> None:
            raise ValueError("unexpected")

    run = _runner().run([Crash("c", "s", "x")])
    assert run.cases[0].status is CaseStatus.FAILED
    assert "ValueError" in (run.cases[0].error or "")


def test_run_result_json_roundtrip(tmp_path: Path) -> None:
    run = _runner().run([_PassingCase("c1", "model-a", "latency")])
    path = run.save_json(tmp_path / "run.json")
    import json

    restored = RunResult.from_dict(json.loads(path.read_text(encoding="utf-8")))
    assert restored.run_id == run.run_id
    assert restored.cases[0].status is CaseStatus.PASSED
    assert restored.cases[0].measurements[0].name == "rtf"


def test_by_subject_grouping() -> None:
    run = _runner().run(
        [_PassingCase("c1", "a", "s1"), _PassingCase("c2", "a", "s2"), _PassingCase("c3", "b", "s1")]
    )
    grouped = run.by_subject()
    assert sorted(grouped) == ["a", "b"]
    assert len(grouped["a"]) == 2
