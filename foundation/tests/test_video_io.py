"""Tests for dependency-free video I/O."""
from __future__ import annotations

from pathlib import Path

import pytest

from foundation.exceptions import PlatformError
from foundation.shared_utils.video_io import (
    VideoFrames,
    generate_test_pattern_video,
    read_raw_avi,
    write_raw_avi,
)


def test_round_trip(tmp_path: Path) -> None:
    frames = [bytes((i % 256,) * (16 * 8 * 3)) for i in range(5)]
    original = VideoFrames(frames, width=16, height=8, fps=10.0)
    path = write_raw_avi(tmp_path / "clip.avi", original)
    loaded = read_raw_avi(path)
    assert loaded.n_frames == 5
    assert (loaded.width, loaded.height) == (16, 8)
    assert loaded.fps == pytest.approx(10.0, abs=0.1)
    assert loaded.frames == original.frames


def test_round_trip_with_row_padding(tmp_path: Path) -> None:
    # width 5 -> 15-byte rows padded to 16; padding must not leak back in.
    frames = [bytes(range(5 * 3)) * 4]
    original = VideoFrames(frames, width=5, height=4, fps=25.0)
    loaded = read_raw_avi(write_raw_avi(tmp_path / "pad.avi", original))
    assert loaded.frames == original.frames


def test_duration_and_grayscale() -> None:
    video = VideoFrames([b"\x00\x00\x00" * 4, b"\xff\xff\xff" * 4], 2, 2, 2.0)
    assert video.duration_s == pytest.approx(1.0)
    assert video.grayscale_frame(0) == [0, 0, 0, 0]
    assert video.grayscale_frame(1) == [255, 255, 255, 255]


def test_rejects_empty_video(tmp_path: Path) -> None:
    with pytest.raises(PlatformError):
        write_raw_avi(tmp_path / "empty.avi", VideoFrames([], 4, 4, 25.0))


def test_rejects_non_avi(tmp_path: Path) -> None:
    bogus = tmp_path / "not.avi"
    bogus.write_bytes(b"definitely not a RIFF file")
    with pytest.raises(PlatformError):
        read_raw_avi(bogus)


def test_generate_test_pattern(tmp_path: Path) -> None:
    path = generate_test_pattern_video(tmp_path / "pattern.avi", 32, 16, 6, 12.0)
    video = read_raw_avi(path)
    assert video.n_frames == 6
    assert (video.width, video.height) == (32, 16)
    # Motion: consecutive frames must differ.
    assert video.frames[0] != video.frames[1]
