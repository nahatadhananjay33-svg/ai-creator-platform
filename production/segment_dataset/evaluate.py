"""STEPS 3-6: independent evaluation and accept/reject decision per segment.

Metrics come from the existing builder's ``analyze()`` and ``score()`` run on
each exported segment WAV — the same measurements every earlier phase used.
Two policies differ from the whole-file builder, by design (Phase V4 spec):

Speaker policy — recordings are assumed to belong to one creator. The old
whole-file boolean (f0 IQR >= 55 Hz) is replaced by a CONFIDENCE in [0, 1]:
0 at 55 Hz (ordinary intonation) rising linearly to 1 at 160 Hz, a spread
natural 5-20 s solo speech does not reach. Only confidence >= 0.8 rejects.
Pitch variation, emotion, laughter, or loudness changes never reject.

Noise policy — steady background (fan/AC/traffic/ambience) never auto-rejects.
A segment is rejected for noise only when the noise actually MASKS the speech,
measured as segment SNR below the builder's "good" band (18 dB). The quality
label still reflects the builder's penalties, for reporting continuity.
"""
from __future__ import annotations

import wave
from pathlib import Path
from typing import Tuple

import numpy as np

from production.voice_dataset.analyze import (_estimate_f0, _frame_dbfs,
                                              _smooth_voiced, analyze, load_wav)
from production.voice_dataset.models import AudioMeta, Detection
from production.voice_dataset.score import score

from .config import V4Config
from .models import Segment, SegmentRecord


def write_segment_wav(samples: np.ndarray, sr: int, seg: Segment, path: Path) -> Path:
    """Export one mono 16-bit segment at the source sample rate."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lo, hi = int(seg.start_s * sr), min(int(seg.end_s * sr), samples.size)
    x = np.clip(samples[lo:hi], -1.0, 1.0)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((x * 32767.0).astype("<i2").tobytes())
    return path


def speaker_confidence(wav_path: Path, cfg: V4Config) -> Tuple[float, float]:
    """(confidence 0..1, f0 IQR Hz) for a segment via the builder's f0 estimator."""
    samples, sr, _, _ = load_wav(Path(wav_path))
    if sr <= 0 or samples.size == 0:
        return 0.0, 0.0
    frame_len = max(1, int(sr * cfg.frame_ms / 1000.0))
    frame_dur = frame_len / sr
    dbfs = _frame_dbfs(samples, frame_len)
    voiced = _smooth_voiced(
        dbfs >= cfg.silence_floor_dbfs,
        max(1, int(round(cfg.vad_min_run_ms / 1000.0 / frame_dur))),
        max(1, int(round(cfg.vad_merge_gap_ms / 1000.0 / frame_dur))))
    f0 = _estimate_f0(samples, sr, np.nonzero(voiced)[0], frame_len)
    if f0.size < 8:
        return 0.0, 0.0                      # not enough voiced evidence
    iqr = float(np.percentile(f0, 75) - np.percentile(f0, 25))
    span = cfg.speaker_iqr_full_hz - cfg.speaker_iqr_zero_hz
    confidence = max(0.0, min(1.0, (iqr - cfg.speaker_iqr_zero_hz) / span))
    return round(confidence, 3), round(iqr, 1)


def decide_segment(meta: AudioMeta, det: Detection, quality_label: str,
                   confidence: float, cfg: V4Config) -> Tuple[bool, str]:
    """V4 accept/reject with an exact reason. Order defines priority."""
    if not det.has_speech:
        return False, "no speech detected"
    if meta.speech_duration < cfg.min_keep_speech_s:
        return False, (f"segment too short ({meta.speech_duration:.1f}s speech "
                       f"< {cfg.min_keep_speech_s:.0f}s)")
    if meta.loudness_dbfs > cfg.loudness_max_dbfs:
        return False, f"clipping ({meta.loudness_dbfs:.1f} dBFS)"
    if meta.loudness_dbfs < cfg.loudness_min_dbfs:
        return False, f"too quiet ({meta.loudness_dbfs:.1f} dBFS)"
    if confidence >= cfg.speaker_reject_confidence:
        return False, f"overlapping speaker (confidence {confidence:.2f})"
    if det.snr_db < cfg.accept_min_snr_db:
        return False, (f"background noise masks speech "
                       f"(snr {det.snr_db:.1f} dB < {cfg.accept_min_snr_db:.0f} dB)")
    return True, f"clear speech - quality {quality_label} - snr {det.snr_db:.1f} dB"


def _segment_snr(wav_path: Path, source_noise_floor: float,
                 cfg: V4Config) -> float:
    """Speech level of THIS segment over the SOURCE recording's noise floor.

    Segments are speech-dense by construction, so the builder's per-file noise
    floor (10th percentile of the segment's own frames) would land on speech
    and collapse SNR to ~0. The room's floor does not change between segments —
    measure it once on the whole recording, measure speech level per segment.
    """
    samples, sr, _, _ = load_wav(Path(wav_path))
    if sr <= 0 or samples.size == 0:
        return 0.0
    frame_len = max(1, int(sr * cfg.frame_ms / 1000.0))
    dbfs = _frame_dbfs(samples, frame_len)
    if dbfs.size == 0:
        return 0.0
    voiced = dbfs >= max(cfg.silence_floor_dbfs, source_noise_floor + cfg.vad_snr_margin_db)
    speech_level = float(np.median(dbfs[voiced])) if np.any(voiced) else float(np.median(dbfs))
    return max(0.0, speech_level - source_noise_floor)


def _noise_label(noise_floor: float, cfg: V4Config) -> str:
    v = cfg.voice
    if noise_floor < v.noise_low_below:
        return "low"
    if noise_floor > v.noise_high_above:
        return "high"
    return "moderate"


def evaluate_segment(wav_path: Path, seg: Segment, source_file: str,
                     source_kind: str, seg_id: int, cfg: V4Config,
                     source_noise_floor: float | None = None) -> SegmentRecord:
    """Measure one exported segment and decide, reusing analyze()/score().

    ``source_noise_floor`` (dBFS, from the whole source recording) corrects the
    segment SNR as described in ``_segment_snr``; without it the builder's own
    per-file estimate is used unchanged.
    """
    meta, det = analyze(Path(wav_path), cfg.voice)
    if source_noise_floor is not None:
        det = Detection(
            has_speech=det.has_speech, multi_speaker=det.multi_speaker,
            has_music=det.has_music, noise_floor_dbfs=round(source_noise_floor, 2),
            snr_db=round(_segment_snr(wav_path, source_noise_floor, cfg), 2),
            noise_estimate=_noise_label(source_noise_floor, cfg))
    quality = score(meta, det, cfg.voice)
    confidence, iqr = speaker_confidence(wav_path, cfg)
    accepted, reason = decide_segment(meta, det, quality.value, confidence, cfg)
    return SegmentRecord(
        id=seg_id, source_file=source_file, source_kind=source_kind,
        segment_file=Path(wav_path).name,
        start_s=seg.start_s, end_s=seg.end_s,
        duration=round(meta.duration, 3),
        speech_duration=round(meta.speech_duration, 3),
        quality=quality.value, accepted=accepted, reason=reason,
        snr_db=round(det.snr_db, 2),
        loudness_dbfs=round(meta.loudness_dbfs, 2),
        noise_floor_dbfs=round(det.noise_floor_dbfs, 2),
        noise_estimate=det.noise_estimate, has_music=det.has_music,
        multi_speaker_confidence=confidence, f0_iqr_hz=iqr,
        sample_rate=meta.sample_rate, audio_path=str(wav_path))
