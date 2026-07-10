"""Validation regression tests (Phase C14) — graph / run / resume validators.

Hermetic: in-memory stages for the negative cases, one tiny mock pipeline run for
the positive run/resume checks.
"""
from __future__ import annotations

from workflow_engine import Presentation, WorkflowEngine
from workflow_engine.core.artifact import KIND_JSON, Artifact
from workflow_engine.core.stage import StageResult, StageStatus
from workflow_engine.core.workflow import Workflow, WorkflowResult
from workflow_engine.validation import validate_run, validate_workflow
from workflow_engine.tests.helpers import ConstStage, FlakyStage, SumStage


# --------------------------------------------------------------- static graph
def test_valid_linear_workflow_passes():
    wf = Workflow("ok", [ConstStage(name="a", produces=("a",)),
                         SumStage(name="b", needs=("a",), produces=("b",))])
    report = validate_workflow(wf, outputs=("b",))
    assert report.ok and not report.problems


def test_duplicate_producer_is_a_problem():
    wf = Workflow("dup", [ConstStage(name="a", produces=("x",)),
                          ConstStage(name="b", needs=("a",), produces=("x",))])
    report = validate_workflow(wf, outputs=("x",))
    assert any("multiple stages" in p for p in report.problems)


def test_orphan_artifact_is_warned():
    wf = Workflow("orph", [ConstStage(name="a", produces=("a",)),
                           SumStage(name="b", needs=("a",), produces=("b",))])
    # b is unconsumed; with no declared outputs it is an orphan warning
    assert any("never consumed" in w for w in validate_workflow(wf, outputs=()).warnings)
    # declaring b as an output clears it
    assert not validate_workflow(wf, outputs=("b",)).warnings


# ------------------------------------------------------------------- run
def test_validate_run_flags_failed_and_blocked():
    wf = Workflow("f", [FlakyStage(name="a", produces=("a",), fail_times=9),
                        ConstStage(name="b", needs=("a",), produces=("b",))])
    import tempfile

    from workflow_engine.execution.executor import WorkflowExecutor
    result = WorkflowExecutor(tempfile.mkdtemp()).run(wf, run_id="r1", max_attempts=1)
    report = validate_run(wf, result, outputs=("b",))
    assert any("failed" in p for p in report.problems)
    assert any("did not run" in p for p in report.problems)


def test_validate_run_flags_orphan_artifact():
    wf = Workflow("ok", [ConstStage(name="a", produces=("a",))])
    result = WorkflowResult(run_id="r", workflow="ok")
    result.stage_results["a"] = StageResult(name="a", status=StageStatus.COMPLETED,
                                            artifacts=("a",))
    result.artifacts = {"a": Artifact("a", KIND_JSON, "h"),
                        "stray": Artifact("stray", KIND_JSON, "h")}
    report = validate_run(wf, result, outputs=("a",))
    assert any("orphan artifact 'stray'" in p for p in report.problems)


# ----------------------------------------------------------- default pipeline
def test_default_pipeline_validates(tmp_path):
    engine = WorkflowEngine(root=tmp_path)
    wf = engine.build("Why investing in real estate early is beneficial",
                      template="real_estate", renderer="mock",
                      presentation=Presentation(fps=8))
    assert engine.validate(wf).ok
    result = engine.run(wf, run_id="job")
    assert engine.validate_result(wf, result).ok
    assert engine.validate_resume(wf, run_id="job").ok
