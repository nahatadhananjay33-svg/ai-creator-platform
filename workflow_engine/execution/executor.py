"""The workflow executor (Phase C14) — deterministic run / resume / retry / incremental.

The executor walks a :class:`~workflow_engine.core.workflow.Workflow` in a stable
topological order and, for each stage, computes an **input hash** from three
deterministic parts:

    input_hash = H( stage.signature(),  { input_artifact.content_hash },  run_salt )

Because a stage's ``needs`` make its input hash depend on the *content* of its
upstream artifacts, the cache is transitive: if an upstream output is unchanged its
content hash is identical, so every downstream input hash is identical too and the
whole downstream chain is reused — and if an upstream output changes, exactly the
affected subtree re-runs. That one rule gives both incremental execution (M3) and
resume (M1): a stage is reused whenever the journal holds a prior success with the
same input hash and its artifact payloads still exist on disk.

Guarantees:
- **Deterministic** — stable ordering, no wall-clock in any hash, per-stage RNG-free.
- **Resume** — an interrupted run continues; already-satisfied stages are skipped.
- **Retry** — a failing stage is retried up to ``max_attempts``; a downstream stage
  whose upstream failed is left ``PENDING`` (never run on missing inputs).
- **force** — named stages (and their transitive dependents) are always re-executed.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from foundation.constants.paths import REEL_OUTPUT_DIR, ensure_dir
from foundation.logging import get_logger
from foundation.shared_utils.hashing import sha256_text
from foundation.shared_utils.timing import Stopwatch

from workflow_engine.core.artifact import Artifact
from workflow_engine.core.context import WorkflowContext
from workflow_engine.core.stage import (
    SATISFIED_STATUSES,
    StageResult,
    StageStatus,
    WorkflowStage,
)
from workflow_engine.core.workflow import Workflow, WorkflowResult
from workflow_engine.execution.journal import RunJournal

logger = get_logger("workflow_engine")

DEFAULT_ROOT = REEL_OUTPUT_DIR / "workflow_runs"


class WorkflowExecutor:
    """Executes a workflow deterministically, with resume/retry/incremental reuse."""

    def __init__(self, root: Path | str | None = None, *, max_attempts: int = 1) -> None:
        self.root = Path(root) if root is not None else DEFAULT_ROOT
        self.max_attempts = max(1, max_attempts)

    # ------------------------------------------------------------------- run
    def run(
        self,
        workflow: Workflow,
        *,
        run_id: str,
        params: dict | None = None,
        force: Iterable[str] = (),
        max_attempts: int | None = None,
    ) -> WorkflowResult:
        """Execute (or resume) ``workflow`` under ``run_id`` and return the result.

        The run directory is ``root/run_id``; re-invoking with the same ``run_id``
        resumes it. ``force`` re-executes the named stages and everything downstream
        of them even if their inputs are unchanged.
        """
        run_dir = ensure_dir(self.root / run_id)
        attempts = max(1, max_attempts or self.max_attempts)
        journal = RunJournal.load(run_dir)
        ctx = WorkflowContext(run_dir, params=params)
        result = WorkflowResult(run_id=run_id, workflow=workflow.name)

        forced = self._expand_forced(workflow, force)
        order = workflow.order()
        logger.info("Workflow run started", extra={"context": {
            "run_id": run_id, "workflow": workflow.name, "stages": len(order),
            "forced": sorted(forced)}})

        for name in order:
            stage = workflow.stage(name)
            sr = StageResult(name=name)
            result.stage_results[name] = sr

            # A stage whose upstream failed/was-skipped cannot run: leave PENDING.
            if not self._inputs_ready(stage, result):
                sr.status = StageStatus.PENDING
                journal.mark(name, sr.status.value)
                logger.warning("Stage blocked (upstream not satisfied)",
                               extra={"context": {"run_id": run_id, "stage": name}})
                continue

            sr.input_hash = self._input_hash(stage, ctx)

            if name not in forced and journal.reusable(name, sr.input_hash):
                self._reuse(name, stage, journal, ctx, sr)
                logger.info("Stage reused (cache hit)", extra={"context": {
                    "run_id": run_id, "stage": name, "input_hash": sr.input_hash[:12]}})
                continue

            self._execute(stage, ctx, sr, attempts)
            status = StageStatus.COMPLETED if sr.status == StageStatus.COMPLETED else sr.status
            produced = {n: ctx.artifact(n) for n in sr.artifacts}
            if status == StageStatus.COMPLETED:
                journal.upsert(name, status.value, sr.input_hash, produced,
                               signature=stage.signature())
            else:
                journal.mark(name, sr.status.value, sr.input_hash,
                             signature=stage.signature(), error=sr.error)
            journal.save(run_id, workflow.name)

        # Materialize every artifact's value (decoding any reused-from-disk ones)
        # so the returned result is self-contained and directly inspectable.
        for art_name in list(ctx.artifacts()):
            ctx.value(art_name)
        result.artifacts = ctx.artifacts()
        result.work_dir = run_dir
        journal.save(run_id, workflow.name)
        logger.info("Workflow run finished", extra={"context": {
            "run_id": run_id, "ok": result.ok, **result.status_counts()}})
        return result

    def resume(self, workflow: Workflow, *, run_id: str, **kwargs) -> WorkflowResult:
        """Alias for :meth:`run` — the same call resumes an existing ``run_id``."""
        return self.run(workflow, run_id=run_id, **kwargs)

    def rebuild(self, workflow: Workflow, *, run_id: str, stages: Iterable[str],
                **kwargs) -> WorkflowResult:
        """Force-rebuild the named stages (and their dependents) for an existing run."""
        return self.run(workflow, run_id=run_id, force=tuple(stages), **kwargs)

    def run_dir(self, run_id: str) -> Path:
        """The directory that holds ``run_id``'s journal and artifact payloads."""
        return self.root / run_id

    # ------------------------------------------------------------- internals
    def _expand_forced(self, workflow: Workflow, force: Iterable[str]) -> set[str]:
        """A forced stage forces its whole downstream subtree (its inputs may change)."""
        forced: set[str] = set()
        for name in force:
            if name in workflow.graph.names:
                forced.add(name)
                forced.update(workflow.graph.transitive_dependents(name))
        return forced

    def _inputs_ready(self, stage: WorkflowStage, result: WorkflowResult) -> bool:
        """True if every upstream stage reached a satisfied status this run."""
        for dep in stage.needs:
            dep_result = result.stage_results.get(dep)
            if dep_result is None or dep_result.status not in SATISFIED_STATUSES:
                return False
        return True

    def _input_hash(self, stage: WorkflowStage, ctx: WorkflowContext) -> str:
        """H(stage signature + the content hashes of its input artifacts + salt).

        Deterministic and content-addressed: a stage depends on the *content* of
        every artifact its ``needs`` produced, so an unchanged upstream yields an
        unchanged input hash (reuse) and a changed upstream re-runs exactly the
        affected subtree. ``salt`` is an optional caller override (empty by default),
        which keeps identical params across resumes mapping to the same key."""
        parts = [f"sig={stage.signature()}"]
        for dep in sorted(stage.needs):
            for art_name in sorted(a for a, art in ctx.artifacts().items()
                                   if art.producer == dep):
                parts.append(f"in={art_name}={ctx.artifact(art_name).content_hash}")
        parts.append(f"salt={ctx.params.get('salt', '')}")
        return sha256_text("\n".join(parts))

    def _reuse(self, name: str, stage: WorkflowStage, journal: RunJournal,
               ctx: WorkflowContext, sr: StageResult) -> None:
        """Load a stage's cached artifacts into the context without executing it."""
        artifacts = journal.load_artifacts(name)
        refs = journal.load_refs(name)
        for art_name, art in artifacts.items():
            ctx.put(art)
            ctx.put_ref(art_name, refs[art_name])
        sr.artifacts = tuple(artifacts.keys())
        sr.status = StageStatus.CACHED
        rec = journal.record(name)
        sr.input_hash = rec.input_hash if rec else sr.input_hash

    def _execute(self, stage: WorkflowStage, ctx: WorkflowContext,
                 sr: StageResult, attempts: int) -> None:
        """Run one stage with retries; record its artifacts or its final error."""
        last_error: str | None = None
        for attempt in range(1, attempts + 1):
            sr.attempts = attempt
            sr.status = StageStatus.RUNNING
            try:
                with Stopwatch() as sw:
                    produced = stage.run(ctx)
                sr.duration_s += sw.elapsed_s
                self._validate_outputs(stage, produced)
                for art in produced.values():
                    ctx.put(art)
                sr.artifacts = tuple(produced.keys())
                sr.status = StageStatus.COMPLETED
                sr.error = None
                return
            except Exception as exc:  # noqa: BLE001 - a stage failure must not crash the run
                last_error = f"{type(exc).__name__}: {exc}"
                logger.error("Stage failed", extra={"context": {
                    "stage": stage.name, "attempt": attempt, "error": last_error}})
        sr.status = StageStatus.FAILED
        sr.error = last_error

    def _validate_outputs(self, stage: WorkflowStage, produced: dict[str, Artifact]) -> None:
        """A stage must return exactly the artifacts it declares in ``produces``."""
        got = set(produced)
        want = set(stage.produces)
        if got != want:
            missing = sorted(want - got)
            extra = sorted(got - want)
            raise ValueError(
                f"stage {stage.name!r} produced {sorted(got)}; "
                f"declared {sorted(want)} (missing={missing}, unexpected={extra})")
