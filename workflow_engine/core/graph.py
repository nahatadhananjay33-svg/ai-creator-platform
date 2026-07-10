"""The dependency graph (Phase C14) — deterministic topological ordering.

A workflow is a DAG of stages; edges are the ``needs`` relation. This module owns
the graph algorithms the executor and the validator depend on:

- :meth:`DependencyGraph.topological_order` — a *stable* linear order (ties broken
  by the stage's declaration index, so the same workflow always runs in the same
  order),
- :meth:`DependencyGraph.levels` — the antichains of the DAG: each level is a set
  of stages whose dependencies are all satisfied by earlier levels, so stages in
  one level are mutually independent and **parallel-safe**,
- :meth:`DependencyGraph.validate` — every dependency resolves and the graph is
  acyclic (a cycle is a construction error, surfaced early).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from workflow_engine.core.stage import WorkflowStage


class GraphError(ValueError):
    """The dependency graph is malformed (unknown dependency or a cycle)."""


@dataclass(frozen=True)
class DependencyGraph:
    """An immutable DAG over stage names, preserving declaration order for ties."""

    order: tuple[str, ...]                       # stage names in declaration order
    needs: dict[str, tuple[str, ...]]            # name -> its upstream dependencies

    @classmethod
    def from_stages(cls, stages: Iterable[WorkflowStage]) -> "DependencyGraph":
        order: list[str] = []
        needs: dict[str, tuple[str, ...]] = {}
        for stage in stages:
            if stage.name in needs:
                raise GraphError(f"duplicate stage name {stage.name!r}")
            order.append(stage.name)
            needs[stage.name] = tuple(stage.needs)
        return cls(order=tuple(order), needs=needs)

    # ---- queries -------------------------------------------------------------
    @property
    def names(self) -> tuple[str, ...]:
        return self.order

    def dependents(self, name: str) -> tuple[str, ...]:
        """Direct successors: stages that list ``name`` in their ``needs``."""
        return tuple(n for n in self.order if name in self.needs.get(n, ()))

    def transitive_dependents(self, name: str) -> tuple[str, ...]:
        """Every stage downstream of ``name`` (its whole affected subtree)."""
        seen: set[str] = set()
        frontier = [name]
        while frontier:
            cur = frontier.pop()
            for succ in self.dependents(cur):
                if succ not in seen:
                    seen.add(succ)
                    frontier.append(succ)
        return tuple(n for n in self.order if n in seen)

    # ---- validation ----------------------------------------------------------
    def missing_dependencies(self) -> dict[str, tuple[str, ...]]:
        """Stages whose ``needs`` reference names that aren't in the graph."""
        known = set(self.order)
        out: dict[str, tuple[str, ...]] = {}
        for name in self.order:
            unknown = tuple(d for d in self.needs[name] if d not in known)
            if unknown:
                out[name] = unknown
        return out

    def find_cycle(self) -> tuple[str, ...]:
        """Return one cycle as an ordered tuple, or ``()`` if the graph is acyclic."""
        WHITE, GREY, BLACK = 0, 1, 2
        color = {n: WHITE for n in self.order}
        stack: list[str] = []

        def visit(node: str) -> tuple[str, ...]:
            color[node] = GREY
            stack.append(node)
            for dep in self.needs.get(node, ()):
                if dep not in color:          # unknown dep — reported separately
                    continue
                if color[dep] == GREY:        # back-edge -> cycle
                    i = stack.index(dep)
                    return tuple(stack[i:] + [dep])
                if color[dep] == WHITE:
                    found = visit(dep)
                    if found:
                        return found
            color[node] = BLACK
            stack.pop()
            return ()

        for n in self.order:
            if color[n] == WHITE:
                found = visit(n)
                if found:
                    return found
        return ()

    def validate(self) -> list[str]:
        """Return every structural problem (empty == a valid DAG)."""
        problems: list[str] = []
        for name, unknown in self.missing_dependencies().items():
            problems.append(f"stage {name!r} depends on unknown stage(s) {list(unknown)}")
        cycle = self.find_cycle()
        if cycle:
            problems.append("dependency cycle: " + " -> ".join(cycle))
        return problems

    # ---- ordering ------------------------------------------------------------
    def topological_order(self) -> tuple[str, ...]:
        """A deterministic topological order (declaration-index tie-break)."""
        problems = self.validate()
        if problems:
            raise GraphError("; ".join(problems))
        rank = {n: i for i, n in enumerate(self.order)}
        indegree = {n: 0 for n in self.order}
        for n in self.order:
            for _dep in self.needs[n]:
                indegree[n] += 1
        # Kahn's algorithm with a declaration-order tie-break for determinism.
        ready = sorted((n for n in self.order if indegree[n] == 0), key=rank.get)
        out: list[str] = []
        while ready:
            node = ready.pop(0)
            out.append(node)
            for succ in self.dependents(node):
                indegree[succ] -= 1
                if indegree[succ] == 0:
                    ready.append(succ)
            ready.sort(key=rank.get)
        return tuple(out)

    def levels(self) -> tuple[tuple[str, ...], ...]:
        """The DAG's antichains: ``levels()[k]`` stages depend only on earlier
        levels, so they are mutually independent and safe to run concurrently."""
        problems = self.validate()
        if problems:
            raise GraphError("; ".join(problems))
        rank = {n: i for i, n in enumerate(self.order)}
        placed: dict[str, int] = {}
        remaining = set(self.order)
        levels: list[tuple[str, ...]] = []
        while remaining:
            ready = [n for n in remaining
                     if all(dep in placed for dep in self.needs[n])]
            if not ready:  # pragma: no cover - guarded by validate()
                raise GraphError("cycle detected while levelling")
            ready.sort(key=rank.get)
            level = tuple(ready)
            levels.append(level)
            for n in ready:
                placed[n] = len(levels) - 1
                remaining.discard(n)
        return tuple(levels)
