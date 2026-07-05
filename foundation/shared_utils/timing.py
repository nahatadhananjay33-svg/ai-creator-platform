"""Timing helpers used by benchmarking and adapters."""
from __future__ import annotations

import time
from datetime import datetime, timezone
from types import TracebackType


def utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


class Stopwatch:
    """Monotonic stopwatch usable as a context manager.

    Example::

        with Stopwatch() as sw:
            do_work()
        print(sw.elapsed_s)
    """

    def __init__(self) -> None:
        self._start: float | None = None
        self._elapsed: float = 0.0

    def start(self) -> "Stopwatch":
        self._start = time.perf_counter()
        return self

    def stop(self) -> float:
        if self._start is None:
            raise RuntimeError("Stopwatch was never started")
        self._elapsed = time.perf_counter() - self._start
        self._start = None
        return self._elapsed

    @property
    def elapsed_s(self) -> float:
        if self._start is not None:
            return time.perf_counter() - self._start
        return self._elapsed

    def __enter__(self) -> "Stopwatch":
        return self.start()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.stop()
