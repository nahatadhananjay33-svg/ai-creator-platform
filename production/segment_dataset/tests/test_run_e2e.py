"""End-to-end V4: multi-source segmentation -> dataset -> report -> verdict."""
from __future__ import annotations

import sqlite3

import numpy as np

from production.segment_dataset import run as run_mod
from production.segment_dataset.pipeline import discover_sources
from production.segment_dataset.report import extra_recording_estimate

from .conftest import SR, quiet, speech_with_pauses, tone, write_wav


def _make_sources(tmp_path):
    """Two source kinds: one long clean take, one noisy/short take."""
    clean = tmp_path / "clean"
    phone = tmp_path / "phone"
    # 40 s of speech with a long pause -> several 5-20 s segments, high SNR
    write_wav(clean / "take1.wav",
              speech_with_pauses([("v", 18), ("s", 2), ("v", 22), ("s", 2)]))
    # mostly silence with 4 s of speech -> short segment (rejected: too short is
    # possible) plus a silent recording that yields nothing
    write_wav(phone / "short.wav", speech_with_pauses([("s", 3), ("v", 4), ("s", 3)]))
    write_wav(phone / "nested" / "silent.wav", quiet(8))
    return clean, phone


def _argv(tmp_path, extra=()):
    clean, phone = tmp_path / "clean", tmp_path / "phone"
    return ["--output", str(tmp_path / "out"), "--workspace", str(tmp_path / "ws"),
            "--source", f"clean_mic={clean}", "--source", f"raw_phone={phone}",
            "--sample-size", "5", "--seed", "1", *extra]


def test_discover_sources_recursive_and_keyed(tmp_path):
    clean, phone = _make_sources(tmp_path)
    found = discover_sources({"clean_mic": clean, "raw_phone": phone,
                              "instagram": tmp_path / "missing"})
    kinds = [(k, key) for k, _, key in found]
    assert ("clean_mic", "take1.wav") in kinds
    assert ("raw_phone", "nested/silent.wav") in kinds     # recursive + relative key
    assert len(found) == 3


def test_full_run_generates_dataset_and_report(tmp_path, capsys):
    _make_sources(tmp_path)
    assert run_mod.run(_argv(tmp_path)) == 0
    out = tmp_path / "out"

    conn = sqlite3.connect(str(out / "metadata" / "dataset.sqlite"))
    rows = conn.execute(
        "SELECT source_kind, accepted, duration, start_s, end_s FROM dataset").fetchall()
    conn.close()
    assert rows, "no segments produced"
    accepted = [r for r in rows if r[1]]
    assert accepted, "expected accepted segments from the clean take"
    assert all(2.0 <= r[2] <= 23.0 for r in rows)          # segment-sized, not whole files
    assert all(r[4] > r[3] for r in rows)                  # start/end stored

    # accepted WAVs exist in accepted_segments/, rejected in rejected_segments/
    assert len(list((out / "accepted_segments").glob("*.wav"))) == len(accepted)
    assert (out / "metadata" / "dataset.csv").exists()
    assert (out / "metadata" / "dataset.xlsx").exists()
    assert (out / "VOICE_DATASET_REPORT.md").exists()

    text = capsys.readouterr().out
    for marker in ("STEPS 1-7", "STEP 8", "STEP 9", "STEPS 10+11",
                   "Accepted segments", "ACCEPTED sample", "duration in band",
                   "more minutes", "Report:"):
        assert marker in text, marker
    md = (out / "VOICE_DATASET_REPORT.md").read_text(encoding="utf-8")
    assert "Source contribution" in md and "clean_mic" in md


def test_resume_skips_processed_sources(tmp_path, capsys):
    _make_sources(tmp_path)
    run_mod.run(_argv(tmp_path))
    capsys.readouterr()
    run_mod.run(_argv(tmp_path))
    text = capsys.readouterr().out
    assert "To process         : 0" in text


def test_crash_on_one_source_is_isolated(tmp_path, capsys, monkeypatch):
    _make_sources(tmp_path)
    real = run_mod.process_source

    def flaky(src, kind, key, *a, **kw):
        if "short" in key:
            raise MemoryError("simulated")
        return real(src, kind, key, *a, **kw)

    monkeypatch.setattr(run_mod, "process_source", flaky)
    run_mod.run(_argv(tmp_path))
    out_text = capsys.readouterr().out
    assert "FAILED (MemoryError)" in out_text
    assert (tmp_path / "out" / "reports" / "crashed_files.json").exists()
    conn = sqlite3.connect(str(tmp_path / "out" / "metadata" / "dataset.sqlite"))
    kinds = {r[0] for r in conn.execute("SELECT source_kind FROM dataset")}
    conn.close()
    assert "clean_mic" in kinds                            # others still processed


def test_extra_recording_estimate_uses_measured_yield():
    records = [
        {"source_kind": "clean_mic", "accepted": True, "duration": 1200.0,
         "end_s": 1800.0},
        {"source_kind": "clean_mic", "accepted": False, "duration": 300.0,
         "end_s": 1500.0},
    ]
    text = extra_recording_estimate(records, missing_hours=0.5)
    assert "67%" in text                    # 1200s accepted / 1800s recorded
    assert "45 more minutes" in text        # 0.5h / (2/3) = 45 min
    assert extra_recording_estimate(records, 0.0) == "No additional recording required."
