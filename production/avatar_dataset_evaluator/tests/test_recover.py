"""Face-crop recovery logic (deterministic; ffmpeg/detection covered on real data)."""
from __future__ import annotations

from production.avatar_dataset_evaluator.recover_crops import compute_crop, find_face_too_small


def test_find_face_too_small(rec):
    recs = [rec(filename="a.mov", accepted=False, reject_reason="face too small"),
            rec(filename="b.mov", accepted=False, reject_reason="heavy blur"),
            rec(filename="c.mov", accepted=True, reject_reason=""),
            rec(filename="d.mov", accepted=False, reject_reason="face too small; face covered")]
    got = {r.filename for r in find_face_too_small(recs)}
    assert got == {"a.mov", "d.mov"}


def test_crop_preserves_aspect_and_enlarges():
    boxes = [(910, 490, 100, 100)] * 5           # small centered face in 1920x1080
    c = compute_crop(1920, 1080, boxes)
    assert c is not None
    x, y, w, h = c
    assert abs((w / h) - (1920 / 1080)) < 0.05    # aspect preserved
    assert w < 1920 and h < 1080                  # actually cropped
    # face occupies a much larger fraction of the crop than of the original frame
    assert (100 * 100) / (w * h) > 5 * (100 * 100) / (1920 * 1080)
    # crop stays within frame bounds
    assert 0 <= x and 0 <= y and x + w <= 1920 and y + h <= 1080


def test_crop_none_when_face_already_large():
    boxes = [(200, 100, 1500, 880)] * 5           # face already fills the frame
    assert compute_crop(1920, 1080, boxes) is None


def test_crop_none_with_too_few_detections():
    assert compute_crop(1920, 1080, [(0, 0, 100, 100)]) is None
