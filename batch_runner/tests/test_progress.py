"""Progress counters, elapsed, and ETA (deterministic clock + sink)."""
from __future__ import annotations

from batch_runner.progress import Progress


class Clock:
    """A deterministic clock advancing 1.0s per read."""

    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        self.t += 1.0
        return self.t


def test_counters_and_remaining():
    lines: list[str] = []
    p = Progress(3, clock=Clock(), out=lines.append)
    p.start_reel(1, "a")
    p.finish_reel("a", ok=True, duration=1.0)
    p.finish_reel("b", ok=False, duration=2.0, error="boom")
    p.skip_reel(3, "c")
    assert p.passed == 1
    assert p.failed == 1
    assert p.skipped == 1
    assert p.done == 3
    assert p.remaining == 0


def test_eta_is_none_before_any_run():
    p = Progress(5, clock=Clock(), out=lambda s: None)
    assert p.eta() is None


def test_eta_extrapolates_from_run_reels():
    p = Progress(4, clock=Clock(), out=lambda s: None)
    p.finish_reel("a", ok=True, duration=1.0)   # 1 of 4 done, 3 remain
    eta = p.eta()
    assert eta is not None and eta > 0


def test_failed_line_shows_error():
    lines: list[str] = []
    p = Progress(1, clock=Clock(), out=lines.append)
    p.finish_reel("x", ok=False, duration=1.0, error="quality FAIL")
    assert any("FAILED (quality FAIL)" in ln for ln in lines)


def test_skip_line_mentions_completed():
    lines: list[str] = []
    p = Progress(1, clock=Clock(), out=lines.append)
    p.skip_reel(1, "done")
    assert any("skipping" in ln and "done" in ln for ln in lines)
