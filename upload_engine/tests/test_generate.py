"""Metadata generation tests (Phase C18) — hermetic, deterministic, no APIs."""
from __future__ import annotations

import pytest

from upload_engine.assistant import (
    REQUIRED_FIELDS,
    ReelSummary,
    UploadAssistant,
    UploadConfig,
    UploadMetadata,
    generate_metadata,
)
from upload_engine.assistant.text import build_hashtags, clamp, hashtagify, thumbnail_text


# ---- summary mining ---------------------------------------------------------

def test_summary_mines_storyboard(summary):
    assert summary.title.startswith("Why investing")
    assert summary.template == "real_estate"
    assert summary.narration[0].startswith("Buying property")
    assert "real estate" in summary.keywords          # deduped, order preserved
    assert summary.cta_lines == ("Follow for more real-estate tips.",)
    assert summary.duration_s == 42.0 and summary.aspect == "9:16"


def test_summary_hook_falls_back_to_first_narration():
    from upload_engine.tests.conftest import StubScene, StubStoryboard
    sb = StubStoryboard(hook="", scenes=(StubScene("First spoken line."),))
    assert ReelSummary.from_storyboard(sb).hook == "First spoken line."


# ---- the eight outputs ------------------------------------------------------

def test_all_required_fields_present_and_nonempty(summary):
    md = generate_metadata(summary)
    assert isinstance(md, UploadMetadata)
    assert md.missing_fields() == ()
    assert md.is_complete
    for name in REQUIRED_FIELDS:
        value = getattr(md, name)
        assert value, f"{name} came out empty"


def test_youtube_title_respects_limit(summary):
    md = generate_metadata(summary, config=UploadConfig(youtube_title_max=30))
    assert len(md.youtube_title) <= 30


def test_instagram_caption_respects_limit(summary):
    md = generate_metadata(summary, config=UploadConfig(instagram_caption_max=120))
    assert len(md.instagram_caption) <= 120


def test_hashtags_are_topical_then_template(summary):
    md = generate_metadata(summary, template="real_estate")
    # keyword-derived tags lead
    assert md.hashtags[0] == "#realestate"
    # template vertical tags are present too
    assert "#property" in md.hashtags
    assert all(h.startswith("#") for h in md.hashtags)


def test_facebook_and_linkedin_carry_fewer_hashtags(summary):
    cfg = UploadConfig(facebook_hashtag_max=3, linkedin_hashtag_max=2)
    md = generate_metadata(summary, config=cfg)
    assert md.facebook_caption.count("#") <= 3
    assert md.linkedin_post.count("#") <= 2
    assert "Key takeaways:" in md.linkedin_post


def test_thumbnail_text_is_short_and_upper(summary):
    md = generate_metadata(summary, template="real_estate")
    assert md.thumbnail_text == md.thumbnail_text.upper()
    assert 1 <= len(md.thumbnail_text.split()) <= 4


def test_suggested_filename_is_slug_mp4(summary):
    md = generate_metadata(summary)
    assert md.suggested_filename.endswith(".mp4")
    assert md.suggested_filename == md.suggested_filename.lower()
    assert " " not in md.suggested_filename


def test_hook_not_duplicated_when_it_is_the_first_narration():
    # The mock provider uses the hook as the first scene's narration.
    from upload_engine.tests.conftest import StubScene, StubStoryboard
    sb = StubStoryboard(
        hook="Start earlier than you think.",
        scenes=(StubScene("Start earlier than you think.", keywords=("money",)),
                StubScene("Compounding does the heavy lifting.")),
    )
    md = generate_metadata(ReelSummary.from_storyboard(sb))
    # the hook line appears exactly once in the YouTube description
    assert md.youtube_description.count("Start earlier than you think.") == 1


def test_template_shapes_ctas(summary):
    md = generate_metadata(summary, template="real_estate")
    assert "real-estate" in md.youtube_description.lower()
    assert md.template == "real_estate"


def test_unknown_template_falls_back_to_general(summary):
    md = generate_metadata(summary, template="not_a_vertical")
    assert md.template == "general"
    assert md.is_complete


# ---- robustness: sparse / empty inputs never yield empty outputs ------------

def test_minimal_summary_still_complete():
    md = generate_metadata(ReelSummary(title="", prompt="", template=""))
    assert md.is_complete, md.missing_fields()
    assert md.suggested_filename == "reel.mp4"
    assert md.thumbnail_text  # falls back to config default


def test_summary_with_only_prompt():
    md = generate_metadata(ReelSummary(prompt="Five tips for better sleep"))
    assert md.youtube_title == "Five tips for better sleep"
    assert md.is_complete


# ---- determinism ------------------------------------------------------------

def test_generation_is_deterministic(summary):
    a = generate_metadata(summary).to_dict()
    b = generate_metadata(summary).to_dict()
    assert a == b


def test_assistant_facade_matches_function(summary):
    a = UploadAssistant().generate(summary).to_dict()
    b = generate_metadata(summary).to_dict()
    assert a == b


def test_assistant_from_storyboard(storyboard):
    md = UploadAssistant().generate_from_storyboard(storyboard, duration_s=42.0,
                                                    aspect="9:16")
    assert md.is_complete
    assert md.template == "real_estate"


# ---- text helpers -----------------------------------------------------------

def test_hashtagify():
    assert hashtagify("Real Estate") == "#realestate"
    assert hashtagify("  ") == ""
    assert hashtagify("100% Free!") == "#100free"


def test_clamp_word_boundary():
    assert clamp("hello world foo", 100) == "hello world foo"
    out = clamp("hello world foo bar", 12)
    assert len(out) <= 12 and out.endswith("…")


def test_build_hashtags_dedup_and_limit():
    tags = build_hashtags(["real estate", "real estate"], ["property", "reels"], limit=3)
    assert tags == ("#realestate", "#property", "#reels")


def test_thumbnail_fallback_when_no_words():
    assert thumbnail_text("", "", max_words=4, fallback="watch now") == "WATCH NOW"


def test_config_validates():
    with pytest.raises(ValueError):
        UploadConfig(youtube_title_max=0)
