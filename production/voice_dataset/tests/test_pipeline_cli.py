"""End-to-end: the CLI produces the datasets, routes files, and is deterministic."""
from __future__ import annotations

import sqlite3

from production.voice_dataset.build import main
from production.voice_dataset.config import Paths
from production.voice_dataset.pipeline import build_dataset
from production.voice_dataset.summary import summarize


def _seed(base, synth):
    paths = Paths.for_creator(base, "tanshi").ensure()
    synth.write_wav(paths.raw_youtube / "clean_talk.wav", synth.bursts(150, 20))
    synth.write_wav(paths.raw_instagram / "silence.wav", synth.silence(5))
    synth.write_wav(paths.raw_instagram / "noisy.wav", synth.noisy())
    return paths


def test_cli_produces_all_outputs(tmp_path, synth):
    paths = _seed(tmp_path, synth)
    rc = main(["--base", str(tmp_path), "--creator", "tanshi"])
    assert rc == 0

    for name in ("dataset.sqlite", "dataset.csv", "dataset.xlsx"):
        assert (paths.metadata / name).exists(), name

    accepted = {p.name for p in paths.accepted.glob("*.wav")}
    rejected = {p.name for p in paths.rejected.glob("*.wav")}
    assert "clean_talk.wav" in accepted
    assert {"silence.wav", "noisy.wav"} <= rejected

    conn = sqlite3.connect(str(paths.metadata / "dataset.sqlite"))
    total = conn.execute("SELECT COUNT(*) FROM dataset").fetchone()[0]
    acc = conn.execute("SELECT COUNT(*) FROM dataset WHERE accepted=1").fetchone()[0]
    conn.close()
    assert total == 3 and acc == 1


def test_summary_counts(tmp_path, synth):
    paths = _seed(tmp_path, synth)
    from production.voice_dataset.config import Config
    records = build_dataset(paths, Config())
    s = summarize(records)
    assert s["total"] == 3
    assert s["accepted"] == 1
    assert s["rejected"] == 2
    assert s["speech_hours"] > 0.0


def test_empty_run(tmp_path):
    rc = main(["--base", str(tmp_path), "--creator", "tanshi"])
    assert rc == 0
    meta = tmp_path / "tanshi" / "voice" / "metadata"
    assert (meta / "dataset.csv").exists()
    assert (meta / "dataset.sqlite").exists()


def test_deterministic_csv(tmp_path, synth):
    paths = _seed(tmp_path, synth)
    main(["--base", str(tmp_path), "--creator", "tanshi"])
    first = (paths.metadata / "dataset.csv").read_text(encoding="utf-8")
    main(["--base", str(tmp_path), "--creator", "tanshi"])
    second = (paths.metadata / "dataset.csv").read_text(encoding="utf-8")
    assert first == second
