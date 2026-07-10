"""Workflow timing report (Phase C17) — a simple per-stage timing summary.

The executor already times every stage (:attr:`StageResult.duration_s`) and marks
reused stages ``CACHED`` (which cost ~0s). This module turns a
:class:`~workflow_engine.core.workflow.WorkflowResult` into a small, readable
timing report — the "where did the time go" view a profiler prints — plus optional
extra rows (e.g. a post-render Quality check) so one report covers the whole
generation.

It is pure presentation over data the run already produced: no clocks of its own,
no re-execution, nothing mutated.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from workflow_engine.core.stage import StageStatus
from workflow_engine.core.workflow import WorkflowResult

#: Friendly labels for the default pipeline's stage names (name -> label).
STAGE_LABELS: dict[str, str] = {
    "storyboard": "Storyboard",
    "scene_plan": "Scene Planning",
    "voice": "Voice",
    "avatar": "Avatar",
    "assets": "Assets",
    "media_intel": "Media Intelligence",
    "editing": "Editing",
    "timeline": "Timeline",
    "render": "Render",
    "export": "Export",
}

#: Statuses that mean the stage was reused from cache rather than executed.
_REUSED = frozenset({StageStatus.CACHED, StageStatus.SKIPPED})


@dataclass(frozen=True)
class StageTiming:
    """One row of the timing report: a label, its seconds, and how it got there."""

    label: str
    seconds: float
    status: str          # "executed" | "cached" | "skipped" | ... | "measured"

    @property
    def reused(self) -> bool:
        return self.status in ("cached", "skipped")


@dataclass(frozen=True)
class WorkflowTiming:
    """A per-stage timing summary for one workflow run (+ optional extra rows)."""

    rows: tuple[StageTiming, ...] = ()
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def total_s(self) -> float:
        return round(sum(r.seconds for r in self.rows), 6)

    @property
    def executed_s(self) -> float:
        """Time spent in stages that actually ran (excludes cache hits)."""
        return round(sum(r.seconds for r in self.rows if not r.reused), 6)

    @property
    def n_reused(self) -> int:
        return sum(1 for r in self.rows if r.reused)

    @classmethod
    def from_result(cls, result: WorkflowResult, *,
                    labels: dict[str, str] | None = None,
                    extra_rows: tuple[StageTiming, ...] = ()) -> "WorkflowTiming":
        """Build a timing report from a completed run's per-stage durations."""
        labels = labels or STAGE_LABELS
        rows: list[StageTiming] = []
        for name in result.stage_results:
            sr = result.stage_results[name]
            label = labels.get(name, name.replace("_", " ").title())
            status = "cached" if sr.status in _REUSED else sr.status.value
            rows.append(StageTiming(label=label, seconds=round(sr.duration_s, 4),
                                    status=status))
        rows.extend(extra_rows)
        meta = {"run_id": result.run_id, "workflow": result.workflow,
                "n_reused": sum(1 for r in rows if r.reused)}
        return cls(rows=tuple(rows), meta=meta)

    # ---- presentation --------------------------------------------------------
    def render_text(self, *, title: str = "Workflow Timing") -> str:
        """The human-readable timing report."""
        width = max((len(r.label) for r in self.rows), default=8)
        lines = [title, "=" * len(title), ""]
        for r in self.rows:
            note = "" if r.status in ("executed", "completed") else f"   ({r.status})"
            lines.append(f"  {r.label:<{width}}  {r.seconds:6.2f} s{note}")
        lines.append("  " + "-" * (width + 11))
        lines.append(f"  {'Total':<{width}}  {self.total_s:6.2f} s")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_s": self.total_s,
            "executed_s": self.executed_s,
            "n_reused": self.n_reused,
            "rows": [{"label": r.label, "seconds": r.seconds, "status": r.status}
                     for r in self.rows],
            "meta": dict(self.meta),
        }
