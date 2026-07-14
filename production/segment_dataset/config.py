"""Deterministic configuration for segment-level dataset generation.

Quality bands are reused from the existing builder's config so V4 stays
consistent with every earlier phase; only segmentation geometry and the two
relaxed policies (speaker confidence, noise-as-masking) are new.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict

from production.voice_dataset.config import Config as VoiceConfig

DEFAULT_OUTPUT = Path(r"D:\AI_CREATOR_DATA\Tanshi\production_voice_dataset")
DEFAULT_WORKSPACE = Path(r"D:\AI_CREATOR_DATA\Tanshi\_workspace_segments")

DEFAULT_SOURCES: Dict[str, Path] = {
    "clean_mic": Path(r"D:\AI_CREATOR_DATA\Tanshi\clean_recordings\raw"),
    "raw_phone": Path(r"D:\AI_CREATOR_DATA\Tanshi\raw_videos"),
    "youtube": Path(r"D:\AI_CREATOR_DATA\Tanshi\youtube_longform"),
    "instagram": Path(r"D:\DJ_projects\ai_creator_platform\production_assets\tanshi\media\instagram"),
}

_V = VoiceConfig()


@dataclass(frozen=True)
class V4Config:
    # --- VAD (frame geometry reused from the builder) --------------------------
    frame_ms: float = _V.frame_ms                    # 30 ms analysis frames
    silence_floor_dbfs: float = _V.silence_floor_dbfs  # -40 dBFS hard floor
    vad_snr_margin_db: float = 8.0     # adaptive floor: noise_floor + margin
    vad_min_run_ms: float = _V.speech_min_run_ms       # 150 ms min voiced run
    vad_merge_gap_ms: float = 400.0    # bridge pauses shorter than this
    # gaps longer than vad_merge_gap_ms end a speech region ("long pauses")

    # --- segmentation ----------------------------------------------------------
    min_segment_s: float = 5.0         # target band
    max_segment_s: float = 20.0
    join_gap_max_s: float = 1.0        # merge neighbouring regions across pauses <= this
    pad_ms: float = 150.0              # context pad so words are not clipped
    min_keep_speech_s: float = _V.min_speech_seconds   # 3 s — below this a segment
    #                                    is rejected as too short (builder's gate)

    # --- STEP 4/5 policies -------------------------------------------------------
    # Noise: reject only when it masks speech, i.e. segment SNR below the
    # builder's "good" band. Steady ambience with clear speech passes.
    accept_min_snr_db: float = _V.snr_good           # 18 dB
    # Speaker: reject only on HIGH confidence. Confidence maps segment f0 IQR
    # from the builder's old whole-file threshold (55 Hz -> 0.0) up to a spread
    # that natural 5-20 s solo speech does not reach (160 Hz -> 1.0).
    speaker_iqr_zero_hz: float = _V.multi_speaker_f0_iqr_hz   # 55 Hz
    speaker_iqr_full_hz: float = 160.0
    speaker_reject_confidence: float = 0.8
    # Loudness sanity: wide by design — normalization is trivial downstream;
    # reject only clipping or near-digital-silence.
    loudness_max_dbfs: float = -3.0
    loudness_min_dbfs: float = -45.0

    # --- assessment ---------------------------------------------------------------
    sufficient_speech_hours: float = 1.0
    sample_size: int = 50
    seed: int = 20260714

    voice: VoiceConfig = field(default_factory=VoiceConfig)
