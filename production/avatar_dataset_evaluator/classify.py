"""Per-clip classification: composite score, quality band, reject reasons."""
from __future__ import annotations

from typing import Tuple

from .config import Config
from .models import Quality, VideoMeta, VisualAnalysis


def composite_score(meta: VideoMeta, va: VisualAnalysis, cfg: Config) -> float:
    """0-100 avatar-suitability score from the key factors (deterministic weights)."""
    face = min(1.0, va.face_visibility_pct / 60.0)
    size = min(1.0, va.avg_face_size_pct / 8.0)
    frontal = va.frontal_pct / 100.0
    sharp = min(1.0, va.motion_blur / 300.0)
    light = (1.0 if cfg.very_dark_below < va.lighting_mean < cfg.very_bright_above else 0.3)
    light *= max(0.3, va.lighting_consistency)
    stab = va.camera_stability
    side = min(meta.width, meta.height)
    res = 1.0 if side >= 720 else 0.6 if side >= 480 else 0.2
    eyes = va.eye_visibility_pct / 100.0
    score = 100 * (0.24 * face + 0.16 * size + 0.16 * frontal + 0.12 * sharp
                   + 0.10 * light + 0.10 * stab + 0.06 * res + 0.06 * eyes)
    return round(score, 1)


def evaluate(meta: VideoMeta, va: VisualAnalysis, cfg: Config) -> Tuple[Quality, bool, str, str, float]:
    """Return (quality, accepted, accept_reason, reject_reason, score)."""
    has_face = va.face_visibility_pct >= cfg.no_face_below_pct
    side = min(meta.width, meta.height)
    reasons = []
    if meta.duration and meta.duration < cfg.min_duration_s:
        reasons.append("too short")
    if not has_face:
        reasons.append("no visible face")
    if has_face and va.avg_face_size_pct < cfg.face_too_small_pct:
        reasons.append("face too small")
    if va.motion_blur and va.motion_blur < cfg.heavy_blur_below:
        reasons.append("heavy blur")
    if va.profile_pct >= cfg.extreme_rotation_profile_pct and has_face:
        reasons.append("extreme head rotation")
    if has_face and va.occlusion_pct >= cfg.occlusion_covered_pct:
        reasons.append("face covered")
    if 0 < va.lighting_mean < cfg.very_dark_below:
        reasons.append("very dark")
    if va.lighting_mean > cfg.very_bright_above:
        reasons.append("very bright")
    if 0 < side < cfg.low_res_min_side:
        reasons.append("low resolution")
    if va.camera_stability < cfg.too_shaky_below:
        reasons.append("too shaky")

    score = composite_score(meta, va, cfg)

    if reasons:
        return Quality.REJECT, False, "", "; ".join(reasons), score

    if score >= cfg.excellent_min:
        q = Quality.EXCELLENT
    elif score >= cfg.good_min:
        q = Quality.GOOD
    elif score >= cfg.usable_min:
        q = Quality.USABLE
    elif score >= cfg.poor_min:
        q = Quality.POOR
    else:
        q = Quality.REJECT

    if q.rank >= cfg.accept_min_quality_rank:
        return q, True, (f"score {score:.0f}; face {va.face_visibility_pct:.0f}%; "
                         f"frontal {va.frontal_pct:.0f}%"), "", score
    return q, False, "", f"quality {q.value} (score {score:.0f})", score
