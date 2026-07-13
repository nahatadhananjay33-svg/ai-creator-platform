"""Deterministic configuration for the voice dataset builder.

Every threshold that influences classification, scoring, or the accept/reject
decision lives here so runs are reproducible and auditable. No value is learned
or randomized.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# Recognised input extensions.
AUDIO_EXTS = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".wma"}
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".flv", ".ts"}
MEDIA_EXTS = AUDIO_EXTS | VIDEO_EXTS


@dataclass(frozen=True)
class Paths:
    """The production_assets/tanshi/voice/* tree."""
    root: Path

    @property
    def voice(self) -> Path: return self.root / "voice"
    @property
    def raw(self) -> Path: return self.voice / "raw"
    @property
    def raw_instagram(self) -> Path: return self.raw / "instagram"
    @property
    def raw_youtube(self) -> Path: return self.raw / "youtube"
    @property
    def extracted(self) -> Path: return self.voice / "extracted"
    @property
    def accepted(self) -> Path: return self.voice / "accepted"
    @property
    def rejected(self) -> Path: return self.voice / "rejected"
    @property
    def metadata(self) -> Path: return self.voice / "metadata"

    def ensure(self) -> "Paths":
        for p in (self.raw_instagram, self.raw_youtube, self.extracted,
                  self.accepted, self.rejected, self.metadata):
            p.mkdir(parents=True, exist_ok=True)
        return self

    @classmethod
    def for_creator(cls, base: Path, creator: str = "tanshi") -> "Paths":
        return cls(root=Path(base) / creator)


@dataclass(frozen=True)
class Config:
    # --- framing (analysis) ---------------------------------------------------
    frame_ms: float = 30.0            # analysis frame size
    silence_floor_dbfs: float = -40.0 # frames quieter than this are "silence"
    speech_min_run_ms: float = 150.0  # drop voiced runs shorter than this
    speech_merge_gap_ms: float = 300.0 # bridge silences shorter than this

    # --- acceptance gates -----------------------------------------------------
    min_speech_seconds: float = 3.0   # need at least this much speech to accept
    max_silence_pct: float = 0.85     # reject if mostly silence
    accept_min_quality_rank: int = 2  # accept only GOOD (2) or EXCELLENT (3)

    # --- SNR -> quality bands (dB) --------------------------------------------
    snr_excellent: float = 25.0
    snr_good: float = 18.0
    snr_fair: float = 10.0

    # --- loudness sanity (dBFS) -----------------------------------------------
    loudness_too_quiet: float = -35.0
    loudness_too_loud: float = -6.0   # near clipping

    # --- noise estimate bands (dBFS of noise floor) ---------------------------
    noise_low_below: float = -55.0    # quieter floor than this => "low"
    noise_high_above: float = -40.0   # louder floor than this  => "high"

    # --- music / speaker heuristics -------------------------------------------
    music_gap_energy_db: float = 12.0 # energy in non-speech frames this far above
                                      # the noise floor suggests a music bed
    music_min_ratio: float = 0.20     # fraction of non-speech frames "musical"
    multi_speaker_f0_iqr_hz: float = 55.0  # wide pitch spread => possibly >1 speaker

    # --- classification durations (seconds) -----------------------------------
    short_max_s: float = 90.0
    meme_max_s: float = 30.0
    talking_head_max_s: float = 600.0
    interview_max_s: float = 1800.0
    music_only_speech_ratio: float = 0.15
    low_speech_ratio: float = 0.40

    def base_dir(self) -> Path:
        """Where production_assets lives (env override for tests/CI)."""
        env = os.environ.get("VOICE_DATASET_BASE")
        if env:
            return Path(env)
        return Path("production_assets")
