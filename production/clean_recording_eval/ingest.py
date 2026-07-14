"""STEP 1: move the recording into the raw folder, verify, and probe it.

Safe by construction: the destination is never overwritten (an existing file
of the same name aborts the move), the sha256 is taken before the copy and
re-verified after, and the source is deleted only once the checksums match.
Cross-drive moves are therefore atomic-in-effect: a failure at any point
leaves the original in Downloads.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from production.media_acquisition.download import sha256
from production.voice_dataset.config import MEDIA_EXTS


class IngestError(Exception):
    pass


@dataclass
class MediaProbe:
    filename: str
    size_bytes: int
    duration_s: float = 0.0
    sample_rate_hz: int = 0
    channels: int = 0
    audio_bitrate_bps: int = 0
    audio_codec: str = ""


def find_recording(downloads: Path, name: Optional[str] = None) -> Path:
    """The recording to ingest: by name, or the newest media file in Downloads."""
    downloads = Path(downloads)
    if name:
        p = downloads / name
        if not p.exists():
            raise IngestError(f"{p} not found")
        return p
    candidates = [p for p in downloads.iterdir()
                  if p.is_file() and p.suffix.lower() in MEDIA_EXTS] \
        if downloads.is_dir() else []
    if not candidates:
        raise IngestError(f"no media files found in {downloads}")
    return max(candidates, key=lambda p: p.stat().st_mtime)


def move_verified(src: Path, dest_dir: Path) -> tuple[Path, str]:
    """Move ``src`` into ``dest_dir`` with checksum verification, no overwrite."""
    src, dest_dir = Path(src), Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    if dest.exists():
        raise IngestError(f"refusing to overwrite existing file: {dest}")
    checksum = sha256(src)
    tmp = dest.with_suffix(dest.suffix + ".part")
    shutil.copyfile(src, tmp)
    if sha256(tmp) != checksum:
        tmp.unlink(missing_ok=True)
        raise IngestError(f"checksum mismatch after copy of {src.name}; source kept")
    tmp.rename(dest)
    src.unlink()                                  # source removed only after verify
    return dest, checksum


def probe(path: Path) -> MediaProbe:
    """Container/audio properties via ffprobe (already required by the builder)."""
    path = Path(path)
    result = MediaProbe(filename=path.name, size_bytes=path.stat().st_size)
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
           "-show_entries", "stream=codec_type,codec_name,sample_rate,channels,bit_rate",
           "-of", "json", str(path)]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
        info = json.loads(out)
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError):
        return result                              # size-only probe if ffprobe absent
    result.duration_s = float((info.get("format") or {}).get("duration") or 0.0)
    for s in info.get("streams") or []:
        if s.get("codec_type") == "audio":
            result.sample_rate_hz = int(s.get("sample_rate") or 0)
            result.channels = int(s.get("channels") or 0)
            result.audio_bitrate_bps = int(s.get("bit_rate") or 0)
            result.audio_codec = s.get("codec_name") or ""
            break
    return result


def format_probe(p: MediaProbe, checksum: str) -> str:
    return "\n".join([
        f"  Filename     : {p.filename}",
        f"  Duration     : {p.duration_s:.1f} s ({p.duration_s / 60.0:.1f} min)",
        f"  File size    : {p.size_bytes / 1e6:.1f} MB",
        f"  Sample rate  : {p.sample_rate_hz} Hz",
        f"  Channels     : {p.channels}",
        f"  Audio bitrate: {p.audio_bitrate_bps / 1000.0:.0f} kbps ({p.audio_codec})",
        f"  sha256       : {checksum}",
    ])
