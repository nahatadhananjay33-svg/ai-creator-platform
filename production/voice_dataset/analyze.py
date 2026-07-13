"""Deterministic audio analysis (Steps 3 & 5).

Pure DSP over decoded PCM — no ML, no GPU, no randomness. Reads a WAV with the
standard library, then measures duration/loudness/silence/speech and derives
heuristic content signals (speech, music bed, multiple speakers, noise).

Heuristics are intentionally simple and documented; they are estimates, not
classifier outputs. Everything is reproducible for a given file + Config.
"""
from __future__ import annotations

import wave
from pathlib import Path
from typing import Tuple

import numpy as np

from .config import Config
from .models import AudioMeta, Detection

_EPS = 1e-10


def load_wav(path: Path) -> Tuple[np.ndarray, int, int, int]:
    """Return (mono float32 in [-1, 1], sample_rate, channels, sample_width_bytes)."""
    with wave.open(str(path), "rb") as w:
        sr = w.getframerate()
        ch = max(1, w.getnchannels())
        sw = w.getsampwidth()
        raw = w.readframes(w.getnframes())

    if len(raw) == 0:
        return np.zeros(0, dtype=np.float32), sr, ch, sw

    if sw == 1:                                  # unsigned 8-bit
        data = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    elif sw == 2:                                # signed 16-bit
        data = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    elif sw == 3:                                # signed 24-bit (packed)
        b = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3).astype(np.int32)
        vals = (b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16))
        vals = np.where(vals & 0x800000, vals - 0x1000000, vals)
        data = vals.astype(np.float32) / 8388608.0
    elif sw == 4:                                # signed 32-bit
        data = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
    else:
        raise ValueError(f"unsupported WAV sample width: {sw} bytes")

    if ch > 1:
        usable = (len(data) // ch) * ch
        data = data[:usable].reshape(-1, ch).mean(axis=1)
    return data.astype(np.float32), sr, ch, sw


def _frame_dbfs(samples: np.ndarray, frame_len: int) -> np.ndarray:
    """Per-frame RMS in dBFS for non-overlapping frames."""
    if frame_len <= 0 or samples.size == 0:
        return np.zeros(0, dtype=np.float32)
    n = (samples.size // frame_len) * frame_len
    if n == 0:
        frames = samples[np.newaxis, :]
    else:
        frames = samples[:n].reshape(-1, frame_len)
    rms = np.sqrt(np.mean(frames.astype(np.float64) ** 2, axis=1) + _EPS)
    return (20.0 * np.log10(rms + _EPS)).astype(np.float64)


def _smooth_voiced(voiced: np.ndarray, min_run: int, merge_gap: int) -> np.ndarray:
    """Bridge short silences, then drop short voiced runs (both in frames)."""
    v = voiced.copy()
    if v.size == 0:
        return v
    # bridge gaps: silence runs shorter than merge_gap between voiced -> voiced
    i = 0
    n = v.size
    while i < n:
        if not v[i]:
            j = i
            while j < n and not v[j]:
                j += 1
            left = i > 0 and v[i - 1]
            right = j < n and v[j]
            if left and right and (j - i) < merge_gap:
                v[i:j] = True
            i = j
        else:
            i += 1
    # drop short voiced runs
    i = 0
    while i < n:
        if v[i]:
            j = i
            while j < n and v[j]:
                j += 1
            if (j - i) < min_run:
                v[i:j] = False
            i = j
        else:
            i += 1
    return v


def _estimate_f0(samples: np.ndarray, sr: int, voiced_idx: np.ndarray, frame_len: int,
                 fmin: float = 80.0, fmax: float = 320.0, max_frames: int = 400) -> np.ndarray:
    """Autocorrelation f0 estimate over (a deterministic subsample of) voiced frames."""
    if voiced_idx.size == 0:
        return np.zeros(0)
    step = max(1, voiced_idx.size // max_frames)
    picks = voiced_idx[::step]
    lag_min = max(1, int(sr / fmax))
    lag_max = max(lag_min + 1, int(sr / fmin))
    out = []
    for fi in picks:
        s = samples[fi * frame_len: fi * frame_len + frame_len].astype(np.float64)
        if s.size < lag_max + 1:
            continue
        s = s - s.mean()
        ac = np.correlate(s, s, mode="full")[s.size - 1:]
        if ac[0] <= _EPS:
            continue
        seg = ac[lag_min:lag_max]
        if seg.size == 0:
            continue
        lag = lag_min + int(np.argmax(seg))
        # require a reasonably periodic frame
        if ac[lag] / ac[0] < 0.3:
            continue
        out.append(sr / lag)
    return np.asarray(out, dtype=np.float64)


def analyze(path: Path, cfg: Config) -> Tuple[AudioMeta, Detection]:
    """Measure metadata (Step 3) and detect content signals (Step 5)."""
    samples, sr, ch, sw = load_wav(Path(path))
    duration = samples.size / sr if sr else 0.0
    bitrate = int(sr * ch * sw * 8)

    frame_len = max(1, int(sr * cfg.frame_ms / 1000.0))
    frame_dur = frame_len / sr if sr else 0.0
    dbfs = _frame_dbfs(samples, frame_len)

    if dbfs.size == 0:
        meta = AudioMeta(duration=duration, sample_rate=sr, channels=ch, bitrate=bitrate,
                         silence_pct=1.0, speech_duration=0.0, loudness_dbfs=-120.0)
        det = Detection(has_speech=False, multi_speaker=False, has_music=False,
                        noise_floor_dbfs=-120.0, snr_db=0.0, noise_estimate="low")
        return meta, det

    voiced_raw = dbfs >= cfg.silence_floor_dbfs
    silence_pct = float(np.mean(~voiced_raw))

    min_run = max(1, int(round(cfg.speech_min_run_ms / 1000.0 / frame_dur))) if frame_dur else 1
    merge_gap = max(1, int(round(cfg.speech_merge_gap_ms / 1000.0 / frame_dur))) if frame_dur else 1
    voiced = _smooth_voiced(voiced_raw, min_run, merge_gap)
    speech_duration = float(np.sum(voiced) * frame_dur)

    rms_all = float(np.sqrt(np.mean(samples.astype(np.float64) ** 2) + _EPS))
    loudness_dbfs = float(20.0 * np.log10(rms_all + _EPS))

    noise_floor = float(np.percentile(dbfs, 10))
    voiced_levels = dbfs[voiced] if np.any(voiced) else dbfs
    speech_level = float(np.median(voiced_levels))
    snr_db = float(max(0.0, speech_level - noise_floor))

    if noise_floor < cfg.noise_low_below:
        noise_estimate = "low"
    elif noise_floor > cfg.noise_high_above:
        noise_estimate = "high"
    else:
        noise_estimate = "moderate"

    has_speech = speech_duration >= 0.5 and float(np.mean(voiced)) >= 0.05

    # music bed: sustained energy during non-speech frames, well above the floor
    nonspeech = ~voiced
    if np.any(nonspeech):
        musical = nonspeech & (dbfs > (noise_floor + cfg.music_gap_energy_db))
        music_ratio = float(np.sum(musical) / max(1, np.sum(nonspeech)))
    else:
        music_ratio = 0.0
    has_music = music_ratio >= cfg.music_min_ratio

    # multiple speakers: wide pitch spread across voiced frames (rough heuristic)
    voiced_idx = np.nonzero(voiced)[0]
    f0 = _estimate_f0(samples, sr, voiced_idx, frame_len)
    if f0.size >= 8:
        iqr = float(np.percentile(f0, 75) - np.percentile(f0, 25))
        multi_speaker = iqr >= cfg.multi_speaker_f0_iqr_hz
    else:
        multi_speaker = False

    meta = AudioMeta(duration=duration, sample_rate=sr, channels=ch, bitrate=bitrate,
                     silence_pct=silence_pct, speech_duration=speech_duration,
                     loudness_dbfs=loudness_dbfs)
    det = Detection(has_speech=has_speech, multi_speaker=multi_speaker, has_music=has_music,
                    noise_floor_dbfs=noise_floor, snr_db=snr_db, noise_estimate=noise_estimate)
    return meta, det
