"""Manifest build/verify + dataset validation (hermetic, offline)."""
from __future__ import annotations

import shutil
import sqlite3

import pytest

from production.cloud_setup.manifest import (build_manifest, validate_metadata,
                                             validate_structure, verify_against,
                                             write_manifest, load_manifest)


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    import socket

    def _blocked(*a, **k):
        raise RuntimeError("network disabled in tests")

    monkeypatch.setattr(socket.socket, "connect", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)


def _dataset(tmp_path, accepted=("a.wav", "b.wav"), rejected=("r.wav",), consistent=True):
    root = tmp_path / "production_voice_dataset"
    for d in ("accepted_segments", "rejected_segments", "metadata", "reports"):
        (root / d).mkdir(parents=True)
    for n in accepted:
        (root / "accepted_segments" / n).write_bytes(b"RIFF" + n.encode() * 8)
    for n in rejected:
        (root / "rejected_segments" / n).write_bytes(b"RIFF" + n.encode() * 4)
    for m in ("dataset.csv", "dataset.xlsx"):
        (root / "metadata" / m).write_bytes(b"meta")
    db = root / "metadata" / "dataset.sqlite"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE dataset (id INTEGER, segment_file TEXT, duration REAL,"
                 " speech_duration REAL, accepted INTEGER, quality TEXT)")
    rows = [(i, n, 10.0, 8.0, 1, "good") for i, n in enumerate(accepted, 1)]
    if consistent:
        rows += [(100 + i, n, 5.0, 1.0, 0, "reject") for i, n in enumerate(rejected, 1)]
    else:
        rows.append((999, "ghost.wav", 10.0, 8.0, 1, "good"))   # metadata row w/o file
    conn.executemany("INSERT INTO dataset VALUES (?,?,?,?,?,?)", rows)
    conn.commit()
    conn.close()
    return root


def test_validate_structure_and_metadata(tmp_path):
    root = _dataset(tmp_path)
    st = validate_structure(root)
    assert st["ok"] and st["accepted_wavs"] == 2 and st["rejected_wavs"] == 1
    md = validate_metadata(root)
    assert md["ok"] and md["accepted_rows"] == 2 and md["accepted_on_disk"] == 2
    assert md["missing_count"] == 0 and md["orphan_count"] == 0
    # hours are rounded to 3dp by validate_metadata (2 accepted x 10s)
    assert md["accepted_hours"] == round(20 / 3600, 3)
    assert md["accepted_speech_hours"] == round(16 / 3600, 3)


def test_validate_detects_missing_dirs(tmp_path):
    root = _dataset(tmp_path)
    shutil.rmtree(root / "reports")
    st = validate_structure(root)
    assert not st["ok"] and "reports" in st["missing_dirs"]


def test_validate_detects_metadata_mismatch(tmp_path):
    root = _dataset(tmp_path, consistent=False)
    md = validate_metadata(root)
    assert not md["ok"] and md["missing_count"] == 1 and "ghost.wav" in md["missing_on_disk"]


def test_manifest_and_verify_roundtrip(tmp_path):
    root = _dataset(tmp_path)
    man = build_manifest(root, progress=False)
    assert man["file_count"] == 6                # 2 acc + 1 rej + 3 metadata
    assert man["total_bytes"] > 0
    assert all(len(e["sha256"]) == 64 for e in man["files"])

    p = write_manifest(man, tmp_path / "m.json", tmp_path / "m.csv")
    assert load_manifest(p)["file_count"] == 6

    # an exact copy verifies clean (full hash)
    target = tmp_path / "uploaded"
    shutil.copytree(root, target)
    res = verify_against(man, target, progress=False)
    assert res["ok"] and res["verified"] == 6


def test_verify_detects_missing_and_corrupt(tmp_path):
    root = _dataset(tmp_path)
    man = build_manifest(root, progress=False)
    target = tmp_path / "uploaded"
    shutil.copytree(root, target)
    (target / "accepted_segments" / "a.wav").unlink()                 # missing
    (target / "accepted_segments" / "b.wav").write_bytes(b"CORRUPTED-DIFFERENT-LENGTH")
    res = verify_against(man, target, progress=False)
    assert not res["ok"]
    assert res["missing_count"] == 1 and "accepted_segments/a.wav" in res["missing"]
    assert res["size_mismatch_count"] == 1


def test_verify_quick_skips_hashing(tmp_path):
    root = _dataset(tmp_path)
    man = build_manifest(root, progress=False)
    target = tmp_path / "uploaded"
    shutil.copytree(root, target)
    # same size, different content -> full catches it, quick does not
    victim = target / "accepted_segments" / "a.wav"
    victim.write_bytes(b"X" * victim.stat().st_size)
    assert verify_against(man, target, quick=True, progress=False)["ok"] is True
    assert verify_against(man, target, quick=False, progress=False)["hash_mismatch_count"] == 1
