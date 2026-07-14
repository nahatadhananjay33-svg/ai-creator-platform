"""Phase V4.1 STEPS 1-4: ZIP ingest, resumable extraction, media scan.

Additive to Phase V4 — nothing here changes the segment builder. Moves reuse
the V3 verified-move (sha256 before copy, re-verify after, never overwrite);
extraction is atomic-per-ZIP (extract to a ``.partial`` dir, rename on
success) so an interrupted run resumes safely.
"""
from __future__ import annotations

import shutil
import zipfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Tuple

from production.clean_recording_eval.ingest import IngestError, move_verified, probe
from production.voice_dataset.config import MEDIA_EXTS

ZIP_PREFIX = "New_videos_for_voice_clone"


def find_zips(downloads: Path, prefix: str = ZIP_PREFIX) -> List[Path]:
    downloads = Path(downloads)
    if not downloads.is_dir():
        return []
    return sorted(p for p in downloads.iterdir()
                  if p.is_file() and p.suffix.lower() == ".zip"
                  and p.name.startswith(prefix))


def move_zips(zips: List[Path], dest_dir: Path) -> Tuple[List[Path], List[str]]:
    """Verified move of each ZIP; existing destinations are kept, never overwritten.

    Returns (paths now in dest_dir, notes for skipped ones).
    """
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    moved, notes = [], []
    for z in zips:
        target = dest_dir / z.name
        if target.exists():
            notes.append(f"{z.name}: already present at destination - source left in place")
            moved.append(target)
            continue
        try:
            dest, _ = move_verified(z, dest_dir)
            moved.append(dest)
        except IngestError as e:
            notes.append(f"{z.name}: {e}")
    return moved, notes


def extract_zips(zips_dir: Path, extracted_dir: Path) -> Tuple[List[str], List[str]]:
    """Extract every ZIP into ``extracted/<zip_stem>/``; done folders are skipped.

    Atomic per ZIP: contents land in ``<stem>.partial`` first and the folder is
    renamed only after a complete extraction, so a crash mid-ZIP re-extracts
    that ZIP from scratch on the next run (never a half-read folder).
    """
    zips_dir, extracted_dir = Path(zips_dir), Path(extracted_dir)
    extracted_dir.mkdir(parents=True, exist_ok=True)
    done, skipped = [], []
    for z in sorted(zips_dir.glob("*.zip")):
        target = extracted_dir / z.stem
        if target.is_dir():
            skipped.append(z.stem)
            continue
        partial = extracted_dir / (z.stem + ".partial")
        if partial.exists():
            shutil.rmtree(partial)                 # leftover from an interrupted run
        with zipfile.ZipFile(z) as zf:
            zf.extractall(partial)
        partial.rename(target)
        done.append(z.stem)
    return done, skipped


@dataclass
class MediaScan:
    files: int = 0
    total_duration_s: float = 0.0
    total_bytes: int = 0
    formats: Counter = field(default_factory=Counter)


def scan_media(extracted_dir: Path) -> MediaScan:
    """STEP 4: count/duration/storage/formats of the extracted media."""
    scan = MediaScan()
    for p in sorted(Path(extracted_dir).rglob("*")):
        if not (p.is_file() and p.suffix.lower() in MEDIA_EXTS):
            continue
        scan.files += 1
        scan.total_bytes += p.stat().st_size
        scan.formats[p.suffix.lower().lstrip(".")] += 1
        scan.total_duration_s += probe(p).duration_s
    return scan


def format_scan(s: MediaScan) -> str:
    fmts = ", ".join(f"{k}: {v}" for k, v in sorted(s.formats.items())) or "none"
    return "\n".join([
        f"  Total videos   : {s.files}",
        f"  Total duration : {s.total_duration_s / 3600.0:.3f} h "
        f"({s.total_duration_s / 60.0:.1f} min)",
        f"  Storage        : {s.total_bytes / 1e9:.2f} GB",
        f"  Formats        : {fmts}",
    ])
