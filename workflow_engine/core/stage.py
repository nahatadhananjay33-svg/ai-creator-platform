"""Workflow stages (Phase C14) — the immutable units of orchestration.

A :class:`WorkflowStage` is a **pure value**: a frozen dataclass carrying only its
declarative wiring (``name`` / ``needs`` / ``produces``) plus its own scalar
parameters. It holds no engine instances and no mutable state — engines are
constructed *inside* :meth:`run`, so a stage is hashable, comparable, and safe to
schedule in parallel. Two stages with the same parameters have the same
:meth:`signature`, which is what makes the executor's cache deterministic.

A stage's contract:

- :meth:`signature` — a stable hash of everything about the stage that affects its
  output (its parameters). Together with the content hashes of its input artifacts
  this forms the stage's *input hash* — the incremental cache key.
- :meth:`run` — invoke the existing engine APIs against the :class:`WorkflowContext`
  and return ``{artifact_name: Artifact}``. It must be deterministic and must not
  mutate the context or any input artifact.
"""
from __future__ import annotations

from dataclasses import dataclass, field, fields
from enum import Enum
from typing import TYPE_CHECKING, Any

from workflow_engine.core.artifact import Artifact, hash_json

if TYPE_CHECKING:  # avoid an import cycle; context only needed for type hints
    from workflow_engine.core.context import WorkflowContext


class StageStatus(str, Enum):
    """The lifecycle state of a stage within one run."""

    PENDING = "pending"       # not yet executed
    RUNNING = "running"       # currently executing
    COMPLETED = "completed"   # executed successfully this run
    CACHED = "cached"         # inputs unchanged -> previous outputs reused
    SKIPPED = "skipped"       # completed in a prior run and resumed unchanged
    FAILED = "failed"         # raised an error (after exhausting retries)


#: Statuses that mean "this stage's declared artifacts are available downstream".
SATISFIED_STATUSES = frozenset({StageStatus.COMPLETED, StageStatus.CACHED, StageStatus.SKIPPED})


@dataclass(frozen=True)
class WorkflowStage:
    """Base class for an immutable stage. Concrete stages are frozen dataclasses
    that add scalar parameter fields and implement :meth:`run`."""

    name: str
    needs: tuple[str, ...] = ()
    produces: tuple[str, ...] = ()

    # ---- identity / cache key ------------------------------------------------
    def _params(self) -> dict[str, Any]:
        """The stage's own parameters (every dataclass field except the wiring)."""
        skip = {"name", "needs", "produces"}
        return {f.name: getattr(self, f.name)
                for f in fields(self) if f.name not in skip}

    def signature(self) -> str:
        """A stable hash of the stage's type + parameters (its half of the cache key)."""
        return hash_json({"type": type(self).__name__, "params": self._params()})

    # ---- execution -----------------------------------------------------------
    def run(self, ctx: "WorkflowContext") -> dict[str, Artifact]:  # pragma: no cover - abstract
        """Execute the stage and return its produced artifacts (name -> Artifact)."""
        raise NotImplementedError

    # ---- helpers for concrete stages ----------------------------------------
    def _single(self, artifact: Artifact) -> dict[str, Artifact]:
        """Convenience for a one-output stage: stamp the producer and key by name."""
        return {artifact.name: artifact.with_producer(self.name)}


@dataclass
class StageResult:
    """The outcome of one stage in one run (mutable during execution, then frozen
    into the :class:`~workflow_engine.core.workflow.WorkflowResult`)."""

    name: str
    status: StageStatus = StageStatus.PENDING
    input_hash: str = ""
    attempts: int = 0
    duration_s: float = 0.0
    artifacts: tuple[str, ...] = ()          # names of produced artifacts
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "input_hash": self.input_hash,
            "attempts": self.attempts,
            "duration_s": round(self.duration_s, 6),
            "artifacts": list(self.artifacts),
            "error": self.error,
        }
