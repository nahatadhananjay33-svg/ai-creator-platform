"""prepare_local orchestration — hermetic (fake ZIPs of WAVs, no ffmpeg/network)."""
from __future__ import annotations

import sqlite3
import zipfile

from production.voice_pipeline.prepare_local import (audit, ensure_structure,
                                                     extract_zips, main, move_zips)


def _make_zip(path, member_path, arcname):
    with zipfile.ZipFile(path, "w") as zf:
        zf.write(member_path, arcname=arcname)


def test_structure_move_extract(tmp_path, synth):
    downloads = tmp_path / "Downloads"; downloads.mkdir()
    base = tmp_path / "AI_CREATOR_DATA" / "Tanshi"
    # two fake takeout ZIPs, each holding one wav
    w1 = tmp_path / "clean.wav"; synth.write_clean(w1)
    w2 = tmp_path / "sil.wav"; synth.write_silence(w2)
    _make_zip(downloads / "Tanshi_raw_videos-001.zip", w1, "clean.wav")
    _make_zip(downloads / "Tanshi_raw_videos-002.zip", w2, "sil.wav")

    ensure_structure(base)
    assert (base / "voice_dataset" / "metadata").is_dir()
    assert (base / "voice_models").is_dir() and (base / "exports").is_dir()

    moved, nbytes = move_zips(downloads, base / "raw_videos")
    assert len(moved) == 2 and nbytes > 0
    assert not list(downloads.glob("*.zip"))       # moved, not copied

    extracted, skipped = extract_zips(base / "raw_videos")
    assert len(extracted) == 2 and not skipped
    assert (base / "raw_videos" / "Tanshi_raw_videos-001" / "clean.wav").exists()
    # resume: re-extract skips
    extracted2, skipped2 = extract_zips(base / "raw_videos")
    assert not extracted2 and len(skipped2) == 2


def test_full_main(tmp_path, synth):
    downloads = tmp_path / "Downloads"; downloads.mkdir()
    base = tmp_path / "AI_CREATOR_DATA" / "Tanshi"
    w1 = tmp_path / "clean.wav"; synth.write_clean(w1)
    w2 = tmp_path / "sil.wav"; synth.write_silence(w2)
    _make_zip(downloads / "Tanshi_raw_videos-001.zip", w1, "clean.wav")
    _make_zip(downloads / "Tanshi_raw_videos-002.zip", w2, "sil.wav")

    rc = main(["--base", str(base), "--downloads", str(downloads),
               "--creator", "tanshi", "--audit-n", "5"])
    assert rc == 0

    meta = base / "voice_dataset" / "metadata"
    for f in ("dataset.sqlite", "dataset.csv", "dataset.xlsx"):
        assert (meta / f).exists(), f
    conn = sqlite3.connect(str(meta / "dataset.sqlite"))
    total = conn.execute("SELECT COUNT(*) FROM dataset").fetchone()[0]
    conn.close()
    assert total == 2

    acc, rej = audit(meta / "dataset.sqlite", n=5)
    assert len(acc) == 1 and len(rej) == 1        # clean accepted, silence rejected
