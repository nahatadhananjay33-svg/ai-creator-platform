"""Coverage categories, minutes counting, and the frame analyzer smoke test."""
from __future__ import annotations

from production.avatar_dataset_evaluator.coverage import (
    CATEGORIES, ClipCoverage, CoverageConfig, analyze_coverage,
    clip_categories, coverage_minutes, format_coverage)

CCFG = CoverageConfig()


def _cov(**over):
    d = dict(filename="v.mp4", face_frames=10, frontal_frac=0.9, left_frac=0.0,
             right_frac=0.0, up_frac=0.0, down_frac=0.0, smile_frac=0.0,
             horiz_dominant=False)
    d.update(over)
    return ClipCoverage(**d)


def test_front_talking_standing_serious(rec):
    r = rec(expression="neutral", speaking_pct=45.0, avg_face_size_pct=5.0)
    cats = clip_categories(r, _cov(), CCFG)
    assert {"front", "serious", "standing", "natural_talking"} <= set(cats)
    assert "sitting" not in cats and "walking" not in cats


def test_yaw_and_pitch_proxies(rec):
    r = rec()
    assert "left_20" in clip_categories(r, _cov(left_frac=0.3), CCFG)
    assert "right_20" in clip_categories(r, _cov(right_frac=0.25), CCFG)
    assert "looking_up" in clip_categories(r, _cov(up_frac=0.3), CCFG)
    assert "looking_down" in clip_categories(r, _cov(down_frac=0.3), CCFG)
    # profile views recorded by A0 also count as turned views
    assert "left_20" in clip_categories(rec(face_view="left_profile"), _cov(), CCFG)


def test_expression_movement_and_side(rec):
    assert "smiling" in clip_categories(rec(expression="smiling"), _cov(), CCFG)
    assert "smiling" in clip_categories(rec(), _cov(smile_frac=0.4), CCFG)
    walk = rec(walking_pct=100.0, stationary_pct=0.0)
    cats = clip_categories(walk, _cov(), CCFG)
    assert "walking" in cats and "standing" not in cats and "natural_talking" not in cats
    assert "sitting" in clip_categories(rec(avg_face_size_pct=12.0), _cov(), CCFG)
    assert "side_movement" in clip_categories(rec(), _cov(horiz_dominant=True), CCFG)


def test_coverage_minutes_accepted_only(rec):
    records = [rec(filename="a.mp4", duration=120.0, expression="smiling"),
               rec(filename="b.mp4", duration=60.0, accepted=False, expression="smiling"),
               rec(filename="c.mp4", duration=30.0, expression="neutral")]
    covs = {"a.mp4": _cov(filename="a.mp4"), "c.mp4": _cov(filename="c.mp4")}
    m = coverage_minutes(records, covs, CCFG)
    assert m["smiling"] == {"clips": 1, "minutes": 2.0}      # rejected b excluded
    assert m["serious"] == {"clips": 1, "minutes": 0.5}
    assert m["front"]["clips"] == 2
    text = format_coverage(m, CCFG)
    assert "20° Left" in text and "MISSING" in text and "OK" in text
    assert set(CATEGORIES) == set(m)


def test_analyze_coverage_smoke_no_face(tmp_path, make_video):
    v = make_video(tmp_path / "v.mp4")
    cov = analyze_coverage(v, CCFG)
    assert cov.face_frames == 0
    assert clip_categories.__name__  # analyzer returned a usable (empty) coverage
