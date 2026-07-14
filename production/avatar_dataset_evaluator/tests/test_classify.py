"""Classification decision logic (deterministic, no video needed)."""
from __future__ import annotations

from production.avatar_dataset_evaluator.classify import composite_score, evaluate
from production.avatar_dataset_evaluator.config import Config
from production.avatar_dataset_evaluator.models import VideoMeta, VisualAnalysis

CFG = Config()


def _meta(dur=10.0, w=1080, h=1920):
    return VideoMeta("v.mp4", dur, w, h, 30.0, round(w / h, 3), "portrait",
                     50.0, "h264", 5_000_000, int(dur * 30), "")


def _va(**over):
    d = dict(face_visibility_pct=90.0, avg_face_size_pct=5.0, frontal_pct=90.0,
             profile_pct=10.0, face_view="frontal", head_rotation="near_frontal",
             lighting_mean=120.0, lighting_consistency=0.9, camera_stability=0.95,
             motion_blur=300.0, occlusion_pct=5.0, eye_visibility_pct=80.0,
             mouth_visibility_pct=60.0, speaking_pct=40.0, walking_pct=0.0,
             stationary_pct=100.0, camera_movement=0.05, scene_changes=0,
             time_of_day="morning", setting="indoor?", expression="talking")
    d.update(over)
    return VisualAnalysis(**d)


def test_clean_frontal_accepted():
    q, acc, ar, rr, s = evaluate(_meta(), _va(), CFG)
    assert acc is True and q.rank >= CFG.accept_min_quality_rank and s > 0


def test_no_face_rejected():
    q, acc, ar, rr, s = evaluate(_meta(), _va(face_visibility_pct=5.0), CFG)
    assert not acc and "no visible face" in rr


def test_too_short():
    _, _, _, rr, _ = evaluate(_meta(dur=1.0), _va(), CFG)
    assert "too short" in rr


def test_very_dark_and_bright():
    assert "very dark" in evaluate(_meta(), _va(lighting_mean=20.0), CFG)[3]
    assert "very bright" in evaluate(_meta(), _va(lighting_mean=230.0), CFG)[3]


def test_low_resolution():
    assert "low resolution" in evaluate(_meta(w=320, h=240), _va(), CFG)[3]


def test_extreme_rotation():
    assert "extreme head rotation" in evaluate(_meta(), _va(profile_pct=90.0, frontal_pct=10.0), CFG)[3]


def test_too_shaky():
    assert "too shaky" in evaluate(_meta(), _va(camera_stability=0.1), CFG)[3]


def test_score_monotonic():
    hi = composite_score(_meta(), _va(), CFG)
    lo = composite_score(_meta(), _va(face_visibility_pct=30.0, motion_blur=10.0), CFG)
    assert hi > lo
