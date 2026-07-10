"""Sequential batch execution (Phase C20).

:class:`BatchRunner` generates each reel **one at a time** by reusing
``creator.run`` exactly as-is — no parallelism, no cloud, no new engines. It:

- resumes: skips reels already completed in a prior run (via :class:`BatchState`);
- reuses: builds a ``CreatorConfig`` per entry and calls ``creator.run.run``;
- is robust: if one reel raises or fails, it logs the error and continues;
- reports: returns a :class:`BatchResult` and persists state after every reel.

The actual per-reel call is injected (``reel_runner``) so the orchestration is
hermetically testable without rendering; the default runs the real pipeline.
"""
from __future__ import annotations

import io
import time
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from foundation.config.loader import deep_merge
from foundation.exceptions import PlatformError

from creator.config import CreatorConfig, load_creator_config
from creator.paths import Workspace, resolve_workspace

from batch_runner.entry import BatchEntry
from batch_runner.progress import Progress
from batch_runner.queue.state import STATE_FILENAME, BatchState

#: signature of the injected per-reel runner: (cfg, name) -> exit code.
ReelRunner = Callable[[CreatorConfig, str], int]


def default_reel_runner(cfg: CreatorConfig, name: str) -> int:
    """Reuse ``creator.run`` unchanged: pre-flight, then run one reel."""
    from creator.run import _preflight, run as creator_run

    _preflight(cfg)
    return creator_run(cfg, name=name, quiet=True)


@dataclass
class ReelOutcome:
    """This batch invocation's outcome for one reel."""

    name: str
    status: str                       # "passed" | "failed" | "skipped"
    code: int | None = None
    error: str = ""
    duration_s: float = 0.0
    output_dir: str = ""


@dataclass
class BatchResult:
    """The result of a whole batch invocation."""

    total: int
    passed: int
    failed: int
    skipped: int
    elapsed_s: float
    workspace: str
    batch_dir: str
    outcomes: list[ReelOutcome] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True if no reel failed in this invocation."""
        return self.failed == 0


class BatchRunner:
    """Run a batch of reels sequentially, with resume, progress, and a result."""

    def __init__(self, entries: list[BatchEntry], *, workspace_root: str | Path,
                 base_config: str | Path | None = None,
                 batch_dir: str | Path | None = None,
                 reel_runner: ReelRunner | None = None,
                 clock: Callable[[], float] = time.monotonic,
                 out: Callable[[str], None] = print) -> None:
        self.entries = entries
        self.base_config = base_config
        self.reel_runner = reel_runner or default_reel_runner
        self.clock = clock
        self.out = out
        self.workspace = resolve_workspace(workspace_root)
        self.batch_dir = Path(batch_dir) if batch_dir else self.workspace.root / "batch"

    # ---- orchestration ----------------------------------------------------- #
    def run(self) -> BatchResult:
        ws = self.workspace.ensure()
        self.batch_dir.mkdir(parents=True, exist_ok=True)
        state = BatchState.load(self.batch_dir / STATE_FILENAME)
        _, to_skip = state.partition(self.entries)
        skip_names = {e.name for e in to_skip}

        progress = Progress(len(self.entries), clock=self.clock, out=self.out)
        self.out(f"Batch: {len(self.entries)} reel(s)  "
                 f"(skipping {len(skip_names)} already completed)  "
                 f"-> {ws.root}")

        outcomes: list[ReelOutcome] = []
        for index, entry in enumerate(self.entries, start=1):
            if entry.name in skip_names:
                progress.skip_reel(index, entry.name)
                rec = state.records[entry.name]
                outcomes.append(ReelOutcome(
                    name=entry.name, status="skipped", code=rec.code,
                    duration_s=rec.duration_s, output_dir=rec.output_dir))
                continue

            progress.start_reel(index, entry.name)
            outcome = self._run_one(entry, ws)
            outcomes.append(outcome)
            if outcome.status == "passed":
                state.mark_completed(entry.name, code=outcome.code or 0,
                                     duration_s=outcome.duration_s,
                                     output_dir=outcome.output_dir)
            else:
                state.mark_failed(entry.name, code=outcome.code,
                                  error=outcome.error,
                                  duration_s=outcome.duration_s)
            state.save()                     # persist after EVERY reel -> resume
            progress.finish_reel(entry.name, ok=(outcome.status == "passed"),
                                 duration=outcome.duration_s, error=outcome.error)

        return BatchResult(
            total=len(self.entries),
            passed=sum(o.status == "passed" for o in outcomes),
            failed=sum(o.status == "failed" for o in outcomes),
            skipped=sum(o.status == "skipped" for o in outcomes),
            elapsed_s=progress.elapsed(),
            workspace=str(ws.root),
            batch_dir=str(self.batch_dir),
            outcomes=outcomes,
        )

    # ---- one reel ---------------------------------------------------------- #
    def _config_for(self, entry: BatchEntry, ws: Workspace) -> CreatorConfig:
        # Default every reel into the batch workspace; the entry may still
        # override any config section (paths included).
        overrides = deep_merge({"paths": {"root": str(ws.root)}},
                               entry.config_overrides())
        return load_creator_config(config_path=self.base_config, overrides=overrides)

    def _run_one(self, entry: BatchEntry, ws: Workspace) -> ReelOutcome:
        output_dir = str(ws.exports / entry.name)
        start = self.clock()
        buffer = io.StringIO()
        code: int | None = None
        error = ""
        try:
            cfg = self._config_for(entry, ws)
            with redirect_stdout(buffer), redirect_stderr(buffer):
                code = self.reel_runner(cfg, entry.name)
            ok = (code == 0)
            if not ok:
                error = _describe_code(code)
        except PlatformError as exc:         # CreatorError / BatchError / config, etc.
            ok = False
            error = getattr(exc, "message", str(exc))
        except Exception as exc:             # unexpected — log and keep going
            ok = False
            error = f"{type(exc).__name__}: {exc}"
        duration = self.clock() - start

        self._write_log(ws, entry.name, buffer.getvalue(), error)
        return ReelOutcome(
            name=entry.name, status="passed" if ok else "failed",
            code=code, error=error, duration_s=duration, output_dir=output_dir)

    def _write_log(self, ws: Workspace, name: str, captured: str, error: str) -> None:
        log = ws.logs / f"{name}.log"
        parts = [captured.rstrip()]
        if error:
            parts.append(f"\n[batch] ERROR: {error}")
        log.write_text("\n".join(p for p in parts if p) + "\n", encoding="utf-8")


def _describe_code(code: int | None) -> str:
    if code == 2:
        return "did not pass quality / empty output"
    if code == 1:
        return "input or environment error"
    return f"exit code {code}"
