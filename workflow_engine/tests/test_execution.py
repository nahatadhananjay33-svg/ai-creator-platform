"""Executor regression tests (Phase C14) — resume, retry, incremental, cache, scheduling.

Fully hermetic and deterministic (tiny in-memory stages; no engine, GPU, or API).
"""
from __future__ import annotations

import pytest

from workflow_engine.core.stage import StageStatus
from workflow_engine.core.workflow import Workflow
from workflow_engine.execution.executor import WorkflowExecutor
from workflow_engine.execution.incremental import plan_incremental
from workflow_engine.execution.journal import RunJournal
from workflow_engine.tests.helpers import CALLS, ConstStage, FlakyStage, SumStage, reset_calls


@pytest.fixture(autouse=True)
def _reset():
    reset_calls()


def _chain(a=1, b=10, c=100) -> Workflow:
    return Workflow("chain", [
        ConstStage(name="a", produces=("a",), value=a),
        SumStage(name="b", needs=("a",), produces=("b",), base=b),
        SumStage(name="c", needs=("b",), produces=("c",), base=c),
    ])


# --------------------------------------------------------------------- basic
def test_runs_in_dependency_order_and_computes(tmp_path):
    r = WorkflowExecutor(tmp_path).run(_chain(), run_id="r1")
    assert r.ok and r.status_counts()["completed"] == 3
    assert r.artifact("c").value == 111          # 100 + (10 + 1)


def test_stage_must_produce_declared_artifacts(tmp_path):
    class Bad(ConstStage):
        def run(self, ctx):
            return {}                             # declares ("a",) but returns nothing
    wf = Workflow("bad", [Bad(name="a", produces=("a",))])
    r = WorkflowExecutor(tmp_path).run(wf, run_id="r1")
    assert r.stage_results["a"].status == StageStatus.FAILED


# -------------------------------------------------------------------- resume
def test_resume_reuses_all_stages(tmp_path):
    ex = WorkflowExecutor(tmp_path)
    ex.run(_chain(), run_id="r1")
    assert CALLS == {"a": 1, "b": 1, "c": 1}
    r2 = ex.run(_chain(), run_id="r1")
    assert r2.status_counts()["cached"] == 3
    assert CALLS == {"a": 1, "b": 1, "c": 1}      # nothing re-executed


def test_resume_in_fresh_executor_decodes_from_disk(tmp_path):
    WorkflowExecutor(tmp_path).run(_chain(), run_id="r1")
    reset_calls()
    r = WorkflowExecutor(tmp_path).run(_chain(), run_id="r1")   # "fresh process"
    assert not CALLS                               # zero executions
    assert r.artifact("c").value == 111            # decoded from the journal


# --------------------------------------------------------------------- retry
def test_retry_succeeds_within_max_attempts(tmp_path):
    wf = Workflow("f", [FlakyStage(name="a", produces=("a",), fail_times=2)])
    r = WorkflowExecutor(tmp_path).run(wf, run_id="r1", max_attempts=3)
    assert r.ok and r.stage_results["a"].attempts == 3


def test_retry_exhausted_fails_and_blocks_downstream(tmp_path):
    wf = Workflow("f", [
        FlakyStage(name="a", produces=("a",), fail_times=9),
        ConstStage(name="b", needs=("a",), produces=("b",), value=5),
    ])
    r = WorkflowExecutor(tmp_path).run(wf, run_id="r1", max_attempts=2)
    assert not r.ok and r.failed == ("a",)
    assert r.stage_results["b"].status == StageStatus.PENDING     # never ran


def test_failed_run_resumes_after_fix(tmp_path):
    ex = WorkflowExecutor(tmp_path)
    bad = Workflow("f", [FlakyStage(name="a", produces=("a",), fail_times=9),
                         ConstStage(name="b", needs=("a",), produces=("b",), value=5)])
    assert not ex.run(bad, run_id="r1", max_attempts=1).ok
    reset_calls()
    good = Workflow("f", [FlakyStage(name="a", produces=("a",), fail_times=0),
                          ConstStage(name="b", needs=("a",), produces=("b",), value=5)])
    r = ex.run(good, run_id="r1")
    assert r.ok and set(r.executed()) == {"a", "b"}


# --------------------------------------------------------------- incremental
def test_change_rebuilds_only_downstream(tmp_path):
    ex = WorkflowExecutor(tmp_path)
    ex.run(_chain(b=10), run_id="r1")
    reset_calls()
    r = ex.run(_chain(b=20), run_id="r1")          # only b's param changed
    assert set(r.executed()) == {"b", "c"} and r.cached() == ("a",)
    assert "a" not in CALLS                          # a truly not re-run
    assert r.artifact("c").value == 121              # 100 + (20 + 1)


def test_idempotent_rerun_upstream_stops_cascade(tmp_path):
    # c depends on b; if b re-runs but yields the SAME output, c is still reused.
    ex = WorkflowExecutor(tmp_path)
    wf = Workflow("chain", [
        ConstStage(name="a", produces=("a",), value=1),
        SumStage(name="b", needs=("a",), produces=("b",), base=10),
        SumStage(name="c", needs=("b",), produces=("c",), base=100),
    ])
    ex.run(wf, run_id="r1")
    reset_calls()
    r = ex.rebuild(wf, run_id="r1", stages=["b"])    # force b only
    assert "b" in r.executed()                        # b re-ran (forced)
    assert "c" in r.executed()                        # c is downstream of a forced stage


def test_force_expands_to_downstream(tmp_path):
    ex = WorkflowExecutor(tmp_path)
    ex.run(_chain(), run_id="r1")
    reset_calls()
    r = ex.rebuild(_chain(), run_id="r1", stages=["b"])
    assert set(r.executed()) == {"b", "c"} and r.cached() == ("a",)


# ------------------------------------------------------ incremental planner
def test_plan_incremental_predicts_reuse(tmp_path):
    ex = WorkflowExecutor(tmp_path)
    ex.run(_chain(b=10), run_id="r1")
    journal = RunJournal.load(ex.run_dir("r1"))
    # unchanged workflow -> everything reused
    plan = plan_incremental(_chain(b=10), journal)
    assert plan.reuse_fraction == 1.0 and not plan.needs_run
    # changed b -> predict b, c rebuild; a reused
    plan2 = plan_incremental(_chain(b=20), journal)
    assert set(plan2.will_run) == {"b", "c"} and plan2.reuse == ("a",)


def test_plan_incremental_matches_actual(tmp_path):
    ex = WorkflowExecutor(tmp_path)
    ex.run(_chain(b=10), run_id="r1")
    journal = RunJournal.load(ex.run_dir("r1"))
    plan = plan_incremental(_chain(b=20), journal)
    reset_calls()
    r = ex.run(_chain(b=20), run_id="r1")
    assert set(plan.will_run) == set(r.executed())
    assert set(plan.reuse) == set(r.cached())


# ------------------------------------------------ parallel-safe scheduling
def _diamond(order):
    stages_by_name = {
        "a": ConstStage(name="a", produces=("a",), value=1),
        "b": SumStage(name="b", needs=("a",), produces=("b",), base=10),
        "c": SumStage(name="c", needs=("a",), produces=("c",), base=100),
        "d": SumStage(name="d", needs=("b", "c"), produces=("d",), base=0),
    }
    return Workflow("diamond", [stages_by_name[n] for n in order])


def test_independent_stages_share_a_level():
    wf = _diamond(["a", "b", "c", "d"])
    levels = wf.graph.levels()
    assert set(levels[1]) == {"b", "c"}          # no edge between b and c


def test_declaration_order_does_not_change_results(tmp_path):
    # b and c are independent; permuting their declaration order must not change any
    # artifact's content hash — the definition of parallel-safe.
    r1 = WorkflowExecutor(tmp_path / "o1").run(_diamond(["a", "b", "c", "d"]), run_id="r")
    r2 = WorkflowExecutor(tmp_path / "o2").run(_diamond(["a", "c", "b", "d"]), run_id="r")
    for name in ("a", "b", "c", "d"):
        assert r1.artifact(name).content_hash == r2.artifact(name).content_hash
    assert r1.artifact("d").value == r2.artifact("d").value == 112   # 0 + (10+1) + (100+1)
