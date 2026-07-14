"""V4.1: ZIP ingest/extract/scan, SHA256-deduped merge, end-to-end expansion."""
from __future__ import annotations

import sqlite3
import zipfile

from production.segment_dataset import expansion as exp_mod
from production.segment_dataset import run as run_mod
from production.segment_dataset.expand import (extract_zips, find_zips,
                                               move_zips, scan_media)
from production.segment_dataset.merge import merge_accepted
from production.segment_dataset.storage import load_segments

from .conftest import speech_with_pauses, write_wav


def _zip_with(path, files):
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as zf:
        for name, src in files.items():
            zf.write(src, arcname=name)
    return path


def _clean_take(tmp_path, name, spans):
    return write_wav(tmp_path / "wavs" / name, speech_with_pauses(spans))


def test_find_and_move_zips_never_overwrites(tmp_path):
    dl = tmp_path / "dl"
    dl.mkdir()
    w = _clean_take(tmp_path, "a.wav", [("v", 6)])
    z1 = _zip_with(dl / "New_videos_for_voice_clone-001.zip", {"a.wav": w})
    _zip_with(dl / "unrelated.zip", {"a.wav": w})
    (dl / "New_videos_for_voice_clone-notzip.txt").write_text("x")

    zips = find_zips(dl)
    assert [z.name for z in zips] == ["New_videos_for_voice_clone-001.zip"]

    dest = tmp_path / "zips"
    moved, notes = move_zips(zips, dest)
    assert [m.name for m in moved] == [z1.name] and not notes
    assert not (dl / z1.name).exists()           # moved out of Downloads

    # a second identical-name zip is never overwritten; source stays put
    z1b = _zip_with(dl / "New_videos_for_voice_clone-001.zip", {"b.wav": w})
    moved2, notes2 = move_zips([z1b], dest)
    assert (dl / z1b.name).exists() and "already present" in notes2[0]
    assert len(moved2) == 1                      # destination copy is used


def test_extract_zips_resumable(tmp_path):
    w = _clean_take(tmp_path, "a.wav", [("v", 6)])
    zips = tmp_path / "zips"
    _zip_with(zips / "New_videos_for_voice_clone-001.zip", {"vids/a.wav": w})
    extracted = tmp_path / "extracted"

    done, skipped = extract_zips(zips, extracted)
    assert done == ["New_videos_for_voice_clone-001"] and not skipped
    assert (extracted / "New_videos_for_voice_clone-001" / "vids" / "a.wav").exists()

    done2, skipped2 = extract_zips(zips, extracted)      # resume: skip done
    assert not done2 and skipped2 == ["New_videos_for_voice_clone-001"]

    # leftover .partial from a crash is discarded and re-extracted
    _zip_with(zips / "New_videos_for_voice_clone-002.zip", {"b.wav": w})
    (extracted / "New_videos_for_voice_clone-002.partial").mkdir()
    done3, _ = extract_zips(zips, extracted)
    assert done3 == ["New_videos_for_voice_clone-002"]


def test_scan_media_counts(tmp_path):
    _clean_take(tmp_path / "x", "a.wav", [("v", 6)])
    _clean_take(tmp_path / "x" / "sub", "b.wav", [("v", 4)])
    (tmp_path / "x" / "notes.txt").write_text("skip")
    scan = scan_media(tmp_path / "x")
    assert scan.files == 2
    assert scan.formats == {"wav": 2}
    assert scan.total_bytes > 0


def _build_prod(tmp_path):
    """A small production dataset built by the real V4 runner."""
    src = tmp_path / "prod_src"
    write_wav(src / "take1.wav",
              speech_with_pauses([("v", 8), ("s", 0.4), ("v", 6), ("s", 2)]))
    prod = tmp_path / "prod"
    run_mod.run(["--source", f"clean_mic={src}", "--output", str(prod),
                 "--workspace", str(tmp_path / "ws1"), "--sample-size", "0",
                 "--seed", "1"])
    return src, prod


def test_merge_dedups_by_sha256(tmp_path):
    src, prod = _build_prod(tmp_path)
    old = load_segments(prod / "metadata" / "dataset.sqlite")
    old_accepted = sum(1 for r in old if r["accepted"])
    assert old_accepted > 0

    # new run over BOTH a genuinely new take and a byte-identical copy of the
    # production source (its segments hash identically -> duplicates)
    new_src = tmp_path / "new_src"
    new_src.mkdir()
    (new_src / "take1_copy.wav").write_bytes((src / "take1.wav").read_bytes())
    write_wav(new_src / "take2.wav",
              speech_with_pauses([("v", 7, 170.0), ("s", 2)]))
    new_out = tmp_path / "new_out"
    run_mod.run(["--source", f"new_raw={new_src}", "--output", str(new_out),
                 "--workspace", str(tmp_path / "ws2"), "--sample-size", "0",
                 "--seed", "1"])

    stats = merge_accepted(new_out, prod)
    assert stats["duplicates_skipped"] >= 1               # the copied take
    assert stats["added"] >= 1                            # the new take
    merged = load_segments(prod / "metadata" / "dataset.sqlite")
    assert len(merged) == len(old) + stats["added"]
    assert [r["id"] for r in merged] == list(range(1, len(merged) + 1))
    # idempotent: merging again adds nothing
    stats2 = merge_accepted(new_out, prod)
    assert stats2["added"] == 0


def test_expansion_end_to_end(tmp_path, capsys):
    _, prod = _build_prod(tmp_path)
    dl = tmp_path / "dl"
    dl.mkdir()
    w = _clean_take(tmp_path, "fresh.wav",
                    [("v", 9, 160.0), ("s", 0.5), ("v", 5, 160.0), ("s", 3)])
    _zip_with(dl / "New_videos_for_voice_clone-100.zip", {"vids/fresh.wav": w})

    rc = exp_mod.run([
        "--downloads", str(dl),
        "--zips", str(tmp_path / "nz" / "zips"),
        "--extracted", str(tmp_path / "nz" / "extracted"),
        "--new-output", str(tmp_path / "new_out"),
        "--prod", str(prod),
        "--workspace", str(tmp_path / "ws3"),
        "--sample-size", "5", "--seed", "1"])
    assert rc == 0

    text = capsys.readouterr().out
    for marker in ("STEP 1", "ZIP count : 1", "STEP 3", "STEP 4",
                   "Total videos   : 1", "STEP 5", "STEP 6",
                   "Added to production", "STEP 7", "Net increase",
                   "STEP 8", "NEWLY ACCEPTED", "STEP 9",
                   "final production dataset", "VALIDATION", "[OK]"):
        assert marker in text, marker
    assert "[FAIL]" not in text

    conn = sqlite3.connect(str(prod / "metadata" / "dataset.sqlite"))
    kinds = {r[0] for r in conn.execute("SELECT DISTINCT source_kind FROM dataset")}
    conn.close()
    assert "new_raw" in kinds and "clean_mic" in kinds
    assert (tmp_path / "new_out" / "reports" / "expansion_report.txt").exists()
