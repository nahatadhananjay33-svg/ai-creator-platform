"""Deterministic configuration for the V3 clean-recording evaluation.

Only V3-specific values live here (paths, sampling, readiness-score bands and
weights used to *assess* the dataset). The Voice Dataset Builder's acceptance
thresholds are untouched.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from production.voice_dataset.config import Config as _VoiceConfig

DEFAULT_RAW = Path(r"D:\AI_CREATOR_DATA\Tanshi\clean_recordings\raw")
DEFAULT_OUTPUT = Path(r"D:\AI_CREATOR_DATA\Tanshi\clean_recordings\voice_dataset")
DEFAULT_WORKSPACE = Path(r"D:\AI_CREATOR_DATA\Tanshi\_workspace_clean")
DEFAULT_BASELINE = Path(r"D:\AI_CREATOR_DATA\Tanshi\voice_dataset")  # raw phone recordings
DEFAULT_DOWNLOADS = Path.home() / "Downloads"

_V = _VoiceConfig()


@dataclass(frozen=True)
class V3Config:
    creator: str = "tanshi"
    sample_size: int = 20            # STEP 4: random clips inspected per bucket
    seed: int = 20260714
    # --- suitability bands (assessment only; same spirit as Phase V2) ---------
    sufficient_speech_hours: float = 1.0
    usable_speech_hours: float = 0.25
    min_avg_snr_db: float = _V.snr_good            # 18 dB
    # --- readiness score bands (all measured, deterministic) ------------------
    snr_full_marks_db: float = _V.snr_excellent    # 25 dB -> 100
    snr_floor_db: float = _V.snr_fair              # 10 dB -> 0
    noise_floor_quiet_dbfs: float = _V.noise_low_below    # -55 dBFS -> 100
    noise_floor_loud_dbfs: float = _V.noise_high_above    # -40 dBFS -> 0
    loudness_ideal_low_dbfs: float = -27.0         # comfortable speech band
    loudness_ideal_high_dbfs: float = -14.0
    loudness_hard_low_dbfs: float = _V.loudness_too_quiet  # -35 -> 0
    loudness_hard_high_dbfs: float = _V.loudness_too_loud  # -6  -> 0
    speech_ratio_full: float = 0.70                # >= 70% speech -> 100
    speech_ratio_floor: float = _V.low_speech_ratio  # 0.40 -> 0
    sample_rate_full_hz: int = 44100               # >= 44.1 kHz -> 100
    sample_rate_floor_hz: int = 16000
    # weights for the overall /100 (sum = 1.0)
    w_recording_quality: float = 0.20
    w_noise_level: float = 0.15
    w_speech_consistency: float = 0.15
    w_single_speaker: float = 0.15
    w_pronunciation: float = 0.10
    w_microphone: float = 0.10
    w_naturalness: float = 0.15
