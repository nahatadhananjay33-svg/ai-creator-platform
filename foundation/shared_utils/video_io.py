"""Dependency-free video I/O for benchmarking and testing.

Same philosophy as :mod:`foundation.shared_utils.audio_io`: the platform's
plumbing (mock adapters, dataset validation, basic video metrics) must run
on any machine with no numpy/opencv installed. The canonical dependency-free
interchange format is the uncompressed BGR24 AVI (``BI_RGB`` DIB frames),
which this module both writes and reads with the stdlib only.

Real model outputs (H.264 MP4 etc.) are decoded by the optional OpenCV
backend in ``avatar_engine.evaluation``; this module stays codec-free.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

from foundation.exceptions import PlatformError


@dataclass(frozen=True)
class VideoFrames:
    """In-memory uncompressed video: one ``bytes`` of BGR24 rows per frame."""

    frames: list[bytes]  # each len == width * height * 3, top-down rows
    width: int
    height: int
    fps: float

    @property
    def n_frames(self) -> int:
        return len(self.frames)

    @property
    def duration_s(self) -> float:
        return self.n_frames / self.fps if self.fps else 0.0

    def grayscale_frame(self, index: int) -> list[int]:
        """Integer-luma pixels (top-down row-major) of one frame."""
        frame = self.frames[index]
        # ITU-R BT.601 luma, integer arithmetic
        return [
            (29 * frame[i] + 150 * frame[i + 1] + 77 * frame[i + 2]) >> 8
            for i in range(0, len(frame), 3)
        ]


def _pad4(n: int) -> int:
    return (n + 3) & ~3


def write_raw_avi(path: Path | str, video: VideoFrames) -> Path:
    """Write an uncompressed BGR24 AVI (``BI_RGB``, bottom-up DIB frames)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    w, h, n = video.width, video.height, video.n_frames
    if w <= 0 or h <= 0 or n == 0:
        raise PlatformError("Cannot write empty video", path=str(path))
    row_bytes = _pad4(w * 3)
    frame_bytes = row_bytes * h
    us_per_frame = int(round(1_000_000 / video.fps)) if video.fps else 40_000

    def bottom_up(frame: bytes) -> bytes:
        rows = [frame[y * w * 3:(y + 1) * w * 3].ljust(row_bytes, b"\x00") for y in range(h)]
        return b"".join(reversed(rows))

    avih = struct.pack(
        "<14I", us_per_frame, frame_bytes * int(video.fps or 25), 0, 0x10,  # AVIF_HASINDEX
        n, 0, 1, frame_bytes, w, h, 0, 0, 0, 0,
    )
    strh = struct.pack(
        "<4s4sIHHIIIIIIIIhhhh", b"vids", b"DIB ", 0, 0, 0, 0,
        1_000_000, us_per_frame and 1_000_000 // us_per_frame or 25, 0, n,
        frame_bytes, 0xFFFFFFFF, 0, 0, 0, w, h,
    )
    strf = struct.pack("<IiiHHIIiiII", 40, w, h, 1, 24, 0, frame_bytes, 0, 0, 0, 0)

    def chunk(fourcc: bytes, payload: bytes) -> bytes:
        pad = b"\x00" if len(payload) % 2 else b""
        return fourcc + struct.pack("<I", len(payload)) + payload + pad

    def lst(fourcc: bytes, payload: bytes) -> bytes:
        return chunk(b"LIST", fourcc + payload)

    strl = lst(b"strl", chunk(b"strh", strh) + chunk(b"strf", strf))
    hdrl = lst(b"hdrl", chunk(b"avih", avih) + strl)

    movi_frames = [chunk(b"00db", bottom_up(f)) for f in video.frames]
    movi = lst(b"movi", b"".join(movi_frames))

    idx_entries, offset = [], 4  # offset counted from start of 'movi' fourcc
    for f in movi_frames:
        idx_entries.append(struct.pack("<4sIII", b"00db", 0x10, offset, len(f) - 8))
        offset += len(f)
    idx1 = chunk(b"idx1", b"".join(idx_entries))

    riff_payload = b"AVI " + hdrl + movi + idx1
    path.write_bytes(b"RIFF" + struct.pack("<I", len(riff_payload)) + riff_payload)
    return path


def read_raw_avi(path: Path | str) -> VideoFrames:
    """Read an uncompressed BGR24 AVI written by :func:`write_raw_avi`.

    Raises :class:`PlatformError` for compressed or foreign AVI flavors —
    callers fall back to the optional OpenCV backend for those.
    """
    path = Path(path)
    data = path.read_bytes()
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"AVI ":
        raise PlatformError("Not a RIFF/AVI file", path=str(path))

    width = height = 0
    fps = 25.0
    frames: list[bytes] = []

    def walk(start: int, end: int) -> None:
        nonlocal width, height, fps
        pos = start
        while pos + 8 <= end:
            fourcc = data[pos:pos + 4]
            (size,) = struct.unpack_from("<I", data, pos + 4)
            body_start, body_end = pos + 8, pos + 8 + size
            if fourcc == b"LIST":
                walk(body_start + 4, body_end)
            elif fourcc == b"avih":
                (us_per_frame,) = struct.unpack_from("<I", data, body_start)
                if us_per_frame:
                    fps = 1_000_000 / us_per_frame
                width, height = struct.unpack_from("<II", data, body_start + 32)
            elif fourcc == b"strf":
                bit_count = struct.unpack_from("<H", data, body_start + 14)[0]
                compression = struct.unpack_from("<I", data, body_start + 16)[0]
                if bit_count != 24 or compression != 0:
                    raise PlatformError(
                        "Compressed/non-BGR24 AVI; use the OpenCV backend",
                        path=str(path),
                    )
            elif fourcc in (b"00db", b"00dc") and size:
                frames.append(data[body_start:body_end])
            pos = body_end + (size % 2)

    walk(12, len(data))
    if not width or not height or not frames:
        raise PlatformError("AVI contains no decodable frames", path=str(path))

    row_bytes = _pad4(width * 3)
    top_down: list[bytes] = []
    for raw in frames:
        rows = [raw[y * row_bytes:y * row_bytes + width * 3] for y in range(height)]
        top_down.append(b"".join(reversed(rows)))
    return VideoFrames(frames=top_down, width=width, height=height, fps=round(fps, 3))


def generate_test_pattern_video(
    path: Path | str,
    width: int = 64,
    height: int = 64,
    n_frames: int = 25,
    fps: float = 25.0,
    motion: bool = True,
) -> Path:
    """Write a synthetic moving-gradient AVI — deterministic test footage."""
    frames: list[bytes] = []
    for t in range(n_frames):
        shift = (t * 4) % 256 if motion else 0
        row = bytearray()
        frame = bytearray()
        for y in range(height):
            row.clear()
            for x in range(width):
                row += bytes((
                    (x * 4 + shift) % 256,          # B
                    (y * 4) % 256,                  # G
                    (x * 2 + y * 2 + shift) % 256,  # R
                ))
            frame += row
        frames.append(bytes(frame))
    return write_raw_avi(path, VideoFrames(frames, width, height, fps))
