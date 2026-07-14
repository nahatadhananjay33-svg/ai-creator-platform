"""STEP 6: Voice Cloning Readiness Score (0-100, deterministic).

Every sub-score is a documented arithmetic mapping over values the Voice
Dataset Builder already measured and persisted (SNR, loudness, silence,
speech ratio, heuristic flags, sample rate). No ML, no re-analysis, no
randomness — the same dataset always scores the same. Sub-scores that have no
direct acoustic measurement (pronunciation consistency, naturalness) are
explicit PROXIES computed from the closest measured signals and labelled as
such in the report.

Multi-clip datasets are aggregated by duration-weighted mean so one long clip
counts for more than many short ones.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from .config import V3Config

NOISE_ESTIMATE_SCORE = {"low": 100.0, "moderate": 55.0, "high": 15.0}


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def _linear(x: float, x0: float, x1: float) -> float:
    """0 at x0, 100 at x1 (works for descending ranges too), clamped."""
    if x1 == x0:
        return 100.0 if x >= x1 else 0.0
    return _clamp((x - x0) / (x1 - x0) * 100.0)


@dataclass
class Readiness:
    recording_quality: float
    noise_level: float
    speech_consistency: float
    single_speaker: float
    pronunciation: float          # proxy: loudness inside the comfortable band
    microphone: float
    naturalness: float            # proxy: no music bed, speech present, human pausing
    overall: float


def _score_clip(r: dict, cfg: V3Config) -> Dict[str, float]:
    duration = float(r.get("duration") or 0.0)
    speech_ratio = (float(r.get("speech_duration") or 0.0) / duration) if duration else 0.0
    loudness = float(r.get("loudness_dbfs") or -100.0)

    recording_quality = _linear(float(r.get("snr_db") or 0.0),
                                cfg.snr_floor_db, cfg.snr_full_marks_db)
    noise_level = NOISE_ESTIMATE_SCORE.get(str(r.get("noise_estimate") or ""), 15.0)
    speech_consistency = _linear(speech_ratio, cfg.speech_ratio_floor, cfg.speech_ratio_full)
    single_speaker = 25.0 if r.get("multi_speaker") else 100.0

    # pronunciation proxy: stable, comfortable loudness. 100 inside the ideal
    # band, falling linearly to 0 at the builder's hard too-quiet/too-loud limits.
    if cfg.loudness_ideal_low_dbfs <= loudness <= cfg.loudness_ideal_high_dbfs:
        pronunciation = 100.0
    elif loudness < cfg.loudness_ideal_low_dbfs:
        pronunciation = _linear(loudness, cfg.loudness_hard_low_dbfs, cfg.loudness_ideal_low_dbfs)
    else:
        pronunciation = _linear(loudness, cfg.loudness_hard_high_dbfs, cfg.loudness_ideal_high_dbfs)

    microphone = _linear(float(r.get("sample_rate") or 0),
                         cfg.sample_rate_floor_hz, cfg.sample_rate_full_hz)
    if loudness > cfg.loudness_hard_high_dbfs:            # clipping-adjacent
        microphone = min(microphone, 30.0)

    naturalness = 100.0
    if r.get("has_music"):
        naturalness -= 40.0
    if not r.get("has_speech"):
        naturalness -= 30.0
    if float(r.get("silence_pct") or 0.0) > 0.60:
        naturalness -= 20.0                                # long dead air
    if speech_ratio > 0.95:
        naturalness -= 10.0                                # no human pausing at all
    naturalness = _clamp(naturalness)

    return {"recording_quality": recording_quality, "noise_level": noise_level,
            "speech_consistency": speech_consistency, "single_speaker": single_speaker,
            "pronunciation": pronunciation, "microphone": microphone,
            "naturalness": naturalness}


def readiness_score(records: List[dict], cfg: V3Config) -> Readiness:
    if not records:
        return Readiness(0, 0, 0, 0, 0, 0, 0, 0)
    weights = [max(float(r.get("duration") or 0.0), 1e-9) for r in records]
    total_w = sum(weights)
    agg: Dict[str, float] = {}
    for r, w in zip(records, weights):
        for k, v in _score_clip(r, cfg).items():
            agg[k] = agg.get(k, 0.0) + v * w / total_w

    overall = (agg["recording_quality"] * cfg.w_recording_quality
               + agg["noise_level"] * cfg.w_noise_level
               + agg["speech_consistency"] * cfg.w_speech_consistency
               + agg["single_speaker"] * cfg.w_single_speaker
               + agg["pronunciation"] * cfg.w_pronunciation
               + agg["microphone"] * cfg.w_microphone
               + agg["naturalness"] * cfg.w_naturalness)
    return Readiness(overall=round(overall, 1),
                     **{k: round(v, 1) for k, v in agg.items()})


def format_readiness(s: Readiness) -> str:
    rows: List[Tuple[str, float]] = [
        ("Recording quality (SNR)", s.recording_quality),
        ("Noise level", s.noise_level),
        ("Speech consistency", s.speech_consistency),
        ("Single-speaker confidence", s.single_speaker),
        ("Pronunciation consistency (proxy)", s.pronunciation),
        ("Microphone quality", s.microphone),
        ("Naturalness (proxy)", s.naturalness),
    ]
    lines = [f"  {'component':<36} {'score /100':>10}", "  " + "-" * 48]
    lines += [f"  {name:<36} {val:>10.1f}" for name, val in rows]
    lines.append("  " + "-" * 48)
    lines.append(f"  {'OVERALL READINESS':<36} {s.overall:>10.1f}")
    return "\n".join(lines)
