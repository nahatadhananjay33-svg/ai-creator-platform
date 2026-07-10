"""Live batch progress: current / completed / remaining / failed / time (Phase C20).

A tiny, dependency-free reporter. The clock is injected (defaults to
``time.monotonic``) and the output sink is injected (defaults to ``print``), so
progress is fully deterministic to test.
"""
from __future__ import annotations

import time
from typing import Callable


class Progress:
    """Track and display sequential batch progress."""

    def __init__(self, total: int, *, clock: Callable[[], float] = time.monotonic,
                 out: Callable[[str], None] = print) -> None:
        self._total = total
        self._clock = clock
        self._out = out
        self._start = clock()
        self._passed = 0
        self._failed = 0
        self._skipped = 0

    # ---- counters ---------------------------------------------------------- #
    @property
    def passed(self) -> int:
        return self._passed

    @property
    def failed(self) -> int:
        return self._failed

    @property
    def skipped(self) -> int:
        return self._skipped

    @property
    def done(self) -> int:
        return self._passed + self._failed + self._skipped

    @property
    def remaining(self) -> int:
        return self._total - self.done

    def elapsed(self) -> float:
        return self._clock() - self._start

    def eta(self) -> float | None:
        """Estimated seconds remaining, from the average of reels actually run."""
        ran = self._passed + self._failed
        if ran == 0:
            return None
        return (self.elapsed() / ran) * self.remaining

    # ---- events ------------------------------------------------------------ #
    def start_reel(self, index: int, name: str) -> None:
        self._out(f'[{index}/{self._total}] ▶  generating "{name}" …')

    def skip_reel(self, index: int, name: str) -> None:
        self._skipped += 1
        self._out(f'[{index}/{self._total}] ⤼  skipping "{name}" (already completed)')

    def finish_reel(self, name: str, *, ok: bool, duration: float,
                    error: str = "") -> None:
        if ok:
            self._passed += 1
            line = f"      ✓ {name}  PASS  {duration:.1f}s"
        else:
            self._failed += 1
            verdict = f"FAILED ({error})" if error else "FAILED"
            line = f"      ✗ {name}  {verdict}  {duration:.1f}s"
        eta = self.eta()
        eta_s = f"ETA ~{eta:.1f}s" if eta is not None else "ETA —"
        self._out(f"{line}  |  done {self.done}/{self._total}  "
                  f"ok {self._passed}  failed {self._failed}  "
                  f"remaining {self.remaining}  elapsed {self.elapsed():.1f}s  {eta_s}")
