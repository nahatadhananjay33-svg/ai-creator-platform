"""Glue: run the existing Voice Dataset Builder over a flat video folder.

Reuses ``production.voice_dataset`` end to end (extract -> analyze -> classify ->
score -> decide -> storage). Adds folder discovery, tqdm progress, resume, and
Drive-sync of outputs. Deterministic; no ML/GPU of its own.
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import time
from collections import Counter
from pathlib import Path
from typing import Iterator, List, Optional

from production.voice_dataset.config import MEDIA_EXTS, Config as VConfig, Paths as VPaths
from production.voice_dataset.models import (MediaItem, Platform, Record,
                                             RECORD_COLUMNS)
from production.voice_dataset.pipeline import build_dataset
from production.voice_dataset.providers.base import MediaProvider
from production.voice_dataset.storage import write_csv, write_sqlite, write_xlsx
from production.voice_dataset.summary import summarize

_BOOL_COLS = {"accepted", "has_speech", "multi_speaker", "has_music"}


def _progress(iterable, total=None, desc="clips"):
    try:
        from tqdm.auto import tqdm
        return tqdm(iterable, total=total, desc=desc, unit="clip")
    except Exception:
        return iterable


class FolderProvider(MediaProvider):
    """Yields every video/audio file in a flat source folder (recursive, sorted).

    ``skip`` (a set of filenames) supports resume: already-processed clips are
    not yielded. When ``progress`` is on, discovery is wrapped in a tqdm bar that
    advances as the builder consumes each item.
    """

    def __init__(self, source_dir: Path, skip: Optional[set] = None,
                 progress: bool = True, desc: str = "clips"):
        self.source_dir = Path(source_dir)
        self.skip = skip or set()
        self.progress = progress
        self.desc = desc

    def files(self) -> List[Path]:
        return sorted(
            (p for p in self.source_dir.rglob("*")
             if p.is_file() and p.suffix.lower() in MEDIA_EXTS and p.name not in self.skip),
            key=lambda x: x.as_posix())

    def discover(self) -> Iterator[MediaItem]:
        fs = self.files()
        it = _progress(fs, total=len(fs), desc=self.desc) if self.progress else fs
        for p in it:
            yield MediaItem(path=str(p), filename=p.name,
                            platform=Platform.UNKNOWN, source=p.name)


def _load_records(dataset_sqlite: Path) -> List[dict]:
    if not Path(dataset_sqlite).exists():
        return []
    conn = sqlite3.connect(str(dataset_sqlite))
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM dataset")]
    except Exception:
        return []
    finally:
        conn.close()


def _row_to_record(row: dict) -> Record:
    kw = {c: (bool(row[c]) if c in _BOOL_COLS else row[c]) for c in RECORD_COLUMNS}
    return Record(**kw)


def _wav_name(rec: Record) -> str:
    return Path(rec.filename).stem + ".wav"


def _dir_size(path: Path) -> int:
    total = 0
    for p in Path(path).rglob("*"):
        try:
            if p.is_file():
                total += p.stat().st_size
        except OSError:                      # tolerate a flaky mount
            continue
    return total


def _same_size(a, b) -> bool:
    try:
        return Path(a).stat().st_size == Path(b).stat().st_size
    except OSError:
        return False


def _robust_copyfile(src, dst, retries: int = 3, on_error=None,
                     backoff: float = 1.0, sleep=time.sleep) -> bool:
    """Copy with retry — survives a transient Drive FUSE drop (Errno 107).

    ``on_error`` (e.g. a Drive remount) is called between attempts.
    """
    for attempt in range(1, retries + 1):
        try:
            shutil.copyfile(src, dst)
            return True
        except OSError:
            if attempt == retries:
                return False
            if on_error:
                try:
                    on_error()
                except Exception:
                    pass
            if backoff:
                sleep(backoff * attempt)
    return False


def _list_media(src_dir, on_error=None, retries: int = 3, sleep=time.sleep) -> List[Path]:
    """List media files (by extension, no per-file stat), retrying the walk on OSError."""
    src_dir = Path(src_dir)
    for attempt in range(1, retries + 1):
        try:
            return sorted((p for p in src_dir.rglob("*")
                           if p.suffix.lower() in MEDIA_EXTS),
                          key=lambda x: x.as_posix())
        except OSError:
            if attempt == retries:
                raise
            if on_error:
                try:
                    on_error()
                except Exception:
                    pass
            sleep(1.0 * attempt)
    return []


def copy_media(src_dir, dst_dir, retries: int = 3, on_error=None,
               progress: bool = True):
    """Copy every media file src_dir -> dst_dir (flat), resumable and retrying.

    Skips files already present at the same size (resume). Returns
    (copied_paths, failed_names). Use this to stage flaky Drive media onto fast,
    reliable local disk before processing.
    """
    src_dir, dst_dir = Path(src_dir), Path(dst_dir)
    dst_dir.mkdir(parents=True, exist_ok=True)
    files = _list_media(src_dir, on_error=on_error, retries=retries)
    it = _progress(files, total=len(files), desc="copying") if progress else files
    copied, failed = [], []
    for p in it:
        target = dst_dir / p.name
        if target.exists() and _same_size(p, target):
            copied.append(target)
            continue
        if _robust_copyfile(p, target, retries=retries, on_error=on_error):
            copied.append(target)
        else:
            failed.append(p.name)
    return copied, failed


def run_pipeline(source_dir: Path, workspace: Path, drive_out: Path,
                 creator: str = "tanshi", resume: bool = True,
                 progress: bool = True, cfg: Optional[VConfig] = None,
                 on_error=None) -> dict:
    """Process ``source_dir`` into a voice dataset saved under ``drive_out``.

    Reuses the existing builder for all per-clip work. Returns the summary dict.
    """
    t0 = time.time()
    cfg = cfg or VConfig()
    source_dir, workspace, drive_out = Path(source_dir), Path(workspace), Path(drive_out)

    vpaths = VPaths.for_creator(workspace, creator).ensure()
    drive_meta = drive_out / "metadata"
    drive_acc = drive_out / "accepted"
    drive_rej = drive_out / "rejected"
    drive_reports = drive_out / "reports"
    for d in (drive_meta, drive_acc, drive_rej, drive_reports):
        d.mkdir(parents=True, exist_ok=True)

    prior = [_row_to_record(r) for r in _load_records(drive_meta / "dataset.sqlite")] if resume else []
    done = {r.filename for r in prior}

    provider = FolderProvider(source_dir, skip=done, progress=progress)
    new_records = build_dataset(vpaths, cfg, provider=provider)

    # sync freshly-processed audio to Drive (resilient to Drive FUSE drops)
    for rec in new_records:
        wn = _wav_name(rec)
        src = (vpaths.accepted if rec.accepted else vpaths.rejected) / wn
        if src.exists():
            _robust_copyfile(src, (drive_acc if rec.accepted else drive_rej) / wn,
                             on_error=on_error)

    merged = prior + new_records
    for i, rec in enumerate(merged, 1):          # renumber ids, point audio at Drive
        rec.id = i
        rec.audio_path = str((drive_acc if rec.accepted else drive_rej) / _wav_name(rec))

    ws_meta = vpaths.metadata
    write_sqlite(merged, ws_meta / "dataset.sqlite")
    write_csv(merged, ws_meta / "dataset.csv")
    write_xlsx(merged, ws_meta / "dataset.xlsx")
    for name in ("dataset.sqlite", "dataset.csv", "dataset.xlsx"):
        _robust_copyfile(ws_meta / name, drive_meta / name, on_error=on_error)

    summary = _summary(merged, processed=len(new_records), skipped=len(done),
                       elapsed=time.time() - t0, drive_out=drive_out)
    (drive_reports / "summary.json").write_text(json.dumps(summary, indent=2))
    (drive_out / "summary.json").write_text(json.dumps(summary, indent=2))
    return summary


def _summary(records: List[Record], processed: int, skipped: int,
             elapsed: float, drive_out: Path) -> dict:
    s = summarize(records)
    accepted = [r for r in records if r.accepted]
    rejected = [r for r in records if not r.accepted]
    durations = [r.duration for r in records] or [0.0]
    failed = sum(1 for r in records if r.reason.startswith("extract failed"))
    top = Counter(r.reason for r in rejected).most_common(5)
    return {
        "total_videos": len(records),
        "videos_processed": processed,
        "videos_skipped": skipped,
        "videos_failed": failed,
        "accepted_clips": len(accepted),
        "rejected_clips": len(rejected),
        "accepted_speech_hours": round(sum(r.speech_duration for r in accepted) / 3600.0, 3),
        "rejected_speech_hours": round(sum(r.speech_duration for r in rejected) / 3600.0, 3),
        "average_clip_duration_s": round(sum(durations) / len(durations), 1),
        "average_quality": s["average_quality"],
        "top_rejection_reasons": top,
        "total_processing_time_s": round(elapsed, 1),
        "storage_used_mb": round(_dir_size(drive_out) / 1e6, 1),
    }


def format_report(summary: dict) -> str:
    lines = ["=" * 50, "  VOICE DATASET REPORT", "=" * 50,
             f"  Videos processed     : {summary['videos_processed']}",
             f"  Videos skipped       : {summary['videos_skipped']}",
             f"  Videos failed        : {summary['videos_failed']}",
             f"  Accepted clips       : {summary['accepted_clips']}",
             f"  Rejected clips       : {summary['rejected_clips']}",
             f"  Accepted speech hours: {summary['accepted_speech_hours']:.3f}",
             f"  Rejected speech hours: {summary['rejected_speech_hours']:.3f}",
             f"  Avg clip duration    : {summary['average_clip_duration_s']:.1f} s",
             f"  Average quality      : {summary['average_quality']}",
             f"  Processing time      : {summary['total_processing_time_s']:.1f} s",
             f"  Storage used         : {summary['storage_used_mb']:.1f} MB"]
    if summary["top_rejection_reasons"]:
        lines.append("  Top rejection reasons:")
        for reason, count in summary["top_rejection_reasons"]:
            lines.append(f"    - {reason} ({count})")
    lines.append("=" * 50)
    return "\n".join(lines)
