"""Quality scoring (Step 6).

Starts from an SNR band and applies deterministic penalties for out-of-range
loudness, excessive silence, a high noise floor, or a music bed. Returns an
ordered Quality label.
"""
from __future__ import annotations

from .config import Config
from .models import AudioMeta, Detection, Quality

_ORDER = [Quality.POOR, Quality.FAIR, Quality.GOOD, Quality.EXCELLENT]


def score(meta: AudioMeta, det: Detection, cfg: Config) -> Quality:
    if det.snr_db >= cfg.snr_excellent:
        base = Quality.EXCELLENT
    elif det.snr_db >= cfg.snr_good:
        base = Quality.GOOD
    elif det.snr_db >= cfg.snr_fair:
        base = Quality.FAIR
    else:
        base = Quality.POOR

    penalty = 0
    if meta.loudness_dbfs < cfg.loudness_too_quiet or meta.loudness_dbfs > cfg.loudness_too_loud:
        penalty += 1
    if meta.silence_pct > cfg.max_silence_pct:
        penalty += 1
    if det.noise_estimate == "high":
        penalty += 1
    if det.has_music:
        penalty += 1

    rank = max(0, base.rank - penalty)
    return _ORDER[rank]
