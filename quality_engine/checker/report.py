"""Quality report value types (Phase C16) — the deterministic verdict.

A run of the Quality Checker produces one :class:`QualityReport`: an ordered
tuple of :class:`CheckResult` values plus a single rolled-up verdict. Everything
here is immutable, JSON-serializable, and free of timestamps or any volatile
value, so the *same* rendered reel always yields the *same* report (and the same
rendered bytes hash to the same text). No AI, no ML — a check either passes,
warns, fails, or is skipped, by a fixed rule.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CheckStatus(str, Enum):
    """The outcome of a single check (also the report's rolled-up verdict).

    - ``PASS`` — the check's condition held.
    - ``WARN`` — an *advisory* element is missing (e.g. no music); the reel is
      still deliverable, so this never fails the gate.
    - ``FAIL`` — a *required* condition was violated; this fails the gate.
    - ``SKIP`` — the check could not run (a needed input was absent).
    """

    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    SKIP = "skip"

    @property
    def mark(self) -> str:
        return {"pass": "✓", "warn": "!", "fail": "✗", "skip": "-"}[self.value]


@dataclass(frozen=True)
class CheckResult:
    """One check's outcome: a stable machine ``key``, a human ``label``, its
    :class:`CheckStatus`, and a short human ``detail`` explaining the value seen."""

    key: str
    label: str
    status: CheckStatus
    detail: str = ""

    @property
    def ok(self) -> bool:
        """True unless this check FAILED (warnings/skips do not fail the gate)."""
        return self.status is not CheckStatus.FAIL

    def to_dict(self) -> dict[str, Any]:
        return {"key": self.key, "label": self.label,
                "status": self.status.value, "detail": self.detail}


@dataclass(frozen=True)
class QualityReport:
    """The full verdict for one rendered reel: every check + the overall status.

    ``overall`` is FAIL if any check FAILED, else PASS — warnings and skips never
    fail the gate (that is what makes a minimal but valid reel pass). ``ok`` is the
    boolean the Workflow gate reads."""

    checks: tuple[CheckResult, ...] = ()
    meta: dict[str, Any] = field(default_factory=dict)

    # ---- rollups -------------------------------------------------------------
    @property
    def overall(self) -> CheckStatus:
        return CheckStatus.FAIL if self.failures else CheckStatus.PASS

    @property
    def ok(self) -> bool:
        return self.overall is not CheckStatus.FAIL

    @property
    def failures(self) -> tuple[CheckResult, ...]:
        return tuple(c for c in self.checks if c.status is CheckStatus.FAIL)

    @property
    def warnings(self) -> tuple[CheckResult, ...]:
        return tuple(c for c in self.checks if c.status is CheckStatus.WARN)

    @property
    def passed(self) -> tuple[CheckResult, ...]:
        return tuple(c for c in self.checks if c.status is CheckStatus.PASS)

    def status_counts(self) -> dict[str, int]:
        counts = {s.value: 0 for s in CheckStatus}
        for c in self.checks:
            counts[c.status.value] += 1
        return counts

    # ---- presentation --------------------------------------------------------
    def render_text(self) -> str:
        """The human-readable report — the exact thing the CLI prints."""
        lines = ["QUALITY REPORT", "=" * 14, "", f"Overall: {self.overall.name}", "", "Checks"]
        for c in self.checks:
            suffix = f"  ({c.detail})" if c.detail and c.status is not CheckStatus.PASS else ""
            lines.append(f"  {c.status.mark} {c.label}{suffix}")
        lines += ["", "Warnings"]
        if self.warnings:
            lines += [f"  {c.status.mark} {c.label} ({c.detail})" for c in self.warnings]
        else:
            lines.append("  None")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall": self.overall.value,
            "ok": self.ok,
            "status_counts": self.status_counts(),
            "checks": [c.to_dict() for c in self.checks],
            "meta": dict(self.meta),
        }
