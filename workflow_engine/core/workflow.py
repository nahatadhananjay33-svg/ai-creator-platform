"""The Workflow and WorkflowResult values (Phase C14).

A :class:`Workflow` is an immutable, validated bundle of stages plus the
:class:`~workflow_engine.core.graph.DependencyGraph` they induce. It is a pure
description of *what* to run and in what dependency order — it holds no run state.
The :class:`~workflow_engine.execution.executor.WorkflowExecutor` consumes a
Workflow and produces a :class:`WorkflowResult`: the per-stage outcomes, the final
artifacts, and the overall status of one execution.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from workflow_engine.core.artifact import Artifact
from workflow_engine.core.graph import DependencyGraph, GraphError
from workflow_engine.core.stage import StageResult, StageStatus, WorkflowStage


class Workflow:
    """An immutable, validated DAG of stages."""

    def __init__(self, name: str, stages: list[WorkflowStage]) -> None:
        self.name = name
        self._stages: tuple[WorkflowStage, ...] = tuple(stages)
        self._by_name: dict[str, WorkflowStage] = {}
        for stage in self._stages:
            if stage.name in self._by_name:
                raise GraphError(f"duplicate stage name {stage.name!r}")
            self._by_name[stage.name] = stage
        self.graph = DependencyGraph.from_stages(self._stages)
        problems = self.graph.validate()
        if problems:
            raise GraphError("invalid workflow: " + "; ".join(problems))

    # ---- access --------------------------------------------------------------
    @property
    def stages(self) -> tuple[WorkflowStage, ...]:
        return self._stages

    def stage(self, name: str) -> WorkflowStage:
        return self._by_name[name]

    def order(self) -> tuple[str, ...]:
        return self.graph.topological_order()

    def declared_artifacts(self) -> dict[str, str]:
        """Map every declared artifact name -> the stage that produces it."""
        out: dict[str, str] = {}
        for stage in self._stages:
            for name in stage.produces:
                out[name] = stage.name
        return out

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"Workflow({self.name!r}, stages={list(self.graph.names)})"


@dataclass
class WorkflowResult:
    """The outcome of one workflow execution."""

    run_id: str
    workflow: str
    stage_results: dict[str, StageResult] = field(default_factory=dict)
    artifacts: dict[str, Artifact] = field(default_factory=dict)
    work_dir: Any = None                     # Path to the run directory (set by the executor)

    # ---- rollups -------------------------------------------------------------
    @property
    def ok(self) -> bool:
        return not any(r.status == StageStatus.FAILED for r in self.stage_results.values())

    @property
    def failed(self) -> tuple[str, ...]:
        return tuple(n for n, r in self.stage_results.items()
                     if r.status == StageStatus.FAILED)

    def status_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {s.value: 0 for s in StageStatus}
        for r in self.stage_results.values():
            counts[r.status.value] += 1
        return counts

    def cached(self) -> tuple[str, ...]:
        return tuple(n for n, r in self.stage_results.items()
                     if r.status in (StageStatus.CACHED, StageStatus.SKIPPED))

    def executed(self) -> tuple[str, ...]:
        return tuple(n for n, r in self.stage_results.items()
                     if r.status == StageStatus.COMPLETED)

    def artifact(self, name: str) -> Artifact:
        return self.artifacts[name]

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "workflow": self.workflow,
            "ok": self.ok,
            "status_counts": self.status_counts(),
            "stages": {n: r.to_dict() for n, r in self.stage_results.items()},
            "artifacts": {n: a.descriptor() for n, a in self.artifacts.items()},
        }
