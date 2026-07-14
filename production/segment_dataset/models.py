"""Typed models for segment-level dataset records."""
from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class Segment:
    """A planned speech segment inside a source recording (sample domain)."""
    start_s: float
    end_s: float

    @property
    def duration(self) -> float:
        return self.end_s - self.start_s


@dataclass
class SegmentRecord:
    """One row of the production dataset — the persisted result for a segment."""
    id: int
    source_file: str          # original recording filename
    source_kind: str          # clean_mic | raw_phone | youtube | instagram
    segment_file: str         # exported WAV basename
    start_s: float
    end_s: float
    duration: float
    speech_duration: float
    quality: str
    accepted: bool
    reason: str               # acceptance summary or exact rejection reason
    snr_db: float
    loudness_dbfs: float
    noise_floor_dbfs: float
    noise_estimate: str       # low | moderate | high
    has_music: bool
    multi_speaker_confidence: float   # 0..1, heuristic (segment f0 IQR)
    f0_iqr_hz: float
    sample_rate: int
    audio_path: str

    def as_dict(self) -> dict:
        return asdict(self)


SEGMENT_COLUMNS = [
    "id", "source_file", "source_kind", "segment_file", "start_s", "end_s",
    "duration", "speech_duration", "quality", "accepted", "reason", "snr_db",
    "loudness_dbfs", "noise_floor_dbfs", "noise_estimate", "has_music",
    "multi_speaker_confidence", "f0_iqr_hz", "sample_rate", "audio_path",
]
