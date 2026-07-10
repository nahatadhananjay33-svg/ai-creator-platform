"""The Workflow Engine facade (Phase C14) — the single entry point.

:class:`WorkflowEngine` ties the pieces together: build the default prompt-to-export
pipeline, run (or resume) it deterministically under a run id, force-rebuild named
stages, and validate a workflow or a completed run. It owns no orchestration logic
of its own — it delegates to :func:`build_default_workflow`, the
:class:`WorkflowExecutor`, and the validators — so the facade stays a thin, stable
surface for callers (the demo, benchmarks, and a future distributed scheduler).
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from foundation.shared_utils.text import new_run_id

from workflow_engine.core.workflow import Workflow, WorkflowResult
from workflow_engine.execution.executor import DEFAULT_ROOT, WorkflowExecutor
from workflow_engine.execution.incremental import IncrementalPlan, plan_incremental
from workflow_engine.execution.journal import RunJournal
from workflow_engine.stages.base import Presentation
from workflow_engine.stages.pipeline import build_default_workflow


class WorkflowEngine:
    """Compose, run, resume, and validate the production pipeline."""

    def __init__(self, root: Path | str | None = None, *, max_attempts: int = 1) -> None:
        self.root = Path(root) if root is not None else DEFAULT_ROOT
        self.executor = WorkflowExecutor(self.root, max_attempts=max_attempts)

    # ---- build ---------------------------------------------------------------
    def build(self, prompt: str, **options) -> Workflow:
        """Build the default prompt -> export workflow (see ``build_default_workflow``)."""
        return build_default_workflow(prompt, **options)

    # ---- run / resume --------------------------------------------------------
    def run(self, workflow: Workflow, *, run_id: str | None = None,
            force: Iterable[str] = (), max_attempts: int | None = None,
            params: dict | None = None) -> WorkflowResult:
        """Execute (or resume) ``workflow`` under ``run_id`` (generated if omitted)."""
        rid = run_id or new_run_id("wf")
        return self.executor.run(workflow, run_id=rid, force=force,
                                 max_attempts=max_attempts, params=params)

    def resume(self, workflow: Workflow, *, run_id: str, **kwargs) -> WorkflowResult:
        """Resume an interrupted run (same call, same ``run_id``)."""
        return self.executor.run(workflow, run_id=run_id, **kwargs)

    def rebuild(self, workflow: Workflow, *, run_id: str, stages: Iterable[str],
                **kwargs) -> WorkflowResult:
        """Force-rebuild the named stages (and their dependents) for an existing run."""
        return self.executor.run(workflow, run_id=run_id, force=tuple(stages), **kwargs)

    # ---- incremental ---------------------------------------------------------
    def incremental_plan(self, workflow: Workflow, *, run_id: str,
                         force: tuple[str, ...] = ()) -> IncrementalPlan:
        """Predict which stages the next run of ``workflow`` would reuse vs rebuild.

        A pure what-if over the persisted journal — nothing is executed."""
        journal = RunJournal.load(self.run_dir(run_id))
        return plan_incremental(workflow, journal, force=force)

    # ---- convenience ---------------------------------------------------------
    def produce(self, prompt: str, *, run_id: str | None = None, **options) -> WorkflowResult:
        """Build the default workflow for ``prompt`` and run it in one call."""
        return self.run(self.build(prompt, **options), run_id=run_id)

    def run_dir(self, run_id: str) -> Path:
        return self.executor.run_dir(run_id)
