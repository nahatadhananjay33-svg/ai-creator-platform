"""STEPS 8-11: merged statistics, seeded inspection, report, recommendation."""
from __future__ import annotations

import random
from collections import Counter, defaultdict
from typing import Dict, List, Tuple

from .config import V4Config


def _mean(xs: List[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def dataset_stats(records: List[dict], n_sources: int) -> dict:
    acc = [r for r in records if r["accepted"]]
    rej = [r for r in records if not r["accepted"]]
    return {
        "n_sources": n_sources,
        "n_segments": len(records),
        "accepted_segments": len(acc),
        "rejected_segments": len(rej),
        "accepted_pct": round(100.0 * len(acc) / len(records), 1) if records else 0.0,
        "rejected_pct": round(100.0 * len(rej) / len(records), 1) if records else 0.0,
        "accepted_hours": round(sum(r["duration"] for r in acc) / 3600.0, 3),
        "rejected_hours": round(sum(r["duration"] for r in rej) / 3600.0, 3),
        "accepted_speech_hours": round(sum(r["speech_duration"] for r in acc) / 3600.0, 3),
        "avg_snr_db": round(_mean([r["snr_db"] for r in acc]), 2),
        "avg_loudness_dbfs": round(_mean([r["loudness_dbfs"] for r in acc]), 2),
        "avg_duration_s": round(_mean([r["duration"] for r in acc]), 1),
        "noise_distribution": dict(Counter(r["noise_estimate"] for r in acc)),
        "avg_noise_floor_dbfs": round(_mean([r["noise_floor_dbfs"] for r in acc]), 1),
        "top_rejection_reasons": Counter(r["reason"] for r in rej).most_common(8),
    }


def format_stats(s: dict) -> str:
    lines = [f"  Source recordings     : {s['n_sources']}",
             f"  Segments evaluated    : {s['n_segments']}",
             f"  Accepted segments     : {s['accepted_segments']} ({s['accepted_pct']:.1f}%)",
             f"  Rejected segments     : {s['rejected_segments']} ({s['rejected_pct']:.1f}%)",
             f"  Accepted hours        : {s['accepted_hours']:.3f} "
             f"(speech {s['accepted_speech_hours']:.3f})",
             f"  Rejected hours        : {s['rejected_hours']:.3f}",
             f"  Avg SNR (accepted)    : {s['avg_snr_db']:.2f} dB",
             f"  Avg loudness          : {s['avg_loudness_dbfs']:.2f} dBFS",
             f"  Avg segment duration  : {s['avg_duration_s']:.1f} s",
             f"  Noise floors (accept) : {s['avg_noise_floor_dbfs']:.1f} dBFS avg, "
             f"{s['noise_distribution']}"]
    if s["top_rejection_reasons"]:
        lines.append("  Top rejection reasons :")
        for reason, count in s["top_rejection_reasons"]:
            lines.append(f"    - {reason} ({count})")
    return "\n".join(lines)


def source_contribution(records: List[dict]) -> List[dict]:
    by_kind: Dict[str, List[dict]] = defaultdict(list)
    for r in records:
        by_kind[r["source_kind"]].append(r)
    rows = []
    for kind in sorted(by_kind):
        rs = by_kind[kind]
        acc = [r for r in rs if r["accepted"]]
        rows.append({
            "kind": kind,
            "sources": len({r["source_file"] for r in rs}),
            "segments": len(rs),
            "accepted": len(acc),
            "accepted_minutes": round(sum(r["duration"] for r in acc) / 60.0, 1),
            "avg_snr_db": round(_mean([r["snr_db"] for r in acc]), 1),
        })
    return rows


def format_contribution(rows: List[dict]) -> str:
    lines = [f"  {'source':<12} {'files':>6} {'segments':>9} {'accepted':>9} "
             f"{'acc.min':>8} {'avg SNR':>8}",
             "  " + "-" * 58]
    for r in rows:
        lines.append(f"  {r['kind']:<12} {r['sources']:>6} {r['segments']:>9} "
                     f"{r['accepted']:>9} {r['accepted_minutes']:>8.1f} "
                     f"{r['avg_snr_db']:>8.1f}")
    if not rows:
        lines.append("  (no segments)")
    return "\n".join(lines)


# --- STEP 9 -----------------------------------------------------------------------

def sample_segments(records: List[dict], n: int, seed: int) -> Tuple[List[dict], List[dict]]:
    rng = random.Random(seed)
    acc = sorted((r for r in records if r["accepted"]), key=lambda r: r["segment_file"])
    rej = sorted((r for r in records if not r["accepted"]), key=lambda r: r["segment_file"])
    return (rng.sample(acc, min(n, len(acc))), rng.sample(rej, min(n, len(rej))))


def verify_sample(sample: List[dict], cfg: V4Config) -> Dict[str, str]:
    """Programmatic verification proxies for STEP 9 (no listening possible)."""
    import os.path
    if not sample:
        return {"segments": "0", "duration_in_band": "n/a", "files_exist": "n/a",
                "speech_ratio_ok": "n/a"}
    tol = 1.0 + 2.0 * cfg.pad_ms / 1000.0
    in_band = sum(1 for r in sample
                  if cfg.min_segment_s * 0.5 <= r["duration"] <= cfg.max_segment_s * 1.1 + tol)
    exist = sum(1 for r in sample if os.path.exists(r["audio_path"]))
    speech_ok = sum(1 for r in sample
                    if r["duration"] and r["speech_duration"] / r["duration"] >= 0.5)
    n = len(sample)
    return {"segments": str(n),
            "duration_in_band": f"{in_band}/{n}",
            "files_exist": f"{exist}/{n}",
            "speech_ratio_ok": f"{speech_ok}/{n}"}


def format_inspection(sample: List[dict], bucket: str, checks: Dict[str, str]) -> str:
    lines = [f"  {bucket} sample ({len(sample)} segments) - "
             f"duration in band {checks['duration_in_band']}, files exist "
             f"{checks['files_exist']}, speech-ratio>=0.5 {checks['speech_ratio_ok']}",
             f"  {'segment':<52} {'dur(s)':>7} {'SNR':>6} {'conf':>5}  reason",
             "  " + "-" * 110]
    for r in sample:
        lines.append(f"  {r['segment_file'][:52]:<52} {r['duration']:>7.1f} "
                     f"{r['snr_db']:>6.1f} {r['multi_speaker_confidence']:>5.2f}  "
                     f"{r['reason'][:60]}")
    if not sample:
        lines.append("  (none)")
    return "\n".join(lines)


# --- STEPS 10+11 ----------------------------------------------------------------------

def readiness_estimate(s: dict, cfg: V4Config) -> Tuple[str, str]:
    """(verdict sentence, detail) for production sufficiency."""
    hours = s["accepted_hours"]
    if hours >= cfg.sufficient_speech_hours and s["avg_snr_db"] >= cfg.accept_min_snr_db:
        return ("YES - the dataset is sufficient for production voice cloning.",
                f"{hours:.2f} h of accepted segments at avg SNR "
                f"{s['avg_snr_db']:.1f} dB meets the >= {cfg.sufficient_speech_hours:.1f} h "
                f"/ >= {cfg.accept_min_snr_db:.0f} dB target.")
    missing_h = max(0.0, cfg.sufficient_speech_hours - hours)
    return ("NOT YET - more clean speech is required.",
            f"{hours:.2f} h accepted vs the {cfg.sufficient_speech_hours:.1f} h target: "
            f"approximately {missing_h * 60.0:.0f} more minutes of accepted speech "
            f"are needed.")


def extra_recording_estimate(records: List[dict], missing_hours: float) -> str:
    """Minutes of NEW clean-mic recording needed, using the measured yield."""
    if missing_hours <= 0:
        return "No additional recording required."
    clean = [r for r in records if r["source_kind"] == "clean_mic"]
    acc_h = sum(r["duration"] for r in clean if r["accepted"]) / 3600.0
    src_h = (max(r["end_s"] for r in clean) / 3600.0) if clean else 0.0
    if acc_h > 0 and src_h > 0:
        yield_ratio = acc_h / src_h
        need_min = missing_hours / yield_ratio * 60.0
        return (f"Measured clean-mic yield is {yield_ratio * 100.0:.0f}% "
                f"(accepted per recorded minute), so record approximately "
                f"{need_min:.0f} more minutes with the same microphone/room.")
    return (f"Record approximately {missing_hours * 60.0 / 0.6:.0f} more minutes "
            f"assuming a 60% accept yield (no measured clean-mic yield available).")
