"""Dependency-free PCM helpers for the streaming layer.

Linear-interpolation resampling is deliberately simple: telephony targets
(8/16 kHz) are far below synthesis rates (22-24 kHz), where interpolation
quality is adequate for voice. Offline/content audio should stay at the
engine-native rate (no resampling) or be exported via FFmpeg.
"""
from __future__ import annotations

import array

from foundation.shared_utils import WavData
from voice_engine.interfaces import AudioChunk


def to_mono(wav: WavData) -> WavData:
    """Downmix interleaved stereo to mono by channel averaging."""
    if wav.channels == 1:
        return wav
    mono = array.array(
        "h",
        (
            (wav.samples[i] + wav.samples[i + 1]) // 2
            for i in range(0, len(wav.samples) - 1, wav.channels)
        ),
    )
    return WavData(samples=mono, sample_rate=wav.sample_rate, channels=1)


def resample(wav: WavData, target_rate: int) -> WavData:
    """Linear-interpolation resample of mono 16-bit PCM."""
    if target_rate <= 0:
        raise ValueError(f"target_rate must be positive, got {target_rate}")
    wav = to_mono(wav)
    if wav.sample_rate == target_rate or not len(wav.samples):
        return WavData(samples=wav.samples, sample_rate=target_rate, channels=1)
    src = wav.samples
    n_out = max(1, int(round(len(src) * target_rate / wav.sample_rate)))
    step = (len(src) - 1) / (n_out - 1) if n_out > 1 else 0.0
    out = array.array("h", bytes(2 * n_out))
    for i in range(n_out):
        pos = i * step
        left = int(pos)
        frac = pos - left
        right = min(left + 1, len(src) - 1)
        out[i] = int(src[left] * (1.0 - frac) + src[right] * frac)
    return WavData(samples=out, sample_rate=target_rate, channels=1)


def resample_pcm_bytes(pcm_s16le: bytes, source_rate: int, target_rate: int) -> bytes:
    """Resample raw mono s16le bytes (streaming chunk payloads)."""
    if source_rate == target_rate:
        return pcm_s16le
    samples = array.array("h")
    samples.frombytes(pcm_s16le)
    wav = WavData(samples=samples, sample_rate=source_rate, channels=1)
    return resample(wav, target_rate).samples.tobytes()


def wav_to_chunks(
    wav: WavData,
    chunk_ms: int,
    start_index: int = 0,
    final: bool = True,
) -> list[AudioChunk]:
    """Slice mono PCM into fixed-duration :class:`AudioChunk` frames.

    ``final`` marks the last produced chunk; pass ``False`` when more audio
    (e.g. the next sentence) will follow.
    """
    if chunk_ms <= 0:
        raise ValueError(f"chunk_ms must be positive, got {chunk_ms}")
    wav = to_mono(wav)
    raw = wav.samples.tobytes()
    bytes_per_chunk = max(2, int(wav.sample_rate * chunk_ms / 1000) * 2)
    pieces = [raw[i : i + bytes_per_chunk] for i in range(0, len(raw), bytes_per_chunk)] or [b""]
    return [
        AudioChunk(
            pcm_s16le=piece,
            sample_rate=wav.sample_rate,
            chunk_index=start_index + i,
            is_final=final and i == len(pieces) - 1,
        )
        for i, piece in enumerate(pieces)
    ]
