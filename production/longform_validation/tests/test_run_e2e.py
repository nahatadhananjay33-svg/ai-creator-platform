"""End-to-end V2 run: download -> build -> stats -> inspect -> compare -> recommend.

Hermetic: FakeProvider serves synthetic WAV bytes as 'videos' (WAV passthrough
needs no ffmpeg), the baseline dataset is written with the builder's own
storage module, and the network is blocked by conftest.
"""
from __future__ import annotations

import json
import sqlite3

import pytest

from production.longform_validation import run as run_mod
from production.longform_validation.provider import LongFormYouTubeProvider
from production.media_acquisition.models import MediaItem, Platform
from production.media_acquisition.tests._fakes import FakeProvider
from production.voice_dataset.models import Record
from production.voice_dataset.storage import write_sqlite

from .conftest import clean_speech, silence


def _item(i, kind="long_form"):
    return MediaItem(platform=Platform.YOUTUBE, item_id=i,
                     url=f"https://example/{i}", title=i, kind=kind, duration=16.0)


def _fake_provider():
    items = [_item("vidA"), _item("vidB"), _item("short1", kind="short"),
             _item("vidC")]
    # distinct durations -> distinct checksums (identical bytes would trip the
    # engine's dedup-by-checksum and skip vidC)
    contents = {"vidA": clean_speech(16.0), "vidB": silence(), "vidC": clean_speech(12.0)}
    return LongFormYouTubeProvider(
        inner=FakeProvider(Platform.YOUTUBE, items, contents=contents, ext="wav"))


def _write_baseline(baseline_dir):
    meta = baseline_dir / "metadata"
    meta.mkdir(parents=True, exist_ok=True)
    recs = [Record(id=1, platform="unknown", source="raw", filename="raw1.mp4",
                   duration=20.0, speech_duration=15.0, classification="talking_head",
                   quality="excellent", accepted=True, reason="accepted",
                   audio_path="", snr_db=28.0),
            Record(id=2, platform="unknown", source="raw", filename="raw2.mp4",
                   duration=20.0, speech_duration=5.0, classification="unknown",
                   quality="poor", accepted=False, reason="multiple speakers",
                   audio_path="", snr_db=6.0)]
    write_sqlite(recs, meta / "dataset.sqlite")


def _argv(tmp_path, extra=()):
    return ["--source", str(tmp_path / "youtube_longform"),
            "--output", str(tmp_path / "youtube_voice_dataset"),
            "--workspace", str(tmp_path / "_ws"),
            "--baseline", str(tmp_path / "baseline"),
            "--sample-size", "5", "--seed", "1", *extra]


def test_full_run_produces_dataset_and_report(tmp_path, capsys):
    _write_baseline(tmp_path / "baseline")
    assert run_mod.run(_argv(tmp_path), provider=_fake_provider()) == 0

    src = tmp_path / "youtube_longform"
    out = tmp_path / "youtube_voice_dataset"
    # STEP 1: only long-form videos downloaded, metadata + checksums verified
    assert sorted(p.name for p in src.glob("*.wav")) == ["vidA.wav", "vidB.wav", "vidC.wav"]
    for f in ("media.sqlite", "media.csv", "media.xlsx", "download.log"):
        assert (src / f).exists(), f
    # STEPS 2+3: builder outputs (metadata + root copies per spec)
    for f in ("dataset.sqlite", "dataset.csv", "dataset.xlsx"):
        assert (out / "metadata" / f).exists() and (out / f).exists(), f
    assert any((out / "accepted").glob("*.wav"))
    assert any((out / "rejected").glob("*.wav"))

    conn = sqlite3.connect(str(out / "metadata" / "dataset.sqlite"))
    rows = conn.execute("SELECT filename, accepted FROM dataset ORDER BY filename").fetchall()
    conn.close()
    assert [r[0] for r in rows] == ["vidA.wav", "vidB.wav", "vidC.wav"]
    assert [r[1] for r in rows] == [1, 0, 1]     # clean accepted, silence rejected

    text = capsys.readouterr().out
    for marker in ("STEP 1", "STEP 4", "STEP 5", "STEP 6", "STEP 7",
                   "Checksums verified : 3", "RECOMMENDATION",
                   "Raw Video Dataset"):
        assert marker in text, marker
    report = (out / "reports" / "validation_report.txt").read_text(encoding="utf-8")
    assert "RECOMMENDATION" in report


def test_second_run_skips_everything(tmp_path, capsys):
    _write_baseline(tmp_path / "baseline")
    run_mod.run(_argv(tmp_path), provider=_fake_provider())
    capsys.readouterr()
    run_mod.run(_argv(tmp_path), provider=_fake_provider())
    text = capsys.readouterr().out
    assert "Skipped (already ok) : 3" in text
    assert "To process     : 0" in text


def test_crash_on_one_file_is_isolated(tmp_path, capsys, monkeypatch):
    _write_baseline(tmp_path / "baseline")
    real = run_mod.run_pipeline

    def flaky(stage_dir, *a, **kw):
        staged = [p.name for p in stage_dir.iterdir()]
        if "vidB.wav" in staged:
            raise MemoryError("simulated oversized WAV")
        return real(stage_dir, *a, **kw)

    monkeypatch.setattr(run_mod, "run_pipeline", flaky)
    run_mod.run(_argv(tmp_path), provider=_fake_provider())

    out = tmp_path / "youtube_voice_dataset"
    crashed = json.loads((out / "reports" / "crashed_files.json").read_text())
    assert crashed == ["vidB.wav"]
    conn = sqlite3.connect(str(out / "metadata" / "dataset.sqlite"))
    names = [r[0] for r in conn.execute("SELECT filename FROM dataset")]
    conn.close()
    assert sorted(names) == ["vidA.wav", "vidC.wav"]   # others still processed
    assert "FAILED (MemoryError)" in capsys.readouterr().out
