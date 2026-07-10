"""Upload-template registry tests (Phase C18) — hermetic, no APIs, no GPU."""
from __future__ import annotations

from upload_engine.templates import (
    UploadTemplate,
    available_templates,
    get_template,
)

REQUIRED_VERTICALS = {"real_estate", "finance", "education", "medical", "general"}


def test_all_required_verticals_present():
    assert REQUIRED_VERTICALS.issubset(set(available_templates()))


def test_get_template_returns_requested_vertical():
    t = get_template("real_estate")
    assert isinstance(t, UploadTemplate)
    assert t.name == "real_estate"
    assert t.emoji == "🏡"


def test_unknown_and_blank_fall_back_to_general():
    assert get_template("does_not_exist").name == "general"
    assert get_template("").name == "general"
    assert get_template(None).name == "general"


def test_every_template_has_nonempty_fields():
    for name in available_templates():
        t = get_template(name)
        assert t.emoji
        assert t.hashtags and all(t.hashtags)
        assert t.youtube_cta and t.instagram_cta
        assert t.facebook_cta and t.linkedin_cta
        assert t.thumbnail_max_words > 0
        assert t.hashtag_limit > 0


def test_hashtags_merge_vertical_first_then_defaults_deduped():
    t = get_template("real_estate")
    # vertical tags lead
    assert t.hashtags[0] == "realestate"
    # generic defaults are appended
    assert "reels" in t.hashtags and "trending" in t.hashtags
    # no duplicates
    assert len(t.hashtags) == len(set(t.hashtags))


def test_loading_is_deterministic():
    a = get_template("finance")
    b = get_template("finance")
    assert a == b


def test_templates_are_immutable():
    import dataclasses
    import pytest

    t = get_template("medical")
    with pytest.raises(dataclasses.FrozenInstanceError):
        t.emoji = "x"  # type: ignore[misc]
