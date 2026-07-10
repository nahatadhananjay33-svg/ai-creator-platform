"""Quality Engine (Phase C16) — simple, local, deterministic reel QA.

A quality gate that runs *after* rendering. It is deliberately tiny and honest:

- **single-user, local-only** — no cloud, no database, no network, no auth;
- **deterministic** — a fixed rule per check, so the same rendered reel always
  yields the same report; **no AI, no ML, no scoring** of any kind;
- **read-only** — it changes no renderer, no Timeline, no engine; it only *reads*
  the files a render produced and the Timeline it was rendered from.

It verifies the things that make a rendered reel deliverable — the master exists
and is playable, it carries audio whose length matches the video, the resolution
is correct, the reel length is within the configured limits — and surfaces the
optional creative elements (avatar, voice, captions, branding, music) as warnings
when absent. The verdict is a single PASS/FAIL the Workflow gate can read.

    Workflow Engine -> Render -> Export -> Quality Check -> PASS | FAIL

Public API:
- :class:`QualityChecker` / :func:`check_reel` — run the checks on a reel
- :class:`ReelArtifacts` / :class:`ExportInfo` — what to check (built from a
  ``RenderResult`` or a workflow run)
- :class:`QualityReport` / :class:`CheckResult` / :class:`CheckStatus` — the verdict
- :class:`QualityConfig` — thresholds/limits
- :func:`check_workflow_result` — quality-gate a Workflow Engine run
"""
from __future__ import annotations

from quality_engine.checker import (
    CHECKS,
    CheckResult,
    CheckStatus,
    ExportInfo,
    ExportProbe,
    QualityChecker,
    QualityConfig,
    QualityReport,
    ReelArtifacts,
    ReelInspection,
    check_reel,
    inspect_reel,
    run_checks,
)

__version__ = "1.0.0"

__all__ = [
    "QualityChecker",
    "check_reel",
    "QualityConfig",
    "QualityReport",
    "CheckResult",
    "CheckStatus",
    "ReelArtifacts",
    "ExportInfo",
    "ExportProbe",
    "ReelInspection",
    "inspect_reel",
    "run_checks",
    "CHECKS",
]
