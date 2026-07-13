"""End-to-end: download (fake) -> voice builder -> stop-condition outputs."""
from __future__ import annotations

import io
import sqlite3
import wave

import numpy as np

from production.media_acquisition.cli import run
from production.media_acquisition.models import Platform
from production.media_acquisition.tests._fakes import FakeProvider, make_items

SR = 16000
STOP_FILES = ["media.sqlite", "media.csv", "media.xlsx",
              "dataset.sqlite", "dataset.csv", "dataset.xlsx"]


def _wav_bytes(x) -> bytes:
    x = np.clip(np.asarray(x, dtype=np.float64), -1, 1)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((x * 32767).astype("<i2").tobytes())
    return buf.getvalue()


def _clean() -> bytes:
    rng = np.random.default_rng(0)
    seg = []
    for _ in range(20):
        t = np.arange(int(SR * 0.5)) / SR
        seg.append(0.15 * (np.sin(2 * np.pi * 150 * t) + 0.4 * np.sin(2 * np.pi * 300 * t)))
        seg.append(1e-4 * rng.standard_normal(int(SR * 0.5)))
    return _wav_bytes(np.concatenate(seg))


def _silence() -> bytes:
    return _wav_bytes(1e-4 * np.random.default_rng(2).standard_normal(SR * 5))


def test_full_pipeline_stop_condition(tmp_path):
    yt = FakeProvider(Platform.YOUTUBE, make_items(Platform.YOUTUBE, ["vid1", "vid2"]),
                      contents={"vid1": _clean(), "vid2": _silence()}, ext="wav")
    ig = FakeProvider(Platform.INSTAGRAM, [], available=False)

    rc = run(["--base", str(tmp_path), "--creator", "tanshi", "--limit", "10"],
             providers=[yt, ig])
    assert rc == 0

    tanshi = tmp_path / "tanshi"
    meta = tanshi / "voice" / "metadata"
    for f in STOP_FILES:
        assert (meta / f).exists(), f

    # downloaded media present
    assert (tanshi / "media" / "youtube" / "vid1.wav").exists()
    assert (tanshi / "media" / "youtube" / "vid2.wav").exists()

    # media db: 2 downloaded
    conn = sqlite3.connect(str(meta / "media.sqlite"))
    dl = conn.execute("SELECT COUNT(*) FROM media WHERE status='downloaded'").fetchone()[0]
    conn.close()
    assert dl == 2

    # voice dataset: 1 accepted (clean) + 1 rejected (silence)
    conn = sqlite3.connect(str(meta / "dataset.sqlite"))
    acc = conn.execute("SELECT COUNT(*) FROM dataset WHERE accepted=1").fetchone()[0]
    rej = conn.execute("SELECT COUNT(*) FROM dataset WHERE accepted=0").fetchone()[0]
    conn.close()
    assert acc == 1 and rej == 1
    assert any((tanshi / "voice" / "accepted").glob("*.wav"))
    assert any((tanshi / "voice" / "rejected").glob("*.wav"))


def test_empty_run_still_produces_all_files(tmp_path):
    # No providers -> no downloads, but the run still builds empty media + voice
    # datasets and prints a summary. Uses explicit [] so it never depends on which
    # download tools happen to be installed in the environment.
    rc = run(["--base", str(tmp_path), "--creator", "tanshi"], providers=[])
    assert rc == 0
    meta = tmp_path / "tanshi" / "voice" / "metadata"
    for f in STOP_FILES:
        assert (meta / f).exists(), f


def test_incremental_second_run_skips(tmp_path):
    yt = FakeProvider(Platform.YOUTUBE, make_items(Platform.YOUTUBE, ["vid1"]),
                      contents={"vid1": _clean()}, ext="wav")
    ig = FakeProvider(Platform.INSTAGRAM, [], available=False)
    run(["--base", str(tmp_path)], providers=[yt, ig])
    # second run: same item already downloaded -> skipped, not re-downloaded
    yt2 = FakeProvider(Platform.YOUTUBE, make_items(Platform.YOUTUBE, ["vid1"]),
                       contents={"vid1": _clean()}, ext="wav")
    run(["--base", str(tmp_path)], providers=[yt2, ig])
    assert yt2._attempts.get("vid1", 0) == 0        # fetch never called on 2nd run
