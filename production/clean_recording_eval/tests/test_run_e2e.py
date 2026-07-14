"""End-to-end V3 run: ingest -> build -> stats -> compare -> score -> recommend.

Hermetic: the 'recording' is a synthetic WAV in a fake Downloads dir (WAV
passthrough needs no ffmpeg; ffprobe failure degrades to a size-only probe),
the baseline is written with the builder's own storage module, and the network
is blocked by conftest.
"""
from __future__ import annotations

import sqlite3

from production.clean_recording_eval import run as run_mod
from production.clean_recording_eval.run import RECOMMENDATIONS, eval_metrics, recommend
from production.clean_recording_eval.config import V3Config
from production.voice_dataset.models import Record
from production.voice_dataset.storage import write_sqlite

from .conftest import clean_speech


def _write_baseline(baseline_dir):
    meta = baseline_dir / "metadata"
    meta.mkdir(parents=True, exist_ok=True)
    recs = [Record(id=1, platform="unknown", source="raw", filename="p1.mp4",
                   duration=15.0, speech_duration=12.0, classification="talking_head",
                   quality="excellent", accepted=True, reason="accepted",
                   audio_path="", snr_db=28.0),
            Record(id=2, platform="unknown", source="raw", filename="p2.mp4",
                   duration=15.0, speech_duration=5.0, classification="unknown",
                   quality="poor", accepted=False, reason="multiple speakers",
                   audio_path="", snr_db=6.0)]
    write_sqlite(recs, meta / "dataset.sqlite")


def _argv(tmp_path, extra=()):
    return ["--downloads", str(tmp_path / "downloads"),
            "--raw", str(tmp_path / "raw"),
            "--output", str(tmp_path / "voice_dataset"),
            "--workspace", str(tmp_path / "_ws"),
            "--baseline", str(tmp_path / "baseline"),
            "--sample-size", "5", "--seed", "1", *extra]


def test_full_run_produces_dataset_report_and_score(tmp_path, capsys):
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    (downloads / "recording.wav").write_bytes(clean_speech(16.0))
    _write_baseline(tmp_path / "baseline")

    assert run_mod.run(_argv(tmp_path)) == 0

    # STEP 1: moved out of Downloads, into raw/, no .part leftovers
    assert not (downloads / "recording.wav").exists()
    assert (tmp_path / "raw" / "recording.wav").exists()
    # STEP 2: builder outputs
    out = tmp_path / "voice_dataset"
    for f in ("dataset.sqlite", "dataset.csv", "dataset.xlsx"):
        assert (out / "metadata" / f).exists() and (out / f).exists(), f
    conn = sqlite3.connect(str(out / "metadata" / "dataset.sqlite"))
    rows = conn.execute("SELECT filename, accepted FROM dataset").fetchall()
    conn.close()
    assert rows == [("recording.wav", 1)]

    text = capsys.readouterr().out
    for marker in ("STEP 1", "Filename     : recording.wav", "sha256",
                   "STEP 3", "Accepted speech minutes",
                   "STEP 4", "ACCEPTED sample (1 clips)",
                   "STEP 5", "Raw phone recordings",
                   "STEP 6", "OVERALL READINESS",
                   "STEP 7", "RECOMMENDATION"):
        assert marker in text, marker
    report = (out / "reports" / "evaluation_report.txt").read_text(encoding="utf-8")
    assert "OVERALL READINESS" in report


def test_rerun_is_idempotent_without_new_download(tmp_path, capsys):
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    (downloads / "recording.wav").write_bytes(clean_speech(16.0))
    _write_baseline(tmp_path / "baseline")
    run_mod.run(_argv(tmp_path))
    capsys.readouterr()

    assert run_mod.run(_argv(tmp_path)) == 0      # Downloads now empty
    text = capsys.readouterr().out
    assert "Continuing with existing raw files: recording.wav" in text
    assert "To process     : 0" in text            # build resumed, nothing new


def test_run_aborts_when_no_recording_anywhere(tmp_path, capsys):
    (tmp_path / "downloads").mkdir()
    assert run_mod.run(_argv(tmp_path)) == 1
    assert "No recording available" in capsys.readouterr().out


def test_recommendation_branches():
    cfg = V3Config()

    def m(hours, snr=25.0, clips=1, minutes=None):
        return {"accepted_clips": clips, "accepted_speech_hours": hours,
                "accepted_speech_minutes": minutes if minutes is not None else hours * 60,
                "avg_snr_db": snr, "avg_quality_label": "excellent"}

    assert recommend(m(1.2), 90.0, cfg)[0] == "A"
    assert recommend(m(0.4), 80.0, cfg)[0] == "B"
    assert recommend(m(0.4), 40.0, cfg)[0] == "C"   # readiness too low
    assert recommend(m(0.1), 90.0, cfg)[0] == "C"   # too little speech
    assert recommend(m(0.0, clips=0), 0.0, cfg)[0] == "C"
    for k in ("A", "B", "C"):
        assert k in RECOMMENDATIONS


def test_eval_metrics_acceptance_rate():
    recs = [{"accepted": True, "speech_duration": 300.0, "duration": 400.0,
             "snr_db": 25.0, "quality": "good"},
            {"accepted": False, "speech_duration": 100.0, "duration": 200.0,
             "snr_db": 8.0, "quality": "poor"}]
    m = eval_metrics(recs)
    assert m["acceptance_rate_pct"] == 50.0
    assert m["accepted_speech_minutes"] == 5.0
    assert m["avg_speech_duration_s"] == 300.0
    assert m["avg_quality_label"] == "good"
    assert eval_metrics([])["acceptance_rate_pct"] == 0.0
