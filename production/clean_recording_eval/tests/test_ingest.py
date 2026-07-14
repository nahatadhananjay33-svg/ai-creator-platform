"""Safe move semantics: newest-file discovery, no overwrite, verified copy."""
from __future__ import annotations

import os
import time

import pytest

from production.clean_recording_eval.ingest import (
    IngestError, MediaProbe, find_recording, format_probe, move_verified)
from production.media_acquisition.download import sha256


def test_find_recording_by_name_and_newest(tmp_path):
    (tmp_path / "old.wav").write_bytes(b"old")
    newer = tmp_path / "new.mov"
    newer.write_bytes(b"new")
    (tmp_path / "notes.txt").write_bytes(b"not media")
    old_time = time.time() - 3600
    os.utime(tmp_path / "old.wav", (old_time, old_time))

    assert find_recording(tmp_path).name == "new.mov"
    assert find_recording(tmp_path, name="old.wav").name == "old.wav"
    with pytest.raises(IngestError, match="not found"):
        find_recording(tmp_path, name="missing.wav")
    with pytest.raises(IngestError, match="no media files"):
        find_recording(tmp_path / "empty")


def test_move_verified_moves_and_checksums(tmp_path):
    src = tmp_path / "downloads" / "rec.wav"
    src.parent.mkdir()
    src.write_bytes(b"audio-bytes" * 1000)
    expected = sha256(src)
    dest_dir = tmp_path / "raw"

    dest, checksum = move_verified(src, dest_dir)

    assert dest == dest_dir / "rec.wav" and dest.exists()
    assert checksum == expected == sha256(dest)
    assert not src.exists()                       # moved, not copied
    assert not list(dest_dir.glob("*.part"))      # temp file cleaned up


def test_move_verified_never_overwrites(tmp_path):
    src = tmp_path / "downloads" / "rec.wav"
    src.parent.mkdir()
    src.write_bytes(b"new content")
    dest_dir = tmp_path / "raw"
    dest_dir.mkdir()
    (dest_dir / "rec.wav").write_bytes(b"existing content")

    with pytest.raises(IngestError, match="refusing to overwrite"):
        move_verified(src, dest_dir)
    assert src.exists()                                    # source untouched
    assert (dest_dir / "rec.wav").read_bytes() == b"existing content"


def test_format_probe_prints_required_fields():
    p = MediaProbe(filename="rec.mov", size_bytes=1_247_311_722,
                   duration_s=1810.1, sample_rate_hz=48000, channels=2,
                   audio_bitrate_bps=101573, audio_codec="aac")
    text = format_probe(p, "abc123")
    for marker in ("Filename     : rec.mov", "30.2 min", "1247.3 MB",
                   "48000 Hz", "Channels     : 2", "102 kbps (aac)", "abc123"):
        assert marker in text, marker
