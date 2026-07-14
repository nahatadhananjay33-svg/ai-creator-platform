"""Deterministic configuration for the V2 long-form validation run.

Only V2-specific values live here (paths, sampling, suitability bands used to
*assess* the datasets). The acceptance thresholds of the Voice Dataset Builder
are untouched — this phase never overrides ``production.voice_dataset.config``.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# Suitability bands reference the builder's own SNR quality bands
# (snr_good = 18 dB) so the assessment stays consistent with acceptance.
from production.voice_dataset.config import Config as _VoiceConfig

DEFAULT_SOURCE = Path(r"D:\AI_CREATOR_DATA\Tanshi\youtube_longform")
DEFAULT_OUTPUT = Path(r"D:\AI_CREATOR_DATA\Tanshi\youtube_voice_dataset")
DEFAULT_WORKSPACE = Path(r"D:\AI_CREATOR_DATA\Tanshi\_workspace_youtube")
DEFAULT_BASELINE = Path(r"D:\AI_CREATOR_DATA\Tanshi\voice_dataset")


@dataclass(frozen=True)
class V2Config:
    creator: str = "tanshi"
    sample_size: int = 30            # STEP 5: random clips inspected per bucket
    seed: int = 20260714             # fixed seed -> reproducible inspection
    # --- suitability assessment (reporting only; NOT acceptance thresholds) ---
    sufficient_speech_hours: float = 1.0   # enough accepted speech to train alone
    usable_speech_hours: float = 0.25      # enough to contribute alongside others
    min_avg_snr_db: float = _VoiceConfig().snr_good  # 18 dB — "good" band
    min_avg_quality_rank: float = 2.0      # >= good on the poor..excellent scale
