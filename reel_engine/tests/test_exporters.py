"""Export-profile math tests (Phase C2). Pure, hermetic — no FFmpeg."""
from __future__ import annotations

import pytest

from reel_engine.exporters import (
    all_profiles,
    fit_box,
    get_profile,
    profile_names,
)


def test_registry_has_three_required_profiles():
    assert profile_names() == ["landscape_16x9", "reel_9x16", "square_1x1"]
    assert get_profile("reel_9x16").aspect == "9:16"
    assert get_profile("square_1x1").aspect == "1:1"
    assert get_profile("landscape_16x9").aspect == "16:9"


def test_unknown_profile_raises():
    with pytest.raises(KeyError):
        get_profile("tiktok_ultrawide")


def test_all_profiles_have_even_dimensions():
    for p in all_profiles():
        assert p.width % 2 == 0 and p.height % 2 == 0


def test_fit_box_letterboxes_portrait_into_landscape():
    # 1080x1920 (9:16) into 1920x1080 (16:9): must scale to fit height, pad sides.
    box = fit_box(1080, 1920, 1920, 1080, mode="pad")
    assert box.scaled_h == 1080                      # limited by height
    assert box.scaled_w == 608                       # 1080*(1080/1920)=607.5 -> even 608
    assert box.pad_x > 0 and box.pad_y == 0
    # scaled fits within target
    assert box.scaled_w + 2 * box.pad_x <= 1920 + 1
    assert all(v % 2 == 0 for v in (box.scaled_w, box.scaled_h, box.pad_x, box.pad_y))


def test_fit_box_same_aspect_no_padding():
    box = fit_box(1080, 1920, 540, 960, mode="pad")   # exact 9:16 downscale
    assert (box.scaled_w, box.scaled_h) == (540, 960)
    assert box.pad_x == 0 and box.pad_y == 0


def test_fit_box_rejects_nonpositive():
    with pytest.raises(ValueError):
        fit_box(0, 10, 10, 10)
