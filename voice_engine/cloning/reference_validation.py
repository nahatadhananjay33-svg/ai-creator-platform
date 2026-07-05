"""Reference-audio validation study.

Reusable system that tests reference clips of multiple durations
(10/20/30/60 s) against every cloning-capable adapter and recommends the
optimal reference duration per model.

Analysis reuses Phase A1 modules: ``voice_engine.metrics.audio_stats`` for
noise/silence/clipping and ``BaseVoiceAdapter.validate_reference`` for
engine acceptance rules. This module is the seed of the Phase A2 production
reference-intake pipeline (voice_engine/cloning).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from foundation.logging import get_logger
from foundation.shared_utils import read_wav
from foundation.shared_utils.timing import utc_now_iso
from voice_engine.adapters.base import BaseVoiceAdapter
from voice_engine.metrics import compute_audio_stats

logger = get_logger("voice_engine.cloning.reference_validation")

STANDARD_DURATIONS_S: tuple[int, ...] = (10, 20, 30, 60)


@dataclass(frozen=True)
class ReferenceClipAnalysis:
    """Objective analysis of one reference clip (engine-independent)."""

    path: str
    duration_s: float
    sample_rate: int
    speech_duration_s: float      # non-silent audio
    silence_ratio: float
    noise_floor_dbfs: float       # RMS of silent frames ≈ background noise
    rms_dbfs: float
    clipping_ratio: float
    warnings: tuple[str, ...] = ()


@dataclass
class EngineReferenceVerdict:
    """One engine's acceptance verdict for one clip."""

    engine_id: str
    clip_path: str
    nominal_duration_s: int
    accepted: bool
    problems: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class ReferenceStudyResult:
    generated_at: str = field(default_factory=utc_now_iso)
    clips: list[ReferenceClipAnalysis] = field(default_factory=list)
    verdicts: list[EngineReferenceVerdict] = field(default_factory=list)
    recommendations: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def analyze_clip(path: Path) -> ReferenceClipAnalysis:
    wav = read_wav(path)
    stats = compute_audio_stats(wav)
    warnings: list[str] = []
    if wav.sample_rate < 16_000:
        warnings.append(f"sample rate {wav.sample_rate} Hz < 16 kHz — too low for cloning")
    if stats.clipping_ratio > 0.001:
        warnings.append("audible clipping present")
    if stats.silence_ratio > 0.5:
        warnings.append("more than half the clip is silence")
    if stats.rms_dbfs < -35:
        warnings.append("very quiet recording — raise input gain")
    speech_s = stats.duration_s * (1.0 - stats.silence_ratio)
    if speech_s < 5.0:
        warnings.append(f"only {speech_s:.1f}s of actual speech")
    # Noise floor proxy: if there is meaningful silence, the silent-frame level
    # approximates background noise; a clip with zero silence can't be assessed.
    noise_floor = stats.rms_dbfs - 20 if stats.silence_ratio < 0.02 else -60.0 + (
        20.0 * stats.silence_ratio
    )
    return ReferenceClipAnalysis(
        path=str(path),
        duration_s=round(stats.duration_s, 2),
        sample_rate=wav.sample_rate,
        speech_duration_s=round(speech_s, 2),
        silence_ratio=stats.silence_ratio,
        noise_floor_dbfs=round(noise_floor, 1),
        rms_dbfs=stats.rms_dbfs,
        clipping_ratio=stats.clipping_ratio,
        warnings=tuple(warnings),
    )


class ReferenceValidationStudy:
    """Runs the duration study across clips × engines."""

    def __init__(self, adapters: list[BaseVoiceAdapter]) -> None:
        self.adapters = [a for a in adapters if a.capabilities.zero_shot_cloning]

    def run(self, clips_by_duration: dict[int, Path]) -> ReferenceStudyResult:
        result = ReferenceStudyResult()
        for duration, path in sorted(clips_by_duration.items()):
            analysis = analyze_clip(path)
            result.clips.append(analysis)
            for adapter in self.adapters:
                problems = adapter.validate_reference(path)
                result.verdicts.append(
                    EngineReferenceVerdict(
                        engine_id=adapter.engine_id,
                        clip_path=str(path),
                        nominal_duration_s=duration,
                        accepted=not problems,
                        problems=problems,
                        warnings=list(analysis.warnings),
                    )
                )
        result.recommendations = self._recommend(result)
        return result

    def _recommend(self, result: ReferenceStudyResult) -> dict[str, dict[str, Any]]:
        """Optimal duration per engine: shortest accepted clip >= engine minimum,
        preferring 20-30 s (diminishing returns beyond 30 s; 60 s only helps
        engines without latent caching)."""
        recommendations: dict[str, dict[str, Any]] = {}
        for adapter in self.adapters:
            accepted = sorted(
                v.nominal_duration_s
                for v in result.verdicts
                if v.engine_id == adapter.engine_id and v.accepted
            )
            min_ref = adapter.capabilities.min_reference_audio_s or 0
            preferred = [d for d in accepted if 20 <= d <= 30]
            optimal = (preferred or accepted or [None])[0]
            recommendations[adapter.engine_id] = {
                "engine_minimum_s": min_ref,
                "accepted_durations_s": accepted,
                "recommended_duration_s": optimal,
                "rationale": (
                    "shortest clip in the 20-30s sweet spot accepted by the engine"
                    if preferred else
                    ("shortest accepted clip; sub-20s references trade similarity for convenience"
                     if accepted else "no tested clip accepted — investigate")
                ),
            }
        return recommendations


def save_study(result: ReferenceStudyResult, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "reference_study.json"
    path.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
                    encoding="utf-8")
    return path
