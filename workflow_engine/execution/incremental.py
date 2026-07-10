"""Incremental execution planning (Phase C14) — predict reuse vs rebuild.

The executor already *achieves* incremental execution at run time: each stage's
input hash folds in the content hashes of its inputs, so an unchanged input yields
a cache hit and a changed one re-runs exactly the affected subtree. This module
exposes that as a **dry-run what-if**: given a workflow and a prior run's journal,
:func:`plan_incremental` classifies every stage as *reuse*, *rebuild*, or *new*
without executing anything — the workflow-level analogue of the Editing Engine's
``plan_incremental`` over a Timeline.

A stage is *dirty* when it has no prior successful record, when its signature
changed (its parameters were edited), or when it is explicitly forced. The dirty
set plus its transitive dependents is exactly what will re-run ("rebuild downstream
only"); everything else with a prior success is reused.
"""
from __future__ import annotations

from dataclasses import dataclass

from workflow_engine.core.workflow import Workflow
from workflow_engine.execution.journal import RunJournal


@dataclass(frozen=True)
class IncrementalPlan:
    """What the next run would reuse vs re-execute (a prediction, not an execution)."""

    total: int
    reuse: tuple[str, ...]        # unchanged inputs -> cached outputs reused
    rebuild: tuple[str, ...]      # previously run, but must re-execute (dirty or downstream)
    new: tuple[str, ...]          # never successfully run before -> must execute
    forced: tuple[str, ...]       # explicitly forced (subset of rebuild ∪ new)
    dirty: tuple[str, ...]        # the direct triggers (changed/forced/never-run)

    @property
    def will_run(self) -> tuple[str, ...]:
        """Every stage that will execute (rebuild + new), in no particular order."""
        return tuple(sorted(set(self.rebuild) | set(self.new)))

    @property
    def n_reuse(self) -> int:
        return len(self.reuse)

    @property
    def n_run(self) -> int:
        return len(self.rebuild) + len(self.new)

    @property
    def reuse_fraction(self) -> float:
        return round(self.n_reuse / self.total, 4) if self.total else 1.0

    @property
    def needs_run(self) -> bool:
        return self.n_run > 0


def plan_incremental(workflow: Workflow, journal: RunJournal,
                     *, force: tuple[str, ...] = ()) -> IncrementalPlan:
    """Classify each stage as reuse / rebuild / new for the next run of ``workflow``."""
    graph = workflow.graph
    order = graph.topological_order()

    # Direct triggers: never-run, signature-changed, or explicitly forced.
    dirty: set[str] = set()
    for name in order:
        stage = workflow.stage(name)
        if not journal.succeeded(name):
            dirty.add(name)
        elif journal.signature_of(name) != stage.signature():
            dirty.add(name)
    forced_closure: set[str] = set()
    for f in force:
        if f in graph.names:
            forced_closure.add(f)
            forced_closure.update(graph.transitive_dependents(f))
    dirty |= forced_closure

    # Rebuild set = dirty + everything downstream of a dirty stage.
    closure: set[str] = set(dirty)
    for name in dirty:
        closure.update(graph.transitive_dependents(name))

    reuse, rebuild, new = [], [], []
    for name in order:
        if name in closure:
            (new if not journal.succeeded(name) else rebuild).append(name)
        else:
            reuse.append(name)

    return IncrementalPlan(
        total=len(order), reuse=tuple(reuse), rebuild=tuple(rebuild),
        new=tuple(new), forced=tuple(sorted(forced_closure)),
        dirty=tuple(n for n in order if n in dirty))
