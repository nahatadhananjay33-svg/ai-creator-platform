"""Shared test helpers (Phase C14) — tiny in-memory stages for fast, hermetic tests.

These deterministic stages exercise the core executor (graph, cache, resume, retry,
scheduling) without touching any engine, so the bulk of the suite runs in
milliseconds. The full engine pipeline is covered separately in ``test_stages.py``.
"""
from __future__ import annotations

from dataclasses import dataclass

from workflow_engine.core.artifact import KIND_JSON, Artifact, hash_json
from workflow_engine.core.stage import WorkflowStage

#: process-wide call counters so tests can assert what actually executed
CALLS: dict[str, int] = {}


def reset_calls() -> None:
    CALLS.clear()


@dataclass(frozen=True)
class SumStage(WorkflowStage):
    """Emits ``base + sum(inputs)`` as a JSON artifact; records each execution."""

    base: int = 0

    def run(self, ctx):
        CALLS[self.name] = CALLS.get(self.name, 0) + 1
        total = self.base + sum(int(ctx.value(dep)) for dep in self.needs)
        return self._single(Artifact(self.produces[0], KIND_JSON,
                                     hash_json(total), value=total))


@dataclass(frozen=True)
class ConstStage(WorkflowStage):
    """Emits a constant value (a source stage)."""

    value: int = 0

    def run(self, ctx):
        CALLS[self.name] = CALLS.get(self.name, 0) + 1
        return self._single(Artifact(self.produces[0], KIND_JSON,
                                     hash_json(self.value), value=self.value))


@dataclass(frozen=True)
class FlakyStage(WorkflowStage):
    """Fails its first ``fail_times`` executions, then succeeds (for retry tests)."""

    fail_times: int = 0

    def run(self, ctx):
        CALLS[self.name] = CALLS.get(self.name, 0) + 1
        if CALLS[self.name] <= self.fail_times:
            raise RuntimeError(f"flaky {self.name} attempt {CALLS[self.name]}")
        return self._single(Artifact(self.produces[0], KIND_JSON,
                                     hash_json("ok"), value="ok"))
