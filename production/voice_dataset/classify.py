"""Content classification (Step 4).

A deterministic decision tree over measured signals — duration, platform,
speech ratio, music, and the (heuristic) speaker estimate. Not an ML classifier;
labels are best-effort and reproducible.
"""
from __future__ import annotations

from .config import Config
from .models import AudioMeta, Classification, Detection, Platform


def classify(meta: AudioMeta, det: Detection, platform: Platform, cfg: Config) -> Classification:
    dur = meta.duration
    speech_ratio = (meta.speech_duration / dur) if dur > 0 else 0.0

    # No speech at all -> music if there's a bed, else unknown.
    if not det.has_speech:
        return Classification.MUSIC_ONLY if det.has_music else Classification.UNKNOWN

    # Speech present but dominated by a music bed.
    if speech_ratio < cfg.music_only_speech_ratio and det.has_music:
        return Classification.MUSIC_ONLY

    # Very short, music-driven or sparse-speech clips.
    if dur <= cfg.meme_max_s and (det.has_music or speech_ratio < cfg.low_speech_ratio):
        return Classification.MEME

    # Conversational (multi-speaker) forms.
    if det.multi_speaker and det.has_speech:
        if dur > cfg.interview_max_s:
            return Classification.PODCAST
        if dur > cfg.short_max_s:
            return Classification.INTERVIEW

    # Short single-clip forms.
    if dur <= cfg.short_max_s:
        if (platform == Platform.INSTAGRAM and speech_ratio < 0.5
                and meta.silence_pct > 0.4):
            return Classification.CAROUSEL_VIDEO
        if det.has_speech:
            return Classification.SHORT_REEL
        return Classification.UNKNOWN

    # Longer single-speaker forms.
    if det.has_speech:
        if dur <= cfg.talking_head_max_s:
            return Classification.TALKING_HEAD
        return Classification.LONG_FORM

    return Classification.UNKNOWN
