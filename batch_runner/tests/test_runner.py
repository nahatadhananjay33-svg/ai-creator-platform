"""Sequential runner: order, failure handling, resume — with a fake reel runner.

No rendering here: the per-reel call is injected, so these tests exercise the
orchestration (state, resume, logging, results) hermetically and instantly.
"""
from __future__ import annotations

from batch_runner.entry import BatchEntry
from batch_runner.queue.state import STATE_FILENAME, BatchState
from batch_runner.runner import BatchRunner


class Clock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        self.t += 1.0
        return self.t


def entries(*names):
    return [BatchEntry(prompt=f"Prompt {n}", template="general", output=n)
            for n in names]


def make_runner(items, tmp_path, reel_runner):
    return BatchRunner(items, workspace_root=tmp_path / "ws",
                       reel_runner=reel_runner, clock=Clock(), out=lambda s: None)


def test_all_pass_sequentially(tmp_path):
    called = []

    def runner(cfg, name):
        called.append(name)
        return 0

    result = make_runner(entries("a", "b", "c"), tmp_path, runner).run()
    assert called == ["a", "b", "c"]                 # one at a time, in order
    assert (result.passed, result.failed, result.skipped) == (3, 0, 0)
    assert result.ok
    assert [o.name for o in result.outcomes] == ["a", "b", "c"]
    assert all(o.duration_s > 0 for o in result.outcomes)


def test_failure_is_logged_and_batch_continues(tmp_path):
    seen = []

    def runner(cfg, name):
        seen.append(name)
        return 2 if name == "b" else 0             # b fails quality

    result = make_runner(entries("a", "b", "c"), tmp_path, runner).run()
    assert seen == ["a", "b", "c"]                    # c still ran after b failed
    assert (result.passed, result.failed, result.skipped) == (2, 1, 0)
    b = next(o for o in result.outcomes if o.name == "b")
    assert b.status == "failed" and b.code == 2 and b.error
    # the error was logged to the reel's log file
    log = (tmp_path / "ws" / "logs" / "b.log").read_text(encoding="utf-8")
    assert "ERROR" in log


def test_exception_in_a_reel_does_not_stop_the_batch(tmp_path):
    def runner(cfg, name):
        if name == "b":
            raise RuntimeError("kaboom")
        return 0

    result = make_runner(entries("a", "b", "c"), tmp_path, runner).run()
    assert (result.passed, result.failed, result.skipped) == (2, 1, 0)
    b = next(o for o in result.outcomes if o.name == "b")
    assert "kaboom" in b.error


def test_state_persisted_after_run(tmp_path):
    make_runner(entries("a", "b"), tmp_path, lambda c, n: 0).run()
    state_path = tmp_path / "ws" / "batch" / STATE_FILENAME
    assert state_path.exists()
    state = BatchState.load(state_path)
    assert state.is_completed("a") and state.is_completed("b")


def test_resume_skips_completed(tmp_path):
    items = entries("a", "b", "c")
    make_runner(items, tmp_path, lambda c, n: 0).run()      # all pass

    called = []

    def runner(cfg, name):
        called.append(name)
        return 0

    result = make_runner(items, tmp_path, runner).run()      # resume
    assert called == []                                      # nothing re-run
    assert (result.passed, result.failed, result.skipped) == (0, 0, 3)


def test_resume_retries_failed_only(tmp_path):
    items = entries("a", "b", "c")
    make_runner(items, tmp_path, lambda c, n: 2 if n == "b" else 0).run()

    called = []

    def runner(cfg, name):
        called.append(name)
        return 0                                             # now b passes

    result = make_runner(items, tmp_path, runner).run()
    assert called == ["b"]                                   # only the failed one
    assert (result.passed, result.failed, result.skipped) == (1, 0, 2)


def test_per_reel_config_overrides_are_applied(tmp_path):
    captured = {}

    def runner(cfg, name):
        captured[name] = cfg
        return 0

    items = [BatchEntry(prompt="Hi", template="finance", output="r1",
                        overrides={"generation": {"renderer": "mock",
                                                  "language": "hi"}})]
    make_runner(items, tmp_path, runner).run()
    cfg = captured["r1"]
    assert cfg.template == "finance"
    assert cfg.language == "hi"
    assert str(tmp_path / "ws") == cfg.workspace_root      # defaulted into batch ws
