"""Per-recording pipeline: extract -> VAD -> segment -> evaluate -> route.

One source file per call so a single oversized or corrupt recording cannot
lose the batch (the V2/V3 lesson); the caller persists incrementally and
cleans the workspace between files.
"""
from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

from production.voice_dataset.analyze import load_wav
from production.voice_dataset.config import MEDIA_EXTS
from production.voice_dataset.extract import extract_audio

from .config import V4Config
from .evaluate import evaluate_segment, write_segment_wav
from .models import SegmentRecord
from .vad import frame_levels, plan_segments, speech_regions


def discover_sources(sources: Dict[str, Path]) -> List[Tuple[str, Path, str]]:
    """(kind, path, source_key) for every media file under every source root.

    ``source_key`` is the root-relative path — unique even when basenames
    repeat across nested folders (the raw phone dump has 11 subtrees).
    """
    out: List[Tuple[str, Path, str]] = []
    for kind in sorted(sources):
        root = Path(sources[kind])
        if not root.is_dir():
            continue
        for p in sorted(root.rglob("*"), key=lambda x: x.as_posix()):
            if p.is_file() and p.suffix.lower() in MEDIA_EXTS:
                out.append((kind, p, p.relative_to(root).as_posix()))
    return out


def _safe_stem(kind: str, source_key: str) -> str:
    """Filesystem-safe, collision-free stem for segment files."""
    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", Path(source_key).stem)[:40]
    tag = hashlib.sha1(f"{kind}/{source_key}".encode()).hexdigest()[:8]
    return f"{kind}__{stem}__{tag}"


def process_source(src: Path, kind: str, source_key: str, accepted_dir: Path,
                   rejected_dir: Path, workspace: Path, cfg: V4Config,
                   next_id: int) -> List[SegmentRecord]:
    """Segment and evaluate one recording; returns its records (ids assigned)."""
    workspace = Path(workspace)
    extracted_dir = workspace / "extracted"
    staging_dir = workspace / "segments"
    for d in (extracted_dir, staging_dir, accepted_dir, rejected_dir):
        Path(d).mkdir(parents=True, exist_ok=True)

    wav = extract_audio(Path(src), extracted_dir)      # reuse (WAV passthrough)
    try:
        samples, sr, _, _ = load_wav(wav)
        if sr <= 0 or samples.size == 0:
            return []
        dbfs, _, frame_dur = frame_levels(samples, sr, cfg)
        if dbfs.size == 0:
            return []
        source_noise_floor = float(np.percentile(dbfs, 10))
        segments = plan_segments(speech_regions(dbfs, frame_dur, cfg),
                                 dbfs, frame_dur, samples.size / sr, cfg)

        records: List[SegmentRecord] = []
        stem = _safe_stem(kind, source_key)
        for i, seg in enumerate(segments, start=1):
            name = f"{stem}__{i:04d}.wav"
            staged = write_segment_wav(samples, sr, seg, staging_dir / name)
            rec = evaluate_segment(staged, seg, source_key, kind,
                                   next_id + len(records), cfg,
                                   source_noise_floor=source_noise_floor)
            final = (accepted_dir if rec.accepted else rejected_dir) / name
            os.replace(staged, final)
            rec.audio_path = str(final)
            records.append(rec)
        return records
    finally:
        wav_path = Path(wav)
        if wav_path.exists() and wav_path.parent == extracted_dir:
            wav_path.unlink()                          # bound workspace disk
        for leftover in staging_dir.glob("*.wav"):
            leftover.unlink()
