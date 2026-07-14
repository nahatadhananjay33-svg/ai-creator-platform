"""Reporting for STEPS 4-7: statistics, random inspection, comparison, recommendation.

Read-only over the dataset.sqlite files the Voice Dataset Builder wrote; every
number is measured, every threshold used for the *assessment* comes from
``V2Config`` (the builder's acceptance thresholds are never touched).
"""
from __future__ import annotations

import random
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .config import V2Config

QUALITY_RANK = {"poor": 0, "fair": 1, "good": 2, "excellent": 3}
RANK_LABEL = {v: k for k, v in QUALITY_RANK.items()}


def load_records(dataset_sqlite: Path) -> List[dict]:
    path = Path(dataset_sqlite)
    if not path.exists():
        return []
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    try:
        rows = [dict(r) for r in conn.execute("SELECT * FROM dataset")]
    finally:
        conn.close()
    for r in rows:
        r["accepted"] = bool(r.get("accepted"))
    return rows


# --- STEP 4: statistics -------------------------------------------------------

def dataset_stats(records: List[dict], total_videos: Optional[int] = None) -> dict:
    accepted = [r for r in records if r["accepted"]]
    rejected = [r for r in records if not r["accepted"]]
    if accepted:
        avg_rank = sum(QUALITY_RANK.get(r["quality"], 0) for r in accepted) / len(accepted)
        avg_quality = RANK_LABEL[int(round(avg_rank))]
    else:
        avg_quality = "n/a"
    return {
        "total_videos": total_videos if total_videos is not None else len(records),
        "total_clips": len(records),
        "total_audio_hours": round(sum(r["duration"] for r in records) / 3600.0, 3),
        "accepted_clips": len(accepted),
        "rejected_clips": len(rejected),
        "accepted_speech_hours": round(sum(r["speech_duration"] for r in accepted) / 3600.0, 3),
        "rejected_speech_hours": round(sum(r["speech_duration"] for r in rejected) / 3600.0, 3),
        "average_quality": avg_quality,
        "top_rejection_reasons": Counter(r["reason"] for r in rejected).most_common(5),
    }


def format_stats(s: dict, title: str) -> str:
    lines = [f"  {title}",
             f"  Total videos          : {s['total_videos']}",
             f"  Total audio duration  : {s['total_audio_hours']:.3f} h",
             f"  Accepted clips        : {s['accepted_clips']}",
             f"  Rejected clips        : {s['rejected_clips']}",
             f"  Accepted speech hours : {s['accepted_speech_hours']:.3f}",
             f"  Rejected speech hours : {s['rejected_speech_hours']:.3f}",
             f"  Average quality       : {s['average_quality']}"]
    if s["top_rejection_reasons"]:
        lines.append("  Top rejection reasons :")
        for reason, count in s["top_rejection_reasons"]:
            lines.append(f"    - {reason} ({count})")
    return "\n".join(lines)


# --- STEP 5: random inspection -------------------------------------------------

def sample_inspection(records: List[dict], n: int, seed: int) -> Tuple[List[dict], List[dict]]:
    """Deterministic random sample of accepted and rejected records."""
    rng = random.Random(seed)
    accepted = sorted((r for r in records if r["accepted"]), key=lambda r: r["filename"])
    rejected = sorted((r for r in records if not r["accepted"]), key=lambda r: r["filename"])
    return (rng.sample(accepted, min(n, len(accepted))),
            rng.sample(rejected, min(n, len(rejected))))


def format_inspection(sample: List[dict], bucket: str) -> str:
    header = (f"  {bucket} sample ({len(sample)} clips)\n"
              f"  {'filename':<44} {'dur(s)':>8} {'quality':>9}  reason")
    lines = [header, "  " + "-" * 100]
    for r in sample:
        lines.append(f"  {r['filename'][:44]:<44} {r['duration']:>8.1f} "
                     f"{r['quality']:>9}  {r['reason']}")
    if not sample:
        lines.append("  (none)")
    return "\n".join(lines)


# --- STEP 6: comparison ---------------------------------------------------------

def dataset_metrics(records: List[dict]) -> Dict[str, float]:
    """Comparison metrics; SNR / duration / quality are over ACCEPTED clips."""
    accepted = [r for r in records if r["accepted"]]
    n = len(accepted)
    return {
        "total_clips": len(records),
        "accepted_clips": n,
        "accepted_speech_hours": round(sum(r["speech_duration"] for r in accepted) / 3600.0, 3),
        "avg_snr_db": round(sum(r["snr_db"] for r in accepted) / n, 2) if n else 0.0,
        "avg_clip_duration_s": round(sum(r["duration"] for r in accepted) / n, 1) if n else 0.0,
        "quality_score": round(sum(QUALITY_RANK.get(r["quality"], 0) for r in accepted) / n, 2)
                         if n else 0.0,
    }


def suitability(m: Dict[str, float], cfg: V2Config) -> str:
    quality_ok = (m["accepted_clips"] > 0
                  and m["avg_snr_db"] >= cfg.min_avg_snr_db
                  and m["quality_score"] >= cfg.min_avg_quality_rank)
    if quality_ok and m["accepted_speech_hours"] >= cfg.sufficient_speech_hours:
        return "suitable on its own"
    if quality_ok and m["accepted_speech_hours"] >= cfg.usable_speech_hours:
        return "usable as a contribution"
    if quality_ok:
        return "high quality but too little speech"
    return "not suitable"


def format_comparison(yt: Dict[str, float], base: Dict[str, float], cfg: V2Config) -> str:
    rows = [("Accepted clips", "accepted_clips", "{:.0f}"),
            ("Accepted speech hours", "accepted_speech_hours", "{:.3f}"),
            ("Average SNR (dB)", "avg_snr_db", "{:.2f}"),
            ("Average clip duration (s)", "avg_clip_duration_s", "{:.1f}"),
            ("Quality score (0-3)", "quality_score", "{:.2f}")]
    lines = [f"  {'metric':<28} {'Raw Video Dataset':>20} {'YouTube Long-form':>20}"]
    lines.append("  " + "-" * 70)
    for label, key, fmt in rows:
        lines.append(f"  {label:<28} {fmt.format(base[key]):>20} {fmt.format(yt[key]):>20}")
    lines.append("")
    lines.append(f"  Voice-cloning suitability (raw videos)      : {suitability(base, cfg)}")
    lines.append(f"  Voice-cloning suitability (YouTube long-form): {suitability(yt, cfg)}")
    return "\n".join(lines)


# --- STEP 7: recommendation -----------------------------------------------------

RECOMMENDATIONS = {
    "A": "YouTube long-form videos are sufficient for production voice cloning.",
    "B": "Use YouTube videos together with the clean recordings.",
    "C": "Use only the clean recordings.",
}


def recommend(yt: Dict[str, float], base: Dict[str, float],
              cfg: V2Config) -> Tuple[str, List[str]]:
    """Deterministic A/B/C decision from the measured metrics."""
    yt_quality_ok = (yt["accepted_clips"] > 0
                     and yt["avg_snr_db"] >= cfg.min_avg_snr_db
                     and yt["quality_score"] >= cfg.min_avg_quality_rank)
    yt_h, base_h = yt["accepted_speech_hours"], base["accepted_speech_hours"]

    reasons = [
        f"YouTube long-form: {yt_h:.3f} h accepted speech, avg SNR "
        f"{yt['avg_snr_db']:.1f} dB, quality score {yt['quality_score']:.2f} "
        f"({yt['accepted_clips']:.0f} clips)",
        f"Raw video dataset: {base_h:.3f} h accepted speech, avg SNR "
        f"{base['avg_snr_db']:.1f} dB, quality score {base['quality_score']:.2f} "
        f"({base['accepted_clips']:.0f} clips)",
        f"Assessment bands: sufficient >= {cfg.sufficient_speech_hours:.2f} h, "
        f"usable >= {cfg.usable_speech_hours:.2f} h, "
        f"min avg SNR {cfg.min_avg_snr_db:.0f} dB, min quality rank "
        f"{cfg.min_avg_quality_rank:.1f} (good)",
    ]

    if yt_quality_ok and yt_h >= cfg.sufficient_speech_hours:
        reasons.append(
            f"YouTube long-form alone clears the sufficiency band "
            f"({yt_h:.3f} h >= {cfg.sufficient_speech_hours:.2f} h) at acceptable quality.")
        return "A", reasons
    if yt_quality_ok and yt_h >= cfg.usable_speech_hours:
        reasons.append(
            f"YouTube long-form is high quality but below the sufficiency band "
            f"({yt_h:.3f} h < {cfg.sufficient_speech_hours:.2f} h); combining it with "
            f"the clean recordings ({base_h:.3f} h) maximises usable speech.")
        return "B", reasons
    if yt_quality_ok and yt_h > 0 and yt_h + base_h > base_h:
        reasons.append(
            f"YouTube long-form contributes little ({yt_h:.3f} h < "
            f"{cfg.usable_speech_hours:.2f} h) but passes quality; it can still "
            f"supplement the clean recordings.")
        return "B", reasons
    reasons.append(
        "YouTube long-form does not pass the quality/volume assessment; "
        "rely on the clean recordings.")
    return "C", reasons


def format_recommendation(letter: str, reasons: List[str]) -> str:
    lines = [f"  RECOMMENDATION {letter}) {RECOMMENDATIONS[letter]}", ""]
    lines += [f"  - {r}" for r in reasons]
    return "\n".join(lines)
