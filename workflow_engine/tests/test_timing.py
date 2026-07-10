"""Workflow timing-report tests (Phase C17) — pure, hermetic."""
from __future__ import annotations

from workflow_engine.core.stage import StageResult, StageStatus
from workflow_engine.core.workflow import WorkflowResult
from workflow_engine.timing import StageTiming, WorkflowTiming


def _result(durations: dict[str, tuple[float, StageStatus]]) -> WorkflowResult:
    res = WorkflowResult(run_id="r", workflow="w")
    for name, (dur, status) in durations.items():
        res.stage_results[name] = StageResult(name=name, status=status, duration_s=dur)
    return res


def test_from_result_totals_and_labels():
    res = _result({
        "storyboard": (0.4, StageStatus.COMPLETED),
        "voice": (6.2, StageStatus.COMPLETED),
        "render": (8.1, StageStatus.COMPLETED),
    })
    t = WorkflowTiming.from_result(res)
    labels = [r.label for r in t.rows]
    assert labels == ["Storyboard", "Voice", "Render"]
    assert t.total_s == 14.7
    assert t.executed_s == 14.7
    assert t.n_reused == 0


def test_cached_stages_are_marked_and_excluded_from_executed():
    res = _result({
        "storyboard": (0.0, StageStatus.CACHED),
        "voice": (0.0, StageStatus.SKIPPED),
        "render": (0.0, StageStatus.CACHED),
    })
    t = WorkflowTiming.from_result(res)
    assert all(r.status == "cached" for r in t.rows)
    assert t.n_reused == 3
    assert t.executed_s == 0.0


def test_extra_rows_are_appended_and_counted():
    res = _result({"render": (8.1, StageStatus.COMPLETED)})
    t = WorkflowTiming.from_result(
        res, extra_rows=(StageTiming("Quality", 0.1, "measured"),))
    assert [r.label for r in t.rows] == ["Render", "Quality"]
    assert t.total_s == 8.2


def test_render_text_shape():
    res = _result({"storyboard": (0.4, StageStatus.COMPLETED),
                   "voice": (6.2, StageStatus.CACHED)})
    text = WorkflowTiming.from_result(res).render_text()
    assert text.startswith("Workflow Timing")
    assert "Storyboard" in text and "0.40 s" in text
    assert "(cached)" in text          # reused stage annotated
    assert "Total" in text


def test_to_dict_is_serializable():
    res = _result({"render": (8.1, StageStatus.COMPLETED)})
    d = WorkflowTiming.from_result(res).to_dict()
    assert d["total_s"] == 8.1 and d["rows"][0]["label"] == "Render"


def test_second_run_faster_property():
    cold = WorkflowTiming.from_result(_result({"voice": (6.0, StageStatus.COMPLETED)}))
    warm = WorkflowTiming.from_result(_result({"voice": (0.0, StageStatus.CACHED)}))
    assert warm.total_s < cold.total_s
