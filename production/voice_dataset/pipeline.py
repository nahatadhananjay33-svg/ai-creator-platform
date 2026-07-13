"""Orchestration: run every media item through Steps 1-7 and route files."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import List, Optional

from .analyze import analyze
from .classify import classify
from .config import Config, Paths
from .decide import decide
from .extract import ExtractionError, extract_audio
from .models import Decision, Record
from .providers import LocalFolderProvider
from .providers.base import MediaProvider
from .score import score


def _round(x: float, n: int) -> float:
    return round(float(x), n)


def build_dataset(paths: Paths, cfg: Config,
                  provider: Optional[MediaProvider] = None) -> List[Record]:
    """Discover -> extract -> analyze -> classify -> score -> decide -> route."""
    paths.ensure()
    provider = provider or LocalFolderProvider(paths)

    records: List[Record] = []
    for idx, item in enumerate(provider.discover(), start=1):
        try:
            wav = extract_audio(Path(item.path), paths.extracted)
        except ExtractionError as e:
            records.append(Record(
                id=idx, platform=item.platform.value, source=item.source,
                filename=item.filename, duration=0.0, speech_duration=0.0,
                classification="unknown", quality="poor", accepted=False,
                reason=f"extract failed: {e}", audio_path=""))
            continue

        meta, det = analyze(wav, cfg)
        cl = classify(meta, det, item.platform, cfg)
        q = score(meta, det, cfg)
        decision, reason = decide(meta, det, cl, q, cfg)
        accepted = decision == Decision.ACCEPT

        dest = (paths.accepted if accepted else paths.rejected) / wav.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(wav, dest)

        records.append(Record(
            id=idx, platform=item.platform.value, source=item.source,
            filename=item.filename,
            duration=_round(meta.duration, 3),
            speech_duration=_round(meta.speech_duration, 3),
            classification=cl.value, quality=q.value,
            accepted=accepted, reason=reason, audio_path=str(dest),
            sample_rate=meta.sample_rate, channels=meta.channels, bitrate=meta.bitrate,
            silence_pct=_round(meta.silence_pct, 4),
            loudness_dbfs=_round(meta.loudness_dbfs, 2),
            snr_db=_round(det.snr_db, 2),
            has_speech=det.has_speech, multi_speaker=det.multi_speaker,
            has_music=det.has_music, noise_estimate=det.noise_estimate))
    return records
