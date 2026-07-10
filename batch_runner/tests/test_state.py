"""Persistent batch state + resume partitioning."""
from __future__ import annotations

from dataclasses import dataclass

from batch_runner.queue import BatchState, EntryRecord


@dataclass
class FakeEntry:
    name: str


def test_empty_state_when_no_file(tmp_path):
    state = BatchState.load(tmp_path / "state.json")
    assert state.records == {}
    assert state.is_completed("anything") is False


def test_mark_and_roundtrip(tmp_path):
    path = tmp_path / "state.json"
    state = BatchState.load(path)
    state.mark_completed("reel-a", code=0, duration_s=1.5, output_dir="/x/reel-a")
    state.mark_failed("reel-b", code=2, error="quality FAIL", duration_s=0.9)
    state.save()

    reloaded = BatchState.load(path)
    assert reloaded.is_completed("reel-a")
    assert reloaded.records["reel-a"].duration_s == 1.5
    assert reloaded.records["reel-a"].output_dir == "/x/reel-a"
    assert reloaded.records["reel-b"].status == "failed"
    assert reloaded.records["reel-b"].error == "quality FAIL"
    assert not reloaded.is_completed("reel-b")


def test_attempts_increment(tmp_path):
    state = BatchState.load(tmp_path / "state.json")
    state.mark_failed("r", code=1, error="boom", duration_s=0.1)
    state.mark_completed("r", code=0, duration_s=0.2)
    assert state.records["r"].attempts == 2
    assert state.records["r"].completed


def test_partition_skips_completed_only(tmp_path):
    state = BatchState.load(tmp_path / "state.json")
    state.mark_completed("done", code=0, duration_s=1.0)
    state.mark_failed("failed-before", code=2, error="x", duration_s=1.0)

    entries = [FakeEntry("done"), FakeEntry("failed-before"), FakeEntry("fresh")]
    to_run, to_skip = state.partition(entries)
    assert [e.name for e in to_skip] == ["done"]
    assert [e.name for e in to_run] == ["failed-before", "fresh"]


def test_save_is_atomic_and_sorted(tmp_path):
    path = tmp_path / "state.json"
    state = BatchState.load(path)
    state.mark_completed("b", code=0, duration_s=1.0)
    state.mark_completed("a", code=0, duration_s=1.0)
    state.save()
    text = path.read_text(encoding="utf-8")
    assert text.index('"a"') < text.index('"b"')       # sorted keys
    assert not (tmp_path / "state.json.tmp").exists()   # temp cleaned up


def test_record_defaults():
    rec = EntryRecord(name="x")
    assert rec.status == "pending"
    assert rec.attempts == 0
    assert rec.completed is False
