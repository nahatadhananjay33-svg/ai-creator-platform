"""STEPS 1+2: energy VAD and 5-20 s segment planning.

Reuses the existing builder's frame primitives (`_frame_dbfs`,
`_smooth_voiced`) so speech detection is measured exactly the way every prior
phase measured it. The VAD floor adapts to each recording: frames must exceed
both the builder's hard silence floor and the recording's own noise floor plus
a margin, so quiet rooms and noisy rooms are treated fairly.

Segment planning targets 5-20 s: regions separated by pauses longer than the
merge gap stay separate ("ignore long pauses"), short neighbouring regions are
joined across sub-second pauses, and regions longer than the target are split
at the QUIETEST frame in the allowed window — the most pause-like moment — to
avoid cutting inside a sentence.
"""
from __future__ import annotations

from typing import List, Tuple

import numpy as np

from production.voice_dataset.analyze import _frame_dbfs, _smooth_voiced

from .config import V4Config
from .models import Segment


def frame_levels(samples: np.ndarray, sr: int, cfg: V4Config) -> Tuple[np.ndarray, int, float]:
    """Per-frame dBFS plus (frame_len, frame_dur) for the recording."""
    frame_len = max(1, int(sr * cfg.frame_ms / 1000.0))
    dbfs = _frame_dbfs(samples, frame_len)
    return dbfs, frame_len, (frame_len / sr if sr else 0.0)


def speech_regions(dbfs: np.ndarray, frame_dur: float, cfg: V4Config) -> List[Tuple[int, int]]:
    """Contiguous voiced frame runs [start, end) after smoothing."""
    if dbfs.size == 0 or frame_dur <= 0:
        return []
    # Adaptive floor: above the recording's own noise floor, but never so high
    # that it swallows speech — in a mostly-voiced take the 10th percentile IS
    # speech, so the adaptive part is capped 6 dB under the loud-frame level.
    noise_floor = float(np.percentile(dbfs, 10))
    speech_level = float(np.percentile(dbfs, 90))
    threshold = max(cfg.silence_floor_dbfs,
                    min(noise_floor + cfg.vad_snr_margin_db, speech_level - 6.0))
    voiced_raw = dbfs >= threshold
    min_run = max(1, int(round(cfg.vad_min_run_ms / 1000.0 / frame_dur)))
    merge_gap = max(1, int(round(cfg.vad_merge_gap_ms / 1000.0 / frame_dur)))
    voiced = _smooth_voiced(voiced_raw, min_run, merge_gap)

    regions: List[Tuple[int, int]] = []
    i, n = 0, voiced.size
    while i < n:
        if voiced[i]:
            j = i
            while j < n and voiced[j]:
                j += 1
            regions.append((i, j))
            i = j
        else:
            i += 1
    return regions


def _join_regions(regions: List[Tuple[int, int]], frame_dur: float,
                  cfg: V4Config) -> List[Tuple[int, int]]:
    """Merge neighbours across pauses <= join_gap_max_s while staying <= max."""
    if not regions:
        return []
    max_frames = int(cfg.max_segment_s / frame_dur)
    join_gap = int(cfg.join_gap_max_s / frame_dur)
    out = [regions[0]]
    for start, end in regions[1:]:
        p_start, p_end = out[-1]
        if start - p_end <= join_gap and (end - p_start) <= max_frames:
            out[-1] = (p_start, end)
        else:
            out.append((start, end))
    return out


def _split_region(start: int, end: int, dbfs: np.ndarray, frame_dur: float,
                  cfg: V4Config) -> List[Tuple[int, int]]:
    """Split a long region at the quietest frames within the allowed window."""
    min_f = max(1, int(cfg.min_segment_s / frame_dur))
    max_f = max(min_f + 1, int(cfg.max_segment_s / frame_dur))
    pieces: List[Tuple[int, int]] = []
    pos = start
    while end - pos > max_f:
        lo, hi = pos + min_f, pos + max_f
        cut = lo + int(np.argmin(dbfs[lo:hi]))       # most pause-like moment
        pieces.append((pos, cut))
        pos = cut
    # tail: if it came out shorter than min and can fold into the previous
    # piece without exceeding max (+small tolerance), extend the previous piece.
    if pieces and (end - pos) < min_f and (end - pieces[-1][0]) <= int(max_f * 1.1):
        pieces[-1] = (pieces[-1][0], end)
    else:
        pieces.append((pos, end))
    return pieces


def plan_segments(regions: List[Tuple[int, int]], dbfs: np.ndarray,
                  frame_dur: float, total_s: float, cfg: V4Config) -> List[Segment]:
    """Turn voiced regions into padded 5-20 s (target) segments in seconds."""
    if frame_dur <= 0:
        return []
    joined = _join_regions(regions, frame_dur, cfg)
    pad = cfg.pad_ms / 1000.0
    segments: List[Segment] = []
    for start, end in joined:
        for s, e in _split_region(start, end, dbfs, frame_dur, cfg):
            start_s = max(0.0, s * frame_dur - pad)
            end_s = min(total_s, e * frame_dur + pad)
            if end_s > start_s:
                segments.append(Segment(start_s=round(start_s, 3), end_s=round(end_s, 3)))
    return segments
