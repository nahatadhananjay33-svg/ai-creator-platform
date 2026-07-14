"""Glue orchestration: outputs, Drive layout, summary, and resume."""
from __future__ import annotations

import json
import sqlite3

from production.voice_pipeline.glue import run_pipeline


def _seed(source, synth):
    source.mkdir(parents=True, exist_ok=True)
    synth.write_clean(source / "vid_clean.wav")
    synth.write_silence(source / "vid_silence.wav")


def test_pipeline_produces_drive_outputs(tmp_path, synth):
    source = tmp_path / "Tanshi_raw_videos"
    ws = tmp_path / "workspace"
    drive = tmp_path / "Tanshi_voice_dataset"
    _seed(source, synth)

    s = run_pipeline(source, ws, drive, creator="tanshi", progress=False)

    meta = drive / "metadata"
    for f in ("dataset.sqlite", "dataset.csv", "dataset.xlsx"):
        assert (meta / f).exists(), f
    assert (drive / "summary.json").exists()
    assert (drive / "reports" / "summary.json").exists()
    assert any((drive / "accepted").glob("*.wav"))
    assert any((drive / "rejected").glob("*.wav"))

    assert s["videos_processed"] == 2
    assert s["accepted_clips"] == 1 and s["rejected_clips"] == 1
    assert s["accepted_speech_hours"] > 0.0

    # dataset rows == 2, audio_path points into the Drive tree
    conn = sqlite3.connect(str(meta / "dataset.sqlite"))
    rows = conn.execute("SELECT filename, audio_path FROM dataset").fetchall()
    conn.close()
    assert len(rows) == 2
    assert all(str(drive) in r[1] for r in rows)


def test_resume_adds_only_new(tmp_path, synth):
    source = tmp_path / "Tanshi_raw_videos"
    ws = tmp_path / "workspace"
    drive = tmp_path / "Tanshi_voice_dataset"
    _seed(source, synth)

    run_pipeline(source, ws, drive, progress=False)              # process 2
    synth.write_clean(source / "vid_clean2.wav")                 # add a 3rd
    s2 = run_pipeline(source, ws, drive, progress=False)         # resume

    assert s2["videos_processed"] == 1        # only the new file
    assert s2["videos_skipped"] == 2
    assert s2["total_videos"] == 3
    conn = sqlite3.connect(str(drive / "metadata" / "dataset.sqlite"))
    assert conn.execute("SELECT COUNT(*) FROM dataset").fetchone()[0] == 3
    conn.close()


def test_resume_noop_when_nothing_new(tmp_path, synth):
    source = tmp_path / "Tanshi_raw_videos"
    ws = tmp_path / "workspace"
    drive = tmp_path / "Tanshi_voice_dataset"
    _seed(source, synth)

    run_pipeline(source, ws, drive, progress=False)
    s2 = run_pipeline(source, ws, drive, progress=False)         # nothing new
    assert s2["videos_processed"] == 0
    assert s2["videos_skipped"] == 2
    assert s2["total_videos"] == 2
