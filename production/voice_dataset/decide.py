"""Accept / reject decision with a human-readable reason (Step 7).

The target is a clean, single-speaker speech corpus, so multi-speaker and
music-bedded audio are rejected even when otherwise high quality. Order of the
checks defines reason priority.
"""
from __future__ import annotations

from typing import Tuple

from .config import Config
from .models import AudioMeta, Classification, Decision, Detection, Quality


def decide(meta: AudioMeta, det: Detection, classification: Classification,
           quality: Quality, cfg: Config) -> Tuple[Decision, str]:
    if not det.has_speech:
        return Decision.REJECT, "no speech detected"
    if classification == Classification.MUSIC_ONLY:
        return Decision.REJECT, "music only"
    if meta.speech_duration < cfg.min_speech_seconds:
        return Decision.REJECT, (f"insufficient speech "
                                 f"({meta.speech_duration:.1f}s < {cfg.min_speech_seconds:.0f}s)")
    if meta.silence_pct > cfg.max_silence_pct:
        return Decision.REJECT, f"mostly silence ({meta.silence_pct * 100:.0f}%)"
    if det.multi_speaker:
        return Decision.REJECT, "multiple speakers"
    if det.has_music:
        return Decision.REJECT, "background music present"
    if quality.rank < cfg.accept_min_quality_rank:
        return Decision.REJECT, (f"quality {quality.value} below threshold "
                                 f"(snr {det.snr_db:.1f} dB)")
    return Decision.ACCEPT, (f"clean speech - quality {quality.value} - "
                             f"snr {det.snr_db:.1f} dB")
