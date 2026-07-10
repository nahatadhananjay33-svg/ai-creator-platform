"""Workflow validation (Phase C14) — is this graph, and this run, well-formed?

Two levels of checking, both returning a :class:`ValidationReport` (problems +
warnings; ``ok`` iff no problems):

- :func:`validate_workflow` — *static*, before running: the dependency graph is a
  DAG (no unknown deps, no cycles), a stable stage ordering exists, no two stages
  produce the same artifact, and no produced artifact is an orphan (never consumed
  and not a declared final output).
- :func:`validate_run` — *after* a run: no failed or blocked stages, every declared
  artifact of a satisfied stage is present (no missing artifacts), and the store
  holds no undeclared (orphan) artifacts.

:func:`validate_resume` actively checks **resume correctness**: resuming a completed
run must be a no-op — every stage reused, every artifact content hash identical.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from workflow_engine.core.stage import SATISFIED_STATUSES, StageStatus
from workflow_engine.core.workflow import Workflow, WorkflowResult


@dataclass
class ValidationReport:
    """The outcome of a validation pass."""

    problems: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems

    def extend(self, other: "ValidationReport") -> "ValidationReport":
        self.problems.extend(other.problems)
        self.warnings.extend(other.warnings)
        return self

    def to_dict(self) -> dict:
        return {"ok": self.ok, "problems": list(self.problems),
                "warnings": list(self.warnings)}


# --------------------------------------------------------------------------- static
def validate_workflow(workflow: Workflow, *, outputs: tuple[str, ...] = ()) -> ValidationReport:
    """Statically validate the workflow DAG (``outputs`` = the expected terminal
    artifact names, exempt from the orphan check)."""
    report = ValidationReport()

    # 1) dependency graph: unknown dependencies + cycles.
    report.problems.extend(workflow.graph.validate())

    # 2) stage ordering: a topological order must exist and cover every stage.
    if report.ok:
        order = workflow.graph.topological_order()
        if set(order) != set(workflow.graph.names):
            report.problems.append("stage ordering does not cover every stage")

    # 3) duplicate producers: at most one stage may produce a given artifact.
    producers: dict[str, list[str]] = {}
    for stage in workflow.stages:
        for art in stage.produces:
            producers.setdefault(art, []).append(stage.name)
    for art, owners in producers.items():
        if len(owners) > 1:
            report.problems.append(f"artifact {art!r} produced by multiple stages {owners}")

    # 4) a dependency must produce at least one artifact (else nothing to consume).
    for stage in workflow.stages:
        for dep in stage.needs:
            dep_stage = workflow.stage(dep) if dep in workflow.graph.names else None
            if dep_stage is not None and not dep_stage.produces:
                report.warnings.append(
                    f"stage {stage.name!r} depends on {dep!r} which produces no artifacts")

    # 5) orphan artifacts: produced but never consumed and not a declared output.
    consumed_stages = {dep for stage in workflow.stages for dep in stage.needs}
    exempt = set(outputs)
    for stage in workflow.stages:
        if stage.name in consumed_stages:
            continue
        for art in stage.produces:
            if art not in exempt:
                report.warnings.append(
                    f"artifact {art!r} (from {stage.name!r}) is never consumed "
                    f"and is not a declared output")
    return report


# --------------------------------------------------------------------------- run
def validate_run(workflow: Workflow, result: WorkflowResult, *,
                 outputs: tuple[str, ...] = ()) -> ValidationReport:
    """Validate a completed run: no failures, no missing/orphan artifacts."""
    report = ValidationReport()

    # failed / blocked stages.
    for name, sr in result.stage_results.items():
        if sr.status == StageStatus.FAILED:
            report.problems.append(f"stage {name!r} failed: {sr.error}")
        elif sr.status == StageStatus.PENDING:
            report.problems.append(f"stage {name!r} did not run (upstream unsatisfied)")

    # missing artifacts: a satisfied stage must have produced all it declared.
    declared = workflow.declared_artifacts()   # artifact -> producer stage
    for stage in workflow.stages:
        sr = result.stage_results.get(stage.name)
        if sr is not None and sr.status in SATISFIED_STATUSES:
            for art in stage.produces:
                if art not in result.artifacts:
                    report.problems.append(
                        f"missing artifact {art!r} from satisfied stage {stage.name!r}")

    # orphan artifacts: present in the store but declared by no stage.
    for name in result.artifacts:
        if name not in declared:
            report.problems.append(f"orphan artifact {name!r} (produced by no declared stage)")

    # terminal outputs, if named, must be present.
    for art in outputs:
        if art not in result.artifacts:
            report.problems.append(f"expected output artifact {art!r} was not produced")
    return report


# --------------------------------------------------------------------------- resume
def validate_resume(workflow: Workflow, run_id: str, executor,
                    *, outputs: tuple[str, ...] = ()) -> ValidationReport:
    """Check resume correctness: a resume of a completed run reuses every stage and
    reproduces identical artifact content hashes (executes nothing)."""
    report = ValidationReport()
    before = executor.run(workflow, run_id=run_id)          # ensure a completed run
    run_report = validate_run(workflow, before, outputs=outputs)
    if not run_report.ok:
        return report.extend(run_report)                     # can't judge resume of a bad run

    after = executor.run(workflow, run_id=run_id)            # the resume
    executed = after.executed()
    if executed:
        report.problems.append(
            f"resume re-executed stages that should have been cached: {sorted(executed)}")
    for name, art in before.artifacts.items():
        other = after.artifacts.get(name)
        if other is None:
            report.problems.append(f"resume lost artifact {name!r}")
        elif other.content_hash != art.content_hash:
            report.problems.append(
                f"resume changed artifact {name!r}: "
                f"{art.content_hash[:12]} -> {other.content_hash[:12]}")
    return report
